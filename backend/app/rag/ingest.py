"""文档入库管线（v2.0 七章 7.3 + 7.4）。

分块 → 向量化 → 存 kb_chunks。
华为 VRP 8.x 手册首发（用户决策）。
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.rag.chunker import Chunk, ManualChunker
from app.rag.embedder import Embedder

logger = get_logger("rag_ingest")


class IngestService:
    """文档分块入库。"""

    def __init__(self, embedder: Embedder, session: AsyncSession) -> None:
        self.embedder = embedder
        self.session = session
        self.chunker = ManualChunker()

    async def ingest_text(
        self,
        content: str,
        doc_id: str,
        source_url: str | None = None,
        version: str | None = None,
        tier: int = 1,
    ) -> int:
        """ ingest 单个文档，返回入库 chunk 数。"""
        chunks = self.chunker.chunk(content, doc_id)
        # 填充元数据
        for c in chunks:
            c.source_url = source_url
            c.version = version
            c.tier = tier

        # 批量向量化
        texts = [c.text for c in chunks]
        embeddings = self.embedder.encode(texts)

        # 批量插入
        from datetime import datetime

        now = datetime.utcnow()
        rows = [
            {
                "doc_id": c.doc_id,
                "source_url": c.source_url,
                "version": c.version,
                "captured_at": now,
                "chunk_text": c.text,
                "embedding": str(emb),
                "metadata_json": json.dumps(c.metadata, ensure_ascii=False),
                "tier": c.tier,
            }
            for c, emb in zip(chunks, embeddings, strict=True)
        ]

        sql = text("""
            INSERT INTO kb_chunks (doc_id, source_url, version, captured_at, chunk_text, embedding, metadata_json, tier)
            VALUES (:doc_id, :source_url, :version, :captured_at, :chunk_text, :embedding, :metadata_json, :tier)
        """)
        for row in rows:
            await self.session.execute(sql, row)
        await self.session.commit()

        logger.info("ingest_ok", doc_id=doc_id, chunks=len(rows), version=version)
        return len(rows)

    async def ingest_file(self, path: str, doc_id: str | None = None, **meta) -> int:
        """ ingest 文件。"""
        p = Path(path)
        content = p.read_text(encoding="utf-8")
        doc_id = doc_id or p.stem
        return await self.ingest_text(content, doc_id, **meta)
