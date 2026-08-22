"""可逆映射表：占位符 ↔ 原始值。

每会话一个映射，存 Redis（TTL 1h）。展示时还原，保证审计链不断（v2.0 20.6）。
Phase 1 用内存实现，Phase 2 换 Redis。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class MappingTable:
    """占位符 ↔ 原始值的双向映射。"""

    _placeholder_to_orig: dict[str, str] = field(default_factory=dict)
    _orig_to_placeholder: dict[str, str] = field(default_factory=dict)
    _counters: dict[str, int] = field(default_factory=dict)

    def add(self, key: str, original: str) -> str:
        """记录映射，返回占位符。同一 original 复用占位符（确定性）。"""
        if original in self._orig_to_placeholder:
            return self._orig_to_placeholder[original]
        self._counters[key] = self._counters.get(key, 0) + 1
        placeholder = f"[{key}_{self._counters[key]}]"
        self._placeholder_to_orig[placeholder] = original
        self._orig_to_placeholder[original] = placeholder
        return placeholder

    def restore(self, text: str) -> str:
        """把文本中的占位符还原为原始值。"""
        if not text:
            return text
        # 按 placeholder 长度降序替换，避免 [IPV4_1] 被 [IPV4_10] 的前缀误伤
        for placeholder in sorted(self._placeholder_to_orig, key=len, reverse=True):
            text = text.replace(placeholder, self._placeholder_to_orig[placeholder])
        return text

    def has(self, placeholder: str) -> bool:
        return placeholder in self._placeholder_to_orig

    @property
    def size(self) -> int:
        return len(self._placeholder_to_orig)

    def redacted_summary(self) -> dict[str, int]:
        """脱敏统计（审计用，不泄露原值）。"""
        from collections import Counter

        counts: Counter[str] = Counter()
        for ph in self._placeholder_to_orig:
            key = re.match(r"\[([A-Z0-9]+)_\d+\]", ph)
            if key:
                counts[key.group(1)] += 1
        return dict(counts)
