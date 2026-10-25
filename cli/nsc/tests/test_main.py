"""nsc CLI 命令测试（respx 拦截 httpx，不碰真实后端）。

覆盖：命令面（≥5 子命令）、version/status/health/login/ask/gen/simulate/report、
客户端 API 路径与 payload、失败路径 exit code。
注意：NSCClient 各方法取 `r.json()["data"]`，mock 响应体须带 `data` 键；
  health 端点默认裸返回（HealthResponse），不带 `data`。
"""
from __future__ import annotations

import json
import re

import httpx
import respx

from nsc import __version__
import nsc.main as main

TEST_BACKEND = "http://testserver"

HEALTH_URL = f"{TEST_BACKEND}/api/v1/health"
SESSION_URL = f"{TEST_BACKEND}/api/v1/agents/sessions"
SESSION_RE = re.compile(rf"{re.escape(TEST_BACKEND)}/api/v1/agents/sessions/[^/]+/config")
VALIDATE_RE = re.compile(rf"{re.escape(TEST_BACKEND)}/api/v1/agents/sessions/[^/]+/validate")
CHANGE_RE = re.compile(rf"{re.escape(TEST_BACKEND)}/api/v1/changes/[^/]+/run")

HEALTH_BODY = {"status": "ok", "version": "0.4.2", "env": "dev"}

REPORT_URL = f"{TEST_BACKEND}/api/v1/reports/overview"

# /reports/overview 示例 Envelope（code + data，data 三块：changes/devices/meta）
OVERVIEW_JSON = {
    "code": 0,
    "data": {
        "changes": {"total": 12, "approved": 8, "deployed": 6, "rolled_back": 1},
        "devices": {"total": 5, "by_vendor": {"huawei": 2, "cisco": 2, "h3c": 1},
                    "source": "nautobot_mock"},
        "meta": {"data_sources": {"nautobot": "mock"}, "generated_at": "2026-10-25T08:00:00Z"},
    },
}


def _session_json(sid: str = "sess-1", intent: str = "config", scenario: str = "bgp") -> dict:
    return {"data": {
        "session_id": sid,
        "intent": intent,
        "scenario": scenario,
        "primary_agent": "config_engineer",
        "requires_approval": True,
    }}


def _config_json() -> dict:
    return {"data": {"config_diff": "router bgp 65001", "lint_passed": True, "rollback": "no router bgp"}}


# ===== 命令面与版本 =====


def test_cli_exposes_at_least_five_subcommands(runner):
    r = runner.invoke(main.app, ["--help"])
    assert r.exit_code == 0
    subcommands = ["login", "status", "health", "version", "ask", "gen", "simulate", "report"]
    shown = [c for c in subcommands if c in r.output]
    assert len(shown) >= 5


def test_version_command_matches_package_version(runner):
    r = runner.invoke(main.app, ["version"])
    assert r.exit_code == 0
    assert f"NetSage v{__version__}" in r.output


# ===== login =====


def test_login_writes_token_config(runner, tmp_path):
    cfg = tmp_path / "config.yaml"
    with respx.mock:
        respx.post(f"{TEST_BACKEND}/api/v1/auth/dev-token").mock(
            return_value=httpx.Response(200, json={"token": "dev-abc"})
        )
        r = runner.invoke(main.app, ["login", "--role", "engineer"])
    assert r.exit_code == 0
    assert cfg.exists()
    assert "dev-abc" in cfg.read_text(encoding="utf-8")


def test_login_rejects_unknown_role(runner):
    r = runner.invoke(main.app, ["login", "--role", "root"])
    assert r.exit_code == 1
    assert "非法角色" in r.output


def test_login_backend_error_exits_1(runner):
    with respx.mock:
        respx.post(f"{TEST_BACKEND}/api/v1/auth/dev-token").mock(
            side_effect=httpx.ConnectError("down")
        )
        r = runner.invoke(main.app, ["login", "--role", "viewer"])
    assert r.exit_code == 1


# ===== status / health =====


