"""三道闸 Pipeline 编排（v2.0 十章 + 开发计划十三章 13.2）。

编排顺序：快照 → 仿真闸 → 校验闸 → 审批闸 → 下发。
任一闸失败：回炉或回滚；下发失败：自动回滚到快照。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.core.logging import get_logger
from app.gates.approval import ApprovalGate
from app.gates.base import GateContext
from app.gates.models import ChangeStatus, GateResult, assert_transition
from app.gates.simulation import SimulationGate
from app.gates.snapshot import SnapshotService
from app.gates.validation import ValidationGate
from app.tools.registry import ToolRegistry

logger = get_logger("gate_pipeline")


@dataclass
class PipelineContext:
    """Pipeline 执行上下文（实现 GateContext）。"""

    request_id: int
    nim: dict
    devices: list[dict]  # [{id, vendor, host, username, password, port}]
    configs: dict[str, str] = field(default_factory=dict)
    assertions: list[dict] = field(default_factory=list)
    tools: ToolRegistry = None  # type: ignore[assignment]
    snapshots: list[dict] = field(default_factory=list)


class GatePipeline:
    """三道闸编排器。"""

    def __init__(self, tools: ToolRegistry) -> None:
        self.tools = tools
        self.snapshot = SnapshotService(tools)
        self.simulation = SimulationGate(tools)
        self.validation = ValidationGate(tools)
        self.approval = ApprovalGate()

    async def run(self, ctx: PipelineContext, status: ChangeStatus = ChangeStatus.SIM_PENDING) -> dict:
        """按状态机推进。每个闸根据当前状态决定是否执行。"""
        result: dict[str, Any] = {"request_id": ctx.request_id, "steps": []}

        # ① 变更前快照（所有设备）
        if status == ChangeStatus.SIM_PENDING:
            for dev in ctx.devices:
                snap = await self.snapshot.capture(
                    dev["id"], dev["vendor"], dev["host"], dev["username"], dev["password"], dev.get("port", 22)
                )
                ctx.snapshots.append(snap)
            result["steps"].append({"gate": "snapshot", "captured": len(ctx.snapshots)})

        # ② 仿真闸
        sim_result = await self.simulation.execute(ctx)
        result["steps"].append({"gate": "simulation", "passed": sim_result.passed})
        if not sim_result.passed:
            assert_transition(status, ChangeStatus.SIM_FAILED)
            result["status"] = ChangeStatus.SIM_FAILED
            result["error"] = sim_result.error
            return result
        assert_transition(status, ChangeStatus.SIM_PASSED)
        status = ChangeStatus.SIM_PASSED

        # ③ 校验闸
        assert_transition(status, ChangeStatus.VAL_PENDING)
        status = ChangeStatus.VAL_PENDING
        val_result = await self.validation.execute(ctx)
        result["steps"].append({"gate": "validation", "passed": val_result.passed})
        if not val_result.passed:
            assert_transition(status, ChangeStatus.VAL_FAILED)
            result["status"] = ChangeStatus.VAL_FAILED
            result["error"] = val_result.error
            return result
        assert_transition(status, ChangeStatus.VAL_PASSED)
        status = ChangeStatus.VAL_PASSED

        # ④ 审批闸（Phase 1：进入 pending，等外部 resume）
        assert_transition(status, ChangeStatus.APPROVAL)
        appr_result = await self.approval.execute(ctx)
        result["steps"].append({"gate": "approval", "passed": appr_result.passed})
        result["status"] = ChangeStatus.APPROVAL
        result["approval_pending"] = True
        return result

    async def deploy(self, ctx: PipelineContext) -> dict:
        """审批通过后下发：顺序 commit + checkpoint，失败自动回滚。"""
        result: dict[str, Any] = {"request_id": ctx.request_id, "steps": []}

        for i, dev in enumerate(ctx.devices):
            try:
                # 加载候选 + commit
                config = ctx.configs.get(dev["name"], dev.get("config", ""))
                await self.tools.invoke(
                    "napalm.load_merge_candidate",
                    vendor=dev["vendor"], host=dev["host"],
                    username=dev["username"], password=dev["password"],
                    config=config, port=dev.get("port", 22),
                )
                await self.tools.invoke(
                    "napalm.commit",
                    vendor=dev["vendor"], host=dev["host"],
                    username=dev["username"], password=dev["password"],
                    port=dev.get("port", 22),
                )
                result["steps"].append({"device": dev["name"], "status": "committed"})
                logger.info("deploy_step_ok", request_id=ctx.request_id, device=dev["name"], step=i)
            except Exception as e:
                logger.error("deploy_step_failed", request_id=ctx.request_id, device=dev["name"], error=str(e))
                # 自动回滚已下发设备
                await self._rollback_all(ctx, upto=i)
                result["status"] = ChangeStatus.ROLLED_BACK
                result["error"] = f"下发失败（{dev['name']}）：{e}，已回滚"
                return result

        result["status"] = ChangeStatus.DONE
        return result

    async def _rollback_all(self, ctx: PipelineContext, upto: int) -> None:
        """回滚前 upto 台设备到快照。"""
        for i in range(upto + 1):
            if i >= len(ctx.snapshots):
                break
            dev = ctx.devices[i]
            snap = ctx.snapshots[i]
            try:
                await self.snapshot.rollback(
                    dev["id"], dev["vendor"], dev["host"], dev["username"], dev["password"],
                    snap["object_key"], snap["config_hash"], dev.get("port", 22),
                )
                logger.info("rollback_ok", request_id=ctx.request_id, device=dev["name"])
            except Exception as e:
                logger.error("rollback_failed", device=dev["name"], error=str(e))
