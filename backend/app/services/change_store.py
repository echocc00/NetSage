"""变更单存储：内存 / DB 双实现 + 启动装配（审查 P1 修复）。

变更单此前存进程内 dict（changes.py 模块级 `_changes`）——重启即失、
uvicorn 多 worker 下互相不可见（快照读空、审批 404）。现抽出存储层：
- MemoryChangeStore：无 DB 环境（单元测试/演示）回退，启动日志明示；
- DbChangeStore：change_requests / approvals / config_snapshots 表。
选择在 app.main lifespan 探测 DB 可达性后 configure_change_store()。
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Protocol

from app.core.logging import get_logger

logger = get_logger("change_store")


@dataclass
class ChangeRecord:
    """变更单（API 层交换结构，与 ORM 解耦）。"""

    id: int
    title: str
    nim: dict
    devices: list[dict]
    configs: dict[str, str]
    assertions: list[dict]
    status: str
    impact: dict
    created_by: int
    pipeline_result: dict | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "nim": self.nim,
            "devices": self.devices,
            "configs": self.configs,
            "assertions": self.assertions,
            "status": self.status,
            "impact": self.impact,
            "created_by": self.created_by,
            "pipeline_result": self.pipeline_result,
        }


@dataclass
class SnapshotMeta:
    device_id: int
    object_key: str
    config_hash: str
    config: str = ""


class ChangeStore(Protocol):
    """变更单 + 快照 + 审批记录存储接口。"""

    @property
    def mode(self) -> str: ...

    async def create(
        self,
        *,
        title: str,
        nim: dict,
        devices: list[dict],
        configs: dict[str, str],
        assertions: list[dict],
        impact: dict,
        created_by: int,
    ) -> ChangeRecord: ...

    async def get(self, change_id: int) -> ChangeRecord | None: ...

    async def update_status(
        self, change_id: int, status: str, pipeline_result: dict | None = None
    ) -> ChangeRecord | None: ...

    async def update_impact(self, change_id: int, impact: dict) -> ChangeRecord | None: ...

    async def list(self, limit: int = 50) -> list[ChangeRecord]: ...

    async def stats(self) -> dict: ...

    async def save_approval(
        self, change_id: int, approver_id: int, decision: str, comment: str = ""
    ) -> None: ...

    async def save_snapshot(
        self, change_id: int, device_id: int, object_key: str, config_hash: str, config: str
    ) -> None: ...

    async def load_snapshot(self, object_key: str) -> str: ...


class MemoryChangeStore:
    """进程内存储（测试/无 DB 环境回退；重启即失，启动日志明示）。"""

    def __init__(self) -> None:
        self._changes: dict[int, ChangeRecord] = {}
        self._counter = 0
        self._snapshots: dict[str, str] = {}

    @property
    def mode(self) -> str:
        return "memory"

    async def create(
        self,
        *,
        title: str,
        nim: dict,
        devices: list[dict],
        configs: dict[str, str],
        assertions: list[dict],
        impact: dict,
        created_by: int,
    ) -> ChangeRecord:
        self._counter += 1
        rec = ChangeRecord(
            id=self._counter,
            title=title,
            nim=nim,
            devices=devices,
            configs=configs,
            assertions=assertions,
            status="draft",
            impact=impact,
            created_by=created_by,
        )
        self._changes[rec.id] = rec
        return rec

    async def get(self, change_id: int) -> ChangeRecord | None:
        return self._changes.get(change_id)

    async def update_status(
        self, change_id: int, status: str, pipeline_result: dict | None = None
    ) -> ChangeRecord | None:
        rec = self._changes.get(change_id)
        if rec is None:
            return None
        rec.status = status
        if pipeline_result is not None:
            rec.pipeline_result = pipeline_result
        return rec

    async def update_impact(self, change_id: int, impact: dict) -> ChangeRecord | None:
        rec = self._changes.get(change_id)
        if rec is None:
            return None
        rec.impact.update(impact)
        return rec

    async def list(self, limit: int = 50) -> list[ChangeRecord]:
        return sorted(self._changes.values(), key=lambda r: r.id, reverse=True)[:limit]

    async def stats(self) -> dict:
        by_status: dict[str, int] = {}
        for rec in self._changes.values():
            by_status[rec.status] = by_status.get(rec.status, 0) + 1
        return {"total": len(self._changes), "by_status": by_status}

    async def save_approval(
        self, change_id: int, approver_id: int, decision: str, comment: str = ""
    ) -> None:
        # 内存模式不单独存审批表；审计链记录决策
        logger.info("approval_recorded", change_id=change_id, decision=decision, store="memory")

    async def save_snapshot(
        self, change_id: int, device_id: int, object_key: str, config_hash: str, config: str
    ) -> None:
        self._snapshots[object_key] = config

    async def load_snapshot(self, object_key: str) -> str:
        return self._snapshots.get(object_key, "")


class DbChangeStore:
    """PostgreSQL 存储（change_requests/approvals/config_snapshots）。"""

    def __init__(self) -> None:
        from app.db import SessionLocal

        self._session_factory = SessionLocal

    @property
    def mode(self) -> str:
        return "db"

    async def create(
        self,
        *,
        title: str,
        nim: dict,
        devices: list[dict],
        configs: dict[str, str],
        assertions: list[dict],
        impact: dict,
        created_by: int,
    ) -> ChangeRecord:
        from app.models.change import ChangeRequest

        async with self._session_factory() as db:
            row = ChangeRequest(
                title=title,
                intent=_dump(nim),
                devices=_dump(devices),
                configs=_dump(configs),
                assertions=_dump(assertions),
                impact=_dump(impact),
                status="draft",
                created_by=created_by,
            )
            db.add(row)
            await db.commit()
            await db.refresh(row)
            return _to_record(row)

    async def get(self, change_id: int) -> ChangeRecord | None:
        from sqlalchemy import select

        from app.models.change import ChangeRequest

        async with self._session_factory() as db:
            row = (await db.execute(select(ChangeRequest).where(ChangeRequest.id == change_id))).scalar_one_or_none()
            return _to_record(row) if row else None

    async def update_status(
        self, change_id: int, status: str, pipeline_result: dict | None = None
    ) -> ChangeRecord | None:
        from sqlalchemy import select

        from app.models.change import ChangeRequest

        async with self._session_factory() as db:
            row = (await db.execute(select(ChangeRequest).where(ChangeRequest.id == change_id))).scalar_one_or_none()
            if row is None:
                return None
            row.status = status
            if pipeline_result is not None:
                row.pipeline_result = _dump(pipeline_result)
            await db.commit()
            return _to_record(row)

    async def update_impact(self, change_id: int, impact: dict) -> ChangeRecord | None:
        from sqlalchemy import select

        from app.models.change import ChangeRequest

        async with self._session_factory() as db:
            row = (await db.execute(select(ChangeRequest).where(ChangeRequest.id == change_id))).scalar_one_or_none()
            if row is None:
                return None
            merged = _load(row.impact)
            merged.update(impact)
            row.impact = _dump(merged)
            await db.commit()
            return _to_record(row)

    async def list(self, limit: int = 50) -> list[ChangeRecord]:
        from sqlalchemy import select

        from app.models.change import ChangeRequest

        async with self._session_factory() as db:
            rows = (
                await db.execute(
                    select(ChangeRequest).order_by(ChangeRequest.id.desc()).limit(limit)
                )
            ).scalars().all()
            return [_to_record(r) for r in rows]

    async def stats(self) -> dict:
        from sqlalchemy import func, select

        from app.models.change import ChangeRequest

        async with self._session_factory() as db:
            rows = (
                await db.execute(
                    select(ChangeRequest.status, func.count()).group_by(ChangeRequest.status)
                )
            ).all()
            by_status = {str(status): int(count) for status, count in rows}
            return {"total": sum(by_status.values()), "by_status": by_status}

    async def save_approval(
        self, change_id: int, approver_id: int, decision: str, comment: str = ""
    ) -> None:
        from app.models.change import Approval

        async with self._session_factory() as db:
            db.add(
                Approval(
                    request_id=change_id, approver_id=approver_id, decision=decision, comment=comment
                )
            )
            await db.commit()

    async def save_snapshot(
        self, change_id: int, device_id: int, object_key: str, config_hash: str, config: str
    ) -> None:
        from app.models.change import ConfigSnapshot

        async with self._session_factory() as db:
            db.add(
                ConfigSnapshot(
                    device_id=device_id,
                    change_request_id=change_id,
                    object_key=object_key,
                    config_hash=config_hash,
                    content=config,
                )
            )
            await db.commit()

    async def load_snapshot(self, object_key: str) -> str:
        from sqlalchemy import select

        from app.models.change import ConfigSnapshot

        async with self._session_factory() as db:
            # 同 key 可能多版本（重跑变更），取最新一条
            row = (
                await db.execute(
                    select(ConfigSnapshot.content)
                    .where(ConfigSnapshot.object_key == object_key)
                    .order_by(ConfigSnapshot.id.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            return row or ""


def _dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _load(text: str) -> dict:
    try:
        return json.loads(text) if text else {}
    except (TypeError, ValueError):
        return {}


def _to_record(row: Any) -> ChangeRecord:
    return ChangeRecord(
        id=row.id,
        title=row.title,
        nim=_load(row.intent) if isinstance(_load(row.intent), dict) else {},
        devices=_list(row.devices),
        configs=_load(row.configs),
        assertions=_list(row.assertions),
        status=row.status,
        impact=_load(row.impact),
        created_by=row.created_by,
        pipeline_result=_load(row.pipeline_result) or None,
    )


def _list(text: str) -> list:
    try:
        value = json.loads(text) if text else []
        return value if isinstance(value, list) else []
    except (TypeError, ValueError):
        return []


# ===== 启动装配（app.main lifespan 调；默认内存回退保证无 DB 可用）=====

_store: ChangeStore = MemoryChangeStore()


def configure_change_store(store: ChangeStore) -> None:
    global _store
    _store = store
    logger.info("change_store_configured", mode=store.mode)


def get_change_store() -> ChangeStore:
    return _store
