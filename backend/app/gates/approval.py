"""闸 3：人工逐条审批（v2.0 十章安全闸 3）。

Phase 1：DB 状态管理（approval → approved/rejected）。
Phase 3：接 LangGraph interrupt_before + SSE 推审批工作台。
"""
from __future__ import annotations

from app.core.logging import get_logger
from app.gates.base import GateContext
from app.gates.models import GateResult

logger = get_logger("gate_approval")


class ApprovalGate:
    """人工审批闸。Phase 1 同步返回 pending，等外部调 approve/reject 后 resume。"""

    name = "approval"

    async def execute(self, ctx: GateContext) -> GateResult:
        # Phase 1：仅标记进入 approval 状态，实际决策由 API 端点触发
        # Phase 3：改用 LangGraph interrupt_before，推 SSE 给前端审批工作台
        logger.info("gate_approval_pending", request_id=ctx.request_id)
        # 返回 passed=True 表示"已进入审批流"，非"已批准"
        # Pipeline 会在此暂停，等待 ApprovalService.resume()
        return GateResult.ok(
            self.name,
            [{"status": "approval_pending", "request_id": ctx.request_id}],
        )
