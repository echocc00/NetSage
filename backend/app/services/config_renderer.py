"""LLM 参数提取 → 模板渲染（v2.0 十章"IR 只作翻译不作裸推理"）。

ConfigEngineer 的核心链路：用户意图 → LLM 提取模板入参（结构化 JSON）
→ template_loader.render() 渲染配置。LLM 不直接写配置文本。
"""
from __future__ import annotations

import json
import re
from typing import Any

from app.core.logging import get_logger
from app.services.llm_gateway import TaskTier
from app.services.template_loader import list_by_vendor

logger = get_logger("config_renderer")


def _extract_json(text: str) -> dict | None:
    """从 LLM 输出提取 JSON（容忍 ```json 围栏和前后杂质）。"""
    text = text.strip()
    fence = re.search(r"```json\s*(.+?)\s*```", text, re.DOTALL)
    if fence:
        text = fence.group(1)
    # 找第一个 { 到最后一个 }
    try:
        obj = json.loads(text[text.index("{") : text.rindex("}") + 1])
        return obj if isinstance(obj, dict) else None
    except (ValueError, json.JSONDecodeError):
        return None


class ConfigRenderer:
    """意图 → 模板参数 → 配置。"""

    def __init__(self, llm: Any) -> None:
        self.llm = llm

    def _match_template(self, query: str, vendor: str, scenario: str) -> str | None:
        """按 query 关键词 + 厂商 + 场景选模板（Phase 1 规则匹配）。"""
        candidates = list_by_vendor(vendor, protocol=scenario)
        if not candidates:
            # 兜底：跨协议/首个可用
            candidates = list_by_vendor(vendor)
        # 关键词打分选最优
        best, best_score = None, 0
        for meta in candidates:
            score = sum(1 for kw in meta.get("feature", "").split("_") if kw in query.lower())
            if score > best_score:
                best, best_score = meta["template_id"], score
        return best

    async def generate(
        self,
        query: str,
        vendor: str,
        scenario: str,
        device: dict | None = None,
    ) -> dict:
        """完整生成：选模板 → LLM 提参 → 渲染。返回 diff + rollback + references。"""
        from app.services.template_loader import TemplateError, render

        template_id = self._match_template(query, vendor, scenario)
        if template_id is None:
            raise TemplateError(f"无可用模板（vendor={vendor} scenario={scenario}）")

        # 1. LLM 提取模板入参（tools 元数据注入上下文）
        meta = self._meta_for(template_id)
        prompt = (
            f"你是网络配置参数提取器。从需求中提取模板入参，只输出 JSON。\n"
            f"模板:{template_id}\n入参 schema:{json.dumps(meta['input_schema'], ensure_ascii=False)}\n"
            f"用户需求:{query}\n"
            f"设备:{json.dumps(device or {}, ensure_ascii=False)}\n"
            "输出格式: {\"name\": ...}（按 input_schema 字段填充）"
        )
        raw = await self.llm.complete(
            [{"role": "user", "content": prompt}],
            tier=TaskTier.CODE,
            content_type="topology_abstraction",  # 灰盒：设备信息强制脱敏（v2.0 二十章）
        )
        params = _extract_json(raw)
        if params is None:
            raise TemplateError(f"LLM 参数提取失败，非 JSON 输出: {raw[:200]}")

        # 2. 模板渲染（StrictUndefined 兜底缺参）
        diff = render(template_id, params)

        return {
            "template_id": template_id,
            "params": params,
            "config_diff": diff,
            "rollback": f"! rollback: 撤销 {template_id} 变更",
            "references": [{"type": "template", "id": template_id}],
            "warnings": [],
        }

    def _meta_for(self, template_id: str) -> dict:
        from app.services.template_loader import load_template

        _, meta = load_template(template_id)
        return meta


_llm: Any = None


def get_config_renderer() -> ConfigRenderer:
    """全局 renderer（llm 网关惰性装配）。"""
    global _llm
    if _llm is None:
        from app.services.llm_gateway import get_llm_gateway

        _llm = get_llm_gateway()
    return ConfigRenderer(_llm)
