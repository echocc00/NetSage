"""RAG 集成测试：真实 ingest + 混合检索（需 PG+pgvector，v2.0 19.1 验收 8）。

标记 integration，CI 可选跑（docker-compose 起依赖后）。
"""
from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import SessionLocal
from app.rag.embedder import HashEmbedder
from app.rag.ingest import IngestService
from app.rag.retriever import HybridRetriever

pytestmark = pytest.mark.integration


@pytest_asyncio.fixture
async def session() -> AsyncSession:
    async with SessionLocal() as s:
        # 清空 kb_chunks 隔离测试
        from sqlalchemy import text
        await s.execute(text("DELETE FROM kb_chunks"))
        await s.commit()
        yield s
        await s.execute(text("DELETE FROM kb_chunks"))
        await s.commit()


@pytest.mark.asyncio
async def test_ingest_and_retrieve(session: AsyncSession):
    """ingest 华为 VRP OSPF 手册片段 → 检索命中（v2.0 22.2 引用溯源）。"""
    embedder = HashEmbedder(dim=1024)
    ingest = IngestService(embedder, session)

    manual = """## OSPF 邻居状态机
OSPF 邻居关系建立经历多个状态：Down、Init、2-Way、ExStart、Exchange、Loading、Full。
Hello 间隔不一致会导致邻居震荡。

## OSPF 区域配置
OSPF 划分区域减少 LSA 泛洪。ABR 连接骨干区域与非骨干区域。
"""
    count = await ingest.ingest_text(
        manual,
        doc_id="vrp-ospf-8.180",
        version="VRP-8.180",
        source_url="https://support.huawei.com/vrp-ospf",
        tier=1,
    )
    assert count >= 2  # 至少 2 个 chunk（两个章节）

    # 检索
    retriever = HybridRetriever(embedder, session)
    results = await retriever.search("OSPF 邻居震荡 hello", top_k=5)
    assert len(results) > 0
    top = results[0]
    assert top.doc_id == "vrp-ospf-8.180"
    assert top.version == "VRP-8.180"
    assert top.source_url is not None  # 引用溯源
    assert "邻居" in top.text or "Hello" in top.text


@pytest.mark.asyncio
async def test_ingest_bm25_search(session: AsyncSession):
    """BM25 精确关键词检索（v2.0 7.2 混合检索的 BM25 路）。"""
    embedder = HashEmbedder(dim=1024)
    ingest = IngestService(embedder, session)
    await ingest.ingest_text(
        "## BGP 配置\nrouter bgp 65001\nneighbor 10.1.1.1 remote-as 65002",
        doc_id="vrp-bgp",
        version="VRP-8.180",
    )
    retriever = HybridRetriever(embedder, session)
    results = await retriever.search("bgp 65001", top_k=5)
    assert any("bgp" in r.text.lower() for r in results)
