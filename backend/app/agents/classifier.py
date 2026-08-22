"""意图分类体系（用户决策 2026-08-21：6×7 矩阵）。

intent（6 类）× scenario（7 类）= 42 格，对齐 v2.0 四章能力矩阵。
Planner 用此矩阵路由到对应 Agent + 工具集。
"""
from __future__ import annotations

from enum import StrEnum
from dataclasses import dataclass


class Intent(StrEnum):
    """6 类意图（v2.0 能力矩阵场景行）。"""
    DESIGN = "design"          # 架构设计
    CONFIG = "config"          # 配置生成
    TROUBLESHOOT = "troubleshoot"  # 故障排查
    AUDIT = "audit"            # 配置审计
    PERFORMANCE = "performance"  # 性能优化
    CAPACITY = "capacity"      # 容量规划


class Scenario(StrEnum):
    """7 类协议场景（v2.0 能力矩阵协议列）。"""
    OSPF = "ospf"
    BGP = "bgp"
    VXLAN = "vxlan"     # VXLAN/EVPN
    VPN = "vpn"          # MPLS VPN / IPsec / SSL
    WIRELESS = "wireless"
    ROCE = "roce"        # RoCE/IB
    SECURITY = "security"


# intent → 主责 Agent 映射
INTENT_AGENT_MAP: dict[Intent, str] = {
    Intent.DESIGN: "planner",
    Intent.CONFIG: "config_engineer",
    Intent.TROUBLESHOOT: "troubleshooter",
    Intent.AUDIT: "security_auditor",
    Intent.PERFORMANCE: "perf_analyst",
    Intent.CAPACITY: "planner",
}

# intent × scenario → 优先级（高/中/低，影响 SLA 与是否强制人审）
PRIORITY_MAP: dict[tuple[Intent, Scenario], str] = {
    (Intent.TROUBLESHOOT, Scenario.BGP): "high",
    (Intent.TROUBLESHOOT, Scenario.OSPF): "high",
    (Intent.TROUBLESHOOT, Scenario.VXLAN): "high",
    (Intent.TROUBLESHOOT, Scenario.ROCE): "high",
    (Intent.CONFIG, Scenario.SECURITY): "high",
    (Intent.AUDIT, Scenario.SECURITY): "high",
}
DEFAULT_PRIORITY = "medium"


@dataclass
class ClassifiedIntent:
    """意图分类结果（Planner 输出）。"""
    intent: Intent
    scenario: Scenario
    priority: str
    vendor: str | None = None
    version: str | None = None
    confidence: float = 1.0

    @property
    def primary_agent(self) -> str:
        return INTENT_AGENT_MAP[self.intent]

    @property
    def requires_human_approval(self) -> bool:
        """所有写操作（config/audit 高优先）强制人审（v2.0 十章三道闸）。"""
        if self.intent in (Intent.CONFIG, Intent.AUDIT):
            return True
        return self.priority == "high"


# 关键词路由表（Planner 用，Phase 1 规则匹配；Phase 2 换 LLM 分类）
INTENT_KEYWORDS: dict[Intent, list[str]] = {
    # 注意："新建" 类动词与配置对象词（peering/专线）组合时归 config（审查中发现的交集场景）
    Intent.DESIGN: ["设计", "规划", "架构", "拓扑", "方案", "架构设计", "扩容规划", "design"],
    Intent.CONFIG: ["配置", "生成", "下发", "修改", "peering", "专线", "隧道", "config", "generate"],
    Intent.TROUBLESHOOT: ["故障", "排障", "为什么", "不通", "抖动", "震荡", "troubleshoot"],
    Intent.AUDIT: ["审计", "合规", "检查", "基线", "audit", "compliance"],
    Intent.PERFORMANCE: ["性能", "延迟", "优化", "调优", "perf", "latency"],
    Intent.CAPACITY: ["容量", "扩容", "带宽", "capacity"],
}

SCENARIO_KEYWORDS: dict[Scenario, list[str]] = {
    Scenario.OSPF: ["ospf", "邻居", "adjacency", "lsdb"],
    Scenario.BGP: ["bgp", "邻居", "peer", "前缀", "as-path", "route-reflector"],
    Scenario.VXLAN: ["vxlan", "evpn", "vni", "vtep"],
    Scenario.VPN: ["vpn", "ipsec", "mpls", "l3vpn", "ssl"],
    Scenario.WIRELESS: ["无线", "wifi", "wlan", "ap", "漫游", "wireless"],
    Scenario.ROCE: ["roce", "ib", "infiniband", "rdma", "pfc", "ecn"],
    Scenario.SECURITY: ["安全", "acl", "防火墙", "攻击", "security"],
}


def classify(query: str) -> ClassifiedIntent:
    """规则匹配分类（Phase 1）。Phase 2 换 LLM 零样本分类。"""
    q = query.lower()
    intent = _match_enum(q, INTENT_KEYWORDS, Intent.CONFIG)
    scenario = _match_enum(q, SCENARIO_KEYWORDS, Scenario.BGP)
    priority = PRIORITY_MAP.get((intent, scenario), DEFAULT_PRIORITY)
    return ClassifiedIntent(intent=intent, scenario=scenario, priority=priority)


def _match_enum[T: StrEnum](text: str, table: dict[T, list[str]], default: T) -> T:
    scores: dict[T, int] = {k: 0 for k in table}
    for key, words in table.items():
        for w in words:
            if w in text:
                scores[key] += 1
    best = max(scores, key=lambda k: scores[k])
    return best if scores[best] > 0 else default
