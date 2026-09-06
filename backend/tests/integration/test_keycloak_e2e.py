"""Keycloak 22.x 真实 provider 集成测试（v0.5.0 阶段1 去 🟡 OIDC）。

覆盖：
- 真实 discovery（authorization/token/jwks 端点）+ 真实 JWKS RS256
- 完整 Authorization Code + PKCE 全链路：GET /auth/oidc/login →（headless 完成 Keycloak 登录表单）
  → 回调 → 真实 id_token 验签（iss/aud/非ce）→ 签发本地 JWT + groups→RBAC 角色映射
- state 单次使用防重放（同一 code+state 二次调用 → 400）
- 错误 code → 401
- 真实 id_token 签名独立验证（直连授权 token，供辅助审计）

前置：
  docker compose -f infra/docker-compose.keycloak.yml up -d
  python backend/scripts/provision_keycloak.py   （生成 gitignored 的 .env.keycloak）
Keycloak 未就绪 / 未 provision 时整包 skip。
"""
from __future__ import annotations

import html
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import httpx
import jwt  # PyJWT（与 oidc.py 同库：jwt.PyJWK / get_unverified_header / decode）
import pytest
from fastapi.testclient import TestClient

from app.api.v1 import oidc
from app.core.config import Settings

MODULE_DIR = Path(__file__).resolve().parent
BACKEND_DIR = MODULE_DIR.parents[1]
PROJECT_ROOT = MODULE_DIR.parents[2]
ENV_FILE = PROJECT_ROOT / ".env.keycloak"
PROVISION = BACKEND_DIR / "scripts" / "provision_keycloak.py"

KEYCLOAK_BASE = "http://localhost:9090"
REALM = "netsage"
DISCOVERY_URL = f"{KEYCLOAK_BASE}/realms/{REALM}"
CALLBACK_PATH = "/api/v1/auth/oidc/callback"


def _load_oidc_env() -> dict[str, str] | None:
    """从真实环境变量或 .env.keycloak 读取 OIDC 配置。"""
    env: dict[str, str] = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env or None


def _keycloak_ready() -> bool:
    try:
        r = httpx.get(f"{DISCOVERY_URL}/.well-known/openid-configuration", timeout=3)
        return r.status_code == 200
    except httpx.HTTPError:
        return False


_env = _load_oidc_env()
pytestmark = pytest.mark.integration
pytest.skip(
    ".env.keycloak 缺失或 Keycloak 未运行——先:\n"
    "  docker compose -f infra/docker-compose.keycloak.yml up -d\n"
    "  python backend/scripts/provision_keycloak.py",
    allow_module_level=True,
) if not (_env and _keycloak_ready()) else None

OIDC_ENV = _env or {}


@pytest.fixture()
def oidc_app(monkeypatch):
    """注入真实 Keycloak 配置的 TestClient + 全局单例 app。"""
    from app.main import app

    settings = Settings(
        oidc_discovery_url=OIDC_ENV["OIDC_DISCOVERY_URL"],
        oidc_client_id=OIDC_ENV["OIDC_CLIENT_ID"],
        oidc_client_secret=OIDC_ENV["OIDC_CLIENT_SECRET"],
        oidc_redirect_base=OIDC_ENV.get("OIDC_REDIRECT_BASE", "http://localhost:8000"),
    )
    monkeypatch.setattr(oidc, "_settings", lambda: settings)
    monkeypatch.setattr(oidc, "_jwks_cache", {})  # 每次测试用真实 Keycloak 会话
    with TestClient(app) as client:
        yield client, settings


