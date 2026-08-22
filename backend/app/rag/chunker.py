"""文档分块器（v2.0 七章 7.3）。

手册：特性→场景→命令→注意事项 四级分块，每块 ≤1500 token，overlap 100。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class Chunk:
    text: str
    doc_id: str
    source_url: str | None = None
    version: str | None = None
    tier: int = 1
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "doc_id": self.doc_id,
            "source_url": self.source_url,
            "version": self.version,
            "tier": self.tier,
            "metadata": self.metadata,
        }


class ManualChunker:
    """厂商手册四级分块。"""

    MAX_TOKENS = 1500
    OVERLAP = 100

    # 章节标题正则（#, ##, ### 或 数字编号 1. / 1.1.）
    HEADING_RE = re.compile(r"^(#{1,4}\s.+|\d+(\.\d+)*\s+\S.+)$", re.MULTILINE)

    def chunk(self, text: str, doc_id: str, **meta) -> list[Chunk]:
        sections = self._split_by_heading(text)
        chunks: list[Chunk] = []
        for section_path, section_text in sections:
            for piece in self._sliding_window(section_text):
                chunks.append(
                    Chunk(
                        text=piece,
                        doc_id=doc_id,
                        metadata={"path": section_path, **meta},
                    )
                )
        return chunks

    def _split_by_heading(self, text: str) -> list[tuple[str, str]]:
        """按标题切分，返回 (章节路径, 内容)。"""
        matches = list(self.HEADING_RE.finditer(text))
        if not matches:
            return [("root", text)]

        sections: list[tuple[str, str]] = []
        for i, m in enumerate(matches):
            heading = m.group(0).strip().lstrip("#").strip()
            start = m.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            content = text[start:end].strip()
            if content:
                sections.append((heading, content))
        return sections

    def _sliding_window(self, text: str) -> list[str]:
        """按 token 上限滑窗（粗略按字符估，1 token ≈ 2 中文字 / 4 英文字符）。
        Phase 1 不做 overlap（v2.0 7.3 overlap 100 为优化项，Phase 2 加）。
        """
        if self._est_tokens(text) <= self.MAX_TOKENS:
            return [text]

        chunks: list[str] = []
        sentences = [s for s in re.split(r"(?<=[。！？\n.!?])", text) if s.strip()]
        buf: list[str] = []
        buf_tokens = 0
        for s in sentences:
            s_tokens = self._est_tokens(s)
            if buf and buf_tokens + s_tokens > self.MAX_TOKENS:
                chunks.append("".join(buf))
                buf, buf_tokens = [], 0
            buf.append(s)
            buf_tokens += s_tokens

        if buf:
            last = "".join(buf)
            # 最后块超限且多句：二分切
            if buf_tokens > self.MAX_TOKENS and len(buf) > 1:
                mid = len(buf) // 2
                chunks.append("".join(buf[:mid]))
                chunks.append("".join(buf[mid:]))
            else:
                chunks.append(last)
        return chunks

    @staticmethod
    def _est_tokens(text: str) -> float:
        """粗略估算 token 数：中文 0.5 token/字，英文 0.25 token/字符（浮点保证累加一致性）。"""
        cn = sum(1 for c in text if "一" <= c <= "鿿")
        en = len(text) - cn
        return cn / 2 + en / 4

    def _keep_overlap(self, buf: list[str], buf_tokens: int) -> tuple[list[str], int]:
        """保留末尾 OVERLAP tokens。"""
        kept: list[str] = []
        kept_tokens = 0
        for s in reversed(buf):
            s_tokens = self._est_tokens(s)
            if kept_tokens + s_tokens > self.OVERLAP:
                break
            kept.insert(0, s)
            kept_tokens += s_tokens
        return kept, kept_tokens
