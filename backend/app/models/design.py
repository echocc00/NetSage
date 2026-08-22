"""网络设计方案 ORM（Phase 3 自研 Nautobot App v0.1 本地落地）。

v2.0 差异化：AI 设计方案持久化。Phase 3 决策：Nautobot 不部署服务，
NetworkDesign 落本地 Postgres，前端"历史方案"功能即可用。
未来部署 Nautobot 时，nautobot-app-designs Django plugin 提供同构 model 可迁移。

与 mcp-servers/nautobot-mcp save_design/list_designs 对齐。
"""
from __future__ import annotations

from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class NetworkDesign(Base, TimestampMixin):
    """AI 生成的网络设计方案（v2.0 差异化：自带 SSoT 持久化）。"""
    __tablename__ = "network_designs"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    site: Mapped[str] = mapped_column(String(100), default="")
    scenario: Mapped[str] = mapped_column(String(50))   # bgp/ospf/vxlan/...
    vendor: Mapped[str] = mapped_column(String(50))
    hld: Mapped[str] = mapped_column(Text, default="{}")       # 高层设计 JSON
    lld: Mapped[str] = mapped_column(Text, default="{}")       # 低层设计 JSON
    config_diff: Mapped[str] = mapped_column(Text, default="")
    rollback_config: Mapped[str] = mapped_column(Text, default="")
    lint_passed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[str] = mapped_column(String(50), default="ai")
