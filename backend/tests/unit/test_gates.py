"""三道闸引擎单元测试（v2.0 十章 + 十九章验收）。

用 MockToolRegistry 验证：
- 状态机合法/非法流转
- Pipeline 编排顺序（快照→仿真→校验→审批）
- 任一闸失败正确中断
- 下发失败自动回滚
- 快照 hash 校验
"""
from __future__ import annotations

import pytest

from app.gates.models import (
    ChangeStatus,
    GateResult,
    IllegalTransitionError,
    assert_transition,
)
from app.gates.pipeline import GatePipeline, PipelineContext
from app.tools.registry import MockToolRegistry


@pytest.fixture
def tools() -> MockToolRegistry:
    registry = MockToolRegistry()
    # 预设所有 MCP 工具的 mock 响应
    registry.stub("napalm.get_config", lambda **kw: {"config": "interface GE0/0\n ip address 10.1.2.3 255.255.255.0"})
    registry.stub("napalm.load_merge_candidate", lambda **kw: {"status": "candidate_loaded"})
    registry.stub("napalm.commit", lambda **kw: {"status": "committed"})
    registry.stub("containerlab.deploy_topology", lambda **kw: {"status": "deployed", "nodes": [{"name": "leaf01"}]})
    registry.stub("containerlab.exec_on_node", lambda **kw: {"stdout": "BGP neighbor is Up"})
    registry.stub("batfish.lint_config", lambda **kw: {"passed": True, "warnings": []})
    registry.stub("batfish.assert_reachability", lambda **kw: {"passed": True})
    registry.stub("batfish.assert_routing", lambda **kw: {"passed": True})
    return registry


@pytest.fixture
def ctx(tools: MockToolRegistry) -> PipelineContext:
    return PipelineContext(
        request_id=42,
        nim={
            "topology_yaml": "name: test\n",
            "sim_checks": [
                {"node": "leaf01", "command": "show bgp summary", "expect": "Up"},
            ],
        },
        devices=[
            {"id": 1, "name": "leaf01", "vendor": "cisco_iosxe", "host": "10.1.2.3",
             "username": "admin", "password": "pass", "port": 22},
        ],
        configs={"leaf01": "router bgp 65001"},
        assertions=[
            {"type": "reachability", "src": "leaf01", "dst": "spine01"},
            {"type": "routing", "prefix": "10.1.2.0/24"},
        ],
        tools=tools,
    )


@pytest.fixture
def pipeline(tools: MockToolRegistry) -> GatePipeline:
    return GatePipeline(tools)


# ===== 状态机 =====


def test_legal_transition():
    assert_transition(ChangeStatus.DRAFT, ChangeStatus.SIM_PENDING)
    assert_transition(ChangeStatus.SIM_PASSED, ChangeStatus.VAL_PENDING)
    assert_transition(ChangeStatus.APPROVED, ChangeStatus.DEPLOYING)


def test_illegal_transition_raises():
    with pytest.raises(IllegalTransitionError):
        assert_transition(ChangeStatus.DRAFT, ChangeStatus.DONE)
    with pytest.raises(IllegalTransitionError):
        assert_transition(ChangeStatus.APPROVAL, ChangeStatus.DONE)  # 必须经 approved


def test_closed_is_terminal():
    """CLOSED 是终态，无合法后继。"""
    assert VALID_TRANSITIONS_CHECK(ChangeStatus.CLOSED)


def VALID_TRANSITIONS_CHECK(status: ChangeStatus) -> bool:
    from app.gates.models import VALID_TRANSITIONS
    return len(VALID_TRANSITIONS.get(status, set())) == 0


# ===== Pipeline 编排 =====


@pytest.mark.asyncio
async def test_pipeline_happy_path(pipeline: GatePipeline, ctx: PipelineContext):
    """全闸通过 → 进入 approval pending（v2.0 十章三道闸顺序）。"""
    result = await pipeline.run(ctx)
    steps = [s["gate"] for s in result["steps"]]
    assert steps == ["snapshot", "simulation", "validation", "approval"]
    assert result["approval_pending"] is True
    assert result["status"] == ChangeStatus.APPROVAL
    # 快照已抓取
    assert len(ctx.snapshots) == 1
    assert ctx.snapshots[0]["config_hash"]


