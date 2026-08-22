"""SUZIEQ MCP Server（v2.0 三章 + 开发计划十八章 18.2）。

包装 SUZIEQ poller + analyzer 为 MCP 工具，供 ObserverAgent/Troubleshooter 调用。
SUZIEQ Docker 后续启动（W3），MCP 代码先就绪。

工具：poll_once / query_state / assert_state / get_path
"""
from __future__ import annotations

import asyncio
import os
from typing import Any

from mcp.server.fastmcp import FastMCP

from netsage_mcp_shared import MCPError, log

mcp = FastMCP("suzieq-mcp")

SUZIEQ_CONFIG = os.getenv("SUZIEQ_CONFIG", "")  # suzieq 配置路径（设备清单 + 凭证）
SUZIEQ_BIN = os.getenv("SUZIEQ_BIN", "suzieq")


async def _run_suzieq(args: list[str]) -> str:
    """异步执行 suzieq CLI（sync 库，to_thread 包装）。"""
    cmd = [SUZIEQ_BIN] + args
    log.info("suzieq_exec", cmd=" ".join(cmd))
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise MCPError("suzieq_failed", f"suzieq 执行失败: {stderr.decode()[:200]}")
    return stdout.decode()


@mcp.tool()
async def poll_once() -> dict:
    """触发一次全量采集（suzieq poller），返回采集摘要。"""
    if not SUZIEQ_CONFIG:
        raise MCPError("not_configured", "SUZIEQ_CONFIG 未配置")
    output = await _run_suzieq(["poller", "-c", SUZIEQ_CONFIG])
    log.info("suzieq_polled", output_len=len(output))
    return {"status": "polled", "raw": output[:500]}


@mcp.tool()
async def query_state(table: str, filter: str = "") -> dict:
    """查询标准化状态表（bgp/ospf/interface/routes/...）。

    Args:
        table: 状态表名（bgp/ospf/interface/routes/vlan/...）
        filter: 过滤条件（SUZIEQ SQL-like，如 "hostname='spine01'"）
    """
    args = ["analyze", "table", table, "--format", "json"]
    if filter:
        args += ["--filter", filter]
    output = await _run_suzieq(args)
    log.info("suzieq_queried", table=table, filter=filter)
    return {"table": table, "filter": filter, "rows": output[:2000]}


@mcp.tool()
async def assert_state(assertion: str) -> dict:
    """SUZIEQ Assert 框架：配置 vs 状态断言。

    Args:
        assertion: 断言名（如 "bgp-assert" / "ospf-assert" / "interfaces-assert"）
    """
    output = await _run_suzieq(["assert", "--name", assertion, "--format", "json"])
    log.info("suzieq_asserted", assertion=assertion)
    # SUZIEQ assert 输出 pass/fail 列表
    return {"assertion": assertion, "result": output[:2000]}


@mcp.tool()
async def get_path(src: str, dst: str) -> dict:
    """端到端路径追踪（suzieq path tracing）。

    Args:
        src: 源设备/接口
        dst: 目标设备/接口
    """
    output = await _run_suzieq(["path", "--src", src, "--dest", dst, "--format", "json"])
    log.info("suzieq_path", src=src, dst=dst)
    return {"src": src, "dst": dst, "path": output[:2000]}


if __name__ == "__main__":
    mcp.run(transport="stdio")