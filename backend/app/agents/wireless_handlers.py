"""WirelessAgent handlers（Phase 4 M10，v2.0 5.1）。

无线专项：AP 布放规划 + 射频规划（信道/功率/带宽）+ 漫游域 + 安全策略。
collect → plan → rf_plan → roaming_security → suggest_config
"""
from __future__ import annotations

from typing import Any

WIRELESS_AGENT_DEFINITION: dict[str, Any] = {
    "name": "wireless_agent",
    "role": "无线网络 Agent：AP 布放 + 射频规划（信道/功率/带宽）+ 漫游域 + 安全策略",
    "system_prompt": (
        "你是无线网络专家。规划 AP 布放密度、射频参数（信道复用/发射功率/信道带宽）、"
        "漫游域（802.11r/k/v）与安全策略（WPA2/WPA3/802.1X）。"
    ),
    "tools": ["napalm.get_config", "rag.search", "template.render"],
    "state_schema": {"type": "object"},
    "transitions": [
        {"from": "collect", "to": "plan"},
        {"from": "plan", "to": "rf_plan"},
        {"from": "rf_plan", "to": "roaming_security"},
        {"from": "roaming_security", "to": "suggest_config"},
        {"from": "suggest_config", "to": "END"},
    ],
    "interrupt_points": [],
}

_VENDOR_KEYS = {
    "huawei": "huawei_vrp",
    "cisco": "cisco_iosxe",
    "h3c": "h3c_comware",
    "juniper": "juniper_junos",
    "arista": "arista_eos",
}

# 2.4G 非重叠信道（20MHz）
CHANNELS_2G = [1, 6, 11]
# 5G UNII-1/2A/2C/3 常用信道（20MHz，避开雷达优先 UNII-1/3）
CHANNELS_5G_20 = [36, 40, 44, 48, 149, 153, 157, 161]
# 5G 40MHz 主信道
CHANNELS_5G_40 = [38, 46, 151, 159]
# 5G 80MHz 主信道
CHANNELS_5G_80 = [42, 155]

# 场景 → 每 AP 覆盖面积（m²）与承载用户数
SCENARIO_PROFILE: dict[str, dict] = {
    "office":     {"area_per_ap": 120, "users_per_ap": 40, "power": 70},
    "highdensity": {"area_per_ap": 60, "users_per_ap": 60, "power": 40},   # 会议室/礼堂
    "warehouse":  {"area_per_ap": 300, "users_per_ap": 20, "power": 100},  # 空旷高顶
    "dormitory":  {"area_per_ap": 80, "users_per_ap": 30, "power": 50},
}

# 安全策略 → 配置要点
SECURITY_PROFILE: dict[str, dict] = {
    "wpa2-psk":  {"policy": "wpa2", "akm": "psk", "cipher": "ccmp", "pmf": "optional"},
    "wpa3-sae":  {"policy": "wpa3", "akm": "sae", "cipher": "ccmp", "pmf": "required"},
    "wpa2-802.1x": {"policy": "wpa2", "akm": "dot1x", "cipher": "ccmp", "pmf": "optional"},
    "wpa3-802.1x": {"policy": "wpa3", "akm": "dot1x", "cipher": "gcmp256", "pmf": "required"},
}


def _vendor_key(vendor: str) -> str:
    for prefix, key in _VENDOR_KEYS.items():
        if vendor.startswith(prefix):
            return key
    return "huawei_vrp"


async def wireless_collect(state: dict, tools: Any) -> dict:
    """采集需求：面积 + 用户数 + 楼层 + 场景 + 现有 AP。"""
    scenario = state.get("scenario", "office")
    if scenario not in SCENARIO_PROFILE:
        scenario = "office"
    return {**state, "scenario": scenario, "profile": SCENARIO_PROFILE[scenario]}


