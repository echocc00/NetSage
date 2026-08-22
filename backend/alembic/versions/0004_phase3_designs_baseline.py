"""network_designs 表（Phase 3 自研 Nautobot App v0.1 本地落地）。

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-23
"""
from __future__ import annotations

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS network_designs (
            id BIGSERIAL PRIMARY KEY,
            name VARCHAR(200) NOT NULL,
            site VARCHAR(100) DEFAULT '',
            scenario VARCHAR(50) NOT NULL,
            vendor VARCHAR(50) NOT NULL,
            hld TEXT DEFAULT '{}',
            lld TEXT DEFAULT '{}',
            config_diff TEXT DEFAULT '',
            rollback_config TEXT DEFAULT '',
            lint_passed BOOLEAN DEFAULT FALSE,
            created_by VARCHAR(50) DEFAULT 'ai',
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_designs_site ON network_designs(site);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_designs_scenario ON network_designs(scenario);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_designs_vendor ON network_designs(vendor);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_designs_created_by ON network_designs(created_by);")
    op.execute("""
        CREATE TABLE IF NOT EXISTS baseline_rules (
            id BIGSERIAL PRIMARY KEY,
            rule_id VARCHAR(64) NOT NULL UNIQUE,
            vendor VARCHAR(50) NOT NULL,
            category VARCHAR(50) NOT NULL,
            severity VARCHAR(16) NOT NULL,
            description TEXT NOT NULL,
            check_type VARCHAR(16) NOT NULL,
            check_expr TEXT NOT NULL,
            remediation TEXT DEFAULT '',
            standard_ref VARCHAR(128) DEFAULT '',
            enabled BOOLEAN DEFAULT TRUE
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_baseline_vendor ON baseline_rules(vendor);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_baseline_category ON baseline_rules(category);")
    op.execute("""
        CREATE TABLE IF NOT EXISTS compliance_reports (
            id BIGSERIAL PRIMARY KEY,
            device_id INT,
            vendor VARCHAR(50),
            scan_result TEXT,
            acl_report TEXT,
            score INT DEFAULT 0,
            markdown TEXT DEFAULT '',
            csv_text TEXT DEFAULT '',
            created_by VARCHAR(50) DEFAULT 'ai',
            created_at TIMESTAMP DEFAULT NOW()
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_reports_device ON compliance_reports(device_id);")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS compliance_reports;")
    op.execute("DROP TABLE IF EXISTS baseline_rules;")
    op.execute("DROP TABLE IF EXISTS network_designs;")
