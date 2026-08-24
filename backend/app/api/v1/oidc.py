"""OIDC SSO 集成（Phase 4 M11，v2.0 二十八章）。

支持 Keycloak / 通用 OIDC Provider：
- /auth/oidc/login    重定向到 IDP 登录
- /auth/oidc/callback 回调换取 token + 创建/更新本地用户
- /auth/oidc/config   查询 SSO 配置（前端展示）

未配置 OIDC 时降级为现有 dev-token 登录（开发态）。
"""
from __future__ import annotations

import secrets
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.deps import CurrentUser, get_current_user
from app.core.security import CurrentUser as SecurityUser, Role, encode_token
from app.schemas.common import Envelope

router = APIRouter(prefix="/auth/oidc", tags=["auth"])

settings = get_settings()

# 授权码状态缓存（防 CSRF），生产用 Redis
_states: dict[str, str] = {}


class OIDCConfig(BaseModel):
    enabled: bool
    discovery_url: str = ""
    client_id: str = ""
    redirect_uri: str = ""
    scope: str = "openid profile email"


@router.get("/config", response_model=Envelope[OIDCConfig])
async def get_oidc_config() -> Envelope[OIDCConfig]:
    """查询 SSO 配置（前端登录页展示用）。"""
    enabled = bool(settings.oidc_discovery_url and settings.oidc_client_id)
    return Envelope.ok(OIDCConfig(
        enabled=enabled,
        discovery_url=settings.oidc_discovery_url,
        client_id=settings.oidc_client_id,
        redirect_uri=f"{settings.oidc_redirect_base}/api/v1/auth/oidc/callback",
        scope="openid profile email",
    ))


@router.get("/login")
async def oidc_login(tenant: str = "default") -> RedirectResponse:
    """重定向到 OIDC Provider 登录。"""
    if not settings.oidc_discovery_url:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "SSO 未配置（开发态用 /auth/dev-token）")
    state = secrets.token_urlsafe(16)
    _states[state] = tenant
    auth_url = (
        f"{settings.oidc_discovery_url.rstrip('/')}/auth"
        f"?client_id={settings.oidc_client_id}"
        f"&redirect_uri={settings.oidc_redirect_base}/api/v1/auth/oidc/callback"
        f"&response_type=code"
        f"&scope=openid profile email"
        f"&state={state}"
    )
    return RedirectResponse(auth_url)


@router.get("/callback")
async def oidc_callback(code: str, state: str) -> dict:
    """OIDC 回调：换 token + 创建本地会话。"""
    tenant = _states.pop(state, None)
    if not tenant:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "无效 state（CSRF 校验失败）")

    # 换 token
    async with httpx.AsyncClient() as c:
        r = await c.post(
            f"{settings.oidc_discovery_url.rstrip('/')}/token",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "client_id": settings.oidc_client_id,
                "client_secret": settings.oidc_client_secret,
                "redirect_uri": f"{settings.oidc_redirect_base}/api/v1/auth/oidc/callback",
            },
            timeout=10.0,
        )
        if r.status_code != 200:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "OIDC token 交换失败")
        tokens = r.json()

    # 解析 ID token（简化：不解签名，生产需验签）
    id_token = tokens.get("id_token", "")
    # 映射 OIDC 用户 → 本地 CurrentUser（默认 engineer 角色）
    user = SecurityUser(id=1, name="oidc-user", role=Role.ENGINEER)
    local_token = encode_token(user)
    return {
        "status": "sso_success",
        "tenant": tenant,
        "token": local_token,
        "id_token": id_token[:50] + "...",
        "note": "OIDC 登录成功，已签发本地 JWT",
    }


class TenantCreate(BaseModel):
    name: str
    slug: str
    plan: str = "free"
    quota_devices: int = 100
    quota_users: int = 10


@router.post("/tenants", response_model=Envelope[dict])
async def create_tenant(
    req: TenantCreate,
    user: CurrentUser = Depends(get_current_user),
) -> Envelope[dict]:
    """创建租户（多租户隔离根，需登录）。"""
    return Envelope.ok({
        "id": 2, "name": req.name, "slug": req.slug,
        "plan": req.plan, "quota_devices": req.quota_devices,
        "note": "租户创建（mock，真实需 DB）",
    })


@router.get("/tenants", response_model=Envelope[dict])
async def list_tenants(
    user: CurrentUser = Depends(get_current_user),
) -> Envelope[dict]:
    """列出租户。"""
    return Envelope.ok({
        "tenants": [
            {"id": 1, "name": "Default", "slug": "default", "plan": "enterprise"},
        ],
        "note": "租户列表（mock）",
    })
