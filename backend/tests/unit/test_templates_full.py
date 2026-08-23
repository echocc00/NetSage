"""v0.1.1 模板库全量测试（80 模板，5 厂商 × 7 协议）。"""
from __future__ import annotations

import pytest
import yaml
from pathlib import Path

from app.services.template_loader import TEMPLATES_ROOT, TemplateError, list_by_vendor, load_template, render


def _all_template_ids() -> list[str]:
    ids = []
    for meta_path in TEMPLATES_ROOT.rglob("*.meta.yaml"):
        meta = yaml.safe_load(meta_path.read_text(encoding="utf-8")) or {}
        if "template_id" in meta:
            ids.append(meta["template_id"])
    return sorted(ids)


def _sample_params(meta: dict) -> dict:
    """按 input_schema 构造必填参数示例值。"""
    params = {}
    for f in meta.get("input_schema", []):
        if not f.get("required"):
            continue
        name, t = f["name"], f.get("type", "string")
        if t == "int":
            params[name] = 10
        elif t == "bool":
            params[name] = True
        elif t == "array":
            items = f.get("items", {})
            item = {k: (10 if v == "int" else "10.1.1.1") for k, v in (items.items() if isinstance(items, dict) else [])} if items else {}
            params[name] = [item] if item else []
        else:
            params[name] = "10.1.1.1"
    return params


ALL_IDS = _all_template_ids()


def test_template_count_80():
    """v0.1.1 验收：模板总数 ≥ 80。"""
    assert len(ALL_IDS) >= 80, f"模板数 {len(ALL_IDS)} < 80"


def test_each_vendor_at_least_16():
    """每厂商 ≥ 16 模板（7 协议覆盖）。"""
    for v in ["huawei", "cisco", "h3c", "juniper", "arista"]:
        count = len(list_by_vendor(v))
        assert count >= 16, f"{v} 模板数 {count} < 16"


def test_each_vendor_covers_7_protocols():
    """每厂商覆盖 ≥ 6 协议（bgp/ospf/vxlan/vpn/interface/static_route/wireless）。"""
    for v in ["huawei", "cisco", "h3c", "juniper", "arista"]:
        protos = {m["protocol"] for m in list_by_vendor(v)}
        assert len(protos) >= 6, f"{v} 协议数 {len(protos)} < 6: {protos}"


@pytest.mark.parametrize("template_id", ALL_IDS)
def test_meta_valid(template_id):
    """每个模板 meta.yaml 校验通过。"""
    _, meta = load_template(template_id)
    assert meta["vendor"] in {"huawei", "cisco", "h3c", "juniper", "arista"}
    assert meta["protocol"] in {"ospf", "bgp", "vxlan", "vpn", "wireless", "interface", "static_route", "roce"}


@pytest.mark.parametrize("template_id", ALL_IDS)
def test_renders_without_unrendered_tags(template_id):
    """每个模板渲染成功且无未渲染变量。"""
    _, meta = load_template(template_id)
    params = _sample_params(meta)
    output = render(template_id, params)
    assert len(output) > 20
    assert "{{" not in output
    assert "{%" not in output


def test_required_param_missing_raises():
    """缺必填参数必须报错（防生成残缺配置）。"""
    with pytest.raises(TemplateError):
        render("huawei_vrp_bgp_peering", {})


def test_optional_param_has_default():
    """可选参数未传时用默认值，不报错（StrictUndefined 不误报）。"""
    out = render("huawei_vrp_static_route_default", {"dest": "10.1.1.0", "next_hop": "10.1.1.1"})
    assert "ip route-static" in out
