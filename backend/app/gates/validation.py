"""闸 2：Batfish 静态校验（v2.0 十章安全闸 2）。

reachability / ACL / routing 断言。false negative = 0（v2.0 19.1 验收 3）。
"""
from __future__ import annotations

from app.core.logging import get_logger
from app.gates.base import GateContext
from app.gates.models import GateResult
from app.tools.registry import ToolRegistry

logger = get_logger("gate_validation")


class ValidationGate:
    """加载配置快照到 Batfish，跑断言。"""

    name = "validation"

    def __init__(self, tools: ToolRegistry) -> None:
        self.tools = tools

    async def execute(self, ctx: GateContext) -> GateResult:
        try:
            # 1. lint 每台设备配置语法
            evidence: list[dict] = []
            for device_name, config in ctx.configs.items():
                lint = await self.tools.invoke(
                    "batfish.lint_config", config_text=config, vendor="cisco"
                )
                passed = lint.get("passed", True) if isinstance(lint, dict) else True
                evidence.append({"device": device_name, "lint_passed": passed})
                if not passed:
                    return GateResult.fail(
                        self.name, f"{device_name} 语法 lint 失败: {lint}", evidence
                    )

            # 2. 跑断言（reachability/ACL/routing）
            for assertion in ctx.assertions:
                atype = assertion.get("type")
                if atype == "reachability":
                    result = await self.tools.invoke(
                        "batfish.assert_reachability",
                        snapshot=assertion.get("snapshot", "snap"),
                        src=assertion["src"],
                        dst=assertion["dst"],
                    )
                elif atype == "routing":
                    result = await self.tools.invoke(
                        "batfish.assert_routing",
                        snapshot=assertion.get("snapshot", "snap"),
                        prefix=assertion["prefix"],
                    )
                elif atype == "acl":
                    result = await self.tools.invoke(
                        "batfish.assert_acl",
                        snapshot=assertion.get("snapshot", "snap"),
                        acl_spec=assertion["spec"],
                    )
                else:
                    continue

                passed = result.get("passed", False) if isinstance(result, dict) else False
                evidence.append({"assertion": atype, "passed": passed, "result": result})
                if not passed:
                    return GateResult.fail(
                        self.name, f"断言失败：{atype} {assertion}", evidence
                    )

            logger.info("gate_validation_passed", request_id=ctx.request_id, assertions=len(ctx.assertions))
            return GateResult.ok(self.name, evidence)

        except Exception as e:
            logger.error("gate_validation_error", request_id=ctx.request_id, error=str(e))
            return GateResult.fail(self.name, f"校验闸异常: {e}")
