"""检索器：向量 + BM25 混合检索 + HyDE 多路召回（v2.0 七章 7.2）。"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.rag.embedder import Embedder


@dataclass
class RetrievedChunk:
    text: str
    doc_id: str
    source_url: str | None
    version: str | None
    tier: int
    score: float
    metadata: dict


# 网络同义词表（v2.0 7.2 查询改写）
SYNONYMS: dict[str, list[str]] = {
    "neighbor": ["adjacency", "peer"],
    "neighbour": ["adjacency", "peer"],
    "peer": ["neighbor", "adjacency"],
    "adjacency": ["neighbor", "peer"],
    "flap": ["flapping", "oscillation"],
    "shutdown": ["down", "disable"],
}


def rewrite_query(query: str) -> str:
    """查询改写：同义词扩展。"""
    words = query.lower().split()
    expanded: list[str] = []
    for w in words:
        expanded.append(w)
        expanded.extend(SYNONYMS.get(w, []))
    return " ".join(expanded)


class HybridRetriever:
    """向量 + BM25 混合检索。"""

    def __init__(self, embedder: Embedder, session: AsyncSession) -> None:
        self.embedder = embedder
        self.session = session

    async def search(
        self,
        query: str,
        top_k: int = 50,
        tier_filter: int | None = None,
    ) -> list[RetrievedChunk]:
        """混合检索：原始 + 改写 query 顺序向量召回 + BM25（async session 不支持并发）。"""
        rewritten = rewrite_query(query)

        # async session 不支持并发，顺序执行
        vec_results = await self._vector_search(query, top_k, tier_filter)
        bm25_results = await self._bm25_search(rewritten, top_k, tier_filter)

        # 合并去重 + 简单分数融合
        merged: dict[str, RetrievedChunk] = {}
        for r in vec_results + bm25_results:
            key = f"{r.doc_id}:{r.text[:64]}"
            if key in merged:
                merged[key].score = max(merged[key].score, r.score)
            else:
                merged[key] = r

        ranked = sorted(merged.values(), key=lambda x: x.score, reverse=True)
        return ranked[:top_k]

    async def _vector_search(
        self, query: str, top_k: int, tier_filter: int | None
    ) -> list[RetrievedChunk]:
        emb = self.embedder.encode([query])[0]
        tier_clause = "AND tier = :tier" if tier_filter else ""
        sql = text(f"""
            SELECT doc_id, chunk_text, source_url, version, tier, metadata_json,
                   1 - (embedding <=> :emb) AS score
            FROM kb_chunks
            WHERE embedding IS NOT NULL {tier_clause}
            ORDER BY embedding <=> :emb
            LIMIT :limit
        """)
        params: dict = {"emb": str(emb), "limit": top_k}
        if tier_filter:
            params["tier"] = tier_filter
        result = await self.session.execute(sql, params)
        return [self._row_to_chunk(r, r.score) for r in result]

    async def _bm25_search(
        self, query: str, top_k: int, tier_filter: int | None
    ) -> list[RetrievedChunk]:
        tier_clause = "AND tier = :tier" if tier_filter else ""
        sql = text(f"""
            SELECT doc_id, chunk_text, source_url, version, tier, metadata_json,
                   ts_rank(bm25_tokens, plainto_tsquery('simple', :q)) AS score
            FROM kb_chunks
            WHERE bm25_tokens @@ plainto_tsquery('simple', :q) {tier_clause}
            ORDER BY score DESC
            LIMIT :limit
        """)
        params: dict = {"q": query, "limit": top_k}
        if tier_filter:
            params["tier"] = tier_filter
        result = await self.session.execute(sql, params)
        return [self._row_to_chunk(r, r.score or 0.0) for r in result]

    @staticmethod
    def _row_to_chunk(row, score: float) -> RetrievedChunk:
        import json

        metadata = {}
        if row.metadata_json:
            try:
                metadata = json.loads(row.metadata_json)
            except Exception:
                metadata = {}
        return RetrievedChunk(
            text=row.chunk_text,
            doc_id=row.doc_id,
            source_url=row.source_url,
            version=row.version,
            tier=row.tier,
            score=float(score),
            metadata=metadata,
        )
