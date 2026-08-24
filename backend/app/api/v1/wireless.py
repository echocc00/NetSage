"""无线网络 API（Phase 4 M10 WirelessAgent）。

POST /wireless/plan    AP 布放规划 + 配置生成
GET  /wireless/templates  无线模板列表
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.core.deps import CurrentUser, get_current_user
from app.schemas.common import Envelope

router = APIRouter(prefix="/wireless", tags=["wireless"])


class WirelessPlanRequest(BaseModel):
    area_sqm: int = Field(500, description="面积 m²")
    users: int = Field(100, description="用户数")
    floors: int = Field(1, description="楼层数")
    ssid: str = "Corp-WiFi"
    security: str = "wpa2-psk"
    vendor: str = "huawei"
    psk_passphrase: str = "changeme123"


@router.post("/plan", response_model=Envelope[dict])
async def plan_wireless(
    req: WirelessPlanRequest,
    user: CurrentUser = Depends(get_current_user),
) -> Envelope[dict]:
    """AP 布放规划 + 配置生成（WirelessAgent，Phase 4 M10）。"""
    from app.agents.registry import build_runner

    runner = build_runner()
    state = {
        "area_sqm": req.area_sqm, "users": req.users, "floors": req.floors,
        "ssid": req.ssid, "security": req.security,
        "vendor": req.vendor, "psk_passphrase": req.psk_passphrase,
    }
    result = await runner.run("wireless_agent", state, session_id="wlan-1")
    return Envelope.ok({
        "plan": result.get("plan", {}),
        "config": result.get("config", ""),
        "template_used": result.get("template_used", ""),
        "recommendations": result.get("recommendations", []),
    })


@router.get("/templates", response_model=Envelope[dict])
async def list_wireless_templates(
    user: CurrentUser = Depends(get_current_user),
) -> Envelope[dict]:
    """无线模板列表。"""
    from app.services.template_loader import list_by_vendor

    templates = []
    for v in ["huawei", "cisco", "h3c"]:
        for m in list_by_vendor(v):
            if m["protocol"] == "wireless":
                templates.append({"template_id": m["template_id"], "vendor": v, "feature": m["feature"]})
    return Envelope.ok({"templates": templates, "count": len(templates)})
