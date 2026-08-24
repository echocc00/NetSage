"""ORM 模型聚合（确保 Alembic autodetect 能发现所有表）。"""
from app.models.audit import AuditLog
from app.models.base import Base, TimestampMixin
from app.models.change import Approval, ChangeRequest, ChangeStep, ConfigSnapshot, Project
from app.models.design import NetworkDesign, RdmaFabric
from app.models.device import Credential, Device
from app.models.kb import KbChunk
from app.models.security import BaselineRule, ComplianceReport
from app.models.tenant import Tenant

__all__ = [
    "Base", "TimestampMixin",
    "AuditLog",
    "Approval", "ChangeRequest", "ChangeStep", "ConfigSnapshot", "Project",
    "NetworkDesign", "RdmaFabric",
    "Credential", "Device",
    "KbChunk",
    "BaselineRule", "ComplianceReport",
    "Tenant",
]
