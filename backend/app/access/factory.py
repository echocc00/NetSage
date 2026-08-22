"""设备接入工厂（v2.0 开发计划十章 10.2）。

按厂商 + 场景选择最优 adapter：
- 主路径（commit/rollback/diff）→ napalm
- napalm 不支持的厂商/命令 → netmiko
- 大批量采集 → scrapli
"""
from __future__ import annotations

from app.access.base import DeviceAdapter, DeviceTarget, NAPALM_DRIVER_MAP
from app.access.napalm_adapter import NapalmAdapter
from app.access.netmiko_adapter import NetmikoAdapter, NETMIKO_TYPE_MAP
from app.access.scrapli_adapter import ScrapliAdapter
from app.core.logging import get_logger

logger = get_logger("access_factory")


class AdapterFactory:
    """按需选择设备 adapter。"""

    def __init__(self) -> None:
        self._napalm = NapalmAdapter()
        self._netmiko = NetmikoAdapter()
        self._scrapli = ScrapliAdapter()

    def for_write(self, target: DeviceTarget) -> DeviceAdapter:
        """写操作优先 napalm（commit/rollback 最成熟）。"""
        if target.vendor in NAPALM_DRIVER_MAP:
            return self._napalm
        logger.warning("adapter_fallback_netmiko", vendor=target.vendor)
        return self._netmiko

    def for_read(self, target: DeviceTarget) -> DeviceAdapter:
        """读操作优先 napalm，不支持回退 netmiko。"""
        if target.vendor in NAPALM_DRIVER_MAP:
            return self._napalm
        return self._netmiko

    def for_batch(self, target: DeviceTarget) -> DeviceAdapter:
        """批量采集用 scrapli（异步高并发）。"""
        return self._scrapli

    def for_cli(self, target: DeviceTarget) -> DeviceAdapter:
        """灵活 CLI 场景用 netmiko。"""
        return self._netmiko


_factory: AdapterFactory | None = None


def get_adapter_factory() -> AdapterFactory:
    global _factory
    if _factory is None:
        _factory = AdapterFactory()
    return _factory
