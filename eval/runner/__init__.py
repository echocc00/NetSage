"""NetAI-Bench 评测 Runner（v2.0 二十二章 22.4）。

加载题目 YAML → 调 Agent → LLM-as-judge 按 grading_rubric 打分 → 报告。
题目出题由资深网络工程师（用户）负责，AI 工程师标注 + 跑评测。
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from app.core.logging import get_logger

logger = get_logger("eval_runner")

DATASET_DIR = Path(__file__).resolve().parents[1] / "dataset"


@dataclass
class EvalQuestion:
    id: str
    title: str
    category: str
    vendor: str
    version: str
    difficulty: int
    input: dict
    expected_output: dict
    anti_examples: list[str]
    grading_rubric: dict


def load_dataset(path: Path | None = None) -> list[EvalQuestion]:
    """加载所有题目 YAML。"""
    d = path or DATASET_DIR
    questions: list[EvalQuestion] = []
    for f in sorted(d.glob("NSG-Q-*.yaml")):
        data = yaml.safe_load(f.read_text(encoding="utf-8"))
        questions.append(
            EvalQuestion(
                id=data["id"],
                title=data["title"],
                category=data["category"],
                vendor=data["vendor"],
                version=data["version"],
                difficulty=data["difficulty"],
                input=data["input"],
                expected_output=data["expected_output"],
                anti_examples=data.get("anti_examples", []),
                grading_rubric=data["grading_rubric"],
            )
        )
    return questions


def grade(response: str, question: EvalQuestion) -> dict:
    """按 grading_rubric 打分（Phase 1 简化版，Phase 2 接 LLM-as-judge）。

    Phase 1：规则匹配 must_have 关键词。
    """
    rubric = question.grading_rubric
    must_have = rubric.get("must_have", [])
    penalty = rubric.get("penalty", [])

    # 简化：检查 must_have 关键词是否在响应中
    must_hits = sum(1 for k in must_have if _keyword_match(response, k))
    penalty_hits = sum(1 for k in penalty if _keyword_match(response, k))

    score = must_hits - penalty_hits * 2
    passed = must_hits >= len(must_have) * 0.6 and penalty_hits == 0

    return {
        "question_id": question.id,
        "score": score,
        "passed": passed,
        "must_hits": must_hits,
        "penalty_hits": penalty_hits,
    }


def _keyword_match(text: str, keyword: str) -> bool:
    """宽松匹配：关键词去标点后子串匹配；中文用 2 字子串兜底。"""
    import re

    clean = re.sub(r"[≥\d\s]", "", keyword).lower()
    text_lower = text.lower()
    if not clean:
        return False
    if clean in text_lower:
        return True
    # 中文：任意 2 字子串命中即算
    for i in range(len(clean) - 1):
        if clean[i : i + 2] in text_lower:
            return True
    return False


def run_eval(agent_response_fn=None) -> dict:
    """跑全量评测集。agent_response_fn(question) -> str，None 时跳过 Agent 调用。"""
    questions = load_dataset()
    results = []
    for q in questions:
        if agent_response_fn:
            resp = agent_response_fn(q)
        else:
            resp = ""  # 占位
        results.append(grade(resp, q))

    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    report = {
        "total": total,
        "passed": passed,
        "hit_rate": passed / total if total else 0,
        "results": results,
    }
    logger.info("eval_done", total=total, passed=passed, hit_rate=report["hit_rate"])
    return report
