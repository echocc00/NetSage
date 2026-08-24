"""Agent 装配器（v2.0 七章 + 三十章）。

把 AgentDefinition + node_handlers + backend 组装成可执行的 AgentRunner。
Phase 1 用 SequentialBackend，W5 联调时换 LangGraphBackend。
"""
from __future__ import annotations

from functools import partial
from typing import Any

from app.runtime.base import AgentDefinition, AgentRunner, Transition
from app.runtime.sequential_backend import SequentialBackend

# Agent 工具集注入：handlers 需要 ToolRegistry
_tools: Any = None


def configure_tools(tools: Any) -> None:
    """注入全局 ToolRegistry（应用启动时调）。"""
    global _tools
    _tools = tools


def _tools_get() -> Any:
    if _tools is None:
        from app.tools.registry import MockToolRegistry
        return MockToolRegistry()
    return _tools


# ===== Agent 定义（W5 起 YAML 化，Phase 1 先用代码定义跑通）=====


def _planner_definition() -> AgentDefinition:
    return AgentDefinition(
        name="planner",
        role="网络规划器：意图分类 + DAG 规划",
        system_prompt="你是网络规划器，负责意图分类和子 Agent 调度。",
        tools=[],
        state_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "intent": {"type": "string"},
                "scenario": {"type": "string"},
                "primary_agent": {"type": "string"},
                "plan": {"type": "array"},
            },
        },
        transitions=[
            Transition("classify", "plan"),
            Transition("plan", "END"),
        ],
    )


def _config_engineer_definition() -> AgentDefinition:
    return AgentDefinition(
        name="config_engineer",
        role="多厂商配置工程师：模板渲染 + 语法校验",
        system_prompt="你是资深网络配置工程师。只渲染模板，不裸生成命令（IR 只作翻译不作裸推理）。",
        tools=["napalm.get_facts", "batfish.lint_config", "template.render", "rag.search"],
        state_schema={"type": "object"},
        transitions=[
            Transition("retrieve_context", "render"),
            Transition("render", "lint"),
            Transition("lint", "END"),
        ],
    )


def _validator_definition() -> AgentDefinition:
    return AgentDefinition(
        name="validator",
        role="校验器：Batfish + Containerlab 断言",
        system_prompt="你是配置校验器，跑 reachability/routing 断言。false negative = 0。",
        tools=["batfish.assert_reachability", "batfish.assert_routing", "containerlab.deploy_topology"],
        state_schema={"type": "object"},
        transitions=[
            Transition("assert", "END"),
        ],
    )


