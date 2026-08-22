"""闸 1：Containerlab 仿真验证（v2.0 十章安全闸 1）。"""
from __future__ import annotations

from app.core.logging import get_logger
from app.gates.base import GateContext
from app.gates.models import GateResult
from app.tools.registry import ToolRegistry

logger = get_logger("gate_simulation")


class SimulationGate:
    """在 Containerlab 拉起拓扑，验证邻居/路由/连通性。"""

    name = "simulation"

    def __init__(self, tools: ToolRegistry) -> None:
        self.tools = tools

    async def execute(self, ctx: GateContext) -> GateResult:
        try:
            # 1. 根据拓扑描述部署（拓扑 YAML 由 ConfigEngine 生成，这里从 ctx 取）
            topo_yaml = ctx.nim.get("topology_yaml") or self._build_topo_from_nim(ctx.nim)
            deploy = await self.tools.invoke(
                "containerlab.deploy_topology", topo_yaml=topo_yaml, name=f"cr-{ctx.request_id}"
            )
            if deploy.get("status") != "deployed":
                return GateResult.fail(self.name, f"部署失败: {deploy}", [deploy])

            # 2. 仿真内验证（exec_on_node 跑 show 命令）
            evidence: list[dict] = [{"deploy": deploy}]
            checks = ctx.nim.get("sim_checks", [])
            for check in checks:
                node = check["node"]
                command = check["command"]
                expect = check.get("expect", "")
                out = await self.tools.invoke(
                    "containerlab.exec_on_node",
                    name=f"cr-{ctx.request_id}",
                    node=node,
                    command=command,
                )
                stdout = out.get("stdout", "")
                passed = expect in stdout if expect else True
                evidence.append({"node": node, "command": command, "passed": passed, "stdout": stdout[:200]})
                if not passed:
                    return GateResult.fail(
                        self.name, f"仿真验证失败：{node} 执行 {command} 未命中 {expect}", evidence
                    )

            logger.info("gate_simulation_passed", request_id=ctx.request_id, checks=len(checks))
            return GateResult.ok(self.name, evidence)

        except Exception as e:
            logger.error("gate_simulation_error", request_id=ctx.request_id, error=str(e))
            return GateResult.fail(self.name, f"仿真闸异常: {e}")

    @staticmethod
    def _build_topo_from_nim(nim: dict) -> str:
        """从 NIM 生成最小 containerlab YAML（W5 ConfigEngine 接入前的占位）。"""
        return nim.get("topology_yaml", "")


class SimulationGateAdapter:
    """适配 Gate 协议。"""

    name = "simulation"

    def __init__(self, inner: SimulationGate) -> None:
        self._inner = inner

    async def execute(self, ctx: GateContext) -> GateResult:
        return await self._inner.execute(ctx)
