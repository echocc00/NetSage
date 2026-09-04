"""Agent 节点处理函数（v2.0 五章 8.1-8.3）。

每个 Agent 的节点逻辑：retrieve_context → render/lint → output。
工具通过 ToolRegistry 调用，LLM 通过 LLMGateway 调用。
"""
from __future__ import annotations

from typing import Any

from app.agents.classifier import ClassifiedIntent, classify
from app.core.logging import get_logger
from app.tools.registry import ToolRegistry

logger = get_logger("agent_handlers")


# ===== Planner =====


async def planner_classify(state: dict) -> dict:
    """Planner 节点：意图分类 → 路由到子 Agent。"""
    query = state.get("query", "")
    classified: ClassifiedIntent = classify(query)
    state["intent"] = classified.intent.value
    state["scenario"] = classified.scenario.value
    state["priority"] = classified.priority
    state["primary_agent"] = classified.primary_agent
    state["requires_approval"] = classified.requires_human_approval
    logger.info(
        "planner_classified",
        intent=state["intent"],
        scenario=state["scenario"],
        agent=state["primary_agent"],
    )
    return state


async def planner_plan(state: dict) -> dict:
    """Planner 节点：构建执行计划（Phase 2 接 LLM 规划，Phase 1 规则）。"""
    intent = state["intent"]
    # Phase 1：固定计划模板
    if intent == "config":
        state["plan"] = ["config_engineer.retrieve_context", "config_engineer.render", "config_engineer.lint"]
    elif intent == "troubleshoot":
        state["plan"] = ["troubleshooter.collect", "troubleshooter.analyze"]
    elif intent == "audit":
        state["plan"] = ["security_auditor.scan", "security_auditor.report"]
    else:
        state["plan"] = ["config_engineer.retrieve_context", "config_engineer.render"]
    return state


# ===== ConfigEngineer =====

# 注入的渲染器（registry 装配；测试可注入 mock）
_renderer: Any = None


def set_renderer(r: Any) -> None:
    """注入 ConfigRenderer（测试/装配用）。"""
    global _renderer
    _renderer = r


def _get_renderer() -> Any:
    if _renderer is None:
        from app.services.config_renderer import get_config_renderer
        return get_config_renderer()
    return _renderer


async def config_retrieve_context(state: dict, tools: ToolRegistry, llm=None) -> dict:
    """检索厂商手册 + 设备 facts。

    Phase 1：设备目标从 state 传入（审查 H6 修复：不硬编码凭证）。
    """
    vendor = state.get("vendor", "huawei")
    device = state.get("device", {})  # {id, vendor, host, username, password}，Vault 注入后使用
    facts = await tools.invoke(
        "napalm.get_facts",
        vendor=vendor,
        host=device.get("host", "sim"),
        username=device.get("username", "session-user"),
        password=device.get("password", "") or "mock-injected-via-vault",
    )
    state["device_facts"] = facts
    state["context_ready"] = True
    return state


async def config_render(state: dict, tools: ToolRegistry, llm=None) -> dict:
    """渲染配置（v2.0 十章"IR 只作翻译不作裸推理"）。

    LLM 提参 → 模板渲染（ConfigRenderer）；无 LLM key 时回落占位模板（Phase 1 mock）。
    """
    intent_text = state.get("query", "")
    scenario = state.get("scenario", "bgp")
    vendor = state.get("vendor", "huawei")

    try:
        result = await _get_renderer().generate(
            query=intent_text, vendor=vendor, scenario=scenario,
            device=state.get("device"),
        )
        state["config_diff"] = result["config_diff"]
        state["rollback_config"] = result["rollback"]
        state["references"] = result["references"]
        state["render_source"] = "llm_template"
    except Exception as e:
        logger.info("render_fallback_placeholder", scenario=scenario, error=str(e)[:120])
        state["config_diff"] = _render_placeholder(scenario, intent_text)
        state["rollback_config"] = _render_rollback(scenario)
        state["render_source"] = "placeholder"
    return state


async def config_lint(state: dict, tools: ToolRegistry, llm=None) -> dict:
    """Batfish 语法 lint（安全闸 2 前置）。"""
    config = state.get("config_diff", "")
    result = await tools.invoke("batfish.lint_config", config_text=config, vendor="cisco")
    state["lint_passed"] = result.get("passed", True) if isinstance(result, dict) else True
    return state


# ===== Validator =====


async def validator_assert(state: dict, tools: ToolRegistry, llm=None) -> dict:
    """跑 Batfish 断言（reachability/routing）。"""
    assertions = state.get("assertions", [
        {"type": "reachability", "src": "leaf01", "dst": "spine01"},
        {"type": "routing", "prefix": "10.1.2.0/24"},
    ])
    results = []
    for a in assertions:
        atype = a.get("type")
        if atype == "reachability":
            r = await tools.invoke("batfish.assert_reachability", snapshot="snap", src=a["src"], dst=a["dst"])
        elif atype == "routing":
            r = await tools.invoke("batfish.assert_routing", snapshot="snap", prefix=a["prefix"])
        else:
            continue
        results.append(r)
    state["validation_passed"] = all(
        r.get("passed", False) if isinstance(r, dict) else False for r in results
    )
    state["validation_evidence"] = results
    return state


# ===== 占位模板（W6 模板库建成后替换）=====


def _render_placeholder(scenario: str, intent: str) -> str:
    """Phase 1 占位配置生成（W6 换真实 Jinja2 模板库）。"""
    templates = {
        "bgp": "router bgp 65001\n neighbor 10.1.1.2 remote-as 65002\n neighbor 10.1.1.2 activate",
        "ospf": "ospf 1\n area 0.0.0.0\n  interface GigabitEthernet0/0/0",
        "vxlan": "bridge-domain 10\n vxlan vni 10010",
    }
    return templates.get(scenario, f"! config for {scenario}")


def _render_rollback(scenario: str) -> str:
    """回滚配置占位。"""
    return f"! rollback for {scenario}"
