"""健康检查端点。W1 验收：curl /health → 200。"""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import get_settings

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    version: str
    env: str


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(status="ok", version=settings.version, env=settings.env)


@router.get("/health/ready", response_model=HealthResponse)
async def readiness() -> HealthResponse:
    """就绪检查：DB / Redis 连通性。"""
    # W1 仅返回 ok，W3 起接入真实依赖检查
    settings = get_settings()
    return HealthResponse(status="ok", version=settings.version, env=settings.env)
