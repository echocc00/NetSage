"""NetAI-Bench 评测 Runner（v2.0 二十二章 22.4）。

加载题目 YAML → 调 Agent → 按 grading_rubric 打分 → 报告。
题目出题由资深网络工程师（用户）负责，AI 工程师标注 + 跑评测。

用法：python -m eval.runner.run_all [--limit N] [--category troubleshoot]
"""
from __future__ import annotations

import asyncio
import json
import sys
from collections import Counter
from dataclasses import asdict
from pathlib import Path

import yaml

from eval.runner import EvalQuestion, grade, load_dataset


async def run_bench(limit: int | None = None, category: str | None = None) -> dict:
    """跑全量评测，返回统计报告。"""
    questions = load_dataset()
    if category:
        questions = [q for q in questions if q.category == category]
    if limit:
        questions = questions[:limit]

    results = []
    for q in questions:
        # 模拟 Agent 响应（真实场景调 build_runner + 对应 Agent）
        # 这里用 expected_output 作为"完美响应"验证 grade 逻辑
        resp = _mock_agent_response(q)
        g = grade(resp, q)
        results.append({**g, "category": q.category, "vendor": q.vendor, "difficulty": q.difficulty})

    # 统计
    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    by_cat = Counter()
    by_vendor = Counter()
    for r in results:
        by_cat[r["category"]] += 1 if r["passed"] else 0
        by_vendor[r["vendor"]] += 1 if r["passed"] else 0

    return {
        "total": total,
        "passed": passed,
        "pass_rate": round(passed / total, 3) if total else 0,
        "by_category": dict(by_cat),
        "by_vendor": dict(by_vendor),
        "avg_score": round(sum(r["score"] for r in results) / total, 2) if total else 0,
    }


def _mock_agent_response(q: EvalQuestion) -> str:
    """模拟 Agent 响应（用 expected_output 构造，验证 grade 逻辑）。

    生产模式：替换为 build_runner().run(agent_name, state)。
    """
    exp = q.expected_output
    if q.category == "troubleshoot":
        causes = exp.get("root_causes", [])
        parts = [c.get("cause", "") + " " + c.get("verify", "") + " " + c.get("fix", "") for c in causes]
        return " ".join(parts) + " " + " ".join(q.grading_rubric.get("must_have", []))
    if q.category == "config":
        return exp.get("config", "") + " " + " ".join(q.grading_rubric.get("must_have", []))
    return " ".join(q.grading_rubric.get("must_have", []))


def main():
    limit = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else None
    category = sys.argv[sys.argv.index("--category") + 1] if "--category" in sys.argv else None

    report = asyncio.run(run_bench(limit=limit, category=category))
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
