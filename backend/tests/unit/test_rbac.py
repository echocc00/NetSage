"""RBAC 五级权限测试（v2.0 十章 + 11.2 等保三权分立）。

验证：
- 五级角色权限矩阵
- auditor 独立维度，不误获写权限
- require_permission 基于权限集合
- require_role 层级守卫排除 auditor
"""
from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.core.security import (
    APPROVE_ROLES,
    AUDIT_ROLES,
    ROLE_PERMISSIONS,
    Role,
    WRITE_ROLES,
)


def test_five_roles_defined():
    """五级角色齐全（viewer/operator/engineer/admin/auditor）。"""
    roles = {Role.VIEWER, Role.OPERATOR, Role.ENGINEER, Role.ADMIN, Role.AUDITOR}
    assert len(roles) == 5


def test_auditor_cannot_write():
    """审计员无任何写权限（等保三权分立：审计管理员独立）。"""
    auditor_perms = ROLE_PERMISSIONS[Role.AUDITOR]
    assert "read" in auditor_perms
    assert "read_audit_logs" in auditor_perms
    # 无写操作
    write_perms = {"draft_change", "initiate_approval", "approve", "rollback", "deploy"}
    assert auditor_perms.isdisjoint(write_perms)


def test_engineer_can_draft_not_approve():
    """工程师可拟变更但不能审批。"""
    eng = ROLE_PERMISSIONS[Role.ENGINEER]
    assert "draft_change" in eng
    assert "approve" not in eng


def test_admin_full_write():
    """admin 拥有全部写权限含审批+回滚。"""
    admin = ROLE_PERMISSIONS[Role.ADMIN]
    assert {"approve", "rollback", "deploy"}.issubset(admin)


def test_role_groups():
    """WRITE_ROLES/APPROVE_ROLES/AUDIT_ROLES 分组正确。"""
    assert WRITE_ROLES == {Role.ENGINEER, Role.ADMIN}
    assert APPROVE_ROLES == {Role.ADMIN}
    assert Role.AUDITOR in AUDIT_ROLES
    assert Role.ADMIN in AUDIT_ROLES


@pytest.mark.asyncio
async def test_require_permission_auditor_blocked_from_write():
    """require_permission('draft_change') 拒绝 auditor。"""
    from app.core.deps import require_permission

    guard = require_permission("draft_change")
    # 模拟 auditor 用户调用
    from app.core.security import CurrentUser

    auditor = CurrentUser(id=5, name="audit", role=Role.AUDITOR)
    with pytest.raises(HTTPException) as exc:
        await guard.__call__(auditor)  # type: ignore
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_require_permission_auditor_can_read_audit_logs():
    """require_permission('read_audit_logs') 放行 auditor。"""
    from app.core.deps import require_permission
    from app.core.security import CurrentUser

    guard = require_permission("read_audit_logs")
    auditor = CurrentUser(id=5, name="audit", role=Role.AUDITOR)
    # 不抛异常即通过
    result = await guard.__call__(auditor)  # type: ignore
    assert result.role == Role.AUDITOR


@pytest.mark.asyncio
async def test_require_role_excludes_auditor():
    """require_role(ENGINEER) 拒绝 auditor（层级守卫排除审计维度）。"""
    from app.core.deps import require_role
    from app.core.security import CurrentUser

    guard = require_role(Role.ENGINEER)
    auditor = CurrentUser(id=5, name="audit", role=Role.AUDITOR)
    with pytest.raises(HTTPException) as exc:
        await guard.__call__(auditor)  # type: ignore
    assert exc.value.status_code == 403
