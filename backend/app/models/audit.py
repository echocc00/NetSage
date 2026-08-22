"""审计日志 ORM（不可篡改：append-only + 哈希链，v2.0 八章 + 十一章）。"""
from __future__ import annotations

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AuditLog(Base):
    """INSERT ONLY：DB 层 REVOKE UPDATE/DELETE 权限。
    self_hash = sha256(prev_hash + payload)，形成哈希链。
    """

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ts: Mapped[str] = mapped_column(String(32))  # ISO，应用层注入
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    action: Mapped[str] = mapped_column(String(32))        # read/write/approve/deploy/rollback
    resource_type: Mapped[str] = mapped_column(String(32))
    resource_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    before: Mapped[str | None] = mapped_column(Text, nullable=True)  # 脱敏后
    after: Mapped[str | None] = mapped_column(Text, nullable=True)
    prev_hash: Mapped[str] = mapped_column(String(64))
    self_hash: Mapped[str] = mapped_column(String(64), unique=True)
