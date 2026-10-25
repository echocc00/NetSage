"""指标事件服务（v0.6：运营指标历史落库，报表真实聚合）。

双实现（DB 落库 / 内存回退），与 change_store/audit_sink 同装配模式
（app.main lifespan 按 DB 可达性选择）。事件类型：
- compliance_scan：value=基线得分
- rca_run：value=top1 概率（hit 判定需人工，先落证据）
- closed_loop_run：value=自动化率
- agent_run：会话级运行计数
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any, Protocol

from app.core.logging import get_logger

logger = get_logger("metrics")

KIND_COMPLIANCE = "compliance_scan"
KIND_RCA = "rca_run"
KIND_CLOSED_LOOP = "closed_loop_run"
KIND_AGENT = "agent_run"


class MetricSink(Protocol):
    """指标事件写入接口。"""

    @property
    def mode(self) -> str: ...

    async def record(self, kind: str, value: float | None, detail: dict) -> None: ...

    async def aggregate(self, kind: str) -> dict: ...


class DbMetricSink:
    """PostgreSQL 指标事件（metric_events 表）。"""

    def __init__(self) -> None:
        from app.db import SessionLocal

        self._session_factory = SessionLocal

    @property
    def mode(self) -> str:
        return "db"

    async def record(self, kind: str, value: float | None, detail: dict) -> None:
        from app.models.metrics import MetricEvent

        async with self._session_factory() as db:
            db.add(MetricEvent(kind=kind, value=value, detail=_dump(detail)))
            await db.commit()

    async def aggregate(self, kind: str) -> dict:
        from sqlalchemy import func, select

        from app.models.metrics import MetricEvent

        async with self._session_factory() as db:
            total, avg, latest_ts = (
                await db.execute(
                    select(func.count(), func.avg(MetricEvent.value), func.max(MetricEvent.created_at))
                    .where(MetricEvent.kind == kind)
                )
            ).one()
            return {
                "total": int(total or 0),
                "avg_value": round(float(avg), 4) if avg is not None else None,
                "latest_at": latest_ts.isoformat() if latest_ts else None,
            }


class MemoryMetricSink:
    """进程内指标（无 DB 回退；重启即失，日志明示）。"""

    def __init__(self) -> None:
        self._events: list[dict[str, Any]] = []

    @property
    def mode(self) -> str:
        return "memory"

    async def record(self, kind: str, value: float | None, detail: dict) -> None:
        self._events.append(
            {"kind": kind, "value": value, "detail": detail,
             "at": datetime.now(UTC).isoformat()}
        )

    async def aggregate(self, kind: str) -> dict:
        evts = [e for e in self._events if e["kind"] == kind]
        vals = [e["value"] for e in evts if e["value"] is not None]
        return {
            "total": len(evts),
            "avg_value": round(sum(vals) / len(vals), 4) if vals else None,
            "latest_at": evts[-1]["at"] if evts else None,
        }


def _dump(value: dict) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


_sink: MetricSink = MemoryMetricSink()


def configure_metric_sink(sink: MetricSink) -> None:
    global _sink
    _sink = sink
    logger.info("metric_sink_configured", mode=sink.mode)


def get_metric_sink() -> MetricSink:
    return _sink
