"""Scrapli Adapter（高并发采集，v2.0 开发计划十章 10.2）。

大批量设备采集用 scrapli（异步性能优于 netmiko）。
Phase 2 接入，Phase 1 占位。
"""
from __future__ import annotations

from app.access.base import DeviceAdapter, DeviceFacts, DeviceTarget
from app.core.logging import get_logger

logger = get_logger("access_scrapli")

# scrapli platform 映射
SCRAPLI_PLATFORM_MAP: dict[str, str] = {
    "cisco_iosxe": "cisco_iosxe",
    "cisco_ios": "cisco_iosxe",
    "cisco_nxos": "cisco_nxos",
    "huawei_vrp": "huawei_vrp",
    "juniper_junos": "juniper_junos",
    "arista_eos": "arista_eos",
}


class ScrapliAdapter(DeviceAdapter):
    """scrapli 高并发采集适配器（Phase 2 完整实现）。

    Phase 1：仅 get_facts/get_config 占位，批量采集场景用。
    """

    async def get_facts(self, target: DeviceTarget) -> DeviceFacts:
        from scrapli.driver import AsyncDriver

        platform = SCRAPLI_PLATFORM_MAP.get(target.vendor, "cisco_iosxe")
        driver = AsyncDriver(
            host=target.host,
            auth_username=target.username,
            auth_password=target.password,
            auth_port=target.port,
            platform=platform,
        )
        await driver.open()
        try:
            version_resp = await driver.send_command("show version")
            facts = _parse_facts(version_resp.result, target)
            logger.info("scrapli_facts", host=target.host)
            return facts
        finally:
            await driver.close()

    async def get_config(self, target: DeviceTarget, source: str = "running") -> str:
        from scrapli.driver import AsyncDriver

        platform = SCRAPLI_PLATFORM_MAP.get(target.vendor, "cisco_iosxe")
        driver = AsyncDriver(
            host=target.host,
            auth_username=target.username,
            auth_password=target.password,
            auth_port=target.port,
            platform=platform,
        )
        await driver.open()
        try:
            cmd = "show running-config" if source == "running" else "show startup-config"
            resp = await driver.send_command(cmd)
            return resp.result
        finally:
            await driver.close()

    async def load_merge_candidate(self, target: DeviceTarget, config: str) -> None:
        raise NotImplementedError("scrapli 候选加载 Phase 2 实现")

    async def compare_config(self, target: DeviceTarget) -> str:
        raise NotImplementedError

    async def commit(self, target: DeviceTarget) -> None:
        raise NotImplementedError("scrapli 写操作 Phase 2 实现，主路径用 napalm")

    async def discard(self, target: DeviceTarget) -> None:
        raise NotImplementedError

    async def rollback(self, target: DeviceTarget, snapshot_config: str) -> None:
        raise NotImplementedError


def _parse_facts(version_output: str, target: DeviceTarget) -> DeviceFacts:
    """解析 show version 输出（简化版）。"""
    return DeviceFacts(
        vendor=target.vendor,
        model="",
        os_version=version_output[:200],
        hostname=target.name,
        serial=None,
        interface_list=[],
    )