@pytest.mark.asyncio
async def test_simulation_failure_aborts(pipeline: GatePipeline, ctx: PipelineContext, tools: MockToolRegistry):
    """仿真闸失败 → SIM_FAILED，不进校验闸。"""
    tools.stub("containerlab.deploy_topology", lambda **kw: {"status": "error"})
    result = await pipeline.run(ctx)
    assert result["status"] == ChangeStatus.SIM_FAILED
    gates = [s["gate"] for s in result["steps"]]
    assert "validation" not in gates  # 仿真失败后不执行校验


@pytest.mark.asyncio
async def test_validation_failure_aborts(pipeline: GatePipeline, ctx: PipelineContext, tools: MockToolRegistry):
    """校验闸失败 → VAL_FAILED。"""
    tools.stub("batfish.assert_reachability", lambda **kw: {"passed": False})
    result = await pipeline.run(ctx)
    assert result["status"] == ChangeStatus.VAL_FAILED
    assert result["error"]


@pytest.mark.asyncio
async def test_snapshot_captured_before_gates(pipeline: GatePipeline, ctx: PipelineContext, tools: MockToolRegistry):
    """变更前必须先抓快照（v2.0 十章配置快照）。"""
    await pipeline.run(ctx)
    # napalm.get_config 在仿真/校验之前被调用
    tool_calls = [c[0] for c in tools.calls]
    assert "napalm.get_config" in tool_calls
    # 第一次调用是快照（在 containerlab.deploy 之前）
    snapshot_idx = tool_calls.index("napalm.get_config")
    deploy_idx = tool_calls.index("containerlab.deploy_topology")
    assert snapshot_idx < deploy_idx


# ===== 下发与回滚 =====


@pytest.mark.asyncio
async def test_deploy_success(pipeline: GatePipeline, ctx: PipelineContext):
    """审批通过后下发成功 → DONE。"""
    result = await pipeline.deploy(ctx)
    assert result["status"] == ChangeStatus.DONE
    assert all(s["status"] == "committed" for s in result["steps"])


@pytest.mark.asyncio
async def test_deploy_failure_triggers_rollback(pipeline: GatePipeline, ctx: PipelineContext, tools: MockToolRegistry):
    """下发失败 → 自动回滚到快照（v2.0 十章失败自动回滚）。"""
    # 预置快照（deploy 不走 run，需先有快照可回滚）
    snap = await pipeline.snapshot.capture(
        1, "cisco_iosxe", "10.1.2.3", "admin", "pass", 22
    )
    ctx.snapshots.append(snap)

    # 第二台设备 commit 失败
    call_count = {"n": 0}

    def flaky_commit(**kw):
        call_count["n"] += 1
        if call_count["n"] >= 2:
            raise RuntimeError("commit timeout")
        return {"status": "committed"}

    tools.stub("napalm.commit", flaky_commit)
    # 两台设备（第二台无快照，跳过回滚但不影响第一台回滚验证）
    ctx.devices.append(
        {"id": 2, "name": "leaf02", "vendor": "cisco_iosxe", "host": "10.1.2.4",
         "username": "admin", "password": "pass", "port": 22}
    )

    result = await pipeline.deploy(ctx)
    assert result["status"] == ChangeStatus.ROLLED_BACK
    # 回滚调用了 napalm.get_config（校验 hash）
    assert any(c[0] == "napalm.get_config" for c in tools.calls)


# ===== GateResult =====


def test_gate_result_ok():
    r = GateResult.ok("simulation", [{"a": 1}])
    assert r.passed and r.gate == "simulation" and r.evidence == [{"a": 1}]


def test_gate_result_fail():
    r = GateResult.fail("validation", "断言失败")
    assert not r.passed and r.error == "断言失败"
