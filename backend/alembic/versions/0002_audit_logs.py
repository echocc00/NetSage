"""audit_logs 表 + INSERT ONLY 权限（等保三权分立）

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-21
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 审计日志表：不可篡改哈希链（v2.0 八章 + security C4 修复）
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("ts", sa.String(32), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("resource_type", sa.String(32), nullable=False),
        sa.Column("resource_id", sa.String(64), nullable=True),
        sa.Column("before", sa.Text(), nullable=True),
        sa.Column("after", sa.Text(), nullable=True),
        sa.Column("prev_hash", sa.String(64), nullable=False),
        sa.Column("self_hash", sa.String(64), nullable=False, unique=True),
    )

    # 等保三权分立：应用账号仅 INSERT，禁止 UPDATE/DELETE（纵深防御）
    op.execute("REVOKE UPDATE, DELETE ON audit_logs FROM PUBLIC")
    # 应用连接账号（netsage）默认不被额外授权 UPDATE/DELETE；
    # 若应用账号是表 owner 则需显式撤销（PG owner 可绕过，靠 DB trigger 兜底见 0003）


def downgrade() -> None:
    op.drop_table("audit_logs")