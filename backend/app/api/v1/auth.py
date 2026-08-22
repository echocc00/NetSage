"""开发态认证端点（Phase 3 OIDC 前的过渡）。

仅 dev 环境可用：生成任意角色 token，供本地 CLI/测试使用。
生产环境此路由不注册（安全审查：CORS/认证不得有后门）。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.security import CurrentUser, Role, encode_token

router = APIRouter(prefix="/auth", tags=["auth"])


class DevTokenRequest(BaseModel):
    user_id: int = 1
    name: str = "dev"
    role: int = 2  # ENGINEER 默认


class DevTokenResponse(BaseModel):
    token: str
    role: str


@router.post("/dev-token", response_model=DevTokenResponse)
async def dev_token(req: DevTokenRequest) -> DevTokenResponse:
    """生成开发态 JWT（仅 dev 环境）。"""
    settings = get_settings()
    if not settings.is_dev:
        raise HTTPException(status_code=403, detail="dev-token 仅开发环境可用")
    if req.role not in {r.value for r in Role}:
        raise HTTPException(status_code=400, detail="非法角色")
    user = CurrentUser(id=req.user_id, name=req.name, role=Role(req.role))
    return DevTokenResponse(token=encode_token(user), role=user.role.name)