"""设备接入层测试（v2.0 开发计划十章）。

覆盖：
- DeviceTarget napalm driver 映射
- AdapterFactory 选择逻辑
- NAPALM/Netmiko driver map 厂商覆盖
"""
from __future__ import annotations

import pytest

from app.access.base import DeviceTarget, NAPALM_DRIVER_MAP
from app.access.factory import AdapterFactory
from app.access.napalm_adapter import NapalmAdapter
from app.access.netmiko_adapter import NETMIKO_TYPE_MAP, NetmikoAdapter
from app.access.scrapli_adapter import SCRAPLI_PLATFORM_MAP, ScrapliAdapter


def test_napalm_driver_map_covers_phase1_vendors():
    """napalm 覆盖 Phase 1 全厂商（v2.0 31.2）。"""
    required = {"cisco_iosxe", "huawei_vrp", "h3c_comware", "juniper_junos", "arista_eos"}
    assert required.issubset(NAPALM_DRIVER_MAP.keys())


def test_netmiko_type_map_covers_vendors():
    assert "huawei_vrp" in NETMIKO_TYPE_MAP
    assert NETMIKO_TYPE_MAP["huawei_vrp"] == "huawei"


def test_scrapli_platform_map_covers_vendors():
    assert "cisco_iosxe" in SCRAPLI_PLATFORM_MAP


def test_device_target_napalm_driver():
    """DeviceTarget 正确映射 napalm driver。"""
    t = DeviceTarget(
        id=1, name="leaf01", vendor="huawei_vrp", host="10.1.2.3",
        username="admin", password="pass",
    )
    assert t.napalm_driver == "huawei"

    t2 = DeviceTarget(
        id=2, name="leaf02", vendor="cisco_iosxe", host="10.1.2.4",
        username="admin", password="pass",
    )
    assert t2.napalm_driver == "iosxe"


def test_device_target_unknown_vendor_fallback():
    """未知厂商 napalm_driver 回退为 vendor 本身（AdapterFactory 再降级 netmiko）。"""
    t = DeviceTarget(
        id=3, name="x", vendor="unknown_vendor", host="1.1.1.1",
        username="a", password="b",
    )
    assert t.napalm_driver == "unknown_vendor"


def test_factory_for_write_prefers_napalm():
    """写操作优先 napalm（commit/rollback 最成熟，v2.0 10.2）。"""
    factory = AdapterFactory()
    target = DeviceTarget(
        id=1, name="l", vendor="huawei_vrp", host="x",
        username="a", password="b",
    )
    adapter = factory.for_write(target)
    assert isinstance(adapter, NapalmAdapter)


def test_factory_for_write_falls_back_to_netmiko():
    """napalm 不支持的厂商降级 netmiko。"""
    factory = AdapterFactory()
    target = DeviceTarget(
        id=1, name="l", vendor="unknown", host="x",
        username="a", password="b",
    )
    adapter = factory.for_write(target)
    assert isinstance(adapter, NetmikoAdapter)


def test_factory_for_batch_uses_scrapli():
    """批量采集用 scrapli（异步高并发，v2.0 10.2）。"""
    factory = AdapterFactory()
    target = DeviceTarget(
        id=1, name="l", vendor="cisco_iosxe", host="x",
        username="a", password="b",
    )
    adapter = factory.for_batch(target)
    assert isinstance(adapter, ScrapliAdapter)


def test_factory_for_cli_uses_netmiko():
    factory = AdapterFactory()
    target = DeviceTarget(
        id=1, name="l", vendor="cisco_iosxe", host="x",
        username="a", password="b",
    )
    assert isinstance(factory.for_cli(target), NetmikoAdapter)


def test_adapter_error_structure():
    from app.access.base import AdapterError

    err = AdapterError("connect_failed", "超时")
    assert err.code == "connect_failed"
