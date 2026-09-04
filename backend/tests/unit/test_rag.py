"""RAG 管线单元测试（v2.0 七章 + 二十二章）。

覆盖：
- ManualChunker 四级分块 + token 上限 + overlap
- HashEmbedder 确定性 + L2 归一化
- rewrite_query 同义词扩展
- 引用溯源字段

DB 依赖的检索/入库测试放 integration（需 pgvector）。
"""
from __future__ import annotations

import numpy as np

from app.rag.chunker import ManualChunker
from app.rag.embedder import HashEmbedder
from app.rag.retriever import SYNONYMS, rewrite_query

# ===== Chunker =====


def test_chunk_single_section_under_limit():
    chunker = ManualChunker()
    text = "## OSPF 概述\nOSPF 是链路状态路由协议。"
    chunks = chunker.chunk(text, doc_id="vrp-ospf")
    assert len(chunks) >= 1
    assert chunks[0].doc_id == "vrp-ospf"
    assert "OSPF" in chunks[0].text


def test_chunk_splits_by_heading():
    chunker = ManualChunker()
    text = "## 概述\n内容A\n## 配置\n内容B\n## 验证\n内容C"
    chunks = chunker.chunk(text, doc_id="doc1")
    assert len(chunks) >= 3
    paths = [c.metadata["path"] for c in chunks]
    assert "概述" in paths
    assert "配置" in paths


def test_chunk_respects_token_limit():
    """超长文本按 1500 token 滑窗切多块（v2.0 7.3 每块 ≤1500 token）。"""
    chunker = ManualChunker()
    long_section = "## 大段\n" + ("OSPF 邻居状态机包含多个阶段。" * 500)
    chunks = chunker.chunk(long_section, doc_id="big")
    assert len(chunks) > 1
    for c in chunks:
        assert ManualChunker._est_tokens(c.text) <= 1500


def test_chunk_metadata_preserved():
    chunker = ManualChunker()
    chunks = chunker.chunk("## A\nx", doc_id="d", version="VRP-8.180", source_url="http://x")
    assert chunks[0].metadata["version"] == "VRP-8.180"


# ===== Embedder =====


def test_hash_embedder_deterministic():
    """同一文本同一向量（确定性，可复现）。"""
    emb = HashEmbedder(dim=64)
    v1 = emb.encode(["hello"])[0]
    v2 = emb.encode(["hello"])[0]
    assert v1 == v2


def test_hash_embedder_different_texts_differ():
    emb = HashEmbedder(dim=64)
    v1, v2 = emb.encode(["hello", "world"])
    assert v1 != v2


def test_hash_embedder_l2_normalized():
    """向量 L2 归一化（余弦相似度有效）。"""
    emb = HashEmbedder(dim=128)
    for v in emb.encode(["测试", "network", "OSPF 邻居"]):
        norm = np.linalg.norm(np.array(v))
        assert abs(norm - 1.0) < 1e-5


def test_hash_embedder_dim():
    assert HashEmbedder(dim=1024).dim == 1024


# ===== 查询改写 =====


def test_rewrite_query_expands_synonyms():
    """同义词扩展（OSPF Neighbor ↔ Adjacency ↔ Peer，v2.0 7.2）。"""
    rewritten = rewrite_query("OSPF neighbor down")
    assert "adjacency" in rewritten or "peer" in rewritten


def test_rewrite_query_no_synonyms_passthrough():
    rewritten = rewrite_query("配置 VLAN")
    assert "配置" in rewritten


def test_synonyms_bidirectional():
    assert "neighbor" in SYNONYMS.get("peer", [])
    assert "peer" in SYNONYMS.get("neighbor", [])
