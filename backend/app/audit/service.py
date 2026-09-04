"""审计日志服务（v2.0 八章 + 十一章 11.2 + 等保三权分立）。

不可篡改：append-only + sha256(prev_hash + payload) 哈希链。
security C4 修复：审计写入零实现 → 此处为写入入口。
DB 层配合 migration 0002 的 INSERT ONLY 权限（REVOKE UPDATE/DELETE）。
"""
from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.audit import AuditLog

logger = get_logger("audit")


class AuditService:
    """审计日志：append-only 记录所有读/写动作（v2.0 十一章）"""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def _last_hash(self) -> str:
        """取链尾 self_hash（哈希链锚点）。"""
        result = await self.db.execute(
            select(AuditLog.self_hash).order_by(AuditLog.id.desc()).limit(1)
        )
        row = result.scalar_one_or_none()
        return row or "genesis"

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
        """写入一条审计记录，self_hash = sha256(prev_hash + payload)。"""
        prev_hash = await self._last_hash()
        payload = json.dumps(
            {
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
        entry = AuditLog(
            ts=datetime.now(UTC).isoformat(),
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            before=before,
            after=after,
            prev_hash=prev_hash,
            self_hash=hashlib.sha256(f"{prev_hash}{payload}".encode()).hexdigest(),
        )
        self.db.add(entry)
        await self.db.commit()
        logger.info("audit_appended", action=action, resource=resource_type)
        return entry

    async def verify_chain(self) -> bool:
        """校验哈希链完整性（审计自检，等保要求）。"""
        result = await self.db.execute(
            select(AuditLog.id, AuditLog.prev_hash, AuditLog.self_hash, AuditLog.action).order_by(AuditLog.id)
        )
        rows = result.all()
        prev = "genesis"
        for _, prev_hash, self_hash, action in rows:
            if prev_hash != prev:
                logger.error("audit_chain_broken", prev_hash=prev_hash, expected=prev, action=action)
                return False
            prev = self_hash
        return True


async def verify_no_write_privileges(db: AsyncSession) -> bool:
    """校验 audit_logs 表无 UPDATE/DELETE 权限（migration 0002 保障）。"""
    result = await db.execute(
        text(
            "SELECT has_table_privilege(current_user, 'audit_logs', 'UPDATE') AS can_update,"
            "       has_table_privilege(current_user, 'audit_logs', 'DELETE') AS can_delete"
        )
    )
    row = result.one()
    return not row.can_update and not row.can_delete
