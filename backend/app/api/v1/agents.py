"""Agent 会话 API（v2.0 五章 + 十二章 UX）。

POST /agents/sessions  发起 Agent 会话
GET  /agents/sessions/{id}/stream  SSE 流式推送 DAG 进度
（v0.5.0 审查修复：此前 docstring 宣称此路由但未实现，前端 EventSource 404）
"""
from __future__ import annotations

import json
import secrets
import time
import uuid
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.agents.registry import build_runner
from app.core.config import get_settings
from app.core.deps import CurrentUser, get_current_user, require_permission
from app.core.logging import get_logger
from app.schemas.common import Envelope

router = APIRouter(prefix="/agents", tags=["agents"])
logger = get_logger("api_agents")

# 会话与流票据（进程内；SSE 为进度通道，重建会话即可，不落库）
_sessions: dict[str, dict] = {}
_STREAM_TICKET_TTL_S = 120
_tickets: dict[str, tuple[str, float]] = {}  # ticket → (session_id, expires_at)


def _issue_stream_ticket(session_id: str) -> str:
    """签发一次性流票据（EventSource 无法带 Authorization 头，避免 token 进 URL）。"""
    ticket = secrets.token_urlsafe(24)
    _tickets[ticket] = (session_id, time.time() + _STREAM_TICKET_TTL_S)
    return ticket


def _consume_stream_ticket(ticket: str, session_id: str) -> bool:
    entry = _tickets.get(ticket)
    if entry is None:
        return False
    del _tickets[ticket]  # 单次使用
    return entry[0] == session_id and entry[1] > time.time()


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
    stream_ticket: str = ""  # SSE 一次性票据（120s）


@router.post("/sessions", response_model=Envelope[AgentSession])
async def create_session(
    req: AgentRequest,
    user: CurrentUser = Depends(get_current_user),
) -> Envelope[AgentSession]:
    """发起 Agent 会话：Planner 分类 → 路由到子 Agent。"""
    runner = build_runner()
    state = {
        "query": req.query,
        "vendor": req.vendor,
        "device": req.device,
        "context": req.context,
    }
    result = await runner.run("planner", state, session_id="init")

    session_id = uuid.uuid4().hex[:16]
    session = AgentSession(
        session_id=session_id,
        intent=result.get("intent", "config"),
        scenario=result.get("scenario", "bgp"),
        primary_agent=result.get("primary_agent", "config_engineer"),
        requires_approval=result.get("requires_approval", True),
        stream_ticket=_issue_stream_ticket(session_id),
    )
    _sessions[session_id] = {"request": req.model_dump(), "classification": session.model_dump()}
    return Envelope.ok(session)


@router.get("/sessions/{session_id}/stream")
async def stream_session(
    session_id: str,
    ticket: str = "",
    user: CurrentUser = Depends(get_current_user),
) -> StreamingResponse:
    """SSE 流式推送主责 Agent 的 DAG 执行进度。

    EventSource 无法携带 Authorization 头，鉴权用 POST /sessions 签发的
    一次性 ticket（120s TTL，单次使用）；已登录用户 + 有效 ticket 双条件。
    """
    sess = _sessions.get(session_id)
    if sess is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "会话不存在或已过期")
    if not ticket or not _consume_stream_ticket(ticket, session_id):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "stream ticket 无效或已使用")

    req = sess["request"]
    classification = sess["classification"]
    primary = classification.get("primary_agent", "config_engineer")
    vendor = req.get("vendor") or "huawei"

    async def event_stream() -> AsyncIterator[str]:
        def sse(payload: dict) -> str:
            return f"data: {json.dumps(payload, ensure_ascii=False, default=str)}\n\n"

        yield sse({"event": "start", "agent": primary, "session_id": session_id})
        runner = build_runner()
        state = {
            "query": req.get("query", ""),
            "symptom": req.get("query", ""),
            "vendor": vendor,
            "device": (req.get("context") or {}).get("device", {}),
            "scenario": classification.get("scenario", "bgp"),
            "protocol_state": (req.get("context") or {}).get("protocol_state", {}),
            "recent_changes": (req.get("context") or {}).get("recent_changes", []),
            "context": req.get("context") or {},
        }
        try:
            async for event in runner.stream(primary, state, session_id=session_id):
                yield sse({"event": "step", **{k: v for k, v in event.items() if k != "state"}})
                if "state" in event:
                    yield sse({"event": "state", "state": _safe_subset(event["state"])})
            yield sse({"event": "done", "agent": primary})
        except Exception as e:
            logger.error("sse_stream_failed", session_id=session_id, error=str(e))
            yield sse({"event": "error", "error": str(e)})

    return StreamingResponse(event_stream(), media_type="text/event-stream")


