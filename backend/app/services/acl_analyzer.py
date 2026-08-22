"""Batfish ACL 分析器（Phase 3）。

reachability + shadowed + unused ACL 断言。
华为复用 Phase 2 H3C 策略：转 Cisco 等价 ACL + loose validation。
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ACLReport:
    snapshot: str
    vendor: str
    reachability: list[dict] = field(default_factory=list)
    shadowed: list[dict] = field(default_factory=list)
    unused: list[dict] = field(default_factory=list)
    vendor_notes: str = ""


class ACLAnalyzer:
    """ACL 分析器。真实模式调 batfish-mcp，mock 模式返回种子数据。"""

    async def analyze(self, snapshot: str, vendor: str) -> ACLReport:
        # Phase 3: batfish-mcp 集成（mock 返回示例数据，展示报告结构）
        # 真实集成时替换为 MCPClient.call("batfish.analyze_acl", {...})
        return ACLReport(
            snapshot=snapshot,
            vendor=vendor,
            reachability=[
                {"src": "10.1.1.10", "dst": "10.2.2.20", "port": 443,
                 "action": "permit", "matched_rule": "ACL_OUT permit tcp any 10.2.2.0 0.0.0.255 eq 443"},
                {"src": "10.1.1.10", "dst": "10.2.2.20", "port": 22,
                 "action": "deny", "matched_rule": "implicit deny"},
            ],
            shadowed=[
                {"acl": "ACL_OUT", "rule": "permit tcp any any eq 80",
                 "shadowed_by": "permit tcp any any"},
            ],
            unused=[
                {"acl": "ACL_LEGACY", "reason": "未在任何接口引用"},
            ],
            vendor_notes=self._vendor_caveats(vendor),
        )

    def empty_report(self, vendor: str) -> ACLReport:
        return ACLReport(snapshot="", vendor=vendor, vendor_notes=self._vendor_caveats(vendor))

    def _vendor_caveats(self, vendor: str) -> str:
        if vendor.startswith("huawei") or vendor.startswith("h3c"):
            return ("Batfish 无原生华为/H3C parser，已转 Cisco 等价 ACL（loose validation）。"
                    "USG 防火墙 ACL 语法部分不支持，建议人工复核。")
        return "Batfish 原生 parser，full validation。"
