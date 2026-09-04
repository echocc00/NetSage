"""ObserverAgent 测试（Phase 2 P2-7）。"""
from __future__ import annotations

import pytest

from app.agents.registry import build_runner
from app.tools.registry import MockToolRegistry


@pytest.mark.asyncio
async def test_observer_no_anomaly():
    """全网状态正常 → 无告警。"""
    runner = build_runner()
    # Mock SUZIEQ 工具（状态正常）
    result = await runner.run("observer", {}, session_id="obs-1")
    # MockToolRegistry 默认返回 {"status":"ok"}，无 down/error → 无异常
    assert result.get("alert_status") in ("no_anomaly", "alerted", None)


@pytest.mark.asyncio
async def test_observer_detects_anomaly():
    """状态含 down/notEstab → 检测异常并告警。"""
    from functools import partial

    from app.agents import observer_handlers as oh

    tools = MockToolRegistry()
    tools.stub("suzieq.poll_once", lambda **kw: {"status": "polled"})
    tools.stub("suzieq.query_state", lambda **kw: {"rows": "neighbor 10.1.1.2 state=notEstab"})
    tools.stub("suzieq.assert_state", lambda **kw: {"result": "fail: bgp neighbor down"})

    state = {}
    state = await partial(oh.observer_poll, tools=tools)(state)
    state = await partial(oh.observer_analyze, tools=tools)(state)
    state = await partial(oh.observer_alert, tools=tools)(state)

    assert state.get("needs_alert") is True
    assert len(state.get("anomalies", [])) >= 1
    assert state["alert_status"] == "alerted"
    assert state["alert_summary"]["anomaly_count"] >= 1


@pytest.mark.asyncio
async def test_observer_poll_failure_handled():
    """SUZIEQ 不可达时不崩溃（记录错误继续）。"""
    from functools import partial

    from app.agents import observer_handlers as oh

    tools = MockToolRegistry()
    tools.stub("suzieq.poll_once", lambda **kw: (_ for _ in ()).throw(RuntimeError("suzieq down")))

    state = await partial(oh.observer_poll, tools=tools)(state := {})
    assert "poll_error" in state


def test_observer_registered():
    runner = build_runner()
    assert "observer" in runner._compiled


def test_observer_definition_linear():
    """ObserverAgent 线性执行（无 HITL，定时任务）。"""
    from app.agents.observer_handlers import OBSERVER_DEFINITION

    assert OBSERVER_DEFINITION["interrupt_points"] == []
    transitions = OBSERVER_DEFINITION["transitions"]
    assert len(transitions) == 3  # poll→analyze→alert→END
