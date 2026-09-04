"""设备接入层抽象（v2.0 开发计划十章 10.1）。

DeviceAdapter 协议统一 get_facts/get_config/load_merge/commit/rollback。
三实现：napalm（主）/ netmiko（兜底）/ scrapli（高并发采集）。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass
class DeviceFacts:
    vendor: str
    model: str
    os_version: str
    hostname: str
    serial: str | None
    interface_list: list[str]


@dataclass
class DeviceTarget:
    """设备连接目标。凭证从 Vault 取，不落明文。"""
    id: int
    name: str
    vendor: str          # cisco_iosxe / huawei_vrp / ...
    host: str
    username: str
    password: str        # Vault 注入，用后即弃
    port: int = 22
    os: str = ""         # iosxe / vrp / ...

    @property
    def napalm_driver(self) -> str:
        """vendor → napalm driver 名。"""
        return NAPALM_DRIVER_MAP.get(self.vendor, self.vendor)


NAPALM_DRIVER_MAP: dict[str, str] = {
    "cisco_iosxe": "iosxe",
    "cisco_ios": "ios",
    "cisco_nxos": "nxos_ssh",
    "huawei_vrp": "huawei",
    "h3c_comware": "h3c",
    "juniper_junos": "junos",
    "arista_eos": "eos",
}


class DeviceAdapter(Protocol):
    """设备接入统一接口（v2.0 十章 10.1）。"""

    async def get_facts(self, target: DeviceTarget) -> DeviceFacts: ...
    async def get_config(self, target: DeviceTarget, source: str = "running") -> str: ...
    async def load_merge_candidate(self, target: DeviceTarget, config: str) -> None: ...
    async def compare_config(self, target: DeviceTarget) -> str: ...
    async def commit(self, target: DeviceTarget) -> None: ...
    async def discard(self, target: DeviceTarget) -> None: ...
    async def rollback(self, target: DeviceTarget, snapshot_config: str) -> None: ...


class AdapterError(Exception):
    """设备接入错误。"""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)
