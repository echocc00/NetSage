"""tenants 表（Phase 4 M11 多租户 + SSO）。

Revision ID: 0006
Revises: 0005
Create Date: 2026-08-24
"""
from __future__ import annotations

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS tenants (
            id BIGSERIAL PRIMARY KEY,
            name VARCHAR(128) NOT NULL UNIQUE,
            slug VARCHAR(64) NOT NULL UNIQUE,
            plan VARCHAR(32) DEFAULT 'free',
            quota_devices INT DEFAULT 100,
            quota_users INT DEFAULT 10,
            sso_enabled BOOLEAN DEFAULT FALSE,
            oidc_client_id VARCHAR(128) DEFAULT '',
            oidc_client_secret VARCHAR(256) DEFAULT '',
            oidc_discovery_url VARCHAR(256) DEFAULT '',
            enabled BOOLEAN DEFAULT TRUE,
            metadata_json TEXT DEFAULT '{}',
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_tenant_slug ON tenants(slug);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_tenant_plan ON tenants(plan);")
    # 默认租户
    op.execute("""
        INSERT INTO tenants (name, slug, plan) VALUES ('Default', 'default', 'enterprise')
        ON CONFLICT (slug) DO NOTHING;
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS tenants;")
