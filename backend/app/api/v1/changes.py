"""变更审批 API（v2.0 十章 + 十九章）。

POST /changes          创建变更请求（engineer）
POST /changes/{id}/run 跑三道闸（snapshot→sim→val→approval）
POST /changes/{id}/approve  审批（admin）
POST /changes/{id}/deploy   下发（admin，审批后）
GET  /changes/{id}/impact   影响范围报告（自动推演+人工确认）
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.core.deps import CurrentUser, CurrentUserDep, require_permission
from app.gates.impact import ImpactAnalyzer
from app.gates.pipeline import GatePipeline, PipelineContext
from app.schemas.common import Envelope
from app.tools.registry import MockToolRegistry

router = APIRouter(prefix="/changes", tags=["changes"])

# Phase 1 内存存储（Phase 2 换 PostgreSQL）
_changes: dict[int, dict] = {}
_counter = [0]


class ChangeCreate(BaseModel):
    title: str
    nim: dict = Field(default_factory=dict)
    devices: list[dict] = Field(default_factory=list)
    configs: dict[str, str] = Field(default_factory=dict)
    assertions: list[dict] = Field(default_factory=list)


class ChangeOut(BaseModel):
    id: int
    title: str
    status: str
    impact: dict | None = None


@router.post("", response_model=Envelope[ChangeOut])
async def create_change(
    req: ChangeCreate,
    user: CurrentUser = Depends(require_permission("draft_change")),
) -> Envelope[ChangeOut]:
    """创建变更请求（engineer/admin，需 draft_change 权限）。"""
    _counter[0] += 1
    cid = _counter[0]
    # 自动推演影响范围（用户决策：自动推演+人工确认）
    impact = ImpactAnalyzer().analyze(req.nim, req.devices)
    _changes[cid] = {
        "id": cid,
        "title": req.title,
        "nim": req.nim,
        "devices": req.devices,
        "configs": req.configs,
        "assertions": req.assertions,
        "status": "draft",
        "impact": impact.to_dict(),
        "created_by": user.id,
    }
    return Envelope.ok(ChangeOut(id=cid, title=req.title, status="draft", impact=impact.to_dict()))


@router.get("/{change_id}/impact", response_model=Envelope[dict])
async def get_impact(
    change_id: int,
    user: CurrentUserDep,
) -> Envelope[dict]:
    """获取影响范围报告（自动推演，待工程师确认）。"""
    c = _changes.get(change_id)
    if not c:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "变更不存在")
    return Envelope.ok(c.get("impact", {}))


@router.post("/{change_id}/impact/confirm", response_model=Envelope[dict])
async def confirm_impact(
    change_id: int,
    modified: dict,
    user: CurrentUser = Depends(require_permission("draft_change")),
) -> Envelope[dict]:
    """工程师确认/修改影响范围（自动推演+人工确认）。"""
    c = _changes.get(change_id)
    if not c:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "变更不存在")
    c["impact"].update(modified)
    c["impact"]["confirmed_by"] = user.name
    return Envelope.ok(c["impact"])


@router.post("/{change_id}/run", response_model=Envelope[dict])
async def run_gates(
    change_id: int,
    user: CurrentUser = Depends(require_permission("draft_change")),
) -> Envelope[dict]:
    """跑三道闸：快照→仿真→校验→审批 pending。"""
    c = _changes.get(change_id)
    if not c:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "变更不存在")

    tools = MockToolRegistry()
    # 预设 mock 响应
    tools.stub("napalm.get_config", lambda **kw: {"config": "running-config-mock"})
    tools.stub("containerlab.deploy_topology", lambda **kw: {"status": "deployed"})
    tools.stub("containerlab.exec_on_node", lambda **kw: {"stdout": "Up"})
    tools.stub("batfish.lint_config", lambda **kw: {"passed": True})
    tools.stub("batfish.assert_reachability", lambda **kw: {"passed": True})
    tools.stub("batfish.assert_routing", lambda **kw: {"passed": True})

    pipeline = GatePipeline(tools)
    ctx = PipelineContext(
        request_id=change_id,
        nim=c["nim"],
        devices=c["devices"],
        configs=c["configs"],
        assertions=c["assertions"],
        tools=tools,
    )
    result = await pipeline.run(ctx)
    c["status"] = result.get("status", "unknown")
    c["pipeline_result"] = result
    return Envelope.ok(result)


@router.post("/{change_id}/approve", response_model=Envelope[dict])
async def approve_change(
    change_id: int,
    decision: str,  # approved / rejected
    user: CurrentUser = Depends(require_permission("approve")),
) -> Envelope[dict]:
    """审批变更（admin，需 approve 权限）。"""
    c = _changes.get(change_id)
    if not c:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "变更不存在")
    if c["status"] != "approval":
        raise HTTPException(status.HTTP_409_CONFLICT, f"当前状态 {c['status']} 不可审批")
    c["status"] = "approved" if decision == "approved" else "rejected"
    return Envelope.ok({"change_id": change_id, "status": c["status"], "approver": user.name})


@router.post("/{change_id}/deploy", response_model=Envelope[dict])
async def deploy_change(
    change_id: int,
    user: CurrentUser = Depends(require_permission("deploy")),
) -> Envelope[dict]:
    """下发变更（admin，需 deploy 权限，审批后）。"""
    c = _changes.get(change_id)
    if not c:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "变更不存在")
    if c["status"] != "approved":
        raise HTTPException(status.HTTP_409_CONFLICT, "未审批，不可下发")

    tools = MockToolRegistry()
    tools.stub("napalm.get_config", lambda **kw: {"config": "running-config-mock"})
    tools.stub("napalm.load_merge_candidate", lambda **kw: {"status": "candidate_loaded"})
    tools.stub("napalm.commit", lambda **kw: {"status": "committed"})

    pipeline = GatePipeline(tools)
    ctx = PipelineContext(
        request_id=change_id,
        nim=c["nim"],
        devices=c["devices"],
        configs=c["configs"],
        assertions=c["assertions"],
        tools=tools,
    )
    # 先抓快照（deploy 前置）
    for dev in ctx.devices:
        snap = await pipeline.snapshot.capture(
            dev["id"], dev["vendor"], dev["host"], dev["username"], dev["password"], dev.get("port", 22)
        )
        ctx.snapshots.append(snap)
    result = await pipeline.deploy(ctx)
    c["status"] = result.get("status", "done")
    return Envelope.ok(result)
