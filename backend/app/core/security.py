"""认证与 RBAC（v2.0 十章权限分级 + 11.2 等保三权分立）。

五级角色（用户决策 2026-08-21）：viewer/operator/engineer/admin/auditor。
auditor 审计员只读审计日志，满足等保 2.0 三权分立（系统管理员/安全管理员/审计管理员分离）。
Phase 1 W1 占位：JWT 解码 + 角色枚举。OIDC（Keycloak）Phase 3 接入。
"""
from __future__ import annotations

from datetime import UTC
from enum import IntEnum

from jose import JWTError, jwt
from pydantic import BaseModel

from app.core.config import get_settings


class Role(IntEnum):
    """RBAC 五级（v2.0 十章 + 11.2 等保三权分立）。"""
    VIEWER = 0    # 只读访客
    OPERATOR = 1  # 网络运维：可读 + 排障
    ENGINEER = 2  # 网络工程师：拟变更 + 发起审批
    ADMIN = 3     # 网络主管：审批 + 回滚
    AUDITOR = 4   # 审计员：只读审计日志（三权分立的审计管理员）


# 角色权限矩阵（供 require_role 与业务逻辑查询）
ROLE_PERMISSIONS: dict[Role, set[str]] = {
    Role.VIEWER: {"read"},
    Role.OPERATOR: {"read", "troubleshoot"},
    Role.ENGINEER: {"read", "troubleshoot", "draft_change", "initiate_approval"},
    Role.ADMIN: {"read", "troubleshoot", "draft_change", "initiate_approval", "approve", "rollback", "deploy", "audit"},
    Role.AUDITOR: {"read", "read_audit_logs", "audit"},  # 合规报告查询 + 审计日志
}

WRITE_ROLES = {Role.ENGINEER, Role.ADMIN}
APPROVE_ROLES = {Role.ADMIN}
AUDIT_ROLES = {Role.AUDITOR, Role.ADMIN}


class CurrentUser(BaseModel):
    id: int
    name: str
    role: Role


def decode_token(token: str) -> CurrentUser | None:
    """解码 JWT，返回当前用户。

    安全要求（审查修复）：
    - 算法硬编码 HS256，不接受配置注入（防 algorithm confusion）
    - 强制校验 exp（require: ["exp"]）
    - iss/aud 校验 Phase 3 OIDC 接入时补充
    """
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=["HS256"],
            options={"require": ["exp"]},
        )
        return CurrentUser(
            id=int(payload["sub"]),
            name=payload["name"],
            role=Role(int(payload["role"])),
        )
    except jwt.ExpiredSignatureError:
        return None
    except (JWTError, KeyError, ValueError):
        return None


def encode_token(user: CurrentUser) -> str:
    """生成 JWT（开发态登录用）。"""
    from datetime import datetime, timedelta

    settings = get_settings()
    payload = {
        "sub": str(user.id),
        "name": user.name,
        "role": user.role.value,
        "exp": datetime.now(UTC) + timedelta(minutes=settings.jwt_expire_minutes),
        "iss": "netsage",
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")
