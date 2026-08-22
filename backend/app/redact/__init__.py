"""数据脱敏四层模型（v2.0 二十章）。

Layer 1: 静态字典脱敏（确定性，正则替换为占位符）
Layer 2: 上下文感知脱敏（Phase 2 引入）
Layer 3: 决策路由（白/灰/黑盒）
Layer 4: 对抗测试（Phase 2 起，eval/fuzz）

可逆性：占位符通过 MappingTable 还原（存 Redis，TTL 1h）。
"""
from __future__ import annotations

from .layer1_dict import Layer1Redactor
from .layer3_router import ContentTier, Layer3Router, Route
from .mapping import MappingTable

__all__ = [
    "Layer1Redactor",
    "Layer3Router",
    "ContentTier",
    "Route",
    "MappingTable",
]
