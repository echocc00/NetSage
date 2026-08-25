"""NetSage FastAPI 入口（v2.0 五章 5.1）。"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import api_router
from app.core.config import get_settings
from app.core.logging import TraceIdMiddleware, get_logger, setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger = get_logger("app")
    settings = get_settings()
    settings.verify_secrets()  # 生产弱密钥启动拒绝（审查 C1）
    _configure_ssot(settings)
    logger.info("startup", env=settings.env, version=settings.version)
    yield
    logger.info("shutdown")


def _configure_ssot(settings) -> None:
    """启动时装配 SourceOfTruth（NetBox 可用时注入，否则降级 NullSSoT）。"""
    from app.access.source_of_truth import NullSSoT, configure_ssot

    if settings.netbox_url and settings.netbox_token:
        from app.access.netbox_adapter import NetBoxAdapter

        adapter = NetBoxAdapter(settings.netbox_url, settings.netbox_token)
        configure_ssot(adapter)  # type: ignore[arg-type]
        logger = get_logger("app")
        logger.info("ssot_configured", backend="netbox", url=settings.netbox_url)
    else:
        configure_ssot(NullSSoT())  # type: ignore[arg-type]


def create_app() -> FastAPI:
    settings = get_settings()
    settings.verify_secrets()
    app = FastAPI(
        title="NetSage · AI 网络工程师智能平台",
        description=(
            "AI 辅助网络工程平台：8 Agent 编排 + 三道闸 + 多厂商 + 双 SSoT + 安全合规。\n\n"
            "- 10 Agent：planner/config_engineer/validator/troubleshooter/deploy/observer/"
            "security_auditor/compliance/rdm_agent/wireless_agent\n"
            "- 三道闸：Containerlab 仿真 → Batfish 校验 → 人工审批\n"
            "- 多厂商：华为/Cisco/H3C/Juniper/Arista\n"
            "- 双 SSoT：NetBox（包装）+ Nautobot（Adapter + 自研 App）\n\n"
            "认证：JWT Bearer（开发态 /auth/dev-token，生产 OIDC）。"
        ),
        version=settings.version,
        openapi_tags=[
            {"name": "health", "description": "健康检查"},
            {"name": "auth", "description": "认证 + RBAC + OIDC SSO"},
            {"name": "agents", "description": "Agent 会话 + 自动化闭环"},
            {"name": "devices", "description": "设备管理 + 实时状态"},
            {"name": "designs", "description": "AI 设计方案持久化"},
            {"name": "changes", "description": "变更审批 + 快照回滚"},
            {"name": "compliance", "description": "安全基线 + ACL 分析"},
            {"name": "rdma", "description": "RDMA/RoCE 专项"},
            {"name": "wireless", "description": "无线网络专项"},
            {"name": "reports", "description": "运营报表 + 大屏"},
            {"name": "topology", "description": "拓扑可视化"},
        ],
        openapi_url="/openapi.json",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    setup_logging(app)
    app.add_middleware(TraceIdMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,  # 从环境读取（审查 #4 修复）
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],  # 收窄（审查 #4）
        allow_headers=["Authorization", "Content-Type", "X-Trace-Id"],
    )

    app.include_router(api_router, prefix="/api/v1")
    return app


app = create_app()
