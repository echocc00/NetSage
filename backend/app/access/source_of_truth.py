"""Source of Truth 抽象（v2.0 三章 + 开发计划十八章 18.1）。

统一接口适配 NetBox（Phase 2 包装）与 Nautobot（Phase 3 集成）。
所有 Agent 通过此接口读写网络资产/拓扑/IPAM，不直接耦合具体 SSoT。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class Device:
    """设备模型（跨 SSoT 统一）。"""
    id: int
    name: str
    vendor: str           # huawei / cisco / h3c / juniper / arista
    os: str               # vrp / iosxe / comware / junos / eos
    model: str
    version: str
    mgmt_ip: str
    role: str             # spine / leaf / pe / ce / ...
    site: str = ""
    status: str = "active"
    metadata: dict = field(default_factory=dict)


@dataclass
class Topology:
    """拓扑（React Flow 友好格式）。"""
    nodes: list[dict]     # [{id, name, role, vendor, mgmt_ip, ...}]
    edges: list[dict]     # [{id, source, target, src_iface, dst_iface}]


@dataclass
class IPAM:
    """IP 地址管理。"""
    prefix: str
    family: int           # 4 / 6
    description: str = ""
    status: str = "active"
    assigned_to: str = ""


@dataclass
class VRF:
    name: str
    rd: str = ""
    route_targets: list[str] = field(default_factory=list)


@dataclass
class ChangeRecord:
    """变更记录（回写 SSoT）。"""
    change_id: int
    device_id: int
    action: str           # deploy / rollback / audit
    status: str           # success / failed / rolled_back
    config_hash: str = ""
    timestamp: str = ""


class SourceOfTruth(Protocol):
    """网络资产/拓扑/IPAM 单一事实源（v2.0 三章）。"""

    # ===== 读 =====
    async def get_device(self, device_id: int) -> Device: ...
    async def list_devices(self, filter: dict | None = None) -> list[Device]: ...
    async def get_topology(self, scope: str) -> Topology: ...
    async def get_ipam(self, prefix: str) -> IPAM: ...
    async def get_vrfs(self, project: str) -> list[VRF]: ...

    # ===== 写（变更后回写） =====
    async def write_change_record(self, record: ChangeRecord) -> None: ...
    async def update_device_status(self, device_id: int, status: str) -> None: ...


class SSoTError(Exception):
    """SourceOfTruth 操作错误。"""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


class NullSSoT:
    """空实现（Phase 1 兼容 / 测试用 / SSoT 不可用时降级）。"""

    async def get_device(self, device_id: int) -> Device:
        raise SSoTError("not_configured", "SourceOfTruth 未配置")

    async def list_devices(self, filter: dict | None = None) -> list[Device]:
        return []

    async def get_topology(self, scope: str) -> Topology:
        return Topology(nodes=[], edges=[])

    async def get_ipam(self, prefix: str) -> IPAM:
        raise SSoTError("not_configured", "SourceOfTruth 未配置")

    async def get_vrfs(self, project: str) -> list[VRF]:
        return []

    async def write_change_record(self, record: ChangeRecord) -> None:
        pass

    async def update_device_status(self, device_id: int, status: str) -> None:
        pass


_ssot: SourceOfTruth | None = None


def get_ssot() -> SourceOfTruth:
    """获取全局 SSoT 实例（应用启动时注入）。"""
    global _ssot
    if _ssot is None:
        return NullSSoT()
    return _ssot


def configure_ssot(ssot: SourceOfTruth) -> None:
    """注入全局 SSoT（lifespan startup 调用）。"""
    global _ssot
    _ssot = ssot


def get_source_of_truth(provider: str = "netbox") -> SourceOfTruth:
    """工厂：按 provider 切换 NetBox / Nautobot 双适配器（v2.0 三章）。

    - netbox：NetBoxAdapter（真实 REST）
    - nautobot：NautobotAdapter（mock 模式默认，不部署服务）
    - null：NullSSoT（未配置）
    """
    from app.core.config import get_settings

    settings = get_settings()
    if provider == "nautobot":
        from app.access.nautobot_adapter import NautobotAdapter
        return NautobotAdapter(
            base_url=settings.nautobot_url,
            token=settings.nautobot_token,
            mock=settings.nautobot_mock,
        )
    if provider == "netbox" and settings.netbox_url:
        from app.access.netbox_adapter import NetBoxAdapter
        return NetBoxAdapter(base_url=settings.netbox_url, token=settings.netbox_token)
    return NullSSoT()
