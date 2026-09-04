"""Troubleshooter Agent 测试（Phase 2 P2-10）。"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.agents.registry import build_runner
from app.core.security import CurrentUser, Role, encode_token
from app.main import app

client = TestClient(app)


def _auth() -> dict[str, str]:
    token = encode_token(CurrentUser(id=1, name="test", role=Role.OPERATOR))
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_troubleshooter_full_flow_bgp():
    """Troubleshooter 完整链路：collect → analyze → suggest_fixes。"""
    runner = build_runner()
    assert "troubleshooter" in runner._compiled

    result = await runner.run(
        "troubleshooter",
        {
            "query": "BGP 邻居反复抖动 Hello expired",
            "scenario": "bgp",
            "device": {"name": "spine01"},
        },
        session_id="ts-1",
    )

    # ≥3 候选根因（v2.0 22.2）
    causes = result.get("root_causes", [])
    assert len(causes) >= 3
    # 按概率排序
    probs = [c["probability"] for c in causes]
    assert probs == sorted(probs, reverse=True)
    # 每个含 verify + fix
    for c in causes:
        assert c["verify_command"]
        assert c["fix"]
    # 修复建议
    fixes = result.get("fixes", [])
    assert len(fixes) >= 1
    assert all(f["requires_approval"] for f in fixes)  # 修复需走三道闸


@pytest.mark.asyncio
async def test_troubleshooter_ospf_crc():
    """OSPF + CRC → 物理根因进入 top 3（与 network_type 平分时排序取决于细节）。"""
    runner = build_runner()
    result = await runner.run(
        "troubleshooter",
        {"query": "OSPF 邻居震荡 接口 CRC 错误", "scenario": "ospf"},
        session_id="ts-2",
    )
    causes = result["root_causes"]
    # CRC 关键词应在 top 3 触发 physical 根因
    top3 = causes[:3]
    assert any(c["category"] == "physical" for c in top3), \
        f"physical 根因未进 top3: {[c['cause'] for c in top3]}"


@pytest.mark.asyncio
async def test_troubleshooter_low_confidence_requires_human():
    """低置信度根因标记需人工确认。"""
    runner = build_runner()
    result = await runner.run(
        "troubleshooter",
        {"query": "模糊问题", "scenario": "bgp"},
        session_id="ts-3",
    )
    fixes = result.get("fixes", [])
    # 至少有 requires_human_confirm 字段
    assert all("requires_human_confirm" in f for f in fixes)


def test_api_troubleshoot_bgp():
    """POST /agents/sessions/{id}/troubleshoot。"""
    response = client.post(
        "/api/v1/agents/sessions/ts-api/troubleshoot",
        json={"query": "BGP 邻居抖动", "vendor": "huawei", "context": {"scenario": "bgp"}},
        headers=_auth(),
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data["root_causes"]) >= 3
    assert len(data["fixes"]) >= 1


def test_api_troubleshoot_requires_auth():
    """无 token 401。"""
    response = client.post(
        "/api/v1/agents/sessions/ts-x/troubleshoot",
        json={"query": "BGP 抖动"},
    )
    assert response.status_code == 401


def test_api_troubleshoot_operator_role_ok():
    """operator 角色可排障（troubleshoot 权限，v2.0 十章 RBAC）。"""
    # operator = role 1，有 troubleshoot 权限
    response = client.post(
        "/api/v1/agents/sessions/ts-op/troubleshoot",
        json={"query": "OSPF 邻居问题", "context": {"scenario": "ospf"}},
        headers=_auth(),  # OPERATOR token
    )
    assert response.status_code == 200
