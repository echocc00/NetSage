"""配置模板库服务（v2.0 二十七章：模板沉淀机制）。

- meta.yaml 校验（必带元数据，v2.0 27.2）
- 按 vendor/os/protocol/feature 匹配模板
- Jinja2 渲染
"""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined

from app.core.logging import get_logger

logger = get_logger("template_loader")

TEMPLATES_ROOT = Path(__file__).resolve().parent.parent.parent / "templates"

# meta.yaml 必填字段（v2.0 27.2）
REQUIRED_META_FIELDS = {
    "template_id",
    "vendor",
    "os",
    "protocol",
    "feature",
    "input_schema",
}

VALID_PROTOCOLS = {"ospf", "bgp", "vxlan", "vpn", "wireless", "roce", "interface", "static_route"}
VALID_VENDORS = {"huawei", "cisco", "h3c", "juniper", "arista", "nokia", "mellanox"}


class TemplateError(Exception):
    """模板加载/校验/渲染错误。"""


@lru_cache(maxsize=1)
def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(TEMPLATES_ROOT)),
        undefined=StrictUndefined,  # 渲染时缺参即报错，防生成残缺配置
        trim_blocks=True,
        lstrip_blocks=True,
    )


def validate_template(template_id: str, meta: dict) -> None:
    """校验模板元数据（v2.0 27.2 必带字段）。"""
    missing = REQUIRED_META_FIELDS - set(meta.keys())
    if missing:
        raise TemplateError(f"模板 [{template_id}] meta.yaml 缺字段: {sorted(missing)}")
    if meta["vendor"] not in VALID_VENDORS:
        raise TemplateError(f"模板 [{template_id}] 非法厂商: {meta['vendor']}")
    if meta["protocol"] not in VALID_PROTOCOLS:
        raise TemplateError(f"模板 [{template_id}] 非法协议: {meta['protocol']}")
    if not isinstance(meta["input_schema"], list):
        raise TemplateError(f"模板 [{template_id}] input_schema 必须是数组（Jinja2 入参 JSON Schema）")
    # 版本区间
    vmin = meta.get("version_min", "")
    vmax = meta.get("version_max", "")
    if vmin and vmax and _ver_tuple(vmin) > _ver_tuple(vmax):
        raise TemplateError(f"模板 [{template_id}] version_min > version_max")


def _ver_tuple(v: str) -> tuple[int, int]:
    parts = re.findall(r"\d+", v)
    parts = (parts + ["0", "0"])[:2]
    return int(parts[0]), int(parts[1])


def load_template(template_id: str) -> tuple[str, dict]:
    """加载 .j2 + .meta.yaml，校验后返回 (jinja2 路径, meta)。"""
    # 定位模板目录：find 所有 *.meta.yaml
    found: Path | None = None
    for meta_path in TEMPLATES_ROOT.rglob("*.meta.yaml"):
        meta = yaml.safe_load(meta_path.read_text(encoding="utf-8")) or {}
        if meta.get("template_id") == template_id:
            found = meta_path
            break
    if found is None:
        raise TemplateError(f"模板 [{template_id}] 不存在")
    validate_template(template_id, meta)
    # Jinja2 loader 需要正斜杠路径（Windows \ 会导致 TemplateNotFound）
    rel = found.relative_to(TEMPLATES_ROOT).with_suffix("").with_suffix("").as_posix()
    return rel, meta


def render(template_id: str, params: dict) -> str:
    """按参数渲染模板。必填缺参报错；可选未传按类型注入默认值（防 StrictUndefined 误报）。"""
    rel, meta = load_template(template_id)
    required = [f["name"] for f in meta["input_schema"] if f.get("required")]
    missing = [r for r in required if r not in params]
    if missing:
        raise TemplateError(f"模板 [{template_id}] 缺必传入参: {missing}")
    # 可选参数未传 → 按类型注入默认值（让模板 {% if x %} 可正常求值）
    full = {}
    for f in meta["input_schema"]:
        name = f["name"]
        if name in params:
            full[name] = params[name]
        elif not f.get("required"):
            full[name] = _default_for(f.get("type", "string"))
    try:
        template = _env().get_template(rel)
        return template.render(**full)
    except Exception as e:
        raise TemplateError(f"模板 [{template_id}] 渲染失败: {e}") from e


def _default_for(type_name: str):
    """可选参数的默认值（按类型，让模板条件判断可求值）。"""
    if type_name == "int":
        return 0
    if type_name == "bool":
        return False
    if type_name == "array":
        return []
    return ""


def list_by_vendor(vendor: str, protocol: str | None = None) -> list[dict]:
    """列出某厂商（可选协议）的可用模板。"""
    results = []
    for meta_path in TEMPLATES_ROOT.rglob("*.meta.yaml"):
        meta = yaml.safe_load(meta_path.read_text(encoding="utf-8")) or {}
        if meta.get("vendor") == vendor and (protocol is None or meta.get("protocol") == protocol):
            results.append(meta)
    return results