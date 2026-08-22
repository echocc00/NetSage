"""LLM 网关（LiteLLM 多模型路由 + 降级，v2.0 二十九章）。

支持 DeepSeek / MiniMax / Claude / GPT 多模型，按任务难度路由。
key 缺失时自动跳过该模型，降级到下一个可用模型。
"""
from __future__ import annotations

from enum import StrEnum
from typing import Any

import litellm
from litellm import acompletion

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger("llm_gateway")


class TaskTier(StrEnum):
    """任务难度→模型路由（v2.0 29.1）。"""
    SIMPLE = "simple"          # 问答/命令查询 → 默认模型
    CODE = "code"              # 配置生成 → 默认模型
    REASONING = "reasoning"    # 架构设计/根因 → reasoning 模型
    DOC = "doc"                # 文档生成 → 默认模型
    CN_COMPLIANCE = "cn"       # 国产化合规 → minimax/qwen


# 路由表：tier → 候选模型列表（按优先级，降级用）
TIER_ROUTES: dict[TaskTier, list[str]] = {
    TaskTier.SIMPLE: ["deepseek/deepseek-chat", "minimax/abab6.5s-chat"],
    TaskTier.CODE: ["deepseek/deepseek-chat", "minimax/abab6.5s-chat", "anthropic/claude-sonnet-5"],
    TaskTier.REASONING: ["deepseek/deepseek-reasoner", "anthropic/claude-sonnet-5", "minimax/abab6.5s-chat"],
    TaskTier.DOC: ["deepseek/deepseek-chat", "minimax/abab6.5s-chat", "gpt-4o-mini"],
    TaskTier.CN_COMPLIANCE: ["minimax/abab6.5s-chat", "deepseek/deepseek-chat"],
}


class LLMGateway:
    """多模型路由 + 降级。key 缺失的模型自动跳过。"""

    def __init__(self) -> None:
        self.settings = get_settings()
        self._configure_keys()

    def _configure_keys(self) -> None:
        """注入 API key 到环境变量，litellm 自动读取。"""
        import os

        s = self.settings
        if s.deepseek_api_key:
            os.environ["DEEPSEEK_API_KEY"] = s.deepseek_api_key
        if s.minimax_api_key:
            os.environ["MINIMAX_API_KEY"] = s.minimax_api_key
        if s.anthropic_api_key:
            os.environ["ANTHROPIC_API_KEY"] = s.anthropic_api_key
        if s.openai_api_key:
            os.environ["OPENAI_API_KEY"] = s.openai_api_key

    def _available_models(self, tier: TaskTier) -> list[str]:
        """返回该 tier 下有 key 的可用模型。"""
        candidates = TIER_ROUTES[tier]
        available = []
        for model in candidates:
            provider = model.split("/", 1)[0]
            if self._has_key(provider):
                available.append(model)
        if not available:
            logger.warning("no_llm_available", tier=tier, candidates=candidates)
        return available

    def _has_key(self, provider: str) -> bool:
        s = self.settings
        return {
            "deepseek": bool(s.deepseek_api_key),
            "minimax": bool(s.minimax_api_key),
            "anthropic": bool(s.anthropic_api_key),
            "gpt": bool(s.openai_api_key),
        }.get(provider, False)

    async def complete(
        self,
        messages: list[dict[str, str]],
        tier: TaskTier = TaskTier.SIMPLE,
        **kwargs: Any,
    ) -> str:
        """按 tier 路由，失败自动降级到下一个模型（v2.0 29.2）。"""
        models = self._available_models(tier)
        if not models:
            raise RuntimeError(
                f"无可用 LLM 模型（tier={tier}）。请配置至少一个 API key。"
            )

        last_error: Exception | None = None
        for model in models:
            try:
                response = await acompletion(model=model, messages=messages, **kwargs)
                logger.info(
                    "llm_call_ok",
                    model=model,
                    tier=tier,
                    tokens=response.usage.total_tokens if response.usage else 0,
                )
                return response.choices[0].message.content or ""
            except Exception as e:
                logger.warning("llm_call_fail", model=model, tier=tier, error=str(e))
                last_error = e
                continue

        raise RuntimeError(f"所有候选模型均失败（tier={tier}）：{last_error}")


_gateway: LLMGateway | None = None


def get_llm_gateway() -> LLMGateway:
    global _gateway
    if _gateway is None:
        _gateway = LLMGateway()
    return _gateway
