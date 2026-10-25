"""指标事件表（v0.6：合规/RCA/闭环运行历史落库）。

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-25
"""
from __future__ import annotations

from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS metric_events (
            id BIGSERIAL PRIMARY KEY,
            kind VARCHAR(32) NOT NULL,
            value DOUBLE PRECISION,
            detail TEXT DEFAULT '{}',
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_metric_events_kind ON metric_events(kind);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_metric_events_created ON metric_events(created_at);")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS metric_events;")
