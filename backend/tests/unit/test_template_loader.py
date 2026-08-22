"""配置模板库服务测试（v2.0 二十七章）。"""
from __future__ import annotations

import pytest

from app.services.template_loader import (
    TemplateError,
    list_by_vendor,
    render,
    validate_template,
)


def test_render_bgp_peering():
    """BGP peering 渲染（v2.0 27.4 Phase 1 华为）。"""
    config = render(
        "huawei_vrp_bgp_peering",
        {
            "local_asn": 65001,
            "router_id": "1.1.1.1",
            "peers": [
                {"address": "10.1.1.2", "remote_asn": 65002, "description": "SH-GZ"},
            ],
        },
    )
    assert "bgp 65001" in config
    assert "router-id 1.1.1.1" in config
    assert "peer 10.1.1.2 as-number 65002" in config
    assert "description SH-GZ" in config


def test_render_ospf_area():
    """OSPF area 渲染。"""
    config = render(
        "huawei_vrp_ospf_area_config",
        {
            "router_id": "2.2.2.2",
            "network_areas": [{"area_id": 0, "network": "10.0.0.0", "wildcard": "255.0.0.0"}],
        },
    )
    assert "ospf 1 router-id 2.2.2.2" in config
    assert "network 10.0.0.0 255.0.0.0" in config


def test_render_missing_required_param_raises():
    """缺必传入参报错（StrictUndefined + 入参校验）。"""
    with pytest.raises(TemplateError):
        render("huawei_vrp_bgp_peering", {"local_asn": 65001})


def test_render_undefined_optional_safe():
    """可选参数未传不报错（is defined 保护）。"""
    config = render(
        "huawei_vrp_ospf_area_config",
        {"router_id": "1.1.1.1", "network_areas": []},
    )
    assert "silent-interface" not in config


def test_unknown_template_raises():
    with pytest.raises(TemplateError):
        render("nonexistent_template", {})


def test_list_by_vendor():
    """按厂商列出模板。"""
    huawei = list_by_vendor("huawei")
    ids = {m["template_id"] for m in huawei}
    assert "huawei_vrp_bgp_peering" in ids
    assert "huawei_vrp_ospf_area_config" in ids


def test_validate_meta_missing_field():
    """meta 缺必填字段报错。"""
    with pytest.raises(TemplateError):
        validate_template("t", {"template_id": "t", "vendor": "huawei"})  # 缺 os/protocol 等


def test_validate_meta_bad_vendor():
    with pytest.raises(TemplateError):
        validate_template(
            "t",
            {
                "template_id": "t",
                "vendor": "unknown_vendor",
                "os": "vrp",
                "protocol": "bgp",
                "feature": "x",
                "input_schema": [{"name": "x", "type": "int", "required": True}],
            },
        )


def test_validate_version_range():
    """version_min > version_max 报错。"""
    with pytest.raises(TemplateError):
        validate_template(
            "t",
            {
                "template_id": "t",
                "vendor": "huawei",
                "os": "vrp",
                "version_min": "9.0",
                "version_max": "8.0",
                "protocol": "bgp",
                "feature": "x",
                "input_schema": [{"name": "x", "type": "int", "required": True}],
            },
        )