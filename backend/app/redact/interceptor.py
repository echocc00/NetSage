"""脱敏拦截器：统一集成到 LLM 调用和 MCP 工具调用（v2.0 20.4 实现）。

所有出网调用前过敏感度标签 + 脱敏；返回时还原占位符。
"""
from __future__ import annotations

from typing import Any

from app.core.logging import get_logger

from .layer1_dict import Layer1Redactor
from .layer3_router import ContentTier, Layer3Router, Route
from .mapping import MappingTable

logger = get_logger("redact_interceptor")


class RedactingInterceptor:
    """LLM/MCP 调用前后脱敏 + 还原。"""

    def __init__(self) -> None:
        self.l1 = Layer1Redactor()
        self.l3 = Layer3Router()

    def before_llm_call(
        self,
        messages: list[dict[str, str]],
        content_type: str,
        mapping: MappingTable,
    ) -> list[dict[str, str]]:
        """LLM 调用前：路由判定 + 脱敏。"""
        tier = self.l3.classify(content_type)

        # 黑盒直接拦截
        if tier == ContentTier.BLACK:
            self.l3.assert_route(content_type, is_redacted=False)
            raise RuntimeError("不应到达此处：黑盒已被 assert_route 拦截")

        # 灰盒必须脱敏
        is_redacted = tier == ContentTier.WHITE  # 白盒无需脱敏
        if tier == ContentTier.GREY:
            is_redacted = True
            messages = self._redact_messages(messages, mapping)

        route = self.l3.route(content_type, is_redacted=is_redacted)
        if route != Route.CLOUD:
            raise RuntimeError(f"路由拒绝：{content_type} → {route}")

        logger.info(
            "redact_before_llm",
            content_type=content_type,
            tier=tier,
            placeholders=mapping.size,
        )
        return messages

    def after_llm_call(self, response: str, mapping: MappingTable) -> str:
        """LLM 返回后：还原占位符（展示给用户时）。"""
        restored = mapping.restore(response)
        if mapping.size > 0:
            logger.info("redact_restore", placeholders=mapping.size)
        return restored

    def before_tool_call(
        self,
        tool_name: str,
        kwargs: dict[str, Any],
        mapping: MappingTable,
    ) -> dict[str, Any]:
        """MCP 工具调用前：脱敏字符串参数（设备配置/IP 等）。"""
        redacted = self.l1.redact_dict(kwargs, mapping)
        if mapping.size > 0:
            logger.info("redact_before_tool", tool=tool_name, placeholders=mapping.size)
        return redacted

    def after_tool_call(self, result: Any, mapping: MappingTable) -> Any:
        """工具返回后：还原占位符。"""
        if isinstance(result, str):
            return mapping.restore(result)
        if isinstance(result, dict):
            return self._restore_dict(result, mapping)
        if isinstance(result, list):
            return [self.after_tool_call(v, mapping) for v in result]
        return result

    def _redact_messages(
        self, messages: list[dict[str, str]], mapping: MappingTable
    ) -> list[dict[str, str]]:
        return [
            {**msg, "content": self.l1.redact(msg.get("content", ""), mapping)}
            for msg in messages
        ]

    def _restore_dict(self, d: dict, mapping: MappingTable) -> dict:
        return {k: self.after_tool_call(v, mapping) for k, v in d.items()}
