"""ObserverAgent 节点处理（Phase 2 P2-7）。

poll → analyze → alert_or_done
定时采集全网状态 → 趋势分析 → 异常告警。
SUZIEQ Assert 框架做配置 vs 状态断言。
"""
from __future__ import annotations

from app.core.logging import get_logger
from app.tools.registry import ToolRegistry

logger = get_logger("observer_handler")


async def observer_poll(state: dict, tools: ToolRegistry, llm=None) -> dict:
    """触发 SUZIEQ poll + 查关键状态表。"""
    try:
        await tools.invoke("suzieq.poll_once")
        # 查 BGP / OSPF / interface 状态
        bgp_state = await tools.invoke("suzieq.query_state", table="bgp", filter="")
        interface_state = await tools.invoke("suzieq.query_state", table="interface", filter="")
        state["polled_state"] = {
            "bgp": bgp_state,
            "interface": interface_state,
        }
        logger.info("observer_polled")
    except Exception as e:
        state["poll_error"] = str(e)
        logger.warning("observer_poll_failed", error=str(e)[:80])
    return state


async def observer_analyze(state: dict, tools: ToolRegistry, llm=None) -> dict:
    """分析状态：SUZIEQ Assert + 异常检测。"""
    anomalies: list[dict] = []

    # 1. SUZIEQ Assert（BGP 邻居全 Established）
    try:
        bgp_assert = await tools.invoke("suzieq.assert_state", assertion="bgp-assert")
        if isinstance(bgp_assert, dict) and "fail" in str(bgp_assert.get("result", "")).lower():
            anomalies.append({
                "type": "bgp_assert_fail",
                "detail": bgp_assert.get("result", ""),
                "severity": "high",
            })
    except Exception:
        pass  # assert 不支持时跳过

    # 2. 状态文本异常检测（简化：查状态表里的 "down" / "notEstab"）
    polled = state.get("polled_state", {})
    for table, data in polled.items():
        data_str = str(data).lower()
        if "down" in data_str or "notestab" in data_str or "error" in data_str:
            anomalies.append({
                "type": f"{table}_anomaly",
                "detail": f"{table} 状态含 down/error",
                "severity": "medium",
            })

    state["anomalies"] = anomalies
    state["needs_alert"] = len(anomalies) > 0
    logger.info("observer_analyzed", anomalies=len(anomalies))
    return state


async def observer_alert(state: dict, tools: ToolRegistry, llm=None) -> dict:
    """有异常时告警（记录 + 可选 LLM 趋势分析）。"""
    if not state.get("needs_alert"):
        state["alert_status"] = "no_anomaly"
        return state

    anomalies = state.get("anomalies", [])
    state["alert_status"] = "alerted"
    state["alert_summary"] = {
        "anomaly_count": len(anomalies),
        "max_severity": max((a["severity"] for a in anomalies), default="low"),
        "anomalies": anomalies,
    }
    logger.warning("observer_alerted", count=len(anomalies))
    return state


OBSERVER_DEFINITION = {
    "name": "observer",
    "role": "网络可观测性 Agent：定时 poll + 趋势分析 + 异常告警",
    "system_prompt": "你是网络可观测性分析器。定时采集全网状态，用 SUZIEQ Assert 做断言，异常时告警。",
    "tools": ["suzieq.poll_once", "suzieq.query_state", "suzieq.assert_state"],
    "state_schema": {"type": "object"},
    "transitions": [
        {"from": "poll", "to": "analyze"},
        {"from": "analyze", "to": "alert"},
        {"from": "alert", "to": "END"},
    ],
    "interrupt_points": [],
}
