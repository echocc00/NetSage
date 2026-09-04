"""NautobotAdapter（v2.0 三章 SourceOfTruth 双适配器）。

Nautobot 与 NetBox 同源 fork，REST API 高度兼容。本适配器：
- mock=True（默认）：内置种子数据，不依赖 Nautobot 服务（Phase 3 决策：不部署服务）
- mock=False：走真实 Nautobot v2 REST（未来部署时切换）

实现与 NetBoxAdapter 同一 SourceOfTruth Protocol，业务层零改切换。
"""
from __future__ import annotations

import httpx

from app.access.source_of_truth import (
    IPAM,
    VRF,
    ChangeRecord,
    Device,
    SourceOfTruth,
    SSoTError,
    Topology,
)
from app.core.logging import get_logger

logger = get_logger("nautobot_adapter")

# Nautobot 厂商映射（与 NetBox 一致，同源 fork）
NAUTOBOT_VENDOR_MAP: dict[str, str] = {
    "cisco": "cisco",
    "huawei": "huawei",
    "h3c": "h3c",
    "juniper": "juniper",
    "arista": "arista",
}

# mock 种子设备（与 NetBox seed_netbox.py 对齐，便于双适配器一致性验证）
_MOCK_DEVICES: list[dict] = [
    {"id": 1, "name": "spine01", "vendor": "huawei", "os": "vrp", "model": "CE12800",
     "version": "8.180", "mgmt_ip": "10.1.1.1", "role": "spine", "site": "shanghai", "status": "active"},
    {"id": 2, "name": "spine02", "vendor": "huawei", "os": "vrp", "model": "CE12800",
     "version": "8.180", "mgmt_ip": "10.1.1.2", "role": "spine", "site": "shanghai", "status": "active"},
    {"id": 3, "name": "leaf01", "vendor": "cisco", "os": "iosxe", "model": "Catalyst 9300",
     "version": "17.6", "mgmt_ip": "10.1.2.1", "role": "leaf", "site": "shanghai", "status": "active"},
    {"id": 4, "name": "leaf02", "vendor": "h3c", "os": "comware", "model": "S6520",
     "version": "7.1", "mgmt_ip": "10.1.2.2", "role": "leaf", "site": "beijing", "status": "active"},
    {"id": 5, "name": "leaf03", "vendor": "arista", "os": "eos", "model": "7050X3",
     "version": "4.30", "mgmt_ip": "10.1.2.3", "role": "leaf", "site": "beijing", "status": "active"},
]

_MOCK_CABLES: list[dict] = [
    {"id": "c1", "source": "spine01", "target": "leaf01", "src_iface": "100GE1/0/1", "dst_iface": "Te1/0/1"},
    {"id": "c2", "source": "spine01", "target": "leaf02", "src_iface": "100GE1/0/2", "dst_iface": "Te1/0/1"},
    {"id": "c3", "source": "spine02", "target": "leaf01", "src_iface": "100GE1/0/1", "dst_iface": "Te1/0/2"},
    {"id": "c4", "source": "spine02", "target": "leaf03", "src_iface": "100GE1/0/2", "dst_iface": "Et1"},
]

_MOCK_IPAM: list[dict] = [
    {"prefix": "10.1.1.0/24", "family": 4, "description": "spine 互联", "status": "active"},
    {"prefix": "10.1.2.0/24", "family": 4, "description": "leaf 管理", "status": "active"},
]

_MOCK_VRFS: list[dict] = [
    {"name": "RDMA_FABRIC", "rd": "65000:100", "route_targets": ["65000:100"]},
]


