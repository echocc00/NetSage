"""OIDC SSO 集成（Phase 4 M11，v2.0 二十八章）。

完整 Authorization Code + PKCE 流程（OAuth 2.1 / OIDC Core 1.0）：
- /auth/oidc/login    → 生成 state + nonce + PKCE challenge，重定向 IDP
- /auth/oidc/callback → 校验 state，用 code_verifier 换 token，验签 ID token（JWKS），校验 nonce/iss/aud/exp
- /auth/oidc/config   → 前端查询 SSO 是否启用

未配置 OIDC 时降级为 dev-token 登录（开发态）。
"""
from __future__ import annotations

import base64
import hashlib
import secrets
import time
from dataclasses import dataclass, field

import httpx
import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.deps import CurrentUser, get_current_user
from app.core.logging import get_logger
from app.core.security import CurrentUser as SecurityUser
from app.core.security import Role, encode_token
from app.schemas.common import Envelope

router = APIRouter(prefix="/auth/oidc", tags=["auth"])
logger = get_logger("oidc")

# state 生命周期（秒）——超时的授权请求视为失效
STATE_TTL = 600

# OIDC 声明 → NetSage 角色映射（IDP group/role claim → 本地 RBAC）
ROLE_CLAIM_MAP: dict[str, Role] = {
    "netsage-admin": Role.ADMIN,
    "netsage-engineer": Role.ENGINEER,
    "netsage-operator": Role.OPERATOR,
    "netsage-auditor": Role.AUDITOR,
    "netsage-viewer": Role.VIEWER,
}


@dataclass
class _PendingAuth:
    """待完成的授权请求（防 CSRF + PKCE + replay）。"""
    tenant: str
    nonce: str
    code_verifier: str
    created_at: float = field(default_factory=time.time)

    @property
    def expired(self) -> bool:
        return time.time() - self.created_at > STATE_TTL


# 授权状态缓存（生产用 Redis，此处内存实现）
_pending: dict[str, _PendingAuth] = {}
# JWKS 缓存（避免每次回调都拉公钥）
_jwks_cache: dict[str, tuple[float, dict]] = {}
JWKS_TTL = 3600


class OIDCConfig(BaseModel):
    enabled: bool
    issuer: str = ""
    client_id: str = ""
    redirect_uri: str = ""
    scope: str = "openid profile email"
    pkce: bool = True


def _settings():
    return get_settings()


def _redirect_uri() -> str:
    return f"{_settings().oidc_redirect_base}/api/v1/auth/oidc/callback"


def _gen_pkce() -> tuple[str, str]:
    """生成 PKCE code_verifier + S256 challenge（RFC 7636）。"""
    verifier = secrets.token_urlsafe(64)[:128]
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return verifier, challenge


def _prune_expired() -> None:
    for k in [k for k, v in _pending.items() if v.expired]:
        _pending.pop(k, None)


@router.get("/config", response_model=Envelope[OIDCConfig])
async def get_oidc_config() -> Envelope[OIDCConfig]:
    """查询 SSO 配置（前端登录页展示用）。"""
    s = _settings()
    enabled = bool(s.oidc_discovery_url and s.oidc_client_id)
    return Envelope.ok(OIDCConfig(
        enabled=enabled,
        issuer=s.oidc_discovery_url,
        client_id=s.oidc_client_id,
        redirect_uri=_redirect_uri(),
    ))


@router.get("/login")
async def oidc_login(tenant: str = "default") -> RedirectResponse:
    """重定向到 OIDC Provider（Authorization Code + PKCE）。"""
    s = _settings()
    if not s.oidc_discovery_url or not s.oidc_client_id:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "SSO 未配置（开发态用 /auth/dev-token）",
        )

    _prune_expired()
    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    verifier, challenge = _gen_pkce()
    _pending[state] = _PendingAuth(tenant=tenant, nonce=nonce, code_verifier=verifier)

    meta = await _discover()
    auth_endpoint = meta.get("authorization_endpoint") or f"{s.oidc_discovery_url.rstrip('/')}/auth"
    params = {
        "client_id": s.oidc_client_id,
        "redirect_uri": _redirect_uri(),
        "response_type": "code",
        "scope": "openid profile email",
        "state": state,
        "nonce": nonce,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    query = "&".join(f"{k}={httpx.QueryParams({k: v})[k]}" for k, v in params.items())
    logger.info("oidc_login_redirect", tenant=tenant)
    return RedirectResponse(f"{auth_endpoint}?{query}")


@router.get("/callback")
async def oidc_callback(code: str, state: str) -> dict:
    """OIDC 回调：校验 state → PKCE 换 token → 验签 ID token → 签发本地 JWT。"""
    _prune_expired()
    pending = _pending.pop(state, None)
    if pending is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "无效或过期的 state（CSRF/replay 防护）")

    s = _settings()
    meta = await _discover()
    token_endpoint = meta.get("token_endpoint") or f"{s.oidc_discovery_url.rstrip('/')}/token"
    if not token_endpoint.startswith(("http://", "https://")):
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "SSO 未配置（无 token_endpoint）")

    async with httpx.AsyncClient(timeout=10.0) as c:
        try:
            r = await c.post(
                token_endpoint,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "client_id": s.oidc_client_id,
                    "client_secret": s.oidc_client_secret,
                    "redirect_uri": _redirect_uri(),
                    "code_verifier": pending.code_verifier,  # PKCE 验证
                },
            )
        except httpx.HTTPError as e:
            logger.warning("oidc_token_endpoint_unreachable", error=str(e)[:80])
            raise HTTPException(
                status.HTTP_502_BAD_GATEWAY, f"IDP token 端点不可达: {e}"
            ) from e
        if r.status_code != 200:
            logger.warning("oidc_token_exchange_failed", status=r.status_code)
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "OIDC token 交换失败")
        tokens = r.json()

    id_token = tokens.get("id_token")
    if not id_token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "IDP 未返回 id_token")

    claims = await _verify_id_token(id_token, expected_nonce=pending.nonce)
    user = _map_user(claims)
    local_token = encode_token(user)

    logger.info("oidc_login_success", tenant=pending.tenant, sub=claims.get("sub", "")[:12],
                role=user.role.name)
    return {
        "status": "sso_success",
        "tenant": pending.tenant,
        "token": local_token,
        "user": {"name": user.name, "role": user.role.name.lower()},
    }