def build_runner() -> AgentRunner:
    """装配所有 Agent 到 runner。"""
    from app.agents import handlers as h

    backend = SequentialBackend()
    runner = AgentRunner(backend)
    tools = _tools_get()

    # 注入 tools 到 handlers（partial 绑定）
    runner.register(
        _planner_definition(),
        {"classify": h.planner_classify, "plan": h.planner_plan},
    )
    runner.register(
        _config_engineer_definition(),
        {
            "retrieve_context": partial(h.config_retrieve_context, tools=tools),
            "render": partial(h.config_render, tools=tools),
            "lint": partial(h.config_lint, tools=tools),
        },
    )
    runner.register(
        _validator_definition(),
        {"assert": partial(h.validator_assert, tools=tools)},
    )
    # Troubleshooter（Phase 2 P2-10）
    from app.agents.troubleshooter_handlers import (
        troubleshoot_analyze,
        troubleshoot_collect,
        troubleshoot_suggest_fixes,
    )

    runner.register(
        _troubleshooter_definition(),
        {
            "collect": partial(troubleshoot_collect, tools=tools),
            "analyze": partial(troubleshoot_analyze, tools=tools),
            "suggest_fixes": partial(troubleshoot_suggest_fixes, tools=tools),
        },
    )

    # DeployAgent（Phase 2 P2-8）
    from app.agents.deploy_handlers import (
        deploy_loop,
        deploy_pre_check,
        deploy_verify,
    )

    runner.register(
        _deploy_definition(),
        {
            "pre_check": partial(deploy_pre_check, tools=tools),
            "deploy_loop": partial(deploy_loop, tools=tools),
            "verify": partial(deploy_verify, tools=tools),
        },
    )

    # ObserverAgent（Phase 2 P2-7）
    from app.agents.observer_handlers import (
        observer_alert,
        observer_analyze,
        observer_poll,
    )

    runner.register(
        _observer_definition(),
        {
            "poll": partial(observer_poll, tools=tools),
            "analyze": partial(observer_analyze, tools=tools),
            "alert": partial(observer_alert, tools=tools),
        },
    )

    # SecurityAuditor + Compliance（Phase 3）
    from app.agents.security_handlers import (
        SECURITY_AUDITOR_DEFINITION,
        COMPLIANCE_DEFINITION,
        compliance_aggregate,
        compliance_gather,
        compliance_render,
        sec_analyze_acl,
        sec_collect_config,
        sec_report,
        sec_scan_baseline,
    )

    runner.register(
        AgentDefinition(
            name=SECURITY_AUDITOR_DEFINITION["name"],
            role=SECURITY_AUDITOR_DEFINITION["role"],
            system_prompt=SECURITY_AUDITOR_DEFINITION["system_prompt"],
            tools=SECURITY_AUDITOR_DEFINITION["tools"],
            state_schema=SECURITY_AUDITOR_DEFINITION["state_schema"],
            transitions=[Transition(t["from"], t["to"]) for t in SECURITY_AUDITOR_DEFINITION["transitions"]],
        ),
        {
            "collect_config": partial(sec_collect_config, tools=tools),
            "scan_baseline": partial(sec_scan_baseline, tools=tools),
            "analyze_acl": partial(sec_analyze_acl, tools=tools),
            "report": partial(sec_report, tools=tools),
        },
    )
    runner.register(
        AgentDefinition(
            name=COMPLIANCE_DEFINITION["name"],
            role=COMPLIANCE_DEFINITION["role"],
            system_prompt=COMPLIANCE_DEFINITION["system_prompt"],
            tools=COMPLIANCE_DEFINITION["tools"],
            state_schema=COMPLIANCE_DEFINITION["state_schema"],
            transitions=[Transition(t["from"], t["to"]) for t in COMPLIANCE_DEFINITION["transitions"]],
        ),
        {
            "gather": partial(compliance_gather, tools=tools),
            "aggregate": partial(compliance_aggregate, tools=tools),
            "render": partial(compliance_render, tools=tools),
        },
    )

    # RdmAgent（Phase 4 RDMA 专项，差异化护城河）
    from app.agents.rdma_handlers import (
        RDMA_AGENT_DEFINITION,
        rdma_collect,
        rdma_diagnose,
        rdma_suggest_tuning,
    )

    runner.register(
        AgentDefinition(
            name=RDMA_AGENT_DEFINITION["name"],
            role=RDMA_AGENT_DEFINITION["role"],
            system_prompt=RDMA_AGENT_DEFINITION["system_prompt"],
            tools=RDMA_AGENT_DEFINITION["tools"],
            state_schema=RDMA_AGENT_DEFINITION["state_schema"],
            transitions=[Transition(t["from"], t["to"]) for t in RDMA_AGENT_DEFINITION["transitions"]],
        ),
        {
            "collect": partial(rdma_collect, tools=tools),
            "diagnose": partial(rdma_diagnose, tools=tools),
            "suggest_tuning": partial(rdma_suggest_tuning, tools=tools),
        },
    )

    # WirelessAgent（Phase 4 M10）
    from app.agents.wireless_handlers import (
        WIRELESS_AGENT_DEFINITION,
        wireless_collect,
        wireless_plan,
        wireless_suggest_config,
    )

    runner.register(
        AgentDefinition(
            name=WIRELESS_AGENT_DEFINITION["name"],
            role=WIRELESS_AGENT_DEFINITION["role"],
            system_prompt=WIRELESS_AGENT_DEFINITION["system_prompt"],
            tools=WIRELESS_AGENT_DEFINITION["tools"],
            state_schema=WIRELESS_AGENT_DEFINITION["state_schema"],
            transitions=[Transition(t["from"], t["to"]) for t in WIRELESS_AGENT_DEFINITION["transitions"]],
        ),
        {
            "collect": partial(wireless_collect, tools=tools),
            "plan": partial(wireless_plan, tools=tools),
            "suggest_config": partial(wireless_suggest_config, tools=tools),
        },
    )
    return runner


def _observer_definition() -> AgentDefinition:
    from app.agents.observer_handlers import OBSERVER_DEFINITION

    d = OBSERVER_DEFINITION
    return AgentDefinition(
        name=d["name"],
        role=d["role"],
        system_prompt=d["system_prompt"],
        tools=d["tools"],
        state_schema=d["state_schema"],
        transitions=[Transition(t["from"], t["to"]) for t in d["transitions"]],
        interrupt_points=d.get("interrupt_points", []),
    )


def _troubleshooter_definition() -> AgentDefinition:
    from app.agents.troubleshooter_handlers import TROUBLESHOOTER_DEFINITION

    d = TROUBLESHOOTER_DEFINITION
    return AgentDefinition(
        name=d["name"],
        role=d["role"],
        system_prompt=d["system_prompt"],
        tools=d["tools"],
        state_schema=d["state_schema"],
        transitions=[Transition(t["from"], t["to"]) for t in d["transitions"]],
        interrupt_points=d.get("interrupt_points", []),
    )


def _deploy_definition() -> AgentDefinition:
    from app.agents.deploy_handlers import DEPLOY_DEFINITION

    d = DEPLOY_DEFINITION
    return AgentDefinition(
        name=d["name"],
        role=d["role"],
        system_prompt=d["system_prompt"],
        tools=d["tools"],
        state_schema=d["state_schema"],
        transitions=[Transition(t["from"], t["to"]) for t in d["transitions"]],
        interrupt_points=d.get("interrupt_points", []),
    )