class NautobotAdapter(SourceOfTruth):
    """Nautobot REST 包装（v2.0 双适配器）。mock 模式不依赖服务。"""

    def __init__(
        self,
        base_url: str = "",
        token: str = "",
        timeout: float = 30.0,
        mock: bool = True,
    ) -> None:
        self.mock = mock
        if mock:
            self.client = None
            logger.info("nautobot_adapter_mock_mode")
        else:
            auth = f"Token {token}"  # Nautobot 用 Token（非 Bearer nbt_）
            self.client = httpx.AsyncClient(
                base_url=base_url.rstrip("/"),
                headers={"Authorization": auth},
                timeout=timeout,
            )

    async def _get(self, path: str, params: dict | None = None) -> dict:
        assert self.client is not None
        try:
            r = await self.client.get(path, params=params)
            r.raise_for_status()
            return r.json()
        except httpx.HTTPStatusError as e:
            raise SSoTError("http_error", f"Nautobot {path} 返回 {e.response.status_code}") from e
        except httpx.RequestError as e:
            raise SSoTError("request_error", f"Nautobot {path} 请求失败: {e}") from e

    # ===== 读 =====

    async def get_device(self, device_id: int) -> Device:
        if self.mock:
            for d in _MOCK_DEVICES:
                if d["id"] == device_id:
                    return self._map_device(d)
            raise SSoTError("not_found", f"设备 {device_id} 不存在")
        data = await self._get(f"/api/dcim/devices/{device_id}/")
        return self._map_device(data)

    async def list_devices(self, filter: dict | None = None) -> list[Device]:
        if self.mock:
            devices = _MOCK_DEVICES
            if filter:
                if "site" in filter:
                    devices = [d for d in devices if d["site"] == filter["site"]]
                if "vendor" in filter:
                    devices = [d for d in devices if d["vendor"] == filter["vendor"]]
            return [self._map_device(d) for d in devices]
        params = filter or {}
        result = await self._get("/api/dcim/devices/", params=params)
        return [self._map_device(d) for d in result.get("results", [])]

    async def get_topology(self, scope: str) -> Topology:
        if self.mock:
            nodes = [
                {"id": str(d["id"]), "name": d["name"], "role": d["role"],
                 "vendor": d["vendor"], "mgmt_ip": d["mgmt_ip"], "site": d["site"]}
                for d in _MOCK_DEVICES if d["site"] == scope or scope == "all"
            ]
            node_names = {n["name"] for n in nodes}
            edges = [
                {"id": c["id"], "source": c["source"], "target": c["target"],
                 "src_iface": c["src_iface"], "dst_iface": c["dst_iface"]}
                for c in _MOCK_CABLES
                if c["source"] in node_names and c["target"] in node_names
            ]
            return Topology(nodes=nodes, edges=edges)
        devices = await self.list_devices({"site": scope})
        nodes = [
            {"id": str(d.id), "name": d.name, "role": d.role,
             "vendor": d.vendor, "mgmt_ip": d.mgmt_ip, "site": d.site}
            for d in devices
        ]
        cables = await self._get("/api/dcim/cables/", params={"site": scope})
        edges = [
            {"id": str(c["id"]),
             "source": c.get("_a_interface", {}).get("device", {}).get("name", ""),
             "target": c.get("_b_interface", {}).get("device", {}).get("name", "")}
            for c in cables.get("results", [])
        ]
        return Topology(nodes=nodes, edges=edges)

    async def get_ipam(self, prefix: str) -> IPAM:
        if self.mock:
            for p in _MOCK_IPAM:
                if p["prefix"] == prefix:
                    return IPAM(**p)
            raise SSoTError("not_found", f"IPAM 前缀 {prefix} 不存在")
        data = await self._get("/api/ipam/prefixes/", params={"prefix": prefix})
        results = data.get("results", [])
        if not results:
            raise SSoTError("not_found", f"IPAM 前缀 {prefix} 不存在")
        p = results[0]
        return IPAM(prefix=p["prefix"], family=p["family"],
                    description=p.get("description", ""),
                    status=p.get("status", {}).get("name", "active"))

    async def get_vrfs(self, project: str) -> list[VRF]:
        if self.mock:
            return [VRF(**v) for v in _MOCK_VRFS]
        data = await self._get("/api/ipam/vrfs/", params={"tenant": project})
        return [
            VRF(name=v["name"], rd=v.get("rd", ""),
                route_targets=[rt["name"] for rt in v.get("import_targets", [])])
            for v in data.get("results", [])
        ]

    # ===== 写 =====

    async def write_change_record(self, record: ChangeRecord) -> None:
        if self.mock:
            logger.info("nautobot_change_recorded_mock", device=record.device_id, change=record.change_id)
            return
        assert self.client is not None
        await self.client.post(
            f"/api/dcim/devices/{record.device_id}/journal-entries/",
            json={
                "assigned_object_type": "dcim.device",
                "assigned_object_id": record.device_id,
                "kind": "info",
                "comment": f"[NetSage] change={record.change_id} action={record.action} status={record.status}",
            },
        )
        logger.info("nautobot_change_recorded", device=record.device_id, change=record.change_id)

    async def update_device_status(self, device_id: int, status: str) -> None:
        if self.mock:
            logger.info("nautobot_status_updated_mock", device=device_id, status=status)
            return
        assert self.client is not None
        await self.client.patch(f"/api/dcim/devices/{device_id}/", json={"status": status})
        logger.info("nautobot_status_updated", device=device_id, status=status)

    # ===== 映射 =====

    def _map_device(self, d: dict) -> Device:
        return Device(
            id=d["id"],
            name=d["name"],
            vendor=d.get("vendor", "unknown"),
            os=d.get("os", ""),
            model=d.get("model", ""),
            version=d.get("version", ""),
            mgmt_ip=d.get("mgmt_ip", ""),
            role=d.get("role", ""),
            site=d.get("site", ""),
            status=d.get("status", "active"),
        )

    async def close(self) -> None:
        if self.client is not None:
            await self.client.aclose()
