"""v0.5.0 审查修复回归测试。

覆盖：
- 工具装配（mock/mcp 双模式 + HttpToolRegistry 路由与错误）
- 审计链（内存链 tamper 检测 + fail-closed 路由行为）
- 变更存储（内存 CRUD/快照/统计 + GET /changes）
- auto_approve 服务端强制（生产强制 False）
- SSE 流（ticket 单次使用 + 事件流）
- 脱敏加固（内容自动分级 + secret 5 哈希整行 + .lan 主机名）
- 模板参数消毒（换行注入拒绝）
- 基线扫描否定语义（no X 行不再误判）
"""
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app.core.security import CurrentUser, Role, encode_token
from app.main import app

client = TestClient(app)


def _auth(role: Role = Role.ADMIN) -> dict[str, str]:
    return {"Authorization": f"Bearer {encode_token(CurrentUser(id=1, name='t', role=role))}"}


# ===== 工具装配 =====


def test_build_registry_mock_mode_installs_demo_stubs():
    from app.core.config import Settings
    from app.tools.wiring import MOCK_MODE, build_registry

    s = Settings(database_url="postgresql+asyncpg://x:y@localhost:5432/z", env="dev")
    registry, mode = build_registry(s)
    assert mode == MOCK_MODE


def test_build_registry_mcp_mode_returns_http_registry():
    from app.core.config import Settings
    from app.tools.http_registry import HttpToolRegistry
    from app.tools.wiring import MCP_MODE, build_registry

    s = Settings(
        database_url="postgresql+asyncpg://x:y@localhost:5432/z",
        env="dev",
        tools_backend="mcp",
        mcp_napalm_url="http://localhost:9003",
    )
    registry, mode = build_registry(s)
    assert mode == MCP_MODE
    assert isinstance(registry, HttpToolRegistry)


@pytest.mark.asyncio
async def test_http_registry_routes_by_server_prefix(monkeypatch):
    from app.tools import http_registry

    calls: list[tuple[str, str, dict]] = []

    class _FakeResult:
        def __init__(self, data: dict) -> None:
            self.data = data

    class _FakeClient:
        def __init__(self, url: str) -> None:
            self.url = url

        async def __aenter__(self) -> _FakeClient:
            return self

        async def __aexit__(self, *args: object) -> bool:
            return False

        async def call_tool(self, name: str, args: dict) -> _FakeResult:
            calls.append((self.url, name, args))
            return _FakeResult({"status": "deployed"})

    monkeypatch.setattr("fastmcp.Client", _FakeClient)
    reg = http_registry.HttpToolRegistry({"containerlab": "http://cl:9001/"})
    result = await reg.invoke("containerlab.deploy_topology", topo_yaml="name: x")
    assert result == {"status": "deployed"}
    assert calls == [("http://cl:9001/mcp", "deploy_topology", {"topo_yaml": "name: x"})]


@pytest.mark.asyncio
async def test_http_registry_unknown_server_raises():
    from app.tools.http_registry import HttpToolRegistry, ToolCallError

    reg = HttpToolRegistry({"napalm": "http://n:9003"})
    with pytest.raises(ToolCallError, match="未配置"):
        await reg.invoke("containerlab.deploy_topology")


# ===== 审计链 =====


@pytest.mark.asyncio
async def test_memory_audit_chain_verify_and_tamper_detect():
    from app.audit.service import MemoryAuditSink

    sink = MemoryAuditSink()
    for i in range(3):
        ok = await sink.append(user_id=1, action="change.create", resource_type="change_request",
                               resource_id=str(i))
        assert ok
    assert await sink.verify() is True
    # 篡改记录内容 → 重算哈希不匹配（v0.5.0：verify 现在重算 sha256）
    sink._entries[1]["fields"]["action"] = "change.approve"
    assert await sink.verify() is False


@pytest.mark.asyncio
async def test_audit_payload_includes_ts():
    from app.audit.service import MemoryAuditSink

    sink = MemoryAuditSink()
    await sink.append(user_id=1, action="change.create", resource_type="change_request")
    assert "ts" in sink._entries[0]["fields"]  # ts 进哈希：改时间戳会被发现


