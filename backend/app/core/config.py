"""应用配置（pydantic-settings）。

启动时校验必填项，缺失即拒绝启动（v2.0 二十二章 22.2）。
"""
from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore",
    )

    # 应用
    env: str = "dev"
    log_level: str = "INFO"
    app_name: str = "NetSage"
    version: str = "0.1.0"

    # 数据库
    database_url: str = Field(...)
    postgres_user: str = "netsage"
    postgres_password: str = ""
    postgres_db: str = "netsage"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Vault
    vault_addr: str = ""
    vault_token: str = ""

    # LLM 网关（LiteLLM 多模型路由，v2.0 二十九章）
    litellm_master_key: str = ""
    deepseek_api_key: str = ""
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    minimax_api_key: str = ""              # 用户后续提供
    minimax_api_base: str = "https://api.minimax.chat/v1"
    # 默认模型路由（难度→模型）
    llm_default_model: str = "deepseek/deepseek-chat"
    llm_fallback_model: str = "minimax/abab6.5s-chat"
    llm_reasoning_model: str = "deepseek/deepseek-reasoner"

    # MCP 端点
    mcp_containerlab_url: str = "http://localhost:9001"
    mcp_batfish_url: str = "http://localhost:9002"
    mcp_napalm_url: str = "http://localhost:9003"
    mcp_opensm_url: str = "http://localhost:9006"

    # 仿真
    containerlab_host: str = ""
    batfish_host: str = "http://localhost:9996"

    # 脱敏
    redact_blackbox_local_only: bool = True

    # 认证
    jwt_secret: str = Field(default="changeme_dev_only", description="HS256 密钥，生产必须显式配置")
    jwt_algo: str = "HS256"
    jwt_expire_minutes: int = 60 * 24

    # CORS（从环境读取，生产必填具体域名）
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    # Source of Truth（NetBox，Phase 2）
    netbox_url: str = ""
    netbox_token: str = ""

    # Source of Truth（Nautobot，Phase 3 — mock 模式默认不部署服务）
    nautobot_url: str = ""
    nautobot_token: str = ""
    nautobot_mock: bool = True

    @property
    def is_dev(self) -> bool:
        return self.env == "dev"

    def verify_secrets(self) -> None:
        """启动校验：非 dev 环境禁止弱默认密钥（审查 C1 修复）。"""
        if not self.is_dev:
            if self.jwt_secret == "changeme_dev_only":
                raise RuntimeError("生产环境必须显式配置 JWT_SECRET，禁止使用默认值")
            if self.postgres_password == "changeme_dev_only":
                raise RuntimeError("生产环境必须显式配置 POSTGRES_PASSWORD")


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
