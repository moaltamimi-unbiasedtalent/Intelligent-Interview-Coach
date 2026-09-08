"""Preparation memory (Sprint 4 Phase 7 — long-term preparation memory).

Adds the ``preparation_memories`` table: selective, user-scoped, structured
preparation facts that persist across sessions. Explicit Alembic operations only;
does NOT import the live model metadata and does NOT modify 0001_initial.

Revision ID: 0002_preparation_memory
Revises: 0001_initial
Create Date: 2026-09-08
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002_preparation_memory"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "preparation_memories",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("summary", sa.String(length=500), nullable=False),
        sa.Column("target_role", sa.String(length=200), nullable=True),
        sa.Column("source_run_id", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_preparation_memories_user_id", "preparation_memories", ["user_id"]
    )
    op.create_index(
        "ix_preparation_memories_user_category",
        "preparation_memories",
        ["user_id", "category"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_preparation_memories_user_category", table_name="preparation_memories"
    )
    op.drop_index(
        "ix_preparation_memories_user_id", table_name="preparation_memories"
    )
    op.drop_table("preparation_memories")