def test_change_create_fails_closed_when_audit_down(monkeypatch):
    """审计写不进 → 操作 503 中止（fail-closed）。"""
    import app.api.v1.changes as changes_api

    class _BrokenSink:
        @property
        def mode(self) -> str:
            return "broken"

        async def append(self, **kw) -> bool:
            raise RuntimeError("audit sink down")

    monkeypatch.setattr(changes_api, "get_audit_sink", lambda: _BrokenSink())
    r = client.post(
        "/api/v1/changes",
        json={"title": "t", "nim": {}, "devices": [], "configs": {}, "assertions": []},
        headers=_auth(Role.ENGINEER),
    )
    assert r.status_code == 503


# ===== 变更存储 + GET /changes =====


@pytest.mark.asyncio
async def test_memory_change_store_roundtrip():
    from app.services.change_store import MemoryChangeStore

    store = MemoryChangeStore()
    rec = await store.create(title="t", nim={"a": 1}, devices=[], configs={}, assertions=[],
                             impact={"risk_level": "high"}, created_by=1)
    assert rec.status == "draft"
    await store.update_status(rec.id, "approval", pipeline_result={"steps": []})
    got = await store.get(rec.id)
    assert got is not None and got.status == "approval" and got.pipeline_result == {"steps": []}
    await store.save_snapshot(rec.id, 7, "snapshots/device-7/abc", "h" * 64, "config-body")
    assert await store.load_snapshot("snapshots/device-7/abc") == "config-body"
    stats = await store.stats()
    assert stats["total"] == 1 and stats["by_status"]["approval"] == 1


def test_list_changes_route_returns_real_store():
    before = client.get("/api/v1/changes", headers=_auth(Role.AUDITOR))
    assert before.status_code == 200
    base = before.json()["data"]["count"]
    created_ids: list[int] = []
    for i in range(2):
        r = client.post(
            "/api/v1/changes",
            json={"title": f"list-{i}", "nim": {}, "devices": [], "configs": {}, "assertions": []},
            headers=_auth(Role.ENGINEER),
        )
        assert r.status_code == 200
        created_ids.append(r.json()["data"]["id"])
    after = client.get("/api/v1/changes", headers=_auth(Role.AUDITOR)).json()["data"]
    assert after["count"] >= base + 2  # 并发测试共享 store，只断言增量下限
    assert after["count"] >= len(after["items"])  # count=总数，items 截断到 limit=50
    assert after["storage"] in ("memory", "db")
    assert {"id", "title", "status"} <= set(after["items"][0])
    assert set(created_ids) <= {item["id"] for item in after["items"]}  # 新建的都在列表里


# ===== auto_approve 服务端强制（审查 P0）=====


def test_auto_approve_forced_off_in_production(monkeypatch):
    import app.api.v1.agents as agents_api

    class _ProdSettings:
        is_dev = False

    monkeypatch.setattr(agents_api, "get_settings", lambda: _ProdSettings())
    r = client.post(
        "/api/v1/agents/closed-loop",
        json={"symptom": "BGP 邻居抖动", "vendor": "huawei_vrp", "auto_approve": True},
        headers=_auth(),
    )
    assert r.status_code == 200
    d = r.json()["data"]
    assert d["approved"] is False  # 生产强制人工审批


# ===== agents deploy 审批校验 =====


def test_deploy_without_change_id_rejected_in_production(monkeypatch):
    import app.api.v1.agents as agents_api

    class _ProdSettings:
        is_dev = False

    monkeypatch.setattr(agents_api, "get_settings", lambda: _ProdSettings())
    r = client.post(
        "/api/v1/agents/sessions/s1/deploy",
        json={"devices": [], "configs": {}},
        headers=_auth(),
    )
    assert r.status_code == 409


