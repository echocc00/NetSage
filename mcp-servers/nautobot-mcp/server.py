"""Nautobot MCP Server（v2.0 三章 双适配器 + Phase 3 自研 App v0.1）。

包装 Nautobot REST + 自研 NetworkDesign App。Phase 3 决策：不部署 Nautobot 服务，
mock 模式返回种子数据。未来部署 Nautobot 后切换 NAUTOBOT_MOCK=false 即走真实 REST。

工具：
- get_device / list_devices / get_topology / get_ipam（与 netbox-mcp 对齐）
- save_design / list_designs（自研 App v0.1，NetworkDesign 持久化）
"""
from __future__ import annotations

import os
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

from netsage_mcp_shared import MCPError, log

mcp = FastMCP("nautobot-mcp")

NAUTOBOT_URL = os.getenv("NAUTOBOT_URL", "http://nautobot:8000")
NAUTOBOT_TOKEN = os.getenv("NAUTOBOT_TOKEN", "")
NAUTOBOT_MOCK = os.getenv("NAUTOBOT_MOCK", "true").lower() == "true"

# mock 种子设备（与 NautobotAdapter 对齐）
_MOCK_DEVICES = [
    {"id": 1, "name": "spine01", "vendor": "huawei", "os": "vrp", "model": "CE12800",
     "mgmt_ip": "10.1.1.1", "role": "spine", "site": "shanghai", "status": "active"},
    {"id": 2, "name": "spine02", "vendor": "huawei", "os": "vrp", "model": "CE12800",
     "mgmt_ip": "10.1.1.2", "role": "spine", "site": "shanghai", "status": "active"},
    {"id": 3, "name": "leaf01", "vendor": "cisco", "os": "iosxe", "model": "Catalyst 9300",
     "mgmt_ip": "10.1.2.1", "role": "leaf", "site": "shanghai", "status": "active"},
    {"id": 4, "name": "leaf02", "vendor": "h3c", "os": "comware", "model": "S6520",
     "mgmt_ip": "10.1.2.2", "role": "leaf", "site": "beijing", "status": "active"},
    {"id": 5, "name": "leaf03", "vendor": "arista", "os": "eos", "model": "7050X3",
     "mgmt_ip": "10.1.2.3", "role": "leaf", "site": "beijing", "status": "active"},
]

# NetworkDesign 持久化存储（mock：内存；真实：Nautobot App model）
_DESIGNS: list[dict] = []
_DESIGN_SEQ = [0]


def _client() -> httpx.AsyncClient:
    if not NAUTOBOT_TOKEN and not NAUTOBOT_MOCK:
        raise MCPError("not_configured", "NAUTOBOT_TOKEN 未配置")
    return httpx.AsyncClient(
        base_url=NAUTOBOT_URL.rstrip("/"),
        headers={"Authorization": f"Token {NAUTOBOT_TOKEN}"},
        timeout=30.0,
    )


@mcp.tool()
async def get_device(device_id: int) -> dict:
    """获取设备详情（Nautobot dcim/devices）。"""
    if NAUTOBOT_MOCK:
        for d in _MOCK_DEVICES:
            if d["id"] == device_id:
                return d
        raise MCPError("not_found", f"设备 {device_id} 不存在")
    async with _client() as c:
        r = await c.get(f"/api/dcim/devices/{device_id}/")
        if r.status_code == 404:
            raise MCPError("not_found", f"设备 {device_id} 不存在")
        r.raise_for_status()
        return r.json()


@mcp.tool()
async def list_devices(site: str | None = None, vendor: str | None = None) -> dict:
    """列出设备（可按 site/vendor 过滤）。"""
    if NAUTOBOT_MOCK:
        devices = _MOCK_DEVICES
        if site:
            devices = [d for d in devices if d["site"] == site]
        if vendor:
            devices = [d for d in devices if d["vendor"] == vendor]
        return {"count": len(devices), "devices": devices}
    params: dict[str, Any] = {}
    if site:
        params["site"] = site
    if vendor:
        params["vendor"] = vendor
    async with _client() as c:
        r = await c.get("/api/dcim/devices/", params=params)
        r.raise_for_status()
        data = r.json()
        return {"count": data.get("count", 0), "devices": data.get("results", [])}


