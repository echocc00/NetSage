"""Phase 4 M10/M11 测试：WirelessAgent + 多租户 + OIDC。"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.security import CurrentUser, Role, encode_token
from app.main import app

client = TestClient(app)


def _auth(role: Role = Role.ADMIN) -> dict[str, str]:
    return {"Authorization": f"Bearer {encode_token(CurrentUser(id=1, name='test', role=role))}"}


# ===== WirelessAgent =====


@pytest.mark.asyncio
async def test_wireless_agent_plan():
    """WirelessAgent 跑通 collect → plan → suggest_config。"""
    from app.agents.registry import build_runner

    runner = build_runner()
    state = {"area_sqm": 1000, "users": 200, "floors": 2, "ssid": "Corp-WiFi", "vendor": "huawei"}
    result = await runner.run("wireless_agent", state, session_id="wlan-1")
    assert result["plan"]["total_aps"] >= 4
    assert len(result["plan"]["ap_plan"]) >= 4
    assert len(result["recommendations"]) >= 3


@pytest.mark.asyncio
async def test_wireless_agent_channel_rotation():
    """信道轮转：2.4G 1/6/11 错开。"""
    from app.agents.registry import build_runner

    runner = build_runner()
    result = await runner.run("wireless_agent", {"area_sqm": 300, "users": 50, "floors": 1, "vendor": "cisco"}, session_id="wlan-2")
    channels = [ap["channel_2g"] for ap in result["plan"]["ap_plan"]]
    assert all(c in [1, 6, 11] for c in channels)


# ===== Agent 注册 10 =====


def test_agent_count_10():
    """v0.3.0 验收：10 Agent（+WirelessAgent）。"""
    from app.agents.registry import build_runner

    runner = build_runner()
    agents = list(runner._compiled.keys())
    assert len(agents) >= 10
    assert "wireless_agent" in agents


# ===== 无线模板 =====


def test_wireless_templates_exist():
    """无线模板 ≥6（3 厂商 × ssid/roaming）。"""
    from app.services.template_loader import list_by_vendor

    count = sum(len([m for m in list_by_vendor(v) if m["protocol"] == "wireless"]) for v in ["huawei", "cisco", "h3c"])
    assert count >= 6


# ===== API =====


def test_wireless_plan_api():
    r = client.post("/api/v1/wireless/plan", json={"area_sqm": 500, "users": 100, "vendor": "huawei"}, headers=_auth())
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["plan"]["total_aps"] >= 2


def test_wireless_templates_api():
    r = client.get("/api/v1/wireless/templates", headers=_auth(Role.VIEWER))
    assert r.status_code == 200
    assert r.json()["data"]["count"] >= 6


# ===== OIDC / 多租户 =====


def test_oidc_config_disabled():
    """未配置 OIDC → enabled=False。"""
    r = client.get("/api/v1/auth/oidc/config")
    assert r.status_code == 200
    assert r.json()["data"]["enabled"] is False


def test_oidc_login_not_configured():
    """SSO 未配置 → 503。"""
    r = client.get("/api/v1/auth/oidc/login")
    assert r.status_code == 503


def test_tenant_create_api():
    r = client.post("/api/v1/auth/oidc/tenants", json={"name": "Acme", "slug": "acme", "plan": "pro"}, headers=_auth())
    assert r.status_code == 200
    assert r.json()["data"]["slug"] == "acme"


def test_tenant_list_api():
    r = client.get("/api/v1/auth/oidc/tenants", headers=_auth())
    assert r.status_code == 200
    assert len(r.json()["data"]["tenants"]) >= 1


# ===== Tenant model =====


def test_tenant_model():
    from app.models.tenant import Tenant

    cols = [c.name for c in Tenant.__table__.columns]
    assert "slug" in cols
    assert "oidc_client_id" in cols
    assert "sso_enabled" in cols


# ===== 评测集 =====


def test_bench_513():
    """NetAI-Bench：513 题，5 类齐全。"""
    from eval.runner import load_dataset

    qs = load_dataset()
    assert len(qs) >= 513
    cats = {q.category for q in qs}
    assert cats >= {"troubleshoot", "config", "design", "audit", "perf"}