def test_deploy_with_unapproved_change_id_rejected():
    create = client.post(
        "/api/v1/changes",
        json={"title": "d", "nim": {}, "devices": [], "configs": {}, "assertions": []},
        headers=_auth(Role.ENGINEER),
    )
    cid = create.json()["data"]["id"]  # draft 状态
    r = client.post(
        "/api/v1/agents/sessions/s1/deploy",
        json={"devices": [], "configs": {}, "change_id": cid},
        headers=_auth(),
    )
    assert r.status_code == 409


# ===== SSE 流（ticket 单次使用）=====


def _make_session() -> dict:
    r = client.post(
        "/api/v1/agents/sessions",
        json={"query": "BGP 邻居抖动怎么排查"},
        headers=_auth(),
    )
    assert r.status_code == 200
    return r.json()["data"]


def test_sse_stream_requires_ticket():
    sess = _make_session()
    r = client.get(f"/api/v1/agents/sessions/{sess['session_id']}/stream", headers=_auth())
    assert r.status_code == 401


def test_sse_stream_events_and_ticket_single_use():
    sess = _make_session()
    url = f"/api/v1/agents/sessions/{sess['session_id']}/stream?ticket={sess['stream_ticket']}"
    r1 = client.get(url, headers=_auth())
    assert r1.status_code == 200
    events = [json.loads(ln.removeprefix("data: ")) for ln in r1.text.splitlines()
              if ln.startswith("data: ")]
    kinds = [e["event"] for e in events]
    assert kinds[0] == "start" and kinds[-1] == "done"
    # ticket 单次使用：第二次 401
    r2 = client.get(url, headers=_auth())
    assert r2.status_code == 401


def test_sse_unknown_session_404():
    r = client.get("/api/v1/agents/sessions/nope/stream?ticket=x", headers=_auth())
    assert r.status_code == 404


# ===== 脱敏加固 =====


def test_detect_running_config_escalates_to_blackbox():
    """声明白盒但内容是 running-config → 黑盒阻断（不再信任 caller 字符串）。"""
    from app.redact.interceptor import RedactingInterceptor
    from app.redact.layer3_router import BlackboxBlockError
    from app.redact.mapping import MappingTable

    config_text = (
        "! \nversion 17\nhostname CORE-01\ninterface GE0/0\n ip address 10.1.2.3 255.255.255.0\n"
    )
    itc = RedactingInterceptor()
    with pytest.raises(BlackboxBlockError):
        itc.before_llm_call(
            [{"role": "user", "content": f"分析这段配置：\n{config_text}"}],
            "general_qa",  # 谎报白盒
            MappingTable(),
        )


def test_detect_config_fragment_escalates_to_grey():
    """配置片段（非完整 running-config）→ 灰盒强制脱敏后放行。"""
    from app.redact.interceptor import RedactingInterceptor
    from app.redact.mapping import MappingTable

    fragment = "interface GE0/0\nrouter bgp 65001\nsnmp-server community public\n"
    itc = RedactingInterceptor()
    out = itc.before_llm_call(
        [{"role": "user", "content": fragment}], "general_qa", MappingTable()
    )
    assert "public" not in out[0]["content"]
    assert "[REDACTED]" in out[0]["content"]


def test_benign_content_not_escalated():
    from app.redact.detector import detect_content_type

    assert detect_content_type([{"role": "user", "content": "什么是 BGP AS-Path prepend？"}]) is None


def test_secret_hash_fully_redacted():
    """`secret 5 $1$salt$hash`：真实哈希必须被整行清除（v0.5.0 正则加固）。"""
    from app.redact.layer1_dict import Layer1Redactor
    from app.redact.mapping import MappingTable

    text = "username admin secret 5 $1$salt$hash$."
    out = Layer1Redactor().redact(text, MappingTable())
    assert "$1$" not in out
    assert "secret [REDACTED]" in out


def test_lan_hostname_redacted():
    from app.redact.layer1_dict import Layer1Redactor
    from app.redact.mapping import MappingTable

    out = Layer1Redactor().redact("ping core-sw.lan", MappingTable())
    assert "core-sw.lan" not in out


def test_invalid_ipv4_octets_not_matched():
    from app.redact.layer1_dict import Layer1Redactor
    from app.redact.mapping import MappingTable

    out = Layer1Redactor().redact("错误示例 999.999.999.999", MappingTable())
    assert "999.999.999.999" in out  # 非法 IP 不产生占位符噪声


