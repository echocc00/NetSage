"""NetBox MCP Server（v2.0 三章 🟡 包装 + 开发计划九章）。

包装 NetBox v4 REST API 为 MCP 工具，供 Agent + 外部客户端（Claude/Cursor）调用。
后端的 NetBoxAdapter 是拓扑 API 的快速路径（少一层），Agent 走 MCP 统一架构。

工具：get_device / list_devices / get_topology / get_ipam / write_change_record
"""
from __future__ import annotations

import os
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

from netsage_mcp_shared import MCPError, log

mcp = FastMCP("netbox-mcp")

NETBOX_URL = os.getenv("NETBOX_URL", "http://netbox:8000")
NETBOX_TOKEN = os.getenv("NETBOX_TOKEN", "")


def _client() -> httpx.AsyncClient:
    if not NETBOX_TOKEN:
        raise MCPError("not_configured", "NETBOX_TOKEN 未配置")
    return httpx.AsyncClient(
        base_url=NETBOX_URL.rstrip("/"),
        headers={"Authorization": f"Token {NETBOX_TOKEN}"},
        timeout=30.0,
    )


@mcp.tool()
async def get_device(device_id: int) -> dict:
    """获取设备详情（NetBox dcim/devices）。"""
    async with _client() as c:
        r = await c.get(f"/api/dcim/devices/{device_id}/")
        if r.status_code == 404:
            raise MCPError("not_found", f"设备 {device_id} 不存在")
        r.raise_for_status()
        log.info("netbox_get_device", device_id=device_id)
        return r.json()


@mcp.tool()
async def list_devices(site: str | None = None, role: str | None = None) -> dict:
    """列出设备（可按 site/role 过滤）。"""
    params: dict[str, Any] = {}
    if site:
        params["site"] = site
    if role:
        params["role"] = role
    async with _client() as c:
        r = await c.get("/api/dcim/devices/", params=params)
        r.raise_for_status()
        data = r.json()
        log.info("netbox_list_devices", count=len(data.get("results", [])))
        return {"count": data.get("count", 0), "devices": data.get("results", [])}


@mcp.tool()
async def get_topology(scope: str) -> dict:
    """拉取站点拓扑（设备 + 线缆，React Flow 格式）。"""
    async with _client() as c:
        # 设备
        dev_resp = await c.get("/api/dcim/devices/", params={"site": scope})
        dev_resp.raise_for_status()
        devices = dev_resp.json().get("results", [])
        # 线缆
        cab_resp = await c.get("/api/dcim/cables/", params={"site": scope})
        cab_resp.raise_for_status()
        cables = cab_resp.json().get("results", [])

        nodes = [
            {
                "id": str(d["id"]),
                "name": d["name"],
                "role": (d.get("role") or {}).get("name", ""),
                "model": (d.get("device_type") or {}).get("model", ""),
                "mgmt_ip": (d.get("primary_ip4") or {}).get("address", ""),
            }
            for d in devices
        ]
        edges = [
            {"id": str(c["id"]), "source": c.get("a_terminations", [{}])[0], "target": c.get("b_terminations", [{}])[0]}
            for c in cables
        ]
        log.info("netbox_topology", scope=scope, nodes=len(nodes), edges=len(edges))
        return {"scope": scope, "nodes": nodes, "edges": edges}


@mcp.tool()
async def get_ipam(prefix: str) -> dict:
    """查询 IPAM 前缀。"""
    async with _client() as c:
        r = await c.get("/api/ipam/prefixes/", params={"prefix": prefix})
        r.raise_for_status()
        results = r.json().get("results", [])
        if not results:
            raise MCPError("not_found", f"前缀 {prefix} 不存在")
        return results[0]


@mcp.tool()
async def write_change_record(
    device_id: int, change_id: int, action: str, status: str, config_hash: str = ""
) -> dict:
    """变更记录回写 NetBox（journal entry）。"""
    async with _client() as c:
        r = await c.post(
            f"/api/dcim/devices/{device_id}/journal-entries/",
            json={
                "assigned_object_type": "dcim.device",
                "assigned_object_id": device_id,
                "kind": "info",
                "comment": f"[NetSage] change={change_id} action={action} status={status} hash={config_hash[:12]}",
            },
        )
        r.raise_for_status()
        log.info("netbox_change_recorded", device=device_id, change=change_id)
        return {"status": "recorded", "device_id": device_id}


if __name__ == "__main__":
    mcp.run(transport="stdio")