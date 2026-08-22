"""设计方案 API（Phase 3 自研 Nautobot App v0.1 业务对接）。

GET  /designs           列出历史方案
POST /designs           保存方案（ConfigEngineer 生成后调用）
GET  /designs/{id}      方案详情
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser, get_current_user
from app.db import get_session
from app.models.design import NetworkDesign
from app.schemas.common import Envelope

router = APIRouter(prefix="/designs", tags=["designs"])


class DesignCreate(BaseModel):
    name: str = Field(..., description="方案名称")
    site: str = ""
    scenario: str = Field(..., examples=["bgp", "ospf", "vxlan"])
    vendor: str = Field(..., examples=["huawei", "cisco_iosxe"])
    hld: str = "{}"
    lld: str = "{}"
    config_diff: str = ""
    rollback_config: str = ""
    lint_passed: bool = False
    created_by: str = "ai"


class DesignOut(BaseModel):
    id: int
    name: str
    site: str
    scenario: str
    vendor: str
    hld: str
    lld: str
    config_diff: str
    rollback_config: str
    lint_passed: bool
    created_by: str


@router.get("", response_model=Envelope[list[DesignOut]])
async def list_designs(
    site: str | None = None,
    scenario: str | None = None,
    vendor: str | None = None,
    db: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(get_current_user),
) -> Envelope[list[DesignOut]]:
    """列出历史设计方案（自研 App v0.1）。"""
    stmt = select(NetworkDesign).order_by(NetworkDesign.id.desc())
    if site:
        stmt = stmt.where(NetworkDesign.site == site)
    if scenario:
        stmt = stmt.where(NetworkDesign.scenario == scenario)
    if vendor:
        stmt = stmt.where(NetworkDesign.vendor == vendor)
    result = await db.execute(stmt)
    designs = result.scalars().all()
    return Envelope.ok([
        DesignOut(
            id=d.id, name=d.name, site=d.site, scenario=d.scenario, vendor=d.vendor,
            hld=d.hld, lld=d.lld, config_diff=d.config_diff,
            rollback_config=d.rollback_config, lint_passed=d.lint_passed,
            created_by=d.created_by,
        )
        for d in designs
    ])


@router.post("", response_model=Envelope[DesignOut], status_code=status.HTTP_201_CREATED)
async def save_design(
    req: DesignCreate,
    db: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(get_current_user),
) -> Envelope[DesignOut]:
    """保存 AI 设计方案（ConfigEngineer 生成后调用，自研 App v0.1）。"""
    design = NetworkDesign(
        name=req.name, site=req.site, scenario=req.scenario, vendor=req.vendor,
        hld=req.hld, lld=req.lld, config_diff=req.config_diff,
        rollback_config=req.rollback_config, lint_passed=req.lint_passed,
        created_by=req.created_by,
    )
    db.add(design)
    await db.commit()
    await db.refresh(design)
    return Envelope.ok(DesignOut(
        id=design.id, name=design.name, site=design.site, scenario=design.scenario,
        vendor=design.vendor, hld=design.hld, lld=design.lld,
        config_diff=design.config_diff, rollback_config=design.rollback_config,
        lint_passed=design.lint_passed, created_by=design.created_by,
    ))


@router.get("/{design_id}", response_model=Envelope[DesignOut])
async def get_design(
    design_id: int,
    db: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(get_current_user),
) -> Envelope[DesignOut]:
    """方案详情。"""
    result = await db.execute(select(NetworkDesign).where(NetworkDesign.id == design_id))
    design = result.scalar_one_or_none()
    if not design:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"方案 {design_id} 不存在")
    return Envelope.ok(DesignOut(
        id=design.id, name=design.name, site=design.site, scenario=design.scenario,
        vendor=design.vendor, hld=design.hld, lld=design.lld,
        config_diff=design.config_diff, rollback_config=design.rollback_config,
        lint_passed=design.lint_passed, created_by=design.created_by,
    ))
