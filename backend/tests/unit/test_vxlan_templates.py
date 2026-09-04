"""v0.1.1 batch1 VXLAN 模板测试（10 模板，5 厂商 × 2 feature）。"""
from __future__ import annotations

import pytest

from app.services.template_loader import TemplateError, list_by_vendor, load_template, render

VXLAN_TEMPLATES = [
    ("huawei_vrp_vxlan_evpn_l2vpn", {
        "local_asn": 65000,
        "vtep_peers": [{"address": "10.1.1.1", "remote_asn": 65001}],
        "bridge_domain_id": 10,
        "vni": 10010,
        "vbdif_ip": "10.1.10.1/24",
    }),
    ("huawei_vrp_vxlan_anycast_gateway", {
        "bridge_domain_id": 20,
        "vni": 10020,
        "vbdif_ip": "10.1.20.1/24",
        "anycast_gw_mac": "00-00-5e-00-01-20",
    }),
    ("cisco_iosxe_vxlan_evpn_l2vpn", {
        "local_asn": 65000,
        "vtep_peers": [{"address": "10.1.1.1", "remote_asn": 65001}],
        "vlan_id": 10,
        "vni": 10010,
        "evpn_instance_id": 10,
        "rd": "10.0.0.1:10",
        "route_target": "65000:10010",
    }),
    ("cisco_iosxe_vxlan_anycast_gateway", {
        "anycast_gw_mac": "0000.5e00.0120",
        "vlan_id": 20,
        "vni": 10020,
        "vlanif_ip": "10.1.20.1 255.255.255.0",
        "local_asn": 65000,
        "evpn_instance_id": 20,
        "rd": "10.0.0.1:20",
        "route_target": "65000:10020",
    }),
    ("h3c_comware_vxlan_evpn_l2vpn", {
        "local_asn": 65000,
        "vtep_peers": [{"address": "10.1.1.1", "remote_asn": 65001}],
        "vsi_name": "vsi10",
        "vni": 10010,
        "vsi_interface_id": 1,
        "vsi_interface_ip": "10.1.10.1 24",
    }),
    ("h3c_comware_vxlan_anycast_gateway", {
        "anycast_gw_mac": "0000-5e00-0120",
        "vsi_name": "vsi20",
        "vni": 10020,
        "vsi_interface_id": 2,
        "vsi_interface_ip": "10.1.20.1 24",
    }),
    ("juniper_junos_vxlan_evpn_l2vpn", {
        "instance_name": "vsrx-evpn",
        "vlan_id": 10,
        "vni": 10010,
        "rd": "10.0.0.1:10",
        "vrf_target": "65000:10010",
        "bgp_neighbor": "10.1.1.1",
        "local_address": "10.0.0.1",
    }),
    ("juniper_junos_vxlan_anycast_gateway", {
        "instance_name": "anycast-gw",
        "vlan_id": 20,
        "vni": 10020,
        "irb_unit": 20,
        "irb_ip": "10.1.20.1/24",
        "anycast_gw_mac": "00:00:5e:00:01:20",
    }),
    ("arista_eos_vxlan_evpn_l2vpn", {
        "local_asn": 65000,
        "router_id": "10.0.0.1",
        "vtep_peers": [{"address": "10.1.1.1", "remote_asn": 65001}],
        "vlan_id": 10,
        "vni": 10010,
        "vxlan_interface": "Vxlan1",
    }),
    ("arista_eos_vxlan_anycast_gateway", {
        "anycast_gw_mac": "00:00:5e:00:01:20",
        "vlan_id": 20,
        "vni": 10020,
        "vlanif_ip": "10.1.20.1/24",
        "local_asn": 65000,
    }),
]


@pytest.mark.parametrize("template_id,params", VXLAN_TEMPLATES)
def test_vxlan_template_meta_valid(template_id, params):
    """每个 VXLAN 模板 meta.yaml 校验通过。"""
    _, meta = load_template(template_id)
    assert meta["protocol"] == "vxlan"
    assert meta["vendor"] in {"huawei", "cisco", "h3c", "juniper", "arista"}


@pytest.mark.parametrize("template_id,params", VXLAN_TEMPLATES)
def test_vxlan_template_renders(template_id, params):
    """每个 VXLAN 模板渲染成功且输出含关键关键字。"""
    output = render(template_id, params)
    assert len(output) > 50
    assert "{{" not in output  # 无未渲染变量


def test_vxlan_template_count():
    """v0.1.1 batch1：10 个 VXLAN 模板（5 厂商 × 2 feature）。"""
    count = 0
    for vendor in ["huawei", "cisco", "h3c", "juniper", "arista"]:
        count += len(list_by_vendor(vendor, "vxlan"))
    assert count == 10


def test_vxlan_template_missing_param_raises():
    """缺必填参数必须报错（StrictUndefined，防生成残缺配置）。"""
    with pytest.raises(TemplateError):
        render("huawei_vrp_vxlan_evpn_l2vpn", {"local_asn": 65000})  # 缺 vtep_peers 等


def test_huawei_vxlan_evpn_contains_bgp_and_vni():
    """华为 VXLAN EVPN 渲染含关键命令。"""
    out = render("huawei_vrp_vxlan_evpn_l2vpn", VXLAN_TEMPLATES[0][1])
    assert "bgp 65000" in out
    assert "vxlan vni 10010" in out
    assert "bridge-domain 10" in out
