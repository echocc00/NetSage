"""WirelessAgent（Phase 4 M10，v2.0 5.1）。

无线专项：AP 布放规划 + 信道/功率调优 + 漫游域 + 安全策略。
collect → plan → suggest_config
"""
from __future__ import annotations

from typing import Any

WIRELESS_AGENT_DEFINITION = {
    "name": "wireless_agent",
    "role": "无线网络 Agent：AP 布放 + 信道/功率调优 + 漫游域 + 安全策略",
    "system_prompt": "你是无线网络专家。规划 AP 布放、信道、功率、漫游域、安全策略。",
    "tools": ["napalm.get_config", "rag.search", "template.render"],
    "state_schema": {"type": "object"},
    "transitions": [
        {"from": "collect", "to": "plan"},
        {"from": "plan", "to": "suggest_config"},
        {"from": "suggest_config", "to": "END"},
    ],
    "interrupt_points": [],
}


def _infer_vendor_key(vendor: str) -> str:
    if vendor.startswith("huawei"): return "huawei_vrp"
    if vendor.startswith("cisco"): return "cisco_iosxe"
    if vendor.startswith("h3c"): return "h3c_comware"
    return "huawei_vrp"


async def wireless_collect(state: dict, tools: Any) -> dict:
    """采集需求：面积 + 用户数 + 终端类型 + 现有 AP。"""
    return state


async def wireless_plan(state: dict, tools: Any) -> dict:
    """规划：AP 数量 + 信道方案 + 漫游域。"""
    area = state.get("area_sqm", 500)      # 面积 m²
    users = state.get("users", 100)         # 用户数
    floor = state.get("floors", 1)          # 楼层数

    # 简化估算：每 100m² 一个 AP，每 AP 承载 50 用户
    ap_per_floor = max(2, area // 100)
    total_aps = ap_per_floor * floor
    # 信道规划：2.4G 1/6/11 错开，5G 36/40/44/48 轮转
    channels_2g = [1, 6, 11]
    channels_5g = [36, 40, 44, 48, 52, 56]
    ap_plan = []
    for i in range(total_aps):
        ap_plan.append({
            "ap_id": i + 1,
            "ap_name": f"ap-{i+1:02d}",
            "floor": (i // ap_per_floor) + 1,
            "channel_2g": channels_2g[i % 3],
            "channel_5g": channels_5g[i % len(channels_5g)],
            "power": 70 if users > 50 else 100,
        })
    return {
        **state,
        "plan": {
            "total_aps": total_aps,
            "ap_per_floor": ap_per_floor,
            "roaming_domain": state.get("ssid", "Corp-WiFi"),
            "ap_plan": ap_plan,
            "capacity": {"per_ap_users": 50, "total_capacity": total_aps * 50},
        },
    }


async def wireless_suggest_config(state: dict, tools: Any) -> dict:
    """生成配置：SSID + 漫游 + 安全策略模板渲染。"""
    from app.services.template_loader import TemplateError, render

    vendor = state.get("vendor", "huawei")
    vendor_key = _infer_vendor_key(vendor)
    plan = state.get("plan", {})
    ap_plan = plan.get("ap_plan", [])
    first_ap = ap_plan[0] if ap_plan else {"ap_id": 1, "ap_name": "ap-01", "channel_2g": 1, "channel_5g": 36, "power": 70}

    ssid = state.get("ssid", "Corp-WiFi")
    security = state.get("security", "wpa2-psk")
    psk = state.get("psk_passphrase", "changeme123")

    config = ""
    template_id = f"{vendor_key}_wireless_ssid"
    try:
        config = render(template_id, {
            "radio_name": f"radio-{first_ap['ap_name']}",
            "channel": first_ap["channel_5g"],
            "power": first_ap["power"],
            "security_name": f"sec-{ssid}",
            "ssid": ssid,
            "security_policy": security,
            "psk_passphrase": psk,
            "traffic_name": f"traffic-{ssid}",
            "vap_name": f"vap-{ssid}",
            "ap_group_name": f"group-{ssid}",
            "ap_id": first_ap["ap_id"],
            "ap_mac": f"00:1a:{first_ap['ap_id']:02x}:00:00:01",
            "ap_name": first_ap["ap_name"],
        })
    except (TemplateError, KeyError):
        config = ""

    return {
        **state,
        "config": config,
        "template_used": template_id,
        "recommendations": [
            f"部署 {plan.get('total_aps', 0)} 台 AP（{plan.get('ap_per_floor', 0)} 台/层）",
            f"SSID: {ssid}，漫游域统一",
            f"安全策略: {security}（建议企业版用 802.1X）",
            "2.4G 信道 1/6/11 错开，5G 优先 36/40/44/48",
            "启用 802.11r FT 漫游（roaming 模板）",
        ],
    }
