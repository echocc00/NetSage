"""知识库 chunk ORM（v2.0 六章 6.2 pgvector）。

向量 + BM25 混合检索，HNSW 索引。
"""
from __future__ import annotations

from pgvector.sqlalchemy import Vector
from sqlalchemy import TIMESTAMP, Column, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class KbChunk(Base):
    """知识库分块表。向量列 + BM25 tsvector 列（迁移时建索引）。"""

    __tablename__ = "kb_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    doc_id: Mapped[str] = mapped_column(String(128), index=True)     # 文档来源
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[str | None] = mapped_column(String(64), index=True)  # VRP-8.180
    captured_at: Mapped[str | None] = mapped_column(TIMESTAMP, nullable=True)
    chunk_text: Mapped[str] = mapped_column(Text)
    embedding = Column(Vector(1024))  # bge-m3 dim=1024
    metadata_json: Mapped[dict | None] = mapped_column(Text, nullable=True)  # 章节/标签 JSON
    tier: Mapped[int] = mapped_column(Integer, default=1)  # L1-L5 知识分层
    # bm25_tokens tsvector 列由迁移脚本建（GENERATED + GIN 索引）
