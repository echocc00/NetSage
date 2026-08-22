"""Agent 运行时适配层（v2.0 三十章）。

抽象 AgentDefinition + AgentBackend，让 Agent 定义与框架解耦。
换框架（LangGraph→CrewAI/AutoGen）只改 backend，YAML 定义零改动。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class Transition:
    """DAG 边：from_node → to_node（可带条件）。"""
    from_node: str
    to_node: str          # "END" 表示终态
    condition: str | None = None


@dataclass
class AgentDefinition:
    """Agent 定义（可移植中间格式，框架无关）。

    所有 Agent 写成 YAML，runner 加载后编译为具体框架的图。
    """
    name: str
    role: str
    system_prompt: str
    tools: list[str]                      # 工具名，引用 registry（不绑框架 Tool 类）
    state_schema: dict                    # JSON Schema 描述状态
    transitions: list[Transition] = field(default_factory=list)
    interrupt_points: list[str] = field(default_factory=list)  # HITL 节点
    model_tier: str = "simple"            # LLM 难度路由（v2.0 二十九章）


class CompiledGraph(Protocol):
    """编译后的图（框架无关接口）。"""

    async def invoke(self, state: dict, config: dict) -> dict: ...
    async def stream(self, state: dict, config: dict): ...
    async def resume(self, config: dict) -> dict: ...


class AgentBackend(Protocol):
    """Agent 编排后端抽象（v2.0 三十章 30.1）。"""

    def compile(self, defn: AgentDefinition, node_handlers: dict[str, Any]) -> CompiledGraph:
        """编译 Agent 定义为可执行图。node_handlers: 节点名→异步处理函数。"""
        ...


class AgentRunner:
    """加载 YAML 定义 → 编译 → 执行。业务逻辑只依赖此接口。"""

    def __init__(self, backend: AgentBackend) -> None:
        self.backend = backend
        self._compiled: dict[str, CompiledGraph] = {}

    def register(self, defn: AgentDefinition, node_handlers: dict[str, Any]) -> None:
        """注册并编译 Agent。"""
        self._compiled[defn.name] = self.backend.compile(defn, node_handlers)

    async def run(self, agent_name: str, state: dict, session_id: str) -> dict:
        """同步执行（无 HITL 中断）。"""
        graph = self._compiled[agent_name]
        config = {"configurable": {"thread_id": session_id}}
        return await graph.invoke(state, config)

    async def stream(self, agent_name: str, state: dict, session_id: str):
        """流式执行（推送 DAG 进度给前端）。"""
        graph = self._compiled[agent_name]
        config = {"configurable": {"thread_id": session_id}}
        async for event in graph.stream(state, config):
            yield event

    async def resume(self, agent_name: str, session_id: str) -> dict:
        """恢复中断的执行（HITL 审批后 resume）。"""
        graph = self._compiled[agent_name]
        config = {"configurable": {"thread_id": session_id}}
        return await graph.resume(config)
