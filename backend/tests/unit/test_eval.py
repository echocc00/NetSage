"""NetAI-Bench 评测 Runner 测试。"""
from __future__ import annotations

from eval.runner import grade, load_dataset, run_eval


def test_load_dataset_finds_questions():
    """能加载 NSG-Q-*.yaml 题目（v2.0 22.1）。"""
    qs = load_dataset()
    assert len(qs) >= 1
    assert qs[0].id.startswith("NSG-Q-")
    assert qs[0].category in {"troubleshoot", "config", "design", "audit", "perf"}


def test_grade_good_response():
    """好响应：命中 must_have，无 penalty → passed（v2.0 22.4）。"""
    qs = load_dataset()
    q = qs[0]
    # 构造一个命中 must_have 的响应
    resp = "根因：光模块 CRC。验证：display interface。修复：更换光模块。"
    result = grade(resp, q)
    assert result["penalty_hits"] == 0


def test_grade_penalty_for_restart():
    """推荐重启设备 → penalty 扣分（v2.0 22.2 anti_examples）。"""
    qs = load_dataset()
    q = qs[0]
    resp = "请重启设备解决"
    result = grade(resp, q)
    assert result["penalty_hits"] > 0
    assert not result["passed"]


def test_run_eval_returns_report():
    report = run_eval(agent_response_fn=None)
    assert "total" in report
    assert "hit_rate" in report
    assert report["total"] >= 1
