"""变更审批 API（v2.0 十章 + 十九章）。

POST /changes          创建变更请求（engineer）
GET  /changes          变更单列表
POST /changes/{id}/run 跑三道闸（snapshot→sim→val→approval）
POST /changes/{id}/approve  审批（admin）
POST /changes/{id}/deploy   下发（admin，审批后）
GET  /changes/{id}/impact   影响范围报告（自动推演+人工确认）

v0.5.0 修复（审查 P0/P1）：
- 三道闸原就地 new MockToolRegistry 并 stub 闸门必过——现改用启动装配的
  全局注册表（TOOLS_BACKEND=mcp 时走真实 MCP server；mock 模式响应明示）。
- 变更单原存进程内 dict（重启即失/多 worker 不可见）——现经 ChangeStore
  落库（DB 可用）或内存回退。
- 生命周期动作（create/run/approve/deploy）接入审计哈希链（fail-closed：
  审计写不进则操作中止）。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.agents.registry import get_tools, tools_mode
from app.audit.service import get_audit_sink
from app.core.deps import CurrentUser, CurrentUserDep, require_permission
from app.core.logging import get_logger
from app.gates.impact import ImpactAnalyzer
from app.gates.pipeline import GatePipeline, PipelineContext
from app.gates.snapshot import StoreBackedObjectStore
from app.schemas.common import Envelope
from app.services.change_store import ChangeRecord, get_change_store

router = APIRouter(prefix="/changes", tags=["changes"])
logger = get_logger("api_changes")


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


async def _audit(
    *,
    user_id: int | None,
    action: str,
    resource_id: str | None,
    after: str | None = None,
) -> None:
    """审计写入（fail-closed）：写不进审计链则中止操作。"""
    try:
        ok = await get_audit_sink().append(
            user_id=user_id,
            action=action,
            resource_type="change_request",
            resource_id=resource_id,
            before=None,
            after=after,
        )
        if not ok:
            raise RuntimeError("审计写入返回失败")
    except Exception as e:
        logger.error("audit_write_failed", action=action, error=str(e))
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "审计链写入失败，操作中止") from e


@router.post("", response_model=Envelope[ChangeOut])
async def create_change(
    req: ChangeCreate,
    user: CurrentUser = Depends(require_permission("draft_change")),
) -> Envelope[ChangeOut]:
    """创建变更请求（engineer/admin，需 draft_change 权限）。"""
    store = get_change_store()
    impact = ImpactAnalyzer().analyze(req.nim, req.devices)
    rec = await store.create(
        title=req.title,
        nim=req.nim,
        devices=req.devices,
        configs=req.configs,
        assertions=req.assertions,
        impact=impact.to_dict(),
        created_by=user.id,
    )
    await _audit(user_id=user.id, action="change.create", resource_id=str(rec.id),
                 after=f"status=draft,title={rec.title}")
    return Envelope.ok(ChangeOut(id=rec.id, title=rec.title, status=rec.status, impact=rec.impact))


@router.get("", response_model=Envelope[dict])
async def list_changes(
    user: CurrentUserDep,
    limit: int = 50,
) -> Envelope[dict]:
    """变更单列表（审查修复：前端审批页原调用此路由 405）。

    count 为全库真实总数（stats），items 截断到 limit（默认 50，按 id 降序）。
    """
    store = get_change_store()
    items = await store.list(limit=limit)
    stats = await store.stats()
    return Envelope.ok({
        "count": int(stats.get("total", len(items))),
        "storage": store.mode,
        "items": [
            {"id": r.id, "title": r.title, "status": r.status,
             "impact_confirmed": bool(r.impact.get("confirmed_by"))}
            for r in items
        ],
    })


async def _get_or_404(change_id: int) -> ChangeRecord:
    rec = await get_change_store().get(change_id)
    if rec is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "变更不存在")
    return rec


@router.get("/{change_id}/impact", response_model=Envelope[dict])
async def get_impact(
    change_id: int,
    user: CurrentUserDep,
) -> Envelope[dict]:
    """获取影响范围报告（自动推演，待工程师确认）。"""
    rec = await _get_or_404(change_id)
    return Envelope.ok(rec.impact)


@router.post("/{change_id}/impact/confirm", response_model=Envelope[dict])
async def confirm_impact(
    change_id: int,
    modified: dict,
    user: CurrentUser = Depends(require_permission("draft_change")),
) -> Envelope[dict]:
    """工程师确认/修改影响范围（自动推演+人工确认）。"""
    store = get_change_store()
    await _get_or_404(change_id)  # 404 守卫
    modified = dict(modified)
    modified["confirmed_by"] = user.name
    updated = await store.update_impact(change_id, modified)
    assert updated is not None  # _get_or_404 已保证存在
    return Envelope.ok(updated.impact)


@router.post("/{change_id}/run", response_model=Envelope[dict])
async def run_gates(
    change_id: int,
    user: CurrentUser = Depends(require_permission("draft_change")),
) -> Envelope[dict]:
    """跑三道闸：快照→仿真→校验→审批 pending。

    工具来自启动装配的全局注册表：TOOLS_BACKEND=mcp 走真实
    containerlab/batfish/napalm；默认 mock 模式闸门必过（响应明示）。
    """
    rec = await _get_or_404(change_id)
    store = get_change_store()
    tools = get_tools()
    pipeline = GatePipeline(tools, snapshot_store=StoreBackedObjectStore(store, change_id))
    ctx = PipelineContext(
        request_id=change_id,
        nim=rec.nim,
        devices=rec.devices,
        configs=rec.configs,
        assertions=rec.assertions,
        tools=tools,
    )
    result = await pipeline.run(ctx)
    result["tools_mode"] = tools_mode()
    updated = await store.update_status(change_id, result.get("status", "unknown"), pipeline_result=result)
    assert updated is not None
    await _audit(user_id=user.id, action="change.run_gates", resource_id=str(change_id),
                 after=f"status={updated.status},tools_mode={result['tools_mode']}")
    return Envelope.ok(result)


@router.post("/{change_id}/approve", response_model=Envelope[dict])
async def approve_change(
    change_id: int,
    decision: str,  # approved / rejected
    user: CurrentUser = Depends(require_permission("approve")),
) -> Envelope[dict]:
    """审批变更（admin，需 approve 权限）。"""
    if decision not in ("approved", "rejected"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "decision 须为 approved/rejected")
    rec = await _get_or_404(change_id)
    if rec.status != "approval":
        raise HTTPException(status.HTTP_409_CONFLICT, f"当前状态 {rec.status} 不可审批")
    store = get_change_store()
    new_status = "approved" if decision == "approved" else "rejected"
    updated = await store.update_status(change_id, new_status)
    assert updated is not None
    await store.save_approval(change_id, approver_id=user.id, decision=decision)
    await _audit(user_id=user.id, action="change.approve", resource_id=str(change_id),
                 after=f"decision={decision},status={new_status}")
    return Envelope.ok({"change_id": change_id, "status": new_status, "approver": user.name})


@router.post("/{change_id}/deploy", response_model=Envelope[dict])
async def deploy_change(
    change_id: int,
    user: CurrentUser = Depends(require_permission("deploy")),
) -> Envelope[dict]:
    """下发变更（admin，需 deploy 权限，审批后）。"""
    rec = await _get_or_404(change_id)
    if rec.status != "approved":
        raise HTTPException(status.HTTP_409_CONFLICT, "未审批，不可下发")

    store = get_change_store()
    tools = get_tools()
    pipeline = GatePipeline(tools, snapshot_store=StoreBackedObjectStore(store, change_id))
    ctx = PipelineContext(
        request_id=change_id,
        nim=rec.nim,
        devices=rec.devices,
        configs=rec.configs,
        assertions=rec.assertions,
        tools=tools,
    )
    # 下发前抓新鲜快照（跨 worker 也可回滚：快照正文已落 ChangeStore）
    for dev in ctx.devices:
        snap = await pipeline.snapshot.capture(
            dev["id"], dev["vendor"], dev["host"], dev["username"], dev["password"], dev.get("port", 22)
        )
        ctx.snapshots.append(snap)
    result = await pipeline.deploy(ctx)
    result["tools_mode"] = tools_mode()
    await store.update_status(change_id, result.get("status", "done"), pipeline_result=result)
    await _audit(user_id=user.id, action="change.deploy", resource_id=str(change_id),
                 after=f"status={result.get('status')},tools_mode={result['tools_mode']}")
    return Envelope.ok(result)
