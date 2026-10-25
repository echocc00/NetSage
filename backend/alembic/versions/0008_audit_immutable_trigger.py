"""audit_logs 防篡改 trigger 兜底（v0.5.1：等保 INSERT ONLY 最后防线）。

此前仅 REVOKE UPDATE/DELETE——对表 owner（应用连接用户）无效（评审确认）。
现加 BEFORE UPDATE/DELETE trigger 强制抛异常，owner 也无法改写/删除审计记录；
哈希重算校验（verify_chain）为第二道检测防线。

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-25
"""
from __future__ import annotations

from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE OR REPLACE FUNCTION audit_logs_immutable() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'audit_logs is INSERT ONLY (等保三权分立): % 被拒绝', TG_OP;
        END;
        $$ LANGUAGE plpgsql;
    """)
    op.execute("DROP TRIGGER IF EXISTS audit_logs_no_update ON audit_logs;")
    op.execute("""
        CREATE TRIGGER audit_logs_no_update
            BEFORE UPDATE ON audit_logs
            FOR EACH ROW EXECUTE FUNCTION audit_logs_immutable();
    """)
    op.execute("DROP TRIGGER IF EXISTS audit_logs_no_delete ON audit_logs;")
    op.execute("""
        CREATE TRIGGER audit_logs_no_delete
            BEFORE DELETE ON audit_logs
            FOR EACH ROW EXECUTE FUNCTION audit_logs_immutable();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS audit_logs_no_update ON audit_logs;")
    op.execute("DROP TRIGGER IF EXISTS audit_logs_no_delete ON audit_logs;")
    op.execute("DROP FUNCTION IF EXISTS audit_logs_immutable();")
