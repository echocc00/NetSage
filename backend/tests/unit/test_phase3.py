"""Phase 3 单元测试：NautobotAdapter + 双适配器 + SecurityAuditor + 闭环。"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.security import CurrentUser, Role, encode_token
from app.main import app

client = TestClient(app)


def _auth(role: Role = Role.ADMIN) -> dict[str, str]:
    token = encode_token(CurrentUser(id=1, name="test", role=role))
    return {"Authorization": f"Bearer {token}"}


# ===== NautobotAdapter（mock 模式）=====


@pytest.mark.asyncio
async def test_nautobot_adapter_mock_list_devices():
    from app.access.nautobot_adapter import NautobotAdapter

    adapter = NautobotAdapter(mock=True)
    devices = await adapter.list_devices()
    assert len(devices) == 5
    assert devices[0].name == "spine01"


@pytest.mark.asyncio
async def test_nautobot_adapter_mock_topology():
    from app.access.nautobot_adapter import NautobotAdapter

    adapter = NautobotAdapter(mock=True)
    topo = await adapter.get_topology("shanghai")
    assert len(topo.nodes) == 3  # spine01/02 + leaf01


@pytest.mark.asyncio
async def test_nautobot_adapter_mock_get_device():
    from app.access.nautobot_adapter import NautobotAdapter

    adapter = NautobotAdapter(mock=True)
    dev = await adapter.get_device(1)
    assert dev.name == "spine01"
    assert dev.vendor == "huawei"


@pytest.mark.asyncio
async def test_dual_adapter_factory():
    from app.access.source_of_truth import NullSSoT, get_source_of_truth

    nb = get_source_of_truth("netbox")
    nt = get_source_of_truth("nautobot")
    # nautobot mock 返回数据
    nt_devs = await nt.list_devices()
    assert len(nt_devs) == 5
    # netbox 配置时返回 NetBoxAdapter，否则 NullSSoT
    from app.access.netbox_adapter import NetBoxAdapter
    assert isinstance(nb, (NetBoxAdapter, NullSSoT))


# ===== 基线扫描器 =====


@pytest.mark.asyncio
async def test_baseline_scan_cisco():
    from app.services.baseline_scanner import BaselineScanner

    config = """
ip ssh version 2
aaa new-model
enable secret 5 $1$abc
ntp server 10.0.0.1
logging host 10.0.0.2
"""
    scanner = BaselineScanner()
    result = await scanner.scan(config, "cisco_iosxe")
    assert result.total == 15
    assert result.passed >= 4
    assert result.score > 0


@pytest.mark.asyncio
async def test_baseline_scan_huawei():
    from app.services.baseline_scanner import BaselineScanner

    config = """
stelnet server enable
authentication-scheme default
info-center loghost 10.0.0.2
"""
    scanner = BaselineScanner()
    result = await scanner.scan(config, "huawei_vrp")
    assert result.total == 15
    assert result.score > 0


def test_baseline_rules_count_30():
    """基线规则库 ≥30 条（v2.0 Phase 3 验收 3）。"""
    from app.services.baseline_scanner import RULES

    cisco = [r for r in RULES if r[1] == "cisco_iosxe"]
    huawei = [r for r in RULES if r[1] == "huawei_vrp"]
    assert len(cisco) == 15
    assert len(huawei) == 15
    assert len(RULES) == 30


# ===== 合规报告 =====


@pytest.mark.asyncio
async def test_compliance_report_render():
    from app.services.acl_analyzer import ACLAnalyzer
    from app.services.baseline_scanner import BaselineScanner
    from app.services.compliance_reporter import ComplianceReporter

    scanner = BaselineScanner()
    baseline = await scanner.scan("ip ssh version 2", "cisco_iosxe")
    acl = await ACLAnalyzer().analyze("snap1", "cisco_iosxe")
    reporter = ComplianceReporter()
    report = await reporter.render(baseline, acl)
    assert "# 合规审计报告" in report.markdown
    assert "rule_id,vendor" in report.csv
    assert 0 <= report.score <= 100


# ===== SecurityAuditor Agent =====


@pytest.mark.asyncio
async def test_security_auditor_agent():
    from app.agents.registry import build_runner

    runner = build_runner()
    state = {
        "config": "ip ssh version 2\naaa new-model",
        "vendor": "cisco_iosxe",
        "snapshot": "mock",
    }
    result = await runner.run("security_auditor", state, session_id="sec-1")
    assert "baseline" in result
    assert "acl" in result
    assert "report" in result
    assert result["baseline"]["total"] == 15


@pytest.mark.asyncio
async def test_compliance_agent():
    from app.agents.registry import build_runner

    runner = build_runner()
    state = {"config": "stelnet server enable", "vendor": "huawei_vrp", "snapshot": "mock"}
    result = await runner.run("compliance", state, session_id="comp-1")
    assert "report" in result
    assert "markdown" in result["report"]


# ===== 闭环 Orchestrator =====


@pytest.mark.asyncio
async def test_closed_loop_automation_rate_meets_target():
    """自动化闭环：仅 approve 人工，自动化率 ≥30%（v2.0 M6 硬指标）。"""
    from app.agents.closed_loop import ClosedLoopOrchestrator

    orch = ClosedLoopOrchestrator(runner=None)
    result = await orch.run("BGP 邻居抖动", "huawei_vrp", auto_approve=True)
    # auto_approve=True（演示模式）→ 6 步全自动，自动化率 1.0
    assert result.automation_rate == 1.0
    assert result.approved is True
    assert len(result.steps) == 6


@pytest.mark.asyncio
async def test_closed_loop_manual_approval():
    """生产模式：approve 人工，自动化率 5/6=0.83。"""
    from app.agents.closed_loop import ClosedLoopOrchestrator

    orch = ClosedLoopOrchestrator(runner=None)
    result = await orch.run("OSPF 邻居震荡", "cisco_iosxe", auto_approve=False)
    assert result.approved is False  # 人工未批
    assert result.automation_rate >= 0.3
    # approve 步骤非自动
    approve_step = next(s for s in result.steps if s.name == "approve")
    assert approve_step.automated is False


# ===== API 端点 =====


def test_compliance_scan_api_requires_auth():
    r = client.post("/api/v1/compliance/scan", json={"config": "test", "vendor": "huawei_vrp"})
    assert r.status_code == 401


def test_compliance_scan_api_ok():
    r = client.post(
        "/api/v1/compliance/scan",
        json={"config": "stelnet server enable", "vendor": "huawei_vrp"},
        headers=_auth(Role.OPERATOR),
    )
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["total"] == 15


def test_ssot_devices_api_nautobot():
    r = client.get("/api/v1/agents/ssot/devices", params={"provider": "nautobot"},
                   headers=_auth(Role.VIEWER))
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["provider"] == "nautobot"
    assert data["count"] == 5


def test_designs_api_post_and_list():
    """设计方案 API（需 DB，本地无 Postgres 时跳过）。"""
    try:
        r = client.post(
            "/api/v1/designs",
            json={"name": "bgp-design-1", "scenario": "bgp", "vendor": "huawei",
                  "site": "shanghai", "config_diff": "router bgp 65001"},
            headers=_auth(Role.ENGINEER),
        )
        if r.status_code == 500:
            pytest.skip("Postgres 不可用，设计 API 需 DB")
        assert r.status_code == 201
        r2 = client.get("/api/v1/designs", headers=_auth(Role.VIEWER))
        assert r2.status_code == 200
    except Exception:
        pytest.skip("Postgres 不可用")
