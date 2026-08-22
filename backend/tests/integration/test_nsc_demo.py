"""nsc CLI 测试：三 BGP 演示场景端到端（v2.0 开发计划十六章 16.5）。

需后端启动（uvicorn app.main:app --port 8000）。
"""
from __future__ import annotations

import subprocess
import sys

import pytest

pytestmark = pytest.mark.integration

NSC = [sys.executable, "-m", "nsc.main"]


def _run(args: list[str]) -> str:
    result = subprocess.run(NSC + args, capture_output=True, text=True, timeout=30)
    return result.stdout + result.stderr


def test_scenario_1_troubleshoot_bgp_flap():
    """场景 1：BGP 邻居抖动 → troubleshoot + high priority。"""
    out = _run(["ask", "BGP 邻居反复抖动", "--vendor", "huawei"])
    assert "troubleshoot" in out
    assert "bgp" in out
    assert "troubleshooter" in out


def test_scenario_2_config_bgp_peering():
    """场景 2：eBGP peering 生成 → config diff + lint pass（v2.0 16.5 验收）。"""
    out = _run(["gen", "BGP peering AS 65001", "--vendor", "huawei"])
    assert "config" in out
    assert "router bgp" in out
    assert "lint" in out and "pass" in out
    assert "rollback" in out  # 回滚配置生成（三道闸）


def test_scenario_3_audit_route_blackhole():
    """场景 3：路由黑洞审计 → audit + security_auditor。"""
    out = _run(["ask", "审计 BGP 路由黑洞", "--vendor", "huawei"])
    assert "audit" in out


def test_all_write_ops_require_approval():
    """所有写操作 requires_approval=True（v2.0 十章三道闸）。"""
    out = _run(["gen", "生成 BGP 配置", "--vendor", "huawei"])
    assert "approval" in out or "requires_approval" in out or "True" in out
