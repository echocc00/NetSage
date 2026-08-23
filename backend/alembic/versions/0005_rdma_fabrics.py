"""rdma_fabrics 表（Phase 4 RdmAgent 差异化护城河）。

Revision ID: 0005
Revises: 0004
Create Date: 2026-08-24
"""
from __future__ import annotations

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS rdma_fabrics (
            id BIGSERIAL PRIMARY KEY,
            name VARCHAR(200) NOT NULL,
            site VARCHAR(100) DEFAULT '',
            vendor VARCHAR(50) NOT NULL,
            fabric_type VARCHAR(32) DEFAULT 'rocev2',
            pfc_priority INT DEFAULT 3,
            ecn_enabled BOOLEAN DEFAULT TRUE,
            dcqcn_enabled BOOLEAN DEFAULT TRUE,
            mtu INT DEFAULT 9100,
            tuning_params TEXT DEFAULT '{}',
            topology TEXT DEFAULT '{}',
            created_by VARCHAR(50) DEFAULT 'ai',
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_rdma_site ON rdma_fabrics(site);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_rdma_vendor ON rdma_fabrics(vendor);")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS rdma_fabrics;")
