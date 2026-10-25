"""指标事件 ORM（v0.6：合规/RCA/闭环运行历史落库，报表真实聚合）。

一张通用事件表（append-only，指标口径见 app/services/metrics.py KIND_*）。
此前合规得分/RCA 命中/Agent 运行无历史——报表只能 no_data。
"""
from __future__ import annotations

from sqlalchemy import Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class MetricEvent(Base, TimestampMixin):
    __tablename__ = "metric_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(String(32))     # compliance_scan / rca_run / closed_loop_run / agent_run
    value: Mapped[float | None] = mapped_column(Float, nullable=True)  # 主指标（score/hit rate/automation_rate）
    detail: Mapped[str] = mapped_column(Text, default="{}")  # JSON 载荷（kind 相关结构）