async def _discover() -> dict:
    """拉取 OIDC discovery 文档（缓存 1h）。未配置时返回空 dict。"""
    s = _settings()
    if not s.oidc_discovery_url:
        return {}
    url = s.oidc_discovery_url.rstrip("/")
    if not url.startswith(("http://", "https://")):
        logger.warning("oidc_discovery_url_invalid", url=url[:40])
        return {}
    if not url.endswith("/.well-known/openid-configuration"):
        url = f"{url}/.well-known/openid-configuration"

    cached = _jwks_cache.get(f"meta:{url}")
    if cached and time.time() - cached[0] < JWKS_TTL:
        return cached[1]

    try:
        async with httpx.AsyncClient(timeout=10.0) as c:
            r = await c.get(url)
            r.raise_for_status()
            meta = r.json()
        _jwks_cache[f"meta:{url}"] = (time.time(), meta)
        return meta
    except httpx.HTTPError as e:
        logger.warning("oidc_discovery_failed", error=str(e)[:80])
        return {}  # 降级：调用方回退到约定端点


async def _fetch_jwks(jwks_uri: str) -> dict:
    """拉取 JWKS 公钥（缓存 1h）。"""
    cached = _jwks_cache.get(f"jwks:{jwks_uri}")
    if cached and time.time() - cached[0] < JWKS_TTL:
        return cached[1]
    async with httpx.AsyncClient(timeout=10.0) as c:
        r = await c.get(jwks_uri)
        r.raise_for_status()
        jwks = r.json()
    _jwks_cache[f"jwks:{jwks_uri}"] = (time.time(), jwks)
    return jwks


async def _verify_id_token(id_token: str, expected_nonce: str) -> dict:
    """验签 ID token：JWKS 公钥 + iss/aud/exp/nonce 校验（OIDC Core 3.1.3.7）。"""
    s = _settings()
    meta = await _discover()
    jwks_uri = meta.get("jwks_uri")
    if not jwks_uri:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "IDP 未提供 jwks_uri，无法验签")

    header = jwt.get_unverified_header(id_token)
    kid = header.get("kid")
    jwks = await _fetch_jwks(jwks_uri)
    key = next((k for k in jwks.get("keys", []) if k.get("kid") == kid), None)
    if key is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"JWKS 中无匹配 kid={kid}")

    try:
        claims = jwt.decode(
            id_token,
            key=jwt.PyJWK(key).key,
            algorithms=[header.get("alg", "RS256")],
            audience=s.oidc_client_id,
            issuer=meta.get("issuer"),
            options={"require": ["exp", "iat", "iss", "aud", "sub"]},
        )
    except jwt.InvalidTokenError as e:
        logger.warning("oidc_id_token_invalid", error=str(e)[:80])
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"ID token 验签失败: {e}") from e

    # nonce 防重放（OIDC Core 3.1.3.7 step 11）
    if claims.get("nonce") != expected_nonce:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "nonce 不匹配（replay 防护）")

    return claims


def _map_user(claims: dict) -> SecurityUser:
    """OIDC claims → 本地 CurrentUser（按 groups/roles claim 映射 RBAC）。"""
    name = claims.get("preferred_username") or claims.get("email") or claims.get("sub", "oidc-user")
    groups = claims.get("groups") or claims.get("roles") or []
    if isinstance(groups, str):
        groups = [groups]
    role = Role.VIEWER  # 默认最小权限
    for g in groups:
        mapped = ROLE_CLAIM_MAP.get(str(g).lower())
        if mapped is not None and mapped > role:
            role = mapped
    # sub 是 IDP 唯一标识，本地 user id 用其哈希（真实场景查/建本地用户表）
    uid = int(hashlib.sha256(str(claims.get("sub", "")).encode()).hexdigest()[:8], 16)
    return SecurityUser(id=uid, name=str(name), role=role)


# ===== 租户管理 =====


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
