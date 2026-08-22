"""变更审批测试（v2.0 十章 + 十九章验收）。

覆盖：
- 影响范围自动推演（风险分级 + 变更窗口建议）
- 变更 API 端点（创建/跑闸/审批/下发）
- RBAC 权限（engineer 创建、admin 审批、auditor 被拒）
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.gates.impact import ImpactAnalyzer
from app.main import app

client = TestClient(app)


# ===== 影响范围推演 =====


def test_impact_bgp_high_risk():
    """BGP 变更高风险（v2.0 十章影响范围）。"""
    analyzer = ImpactAnalyzer()
    nim = {"topology": {"underlay": {"protocol": "bgp"}}, "business_requirements": [{"service": "专线"}]}
    devices = [{"name": "spine01", "role": "spine"}]
    report = analyzer.analyze(nim, devices)
    assert report.risk_level in ("high", "critical")
    assert "spine01" in report.affected_devices
    assert report.suggested_window == "maintenance"
    assert any("BGP" in r or "Spine" in r for r in report.risk_reasons)


def test_impact_roce_critical():
    """RoCE 变更 critical（影响 AI 训练）。"""
    analyzer = ImpactAnalyzer()
    nim = {"topology": {"underlay": {"protocol": "roce"}}}
    devices = [{"name": "leaf01", "role": "leaf"}]
    report = analyzer.analyze(nim, devices)
    assert report.risk_level == "critical"


def test_impact_affected_services():
    """业务流推演。"""
    analyzer = ImpactAnalyzer()
    nim = {"business_requirements": [{"service": "ai_training"}, {"service": "storage"}]}
    report = analyzer.analyze(nim, [{"name": "l", "role": "leaf"}])
    assert "ai_training" in report.affected_services
    assert "storage" in report.affected_services


# ===== 变更 API 端点 =====


def _auth_token(role: int) -> str:
    from app.core.security import CurrentUser, Role, encode_token

    user = CurrentUser(id=1, name="test", role=Role(role))
    return encode_token(user)


def test_create_change_requires_auth():
    """无 token 401。"""
    r = client.post("/api/v1/changes", json={"title": "t"})
    assert r.status_code == 401


def test_create_change_engineer_ok():
    """engineer 可创建变更（需 draft_change 权限）。"""
    token = _auth_token(2)  # ENGINEER
    r = client.post(
        "/api/v1/changes",
        json={
            "title": "BGP peering 变更",
            "nim": {"topology": {"underlay": {"protocol": "bgp"}}},
            "devices": [{"id": 1, "name": "spine01", "vendor": "huawei_vrp", "host": "10.1.2.3", "username": "a", "password": "b"}],
            "configs": {"spine01": "router bgp 65001"},
            "assertions": [{"type": "reachibility", "src": "spine01", "dst": "leaf01"}],
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["status"] == "draft"
    assert data["impact"]["risk_level"] in ("high", "critical")
    assert "spine01" in data["impact"]["affected_devices"]


def test_create_change_auditor_blocked():
    """auditor 无 draft_change 权限，403（等保三权分立）。"""
    token = _auth_token(4)  # AUDITOR
    r = client.post("/api/v1/changes", json={"title": "t"}, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403


def test_run_gates_full_pipeline():
    """跑三道闸：快照→仿真→校验→approval pending（v2.0 十九章验收）。"""
    token = _auth_token(2)  # ENGINEER
    # 创建
    r = client.post(
        "/api/v1/changes",
        json={
            "title": "BGP 变更",
            "nim": {"topology": {"underlay": {"protocol": "bgp"}}, "sim_checks": [{"node": "spine01", "command": "show bgp", "expect": "Up"}]},
            "devices": [{"id": 1, "name": "spine01", "vendor": "huawei_vrp", "host": "10.1.2.3", "username": "a", "password": "b"}],
            "configs": {"spine01": "router bgp 65001"},
            "assertions": [{"type": "reachability", "src": "spine01", "dst": "leaf01"}],
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    cid = r.json()["data"]["id"]
    # 跑闸
    r2 = client.post(f"/api/v1/changes/{cid}/run", headers={"Authorization": f"Bearer {token}"})
    assert r2.status_code == 200
    result = r2.json()["data"]
    gates = [s["gate"] for s in result["steps"]]
    assert "snapshot" in gates
    assert "simulation" in gates
    assert "validation" in gates
    assert "approval" in gates
    assert result["status"] == "approval"
    assert result["approval_pending"] is True


def test_approve_requires_admin():
    """审批需 admin（approve 权限），engineer 403。"""
    token_eng = _auth_token(2)  # ENGINEER
    token_admin = _auth_token(3)  # ADMIN
    # 创建 + 跑闸
    r = client.post("/api/v1/changes", json={"title": "t", "nim": {}, "devices": [{"id":1,"name":"d","vendor":"huawei_vrp","host":"x","username":"a","password":"b"}], "configs": {}, "assertions": []}, headers={"Authorization": f"Bearer {token_eng}"})
    cid = r.json()["data"]["id"]
    client.post(f"/api/v1/changes/{cid}/run", headers={"Authorization": f"Bearer {token_eng}"})
    # engineer 审批 403
    r_eng = client.post(f"/api/v1/changes/{cid}/approve?decision=approved", headers={"Authorization": f"Bearer {token_eng}"})
    assert r_eng.status_code == 403
    # admin 审批 200
    r_admin = client.post(f"/api/v1/changes/{cid}/approve?decision=approved", headers={"Authorization": f"Bearer {token_admin}"})
    assert r_admin.status_code == 200
    assert r_admin.json()["data"]["status"] == "approved"


def test_deploy_requires_approved_status():
    """未审批不可下发，409。"""
    token = _auth_token(3)  # ADMIN
    # 创建但未跑闸/审批
    r = client.post("/api/v1/changes", json={"title": "t", "nim": {}, "devices": [{"id":1,"name":"d","vendor":"huawei_vrp","host":"x","username":"a","password":"b"}], "configs": {}, "assertions": []}, headers={"Authorization": f"Bearer {token}"})
    cid = r.json()["data"]["id"]
    r2 = client.post(f"/api/v1/changes/{cid}/deploy", headers={"Authorization": f"Bearer {token}"})
    assert r2.status_code == 409


def test_impact_confirm_modifies_report():
    """工程师可修改影响范围（人工确认）。"""
    token = _auth_token(2)
    r = client.post("/api/v1/changes", json={"title": "t", "nim": {}, "devices": [], "configs": {}, "assertions": []}, headers={"Authorization": f"Bearer {token}"})
    cid = r.json()["data"]["id"]
    r2 = client.post(f"/api/v1/changes/{cid}/impact/confirm", json={"risk_level": "high", "affected_devices": ["extra-device"]}, headers={"Authorization": f"Bearer {token}"})
    assert r2.status_code == 200
    data = r2.json()["data"]
    assert data["risk_level"] == "high"
    assert "extra-device" in data["affected_devices"]
    assert data["confirmed_by"] == "test"