async def wireless_plan(state: dict, tools: Any) -> dict:
    """AP 数量规划：面积驱动 + 容量驱动，取较大值。"""
    area = int(state.get("area_sqm", 500))
    users = int(state.get("users", 100))
    floors = max(1, int(state.get("floors", 1)))
    profile = state.get("profile") or SCENARIO_PROFILE["office"]

    # 双约束：覆盖（面积）与容量（用户数），取较大者
    by_area = -(-area // profile["area_per_ap"])          # ceil
    by_capacity = -(-users // profile["users_per_ap"])    # ceil
    ap_per_floor = max(2, by_area, by_capacity)
    total_aps = ap_per_floor * floors

    return {
        **state,
        "plan": {
            "total_aps": total_aps,
            "ap_per_floor": ap_per_floor,
            "floors": floors,
            "sizing": {
                "by_coverage": by_area,
                "by_capacity": by_capacity,
                "binding_constraint": "capacity" if by_capacity > by_area else "coverage",
            },
            "capacity": {
                "per_ap_users": profile["users_per_ap"],
                "total_capacity": total_aps * profile["users_per_ap"],
            },
        },
    }


async def wireless_rf_plan(state: dict, tools: Any) -> dict:
    """射频规划：信道复用（同层错开 + 层间偏移）+ 功率 + 信道带宽。"""
    plan = state.get("plan", {})
    profile = state.get("profile") or SCENARIO_PROFILE["office"]
    total = int(plan.get("total_aps", 0))
    per_floor = max(1, int(plan.get("ap_per_floor", 1)))
    band_width = int(state.get("channel_width_mhz", 40))

    channels_5g = (
        CHANNELS_5G_80 if band_width >= 80
        else CHANNELS_5G_40 if band_width >= 40
        else CHANNELS_5G_20
    )

    ap_plan = []
    for i in range(total):
        floor = i // per_floor + 1
        idx_in_floor = i % per_floor
        # 层间偏移：不同楼层错开起始信道，减少垂直同频干扰
        offset_2g = (floor - 1) % len(CHANNELS_2G)
        offset_5g = (floor - 1) % len(channels_5g)
        ap_plan.append({
            "ap_id": i + 1,
            "ap_name": f"ap-{i + 1:02d}",
            "floor": floor,
            "channel_2g": CHANNELS_2G[(idx_in_floor + offset_2g) % len(CHANNELS_2G)],
            "channel_5g": channels_5g[(idx_in_floor + offset_5g) % len(channels_5g)],
            "channel_width_mhz": band_width,
            "power": profile["power"],
        })

    # 同层同频复用间隔（越大越好；3 个 2.4G 信道决定上限）
    reuse_distance = len(CHANNELS_2G)
    return {
        **state,
        "plan": {**plan, "ap_plan": ap_plan},
        "rf_plan": {
            "channel_width_mhz": band_width,
            "channels_2g": CHANNELS_2G,
            "channels_5g": channels_5g,
            "tx_power_percent": profile["power"],
            "reuse_distance_2g": reuse_distance,
            "band_steering": True,
            "dfs_required": any(52 <= c <= 144 for c in channels_5g),
        },
    }


async def wireless_roaming_security(state: dict, tools: Any) -> dict:
    """漫游域 + 安全策略：802.11r/k/v + WPA2/WPA3 + 802.1X。"""
    ssid = state.get("ssid", "Corp-WiFi")
    security = state.get("security", "wpa2-psk")
    if security not in SECURITY_PROFILE:
        security = "wpa2-psk"
    sec = SECURITY_PROFILE[security]
    plan = state.get("plan", {})
    total_aps = int(plan.get("total_aps", 0))

    # 漫游域：同 SSID + 同 mobility domain，AP 多时分组避免大二层泛洪
    aps_per_domain = 32
    domain_count = max(1, -(-total_aps // aps_per_domain))

    roaming = {
        "mobility_domain": ssid.lower().replace(" ", "-"),
        "domain_count": domain_count,
        "fast_transition": {
            "802.11r": True,
            "ft_over_ds": total_aps <= aps_per_domain,  # 小规模用 over-the-DS
            "802.11k": True,   # 邻居报告，加速扫描
            "802.11v": True,   # BSS transition management
        },
        "pmk_caching": True,
        "okc": security.endswith("802.1x"),  # 802.1X 才有 OKC 意义
    }
    security_policy = {
        "profile": security,
        "policy": sec["policy"],
        "akm": sec["akm"],
        "cipher": sec["cipher"],
        "pmf": sec["pmf"],
        "client_isolation": state.get("client_isolation", False),
        "radius": {"required": sec["akm"] == "dot1x",
                   "server": state.get("radius_server", "10.0.0.10")}
        if sec["akm"] == "dot1x" else None,
    }
    return {**state, "roaming": roaming, "security_policy": security_policy}


async def wireless_suggest_config(state: dict, tools: Any) -> dict:
    """生成配置：SSID + 射频 + 漫游 + 安全策略模板渲染。"""
    from app.services.template_loader import TemplateError, render

    vendor_key = _vendor_key(state.get("vendor", "huawei"))
    plan = state.get("plan", {})
    rf = state.get("rf_plan", {})
    roaming = state.get("roaming", {})
    sec = state.get("security_policy", {})
    ap_plan = plan.get("ap_plan", [])
    first_ap = ap_plan[0] if ap_plan else {
        "ap_id": 1, "ap_name": "ap-01", "channel_2g": 1, "channel_5g": 36, "power": 70,
    }
    ssid = state.get("ssid", "Corp-WiFi")

    configs: dict[str, str] = {}
    for feature in ("ssid", "roaming"):
        template_id = f"{vendor_key}_wireless_{feature}"
        try:
            configs[feature] = render(template_id, {
                "radio_name": f"radio-{first_ap['ap_name']}",
                "channel": first_ap["channel_5g"],
                "power": first_ap["power"],
                "security_name": f"sec-{ssid}",
                "ssid": ssid,
                "security_policy": sec.get("policy", "wpa2"),
                "psk_passphrase": state.get("psk_passphrase", "changeme123"),
                "traffic_name": f"traffic-{ssid}",
                "vap_name": f"vap-{ssid}",
                "ap_group_name": f"group-{ssid}",
                "ap_id": first_ap["ap_id"],
                "ap_mac": f"00:1a:{first_ap['ap_id']:02x}:00:00:01",
                "ap_name": first_ap["ap_name"],
                "mobility_domain": roaming.get("mobility_domain", "corp"),
            })
        except (TemplateError, KeyError):
            continue

    recommendations = [
        f"部署 {plan.get('total_aps', 0)} 台 AP（{plan.get('ap_per_floor', 0)} 台/层，"
        f"约束={plan.get('sizing', {}).get('binding_constraint', 'coverage')}）",
        f"射频：5G {rf.get('channel_width_mhz', 40)}MHz，"
        f"2.4G 信道 {rf.get('channels_2g', CHANNELS_2G)} 复用",
        f"发射功率 {rf.get('tx_power_percent', 70)}%（高密场景降功率提复用）",
        f"漫游：802.11r/k/v 全开，mobility domain={roaming.get('mobility_domain', '')}，"
        f"{roaming.get('domain_count', 1)} 个漫游域",
        f"安全：{sec.get('profile', 'wpa2-psk')}（{sec.get('cipher', 'ccmp')}，"
        f"PMF {sec.get('pmf', 'optional')}）",
    ]
    if rf.get("dfs_required"):
        recommendations.append("5G 使用 DFS 信道，需确认雷达检测合规")
    if sec.get("radius"):
        recommendations.append(f"802.1X 需 RADIUS：{sec['radius']['server']}")
    if not configs:
        recommendations.append(f"该厂商（{vendor_key}）无无线模板，仅输出规划")

    return {
        **state,
        "config": configs.get("ssid", ""),
        "configs": configs,
        "template_used": f"{vendor_key}_wireless_ssid",
        "recommendations": recommendations,
    }
