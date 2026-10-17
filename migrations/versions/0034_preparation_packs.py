"""Opportunity Preparation Packs (W12.4D-P5-A). SCHEMA ONLY: nothing is seeded or back-filled, generation stays disabled.

Additive. ``preparation_packs`` stores one candidate-owned Pack revision per row: schema-validated structured content with evidence categories and source
provenance, bounded generation metadata and a bounded failure category. It never stores interview transcripts, feedback, reports, analytics snapshots, raw
model output or prompts. ``op_key`` is unique (idempotency); a partial unique index allows at most one ``generating`` row per user and opportunity, and a unique constraint makes a revision number unique per user and opportunity. ``user_id``
cascades on account deletion; ``opportunity_id`` is SET NULL so a Pack survives the deletion of its opportunity. With the table empty nothing changes for any
candidate. Downgrade drops the table. Chains from 0033. Single head.

Revision ID: 0034_preparation_packs
Revises: 0033_usage_quotas
Create Date: 2026-10-18
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0034_preparation_packs"
down_revision = "0033_usage_quotas"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "preparation_packs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("op_key", sa.String(length=120), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("opportunity_id", sa.Integer(), nullable=True),
        sa.Column("revision", sa.Integer(), server_default="1", nullable=False),
        sa.Column("status", sa.String(length=24), server_default="generating", nullable=False),
        sa.Column("schema_version", sa.String(length=16), nullable=False),
        sa.Column("content", sa.JSON(), nullable=True),
        sa.Column("generation", sa.JSON(), nullable=True),
        sa.Column("failure_category", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["opportunity_id"], ["opportunities.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("op_key", name="uq_pack_op_key"),
        sa.UniqueConstraint("user_id", "opportunity_id", "revision", name="uq_pack_revision"),
        sa.CheckConstraint("status IN ('generating', 'completed', 'failed', 'insufficient_evidence')", name="ck_pack_status"),
    )
    op.create_index("ix_preparation_packs_user_id", "preparation_packs", ["user_id"])
    op.create_index("ix_pack_user_opp_created", "preparation_packs", ["user_id", "opportunity_id", "created_at"])
    op.create_index("uq_pack_one_generating", "preparation_packs", ["user_id", "opportunity_id"], unique=True,
                    sqlite_where=sa.text("status = 'generating'"), postgresql_where=sa.text("status = 'generating'"))


def downgrade() -> None:
    op.drop_index("uq_pack_one_generating", table_name="preparation_packs")
    op.drop_index("ix_pack_user_opp_created", table_name="preparation_packs")
    op.drop_index("ix_preparation_packs_user_id", table_name="preparation_packs")
    op.drop_table("preparation_packs")
