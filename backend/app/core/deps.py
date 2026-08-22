"""FastAPI 依赖注入（v2.0 五章 5.3）。"""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import ROLE_PERMISSIONS, CurrentUser, Role, decode_token
from app.db import get_session

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> CurrentUser:
    """解析 Bearer token 返回当前用户。"""
    if creds is None or creds.scheme.lower() != "bearer":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "未提供凭证")
    user = decode_token(creds.credentials)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "凭证无效或已过期")
    return user


CurrentUserDep = Annotated[CurrentUser, Depends(get_current_user)]
DBSession = Annotated[AsyncSession, Depends(get_session)]


def require_permission(perm: str):
    """权限守卫：基于角色权限集合（auditor 独立维度，不误获写权限，等保三权分立）。"""

    async def _checker(user: CurrentUserDep) -> CurrentUser:
        allowed = ROLE_PERMISSIONS.get(user.role, set())
        if perm not in allowed:
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"权限不足：需要 {perm}")
        return user

    return _checker


# 向后兼容：纯写权限层级（viewer<operator<engineer<admin，auditor 排除）
def require_role(min_role: Role):
    """角色层级守卫（viewer<operator<engineer<admin）。auditor 不在此层级。"""

    async def _checker(user: CurrentUserDep) -> CurrentUser:
        # auditor 独立维度，不通过层级守卫（除非明确要求 auditor）
        if user.role == Role.AUDITOR and min_role != Role.AUDITOR:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "审计员无此操作权限")
        if user.role != Role.AUDITOR and user.role < min_role:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "权限不足")
        return user

    return _checker
