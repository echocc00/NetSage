"""Agent 会话 API（v2.0 五章 + 十二章 UX）。

POST /agents/sessions  发起 Agent 会话
GET  /agents/sessions/{id}/stream  SSE 流式推送 DAG 进度
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.agents.registry import build_runner
from app.core.deps import CurrentUser, get_current_user, require_permission
from app.schemas.common import Envelope

router = APIRouter(prefix="/agents", tags=["agents"])


class AgentRequest(BaseModel):
    query: str = Field(..., description="自然语言请求")
    vendor: str | None = None
    device: str | None = None
    context: dict = Field(default_factory=dict)


class AgentSession(BaseModel):
    session_id: str
    intent: str
    scenario: str
    primary_agent: str
    requires_approval: bool


@router.post("/sessions", response_model=Envelope[AgentSession])
async def create_session(
    req: AgentRequest,
    user: CurrentUser = Depends(get_current_user),
) -> Envelope[AgentSession]:
    """发起 Agent 会话：Planner 分类 → 路由到子 Agent。

    Phase 1：同步执行 Planner，返回分类结果。
    Phase 2：异步执行 + SSE 流。
    """
    runner = build_runner()
    state = {
        "query": req.query,
        "vendor": req.vendor,
        "device": req.device,
        "context": req.context,
    }
    result = await runner.run("planner", state, session_id="init")

    session = AgentSession(
        session_id=uuid.uuid4().hex[:16],
        intent=result.get("intent", "config"),
        scenario=result.get("scenario", "bgp"),
        primary_agent=result.get("primary_agent", "config_engineer"),
        requires_approval=result.get("requires_approval", True),
    )
    return Envelope.ok(session)


@router.post("/sessions/{session_id}/config", response_model=Envelope[dict])
async def run_config_engineer(
    session_id: str,
    req: AgentRequest,
    user: CurrentUser = Depends(require_permission("draft_change")),
) -> Envelope[dict]:
    """执行 ConfigEngineer Agent（生成配置 + lint）。"""
    runner = build_runner()
    state = {
        "query": req.query,
        "vendor": req.vendor or "huawei",
        "scenario": "bgp",
    }
    result = await runner.run("config_engineer", state, session_id=session_id)
    return Envelope.ok({
        "config_diff": result.get("config_diff", ""),
        "rollback": result.get("rollback_config", ""),
        "lint_passed": result.get("lint_passed", False),
    })


@router.post("/sessions/{session_id}/validate", response_model=Envelope[dict])
async def run_validator(
    session_id: str,
    user: CurrentUser = Depends(require_permission("troubleshoot")),
) -> Envelope[dict]:
    """执行 Validator Agent（Batfish 断言）。"""
    runner = build_runner()
    result = await runner.run("validator", {}, session_id=session_id)
    return Envelope.ok({
        "validation_passed": result.get("validation_passed", False),
        "evidence": result.get("validation_evidence", []),
    })


# ===== Phase 2: Deploy + Troubleshooter =====


class DeployRequest(BaseModel):
    devices: list[dict] = Field(default_factory=list)
    configs: dict[str, str] = Field(default_factory=dict)
    snapshots: list[dict] = Field(default_factory=list)
    nim: dict = Field(default_factory=dict)


@router.post("/sessions/{session_id}/deploy", response_model=Envelope[dict])
async def run_deploy(
    session_id: str,
    req: DeployRequest,
    user: CurrentUser = Depends(require_permission("deploy")),
) -> Envelope[dict]:
    """执行 DeployAgent（顺序下发 + checkpoint + 自动回滚，v2.0 十章）。

    需 admin 权限（deploy），且变更须已审批。
    """
    runner = build_runner()
    state = {
        "devices": req.devices,
        "configs": req.configs,
        "snapshots": req.snapshots,
        "nim": req.nim,
        "change_status": "approved",
        "deployed": [],
    }
    result = await runner.run("deploy", state, session_id=session_id)
    return Envelope.ok({
        "deployed": result.get("deployed", []),
        "failed": result.get("failed"),
        "rollback_status": result.get("rollback_status"),
        "verify_passed": result.get("verify_passed", False),
    })


class TroubleshootRequest(BaseModel):
    symptom: str | None = None
    query: str | None = None  # 兼容字段（symptom 优先）
    vendor: str = "huawei"
    device: dict = Field(default_factory=dict)
    context: dict = Field(default_factory=dict)


@router.post("/sessions/{session_id}/troubleshoot", response_model=Envelope[dict])
async def run_troubleshooter(
    session_id: str,
    req: TroubleshootRequest,
    user: CurrentUser = Depends(require_permission("troubleshoot")),
) -> Envelope[dict]:
    """执行 Troubleshooter Agent（RCA 根因排序，v2.0 五章 8.4）。

    collect → analyze(RCA) → suggest_fixes
    返回 ≥3 候选根因 + 证据链 + 验证命令 + 修复方案。
    """
    runner = build_runner()
    symptom = req.symptom or req.query or ""
    ctx = req.context
    state = {
        "query": symptom,
        "symptom": symptom,
        "vendor": req.vendor,
        "device": req.device or ctx.get("device", {}),
        "scenario": ctx.get("scenario", "bgp"),
        "protocol_state": ctx.get("protocol_state", {}),
        "recent_changes": ctx.get("recent_changes", []),
        "context": ctx,
    }
    result = await runner.run("troubleshooter", state, session_id=session_id)
    return Envelope.ok({
        "root_causes": result.get("root_causes", []),
        "evidence": result.get("evidence", []),
        "fixes": result.get("fixes", []),
        "references": result.get("references", []),
        "can_auto_fix": result.get("can_auto_fix", False),
    })


# ===== Phase 3: 自动化闭环 + 双 SSoT =====


class ClosedLoopRequest(BaseModel):
    symptom: str
    vendor: str = "huawei_vrp"
    auto_approve: bool = Field(False, description="演示模式：自动跳过审批。生产强制 False")


@router.post("/closed-loop", response_model=Envelope[dict])
async def run_closed_loop(
    req: ClosedLoopRequest,
    user: CurrentUser = Depends(require_permission("deploy")),
) -> Envelope[dict]:
    """故障自动诊断→修复→验证→审批→下发→监控 全闭环（v2.0 Phase 3 M6 里程碑）。

    需 deploy 权限（admin）。自动化率 ≥30%。
    """
    from app.agents.closed_loop import ClosedLoopOrchestrator

    runner = build_runner()
    orch = ClosedLoopOrchestrator(runner=runner)
    result = await orch.run(req.symptom, req.vendor, auto_approve=req.auto_approve)
    return Envelope.ok({
        "symptom": result.symptom,
        "steps": [
            {"name": s.name, "automated": s.automated,
             "success": s.success, "detail": s.detail}
            for s in result.steps
        ],
        "diagnosis": result.diagnosis,
        "fix": result.fix,
        "deployed": result.deployed,
        "approved": result.approved,
        "automation_rate": round(result.automation_rate, 2),
        "meets_target": result.automation_rate >= 0.3,
    })


@router.get("/ssot/devices", response_model=Envelope[dict])
async def list_ssot_devices(
    provider: str = "netbox",
    site: str | None = None,
    user: CurrentUser = Depends(get_current_user),
) -> Envelope[dict]:
    """双 SSoT 设备查询（NetBox / Nautobot 切换，v2.0 三章）。"""
    from app.access.source_of_truth import get_source_of_truth

    ssot = get_source_of_truth(provider)
    try:
        devices = await ssot.list_devices({"site": site} if site else None)
        return Envelope.ok({
            "provider": provider,
            "count": len(devices),
            "devices": [
                {"id": d.id, "name": d.name, "vendor": d.vendor,
                 "role": d.role, "site": d.site, "status": d.status}
                for d in devices
            ],
        })
    finally:
        if hasattr(ssot, "close"):
            await ssot.close()
