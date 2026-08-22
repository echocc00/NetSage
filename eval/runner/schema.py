"""NetAI-Bench 题目 schema 校验器（v2.0 二十二章 22.2）。

出题后先过校验再入库，保证 50 题结构一致可评测。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

REQUIRED_FIELDS = {"id", "title", "category", "vendor", "difficulty", "input", "expected_output"}
VALID_CATEGORIES = {"troubleshoot", "config", "design", "audit", "perf"}
VALID_VENDORS = {"huawei", "cisco", "h3c", "juniper", "arista", "mellanox", "cross"}

INPUT_REQUIRED = {"symptom", "question"} if False else set()  # 占位，实际按类校验
EXPECTED_REQUIRED = {"root_causes"}


class DatasetError(Exception):
    """题目校验错误。"""


def validate_question(data: dict) -> list[str]:
    """返回错误列表；空 = 通过。"""
    errors: list[str] = []

    missing = REQUIRED_FIELDS - set(data.keys())
    if missing:
        errors.append(f"缺字段: {sorted(missing)}")
        return errors

    if data["category"] not in VALID_CATEGORIES:
        errors.append(f"非法 category: {data['category']}")
    if data["vendor"] not in VALID_VENDORS:
        errors.append(f"非法 vendor: {data['vendor']}")

    # difficulty 1-5
    if not (1 <= int(data.get("difficulty", 0)) <= 5):
        errors.append(f"difficulty 需在 1-5: {data.get('difficulty')}")

    # input
    inp = data.get("input", {})
    if "symptom" not in inp and data["category"] in ("troubleshoot", "config"):
        errors.append("input 缺 symptom（troubleshoot/config 类必填）")
    if "question" not in inp:
        errors.append("input 缺 question")

    # expected_output
    exp = data.get("expected_output", {})
    if data["category"] in ("troubleshoot", "perf"):
        if "root_causes" not in exp:
            errors.append("expected_output 缺 root_causes（troubleshoot/perf 类必填）")
        else:
            causes = exp["root_causes"]
            if len(causes) < 3:
                errors.append("root_causes 至少 3 个（v2.0 22.2）")
            for cause in causes:
                if "verify" not in cause or "fix" not in cause:
                    errors.append(f"root_cause 缺 verify/fix: {cause.get('cause', '?')[:30]}")

    # grading_rubric
    rubric = data.get("grading_rubric", {})
    if "must_have" not in rubric:
        errors.append("grading_rubric 缺 must_have")

    # anti_examples（troubleshoot 必填）
    if data["category"] == "troubleshoot" and not data.get("anti_examples"):
        errors.append("troubleshoot 类必须给 anti_examples（反例）")

    return errors


def validate_dataset(dataset_dir: Path) -> tuple[int, int, list[str]]:
    """校验整个目录。返回 (通过数, 总数, 错误列表)。"""
    passed = 0
    total = 0
    all_errors: list[str] = []
    for f in sorted(dataset_dir.glob("NSG-Q-*.yaml")):
        total += 1
        data = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        errors = validate_question(data)
        if errors:
            all_errors.append(f"{f.name}: {errors}")
        else:
            passed += 1
    return passed, total, all_errors


if __name__ == "__main__":
    dataset_dir = Path(__file__).resolve().parent.parent / "dataset"
    p, t, errs = validate_dataset(dataset_dir)
    print(f"评测集校验: {p}/{t} 通过")
    for e in errs:
        print(f"  ✗ {e}")