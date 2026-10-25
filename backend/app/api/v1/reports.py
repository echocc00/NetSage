"""运营报表 API（Phase 4 M12 生产化，v2.0 二十八章）。

GET /reports/overview    总览（设备/变更/合规/RCA 命中）
GET /reports/devices     设备统计（按厂商/角色/站点）
GET /reports/changes     变更统计（按状态/时间）
GET /reports/compliance  合规得分趋势
GET /reports/dashboard   大屏聚合数据

v0.5.0 修复（审查 P0）：此前 5 个端点全部返回硬编码演示数字
（devices=5 / automation_rate=0.83 / rca_hit_rate=0.75 均为编造）。
现改为真实数据源：变更统计来自 ChangeStore（内存或 DB，响应标注
storage）、设备来自 SSoT（未配置 NetBox 时为 0 并标注来源）、
RCA/自动化率无历史数据时显式返回 null + no_data 原因，不再编造。
"""
from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends

from app.core.deps import CurrentUser, get_current_user
from app.schemas.common import Envelope
from app.services.change_store import get_change_store
from app.services.metrics import (
    KIND_CLOSED_LOOP,
    KIND_COMPLIANCE,
    KIND_RCA,
    get_metric_sink,
)

router = APIRouter(prefix="/reports", tags=["reports"])


async def _change_summary() -> dict:
    stats = await get_change_store().stats()
    by = stats.get("by_status", {})
    return {
        "total": stats.get("total", 0),
        "approved": by.get("approved", 0) + by.get("done", 0) + by.get("deployed", 0),
        "deployed": by.get("done", 0) + by.get("deployed", 0),
        "rolled_back": by.get("rolled_back", 0),
    }


async def _device_summary() -> dict:
    """设备统计来自 SSoT（NetBox 可用时真实清单；不可达/未配置时如实标注）。"""
    from app.access.source_of_truth import get_source_of_truth

    ssot = get_source_of_truth()
    source = type(ssot).__name__
    try:
        devices = await ssot.list_devices(None)
        by_vendor: dict[str, int] = {}
        for d in devices:
            by_vendor[d.vendor] = by_vendor.get(d.vendor, 0) + 1
        return {"total": len(devices), "by_vendor": by_vendor, "source": source}
    except Exception:
        return {"total": 0, "by_vendor": {}, "source": f"{source}(unreachable)"}


async def _list_ssot_devices() -> tuple[list, str]:
    from app.access.source_of_truth import get_source_of_truth

    ssot = get_source_of_truth()
    source = type(ssot).__name__
    try:
        return await ssot.list_devices(None), source
    except Exception:
        return [], f"{source}(unreachable)"


@router.get("/overview", response_model=Envelope[dict])
async def overview(
    user: CurrentUser = Depends(get_current_user),
) -> Envelope[dict]:
    """运营总览（v0.6：合规/RCA/闭环历史从 metric_events 真实聚合）。"""
    changes = await _change_summary()
    devices = await _device_summary()
    compliance = await get_metric_sink().aggregate(KIND_COMPLIANCE)
    rca = await get_metric_sink().aggregate(KIND_RCA)
    closed_loop = await get_metric_sink().aggregate(KIND_CLOSED_LOOP)
    return Envelope.ok({
        "devices": devices,
        "changes": changes,
        "compliance": {
            "avg_score": compliance["avg_value"],
            "scans": compliance["total"],
            "latest_at": compliance["latest_at"],
        },
        "rca": {
            "total": rca["total"],
            "avg_top1_prob": rca["avg_value"],
            "latest_at": rca["latest_at"],
        },
        "closed_loop": {
            "total_runs": closed_loop["total"],
            "avg_automation_rate": closed_loop["avg_value"],
            "latest_at": closed_loop["latest_at"],
        },
        "meta": {
            "generated_at": datetime.now(UTC).isoformat(),
            "change_storage": get_change_store().mode,
            "metrics_storage": get_metric_sink().mode,
            "demo": False,
        },
    })