def test_status_shows_health(runner):
    with respx.mock:
        respx.get(HEALTH_URL).mock(return_value=httpx.Response(200, json=HEALTH_BODY))
        r = runner.invoke(main.app, ["status"])
    assert r.exit_code == 0
    assert "ok" in r.output and "0.4.2" in r.output


def test_status_accepts_url_flag(runner):
    with respx.mock:
        respx.get(HEALTH_URL).mock(return_value=httpx.Response(200, json=HEALTH_BODY))
        r = runner.invoke(main.app, ["status", "--url", TEST_BACKEND])
    assert r.exit_code == 0
    assert "ok" in r.output


def test_status_unreachable_exits_1(runner):
    with respx.mock:
        respx.get(HEALTH_URL).mock(side_effect=httpx.ConnectError("down"))
        r = runner.invoke(main.app, ["status"])
    assert r.exit_code == 1
    assert "不可达" in r.output


def test_health_success(runner):
    with respx.mock:
        respx.get(HEALTH_URL).mock(return_value=httpx.Response(200, json=HEALTH_BODY))
        r = runner.invoke(main.app, ["health"])
    assert r.exit_code == 0
    assert "NetSage 后端" in r.output


def test_health_unreachable_exits_1(runner):
    with respx.mock:
        respx.get(HEALTH_URL).mock(side_effect=httpx.ConnectError("down"))
        r = runner.invoke(main.app, ["health"])
    assert r.exit_code == 1


# ===== ask =====


def test_ask_config_intent_renders_markdown_report(runner):
    with respx.mock:
        respx.post(SESSION_URL).mock(return_value=httpx.Response(200, json=_session_json()))
        respx.post(SESSION_RE).mock(return_value=httpx.Response(200, json=_config_json()))
        r = runner.invoke(main.app, ["ask", "生成 BGP peering 配置"])
    assert r.exit_code == 0
    assert "NetSage 智能分析" in r.output
    assert "配置 diff" in r.output
    assert "router bgp 65001" in r.output


def test_ask_non_config_shows_summary(runner):
    with respx.mock:
        respx.post(SESSION_URL).mock(
            return_value=httpx.Response(200, json=_session_json(intent="troubleshoot", scenario="bgp"))
        )
        r = runner.invoke(main.app, ["ask", "BGP 邻居抖动"])
    assert r.exit_code == 0
    assert "troubleshoot" in r.output
    assert "配置 diff" not in r.output


def test_ask_config_falls_back_when_backend_down(runner):
    with respx.mock:
        respx.post(SESSION_URL).mock(return_value=httpx.Response(200, json=_session_json()))
        respx.post(SESSION_RE).mock(side_effect=httpx.ConnectError("down"))
        r = runner.invoke(main.app, ["ask", "生成配置"])
    assert r.exit_code == 0
    assert "仅返回意图分类" in r.output


# ===== gen =====


def test_gen_outputs_diff_lint_rollback(runner):
    with respx.mock:
        respx.post(SESSION_URL).mock(return_value=httpx.Response(200, json=_session_json()))
        respx.post(SESSION_RE).mock(return_value=httpx.Response(200, json=_config_json()))
        r = runner.invoke(main.app, ["gen", "BGP peering AS 65001"])
    assert r.exit_code == 0
    assert "配置 diff" in r.output
    assert "lint: pass" in r.output
    assert "回滚配置" in r.output


# ===== simulate =====


def test_simulate_with_change_id_calls_gates(runner):
    gates = {"data": {"steps": [{"gate": "snapshot", "passed": True},
                                {"gate": "simulation", "passed": True}], "status": "approval"}}
    with respx.mock:
        respx.post(CHANGE_RE).mock(return_value=httpx.Response(200, json=gates))
        r = runner.invoke(main.app, ["simulate", "bgp-2node", "--change-id", "CHG-001"])
    assert r.exit_code == 0
    assert "三道闸结果" in r.output
    assert "CHG-001" in r.output
    assert "approval" in r.output


def test_simulate_without_change_id_prints_note(runner):
    r = runner.invoke(main.app, ["simulate"])
    assert r.exit_code == 0
    assert "仿真拓扑" in r.output


