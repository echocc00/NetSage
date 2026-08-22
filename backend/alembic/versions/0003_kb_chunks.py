"""kb_chunks 表 + pgvector HNSW 索引 + BM25 tsvector。

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-21
"""
from __future__ import annotations

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS kb_chunks (
            id BIGSERIAL PRIMARY KEY,
            doc_id VARCHAR(128) NOT NULL,
            source_url TEXT,
            version VARCHAR(64),
            captured_at TIMESTAMP,
            chunk_text TEXT NOT NULL,
            embedding vector(1024),
            metadata_json TEXT,
            tier INT DEFAULT 1,
            bm25_tokens tsvector GENERATED ALWAYS AS (to_tsvector('simple', chunk_text)) STORED
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_kb_doc_id ON kb_chunks(doc_id);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_kb_version ON kb_chunks(version);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_kb_chunks_embedding ON kb_chunks USING hnsw (embedding vector_cosine_ops);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_kb_chunks_bm25 ON kb_chunks USING gin (bm25_tokens);")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS kb_chunks;")