# ===== 模板参数消毒 =====


def test_template_param_newline_rejected():
    from app.services.template_loader import TemplateError, validate_param_values

    with pytest.raises(TemplateError, match="换行"):
        validate_param_values("t", {"asn": "65001\nrouter bgp 65002"})
    # 正常值放行
    validate_param_values("t", {"asn": "65001", "peers": ["1.1.1.1", "2.2.2.2"]})


# ===== 基线扫描否定语义 =====


@pytest.mark.asyncio
async def test_baseline_absent_respects_no_prefix():
    """`no ip http server` 是已加固配置，不得因子串误判违规（审查 P2）。"""
    from app.services.baseline_scanner import BaselineScanner

    scanner = BaselineScanner()
    hardened = "no ip http server\nservice password-encryption\n"
    assert scanner._match(hardened, "absent", "ip http server") is True  # absent 通过 = 合规
    enabled = "ip http server\n"
    assert scanner._match(enabled, "absent", "ip http server") is False


def test_baseline_absent_alternation():
    from app.services.baseline_scanner import BaselineScanner

    scanner = BaselineScanner()
    config = "undo ftp server enable\n"
    assert scanner._match(config, "absent", "ftp server enable|tftp server enable") is True
    config2 = "tftp server enable\n"
    assert scanner._match(config2, "absent", "ftp server enable|tftp server enable") is False


# ===== ACL 分析去示例化（v0.5.1）=====


@pytest.mark.asyncio
async def test_acl_analyzer_no_hardcoded_demo_data():
    """ACL 分析不再返回编造的 shadowed/unused 示例数据（评审 P1）。"""
    from app.services.acl_analyzer import ACLAnalyzer

    class _FailingTools:
        async def invoke(self, name: str, **kw):
            raise RuntimeError("batfish offline")

    import app.agents.registry as reg

    original = reg.get_tools
    reg.get_tools = lambda: _FailingTools()
    try:
        report = await ACLAnalyzer().analyze("snap", "cisco_iosxe")
    finally:
        reg.get_tools = original
    assert report.reachability == [] and report.unused == []
    assert report.error is not None and "不可用" in report.error  # 如实报 unavailable


@pytest.mark.asyncio
async def test_acl_analyzer_real_rows_extraction():
    """TableAnswerElement 正确解包：rows 进结果，空表不误报。"""
    from app.services.acl_analyzer import ACLAnalyzer, _extract_rows

    el = {"answerElements": [{"class": "TableAnswerElement", "rows": [
        {"Source": "10.1.1.10", "Destination": "10.2.2.20", "Action": "PERMIT"},
    ], "summary": {"numResults": 1}}]}
    rows = _extract_rows(el)
    assert len(rows) == 1 and rows[0]["Action"] == "PERMIT"
    empty = _extract_rows({"answerElements": [{"rows": [], "summary": {"numResults": 0}}]})
    assert empty == []

    class _FakeTools:
        def __init__(self, payloads: dict) -> None:
            self.payloads = payloads

        async def invoke(self, name: str, **kw):
            return self.payloads[name]

    import app.agents.registry as reg

    original = reg.get_tools
    reg.get_tools = lambda: _FakeTools({
        "batfish.search_filters": el,
        "batfish.interface_properties": {"answerElements": [{"rows": [
            {"Interface": "Eth1", "Incoming_Filter": "ACL_IN"},
        ]}]},
        "batfish.filter_tables": {"answerElements": [{"rows": [
            {"Name": "ACL_IN"}, {"Name": "ACL_LEGACY"},
        ]}]},
    })
    try:
        report = await ACLAnalyzer().analyze("snap", "cisco_iosxe")
    finally:
        reg.get_tools = original
    assert report.error is None
    assert report.reachability and report.reachability[0]["action"] == "permit"
    assert report.unused == [{"acl": "ACL_LEGACY", "reason": "未在任何接口引用"}]


