"""SourceOfTruth + NetBoxAdapter 测试（Phase 2 P2-1）。"""
from __future__ import annotations

from typing import Any

import httpx
import pytest

from app.access.netbox_adapter import NetBoxAdapter
from app.access.source_of_truth import (
    ChangeRecord,
    Device,
    IPAM,
    NullSSoT,
    SSoTError,
    configure_ssot,
    get_ssot,
)


# ===== SourceOfTruth 抽象 =====


def test_null_ssot_returns_empty():
    """NullSSoT 降级返回空（SSoT 未配置时不崩溃）。"""
    s = NullSSoT()
    import asyncio

    assert asyncio.run(s.list_devices()) == []
    topo = asyncio.run(s.get_topology("site1"))
    assert topo.nodes == [] and topo.edges == []


def test_null_ssot_get_device_raises():
    s = NullSSoT()
    import asyncio

    with pytest.raises(SSoTError) as exc:
        asyncio.run(s.get_device(1))
    assert exc.value.code == "not_configured"


def test_configure_and_get_ssot():
    """全局 SSoT 注入/读取。"""
    configure_ssot(NullSSoT())  # type: ignore[arg-type]
    assert isinstance(get_ssot(), NullSSoT)


# ===== NetBoxAdapter =====


def _mock_device(netbox_data: dict) -> dict:
    return {
        "id": netbox_data["id"],
        "name": netbox_data["name"],
        "vendor": netbox_data.get("vendor", "huawei"),
        "os": netbox_data.get("os", "vrp"),
        "model": netbox_data.get("model", ""),
        "version": netbox_data.get("version", ""),
        "mgmt_ip": netbox_data.get("mgmt_ip", ""),
        "role": netbox_data.get("role", ""),
        "site": netbox_data.get("site", ""),
    }


@pytest.fixture
def netbox_mock(monkeypatch):
    """mock httpx.AsyncClient 的 get/post/patch。"""
    responses: dict[str, dict] = {}

    class MockResp:
        def __init__(self, data, status_code=200):
            self._data = data
            self.status_code = status_code

        def json(self):
            return self._data

        def raise_for_status(self):
            if self.status_code >= 400:
                raise httpx.HTTPStatusError(
                    "err", request=None, response=httpx.Response(self.status_code)  # type: ignore
                )

    class MockClient:
        def __init__(self, **kw):
            self.base_url = kw.get("base_url", "")
            self.headers = kw.get("headers", {})

        async def get(self, path, params=None):
            key = path
            if key in responses:
                return MockResp(responses[key])
            return MockResp({"results": []})

        async def post(self, path, json=None):
            key = path
            if key in responses:
                return MockResp(responses[key])
            return MockResp({})

        async def patch(self, path, json=None):
            return MockResp({})

        async def aclose(self):
            pass

    monkeypatch.setattr(httpx, "AsyncClient", MockClient)
    return responses


@pytest.mark.asyncio
async def test_netbox_get_device(netbox_mock):
    netbox_mock["/api/dcim/devices/42/"] = {
        "id": 42,
        "name": "spine01",
        "device_type": {"model": "CE12800", "manufacturer": {"name": "Huawei"}},
        "platform": {"name": "vrp"},
        "primary_ip4": {"address": "10.1.1.1/32"},
        "role": {"name": "spine"},
        "site": {"name": "shanghai"},
        "status": {"name": "active"},
    }
    adapter = NetBoxAdapter("http://netbox:8000", "token")
    dev = await adapter.get_device(42)
    assert dev.id == 42
    assert dev.name == "spine01"
    assert dev.vendor == "huawei"
    assert dev.role == "spine"


@pytest.mark.asyncio
async def test_netbox_list_devices(netbox_mock):
    netbox_mock["/api/dcim/devices/"] = {
        "results": [
            {"id": 1, "name": "leaf01", "device_type": {"model": "", "manufacturer": {"name": "Cisco"}}, "platform": {"name": "iosxe"}, "role": {"name": "leaf"}},
        ]
    }
    adapter = NetBoxAdapter("http://netbox", "t")
    devs = await adapter.list_devices()
    assert len(devs) == 1
    assert devs[0].vendor == "cisco"


@pytest.mark.asyncio
async def test_netbox_infer_vendor(netbox_mock):
    """厂商推断：manufacturer + platform 关键词匹配。"""
    adapter = NetBoxAdapter("http://netbox", "t")
    assert adapter._infer_vendor("Huawei", "VRP") == "huawei"
    assert adapter._infer_vendor("Cisco", "IOS-XE") == "cisco"
    assert adapter._infer_vendor("H3C", "Comware") == "h3c"
    assert adapter._infer_vendor("Unknown", "") == "unknown"


@pytest.mark.asyncio
async def test_netbox_get_ipam(netbox_mock):
    netbox_mock["/api/ipam/prefixes/"] = {
        "results": [{"prefix": "10.0.0.0/8", "family": 4, "description": "prod", "status": {"name": "active"}}]
    }
    adapter = NetBoxAdapter("http://netbox", "t")
    ipam = await adapter.get_ipam("10.0.0.0/8")
    assert ipam.prefix == "10.0.0.0/8"
    assert ipam.family == 4


@pytest.mark.asyncio
async def test_netbox_get_ipam_not_found(netbox_mock):
    """前缀不存在明确报错（不返回空）。"""
    netbox_mock["/api/ipam/prefixes/"] = {"results": []}
    adapter = NetBoxAdapter("http://netbox", "t")
    with pytest.raises(SSoTError) as exc:
        await adapter.get_ipam("99.0.0.0/8")
    assert exc.value.code == "not_found"


@pytest.mark.asyncio
async def test_netbox_write_change_record(netbox_mock):
    """变更记录回写 NetBox journal。"""
    netbox_mock["/api/dcim/devices/42/journal-entries/"] = {"id": 1}
    adapter = NetBoxAdapter("http://netbox", "t")
    record = ChangeRecord(change_id=1, device_id=42, action="deploy", status="success", config_hash="abc123")
    await adapter.write_change_record(record)  # 不抛异常即通过


@pytest.mark.asyncio
async def test_netbox_request_error_raises_ssot_error(monkeypatch):
    """NetBox 不可达时抛 SSoTError（不崩溃调用方）。"""

    class ErrClient:
        async def get(self, *a, **kw):
            raise httpx.ConnectError("connection refused")

        async def post(self, *a, **kw):
            raise httpx.ConnectError("connection refused")

        async def patch(self, *a, **kw):
            raise httpx.ConnectError("connection refused")

        async def aclose(self):
            pass

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: ErrClient())
    adapter = NetBoxAdapter("http://unreachable", "t")
    with pytest.raises(SSoTError) as exc:
        await adapter.get_device(1)
    assert exc.value.code == "request_error"