def _real_token(settings: Settings, username: str, password: str) -> dict[str, Any]:
    """直连授权向 Keycloak 换真实 token（辅助签名验证 / 冒烟）。"""
    meta = httpx.get(f"{settings.oidc_discovery_url.rstrip('/')}/.well-known/openid-configuration").json()
    r = httpx.post(meta["token_endpoint"], data={
        "grant_type": "password",
        "client_id": settings.oidc_client_id,
        "client_secret": settings.oidc_client_secret,
        "username": username,
        "password": password,
        "scope": "openid profile email",
    }, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()


def _complete_keycloak_login(authz_url: str, username: str, password: str) -> tuple[str, str]:
    """无浏览器完成 Keycloak 登录表单，返回 (code, state) 到 NetSage 回调。"""
    c = httpx.Client(follow_redirects=False, timeout=20.0)
    try:
        # /auth 可能 302 到 login-actions 页，或直接 200 渲染登录表单
        first = c.get(authz_url)
        login_page = c.get(first.headers["location"]) if first.status_code == 302 else first
        assert login_page.status_code == 200, (login_page.status_code, login_page.text[:200])

        m = re.search(r'<form[^>]*id="kc-form-login"[^>]*action="([^"]+)"', login_page.text)
        assert m, "未找到 Keycloak 登录表单"
        action = html.unescape(m.group(1))  # action 里 &amp; 需还原为 &，否则 execution 参数损坏
        hidden = dict(re.findall(r'<input[^>]*type="hidden"[^>]*name="([^"]+)"[^>]*value="([^"]*)"', login_page.text))
        data = {**hidden, "username": username, "password": password, "credentialId": ""}

        post_url = f"http://localhost:9090{action}" if action.startswith("/") else action
        rr = c.post(post_url, data=data)
        for _ in range(12):
            if rr.status_code == 302:
                loc = rr.headers.get("location", "")
                if CALLBACK_PATH in loc:
                    q = httpx.QueryParams(loc.split("?", 1)[1])
                    return q["code"], q["state"]
                rr = c.get(loc)
            elif rr.status_code == 200:
                # 可能多一步 authorize 页，直接再 POST 同 action 兜底
                rr = c.post(post_url, data=data)
            else:
                break
        raise AssertionError(f"登录流程未到达回调: 最后 {rr.status_code} {rr.text[:300]}")
    finally:
        c.close()


# ===== 1. 真实 discovery / JWKS =====


def test_real_discovery_exposes_endpoints(oidc_app):
    _, settings = oidc_app
    meta = httpx.get(f"{settings.oidc_discovery_url.rstrip('/')}/.well-known/openid-configuration").json()
    for key in ("issuer", "authorization_endpoint", "token_endpoint", "jwks_uri"):
        assert meta.get(key) and meta[key].startswith("http"), f"discovery 缺 {key}"
    assert meta["issuer"] == f"{settings.oidc_discovery_url.rstrip('/')}"


def test_real_jwks_rs256_keys(oidc_app):
    _, settings = oidc_app
    meta = httpx.get(f"{settings.oidc_discovery_url.rstrip('/')}/.well-known/openid-configuration").json()
    jwks = httpx.get(meta["jwks_uri"]).json()
    keys = jwks.get("keys", [])
    assert len(keys) >= 1
    assert any(k.get("alg") == "RS256" and k.get("kid") for k in keys)


# ===== 2. /login 重定向到真实 Keycloak =====


def test_login_redirects_with_pkce_params(oidc_app):
    client, _ = oidc_app
    r = client.get("/api/v1/auth/oidc/login", follow_redirects=False)
    assert r.status_code in (302, 307)
    loc = r.headers["location"]
    assert "protocol/openid-connect/auth" in loc
    q = httpx.QueryParams(loc.split("?", 1)[1])
    assert q["response_type"] == "code"
    assert q["client_id"] == OIDC_ENV["OIDC_CLIENT_ID"]
    assert q["state"] and q["nonce"]
    assert q["code_challenge"] and q["code_challenge_method"] == "S256"


# ===== 3. 完整 Authorization Code + PKCE 全链路 =====


def test_full_sso_flow_issues_local_jwt(oidc_app):
    client, settings = oidc_app
    r = client.get("/api/v1/auth/oidc/login", follow_redirects=False)
    code, state = _complete_keycloak_login(r.headers["location"], "alice", "alice")

    r = client.get(CALLBACK_PATH, params={"code": code, "state": state})
    assert r.status_code == 200, r.text
    body = r.json()  # /callback 返回裸 dict（非 Envelope）
    assert body["status"] == "sso_success"
    assert body["user"]["role"] == "engineer"  # alice ∈ netsage-engineer → RBAC
    # 本地 JWT 可解码（PyJWT：verify_signature=False 取 claims；role 为枚举整数值）
    claims = jwt.decode(body["token"], options={"verify_signature": False})
    assert claims.get("role") == 2  # Role.ENGINEER.value


def test_replay_same_code_state_rejected(oidc_app):
    """同一 code+state 二次回调 → state 已单次消费 → 400（防重放）。"""
    client, _ = oidc_app
    r = client.get("/api/v1/auth/oidc/login", follow_redirects=False)
    code, state = _complete_keycloak_login(r.headers["location"], "bob", "bob")

    assert client.get(CALLBACK_PATH, params={"code": code, "state": state}).status_code == 200
    replay = client.get(CALLBACK_PATH, params={"code": code, "state": state})
    assert replay.status_code == 400
    assert "state" in replay.json()["detail"].lower()


def test_bogus_code_rejected(oidc_app):
    client, _ = oidc_app
    r = client.get("/api/v1/auth/oidc/login", follow_redirects=False)
    q = httpx.QueryParams(r.headers["location"].split("?", 1)[1])
    r = client.get(CALLBACK_PATH, params={"code": "not-a-real-code", "state": q["state"]})
    assert r.status_code in (401, 502)  # token 交换失败 → 401；端点异常 → 502


# ===== 4. 真实 id_token 签名验证（辅助审计） =====


def test_real_id_token_signature_verifies(oidc_app):
    """Keycloak 直连授权签发的真实 id_token 用其真实 JWKS 验签通过。"""
    _, settings = oidc_app
    tokens = _real_token(settings, "carol", "carol")
    id_token = tokens["id_token"]
    header = jwt.get_unverified_header(id_token)
    meta = httpx.get(f"{settings.oidc_discovery_url.rstrip('/')}/.well-known/openid-configuration").json()
    jwks = httpx.get(meta["jwks_uri"]).json()
    key = next(k for k in jwks["keys"] if k.get("kid") == header.get("kid"))
    claims = jwt.decode(
        id_token,
        key=jwt.PyJWK(key).key,
        algorithms=[header.get("alg", "RS256")],
        audience=settings.oidc_client_id,
        issuer=meta["issuer"],
        options={"require": ["exp", "iat", "iss", "aud", "sub"]},
    )
    assert claims["preferred_username"] == "carol"
    assert "netsage-auditor" in claims.get("groups", [])


# ===== 5. provision 脚本冒烟（幂等可重跑） =====


def test_provision_script_idempotent():
    """provision 可重复执行且不报错（已有实体跳过）。"""
    r = subprocess.run(
        [sys.executable, str(PROVISION), "--base", KEYCLOAK_BASE],
        capture_output=True, text=True, timeout=120, encoding="utf-8",
    )
    assert r.returncode == 0, r.stderr[-500:]
