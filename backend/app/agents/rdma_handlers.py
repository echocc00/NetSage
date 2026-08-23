"""RdmAgent handlers（Phase 4 RDMA 专项，v2.0 5.1 差异化护城河）。

collect → diagnose → suggest_tuning
"""
from __future__ import annotations

from typing import Any

RDMA_AGENT_DEFINITION = {
    "name": "rdm_agent",
    "role": "RDMA/IB 专项 Agent：无损网络设计 + RoCE 调优 + 配置诊断",
    "system_prompt": "你是 RDMA/InfiniBand 专家。诊断 RoCE 丢包/延迟，输出 PFC/ECN/DCQCN 调优方案。",
    "tools": ["opensm.ibstat", "opensm.ibdiscover", "opensm.perfquery",
              "napalm.get_config", "rag.search", "template.render"],
    "state_schema": {"type": "object"},
    "transitions": [
        {"from": "collect", "to": "diagnose"},
        {"from": "diagnose", "to": "suggest_tuning"},
        {"from": "suggest_tuning", "to": "END"},
    ],
    "interrupt_points": [],
}


async def rdma_collect(state: dict, tools: Any) -> dict:
    """采集：IB 状态 + RoCE 计数器 + 配置。"""
    ibstat = state.get("ibstat", {})
    perf = state.get("perf", {})
    config = state.get("config", "")
    if tools and not ibstat:
        try:
            ibstat = await tools.call("opensm.ibstat")
        except Exception:
            ibstat = {}
    if tools and not perf:
        try:
            perf = await tools.call("opensm.perfquery", lid=state.get("lid", 1))
        except Exception:
            perf = {}
    return {**state, "ibstat": ibstat, "perf": perf, "config": config}


async def rdma_diagnose(state: dict, tools: Any) -> dict:
    """诊断：瓶颈定位（PFC/ECN/buffer/MTU）。"""
    from app.agents.rdma_engine import RoCEDiagnoseEngine

    engine = RoCEDiagnoseEngine()
    result = engine.analyze(state)
    return {**state, "diagnosis": result}


async def rdma_suggest_tuning(state: dict, tools: Any) -> dict:
    """调优建议：PFC/ECN/DCQCN 参数 + 配置模板渲染。"""
    from app.services.template_loader import TemplateError, render

    diag = state.get("diagnosis", {})
    category = diag.get("category", "")
    vendor = state.get("vendor", "huawei")
    interface = state.get("interface", "10GE1/0/1")

    tuning = {
        "pfc_priority": 3,
        "pfc_headroom": "10KB",
        "ecn_threshold": "150KB",
        "ecn_ce_threshold": "200KB",
        "dcqcn_params": {"alpha": 0.5, "k_min": 1, "k_max": 100, "timer": 10},
        "mtu": 9100,
        "watchdog_interval": 100,
    }

    # 按诊断类别选模板
    config = ""
    vendor_key = "huawei_vrp" if vendor.startswith("huawei") else \
        "cisco_iosxe" if vendor.startswith("cisco") else \
        "arista_eos" if vendor.startswith("arista") else "huawei_vrp"

    template_map = {
        "pfc": f"{vendor_key}_roce_pfc",
        "ecn": f"{vendor_key}_roce_ecn",
        "buffer": f"{vendor_key}_roce_pfc",  # buffer 调 PFC headroom
        "mtu": f"{vendor_key}_roce_pfc",
        "physical": f"{vendor_key}_roce_pfc",
    }
    template_id = template_map.get(category, f"{vendor_key}_roce_pfc")

    try:
        config = render(template_id, {
            "interface": interface,
            "pfc_priority": tuning["pfc_priority"],
            "pfc_headroom": tuning["pfc_headroom"],
            "ecn_threshold": tuning["ecn_threshold"],
            "ecn_ce_threshold": tuning["ecn_ce_threshold"],
            "watchdog_interval": tuning["watchdog_interval"],
        })
    except TemplateError:
        config = ""

    return {
        **state,
        "tuning": tuning,
        "config": config,
        "template_used": template_id,
    }
