"""Layer 3: 决策路由（白/灰/黑盒，v2.0 20.4）。

内容类型 → 敏感度标签 → 允许的目标 LLM。
黑盒绝对本地，禁止任何外部 LLM；灰盒必须已脱敏。
"""
from __future__ import annotations

from enum import StrEnum
from typing import Any

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger("redact_router")


class ContentTier(StrEnum):
    WHITE = "white"   # 可发云：通用知识、公开 RFC、Prompt 模板
    GREY = "grey"     # 本地/脱敏后发云：Postmortem 摘要、脱敏配置、拓扑抽象
    BLACK = "black"   # 绝对本地：完整 running-config、密码、真实 IP/ASN


class Route(StrEnum):
    LOCAL_ONLY = "local_only"   # 黑盒：禁止外发
    CLOUD = "cloud"             # 白盒/灰盒：可发云
    BLOCKED = "blocked"         # 违反规则：阻断


# 内容类型 → tier 映射（简化版，Phase 2 扩展基于 DB 敏感字段标记）
CONTENT_TIER_MAP: dict[str, ContentTier] = {
    # 白盒
    "rfc_query": ContentTier.WHITE,
    "general_qa": ContentTier.WHITE,
    "prompt_template": ContentTier.WHITE,
    # 灰盒（必须已脱敏）
    "postmortem_summary": ContentTier.GREY,
    "config_template_redacted": ContentTier.GREY,
    "topology_abstraction": ContentTier.GREY,
    # 黑盒
    "running_config": ContentTier.BLACK,
    "credentials": ContentTier.BLACK,
    "raw_logs": ContentTier.BLACK,
}


class Layer3Router:
    """按内容敏感度决定能否发云。违反规则立即阻断（v2.0 20.4）。"""

    def __init__(self) -> None:
        self.settings = get_settings()

    def classify(self, content_type: str) -> ContentTier:
        return CONTENT_TIER_MAP.get(content_type, ContentTier.GREY)  # 默认灰盒，保守

    def route(
        self,
        content_type: str,
        is_redacted: bool = False,
        payload: Any = None,
    ) -> Route:
        """决定路由。黑盒且配置本地only → LOCAL_ONLY；灰盒未脱敏 → BLOCKED。"""
        tier = self.classify(content_type)

        if tier == ContentTier.BLACK:
            if self.settings.redact_blackbox_local_only:
                logger.warning("blackbox_blocked_local", content_type=content_type)
                return Route.LOCAL_ONLY
            return Route.CLOUD  # 配置允许黑盒外发（不推荐，仅特殊场景）

        if tier == ContentTier.GREY and not is_redacted:
            logger.error("grey_not_redacted_blocked", content_type=content_type)
            return Route.BLOCKED  # 灰盒未脱敏，阻断

        return Route.CLOUD

    def assert_route(self, content_type: str, is_redacted: bool) -> None:
        """断言可发云，不可则抛异常（供拦截器用）。"""
        route = self.route(content_type, is_redacted)
        if route == Route.LOCAL_ONLY:
            raise BlackboxBlockError(f"黑盒内容禁止外发：{content_type}")
        if route == Route.BLOCKED:
            raise GreyboxNotRedactedError(f"灰盒内容未脱敏：{content_type}")


class BlackboxBlockError(Exception):
    """黑盒内容尝试外发。"""


class GreyboxNotRedactedError(Exception):
    """灰盒内容未脱敏就尝试外发。"""
