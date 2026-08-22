"""NAPALM MCP Server（v2.0 开发计划九章 9.2）。

工具：get_facts / get_config / load_merge_candidate / compare_config / commit / discard
多厂商统一抽象（厂商翻译器，v2.0 三章）。
"""
from __future__ import annotations

import os
from typing import Any

from fastmcp import FastMCP
from napalm import get_network_driver

from netsage_mcp_shared import MCPError, log

mcp = FastMCP("napalm-mcp")

# Phase 1 支持的厂商 driver 映射
DRIVER_MAP: dict[str, str] = {
    "cisco_iosxe": "iosxe",
    "cisco_ios": "ios",
    "cisco_nxos": "nxos_ssh",
    "huawei_vrp": "huawei",
    "h3c_comware": "h3c",
    "juniper_junos": "junos",
    "arista_eos": "eos",
}


def _connect(vendor: str, host: str, username: str, password: str, port: int = 22) -> Any:
    """建立 NAPALM 连接。凭证由调用方注入（生产态走 Vault）。"""
    driver_name = DRIVER_MAP.get(vendor)
    if not driver_name:
        raise MCPError("unsupported_vendor", f"不支持的厂商: {vendor}", list(DRIVER_MAP))
    try:
        driver = get_network_driver(driver_name)
        device = driver(hostname=host, username=username, password=password, optional_args={"port": port})
        device.open()
        return device
    except Exception as e:
        raise MCPError("connect_failed", f"连接设备 {host} 失败: {e}") from e


@mcp.tool()
async def get_facts(vendor: str, host: str, username: str, password: str, port: int = 22) -> dict:
    """获取设备 facts（厂商/型号/版本/接口）。"""
    device = _connect(vendor, host, username, password, port)
    try:
        facts = device.get_facts()
        log.info("napalm_get_facts", host=host, vendor=facts.get("vendor"))
        return {
            "host": host,
            "vendor": facts.get("vendor"),
            "model": facts.get("model"),
            "os_version": facts.get("os_version"),
            "hostname": facts.get("hostname"),
            "serial_number": facts.get("serial_number"),
            "interface_list": facts.get("interface_list", []),
        }
    finally:
        device.close()


@mcp.tool()
async def get_config(vendor: str, host: str, username: str, password: str, source: str = "running", port: int = 22) -> dict:
    """获取设备配置（running/startup/candidate）。"""
    device = _connect(vendor, host, username, password, port)
    try:
        config = device.get_config(retrieve=source)
        log.info("napalm_get_config", host=host, source=source)
        return {"host": host, "source": source, "config": config.get(source, "")}
    finally:
        device.close()


@mcp.tool()
async def load_merge_candidate(
    vendor: str, host: str, username: str, password: str, config: str, port: int = 22
) -> dict:
    """加载合并候选配置（不提交，供 compare_config 用）。"""
    device = _connect(vendor, host, username, password, port)
    try:
        device.load_merge_candidate(config=config)
        log.info("napalm_load_candidate", host=host)
        return {"host": host, "status": "candidate_loaded"}
    finally:
        device.close()


@mcp.tool()
async def compare_config(vendor: str, host: str, username: str, password: str, port: int = 22) -> dict:
    """对比 candidate 与 running，返回 diff。"""
    device = _connect(vendor, host, username, password, port)
    try:
        diff = device.compare_config()
        log.info("napalm_compare", host=host, diff_len=len(diff))
        return {"host": host, "diff": diff}
    finally:
        device.close()


@mcp.tool()
async def commit(vendor: str, host: str, username: str, password: str, port: int = 22) -> dict:
    """提交候选配置（写操作，必须经三道闸 + 审批，v2.0 十章）。"""
    device = _connect(vendor, host, username, password, port)
    try:
        device.commit_config()
        log.info("napalm_commit", host=host)
        return {"host": host, "status": "committed"}
    except Exception as e:
        raise MCPError("commit_failed", f"commit 失败: {e}") from e
    finally:
        device.close()


@mcp.tool()
async def discard(vendor: str, host: str, username: str, password: str, port: int = 22) -> dict:
    """丢弃候选配置。"""
    device = _connect(vendor, host, username, password, port)
    try:
        device.discard_config()
        log.info("napalm_discard", host=host)
        return {"host": host, "status": "discarded"}
    finally:
        device.close()


if __name__ == "__main__":
    mcp.run(transport="stdio")
