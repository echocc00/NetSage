"""NetBoxAdapter（v2.0 三章 🟡 包装决策）。

通过 REST/GraphQL 包装 NetBox v4，实现 SourceOfTruth 协议。
锁 v4 API（v3 不兼容，v2.0 hermes-03 风险）。
"""
from __future__ import annotations

import asyncio
from typing import Any

import httpx

from app.access.source_of_truth import (
    ChangeRecord,
    Device,
    IPAM,
    SSoTError,
    SourceOfTruth,
    Topology,
    VRF,
)
from app.core.logging import get_logger

logger = get_logger("netbox_adapter")

# NetBox vendor → 统一 vendor 名映射
NETBOX_VENDOR_MAP: dict[str, str] = {
    "cisco": "cisco",
    "huawei": "huawei",
    "h3c": "h3c",
    "juniper": "juniper",
    "arista": "arista",
}


class NetBoxAdapter(SourceOfTruth):
    """NetBox REST + GraphQL 包装（v2.0 hermes-03 🟡）。"""

    def __init__(self, base_url: str, token: str, timeout: float = 30.0) -> None:
        # NetBox v4 v2 token 必须用 Bearer header（格式 nbt_<key>.<plaintext>）
        auth = f"Bearer {token}" if token.startswith("nbt_") else f"Token {token}"
        self.client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            headers={"Authorization": auth},
            timeout=timeout,
        )

    async def _get(self, path: str, params: dict | None = None) -> dict:
        try:
            r = await self.client.get(path, params=params)
            r.raise_for_status()
            return r.json()
        except httpx.HTTPStatusError as e:
            raise SSoTError("http_error", f"NetBox {path} 返回 {e.response.status_code}: {e}") from e
        except httpx.RequestError as e:
            raise SSoTError("request_error", f"NetBox {path} 请求失败: {e}") from e

    async def _post(self, path: str, body: dict) -> dict:
        try:
            r = await self.client.post(path, json=body)
            r.raise_for_status()
            return r.json()
        except httpx.HTTPStatusError as e:
            raise SSoTError("http_error", f"NetBox POST {path} 返回 {e.response.status_code}") from e
        except httpx.RequestError as e:
            raise SSoTError("request_error", f"NetBox POST {path} 失败: {e}") from e

    # ===== 读 =====

    async def get_device(self, device_id: int) -> Device:
        data = await self._get(f"/api/dcim/devices/{device_id}/")
        return self._map_device(data)

    async def list_devices(self, filter: dict | None = None) -> list[Device]:
        params = filter or {}
        result = await self._get("/api/dcim/devices/", params=params)
        return [self._map_device(d) for d in result.get("results", [])]

    async def get_topology(self, scope: str) -> Topology:
        """拉拓扑：设备 + 线缆（REST，v4 GraphQL schema 不稳定故直接 REST）。"""
        devices = await self.list_devices({"site": scope})
        nodes = [
            {
                "id": str(d.id),
                "name": d.name,
                "role": d.role,
                "vendor": d.vendor,
                "mgmt_ip": d.mgmt_ip,
                "site": d.site,
            }
            for d in devices
        ]
        cables = await self._get("/api/dcim/cables/", params={"site": scope})
        edges = [self._map_cable_rest(c) for c in cables.get("results", [])]
        return Topology(nodes=nodes, edges=edges)

    async def _topology_via_rest(self, scope: str) -> Topology:
        """GraphQL 不可用时降级 REST 拉拓扑。"""
        devices = await self.list_devices({"site": scope})
        nodes = [
            {
                "id": str(d.id),
                "name": d.name,
                "role": d.role,
                "vendor": d.vendor,
                "mgmt_ip": d.mgmt_ip,
            }
            for d in devices
        ]
        cables = await self._get("/api/dcim/cables/", params={"site": scope})
        edges = [self._map_cable_rest(c) for c in cables.get("results", [])]
        return Topology(nodes=nodes, edges=edges)

    async def get_ipam(self, prefix: str) -> IPAM:
        data = await self._get("/api/ipam/prefixes/", params={"prefix": prefix})
        results = data.get("results", [])
        if not results:
            raise SSoTError("not_found", f"IPAM 前缀 {prefix} 不存在")
        p = results[0]
        return IPAM(
            prefix=p["prefix"],
            family=p["family"],
            description=p.get("description", ""),
            status=p.get("status", {}).get("name", "active"),
        )

    async def get_vrfs(self, project: str) -> list[VRF]:
        data = await self._get("/api/ipam/vrfs/", params={"tenant": project})
        return [
            VRF(
                name=v["name"],
                rd=v.get("rd", ""),
                route_targets=[rt["name"] for rt in v.get("import_targets", [])],
            )
            for v in data.get("results", [])
        ]

    # ===== 写 =====

    async def write_change_record(self, record: ChangeRecord) -> None:
        """变更记录回写 NetBox（custom_field 或 journal entry）。"""
        # NetBox journal entries（v4 原生）
        await self._post(
            "/api/dcim/devices/{}/journal-entries/".format(record.device_id),
            {
                "assigned_object_type": "dcim.device",
                "assigned_object_id": record.device_id,
                "kind": "info",
                "comment": f"[NetSage] change={record.change_id} action={record.action} status={record.status} hash={record.config_hash[:12]}",
            },
        )
        logger.info("netbox_change_recorded", device=record.device_id, change=record.change_id)

    async def update_device_status(self, device_id: int, status: str) -> None:
        """更新设备状态（active/maintenance/failed）。"""
        # 状态需用 status id，先查
        statuses = await self._get("/api/dcim/devices/{}/".format(device_id))
        await self.client.patch(
            "/api/dcim/devices/{}/".format(device_id),
            json={"status": status},
        )
        logger.info("netbox_status_updated", device=device_id, status=status)

    # ===== 映射 =====

    def _map_device(self, d: dict) -> Device:
        platform = (d.get("platform") or {}).get("name", "")
        vendor = self._infer_vendor(d.get("device_type", {}).get("manufacturer", {}).get("name", ""), platform)
        return Device(
            id=d["id"],
            name=d["name"],
            vendor=vendor,
            os=platform,
            model=d.get("device_type", {}).get("model", ""),
            version=d.get("custom_fields", {}).get("os_version", ""),
            mgmt_ip=(d.get("primary_ip4") or {}).get("address", "") if d.get("primary_ip4") else "",
            role=(d.get("role") or {}).get("name", ""),
            site=(d.get("site") or {}).get("name", ""),
            status=(d.get("status") or {}).get("name", "active"),
        )

    def _infer_vendor(self, manufacturer: str, platform: str) -> str:
        m = (manufacturer + " " + platform).lower()
        for key, vendor in NETBOX_VENDOR_MAP.items():
            if key in m:
                return vendor
        return manufacturer.lower() or "unknown"

    def _map_topology_node(self, d: dict) -> dict:
        return {
            "id": str(d["id"]),
            "name": d["name"],
            "role": (d.get("role") or {}).get("name", ""),
            "vendor": self._infer_vendor(
                "",
                (d.get("platform") or {}).get("name", ""),
            ),
            "model": (d.get("device_type") or {}).get("model", ""),
            "mgmt_ip": (d.get("primary_ip4") or {}).get("address", ""),
        }

    def _map_cable(self, c: dict) -> dict:
        a = c.get("a_terminations") or [{}]
        b = c.get("b_terminations") or [{}]
        a_dev = (a[0].get("device") or {}).get("name", "") if a else ""
        b_dev = (b[0].get("device") or {}).get("name", "") if b else ""
        return {
            "id": str(c["id"]),
            "source": a_dev,
            "target": b_dev,
            "src_iface": a[0].get("name", "") if a else "",
            "dst_iface": b[0].get("name", "") if b else "",
        }

    def _map_cable_rest(self, c: dict) -> dict:
        return {
            "id": str(c["id"]),
            "source": c.get("_a_interface", {}).get("device", {}).get("name", ""),
            "target": c.get("_b_interface", {}).get("device", {}).get("name", ""),
        }

    async def close(self) -> None:
        await self.client.aclose()