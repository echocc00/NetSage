"""变更请求 ORM（v2.0 八章 + 开发计划十三章）。"""
from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class ChangeRequest(Base, TimestampMixin):
    __tablename__ = "change_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    title: Mapped[str] = mapped_column(String(256))
    intent: Mapped[dict] = mapped_column(Text)  # NIM 片段 JSON
    status: Mapped[str] = mapped_column(String(32), default="draft")
    created_by: Mapped[int] = mapped_column(Integer)
    # status 流转见 app.gates.models.ChangeStatus
    steps: Mapped[list[ChangeStep]] = relationship(back_populates="request")
    approvals: Mapped[list[Approval]] = relationship(back_populates="request")


class ChangeStep(Base, TimestampMixin):
    __tablename__ = "change_steps"

    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("change_requests.id"))
    seq: Mapped[int] = mapped_column(Integer)
    device_id: Mapped[int] = mapped_column(Integer)
    config_diff: Mapped[str] = mapped_column(Text, default="")
    rollback_config: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), default="pending")
    request: Mapped[ChangeRequest] = relationship(back_populates="steps")


class Approval(Base, TimestampMixin):
    __tablename__ = "approvals"

    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("change_requests.id"))
    approver_id: Mapped[int] = mapped_column(Integer)
    decision: Mapped[str] = mapped_column(String(16))  # approved / rejected
    comment: Mapped[str] = mapped_column(Text, default="")
    request: Mapped[ChangeRequest] = relationship(back_populates="approvals")


class ConfigSnapshot(Base, TimestampMixin):
    __tablename__ = "config_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[int] = mapped_column(Integer)
    change_request_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    object_key: Mapped[str] = mapped_column(String(256))  # MinIO 对象 key
    config_hash: Mapped[str] = mapped_column(String(64))  # sha256
    restored: Mapped[bool] = mapped_column(default=False)


class Project(Base, TimestampMixin):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True)
    description: Mapped[str] = mapped_column(Text, default="")
