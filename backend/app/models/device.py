"""设备与凭证 ORM（v2.0 八章）。"""
from __future__ import annotations

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Device(Base, TimestampMixin):
    __tablename__ = "devices"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True)
    vendor: Mapped[str] = mapped_column(String(32))   # cisco / huawei / h3c / juniper / arista
    os: Mapped[str] = mapped_column(String(32))       # iosxe / vrp / comware / junos / eos
    model: Mapped[str] = mapped_column(String(64), default="")
    version: Mapped[str] = mapped_column(String(32), default="")  # VRP-8.180 / 17.x
    mgmt_ip: Mapped[str] = mapped_column(String(64))  # 访问时解密
    role: Mapped[str] = mapped_column(String(32), default="")    # spine/leaf/pe/ce
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    credential_id: Mapped[int] = mapped_column(ForeignKey("credentials.id"))


class Credential(Base, TimestampMixin):
    __tablename__ = "credentials"

    id: Mapped[int] = mapped_column(primary_key=True)
    ref: Mapped[str] = mapped_column(String(256))  # Vault path，不存明文
    type: Mapped[str] = mapped_column(String(16))  # ssh / snmp / netconf
    username: Mapped[str] = mapped_column(String(64), default="")
