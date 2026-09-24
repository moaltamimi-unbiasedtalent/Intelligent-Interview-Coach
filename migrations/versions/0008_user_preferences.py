"""User preferences — response presentation depth (Capstone P2/E2).

Adds the ``user_preferences`` table holding a low-sensitivity, user-scoped
``response_detail`` (brief/detailed) preference. It is NOT candidate content, NOT a
model profile, and NOT entitlement-gated. Additive only; chains from 0007. Single head.

Revision ID: 0008_user_preferences
Revises: 0007_identity_platform
Create Date: 2026-09-24
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0008_user_preferences"
down_revision = "0007_identity_platform"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_preferences",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("response_detail", sa.String(length=16), nullable=False, server_default="brief"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", name="uq_user_preferences_user"),
    )
    op.create_index("ix_user_preferences_user_id", "user_preferences", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_user_preferences_user_id", table_name="user_preferences")
    op.drop_table("user_preferences")
