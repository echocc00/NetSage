"""审计日志服务（v2.0 八章 + 十一章 11.2 + 等保三权分立）。

不可篡改：append-only + sha256(prev_hash + payload) 哈希链。
v0.5.0 修复（审查 P0/P1）：
- AuditService 此前全库零调用——审计链从未写入。现经 AuditSink 双实现
  （Db/内存）接入 changes/agents 生命周期（见 app.main lifespan 装配）。
- payload 补 ts 字段（此前改时间戳不影响哈希）。
- verify_chain 重算 sha256（此前只比对链式相等，改写记录内容不被发现）。
DB 层配合 migration 0002 的 INSERT ONLY + 0007 的 prev_hash 唯一约束
（并发分叉链由服务层 IntegrityError 重试兜底）。
"""
from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any, Protocol

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.audit import AuditLog

logger = get_logger("audit")

GENESIS = "genesis"
_MAX_CHAIN_RETRIES = 3


def _payload_hash(prev_hash: str, payload: str) -> str:
    return hashlib.sha256(f"{prev_hash}{payload}".encode()).hexdigest()


def _canonical_payload(
    *,
    ts: str,
    user_id: int | None,
    action: str,
    resource_type: str,
    resource_id: str | None,
    before: str | None,
    after: str | None,
    trace_id: str | None,
) -> str:
    return json.dumps(
        {
            "ts": ts,
            "user_id": user_id,
            "action": action,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "before": before,
            "after": after,
            "trace_id": trace_id,
        },
        ensure_ascii=False,
        sort_keys=True,
    )


class AuditService:
    """审计日志：append-only 记录所有读/写动作（v2.0 十一章）。"""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def _last_hash(self) -> str:
        """取链尾 self_hash（哈希链锚点）。"""
        result = await self.db.execute(
            select(AuditLog.self_hash).order_by(AuditLog.id.desc()).limit(1)
        )
        row = result.scalar_one_or_none()
        return row or GENESIS

    async def append(
        self,
        *,
        user_id: int | None,
        action: str,
        resource_type: str,
        resource_id: str | None = None,
        before: str | None = None,
        after: str | None = None,
        trace_id: str | None = None,
    ) -> AuditLog:
        """写入一条审计记录，self_hash = sha256(prev_hash + payload 含 ts)。

        prev_hash 唯一约束（migration 0007）下，并发追加触发
        IntegrityError 时重试（重读链尾重新计算），保证链线性。
        """
        for attempt in range(_MAX_CHAIN_RETRIES):
            prev_hash = await self._last_hash()
            ts = datetime.now(UTC).isoformat()
            payload = _canonical_payload(
                ts=ts,
                user_id=user_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                before=before,
                after=after,
                trace_id=trace_id,
            )
            entry = AuditLog(
                ts=ts,
                user_id=user_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                before=before,
                after=after,
                prev_hash=prev_hash,
                self_hash=_payload_hash(prev_hash, payload),
            )
            try:
                self.db.add(entry)
                await self.db.commit()
                logger.info("audit_appended", action=action, resource=resource_type)
                return entry
            except IntegrityError as e:
                await self.db.rollback()
                if attempt == _MAX_CHAIN_RETRIES - 1:
                    raise RuntimeError(f"审计链追加冲突重试耗尽（action={action}）") from e
                logger.warning("audit_chain_conflict_retry", attempt=attempt + 1)

        raise RuntimeError("unreachable")  # pragma: no cover

    async def verify_chain(self) -> bool:
        """校验哈希链完整性：链接性 + 逐条重算 sha256（防内容改写）。"""
        result = await self.db.execute(
            select(
                AuditLog.id,
                AuditLog.ts,
                AuditLog.user_id,
                AuditLog.action,
                AuditLog.resource_type,
                AuditLog.resource_id,
                AuditLog.before,
                AuditLog.after,
                AuditLog.prev_hash,
                AuditLog.self_hash,
            ).order_by(AuditLog.id)
        )
        rows = result.all()
        prev = GENESIS
        for row in rows:
            if row.prev_hash != prev:
                logger.error("audit_chain_broken", id=row.id, expected_prev=prev)
                return False
            payload = _canonical_payload(
                ts=row.ts,
                user_id=row.user_id,
                action=row.action,
                resource_type=row.resource_type,
                resource_id=row.resource_id,
                before=row.before,
                after=row.after,
                trace_id=None,  # trace_id 不落列，仅进 payload 哈希（写入侧同理）
            )
            if _payload_hash(prev, payload) != row.self_hash:
                logger.error("audit_hash_mismatch", id=row.id, action=row.action)
                return False
            prev = row.self_hash
        return True


async def verify_no_write_privileges(db: AsyncSession) -> bool:
    """校验 audit_logs 表无 UPDATE/DELETE 权限（migration 0002 保障）。"""
    from sqlalchemy import text

    result = await db.execute(
        text(
            "SELECT has_table_privilege(current_user, 'audit_logs', 'UPDATE') AS can_update,"
            "       has_table_privilege(current_user, 'audit_logs', 'DELETE') AS can_delete"
        )
    )
    row = result.one()
    return not row.can_update and not row.can_delete


# ===== AuditSink：路由层写入入口（DB / 内存双实现，启动装配）=====


class AuditSink(Protocol):
    """审计写入接口（changes/agents 生命周期调用）。"""

    @property
    def mode(self) -> str: ...

    async def append(
        self,
        *,
        user_id: int | None,
        action: str,
        resource_type: str,
        resource_id: str | None = None,
        before: str | None = None,
        after: str | None = None,
        trace_id: str | None = None,
    ) -> bool: ...

    async def verify(self) -> bool: ...


class DbAuditSink:
    """PostgreSQL 审计链（AuditService 包装，自管 session）。"""

    def __init__(self) -> None:
        from app.db import SessionLocal

        self._session_factory = SessionLocal

    @property
    def mode(self) -> str:
        return "db"

    async def append(self, **kwargs: Any) -> bool:
        async with self._session_factory() as db:
            await AuditService(db).append(**kwargs)
        return True

    async def verify(self) -> bool:
        async with self._session_factory() as db:
            return await AuditService(db).verify_chain()


class MemoryAuditSink:
    """内存审计链（无 DB 环境回退；同哈希链算法，重启即失，日志明示）。"""

    def __init__(self) -> None:
        self._entries: list[dict[str, Any]] = []

    @property
    def mode(self) -> str:
        return "memory"

    async def append(self, **kwargs: Any) -> bool:
        prev = self._entries[-1]["self_hash"] if self._entries else GENESIS
        for optional in ("resource_id", "before", "after", "trace_id"):
            kwargs.setdefault(optional, None)
        kwargs["ts"] = datetime.now(UTC).isoformat()
        payload = _canonical_payload(**kwargs)
        self._entries.append(
            {"fields": dict(kwargs), "prev_hash": prev, "self_hash": _payload_hash(prev, payload)}
        )
        return True

    async def verify(self) -> bool:
        prev = GENESIS
        for entry in self._entries:
            if entry["prev_hash"] != prev:
                return False
            payload = _canonical_payload(**entry["fields"])
            if _payload_hash(prev, payload) != entry["self_hash"]:
                return False
            prev = entry["self_hash"]
        return True


_sink: AuditSink = MemoryAuditSink()


def configure_audit_sink(sink: AuditSink) -> None:
    global _sink
    _sink = sink
    logger.info("audit_sink_configured", mode=sink.mode)


def get_audit_sink() -> AuditSink:
    return _sink
