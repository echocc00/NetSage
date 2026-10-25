"""经 MCP 协议调用真实 MCP server 的工具注册表（审查 P0 修复）。

此前生产路由就地 new MockToolRegistry 并 stub 全部闸门工具为必过——
三道闸在 HTTP 路径上从未触达真实 containerlab/batfish/napalm。
本模块提供 ToolRegistry 的真实实现：按 "<server>.<tool>" 前缀路由到
各 MCP server（fastmcp streamable-http 客户端）。

会话策略：每次 invoke 建立独立 MCP 会话（正确性优先；napalm 的
candidate 会话原子性由 server 侧复合工具 apply_candidate 保证）。
"""
from __future__ import annotations

import json
from typing import Any

from app.core.logging import get_logger

logger = get_logger("tools_http")


class ToolCallError(RuntimeError):
    """工具调用失败（server 未配置 / 不可达 / 执行报错）。"""


class HttpToolRegistry:
    """真实工具注册表：MCP server 前缀路由 + 每调用独立会话。"""

    def __init__(self, urls: dict[str, str]) -> None:
        # urls: {"napalm": "http://localhost:9003", ...}
        self._urls = {k: v.rstrip("/") for k, v in urls.items() if v}

    @property
    def servers(self) -> list[str]:
        return sorted(self._urls)

    async def invoke(self, tool_name: str, **kwargs: Any) -> Any:
        server, _, tool = tool_name.partition(".")
        if not tool:
            raise ToolCallError(f"工具名缺少 server 前缀: {tool_name!r}")
        base = self._urls.get(server)
        if not base:
            raise ToolCallError(
                f"MCP server '{server}' 未配置（工具 {tool_name}）；已配置: {self.servers}"
            )
        try:
            from fastmcp import Client
        except ImportError as e:  # pragma: no cover - 依赖缺失属部署错误
            raise ToolCallError("fastmcp 未安装，无法走 MCP 通道（pip install fastmcp）") from e

        try:
            async with Client(f"{base}/mcp") as client:
                result = await client.call_tool(tool, kwargs)
        except Exception as e:
            logger.error("mcp_call_failed", tool=tool_name, server=server, error=str(e))
            raise ToolCallError(f"MCP 调用失败 {tool_name}: {e}") from e
        return _unwrap(result, tool_name)


def _unwrap(result: Any, tool_name: str) -> Any:
    """fastmcp CallToolResult → 普通 dict/str（兼容 fastmcp 2.x 与 mcp 原生类型）。"""
    # fastmcp 2.x：.data 是反序列化后的结构化结果
    data = getattr(result, "data", None)
    if data is not None and not isinstance(data, type(None)):
        return data
    content = getattr(result, "content", result)
    if isinstance(content, list) and content:
        first = content[0]
        text = getattr(first, "text", None)
        if isinstance(text, str):
            try:
                return json.loads(text)
            except (TypeError, ValueError):
                return text
        return first
    return content