@mcp.tool()
async def get_topology(scope: str) -> dict:
    """拉取站点拓扑（设备 + 线缆）。"""
    if NAUTOBOT_MOCK:
        nodes = [{"id": str(d["id"]), "name": d["name"], "role": d["role"],
                  "vendor": d["vendor"], "mgmt_ip": d["mgmt_ip"], "site": d["site"]}
                 for d in _MOCK_DEVICES if d["site"] == scope or scope == "all"]
        return {"scope": scope, "source": "nautobot_mock", "nodes": nodes, "edges": []}
    async with _client() as c:
        dev_resp = await c.get("/api/dcim/devices/", params={"site": scope})
        dev_resp.raise_for_status()
        devices = dev_resp.json().get("results", [])
        nodes = [
            {"id": str(d["id"]), "name": d["name"],
             "role": (d.get("role") or {}).get("name", ""),
             "vendor": (d.get("platform") or {}).get("name", ""),
             "mgmt_ip": (d.get("primary_ip4") or {}).get("address", "")}
            for d in devices
        ]
        return {"scope": scope, "source": "nautobot", "nodes": nodes, "edges": []}


@mcp.tool()
async def get_ipam(prefix: str) -> dict:
    """查询 IPAM 前缀。"""
    if NAUTOBOT_MOCK:
        return {"prefix": prefix, "family": 4, "description": "mock", "status": "active"}
    async with _client() as c:
        r = await c.get("/api/ipam/prefixes/", params={"prefix": prefix})
        r.raise_for_status()
        results = r.json().get("results", [])
        if not results:
            raise MCPError("not_found", f"前缀 {prefix} 不存在")
        return results[0]


@mcp.tool()
async def save_design(
    name: str,
    site: str,
    scenario: str,
    vendor: str,
    hld: str = "{}",
    lld: str = "{}",
    config_diff: str = "",
    rollback_config: str = "",
    lint_passed: bool = False,
    created_by: str = "ai",
) -> dict:
    """保存 AI 网络设计方案到 Nautobot App（NetworkDesign model，自研 App v0.1）。

    mock 模式存内存；真实模式 POST /api/plugins/designs/network-designs/。
    """
    if NAUTOBOT_MOCK:
        _DESIGN_SEQ[0] += 1
        design = {
            "id": _DESIGN_SEQ[0], "name": name, "site": site, "scenario": scenario,
            "vendor": vendor, "hld": hld, "lld": lld, "config_diff": config_diff,
            "rollback_config": rollback_config, "lint_passed": lint_passed,
            "created_by": created_by, "created_at": "2026-08-23T00:00:00Z",
        }
        _DESIGNS.append(design)
        log.info("nautobot_save_design_mock", id=design["id"], name=name)
        return {"status": "saved", "design": design}
    async with _client() as c:
        r = await c.post(
            "/api/plugins/designs/network-designs/",
            json={"name": name, "site": site, "scenario": scenario, "vendor": vendor,
                  "hld": hld, "lld": lld, "config_diff": config_diff,
                  "rollback_config": rollback_config, "lint_passed": lint_passed,
                  "created_by": created_by},
        )
        r.raise_for_status()
        log.info("nautobot_save_design", name=name)
        return {"status": "saved", "design": r.json()}


@mcp.tool()
async def list_designs(site: str | None = None, scenario: str | None = None) -> dict:
    """列出历史设计方案（自研 App v0.1）。"""
    if NAUTOBOT_MOCK:
        designs = _DESIGNS
        if site:
            designs = [d for d in designs if d["site"] == site]
        if scenario:
            designs = [d for d in designs if d["scenario"] == scenario]
        return {"count": len(designs), "designs": designs}
    params: dict[str, Any] = {}
    if site:
        params["site"] = site
    if scenario:
        params["scenario"] = scenario
    async with _client() as c:
        r = await c.get("/api/plugins/designs/network-designs/", params=params)
        r.raise_for_status()
        data = r.json()
        return {"count": data.get("count", 0), "designs": data.get("results", [])}


if __name__ == "__main__":
    mcp.run(transport="stdio")
