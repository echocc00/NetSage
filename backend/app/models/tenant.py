"""租户 ORM（Phase 4 M11 多租户，v2.0 二十八章）。

per-tenant 隔离：项目/设备/变更按 tenant_id 隔离。
SSO：OIDC（Keycloak）集成，JWT 复用现有 HS256（OIDC 为可选外部 IDP）。
"""
from __future__ import annotations

from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Tenant(Base, TimestampMixin):
    """租户（多租户隔离根）。"""
    __tablename__ = "tenants"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True)     # URL 友好标识
    plan: Mapped[str] = mapped_column(String(32), default="free")  # free/pro/enterprise
    quota_devices: Mapped[int] = mapped_column(Integer, default=100)
    quota_users: Mapped[int] = mapped_column(Integer, default=10)
    sso_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    oidc_client_id: Mapped[str] = mapped_column(String(128), default="")
    oidc_client_secret: Mapped[str] = mapped_column(String(256), default="")  # Vault 引用，不落明文
    oidc_discovery_url: Mapped[str] = mapped_column(String(256), default="")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")
