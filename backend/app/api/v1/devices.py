"""设备管理 API（v2.0 八章 devices 表 + 十章接入层）。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser, get_current_user, require_permission
from app.db import get_session
from app.schemas.common import Envelope
router = APIRouter(prefix="/devices", tags=["devices"])


class DeviceCreate(BaseModel):
    name: str
    vendor: str = Field(..., examples=["huawei_vrp", "cisco_iosxe"])
    os: str = Field("", examples=["vrp", "iosxe"])
    model: str = ""
    version: str = ""
    mgmt_ip: str
    role: str = ""
    project_id: int


class DeviceOut(BaseModel):
    id: int
    name: str
    vendor: str
    os: str
    model: str
    version: str
    mgmt_ip: str  # 展示前脱敏（Phase 2）
    role: str


@router.get("", response_model=Envelope[list[DeviceOut]])
async def list_devices(
    db: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(get_current_user),
) -> Envelope[list[DeviceOut]]:
    """列出设备（需登录，read 权限）。Phase 1 占位。"""
    return Envelope.ok([])


@router.post("", response_model=Envelope[DeviceOut])
async def create_device(
    req: DeviceCreate,
    db: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_permission("draft_change")),
) -> Envelope[DeviceOut]:
    """新增设备（需 draft_change 权限，engineer/admin）。"""
    device = DeviceOut(
        id=1,
        name=req.name,
        vendor=req.vendor,
        os=req.os,
        model=req.model,
        version=req.version,
        mgmt_ip=req.mgmt_ip,
        role=req.role,
    )
    return Envelope.ok(device)


@router.get("/{device_id}", response_model=Envelope[dict])
async def get_device(
    device_id: int,
    user: CurrentUser = Depends(get_current_user),
) -> Envelope[dict]:
    """设备详情（从 NetBox 拉，Phase 2 P2-12）。"""
    from app.access.netbox_adapter import NetBoxAdapter
    from app.core.config import get_settings

    settings = get_settings()
    adapter = NetBoxAdapter(base_url=settings.netbox_url, token=settings.netbox_token)
    try:
        dev = await adapter.get_device(device_id)
        return Envelope.ok({
            "id": dev.id, "name": dev.name, "vendor": dev.vendor,
            "os": dev.os, "model": dev.model, "version": dev.version,
            "mgmt_ip": dev.mgmt_ip, "role": dev.role, "site": dev.site,
            "status": dev.status,
        })
    except Exception as e:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"NetBox 不可达: {e}") from e
    finally:
        await adapter.client.aclose()


@router.get("/{device_id}/state", response_model=Envelope[dict])
async def get_device_state(
    device_id: int,
    user: CurrentUser = Depends(get_current_user),
) -> Envelope[dict]:
    """设备实时状态（NAPALM facts + SUZIEQ 状态合并，Phase 2 P2-12）。

    Phase 2 W4：SUZIEQ 接入后补实时状态；当前返回 NetBox 静态 facts。
    """
    from app.access.netbox_adapter import NetBoxAdapter
    from app.core.config import get_settings

    settings = get_settings()
    adapter = NetBoxAdapter(base_url=settings.netbox_url, token=settings.netbox_token)
    try:
        dev = await adapter.get_device(device_id)
        return Envelope.ok({
            "device": {
                "id": dev.id, "name": dev.name, "vendor": dev.vendor,
                "os": dev.os, "model": dev.model, "version": dev.version,
                "mgmt_ip": dev.mgmt_ip, "role": dev.role, "site": dev.site,
                "status": dev.status,
            },
            "realtime": {
                "source": "netbox_static",
                "note": "SUZIEQ 实时状态 Phase 2 W4 后接入",
            },
            "health": "unknown",  # healthy / warning / critical / unknown
        })
    except Exception as e:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"NetBox 不可达: {e}") from e
    finally:
        await adapter.client.aclose()


@router.post("/{device_id}/facts", response_model=Envelope[dict])
async def get_device_facts(
    device_id: int,
    user: CurrentUser = Depends(require_permission("troubleshoot")),
) -> Envelope[dict]:
    """采集设备 facts（需 troubleshoot 权限，operator+）。Phase 1 占位。"""
    return Envelope.ok({
        "device_id": device_id,
        "status": "phase1_placeholder",
        "note": "Phase 2 接 AdapterFactory + Vault 凭证",
    })
