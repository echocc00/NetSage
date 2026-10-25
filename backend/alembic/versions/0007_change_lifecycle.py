"""变更生命周期表（v0.5.0 审查 P1 修复：models 14 表此前仅迁移 7 表）。

补齐：projects / credentials / devices / change_requests / change_steps /
approvals / config_snapshots。audit_logs.prev_hash 加唯一约束，
并发追加写链时第二个事务会触发 IntegrityError 由服务层重试（线性链保证）。

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-25
"""
from __future__ import annotations

from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id BIGSERIAL PRIMARY KEY,
            name VARCHAR(128) NOT NULL UNIQUE,
            description TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        );
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS credentials (
            id BIGSERIAL PRIMARY KEY,
            ref VARCHAR(256) NOT NULL,
            type VARCHAR(16) NOT NULL,
            username VARCHAR(64) DEFAULT '',
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        );
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS devices (
            id BIGSERIAL PRIMARY KEY,
            name VARCHAR(128) NOT NULL UNIQUE,
            vendor VARCHAR(32) NOT NULL,
            os VARCHAR(32) NOT NULL,
            model VARCHAR(64) DEFAULT '',
            version VARCHAR(32) DEFAULT '',
            mgmt_ip VARCHAR(64) NOT NULL,
            role VARCHAR(32) DEFAULT '',
            project_id BIGINT REFERENCES projects(id),
            credential_id BIGINT REFERENCES credentials(id),
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        );
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS change_requests (
            id BIGSERIAL PRIMARY KEY,
            project_id BIGINT REFERENCES projects(id),
            title VARCHAR(256) NOT NULL,
            intent TEXT NOT NULL,
            devices TEXT DEFAULT '[]',
            configs TEXT DEFAULT '{}',
            assertions TEXT DEFAULT '[]',
            impact TEXT DEFAULT '{}',
            pipeline_result TEXT DEFAULT '',
            status VARCHAR(32) DEFAULT 'draft',
            created_by BIGINT NOT NULL,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_change_requests_status ON change_requests(status);")
    op.execute("""
        CREATE TABLE IF NOT EXISTS change_steps (
            id BIGSERIAL PRIMARY KEY,
            request_id BIGINT NOT NULL REFERENCES change_requests(id),
            seq INT NOT NULL,
            device_id BIGINT NOT NULL,
            config_diff TEXT DEFAULT '',
            rollback_config TEXT DEFAULT '',
            status VARCHAR(32) DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        );
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS approvals (
            id BIGSERIAL PRIMARY KEY,
            request_id BIGINT NOT NULL REFERENCES change_requests(id),
            approver_id BIGINT NOT NULL,
            decision VARCHAR(16) NOT NULL,
            comment TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        );
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS config_snapshots (
            id BIGSERIAL PRIMARY KEY,
            device_id BIGINT NOT NULL,
            change_request_id BIGINT,
            object_key VARCHAR(256) NOT NULL,
            config_hash VARCHAR(64) NOT NULL,
            content TEXT DEFAULT '',
            restored BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_config_snapshots_key ON config_snapshots(object_key);")
    # 哈希链线性保证：同一 prev_hash 只允许一条记录（audit_logs 已存在，仅加约束）
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_audit_prev_hash ON audit_logs(prev_hash);"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_audit_prev_hash;")
    op.execute("DROP TABLE IF EXISTS config_snapshots;")
    op.execute("DROP TABLE IF EXISTS approvals;")
    op.execute("DROP TABLE IF EXISTS change_steps;")
    op.execute("DROP TABLE IF EXISTS change_requests;")
    op.execute("DROP TABLE IF EXISTS devices;")
    op.execute("DROP TABLE IF EXISTS credentials;")
    op.execute("DROP TABLE IF EXISTS projects;")
