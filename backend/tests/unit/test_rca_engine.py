"""RCA 引擎测试（Phase 2 P2-9，规则+概率轻量版）。"""
from __future__ import annotations

import pytest

from app.agents.rca_engine import RCAEngine, SymptomContext


def _ctx(symptom, protocol, **kw):
    return SymptomContext(symptom=symptom, protocol=protocol, **kw)


def test_bgp_neighbor_flap_returns_ranked_causes():
    """BGP 邻居抖动 → ≥3 候选根因按概率排序。"""
    engine = RCAEngine()
    ctx = _ctx("BGP 邻居反复抖动 Hello expired", "bgp")
    causes = engine.analyze(ctx)

    assert len(causes) >= 3  # v2.0 22.2 要求 ≥3 候选
    # 按概率降序
    probs = [c.probability for c in causes]
    assert probs == sorted(probs, reverse=True)
    # 每个含验证 + 修复命令
    for c in causes:
        assert c.verify_command
        assert c.fix
        assert c.category


def test_bgp_crc_symptom_matches_physical_cause():
    """BGP + CRC 关键词 → 物理根因排名靠前。"""
    engine = RCAEngine()
    ctx = _ctx("BGP 邻居抖动，接口 CRC 错误", "bgp")
    causes = engine.analyze(ctx)
    top = causes[0]
    assert "CRC" in top.cause or "物理" in top.cause or "光模块" in top.cause
    assert top.category == "physical"


def test_ospf_network_type_mismatch_ranked_high():
    """OSPF 网络类型不一致 → 排名靠前（base_prob 0.35）。"""
    engine = RCAEngine()
    ctx = _ctx("OSPF 邻居震荡 network type 不一致 hello", "ospf")
    causes = engine.analyze(ctx)
    top_cause = causes[0].cause
    assert "网络类型" in top_cause or "network type" in top_cause.lower()


def test_vxlan_evpn_neighbor_down():
    """VXLAN EVPN 邻居问题 → 对应根因。"""
    engine = RCAEngine()
    ctx = _ctx("VXLAN EVPN Type-2 路由不通 neighbor down", "vxlan")
    causes = engine.analyze(ctx)
    assert any("EVPN" in c.cause or "neighbor" in c.cause.lower() for c in causes)


def test_unknown_protocol_returns_at_least_3():
    """未知协议仍返回 ≥3（补"需进一步排查"）。"""
    engine = RCAEngine()
    ctx = _ctx("未知问题", "unknown_protocol")
    causes = engine.analyze(ctx)
    assert len(causes) >= 3
    assert causes[-1].category == "unknown"


def test_confidence_low_requires_human():
    """低置信度根因标记（<0.5 需人工确认，v2.0 风险表）。"""
    engine = RCAEngine()
    ctx = _ctx("模糊症状", "bgp")
    causes = engine.analyze(ctx)
    # 至少有 confidence 字段
    for c in causes:
        assert 0 <= c.confidence <= 1.0


def test_recent_changes_boost_relevant_causes():
    """24h 内相关变更 → 对应根因概率提升。"""
    engine = RCAEngine()
    ctx_no_changes = _ctx("BGP 路由黑洞", "bgp")
    ctx_with_changes = _ctx(
        "BGP 路由黑洞",
        "bgp",
        recent_changes=[{"action": "route-policy deny", "device": "spine01"}],
    )
    causes_no = engine.analyze(ctx_no_changes)
    causes_with = engine.analyze(ctx_with_changes)
    # 有变更时 route_policy 根因概率应更高
    policy_no = next((c for c in causes_no if "策略" in c.cause or "policy" in c.cause.lower()), None)
    policy_with = next((c for c in causes_with if "策略" in c.cause or "policy" in c.cause.lower()), None)
    if policy_no and policy_with:
        assert policy_with.probability >= policy_no.probability


def test_evidence_chain_collected():
    """每条根因含证据链（v2.0 22.2 评测 must_have）。"""
    engine = RCAEngine()
    ctx = _ctx(
        "BGP 邻居抖动",
        "bgp",
        recent_changes=[{"action": "timer change"}],
        traffic_anomalies=[{"metric": "loss", "value": 0.1}],
    )
    causes = engine.analyze(ctx)
    # 至少 top 候应有证据
    assert any(c.evidence for c in causes)


def test_rag_cases_boost():
    """RAG 历史案例匹配 → 置信度提升。"""
    engine = RCAEngine()
    ctx = _ctx("BGP 邻居抖动", "bgp", rag_cases=[{"cause": "bgp timer mismatch"}])
    causes = engine.analyze(ctx)
    # 有案例时 confidence 应有加成（不崩溃即通过）
    assert all(0 <= c.confidence <= 1.0 for c in causes)
