"""Agent 编排层测试（v2.0 五章 + 三十章）。

覆盖：
- 意图分类 6×7 矩阵
- SequentialBackend 拓扑排序 + 执行 + 中断/resume
- AgentRunner 装配
- ConfigEngineer/Validator handlers
- API 端点
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.agents.classifier import (
    INTENT_AGENT_MAP,
    Intent,
    Scenario,
    classify,
)
from app.main import app
from app.runtime.base import AgentDefinition, Transition
from app.runtime.sequential_backend import SequentialBackend

client = TestClient(app)


# ===== 意图分类 6×7 =====


@pytest.mark.parametrize(
    "query,expected_intent",
    [
        ("设计一套 BGP 网络", Intent.DESIGN),
        ("生成 OSPF 配置", Intent.CONFIG),
        ("BGP 邻居为什么抖动", Intent.TROUBLESHOOT),
        ("审计 ACL 合规", Intent.AUDIT),
        ("RoCE 延迟优化", Intent.PERFORMANCE),
        ("链路带宽扩容容量", Intent.CAPACITY),
    ],
)
def test_classify_intent(query, expected_intent):
    result = classify(query)
    assert result.intent == expected_intent


@pytest.mark.parametrize(
    "query,expected_scenario",
    [
        ("OSPF 邻居问题", Scenario.OSPF),
        ("BGP peer 不通", Scenario.BGP),
        ("VXLAN VNI 配置", Scenario.VXLAN),
        ("IPSec VPN 配置", Scenario.VPN),
        ("无线漫游", Scenario.WIRELESS),
        ("RoCE PFC 调优", Scenario.ROCE),
        ("ACL 安全审计", Scenario.SECURITY),
    ],
)
def test_classify_scenario(query, expected_scenario):
    assert classify(query).scenario == expected_scenario


def test_config_intent_requires_approval():
    """所有 config 操作强制人审（v2.0 十章三道闸）。"""
    result = classify("生成 BGP 配置")
    assert result.requires_human_approval is True


def test_troubleshoot_bgp_high_priority():
    """BGP 排障高优先级。"""
    result = classify("BGP 邻居抖动排障")
    assert result.priority == "high"


def test_intent_agent_map_covers_all_intents():
    """6 类 intent 都有主责 Agent。"""
    for intent in Intent:
        assert intent in INTENT_AGENT_MAP


# ===== SequentialBackend =====


@pytest.mark.asyncio
async def test_sequential_graph_linear_execution():
    """线性 DAG 顺序执行 3 节点。"""
    defn = AgentDefinition(
        name="test",
        role="t",
        system_prompt="t",
        tools=[],
        state_schema={},
        transitions=[Transition("a", "b"), Transition("b", "c"), Transition("c", "END")],
    )

    calls: list[str] = []

    async def node_a(state):
        calls.append("a")
        return {**state, "a": True}

    async def node_b(state):
        calls.append("b")
        return {**state, "b": True}

    async def node_c(state):
        calls.append("c")
        return {**state, "c": True}

    graph = SequentialBackend().compile(defn, {"a": node_a, "b": node_b, "c": node_c})
    result = await graph.invoke({}, {"configurable": {"thread_id": "s1"}})
    assert calls == ["a", "b", "c"]
    assert result == {"a": True, "b": True, "c": True}


@pytest.mark.asyncio
async def test_sequential_graph_interrupt():
    """interrupt_point 暂停执行（HITL 强制点，v2.0 五章 5.2）。"""
    defn = AgentDefinition(
        name="test",
        role="t",
        system_prompt="t",
        tools=[],
        state_schema={},
        transitions=[Transition("a", "b"), Transition("b", "END")],
        interrupt_points=["b"],
    )

    async def node_a(state):
        return {**state, "a": True}

    async def node_b(state):
        return {**state, "b": True}

    graph = SequentialBackend().compile(defn, {"a": node_a, "b": node_b})
    result = await graph.invoke({}, {"configurable": {"thread_id": "s2"}})
    assert result["__interrupted_at__"] == "b"
    assert "b" not in result  # b 未执行

    # resume 后执行 b
    result = await graph.resume({"configurable": {"thread_id": "s2"}})
    assert result.get("b") is True


@pytest.mark.asyncio
async def test_sequential_graph_stream():
    """stream 模式每步 yield 事件。"""
    defn = AgentDefinition(
        name="test",
        role="t",
        system_prompt="t",
        tools=[],
        state_schema={},
        transitions=[Transition("a", "b"), Transition("b", "END")],
    )

    async def node_a(s):
        return {**s, "a": True}

    async def node_b(s):
        return {**s, "b": True}

    graph = SequentialBackend().compile(defn, {"a": node_a, "b": node_b})
    events = []
    async for ev in graph.stream({}, {"configurable": {"thread_id": "s3"}}):
        events.append(ev)
    assert len(events) == 2
    assert events[0]["node"] == "a"
    assert events[1]["node"] == "b"


# ===== AgentRunner 装配 =====


@pytest.fixture(autouse=True)
def _mock_renderer():
    """隔离真实 LLM：给 handlers 注入 Mock 渲染器（真实 LLM 链路已在 test_config_renderer 覆盖）。"""
    from app.agents import handlers as h
    from app.services.config_renderer import ConfigRenderer
    from tests.unit.test_config_renderer import MockLLM

    llm = MockLLM([
        '{"local_asn": 65001, "router_id": "1.1.1.1",'
        ' "peers": [{"address": "10.1.1.2", "remote_asn": 65002, "description": "demo"}]}'
    ])
    h.set_renderer(ConfigRenderer(llm))
    yield
    h.set_renderer(None)


@pytest.mark.asyncio
async def test_runner_registers_and_runs():
    """runner 注册 Agent 后能执行。"""
    from app.agents.registry import build_runner

    runner = build_runner()
    assert "planner" in runner._compiled
    assert "config_engineer" in runner._compiled
    assert "validator" in runner._compiled

    result = await runner.run("planner", {"query": "生成 BGP 配置"}, session_id="t1")
    assert result["intent"] == "config"
    assert result["scenario"] == "bgp"
    assert result["primary_agent"] == "config_engineer"
    assert result["requires_approval"] is True


@pytest.mark.asyncio
async def test_config_engineer_generates_config():
    """ConfigEngineer 生成配置 + lint（v2.0 八章 8.2）。"""
    from app.agents.registry import build_runner

    runner = build_runner()
    result = await runner.run(
        "config_engineer",
        {"query": "BGP peering", "vendor": "huawei", "scenario": "bgp"},
        session_id="t2",
    )
    assert "config_diff" in result
    assert "bgp 65001" in result["config_diff"]  # 华为 VRP 模板格式
    assert result["lint_passed"] is True  # MockToolRegistry 返回 passed


# ===== API 端点 =====

from app.core.security import CurrentUser, Role, encode_token


def _auth() -> dict[str, str]:
    token = encode_token(CurrentUser(id=1, name="test", role=Role.ENGINEER))
    return {"Authorization": f"Bearer {token}"}


def test_api_create_agent_session():
    """POST /agents/sessions 分类并路由（v2.0 十二章 UX）。"""
    response = client.post(
        "/api/v1/agents/sessions",
        json={"query": "BGP 邻居为什么抖动", "vendor": "huawei"},
        headers=_auth(),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    data = body["data"]
    assert data["intent"] == "troubleshoot"
    assert data["scenario"] == "bgp"
    assert data["primary_agent"] == "troubleshooter"
    assert data["session_id"]


def test_api_session_requires_auth():
    """无 token 401（审查 #8 修复：agents API 加鉴权）。"""
    response = client.post(
        "/api/v1/agents/sessions",
        json={"query": "BGP"},
    )
    assert response.status_code == 401


def test_api_run_config_engineer():
    response = client.post(
        "/api/v1/agents/sessions/sess1/config",
        json={"query": "BGP peering", "vendor": "huawei"},
        headers=_auth(),
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert "config_diff" in data
    assert "bgp 65001" in data["config_diff"]  # 华为 VRP 模板格式
