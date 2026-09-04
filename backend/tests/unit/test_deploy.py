"""DeployAgent 测试（Phase 2 P2-8）。"""
from __future__ import annotations

import pytest

from app.agents.deploy_handlers import DEPLOY_DEFINITION
from app.agents.registry import build_runner
from app.tools.registry import MockToolRegistry


def _tools() -> MockToolRegistry:
    t = MockToolRegistry()
    t.stub("napalm.apply_candidate", lambda **kw: {"status": "applied"})
    t.stub("napalm.get_facts", lambda **kw: {"vendor": "huawei", "hostname": "ok"})
    t.stub("napalm.rollback", lambda **kw: {"status": "rolled_back"})
    return t


def _approved_state(devices=None, configs=None, fail_device=None):
    """构造已审批 + 有快照的下发状态。"""
    devices = devices or [
        {"id": 1, "name": "spine01", "vendor": "huawei", "host": "10.1.1.1", "username": "a", "password": "b"},
    ]
    configs = configs or {"spine01": "router bgp 65001"}
    return {
        "change_status": "approved",
        "impact": {"confirmed_by": "engineer1"},
        "snapshots": [{"device_name": "spine01", "config": "old-config", "vendor": "huawei"}],
        "devices": devices,
        "configs": configs,
        "fail_device": fail_device,
    }


@pytest.mark.asyncio
async def test_deploy_full_success():
    """单设备下发成功（pre_check → deploy_loop → verify）。"""

    tools = _tools()
    runner = build_runner()
    state = _approved_state()
    result = await runner.run("deploy", state, session_id="dep-1")
    assert result["deploy_status"] == "success"
    assert "spine01" in result["deployed"]
    assert result.get("needs_rollback") is False


@pytest.mark.asyncio
async def test_deploy_multi_device_success():
    """多设备顺序下发全部成功。"""
    runner = build_runner()
    devices = [
        {"id": 1, "name": "spine01", "vendor": "huawei", "host": "10.1.1.1", "username": "a", "password": "b"},
        {"id": 2, "name": "spine02", "vendor": "huawei", "host": "10.1.1.2", "username": "a", "password": "b"},
    ]
    state = _approved_state(devices=devices, configs={"spine01": "cfg1", "spine02": "cfg2"})
    result = await runner.run("deploy", state, session_id="dep-2")
    assert result["deploy_status"] == "success"
    assert len(result["deployed"]) == 2


@pytest.mark.asyncio
async def test_deploy_failure_triggers_rollback(monkeypatch):
    """设备下发失败 → 自动回滚已下发设备。"""
    runner = build_runner()

    # mock apply_candidate 第二台失败（async callable）
    call_count = [0]

    async def failing_apply(**kw):
        call_count[0] += 1
        if call_count[0] == 2:
            raise RuntimeError("设备 spine02 下发失败：邻居未建立")
        return {"status": "applied"}

    tools = MockToolRegistry()
    tools.stub("napalm.apply_candidate", failing_apply)
    tools.stub("napalm.get_facts", lambda **kw: {"vendor": "huawei"})
    tools.stub("napalm.rollback", lambda **kw: {"status": "rolled_back"})

    # 注入 tools 到 deploy handlers
    from functools import partial

    from app.agents import deploy_handlers as dh

    devices = [
        {"id": 1, "name": "spine01", "vendor": "huawei", "host": "10.1.1.1", "username": "a", "password": "b"},
        {"id": 2, "name": "spine02", "vendor": "huawei", "host": "10.1.1.2", "username": "a", "password": "b"},
    ]
    state = _approved_state(devices=devices, configs={"spine01": "cfg1", "spine02": "cfg2"})
    state["snapshots"] = [
        {"device_name": "spine01", "config": "old1", "vendor": "huawei", "host": "10.1.1.1", "username": "a", "password": "b"},
        {"device_name": "spine02", "config": "old2", "vendor": "huawei", "host": "10.1.1.2", "username": "a", "password": "b"},
    ]

    # 手动跑 deploy_loop + verify（用注入的 tools）
    state = await partial(dh.deploy_pre_check, tools=tools)(state)
    state = await partial(dh.deploy_loop, tools=tools)(state)
    state = await partial(dh.deploy_verify, tools=tools)(state)

    assert state.get("failed")
    assert state["deploy_status"] == "rolled_back"
    assert state.get("needs_rollback") is True
    # spine01 已下发 → 应回滚
    rollback_devs = [r["device"] for r in state.get("rollback_results", [])]
    assert "spine01" in rollback_devs


@pytest.mark.asyncio
async def test_deploy_blocked_if_not_approved():
    """未审批 → pre_check 阻断。"""
    runner = build_runner()
    state = _approved_state()
    state["change_status"] = "draft"  # 未审批
    result = await runner.run("deploy", state, session_id="dep-4")
    assert result.get("deploy_blocked") is True
    assert "未审批" in result.get("deploy_error", "")
    assert result.get("deployed", []) == []


@pytest.mark.asyncio
async def test_deploy_blocked_if_no_snapshot():
    """无快照 → 阻断（无法保证回滚）。"""
    runner = build_runner()
    state = _approved_state()
    state["snapshots"] = []  # 无快照
    result = await runner.run("deploy", state, session_id="dep-5")
    assert result.get("deploy_blocked") is True
    assert "快照" in result.get("deploy_error", "")


@pytest.mark.asyncio
async def test_deploy_blocked_if_impact_unconfirmed():
    """影响范围未确认 → 阻断（v2.0 十章：自动推演+人工确认）。"""
    runner = build_runner()
    state = _approved_state()
    state["impact"] = {"confirmed_by": None}
    result = await runner.run("deploy", state, session_id="dep-6")
    assert result.get("deploy_blocked") is True
    assert "影响范围" in result.get("deploy_error", "")


def test_deploy_definition_linear_no_interrupt():
    """DeployAgent 线性执行，人审在外层三道闸完成（不在此 interrupt）。"""
    assert DEPLOY_DEFINITION["interrupt_points"] == []


def test_deploy_registered_in_runner():
    runner = build_runner()
    assert "deploy" in runner._compiled
