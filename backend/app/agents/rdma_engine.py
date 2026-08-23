"""RoCE 诊断引擎（Phase 4 RdmAgent，规则 + 概率，复用 RCA 模式）。

从症状 + 计数器推断 RoCE 丢包/延迟瓶颈（PFC/ECN/buffer/MTU）。
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RoCECause:
    cause_id: str
    cause: str
    probability: float
    category: str              # pfc / ecn / buffer / mtu / physical
    verify: str = ""
    fix: str = ""
    confidence: float = 1.0


# RoCE 诊断规则库（v2.0 5.1 RdmAgent + RDMA 知识）
RULES: list[dict] = [
    {
        "id": "pfc_watchdog_disabled",
        "keywords": ["pfc", "pause", "drop", "storm", "暂停"],
        "cause": "PFC watchdog 未启用导致暂停风暴",
        "category": "pfc",
        "verify": "display dcb pfc | include watchdog",
        "fix": "启用 PFC watchdog（watchdog enable + interval 100）",
        "base_prob": 0.3,
    },
    {
        "id": "ecn_missing",
        "keywords": ["congestion", "latency", "拥塞", "延迟", "ecn"],
        "cause": "ECN 未启用导致拥塞无反馈",
        "category": "ecn",
        "verify": "display roce ecn",
        "fix": "配置 ECN 阈值（150KB）+ CE 标记",
        "base_prob": 0.25,
    },
    {
        "id": "dcqcn_disabled",
        "keywords": ["throughput", "allreduce", "吞吐", "dcqcn"],
        "cause": "DCQCN 未启用导致发送端不降速",
        "category": "ecn",
        "verify": "display roce dcqcn",
        "fix": "启用 DCQCN（alpha 0.5, k_min 1, k_max 100）",
        "base_prob": 0.2,
    },
    {
        "id": "mtu_mismatch",
        "keywords": ["fragment", "mtu", "分片", "drop"],
        "cause": "MTU 不一致导致分片丢包",
        "category": "mtu",
        "verify": "display interface | include MTU",
        "fix": "对齐两端 MTU 9100（jumbo frame）",
        "base_prob": 0.15,
    },
    {
        "id": "buffer_exhaustion",
        "keywords": ["drop", "buffer", "缓冲", "egress"],
        "cause": "egress buffer 耗尽（headroom 不足）",
        "category": "buffer",
        "verify": "display qos buffer",
        "fix": "增大 headroom（10KB）+ 共享 buffer",
        "base_prob": 0.15,
    },
    {
        "id": "priority_mismatch",
        "keywords": ["pfc", "priority", "优先级", "vlan"],
        "cause": "PFC 优先级两端不一致",
        "category": "pfc",
        "verify": "display dcb pfc",
        "fix": "对齐两端 PFC priority（建议 3）",
        "base_prob": 0.1,
    },
    {
        "id": "link_error",
        "keywords": ["crc", "error", "symbol", "physical"],
        "cause": "物理层误码（CRC/symbol error）",
        "category": "physical",
        "verify": "display interface | include CRC",
        "fix": "更换光模块/线缆",
        "base_prob": 0.05,
    },
]


class RoCEDiagnoseEngine:
    """RoCE 诊断引擎：症状 + 计数器 → 瓶颈定位 + 调优建议。"""

    def analyze(self, state: dict) -> dict:
        symptom = (state.get("symptom", "") + " " + str(state.get("config", ""))).lower()
        perf = state.get("perf", {})
        counters = perf.get("counters", {}) if isinstance(perf, dict) else {}

        # 计数器加权：丢包/错误计数高时提升相关根因概率
        causes: list[RoCECause] = []
        for rule in RULES:
            score = rule["base_prob"]
            matched = any(kw in symptom for kw in rule["keywords"])
            if matched:
                score *= 2.0
            # 计数器关联
            if rule["category"] == "pfc" and int(counters.get("port_xmit_discards", 0)) > 0:
                score *= 1.5
            if rule["category"] == "physical" and int(counters.get("symbol_errors", 0)) > 0:
                score *= 2.0
            if rule["category"] == "buffer" and int(counters.get("port_rcv_errors", 0)) > 10:
                score *= 1.3
            if matched or score > rule["base_prob"]:
                causes.append(RoCECause(
                    cause_id=rule["id"], cause=rule["cause"],
                    probability=min(score, 0.9), category=rule["category"],
                    verify=rule["verify"], fix=rule["fix"],
                ))

        causes.sort(key=lambda c: c.probability, reverse=True)
        if not causes:
            causes = [RoCECause(
                cause_id="unknown", cause="未知瓶颈，需人工排查",
                probability=0.1, category="unknown",
                verify="ibstat + perfquery + display interface",
                fix="收集计数器后重新诊断",
            )]

        total = sum(c.probability for c in causes) or 1
        for c in causes:
            c.probability = round(c.probability / total, 2)

        return {
            "bottleneck": causes[0].cause,
            "category": causes[0].category,
            "confidence": causes[0].probability,
            "causes": [
                {"cause_id": c.cause_id, "cause": c.cause,
                 "probability": c.probability, "category": c.category,
                 "verify": c.verify, "fix": c.fix}
                for c in causes[:3]
            ],
        }
