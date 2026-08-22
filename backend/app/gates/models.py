"""三道闸状态机与 DTO（v2.0 十章 + 开发计划十三章 13.1）。"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class ChangeStatus(StrEnum):
    """变更请求状态机。

    draft → sim_pending → val_pending → approval → deploying → done
                              ↓              ↓           ↓
                          sim_failed    rejected    failed → rolled_back
    """
    DRAFT = "draft"
    SIM_PENDING = "sim_pending"
    SIM_PASSED = "sim_passed"
    SIM_FAILED = "sim_failed"
    VAL_PENDING = "val_pending"
    VAL_PASSED = "val_passed"
    VAL_FAILED = "val_failed"
    APPROVAL = "approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    DEPLOYING = "deploying"
    DONE = "done"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"
    CLOSED = "closed"


# 合法状态流转（状态机约束）
VALID_TRANSITIONS: dict[ChangeStatus, set[ChangeStatus]] = {
    ChangeStatus.DRAFT: {ChangeStatus.SIM_PENDING},
    ChangeStatus.SIM_PENDING: {ChangeStatus.SIM_PASSED, ChangeStatus.SIM_FAILED},
    ChangeStatus.SIM_PASSED: {ChangeStatus.VAL_PENDING},
    ChangeStatus.SIM_FAILED: {ChangeStatus.DRAFT, ChangeStatus.CLOSED},  # 回炉或关闭
    ChangeStatus.VAL_PENDING: {ChangeStatus.VAL_PASSED, ChangeStatus.VAL_FAILED},
    ChangeStatus.VAL_PASSED: {ChangeStatus.APPROVAL},
    ChangeStatus.VAL_FAILED: {ChangeStatus.DRAFT, ChangeStatus.CLOSED},
    ChangeStatus.APPROVAL: {ChangeStatus.APPROVED, ChangeStatus.REJECTED},
    ChangeStatus.APPROVED: {ChangeStatus.DEPLOYING},
    ChangeStatus.REJECTED: {ChangeStatus.CLOSED},
    ChangeStatus.DEPLOYING: {ChangeStatus.DONE, ChangeStatus.FAILED},
    ChangeStatus.DONE: {ChangeStatus.CLOSED},
    ChangeStatus.FAILED: {ChangeStatus.ROLLED_BACK, ChangeStatus.CLOSED},
    ChangeStatus.ROLLED_BACK: {ChangeStatus.CLOSED},
    ChangeStatus.CLOSED: set(),
}


class IllegalTransitionError(Exception):
    """状态机非法流转。"""


def assert_transition(current: ChangeStatus, target: ChangeStatus) -> None:
    if target not in VALID_TRANSITIONS.get(current, set()):
        raise IllegalTransitionError(f"非法状态流转：{current} → {target}")


@dataclass
class GateResult:
    """单个闸的执行结果。"""
    passed: bool
    gate: str
    evidence: list[dict] = field(default_factory=list)
    error: str | None = None

    @classmethod
    def ok(cls, gate: str, evidence: list[dict] | None = None) -> "GateResult":
        return cls(passed=True, gate=gate, evidence=evidence or [])

    @classmethod
    def fail(cls, gate: str, error: str, evidence: list[dict] | None = None) -> "GateResult":
        return cls(passed=False, gate=gate, error=error, evidence=evidence or [])
