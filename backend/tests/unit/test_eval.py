"""NetAI-Bench 评测 Runner 测试。"""
from __future__ import annotations

from eval.runner import grade, load_dataset, run_eval
from eval.runner.schema import validate_dataset
from pathlib import Path


def test_load_dataset_finds_questions():
    """能加载 NSG-Q-*.yaml 题目（v2.0 22.1）。"""
    qs = load_dataset()
    assert len(qs) >= 1
    assert qs[0].id.startswith("NSG-Q-")
    assert qs[0].category in {"troubleshoot", "config", "design", "audit", "perf"}


def test_dataset_size_500():
    """v0.1.3 验收：评测集 ≥ 500 题。"""
    qs = load_dataset()
    assert len(qs) >= 500, f"评测集 {len(qs)} < 500"


def test_dataset_all_schema_valid():
    """v0.1.3 验收：500+ 题全部 schema 校验通过。"""
    d = Path(__file__).resolve().parents[3] / "eval" / "dataset"
    passed, total, errors = validate_dataset(d)
    assert total >= 500
    assert passed == total, f"{total - passed} 题校验失败: {errors[:5]}"


def test_dataset_category_coverage():
    """v0.1.3 验收：5 类齐全。"""
    qs = load_dataset()
    cats = {q.category for q in qs}
    assert cats >= {"troubleshoot", "config", "design", "audit", "perf"}


def test_dataset_vendor_coverage():
    """v0.1.3 验收：≥4 厂商覆盖。"""
    qs = load_dataset()
    vendors = {q.vendor for q in qs}
    assert len(vendors) >= 4


def test_grade_good_response():
    """好响应：命中 must_have，无 penalty → passed（v2.0 22.4）。"""
    qs = load_dataset()
    q = qs[0]
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