def test_simulate_change_failure_exits_1(runner):
    with respx.mock:
        respx.post(CHANGE_RE).mock(side_effect=httpx.ConnectError("down"))
        r = runner.invoke(main.app, ["simulate", "topo", "--change-id", "CHG-9"])
    assert r.exit_code == 1
    assert "变更执行失败" in r.output


# ===== report =====


def test_report_renders_backend_overview(runner):
    with respx.mock:
        respx.get(REPORT_URL).mock(return_value=httpx.Response(200, json=OVERVIEW_JSON))
        r = runner.invoke(main.app, ["report"])
    assert r.exit_code == 0
    assert "NetSage 运营总览" in r.output
    # 渲染的是后端真实数据，不是本地编造
    assert "12" in r.output                      # changes.total
    assert "huawei=2" in r.output                # devices.by_vendor
    assert "nautobot=mock" in r.output           # meta.data_sources
    assert "2026-10-25T08:00:00Z" in r.output    # meta.generated_at
    assert f"v{__version__}" in r.output


def test_report_tolerates_missing_fields(runner):
    # data 为空 dict（后端字段缺失/降级）时渲染 '-' 而不是崩溃
    with respx.mock:
        respx.get(REPORT_URL).mock(return_value=httpx.Response(200, json={"code": 0, "data": {}}))
        r = runner.invoke(main.app, ["report"])
    assert r.exit_code == 0
    assert "NetSage 运营总览" in r.output
    assert "-" in r.output


def test_report_backend_unreachable_exits_1(runner):
    with respx.mock:
        respx.get(REPORT_URL).mock(side_effect=httpx.ConnectError("down"))
        r = runner.invoke(main.app, ["report"])
    assert r.exit_code == 1
    assert "获取报表数据失败" in r.output
    # 不可达时只报错，不再输出编造的校验结论
    assert "Batfish" not in r.output


# ===== NSCClient 路径与 payload =====


def test_client_health_parses():
    from nsc.client import NSCClient

    with respx.mock:
        respx.get(HEALTH_URL).mock(return_value=httpx.Response(200, json=HEALTH_BODY))
        assert NSCClient(backend=TEST_BACKEND).health()["status"] == "ok"


def test_client_create_session_sends_payload():
    from nsc.client import NSCClient

    with respx.mock:
        route = respx.post(SESSION_URL).mock(
            return_value=httpx.Response(200, json=_session_json())
        )
        NSCClient(backend=TEST_BACKEND).create_session("hello", vendor="cisco")
        assert route.calls.last.request.content
        payload = json.loads(route.calls.last.request.content.decode())
        assert payload == {"query": "hello", "vendor": "cisco"}


def test_client_run_config_path():
    from nsc.client import NSCClient

    with respx.mock:
        route = respx.post(SESSION_RE).mock(return_value=httpx.Response(200, json=_config_json()))
        NSCClient(backend=TEST_BACKEND).run_config("s1", "q")
        assert "sessions/s1/config" in route.calls.last.request.url.path


def test_client_run_change_path():
    from nsc.client import NSCClient

    with respx.mock:
        route = respx.post(CHANGE_RE).mock(return_value=httpx.Response(200, json={"data": {}}))
        NSCClient(backend=TEST_BACKEND).run_change("CHG-7")
        assert "changes/CHG-7/run" in route.calls.last.request.url.path


def test_client_run_validate_path():
    from nsc.client import NSCClient

    with respx.mock:
        route = respx.post(VALIDATE_RE).mock(return_value=httpx.Response(200, json={"data": {}}))
        NSCClient(backend=TEST_BACKEND).run_validate("s2")
        assert "sessions/s2/validate" in route.calls.last.request.url.path


def test_client_report_overview_path():
    from nsc.client import NSCClient

    with respx.mock:
        route = respx.get(REPORT_URL).mock(return_value=httpx.Response(200, json=OVERVIEW_JSON))
        data = NSCClient(backend=TEST_BACKEND).report_overview()
        assert "reports/overview" in route.calls.last.request.url.path
        assert data["changes"]["total"] == 12
        assert data["devices"]["source"] == "nautobot_mock"