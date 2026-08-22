"""顺序执行 backend（Phase 1 W5 默认）。

不依赖 LangGraph API 细节，按 transitions 顺序执行 node_handlers。
LangGraph 真实 backend（含 checkpoint/interrupt）W5 联调时接入（v2.0 三十章 30.1）。
这样 Agent 定义与执行解耦，换 backend 零改 YAML。
"""
from __future__ import annotations

from typing import Any

from app.core.logging import get_logger
from app.runtime.base import AgentBackend, AgentDefinition, CompiledGraph

logger = get_logger("runtime_sequential")


class SequentialGraph:
    """顺序执行 transitions，支持 interrupt_points 暂停。"""

    def __init__(
        self,
        defn: AgentDefinition,
        node_handlers: dict[str, Any],
    ) -> None:
        self.defn = defn
        self.handlers = node_handlers
        # 暂存中断状态（Phase 3 换 LangGraph checkpointer 持久化）
        self._interrupted: dict[str, dict] = {}

    async def invoke(self, state: dict, config: dict) -> dict:
        """顺序执行所有节点，遇 interrupt_point 暂停返回。"""
        ordered = self._topological_order()
        for node_name in ordered:
            if node_name in self.defn.interrupt_points:
                self._interrupted[config["configurable"]["thread_id"]] = {
                    "state": state,
                    "next": ordered[ordered.index(node_name):],
                }
                logger.info("agent_interrupted", agent=self.defn.name, node=node_name)
                state["__interrupted_at__"] = node_name
                return state
            handler = self.handlers.get(node_name)
            if handler is None:
                logger.warning("agent_no_handler", agent=self.defn.name, node=node_name)
                continue
            logger.info("agent_step", agent=self.defn.name, node=node_name)
            state = await handler(state) if _is_async(handler) else handler(state)
        return state

    async def stream(self, state: dict, config: dict):
        """流式执行，每步 yield 事件。"""
        ordered = self._topological_order()
        for node_name in ordered:
            if node_name in self.defn.interrupt_points:
                yield {"node": node_name, "event": "interrupt", "state": state}
                return
            handler = self.handlers.get(node_name)
            if handler is None:
                continue
            state = await handler(state) if _is_async(handler) else handler(state)
            yield {"node": node_name, "event": "step_done", "state": state}

    async def resume(self, config: dict) -> dict:
        """恢复中断执行：执行 interrupt 节点本身（已审批）+ 后续。"""
        thread_id = config["configurable"]["thread_id"]
        ctx = self._interrupted.pop(thread_id, None)
        if ctx is None:
            return {"error": "no interrupted state"}
        state = ctx["state"]
        remaining = ctx["next"]
        # 执行 interrupt 节点本身（审批通过）+ 后续节点
        for node_name in remaining:
            handler = self.handlers.get(node_name)
            if handler is None:
                continue
            state = await handler(state) if _is_async(handler) else handler(state)
        state.pop("__interrupted_at__", None)
        return state

    def _topological_order(self) -> list[str]:
        """从 transitions 推导节点执行顺序（简单线性 DAG）。"""
        if not self.defn.transitions:
            return list(self.handlers.keys())
        order: list[str] = []
        seen: set[str] = set()
        # 找起点（无入边）
        all_nodes = {t.from_node for t in self.defn.transitions}
        to_nodes = {t.to_node for t in self.defn.transitions if t.to_node != "END"}
        starts = all_nodes - to_nodes
        current = next(iter(starts), None)
        while current and current != "END" and current not in seen:
            order.append(current)
            seen.add(current)
            # 找下一个
            current = next(
                (t.to_node for t in self.defn.transitions if t.from_node == current and t.to_node != "END"),
                None,
            )
        return order


def _is_async(fn: Any) -> bool:
    import asyncio

    return asyncio.iscoroutinefunction(fn)


class SequentialBackend(AgentBackend):
    """顺序执行后端工厂。"""

    def compile(self, defn: AgentDefinition, node_handlers: dict[str, Any]) -> CompiledGraph:
        return SequentialGraph(defn, node_handlers)