def _safe_subset(state: dict) -> dict:
    """状态瘦身推送（剔除超大字段，SSE 只做进度通道）。"""
    keep = ("intent", "scenario", "primary_agent", "lint_passed", "validation_passed",
            "requires_approval", "can_auto_fix", "root_causes", "evidence")
    return {k: state[k] for k in keep if k in state}


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
    change_id: int | None = Field(
        None, description="关联变更单 id（生产必填，校验其状态须为 approved）"
    )


@router.post("/sessions/{session_id}/deploy", response_model=Envelope[dict])
async def run_deploy(
    session_id: str,
    req: DeployRequest,
    user: CurrentUser = Depends(require_permission("deploy")),
) -> Envelope[dict]:
    """执行 DeployAgent（顺序下发 + checkpoint + 自动回滚，v2.0 十章）。

    需 admin 权限（deploy）。v0.5.0 审查修复：此前路由自写
    change_status="approved" 绕过审批前置校验——现生产环境（非 dev）
    必须携带 change_id 且对应变更单状态为 approved，否则 409。
    """
    settings = get_settings()
    change_status = "approved"
    verified = False
    if req.change_id is not None:
        from app.services.change_store import get_change_store

        rec = await get_change_store().get(req.change_id)
        if rec is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"变更单 {req.change_id} 不存在")
        if rec.status != "approved":
            raise HTTPException(
                status.HTTP_409_CONFLICT, f"变更单 {req.change_id} 状态 {rec.status}，未审批不可下发"
            )
        verified = True
    elif not settings.is_dev:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "生产环境必须携带 change_id（经三道闸审批的变更单）"
        )

    runner = build_runner()
    state = {
        "devices": req.devices,
        "configs": req.configs,
        "snapshots": req.snapshots,
        "nim": req.nim,
        "change_status": change_status,
        "deployed": [],
    }
    result = await runner.run("deploy", state, session_id=session_id)
    return Envelope.ok({
        "deployed": result.get("deployed", []),
        "failed": result.get("failed"),
        "rollback_status": result.get("rollback_status"),
        "verify_passed": result.get("verify_passed", False),
        "approval_verified": verified,
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
    auto_approve: bool = Field(False, description="演示模式：自动跳过审批。仅 dev 生效，生产服务端强制 False")


@router.post("/closed-loop", response_model=Envelope[dict])
async def run_closed_loop(
    req: ClosedLoopRequest,
    user: CurrentUser = Depends(require_permission("deploy")),
) -> Envelope[dict]:
    """故障自动诊断→修复→验证→审批→下发→监控 全闭环（v2.0 Phase 3 M6 里程碑）。

    需 deploy 权限（admin）。自动化率 ≥30%。
    v0.5.0 审查修复（P0）：auto_approve 原为纯请求参数，任何人传 true
    即跳过人工审批直达下发——现服务端强制：非 dev 环境恒为 False。
    """
    from app.agents.closed_loop import ClosedLoopOrchestrator

    settings = get_settings()
    auto_approve = req.auto_approve
    if auto_approve and not settings.is_dev:
        logger.warning("auto_approve_forced_off", user_id=user.id)
        auto_approve = False

    runner = build_runner()
    orch = ClosedLoopOrchestrator(runner=runner)
    result = await orch.run(req.symptom, req.vendor, auto_approve=auto_approve)
    from app.audit.service import get_audit_sink

    await get_audit_sink().append(
        user_id=user.id,
        action="agent.closed_loop",
        resource_type="agent_session",
        resource_id=None,
        after=json.dumps(
            {"symptom": req.symptom, "approved": result.approved,
             "automation_rate": round(result.automation_rate, 2)},
            ensure_ascii=False,
        ),
    )
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
