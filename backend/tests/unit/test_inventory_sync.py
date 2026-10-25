"""测试数三层口径自校验（v0.5.0 审查修复）。

原 conftest.test_inventory() 返回硬编码数字且（作为 conftest 内函数）
根本不会被 pytest 收集——数字漂移（292/501 → 实际 288/506）从未被发现。
现 conftest 用收集钩子精确计数，本文件按目录域断言声明值与实际一致
（域内文件全部收集才校验：单文件运行/部分收集自动跳过该域，兼容
CI 的 `pytest tests/unit` + `pytest tests/e2e` 分开跑法）。
新增/删除测试后此测试会红，须同步 conftest.INVENTORY 与 CHANGELOG。
"""
from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import INVENTORY, _collected

_TESTS_DIR = Path(__file__).resolve().parents[1]


def _scope_complete(scope: str) -> bool:
    """该目录域的测试文件是否被本次运行完整收集。"""
    disk = {f"{scope}/{p.name}" for p in (_TESTS_DIR / scope).glob("test_*.py")}
    collected = {rel for rel in _collected.get("files", set()) if rel.startswith(f"{scope}/")}
    return bool(collected) and collected == disk


def test_inventory_in_sync() -> None:
    checks: list[tuple[str, int]] = []
    if _scope_complete("unit"):
        checks += [
            ("unit_functions", len(_collected.get("unit", set()))),
            ("unit_cases", len(_collected.get("unit_cases", set()))),
        ]
    if _scope_complete("e2e"):
        checks.append(("e2e_scenarios", len(_collected.get("e2e", set()))))
    if not checks:
        pytest.skip("部分收集（单文件/子集运行），跳过口径校验")
    drifted = {key: actual for key, actual in checks if INVENTORY[key] != actual}
    assert not drifted, (
        f"测试数漂移：声明 {INVENTORY}，实际 {drifted}；"
        "请更新 tests/conftest.py 的 INVENTORY 并同步 CHANGELOG 口径"
    )