@router.get("/devices", response_model=Envelope[dict])
async def device_stats(
    user: CurrentUser = Depends(get_current_user),
) -> Envelope[dict]:
    """设备统计（SSoT 真实清单；未配置/不可达时返回空并标注来源）。"""
    devices, source = await _list_ssot_devices()
    by_vendor: dict[str, int] = {}
    by_role: dict[str, int] = {}
    by_site: dict[str, int] = {}
    for d in devices:
        by_vendor[d.vendor] = by_vendor.get(d.vendor, 0) + 1
        by_role[d.role or "unknown"] = by_role.get(d.role or "unknown", 0) + 1
        by_site[d.site or "unknown"] = by_site.get(d.site or "unknown", 0) + 1
    return Envelope.ok({
        "total": len(devices),
        "by_vendor": [{"vendor": k, "count": v} for k, v in sorted(by_vendor.items())],
        "by_role": [{"role": k, "count": v} for k, v in sorted(by_role.items())],
        "by_site": [{"site": k, "count": v} for k, v in sorted(by_site.items())],
        "health": {"no_data": "设备健康需 SUZIEQ 可观测接入（TOOLS_BACKEND=mcp）"},
        "source": source,
    })


@router.get("/changes", response_model=Envelope[dict])
async def change_stats(
    user: CurrentUser = Depends(get_current_user),
) -> Envelope[dict]:
    """变更统计（ChangeStore 真实计数）。"""
    stats = await get_change_store().stats()
    by_status = stats.get("by_status", {})
    return Envelope.ok({
        "total": stats.get("total", 0),
        "by_status": [
            {"status": k, "count": v} for k, v in sorted(by_status.items())
        ],
        # 自动化率是闭环编排的步骤口径指标（(6-1)/6），不是运营实测；
        # 历史运行未持久化前不做数字宣称（审查 P0 修复）
        "automation_rate": None,
        "automation_rate_note": "自动化率需闭环运行历史（未持久化）；口径见 doc/NetSage-Phase3-规划 11.2",
        "storage": get_change_store().mode,
    })


@router.get("/compliance", response_model=Envelope[dict])
async def compliance_stats(
    user: CurrentUser = Depends(get_current_user),
) -> Envelope[dict]:
    """合规得分趋势（历史未持久化：显式 no_data，不编造趋势）。"""
    return Envelope.ok({
        "avg_score": None,
        "scans": 0,
        "trend": [],
        "top_findings": [],
        "no_data": "合规扫描历史未持久化；单次扫描走 POST /compliance/scan",
    })


@router.get("/dashboard", response_model=Envelope[dict])
async def dashboard(
    user: CurrentUser = Depends(get_current_user),
) -> Envelope[dict]:
    """大屏聚合数据（真实来源；无数据指标显式 null/no_data）。"""
    changes = await _change_summary()
    devices = await _device_summary()
    stats = await get_change_store().stats()
    by_status = stats.get("by_status", {})
    from app.core.config import get_settings

    return Envelope.ok({
        "summary": {
            "devices": devices["total"],
            "changes_total": changes["total"],
            "automation_rate": None,
            "alerts": 0,
            "agents_run": 0,
        },
        "device_health": {"no_data": "需 SUZIEQ 接入"},
        "change_pipeline": {
            "draft": by_status.get("draft", 0),
            "approval": by_status.get("approval", 0),
            "approved": by_status.get("approved", 0),
            "deployed": by_status.get("done", 0) + by_status.get("deployed", 0),
            "rolled_back": by_status.get("rolled_back", 0),
        },
        "rca_hit_rate": None,
        "top_alerts": [],
        "meta": {
            "generated_at": datetime.now(UTC).isoformat(),
            "change_storage": get_change_store().mode,
            "device_source": devices["source"],
            "demo": False,
        },
        "version": get_settings().version,
    })


@router.get("/llm-usage", response_model=Envelope[dict])
async def llm_usage(
    user: CurrentUser = Depends(get_current_user),
) -> Envelope[dict]:
    """LLM 用量统计（成本控制，v2.0 二十九章）。"""
    from app.services.llm_gateway import get_llm_gateway

    gw = get_llm_gateway()
    return Envelope.ok({"usage": gw.usage_stats()})
