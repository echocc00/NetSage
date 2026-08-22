"""Troubleshooter Agent 节点处理（Phase 2 P2-10）。

collect → analyze(RCA) → rank_causes → suggest_fixes
调 RCA 引擎 + SUZIEQ 状态 + RAG 历史案例。
"""
from __future__ import annotations

from typing import Any

from app.agents.classifier import Scenario, classify
from app.agents.rca_engine import RCAEngine, SymptomContext
from app.core.logging import get_logger
from app.tools.registry import ToolRegistry

logger = get_logger("troubleshooter_handler")

_rca = RCAEngine()


async def troubleshoot_collect(state: dict, tools: ToolRegistry, llm=None) -> dict:
    """收集多源数据：设备配置 + 协议状态 + 变更历史 + RAG 案例。"""
    symptom = state.get("query", "")
    protocol = state.get("scenario", "bgp")
    device = state.get("device", {})

    # 1. RAG 检索同类历史案例（MockToolRegistry 占位，P2-6 接 SUZIEQ 后补实时状态）
    try:
        cases_result = await tools.invoke(
            "rag.search", query=symptom, top_k=5
        )
        rag_cases = cases_result if isinstance(cases_result, list) else []
    except Exception:
        rag_cases = []

    # 2. 协议状态（Phase 2 W4 接 SUZIEQ，当前占位）
    protocol_state = state.get("protocol_state", {})

    # 3. 变更历史（Phase 2 接 audit_logs，当前占位）
    recent_changes = state.get("recent_changes", [])

    state["collected"] = {
        "rag_cases": rag_cases,
        "protocol_state": protocol_state,
        "recent_changes": recent_changes,
        "device": device,
    }
    logger.info("troubleshoot_collected", protocol=protocol, cases=len(rag_cases))
    return state


async def troubleshoot_analyze(state: dict, tools: ToolRegistry, llm=None) -> dict:
    """RCA 引擎分析 → 根因排序。"""
    collected = state.get("collected", {})
    symptom = state.get("query", "")
    protocol = state.get("scenario", "bgp")

    ctx = SymptomContext(
        symptom=symptom,
        protocol=protocol,
        affected_devices=[state.get("device", {}).get("name", "")] if state.get("device") else [],
        recent_changes=collected.get("recent_changes", []),
        protocol_state=collected.get("protocol_state", {}),
        rag_cases=collected.get("rag_cases", []),
    )

    causes = _rca.analyze(ctx)
    state["root_causes"] = [
        {
            "rank": c.rank,
            "cause": c.cause,
            "probability": c.probability,
            "category": c.category,
            "evidence": c.evidence,
            "verify_command": c.verify_command,
            "fix": c.fix,
            "confidence": c.confidence,
        }
        for c in causes
    ]
    logger.info("troubleshoot_analyzed", causes=len(causes), top=causes[0].cause if causes else "none")
    return state


async def troubleshoot_suggest_fixes(state: dict, tools: ToolRegistry, llm=None) -> dict:
    """为 top 根因生成修复方案 + 验证步骤 + 一键变更单草稿。"""
    causes = state.get("root_causes", [])
    if not causes:
        state["fixes"] = []
        return state

    # 取 top 3 根因的修复方案
    fixes = []
    for cause in causes[:3]:
        fixes.append({
            "rank": cause["rank"],
            "cause": cause["cause"],
            "probability": cause["probability"],
            "confidence": cause["confidence"],
            "verify_command": cause["verify_command"],
            "fix": cause["fix"],
            "requires_approval": True,  # 修复变更需走三道闸（v2.0 十章）
            "requires_human_confirm": cause["confidence"] < 0.5,  # 低置信度需人工确认
        })

    state["fixes"] = fixes
    state["can_auto_fix"] = any(
        f["confidence"] >= 0.7 and not f["requires_human_confirm"] for f in fixes
    )
    logger.info("fixes_suggested", count=len(fixes), auto_fix=state["can_auto_fix"])
    return state


# Troubleshooter Agent 定义（注册到 agent_runtime）
TROUBLESHOOTER_DEFINITION = {
    "name": "troubleshooter",
    "role": "故障排查 Agent：多源数据关联 + 根因排序 + 修复建议",
    "system_prompt": "你是网络故障排查专家。基于症状 + 多源数据，给出 ≥3 候选根因（按概率排序）+ 证据链 + 验证命令 + 修复方案。低置信度要求人工确认。",
    "tools": ["rag.search", "suzieq.query_state", "suzieq.assert_state", "napalm.get_config"],
    "state_schema": {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "scenario": {"type": "string"},
            "root_causes": {"type": "array"},
            "fixes": {"type": "array"},
        },
    },
    "transitions": [
        {"from": "collect", "to": "analyze"},
        {"from": "analyze", "to": "suggest_fixes"},
        {"from": "suggest_fixes", "to": "END"},
    ],
    "interrupt_points": [],
}