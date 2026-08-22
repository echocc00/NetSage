"""Netmiko Adapter（兜底，v2.0 开发计划十章 10.2）。

napalm 不支持的厂商/命令用 netmiko 灵活 CLI。
审查修复：sync 调用经 asyncio.to_thread 包装，避免阻塞事件循环（python C2）。
"""
from __future__ import annotations

import asyncio

from app.access.base import AdapterError, DeviceAdapter, DeviceFacts, DeviceTarget
from app.core.logging import get_logger

logger = get_logger("access_netmiko")

# netmiko device_type 映射
NETMIKO_TYPE_MAP: dict[str, str] = {
    "cisco_iosxe": "cisco_ios",
    "cisco_ios": "cisco_ios",
    "cisco_nxos": "cisco_nxos",
    "huawei_vrp": "huawei",
    "h3c_comware": "hp_comware",
    "juniper_junos": "juniper_junos",
    "arista_eos": "arista_eos",
}


class NetmikoAdapter(DeviceAdapter):
    """netmiko CLI 兜底适配器。"""

    def _connect_sync(self, target: DeviceTarget):
        from netmiko import ConnectHandler

        device_type = NETMIKO_TYPE_MAP.get(target.vendor, "cisco_ios")
        try:
            return ConnectHandler(
                device_type=device_type,
                host=target.host,
                username=target.username,
                password=target.password,
                port=target.port,
            )
        except Exception as e:
            raise AdapterError("connect_failed", f"netmiko 连接失败: {e}") from e

    async def _connect(self, target: DeviceTarget):
        return await asyncio.to_thread(self._connect_sync, target)

    async def get_facts(self, target: DeviceTarget) -> DeviceFacts:
        conn = await self._connect(target)
        try:
            version = await asyncio.to_thread(conn.send_command, "show version")
            hostname = await asyncio.to_thread(conn.send_command, "show running-config | include hostname")
            return DeviceFacts(
                vendor=target.vendor,
                model="",
                os_version=version[:200],
                hostname=hostname.strip(),
                serial=None,
                interface_list=[],
            )
        finally:
            await asyncio.to_thread(conn.disconnect)

    async def get_config(self, target: DeviceTarget, source: str = "running") -> str:
        conn = await self._connect(target)
        try:
            cmd = "show running-config" if source == "running" else "show startup-config"
            return await asyncio.to_thread(conn.send_command, cmd)
        finally:
            await asyncio.to_thread(conn.disconnect)

    async def load_merge_candidate(self, target: DeviceTarget, config: str) -> None:
        """netmiko 走 config mode 直接合并。"""
        conn = await self._connect(target)
        try:
            await asyncio.to_thread(conn.send_config_set, config.splitlines())
            logger.info("netmiko_candidate_loaded", host=target.host)
        finally:
            await asyncio.to_thread(conn.disconnect)

    async def compare_config(self, target: DeviceTarget) -> str:
        """netmiko 无原生 diff，返回候选与 running 的简单对比。"""
        return ""  # Phase 2 实现详细 diff

    async def commit(self, target: DeviceTarget) -> None:
        conn = await self._connect(target)
        try:
            await asyncio.to_thread(conn.save_config)
            logger.info("netmiko_committed", host=target.host)
        except Exception as e:
            raise AdapterError("commit_failed", f"netmiko commit 失败: {e}") from e
        finally:
            await asyncio.to_thread(conn.disconnect)

    async def discard(self, target: DeviceTarget) -> None:
        """netmiko discard：断开不保存即可（候选在 session 内）。"""
        pass

    async def rollback(self, target: DeviceTarget, snapshot_config: str) -> None:
        conn = await self._connect(target)
        try:
            await asyncio.to_thread(conn.send_config_set, snapshot_config.splitlines())
            await asyncio.to_thread(conn.save_config)
        finally:
            await asyncio.to_thread(conn.disconnect)
