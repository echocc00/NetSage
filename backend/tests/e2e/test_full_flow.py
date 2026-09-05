"""E2E 完整业务链路测试（P7-6）。

TestClient 跑真实 HTTP 链路（含中间件/依赖注入/RBAC/审计），
覆盖 v2.0 核心承诺：设计 → 三道闸 → 审批 → 下发 → 报表 + 安全边界。

与 tests/unit 的区别：这里跑跨模块的完整场景（多个 API 串联 + 状态流转），
不 mock 内部实现，只在设备侧用 MockToolRegistry（无真实网络设备）。
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.security import CurrentUser, Role, encode_token
from app.main import app

client = TestClient(app)


def _headers(role: Role) -> dict[str, str]:
    return {"Authorization": f"Bearer {encode_token(CurrentUser(id=1, name=role.name.lower(), role=role))}"}


@pytest.fixture
def engineer() -> dict[str, str]:
    return _headers(Role.ENGINEER)


@pytest.fixture
def admin() -> dict[str, str]:
    return _headers(Role.ADMIN)


@pytest.fixture
def auditor() -> dict[str, str]:
    return _headers(Role.AUDITOR)


@pytest.fixture
def viewer() -> dict[str, str]:
    return _headers(Role.VIEWER)


DEVICES = [
    {"id": 1, "name": "spine01", "vendor": "huawei_vrp",
     "host": "10.1.1.1", "username": "netsage", "password": "secret"},
]
CONFIGS = {"spine01": "bgp 65001\n peer 10.1.1.2 as-number 65002"}


# ===== 场景 1：完整变更闭环（设计 → 三道闸 → 审批 → 下发）=====


@pytest.mark.e2e
def test_change_full_lifecycle(engineer, admin):
    """engineer 建变更 → 确认影响 → 跑三道闸 → admin 审批 → 下发。"""
    # 1. 创建变更（engineer）
    r = client.post("/api/v1/changes", headers=engineer, json={
        "title": "E2E: 上海-广州 eBGP peering",
        "nim": {"intent": "config", "scenario": "bgp"},
        "devices": DEVICES,
        "configs": CONFIGS,
        "assertions": [{"type": "reachability", "src": "spine01", "dst": "10.1.1.2"}],
    })
    assert r.status_code == 200, r.text
    change = r.json()["data"]
    cid = change["id"]
    assert change["status"] == "draft"
    assert change["impact"] is not None, "影响范围未自动推演"

    # 2. 查影响范围
    r = client.get(f"/api/v1/changes/{cid}/impact", headers=engineer)
    assert r.status_code == 200
    impact = r.json()["data"]
    assert "affected_devices" in impact or "risk_level" in impact

    # 3. 人工确认影响范围（v2.0：自动推演 + 人工确认）
    r = client.post(f"/api/v1/changes/{cid}/impact/confirm", headers=engineer,
                    json={"reviewed": True})
    assert r.status_code == 200
    assert r.json()["data"]["confirmed_by"] == "engineer"

    # 4. 跑三道闸（快照 → 仿真 → 校验 → 审批 pending）
    r = client.post(f"/api/v1/changes/{cid}/run", headers=engineer)
    assert r.status_code == 200, r.text
    pipeline = r.json()["data"]
    assert pipeline["status"] == "approval", f"三道闸未进入审批态: {pipeline}"
    # 三道闸都留下证据
    gates = {step["gate"] for step in pipeline["steps"]}
    assert {"snapshot", "simulation", "validation", "approval"} <= gates, f"闸缺失: {gates}"
    assert all(s.get("passed", True) for s in pipeline["steps"]), "有闸未通过"

    # 5. admin 审批
    r = client.post(f"/api/v1/changes/{cid}/approve", headers=admin,
                    params={"decision": "approved"})
    assert r.status_code == 200
    assert r.json()["data"]["status"] == "approved"
    assert r.json()["data"]["approver"] == "admin"

    # 6. 下发
    r = client.post(f"/api/v1/changes/{cid}/deploy", headers=admin)
    assert r.status_code == 200, r.text
    assert r.json()["data"]["status"] in ("done", "deployed", "success")


@pytest.mark.e2e
def test_change_cannot_deploy_without_approval(engineer, admin):
    """未审批直接下发 → 409（写通道门禁）。"""
    r = client.post("/api/v1/changes", headers=engineer, json={
        "title": "E2E: 未审批", "nim": {}, "devices": DEVICES, "configs": CONFIGS,
    })
    cid = r.json()["data"]["id"]
    r = client.post(f"/api/v1/changes/{cid}/deploy", headers=admin)
    assert r.status_code == 409
    assert "未审批" in r.json()["detail"]


@pytest.mark.e2e
def test_change_cannot_approve_before_gates(engineer, admin):
    """三道闸未跑完直接审批 → 409（不可跳闸）。"""
    r = client.post("/api/v1/changes", headers=engineer, json={
        "title": "E2E: 跳闸", "nim": {}, "devices": DEVICES, "configs": CONFIGS,
    })
    cid = r.json()["data"]["id"]
    r = client.post(f"/api/v1/changes/{cid}/approve", headers=admin,
                    params={"decision": "approved"})
    assert r.status_code == 409


# ===== 场景 2：RBAC 边界（五级权限）=====


@pytest.mark.e2e
def test_rbac_viewer_cannot_create_change(viewer):
    """viewer 无 draft_change 权限 → 403。"""
    r = client.post("/api/v1/changes", headers=viewer, json={
        "title": "E2E", "nim": {}, "devices": [], "configs": {},
    })
    assert r.status_code == 403


@pytest.mark.e2e
def test_rbac_engineer_cannot_approve(engineer):
    """engineer 可拟变更但不可审批（三权分立）。"""
    r = client.post("/api/v1/changes", headers=engineer, json={
        "title": "E2E: RBAC", "nim": {}, "devices": DEVICES, "configs": CONFIGS,
    })
    cid = r.json()["data"]["id"]
    r = client.post(f"/api/v1/changes/{cid}/approve", headers=engineer,
                    params={"decision": "approved"})
    assert r.status_code == 403


@pytest.mark.e2e
def test_rbac_auditor_cannot_deploy(auditor):
    """auditor 独立审计维度，不获写权限（等保三权分立）。"""
    r = client.post("/api/v1/changes/1/deploy", headers=auditor)
    assert r.status_code == 403


@pytest.mark.e2e
def test_rbac_auditor_can_read_compliance(auditor):
    """auditor 有 audit 权限，可查合规报告。"""
    r = client.post("/api/v1/compliance/report", headers=auditor, json={
        "config": "telnet server enable", "vendor": "huawei_vrp",
    })
    assert r.status_code == 200
    assert r.json()["data"]["score"] >= 0


@pytest.mark.e2e
def test_unauthenticated_rejected():
    """无 token → 401（所有业务端点）。"""
    for method, path in [
        ("post", "/api/v1/changes"),
        ("get", "/api/v1/reports/dashboard"),
        ("post", "/api/v1/compliance/scan"),
        ("post", "/api/v1/wireless/plan"),
    ]:
        r = client.post(path, json={}) if method == "post" else client.get(path)
        assert r.status_code == 401, f"{method} {path} 未要求认证（得到 {r.status_code}）"


# ===== 场景 3：安全审计闭环（扫描 → 攻击面 → 报告）=====


@pytest.mark.e2e
def test_security_audit_closed_loop(admin):
    """裸配置扫描 → 低分 + 风险清单 → 加固后复扫 → 分数提升。"""
    bare = "telnet server enable\nsnmp-agent community public\nhttp server enable"
    r = client.post("/api/v1/compliance/scan", headers=admin,
                    json={"config": bare, "vendor": "huawei_vrp"})
    assert r.status_code == 200
    before = r.json()["data"]
    assert before["failed"] > 0
    assert before["total"] == 15

    hardened = (
        "stelnet server enable\nundo telnet server enable\n"
        "authentication-scheme default\npassword-policy\n"
        "authentication-mode aaa\ninfo-center loghost 10.0.0.2\n"
        "info-center timestamp log date\nntp-service unicast-server 10.0.0.1\n"
    )
    r = client.post("/api/v1/compliance/scan", headers=admin,
                    json={"config": hardened, "vendor": "huawei_vrp"})
    after = r.json()["data"]
    assert after["score"] > before["score"], "加固后合规分未提升"

    # 报告含攻击面 + 加固优先级（P7-5 深化）
    r = client.post("/api/v1/compliance/report", headers=admin,
                    json={"config": bare, "vendor": "huawei_vrp"})
    assert r.status_code == 200
    md = r.json()["data"]["markdown"]
    assert "# 合规审计报告" in md
    assert "rule_id,vendor" in r.json()["data"]["csv"]


# ===== 场景 4：Agent 编排链路（排障 → 闭环）=====


@pytest.mark.e2e
def test_troubleshoot_to_closed_loop(admin):
    """排障出根因 → 自动化闭环（诊断→修复→验证→审批→下发→监控）。"""
    r = client.post("/api/v1/agents/sessions/e2e-1/troubleshoot", headers=admin, json={
        "symptom": "BGP-5-ADJCHG: Neighbor 10.1.1.2 Down, hello timer expired",
        "vendor": "huawei",
    })
    assert r.status_code == 200, r.text
    causes = r.json()["data"]["root_causes"]
    assert len(causes) >= 3, "RCA 未给出 ≥3 候选根因"
    assert all("cause" in c for c in causes)

    # 闭环（演示模式自动过审批）
    r = client.post("/api/v1/agents/closed-loop", headers=admin, json={
        "symptom": "BGP 邻居抖动", "vendor": "huawei_vrp", "auto_approve": True,
    })
    assert r.status_code == 200, r.text
    loop = r.json()["data"]
    assert loop["meets_target"] is True, f"自动化率未达标: {loop['automation_rate']}"
    assert len(loop["steps"]) == 6
    assert [s["name"] for s in loop["steps"]] == [
        "diagnose", "fix", "verify", "approve", "deploy", "observe",
    ]


@pytest.mark.e2e
def test_closed_loop_requires_deploy_permission(engineer):
    """闭环需 deploy 权限（engineer 无）。"""
    r = client.post("/api/v1/agents/closed-loop", headers=engineer, json={
        "symptom": "BGP 抖动", "auto_approve": True,
    })
    assert r.status_code == 403


@pytest.mark.e2e
def test_closed_loop_production_blocks_on_approval(admin):
    """生产模式（auto_approve=False）在审批处停止，不自动下发。"""
    r = client.post("/api/v1/agents/closed-loop", headers=admin, json={
        "symptom": "OSPF 邻居震荡", "vendor": "cisco_iosxe", "auto_approve": False,
    })
    assert r.status_code == 200
    loop = r.json()["data"]
    assert loop["approved"] is False
    assert loop["deployed"] == []  # 未审批不下发
    approve_step = next(s for s in loop["steps"] if s["name"] == "approve")
    assert approve_step["automated"] is False


# ===== 场景 5：专项 Agent（RDMA / 无线）=====


@pytest.mark.e2e
def test_rdma_diagnose_to_tuning(admin):
    """RoCE 症状 → 诊断 → 调优参数 + 配置。"""
    r = client.post("/api/v1/rdma/diagnose", headers=admin, json={
        "symptom": "RoCEv2 丢包，allreduce 延迟从 5μs 升到 50μs",
        "vendor": "huawei", "link_speed_gbps": 400,
    })
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    assert d["diagnosis"]["bottleneck"]
    assert d["tuning"]["pfc_priority"] in (0, 1, 2, 3)
    assert "KB" in d["tuning"]["pfc_headroom"]


@pytest.mark.e2e
def test_wireless_plan_to_config(admin):
    """无线需求 → AP 规划 + 射频 + 漫游 + 安全 + 配置。"""
    r = client.post("/api/v1/wireless/plan", headers=admin, json={
        "area_sqm": 1200, "users": 300, "floors": 3,
        "ssid": "E2E-WiFi", "vendor": "huawei",
    })
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    assert d["plan"]["total_aps"] >= 6
    assert len(d["plan"]["ap_plan"]) == d["plan"]["total_aps"]
    assert len(d["recommendations"]) >= 5


# ===== 场景 6：报表 + 健康检查 =====


@pytest.mark.e2e
def test_reports_and_health(admin, viewer):
    """大屏 + 各维度报表可读（viewer 也可读）。"""
    for path in ("/api/v1/reports/dashboard", "/api/v1/reports/overview",
                 "/api/v1/reports/devices", "/api/v1/reports/changes",
                 "/api/v1/reports/compliance"):
        r = client.get(path, headers=viewer)
        assert r.status_code == 200, f"{path} 失败"
        assert r.json()["success"] is True

    r = client.get("/api/v1/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"

    r = client.get("/api/v1/health/ready")
    assert r.status_code == 200
    deps = {d["name"] for d in r.json()["deps"]}
    assert deps == {"postgres", "redis", "llm", "ssot"}


# ===== 场景 7：双 SSoT 切换 =====


@pytest.mark.e2e
def test_dual_ssot_switch(viewer):
    """NetBox / Nautobot 双适配器可切换（业务层零改）。"""
    r = client.get("/api/v1/agents/ssot/devices",
                   params={"provider": "nautobot"}, headers=viewer)
    assert r.status_code == 200
    d = r.json()["data"]
    assert d["provider"] == "nautobot"
    assert d["count"] == 5
    assert all("vendor" in dev for dev in d["devices"])


# ===== 场景 8：脱敏安全边界（P7-1）=====


@pytest.mark.e2e
def test_blackbox_never_reaches_llm():
    """黑盒内容（running-config）不可能通过 LLM 网关外发。"""
    import asyncio

    from app.redact.layer3_router import BlackboxBlockError
    from app.services.llm_gateway import LLMGateway

    gw = LLMGateway()
    with pytest.raises(BlackboxBlockError):
        asyncio.run(gw.complete(
            [{"role": "user", "content": "interface GE0/0/1\n ip address 10.1.1.1 24"}],
            content_type="running_config",
        ))


@pytest.mark.e2e
def test_openapi_documents_all_routers():
    """OpenAPI 覆盖所有业务 tag（客户对接凭据）。"""
    r = client.get("/openapi.json")
    assert r.status_code == 200
    spec = r.json()
    tags = {t["name"] for t in spec.get("tags", [])}
    assert {"health", "auth", "agents", "devices", "changes",
            "compliance", "rdma", "wireless", "reports"} <= tags
    # 关键路径都有文档
    for path in ("/api/v1/changes", "/api/v1/agents/closed-loop",
                 "/api/v1/compliance/scan", "/api/v1/reports/dashboard"):
        assert path in spec["paths"], f"{path} 未出现在 OpenAPI"
