"""API v1 路由聚合。"""
from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import agents, auth, changes, compliance, designs, devices, health, oidc, rdma, reports, topology, wireless

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(agents.router)
api_router.include_router(devices.router)
api_router.include_router(changes.router)
api_router.include_router(topology.router)
api_router.include_router(designs.router)
api_router.include_router(compliance.router)
api_router.include_router(rdma.router)
api_router.include_router(wireless.router)
api_router.include_router(oidc.router)
api_router.include_router(reports.router)