# ===== v0.6：closed_loop 验证真实化 / LLM 显式降级 / 指标事件 =====


@pytest.mark.asyncio
async def test_closed_loop_verify_real_batfish():
    """闭环验证走真实 batfish lint：有 parse warning 即 fail。"""
    from app.agents.closed_loop import ClosedLoopOrchestrator

    class _LintTools:
        def __init__(self, passed: bool) -> None:
            self.passed = passed

        async def invoke(self, name: str, **kw):
            assert name == "batfish.lint_config"
            return {"passed": self.passed, "warnings": []}

    orch = ClosedLoopOrchestrator(tools=_LintTools(passed=False))
    assert await orch._verify({"config": "router bgp 65001\n nonsense line"}) is False
    assert orch.verify_mode == "batfish_lint"

    orch2 = ClosedLoopOrchestrator(tools=_LintTools(passed=True))
    assert await orch2._verify({"config": "router bgp 65001"}) is True
    assert orch2.verify_mode == "batfish_lint"


@pytest.mark.asyncio
async def test_closed_loop_verify_fallback_labeled():
    """batfish 不可达 → 降级为配置非空 + verify_mode 显式标注（不伪装）。"""
    from app.agents.closed_loop import ClosedLoopOrchestrator

    class _BrokenTools:
        async def invoke(self, name: str, **kw):
            raise RuntimeError("batfish offline")

    orch = ClosedLoopOrchestrator(tools=_BrokenTools())
    assert await orch._verify({"config": "router bgp 65001"}) is True
    assert orch.verify_mode == "fallback_config_nonempty"
    # 空配置恒 fail（连降级都不给过）
    assert await orch._verify({"config": ""}) is False


@pytest.mark.asyncio
async def test_config_lint_placeholder_forced_fail():
    """LLM 降级占位配置 → lint 强制 fail（不可下发的显式暴露）。"""
    from app.agents import handlers as h
    from app.tools.registry import MockToolRegistry

    tools = MockToolRegistry()
    state = {"config_diff": "router bgp 65001", "render_source": "placeholder"}
    out = await h.config_lint(state, tools)
    assert out["lint_passed"] is False
    assert "占位" in out["lint_note"]

    # LLM 正常产物不受影响
    state2 = {"config_diff": "router bgp 65001", "render_source": "llm_template"}
    out2 = await h.config_lint(state2, tools)
    assert out2["lint_passed"] is True  # mock lint 默认 passed


def test_render_fallback_explicit_fields():
    """LLM 失败降级必须写入 render_fallback（含原因），不只是暗示字段。"""
    import asyncio

    from app.agents import handlers as h

    class _BrokenRenderer:
        async def generate(self, **kw):
            raise RuntimeError("no api key")

    class _T:
        async def invoke(self, *a, **k):
            return {}

    original = h._get_renderer
    h._get_renderer = lambda: _BrokenRenderer()
    try:
        out = asyncio.run(
            h.config_render({"query": "bgp", "vendor": "huawei", "scenario": "bgp"}, _T())
        )
    finally:
        h._get_renderer = original
    assert out["render_source"] == "placeholder"
    assert "no api key" in out["render_fallback"]["llm_error"]
    assert "不可直接下发" in out["render_fallback"]["note"]


@pytest.mark.asyncio
async def test_metric_sink_memory_record_and_aggregate():
    from app.services.metrics import (
        KIND_CLOSED_LOOP,
        KIND_COMPLIANCE,
        MemoryMetricSink,
    )

    sink = MemoryMetricSink()
    await sink.record(KIND_COMPLIANCE, 85.0, {"vendor": "huawei_vrp"})
    await sink.record(KIND_COMPLIANCE, 95.0, {"vendor": "cisco_iosxe"})
    await sink.record(KIND_CLOSED_LOOP, 0.8333, {"symptom": "bgp"})
    agg = await sink.aggregate(KIND_COMPLIANCE)
    assert agg["total"] == 2 and agg["avg_value"] == 90.0 and agg["latest_at"]
    empty = await sink.aggregate("nonexistent")
    assert empty["total"] == 0 and empty["avg_value"] is None
