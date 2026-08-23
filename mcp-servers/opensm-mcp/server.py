"""OpenSM MCP Server（Phase 4 RDMA 专项，v2.0 二十一章 GPL 法务隔离）。

进程外调用 OpenSM，满足 GPL mere aggregation 隔离：
- 不链接 OpenSM 库（仅 subprocess）
- 不分发 OpenSM 二进制（用户本机拉取官方镜像）
- 不修改 OpenSM 源码

mock 模式（OPENSM_MOCK=true，默认）：返回种子数据，无 IB 硬件也可开发。
真实模式：subprocess 调用 ibstat/ibdiscover/perfquery。

工具：ibstat / ibdiscover / perfquery / ibnetdiscover / sminfo
"""
from __future__ import annotations

import asyncio
import os
from typing import Any

from mcp.server.fastmcp import FastMCP

from netsage_mcp_shared import MCPError, log

mcp = FastMCP("opensm-mcp")

OPENSM_MOCK = os.getenv("OPENSM_MOCK", "true").lower() == "true"


# ===== mock 种子数据（模拟 2 节点 4 端口 IB fabric）=====

_MOCK_IBSTAT = {
    "node": "spine01-rdma",
    "guid": "0x248a070300c0a1e0",
    "ports": [
        {"port": 1, "state": "Active", "rate": "100 Gb/s (4X EDR)", "lid": 1, "guid": "0x..."},
        {"port": 2, "state": "Active", "rate": "100 Gb/s (4X EDR)", "lid": 1, "guid": "0x..."},
        {"port": 3, "state": "Down", "rate": "—", "lid": 0, "guid": "0x..."},
        {"port": 4, "state": "Active", "rate": "100 Gb/s (4X EDR)", "lid": 1, "guid": "0x..."},
    ],
}

_MOCK_IBDISCOVER = {
    "nodes": [
        {"lid": 1, "name": "spine01-rdma", "type": "switch", "ports": 32},
        {"lid": 10, "name": "gpu-node-01", "type": "ca", "ports": 4},
        {"lid": 11, "name": "gpu-node-02", "type": "ca", "ports": 4},
    ],
    "links": [
        {"from": "spine01-rdma:1", "to": "gpu-node-01:1", "rate": "100 Gb/s"},
        {"from": "spine01-rdma:2", "to": "gpu-node-01:2", "rate": "100 Gb/s"},
        {"from": "spine01-rdma:3", "to": "gpu-node-02:1", "rate": "100 Gb/s"},
        {"from": "spine01-rdma:4", "to": "gpu-node-02:2", "rate": "100 Gb/s"},
    ],
}

_MOCK_PERFQUERY = {
    "lid": 1,
    "port": 1,
    "counters": {
        "xmit_data": "1234567890",
        "rcv_data": "1234567000",
        "xmit_pkts": "5678901",
        "rcv_pkts": "5678900",
        "symbol_errors": 0,
        "link_err_recover": 0,
        "link_downed": 0,
        "port_rcv_errors": 12,
        "port_rcv_remote_physical_errors": 0,
        "port_rcv_switch_relay_errors": 0,
        "port_xmit_discards": 5,
        "port_xmit_constraint_errors": 0,
        "port_rcv_constraint_errors": 0,
        "vl15_dropped": 0,
        "excessive_buffer_overrun_errors": 0,
    },
}

_MOCK_SMINFO = {
    "sm_guid": "0x248a070300c0a1e0",
    "sm_lid": 1,
    "sm_state": "Active",
    "priority": 0,
    "activity_count": 12345,
}


async def _run_cli(cmd: str, *args: str) -> dict:
    """subprocess 调用 OpenSM CLI（真实模式，GPL 进程外隔离）。"""
    proc = await asyncio.create_subprocess_exec(
        cmd, *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise MCPError("cli_error", f"{cmd} 失败: {stderr.decode()[:200]}")
    return {"output": stdout.decode()[:4000]}


@mcp.tool()
async def ibstat() -> dict:
    """查询 IB HCA 端口状态（state/rate/LID/GUID）。"""
    if OPENSM_MOCK:
        log.info("opensm_ibstat_mock")
        return _MOCK_IBSTAT
    result = await _run_cli("ibstat")
    return {"raw": result["output"]}


@mcp.tool()
async def ibdiscover() -> dict:
    """发现 IB 拓扑（节点 + 链路）。"""
    if OPENSM_MOCK:
        log.info("opensm_ibdiscover_mock", nodes=len(_MOCK_IBDISCOVER["nodes"]))
        return _MOCK_IBDISCOVER
    result = await _run_cli("ibdiscover")
    return {"raw": result["output"]}


@mcp.tool()
async def perfquery(lid: int = 1, port: int = 1) -> dict:
    """查询端口性能计数器（丢包/CRC/错误）。"""
    if OPENSM_MOCK:
        log.info("opensm_perfquery_mock", lid=lid, port=port)
        data = dict(_MOCK_PERFQUERY)
        data["lid"] = lid
        data["port"] = port
        return data
    result = await _run_cli("perfquery", str(lid), str(port))
    return {"raw": result["output"]}


@mcp.tool()
async def ibnetdiscover() -> dict:
    """完整 IB 网络拓扑发现。"""
    if OPENSM_MOCK:
        return _MOCK_IBDISCOVER
    result = await _run_cli("ibnetdiscover")
    return {"raw": result["output"]}


@mcp.tool()
async def sminfo() -> dict:
    """子网管理器（SM）状态。"""
    if OPENSM_MOCK:
        return _MOCK_SMINFO
    result = await _run_cli("sminfo")
    return {"raw": result["output"]}


if __name__ == "__main__":
    mcp.run(transport="stdio")
