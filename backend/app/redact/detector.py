"""内容特征自动分级（v0.5.0 审查 P1 修复）。

此前敏感度分级完全信任调用方传入的 content_type 字符串——caller 传
"general_qa"（默认值）则 running-config 全文按白盒直送云端，"黑盒阻断"
形同荣誉制。现按内容特征检测配置/日志，检测命中则将 tier 上调
（白盒→灰盒强制脱敏；强配置特征→按黑盒阻断），只升不降。
"""
from __future__ import annotations

import re

# 运行配置强特征（命中即按 running_config 黑盒处理）
_RUNNING_CONFIG_SIGNALS = [
    re.compile(r"(?im)^\s*current configuration\s*$"),
    re.compile(r"(?im)^\s*#\s*Last modified"),
    re.compile(r"(?im)^\s*version\s+\d"),
    re.compile(r"(?im)^\s*sysname\s+\S+"),
]

# 配置行特征（≥3 类不同特征 → 配置片段，按灰盒脱敏后放行）
_CONFIG_LINE_SIGNALS = [
    re.compile(r"(?im)^\s*interface\s+\S+"),
    re.compile(r"(?im)^\s*router\s+(bgp|ospf|isis)\s"),
    re.compile(r"(?im)^\s*(ip|ipv4)\s+route\s"),
    re.compile(r"(?im)^\s*snmp-server\s+\w+"),
    re.compile(r"(?im)^\s*line\s+(vty|console|aux)"),
    re.compile(r"(?im)^\s*vlan\s+\d+"),
    re.compile(r"(?im)^\s*hostname\s+\S+"),
    re.compile(r"(?im)^\s*aaa\s+"),
    re.compile(r"(?im)^\s*!\s*$"),
    re.compile(r"(?im)^\s*(undo|no)\s+\w+"),
]

# 日志特征（命中 → 按 raw_logs 黑盒处理）
_LOG_SIGNALS = [
    re.compile(r"%BGP(-\d)?-[0-9A-Z-]+"),
    re.compile(r"%LINK|%LINEPROTO|%SYS(-\d)?-"),
    re.compile(r"(?im)\blevel=(warning|error|critical|alert)\b"),
    re.compile(r"(?im)\b%(EMA|ETH|OSPF)-"),
]

_RUNNING_CONFIG_THRESHOLD = 1  # 任一强特征即判 running-config
_CONFIG_FRAGMENT_THRESHOLD = 3  # ≥3 类不同配置行特征判配置片段


def detect_content_type(messages: list[dict[str, str]]) -> str | None:
    """按内容特征推断真实内容类型；无强特征返回 None（信任调用方声明）。

    只升不降：声明白盒但内容像配置/日志 → 返回更高敏感度的类型，
    由拦截器据此上调 tier。
    """
    text = "\n".join(str(m.get("content", "")) for m in messages if isinstance(m, dict))
    if not text.strip():
        return None

    strong_hits = sum(1 for pat in _RUNNING_CONFIG_SIGNALS if pat.search(text))
    if strong_hits >= _RUNNING_CONFIG_THRESHOLD:
        return "running_config"

    log_hits = sum(1 for pat in _LOG_SIGNALS if pat.search(text))
    if log_hits >= 1:
        return "raw_logs"

    config_hits = sum(1 for pat in _CONFIG_LINE_SIGNALS if pat.search(text))
    if config_hits >= _CONFIG_FRAGMENT_THRESHOLD:
        return "config_template_redacted"  # 灰盒：强制脱敏后放行

    return None
