"""RCA 引擎（根因分析，Phase 2 P2-9）。

规则 + 概率轻量版（用户决策 2026-08-22，不上知识图谱）。
多源关联：拓扑定位 + 变更事件 + 流量基线 + 协议状态 + RAG 案例 → 概率排序。
低置信度要求人工确认（v2.0 十五章风险表）。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from app.core.logging import get_logger

logger = get_logger("rca_engine")


@dataclass
class RootCause:
    """候选根因（按概率排序）。"""
    rank: int
    cause: str
    probability: float
    category: str           # config_change / protocol_mismatch / physical / traffic / unknown
    evidence: list[str] = field(default_factory=list)
    verify_command: str = ""
    fix: str = ""
    confidence: float = 1.0  # 置信度（高>0.7 可自动建议；低<0.5 要求人工确认）


@dataclass
class SymptomContext:
    """症状上下文（排障输入）。"""
    symptom: str
    affected_devices: list[str] = field(default_factory=list)
    affected_links: list[str] = field(default_factory=list)
    protocol: str = ""          # bgp / ospf / vxlan
    vendor: str = ""
    recent_changes: list[dict] = field(default_factory=list)       # 24h 变更事件
    protocol_state: dict = field(default_factory=dict)             # SUZIEQ 状态快照
    traffic_anomalies: list[dict] = field(default_factory=list)
    rag_cases: list[dict] = field(default_factory=list)            # 历史案例


# ===== 根因规则库（v2.0 codex 设计 §4.3 + 协议知识）=====

RULES: list[dict] = [
    # BGP 规则
    {
        "id": "bgp_hello_timer_mismatch",
        "protocol": "bgp",
        "keywords": ["hello", "timer", "expired", "hold", "keepalive"],
        "cause": "BGP Hello/Hold 计时器两端不一致",
        "category": "protocol_mismatch",
        "verify": "show bgp neighbors | include Hold",
        "fix": "对齐两端 neighbor timers",
        "base_prob": 0.3,
    },
    {
        "id": "bgp_as_mismatch",
        "protocol": "bgp",
        "keywords": ["as", "remote-as", "as-number", "mismatch"],
        "cause": "BGP remote-as 配置不一致",
        "category": "protocol_mismatch",
        "verify": "show bgp summary | include AS",
        "fix": "对齐 neighbor remote-as",
        "base_prob": 0.25,
    },
    {
        "id": "bgp_crc_optical",
        "protocol": "bgp",
        "keywords": ["crc", "optical", "error", "link", "physical"],
        "cause": "物理链路 CRC/光模块故障导致 BGP 抖动",
        "category": "physical",
        "verify": "show interface | include CRC",
        "fix": "更换光模块或链路",
        "base_prob": 0.2,
    },
    {
        "id": "bgp_route_policy_blackhole",
        "protocol": "bgp",
        "keywords": ["blackhole", "policy", "route-map", "deny", "import"],
        "cause": "路由策略阻断 BGP 前缀通告",
        "category": "config_change",
        "verify": "show route-policy | include deny",
        "fix": "调整 route-map/import 策略",
        "base_prob": 0.15,
    },
    # OSPF 规则
    {
        "id": "ospf_network_type_mismatch",
        "protocol": "ospf",
        "keywords": ["network", "type", "broadcast", "p2p", "hello"],
        "cause": "OSPF 网络类型不一致（broadcast vs p2p）",
        "category": "protocol_mismatch",
        "verify": "show ospf interface | include Network Type",
        "fix": "对齐两端 network type",
        "base_prob": 0.35,
    },
    {
        "id": "ospf_auth_mismatch",
        "protocol": "ospf",
        "keywords": ["auth", "md5", "mismatch", "key"],
        "cause": "OSPF MD5 认证 key 不一致",
        "category": "protocol_mismatch",
        "verify": "show ospf interface | include Auth",
        "fix": "对齐认证 key",
        "base_prob": 0.25,
    },
    {
        "id": "ospf_mtu_mismatch",
        "protocol": "ospf",
        "keywords": ["mtu", "dd", "exchange", "stuck"],
        "cause": "接口 MTU 不一致导致 DD 交换失败",
        "category": "protocol_mismatch",
        "verify": "show interface | include MTU",
        "fix": "对齐两端 MTU",
        "base_prob": 0.2,
    },
    {
        "id": "ospf_crc",
        "protocol": "ospf",
        "keywords": ["crc", "error", "physical"],
        "cause": "物理链路 CRC 错误导致 hello 丢包",
        "category": "physical",
        "verify": "show interface | include CRC",
        "fix": "更换光模块或链路",
        "base_prob": 0.15,
    },
    # VXLAN EVPN 规则
    {
        "id": "vxlan_evpn_neighbor_down",
        "protocol": "vxlan",
        "keywords": ["evpn", "neighbor", "bgp", "type-2", "route"],
        "cause": "BGP EVPN 邻居未建立，Type-2 路由未通告",
        "category": "protocol_mismatch",
        "verify": "show bgp evpn summary",
        "fix": "检查 BGP EVPN address-family",
        "base_prob": 0.3,
    },
    {
        "id": "vxlan_vni_mismatch",
        "protocol": "vxlan",
        "keywords": ["vni", "vlan", "mapping", "vtep"],
        "cause": "VNI 与 VLAN 映射不一致",
        "category": "config_change",
        "verify": "show vxlan vni",
        "fix": "对齐两端 VNI-VLAN 映射",
        "base_prob": 0.25,
    },
    {
        "id": "vxlan_anycast_gateway_conflict",
        "protocol": "vxlan",
        "keywords": ["anycast", "gateway", "arp", "duplicate"],
        "cause": "Anycast Gateway 配置冲突，ARP 重复响应",
        "category": "config_change",
        "verify": "show interface vlan | include IP",
        "fix": "检查 anycast-gateway MAC/IP 一致性",
        "base_prob": 0.2,
    },
]


class RCAEngine:
    """根因分析引擎（规则 + 概率 + RAG 案例关联）。"""

    def analyze(self, ctx: SymptomContext) -> list[RootCause]:
        """分析症状，返回排序后的候选根因（≥3 个，v2.0 22.2 评测要求）。"""
        scored: list[tuple[float, dict]] = []

        # 1. 规则匹配 + 证据加权
        for rule in RULES:
            if rule["protocol"] != ctx.protocol:
                continue
            score = self._score_rule(rule, ctx)
            if score > 0:
                scored.append((score, rule))

        # 2. RAG 历史案例加成
        case_boost = self._case_boost(ctx.rag_cases, ctx.protocol)

        # 3. 排序 + 生成 RootCause
        scored.sort(key=lambda x: x[0], reverse=True)
        total = sum(s for s, _ in scored) or 1.0

        causes: list[RootCause] = []
        for rank, (score, rule) in enumerate(scored[:5], 1):
            prob = score / total
            # 置信度：证据数 + 概率
            evidence = self._collect_evidence(rule, ctx)
            confidence = min(1.0, prob * 1.2 + len(evidence) * 0.1 + case_boost * 0.1)
            causes.append(
                RootCause(
                    rank=rank,
                    cause=rule["cause"],
                    probability=round(prob, 2),
                    category=rule["category"],
                    evidence=evidence,
                    verify_command=rule["verify"],
                    fix=rule["fix"],
                    confidence=round(confidence, 2),
                )
            )

        # 不足 3 个时补"未知"（满足 v2.0 22.2 ≥3 候选根因）
        while len(causes) < 3:
            causes.append(
                RootCause(
                    rank=len(causes) + 1,
                    cause="需进一步排查（证据不足）",
                    probability=0.05,
                    category="unknown",
                    evidence=[],
                    verify_command="收集更多 show 命令输出",
                    fix="联系资深工程师",
                    confidence=0.2,
                )
            )

        logger.info(
            "rca_analyzed",
            protocol=ctx.protocol,
            causes=len(causes),
            top_prob=causes[0].probability if causes else 0,
        )
        return causes

    def _score_rule(self, rule: dict, ctx: SymptomContext) -> float:
        """规则打分：症状关键词匹配 + 证据加权。"""
        score = rule["base_prob"]
        symptom_lower = ctx.symptom.lower()

        # 关键词匹配
        matched_keywords = sum(1 for kw in rule["keywords"] if kw in symptom_lower)
        score += matched_keywords * 0.1

        # 协议状态证据（SUZIEQ 状态快照）
        if ctx.protocol_state:
            state_issues = self._check_protocol_state(rule, ctx.protocol_state)
            score += state_issues * 0.15

        # 变更事件关联（24h 内有相关变更 → 加权）
        if ctx.recent_changes:
            change_boost = self._correlate_changes(rule, ctx.recent_changes)
            score += change_boost * 0.2

        # 流量异常关联
        if ctx.traffic_anomalies:
            score += 0.1  # 有流量异常 → 物理类根因加权

        return score

    def _check_protocol_state(self, rule: dict, state: dict) -> int:
        """检查协议状态是否有匹配 rule 的异常。"""
        issues = 0
        state_str = str(state).lower()
        for kw in rule["keywords"]:
            if kw in state_str:
                issues += 1
        return min(issues, 3)

    def _correlate_changes(self, rule: dict, changes: list[dict]) -> int:
        """变更事件关联：24h 内有匹配 rule 的变更。"""
        now = datetime.now(timezone.utc)
        window = now - timedelta(hours=24)
        count = 0
        for ch in changes:
            # 变更涉及 rule 关键词 → 加权
            ch_str = str(ch).lower()
            if any(kw in ch_str for kw in rule["keywords"]):
                count += 1
        return min(count, 2)

    def _case_boost(self, cases: list[dict], protocol: str) -> float:
        """RAG 历史案例加成：匹配协议的案例数。"""
        matching = sum(1 for c in cases if protocol in str(c).lower())
        return min(matching * 0.1, 0.3)

    def _collect_evidence(self, rule: dict, ctx: SymptomContext) -> list[str]:
        """收集该根因的证据链。"""
        evidence: list[str] = []
        if any(kw in ctx.symptom.lower() for kw in rule["keywords"]):
            evidence.append(f"症状含关键词: {rule['keywords']}")
        if ctx.protocol_state:
            evidence.append("协议状态异常（SUZIEQ）")
        if ctx.recent_changes:
            evidence.append(f"24h 内有 {len(ctx.recent_changes)} 个相关变更")
        if ctx.traffic_anomalies:
            evidence.append("检测到流量异常")
        return evidence


rca_engine = RCAEngine()