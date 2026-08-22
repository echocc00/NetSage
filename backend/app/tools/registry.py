"""工具注册表接口（v2.0 开发计划九章 9.3）。

Agent 和 Gate 通过此接口调用 MCP server，统一过脱敏拦截器。
Phase 1 W3 提供接口 + mock 实现；W5 接真实 MCP client。
"""
from __future__ import annotations

import inspect
from typing import Any, Protocol


class ToolRegistry(Protocol):
    """工具调用统一入口。实现需在调用前后过脱敏（v2.0 二十章）。"""

    async def invoke(self, tool_name: str, **kwargs: Any) -> Any:
        """调用 MCP 工具，返回结果。

        tool_name 格式："<server>.<tool>"，如 "napalm.get_facts"
        """
        ...


class MockToolRegistry:
    """内存 mock，供 #10 三道闸引擎在 #3 Agent 编排完成前联调。

    支持 sync 和 async callable stub（Phase 2 P2-8 测试需要 async 失败模拟）。
    """

    def __init__(self) -> None:
        self._responses: dict[str, Any] = {}
        self._calls: list[tuple[str, dict]] = []

    def stub(self, tool_name: str, response: Any) -> None:
        """注册工具的预设响应（支持值、sync callable、async callable）。"""
        self._responses[tool_name] = response

    async def invoke(self, tool_name: str, **kwargs: Any) -> Any:
        self._calls.append((tool_name, kwargs))
        if tool_name in self._responses:
            resp = self._responses[tool_name]
            if callable(resp):
                result = resp(**kwargs)
                if inspect.isawaitable(result):
                    result = await result
                return result
            return resp
        return {"status": "ok", "tool": tool_name, "mocked": True}

    @property
    def calls(self) -> list[tuple[str, dict]]:
        return self._calls
