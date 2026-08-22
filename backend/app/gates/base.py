"""Gate 抽象基类（v2.0 开发计划十三章 13.2）。"""
from __future__ import annotations

from typing import Any, Protocol

from app.gates.models import GateResult


class GateContext(Protocol):
    """闸执行上下文：变更请求 + 工具注册表。"""

    request_id: int
    nim: dict
    devices: list[dict]
    configs: dict[str, str]  # device_name -> config text
    assertions: list[dict]
    tools: Any  # ToolRegistry


class Gate(Protocol):
    """三道闸统一接口。"""

    name: str

    async def execute(self, ctx: GateContext) -> GateResult:
        ...
