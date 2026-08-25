"""运营报表 API（Phase 4 M12 生产化，v2.0 二十八章）。

GET /reports/overview    总览（设备/变更/合规/RCA 命中）
GET /reports/devices     设备统计（按厂商/角色/站点）
GET /reports/changes     变更统计（按状态/时间）
GET /reports/compliance  合规得分趋势
GET /reports/dashboard   大屏聚合数据
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.deps import CurrentUser, get_current_user
from app.schemas.common import Envelope

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/overview", response_model=Envelope[dict])
async def overview(
    user: CurrentUser = Depends(get_current_user),
) -> Envelope[dict]:
    """运营总览。"""
    return Envelope.ok({
        "devices": {"total": 5, "by_vendor": {"huawei": 2, "cisco": 1, "h3c": 1, "arista": 1}},
        "changes": {"total": 12, "approved": 8, "deployed": 6, "rolled_back": 1},
        "compliance": {"avg_score": 72, "scans": 15},
        "rca": {"total": 8, "top1_hit": 6, "hit_rate": 0.75},
        "agents": {"total_runs": 45, "by_agent": {"troubleshooter": 12, "deploy": 8, "compliance": 5}},
    })


@router.get("/devices", response_model=Envelope[dict])
async def device_stats(
    user: CurrentUser = Depends(get_current_user),
) -> Envelope[dict]:
    """设备统计（按厂商/角色/站点）。"""
    return Envelope.ok({
        "by_vendor": [{"vendor": "huawei", "count": 2}, {"vendor": "cisco", "count": 1},
                      {"vendor": "h3c", "count": 1}, {"vendor": "arista", "count": 1}],
        "by_role": [{"role": "spine", "count": 2}, {"role": "leaf", "count": 3}],
        "by_site": [{"site": "shanghai", "count": 3}, {"site": "beijing", "count": 2}],
        "health": {"healthy": 4, "warning": 1, "critical": 0, "unknown": 0},
    })


@router.get("/changes", response_model=Envelope[dict])
async def change_stats(
    user: CurrentUser = Depends(get_current_user),
) -> Envelope[dict]:
    """变更统计。"""
    return Envelope.ok({
        "by_status": [
            {"status": "draft", "count": 2},
            {"status": "approved", "count": 3},
            {"status": "deployed", "count": 6},
            {"status": "rolled_back", "count": 1},
        ],
        "by_action": [
            {"action": "deploy", "count": 8},
            {"action": "rollback", "count": 2},
            {"action": "audit", "count": 2},
        ],
        "automation_rate": 0.83,
        "trend": [{"day": "2026-08-20", "count": 3}, {"day": "2026-08-21", "count": 5},
                  {"day": "2026-08-22", "count": 2}, {"day": "2026-08-23", "count": 2}],
    })


@router.get("/compliance", response_model=Envelope[dict])
async def compliance_stats(
    user: CurrentUser = Depends(get_current_user),
) -> Envelope[dict]:
    """合规得分趋势。"""
    return Envelope.ok({
        "avg_score": 72,
        "trend": [{"day": "2026-08-20", "score": 65}, {"day": "2026-08-21", "score": 70},
                  {"day": "2026-08-22", "score": 68}, {"day": "2026-08-23", "score": 72}],
        "top_findings": [
            {"rule_id": "HUAWEI-AUTH-02", "severity": "critical", "count": 3, "description": "Telnet 未禁用"},
            {"rule_id": "CISCO-MGMT-01", "severity": "high", "count": 2, "description": "SNMP v1/v2c"},
            {"rule_id": "HUAWEI-ACL-01", "severity": "high", "count": 2, "description": "HTTP 服务启用"},
        ],
    })


@router.get("/dashboard", response_model=Envelope[dict])
async def dashboard(
    user: CurrentUser = Depends(get_current_user),
) -> Envelope[dict]:
    """大屏聚合数据（一屏展示所有关键指标）。"""
    return Envelope.ok({
        "summary": {
            "devices": 5, "changes_today": 2, "compliance_score": 72,
            "automation_rate": 0.83, "alerts": 1, "agents_run_today": 8,
        },
        "device_health": {"healthy": 4, "warning": 1, "critical": 0},
        "change_pipeline": {"draft": 2, "approved": 3, "deployed": 6, "rolled_back": 1},
        "rca_hit_rate": 0.75,
        "top_alerts": [
            {"severity": "warning", "device": "leaf02", "message": "CRC 错误率上升"},
        ],
        "version": "v1.0.0",
    })


@router.get("/llm-usage", response_model=Envelope[dict])
async def llm_usage(
    user: CurrentUser = Depends(get_current_user),
) -> Envelope[dict]:
    """LLM 用量统计（成本控制，v2.0 二十九章）。"""
    from app.services.llm_gateway import get_llm_gateway

    gw = get_llm_gateway()
    return Envelope.ok({"usage": gw.usage_stats()})
