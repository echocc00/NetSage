"""多厂商模板渲染测试（Phase 2 P2-5）。

验证 5 厂商 × 2 协议 = 10 模板均能正确渲染。
真实语法正确性待网络工程师 review（author/reviewers 字段）。
"""
from __future__ import annotations

import pytest

from app.services.template_loader import list_by_vendor, render

# ===== BGP peering 跨厂商 =====


@pytest.mark.parametrize(
    "template_id,vendor,params,expected_snippets",
    [
        (
            "huawei_vrp_bgp_peering",
            "huawei",
            {
                "local_asn": 65001,
                "router_id": "1.1.1.1",
                "peers": [{"address": "10.1.1.2", "remote_asn": 65002, "description": "SH-GZ"}],
            },
            ["bgp 65001", "router-id 1.1.1.1", "peer 10.1.1.2 as-number 65002"],
        ),
        (
            "cisco_iosxe_bgp_peering",
            "cisco",
            {
                "local_asn": 65001,
                "router_id": "1.1.1.1",
                "peers": [{"address": "10.1.1.2", "remote_asn": 65002, "description": "SH-GZ"}],
            },
            ["router bgp 65001", "neighbor 10.1.1.2 remote-as 65002", "neighbor 10.1.1.2 activate"],
        ),
        (
            "h3c_comware_bgp_peering",
            "h3c",
            {
                "local_asn": 65001,
                "router_id": "1.1.1.1",
                "peers": [{"address": "10.1.1.2", "remote_asn": 65002, "description": "SH-GZ"}],
            },
            ["bgp 65001", "peer 10.1.1.2 as-number 65002", "peer 10.1.1.2 enable"],
        ),
        (
            "juniper_junos_bgp_peering",
            "juniper",
            {
                "group_name": "EBGP-PEERS",
                "remote_asn": 65002,
                "peers": [{"address": "10.1.1.2", "description": "SH-GZ"}],
            },
            ["protocols {", "bgp {", "group EBGP-PEERS", "peer-as 65002", "neighbor 10.1.1.2"],
        ),
        (
            "arista_eos_bgp_peering",
            "arista",
            {
                "local_asn": 65001,
                "router_id": "1.1.1.1",
                "peers": [{"address": "10.1.1.2", "remote_asn": 65002, "description": "SH-GZ"}],
            },
            ["router bgp 65001", "neighbor 10.1.1.2 remote-as 65002", "neighbor 10.1.1.2 activate"],
        ),
    ],
)
def test_bgp_peering_multi_vendor(template_id, vendor, params, expected_snippets):
    """5 厂商 BGP peering 模板均渲染成功（v2.0 31.2 多厂商覆盖）。"""
    config = render(template_id, params)
    for snippet in expected_snippets:
        assert snippet in config, f"{vendor} BGP 模板缺: {snippet}\n渲染结果:\n{config}"


# ===== OSPF area 跨厂商 =====


@pytest.mark.parametrize(
    "template_id,vendor,params,expected_snippets",
    [
        (
            "huawei_vrp_ospf_area_config",
            "huawei",
            {
                "router_id": "2.2.2.2",
                "network_areas": [{"area_id": 0, "network": "10.0.0.0", "wildcard": "255.0.0.0"}],
            },
            ["ospf 1 router-id 2.2.2.2", "network 10.0.0.0 255.0.0.0"],
        ),
        (
            "cisco_iosxe_ospf_area_config",
            "cisco",
            {
                "process_id": 1,
                "router_id": "2.2.2.2",
                "network_areas": [{"area_id": 0, "network": "10.0.0.0", "wildcard": "0.255.255.255"}],
            },
            ["router ospf 1", "network 10.0.0.0 0.255.255.255 area 0"],
        ),
        (
            "h3c_comware_ospf_area_config",
            "h3c",
            {
                "process_id": 1,
                "router_id": "2.2.2.2",
                "network_areas": [{"area_id": 0, "network": "10.0.0.0", "wildcard": "0.255.255.255"}],
            },
            ["ospf 1 router-id 2.2.2.2", "network 10.0.0.0 0.255.255.255"],
        ),
        (
            "juniper_junos_ospf_area_config",
            "juniper",
            {
                "area_id": "0.0.0.0",
                "interfaces": [{"name": "ge-0/0/0", "passive": False}],
            },
            ["protocols {", "ospf {", "area 0.0.0.0", "interface ge-0/0/0"],
        ),
        (
            "arista_eos_ospf_area_config",
            "arista",
            {
                "process_id": 1,
                "router_id": "2.2.2.2",
                "network_areas": [{"area_id": 0, "network": "10.0.0.0", "wildcard": "0.255.255.255"}],
            },
            ["router ospf 1", "network 10.0.0.0 0.255.255.255 area 0"],
        ),
    ],
)
def test_ospf_area_multi_vendor(template_id, vendor, params, expected_snippets):
    """5 厂商 OSPF area 模板均渲染成功。"""
    config = render(template_id, params)
    for snippet in expected_snippets:
        assert snippet in config, f"{vendor} OSPF 模板缺: {snippet}\n渲染结果:\n{config}"


# ===== 模板覆盖率 =====


def test_template_coverage_5_vendors():
    """5 厂商均有模板（v2.0 31.2 多厂商）。"""
    for vendor in ["huawei", "cisco", "h3c", "juniper", "arista"]:
        templates = list_by_vendor(vendor)
        assert len(templates) >= 2, f"{vendor} 模板不足 2 个（现有 {len(templates)}）"


def test_template_coverage_bgp_ospf():
    """每厂商至少 BGP + OSPF 各 1 个（Phase 2 基线）。"""
    for vendor in ["huawei", "cisco", "h3c", "juniper", "arista"]:
        bgp = list_by_vendor(vendor, protocol="bgp")
        ospf = list_by_vendor(vendor, protocol="ospf")
        assert len(bgp) >= 1, f"{vendor} 缺 BGP 模板"
        assert len(ospf) >= 1, f"{vendor} 缺 OSPF 模板"
