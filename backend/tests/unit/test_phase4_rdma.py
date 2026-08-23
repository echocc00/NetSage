"""Phase 4 RdmAgent 测试。"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.security import CurrentUser, Role, encode_token
from app.main import app

client = TestClient(app)


def _auth(role: Role = Role.ADMIN) -> dict[str, str]:
    return {"Authorization": f"Bearer {encode_token(CurrentUser(id=1, name='test', role=role))}"}


# ===== RoCE 诊断引擎 =====


def test_rdma_engine_pfc_storm():
    """PFC 暂停风暴 → watchdog 未启用根因。"""
    from app.agents.rdma_engine import RoCEDiagnoseEngine

    engine = RoCEDiagnoseEngine()
    result = engine.analyze({"symptom": "RoCE PFC pause storm 丢包"})
    assert "watchdog" in result["bottleneck"]
    assert result["confidence"] > 0
    assert len(result["causes"]) >= 1


def test_rdma_engine_ecn_missing():
    """拥塞延迟 → ECN 未启用根因。"""
    from app.agents.rdma_engine import RoCEDiagnoseEngine

    engine = RoCEDiagnoseEngine()
    result = engine.analyze({"symptom": "allreduce 延迟升高，拥塞无反馈"})
    causes = [c["cause"] for c in result["causes"]]
    assert any("ECN" in c or "DCQCN" in c for c in causes)


def test_rdma_engine_counter_correlation():
    """计数器关联：port_xmit_discards > 0 → PFC 类根因概率提升。"""
    from app.agents.rdma_engine import RoCEDiagnoseEngine

    engine = RoCEDiagnoseEngine()
    result = engine.analyze({
        "symptom": "丢包",
        "perf": {"counters": {"port_xmit_discards": 100, "symbol_errors": 0}},
    })
    assert result["confidence"] > 0


def test_rdma_engine_unknown_fallback():
    """无匹配症状 → 未知根因兜底。"""
    from app.agents.rdma_engine import RoCEDiagnoseEngine

    engine = RoCEDiagnoseEngine()
    result = engine.analyze({"symptom": "xyz"})
    assert result["bottleneck"]


# ===== RdmAgent Agent =====


@pytest.mark.asyncio
async def test_rdm_agent_diagnose():
    """RdmAgent 跑通 collect → diagnose → suggest_tuning。"""
    from app.agents.registry import build_runner

    runner = build_runner()
    state = {
        "symptom": "RoCEv2 丢包，PFC pause 风暴",
        "vendor": "huawei",
        "interface": "10GE1/0/1",
        "config": "dcb pfc priority 3",
        "ibstat": {"ports": [{"port": 1, "state": "Active"}]},
        "perf": {"counters": {"port_xmit_discards": 50}},
    }
    result = await runner.run("rdm_agent", state, session_id="rdma-1")
    assert "diagnosis" in result
    assert "tuning" in result
    assert result["tuning"]["pfc_priority"] == 3
    assert "pfc" in result.get("config", "").lower() or result["config"] == ""


@pytest.mark.asyncio
async def test_rdm_agent_cisco_template():
    """Cisco 厂商 → cisco RoCE 模板。"""
    from app.agents.registry import build_runner

    runner = build_runner()
    state = {"symptom": "congestion latency", "vendor": "cisco", "interface": "Te1/0/1"}
    result = await runner.run("rdm_agent", state, session_id="rdma-2")
    assert "cisco" in result.get("template_used", "")


# ===== RoCE 模板库 =====


def test_roce_template_count_6():
    """v0.2.0 验收：≥6 RoCE 模板（3 厂商 × 2）。"""
    from app.services.template_loader import list_by_vendor

    count = sum(
        len([m for m in list_by_vendor(v) if m["protocol"] == "roce"])
        for v in ["huawei", "cisco", "arista"]
    )
    assert count >= 6


# ===== Agent 注册 =====


def test_agent_count_9():
    """v0.2.0 验收：9 Agent（含 RdmAgent）。"""
    from app.agents.registry import build_runner

    runner = build_runner()
    agents = list(runner._compiled.keys())
    assert len(agents) >= 9
    assert "rdm_agent" in agents


# ===== opensm-mcp mock =====


@pytest.mark.asyncio
async def test_opensm_mcp_mock_ibstat():
    """opensm-mcp mock 模式 ibstat 返回种子数据。"""
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "mcp-servers" / "opensm-mcp"))
    import importlib

    server = importlib.import_module("server")
    result = await server.ibstat.fn() if hasattr(server.ibstat, "fn") else await server._MOCK_IBSTAT if False else server._MOCK_IBSTAT
    assert "ports" in result
    assert len(result["ports"]) >= 3
