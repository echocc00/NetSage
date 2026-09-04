"""OIDC 完整流程测试（P7-4）：PKCE + nonce + JWKS 验签。"""
from __future__ import annotations

import base64
import hashlib
import time

import jwt
import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


# ===== 未配置 SSO 时的降级 =====


def test_config_disabled_when_unconfigured():
    r = client.get("/api/v1/auth/oidc/config")
    assert r.status_code == 200
    d = r.json()["data"]
    assert d["enabled"] is False
    assert d["pkce"] is True  # PKCE 始终启用


def test_login_503_when_unconfigured():
    r = client.get("/api/v1/auth/oidc/login")
    assert r.status_code == 503


# ===== PKCE =====


def test_pkce_challenge_is_s256_of_verifier():
    from app.api.v1.oidc import _gen_pkce

    verifier, challenge = _gen_pkce()
    expected = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode("ascii")).digest()
    ).decode("ascii").rstrip("=")
    assert challenge == expected
    assert 43 <= len(verifier) <= 128  # RFC 7636 §4.1


def test_pkce_verifier_unique_per_call():
    from app.api.v1.oidc import _gen_pkce

    v1, _ = _gen_pkce()
    v2, _ = _gen_pkce()
    assert v1 != v2


# ===== state 防 CSRF / replay =====


def test_callback_rejects_unknown_state():
    r = client.get("/api/v1/auth/oidc/callback", params={"code": "x", "state": "forged"})
    assert r.status_code == 400
    assert "state" in r.json()["detail"]


def test_state_single_use():
    """state 用过即失效（防 replay）。"""
    from app.api.v1.oidc import _PendingAuth, _pending

    _pending["st1"] = _PendingAuth(tenant="default", nonce="n1", code_verifier="v1")
    # 第一次会走到 token 交换（因 SSO 未配置会失败），但 state 已被 pop
    client.get("/api/v1/auth/oidc/callback", params={"code": "c", "state": "st1"})
    assert "st1" not in _pending
    # 第二次必须 400
    r2 = client.get("/api/v1/auth/oidc/callback", params={"code": "c", "state": "st1"})
    assert r2.status_code == 400


def test_state_expires():
    from app.api.v1.oidc import STATE_TTL, _PendingAuth

    old = _PendingAuth(tenant="d", nonce="n", code_verifier="v")
    old.created_at = time.time() - STATE_TTL - 1
    assert old.expired

    fresh = _PendingAuth(tenant="d", nonce="n", code_verifier="v")
    assert not fresh.expired


def test_prune_removes_expired_states():
    from app.api.v1.oidc import STATE_TTL, _PendingAuth, _pending, _prune_expired

    _pending.clear()
    stale = _PendingAuth(tenant="d", nonce="n", code_verifier="v")
    stale.created_at = time.time() - STATE_TTL - 10
    _pending["stale"] = stale
    _pending["fresh"] = _PendingAuth(tenant="d", nonce="n", code_verifier="v")
    _prune_expired()
    assert "stale" not in _pending
    assert "fresh" in _pending
    _pending.clear()


# ===== ID token 验签 =====


@pytest.mark.asyncio
async def test_id_token_rejected_without_jwks(monkeypatch):
    """IDP 无 jwks_uri → 拒绝（不接受未验签 token）。"""
    from fastapi import HTTPException

    from app.api.v1 import oidc

    async def fake_discover():
        return {}  # 无 jwks_uri

    monkeypatch.setattr(oidc, "_discover", fake_discover)
    with pytest.raises(HTTPException) as exc:
        await oidc._verify_id_token("fake.token.here", expected_nonce="n")
    assert exc.value.status_code == 401
    assert "jwks" in exc.value.detail.lower()


