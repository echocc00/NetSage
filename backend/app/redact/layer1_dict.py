"""Layer 1: 静态字典脱敏（确定性）。

正则 + 字典 → 占位符替换（v2.0 20.2）。
Phase 1 必做，覆盖 8 类 PII：IPV4/IPV6/MAC/ASN/密码/SNMP community/邮箱/内部主机名。
"""
from __future__ import annotations

import re

from .mapping import MappingTable

# (key, compiled_pattern)
# 顺序敏感：
# - 邮箱优先于主机名（含 @）
# - MAC 必须在 IPv6 前（6 段 2 位会被 IPv6 正则吞掉）
# - 主机名在 IPv4 前（避免域名里的 IP 段被先替换）
PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    # 邮箱优先
    ("EMAIL", re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b")),
    # 内部主机名
    ("HOST", re.compile(r"\b[\w-]+\.(corp|internal|local|intranet)\b", re.IGNORECASE)),
    # MAC（在 IPv6 前，避免被 IPv6 正则误匹配）
    ("MAC", re.compile(r"\b[0-9a-fA-F]{2}(?::[0-9a-fA-F]{2}){5}\b")),
    # IPv6（支持 :: 缩写：fe80::1 / 2001:db8::1 / 完整 8 段）
    ("IPV6", re.compile(
        r"\b(?:[0-9a-fA-F]{1,4}:){1,7}[0-9a-fA-F]{1,4}\b"                       # 无 :: 完整形式
        r"|\b(?:[0-9a-fA-F]{1,4}:){1,6}:[0-9a-fA-F]{0,4}\b"                     # 前缀含 ::
        r"|\b[0-9a-fA-F]{0,4}(?::[0-9a-fA-F]{1,4}){1,6}:[0-9a-fA-F]{0,4}\b"     # 中间/尾部含 ::
    )),
    # IPv4
    ("IPV4", re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")),
    # ASN
    ("ASN", re.compile(r"\bAS\s?\d{2,6}\b", re.IGNORECASE)),
    # 密码（关键字后跟非空白）
    ("PASS", re.compile(r"(password|passwd|pwd|secret)\s+\S+", re.IGNORECASE)),
    # SNMP community
    ("SNMP", re.compile(r"community\s+\S+", re.IGNORECASE)),
]


class Layer1Redactor:
    """静态字典脱敏：确定性，可逆。"""

    def redact(self, text: str, mapping: MappingTable) -> str:
        """对文本应用所有正则，替换为占位符。"""
        if not text:
            return text

        # 密码/community 整段替换为 REDACTED（不保留原值特征）
        text = PATTERNS[6][1].sub(
            lambda m: self._redact_keyword(m, mapping, "PASS"), text
        )
        text = PATTERNS[7][1].sub(
            lambda m: self._redact_keyword(m, mapping, "SNMP"), text
        )

        # 其余类别替换为带编号占位符（保留可还原性）
        for key, pat in PATTERNS[:6]:
            text = pat.sub(lambda m, k=key: mapping.add(k, m.group(0)), text)
        return text

    @staticmethod
    def _redact_keyword(match: re.Match, mapping: MappingTable, key: str) -> str:
        """password/community 行：关键字保留，值替换为 [REDACTED]。"""
        full = match.group(0)
        keyword = re.match(r"(\w+)", full).group(1)
        mapping.add(key, full)  # 仍记录映射供审计
        return f"{keyword} [REDACTED]"

    def redact_dict(self, data: dict, mapping: MappingTable) -> dict:
        """递归脱敏 dict 的所有字符串值。"""
        return self._walk(data, mapping)

    def _walk(self, obj, mapping):
        if isinstance(obj, str):
            return self.redact(obj, mapping)
        if isinstance(obj, dict):
            return {k: self._walk(v, mapping) for k, v in obj.items()}
        if isinstance(obj, list):
            return [self._walk(v, mapping) for v in obj]
        return obj
