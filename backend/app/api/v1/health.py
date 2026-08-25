"""健康检查端点（生产化强化，v2.0 二十五章 DR + 十七章监控）。

/health        存活检查（liveness，总是 200）
/health/ready  就绪检查（readiness，探测 PG / Redis / LLM / SSoT）
/health/deps   依赖详情（诊断用）
"""
from __future__ import annotations

import asyncio

import httpx
from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import get_settings

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    version: str
    env: str


class DepStatus(BaseModel):
    name: str
    healthy: bool
    detail: str = ""


class ReadyResponse(BaseModel):
    status: str
    version: str
    env: str
    deps: list[DepStatus]


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """存活检查（liveness）。"""
    settings = get_settings()
    return HealthResponse(status="ok", version=settings.version, env=settings.env)


@router.get("/health/ready", response_model=ReadyResponse)
async def readiness() -> ReadyResponse:
    """就绪检查（readiness）：探测 PG / Redis / LLM / SSoT。"""
    settings = get_settings()
    deps = await _check_deps(settings)
    all_ok = all(d.healthy for d in deps)
    return ReadyResponse(
        status="ready" if all_ok else "degraded",
        version=settings.version,
        env=settings.env,
        deps=deps,
    )


@router.get("/health/deps", response_model=ReadyResponse)
async def deps_detail() -> ReadyResponse:
    """依赖详情（诊断用）。"""
    return await readiness()


async def _check_deps(settings) -> list[DepStatus]:
    """并行探测所有依赖。"""
    pg_task = _check_pg(settings)
    redis_task = _check_redis(settings)
    llm_task = _check_llm(settings)
    ssot_task = _check_ssot(settings)
    pg, redis, llm, ssot = await asyncio.gather(pg_task, redis_task, llm_task, ssot_task)
    return [pg, redis, llm, ssot]


async def _check_pg(settings) -> DepStatus:
    try:
        from sqlalchemy.ext.asyncio import create_async_engine
        engine = create_async_engine(settings.database_url)
        async with engine.connect() as conn:
            await conn.execute(__import__("sqlalchemy").text("SELECT 1"))
        await engine.dispose()
        return DepStatus(name="postgres", healthy=True)
    except Exception as e:
        return DepStatus(name="postgres", healthy=False, detail=str(e)[:80])


async def _check_redis(settings) -> DepStatus:
    try:
        import redis.asyncio as aioredis
        r = aioredis.from_url(settings.redis_url)
        await r.ping()
        await r.aclose()
        return DepStatus(name="redis", healthy=True)
    except Exception as e:
        return DepStatus(name="redis", healthy=False, detail=str(e)[:80])


async def _check_llm(settings) -> DepStatus:
    has_key = bool(settings.deepseek_api_key or settings.minimax_api_key or settings.anthropic_api_key)
    return DepStatus(
        name="llm",
        healthy=has_key,
        detail="已配置" if has_key else "未配置任何 LLM key（降级 mock）",
    )


async def _check_ssot(settings) -> DepStatus:
    if not settings.netbox_url:
        return DepStatus(name="ssot", healthy=True, detail="未配置 NetBox（NullSSoT 降级）")
    try:
        async with httpx.AsyncClient(timeout=3.0) as c:
            r = await c.get(f"{settings.netbox_url.rstrip('/')}/health/")
            return DepStatus(name="ssot", healthy=r.status_code < 500, detail=f"NetBox {r.status_code}")
    except Exception as e:
        return DepStatus(name="ssot", healthy=False, detail=str(e)[:80])