@pytest.mark.asyncio
async def test_nonce_mismatch_rejected(monkeypatch):
    """nonce 不匹配 → 拒绝（replay 防护）。"""
    from cryptography.hazmat.primitives.asymmetric import rsa
    from fastapi import HTTPException

    from app.api.v1 import oidc

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    token = jwt.encode(
        {
            "sub": "user1", "iss": "https://idp.test", "aud": "netsage-client",
            "exp": int(time.time()) + 300, "iat": int(time.time()),
            "nonce": "WRONG_NONCE",
        },
        key, algorithm="RS256", headers={"kid": "k1"},
    )
    pub_numbers = key.public_key().public_numbers()

    def _b64(n: int) -> str:
        raw = n.to_bytes((n.bit_length() + 7) // 8, "big")
        return base64.urlsafe_b64encode(raw).decode().rstrip("=")

    jwks = {"keys": [{"kty": "RSA", "kid": "k1", "alg": "RS256", "use": "sig",
                      "n": _b64(pub_numbers.n), "e": _b64(pub_numbers.e)}]}

    async def fake_discover():
        return {"issuer": "https://idp.test", "jwks_uri": "https://idp.test/jwks"}

    async def fake_jwks(uri):
        return jwks

    monkeypatch.setattr(oidc, "_discover", fake_discover)
    monkeypatch.setattr(oidc, "_fetch_jwks", fake_jwks)
    monkeypatch.setattr(oidc._settings(), "oidc_client_id", "netsage-client")

    with pytest.raises(HTTPException) as exc:
        await oidc._verify_id_token(token, expected_nonce="CORRECT_NONCE")
    assert exc.value.status_code == 401
    assert "nonce" in exc.value.detail


@pytest.mark.asyncio
async def test_valid_id_token_accepted(monkeypatch):
    """完整验签通过：签名 + iss + aud + exp + nonce。"""
    from cryptography.hazmat.primitives.asymmetric import rsa

    from app.api.v1 import oidc

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    nonce = "the-nonce"
    token = jwt.encode(
        {
            "sub": "user1", "iss": "https://idp.test", "aud": "netsage-client",
            "exp": int(time.time()) + 300, "iat": int(time.time()),
            "nonce": nonce, "preferred_username": "alice",
            "groups": ["netsage-engineer"],
        },
        key, algorithm="RS256", headers={"kid": "k1"},
    )
    pub = key.public_key().public_numbers()

    def _b64(n: int) -> str:
        raw = n.to_bytes((n.bit_length() + 7) // 8, "big")
        return base64.urlsafe_b64encode(raw).decode().rstrip("=")

    async def fake_discover():
        return {"issuer": "https://idp.test", "jwks_uri": "https://idp.test/jwks"}

    async def fake_jwks(uri):
        return {"keys": [{"kty": "RSA", "kid": "k1", "alg": "RS256", "use": "sig",
                          "n": _b64(pub.n), "e": _b64(pub.e)}]}

    monkeypatch.setattr(oidc, "_discover", fake_discover)
    monkeypatch.setattr(oidc, "_fetch_jwks", fake_jwks)
    monkeypatch.setattr(oidc._settings(), "oidc_client_id", "netsage-client")

    claims = await oidc._verify_id_token(token, expected_nonce=nonce)
    assert claims["sub"] == "user1"
    assert claims["preferred_username"] == "alice"


@pytest.mark.asyncio
async def test_expired_token_rejected(monkeypatch):
    """过期 token → 拒绝。"""
    from cryptography.hazmat.primitives.asymmetric import rsa
    from fastapi import HTTPException

    from app.api.v1 import oidc

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    token = jwt.encode(
        {"sub": "u", "iss": "https://idp.test", "aud": "netsage-client",
         "exp": int(time.time()) - 10, "iat": int(time.time()) - 300, "nonce": "n"},
        key, algorithm="RS256", headers={"kid": "k1"},
    )
    pub = key.public_key().public_numbers()

    def _b64(n: int) -> str:
        raw = n.to_bytes((n.bit_length() + 7) // 8, "big")
        return base64.urlsafe_b64encode(raw).decode().rstrip("=")

    async def fake_discover():
        return {"issuer": "https://idp.test", "jwks_uri": "https://idp.test/jwks"}

    async def fake_jwks(uri):
        return {"keys": [{"kty": "RSA", "kid": "k1", "alg": "RS256",
                          "n": _b64(pub.n), "e": _b64(pub.e)}]}

    monkeypatch.setattr(oidc, "_discover", fake_discover)
    monkeypatch.setattr(oidc, "_fetch_jwks", fake_jwks)
    monkeypatch.setattr(oidc._settings(), "oidc_client_id", "netsage-client")

    with pytest.raises(HTTPException) as exc:
        await oidc._verify_id_token(token, expected_nonce="n")
    assert exc.value.status_code == 401


# ===== 角色映射 =====


def test_role_mapping_from_groups():
    from app.core.security import Role
    from app.api.v1.oidc import _map_user

    u = _map_user({"sub": "s1", "preferred_username": "bob", "groups": ["netsage-admin"]})
    assert u.role == Role.ADMIN
    assert u.name == "bob"


def test_role_mapping_picks_highest():
    from app.core.security import Role
    from app.api.v1.oidc import _map_user

    u = _map_user({"sub": "s", "groups": ["netsage-viewer", "netsage-engineer"]})
    assert u.role == Role.ENGINEER


def test_role_mapping_defaults_to_viewer():
    """无匹配 group → 最小权限（viewer），不默认给 engineer。"""
    from app.core.security import Role
    from app.api.v1.oidc import _map_user

    u = _map_user({"sub": "s", "groups": ["some-other-group"]})
    assert u.role == Role.VIEWER


def test_role_mapping_no_groups_claim():
    from app.core.security import Role
    from app.api.v1.oidc import _map_user

    u = _map_user({"sub": "s", "email": "x@y.com"})
    assert u.role == Role.VIEWER
    assert u.name == "x@y.com"
