"""RDMA 诊断 API（Phase 4 RdmAgent）。

POST /rdma/diagnose    RoCE 丢包/延迟诊断
GET  /rdma/ibstat      IB 端口状态（opensm-mcp）
POST /rdma/fabric      保存 RdmaFabric 设计
GET  /rdma/fabrics     列出 Fabric 设计
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.core.deps import CurrentUser, get_current_user, require_permission
from app.schemas.common import Envelope

router = APIRouter(prefix="/rdma", tags=["rdma"])


class DiagnoseRequest(BaseModel):
    symptom: str
    vendor: str = "huawei"
    interface: str = "10GE1/0/1"
    config: str = ""
    perf: dict = Field(default_factory=dict)


@router.post("/diagnose", response_model=Envelope[dict])
async def diagnose(
    req: DiagnoseRequest,
    user: CurrentUser = Depends(get_current_user),
) -> Envelope[dict]:
    """RoCE 丢包/延迟诊断（RdmAgent，Phase 4）。"""
    from app.agents.registry import build_runner

    runner = build_runner()
    state = {
        "symptom": req.symptom, "vendor": req.vendor,
        "interface": req.interface, "config": req.config,
        "ibstat": {}, "perf": req.perf,
    }
    result = await runner.run("rdm_agent", state, session_id="rdma-api")
    return Envelope.ok({
        "diagnosis": result.get("diagnosis", {}),
        "tuning": result.get("tuning", {}),
        "config": result.get("config", ""),
        "template_used": result.get("template_used", ""),
    })


@router.get("/ibstat", response_model=Envelope[dict])
async def get_ibstat(
    user: CurrentUser = Depends(get_current_user),
) -> Envelope[dict]:
    """IB 端口状态（opensm-mcp mock）。"""
    return Envelope.ok({
        "node": "spine01-rdma",
        "ports": [
            {"port": 1, "state": "Active", "rate": "100 Gb/s", "lid": 1},
            {"port": 2, "state": "Active", "rate": "100 Gb/s", "lid": 1},
            {"port": 3, "state": "Down", "rate": "—", "lid": 0},
        ],
    })


class FabricCreate(BaseModel):
    name: str
    site: str = ""
    vendor: str
    fabric_type: str = "rocev2"
    pfc_priority: int = 3
    ecn_enabled: bool = True
    dcqcn_enabled: bool = True
    mtu: int = 9100
    tuning_params: str = "{}"
    topology: str = "{}"


@router.post("/fabric", response_model=Envelope[dict], status_code=201)
async def save_fabric(
    req: FabricCreate,
    user: CurrentUser = Depends(require_permission("draft_change")),
) -> Envelope[dict]:
    """保存 RdmaFabric 设计（Phase 4，需 draft_change 权限）。"""
    try:
        from sqlalchemy import select
        from app.db import get_session
        from app.models.design import RdmaFabric

        async for db in get_session():
            fabric = RdmaFabric(
                name=req.name, site=req.site, vendor=req.vendor,
                fabric_type=req.fabric_type, pfc_priority=req.pfc_priority,
                ecn_enabled=req.ecn_enabled, dcqcn_enabled=req.dcqcn_enabled,
                mtu=req.mtu, tuning_params=req.tuning_params, topology=req.topology,
            )
            db.add(fabric)
            await db.commit()
            await db.refresh(fabric)
            return Envelope.ok({"id": fabric.id, "name": fabric.name})
    except Exception as e:
        return Envelope.ok({"status": "mock", "name": req.name, "error": str(e)[:80]})


@router.get("/fabrics", response_model=Envelope[dict])
async def list_fabrics(
    user: CurrentUser = Depends(get_current_user),
) -> Envelope[dict]:
    """列出 RdmaFabric 设计。"""
    return Envelope.ok({
        "fabrics": [],
        "note": "Phase 4 RdmaFabric 列表（需 DB，mock 返回空）",
    })
