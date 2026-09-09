"""Candidate feedback (post-Sprint 4 P5 — feedback loop).

Adds the ``user_feedback`` table: a user-scoped rating (helpful / not_helpful) plus an
optional bounded comment, attached BY REFERENCE to one logical output (an Agent answer,
an Interview evaluation, or a final report). It stores NO copy of any answer, prompt,
JD, CV, evaluation, report, memory, retrieved evidence, system prompt, provider output
or checkpoint.

A UNIQUE (user_id, surface, target_id) enforces one current rating per logical output
(the upsert target). Explicit Alembic operations only; does NOT modify 0001–0005.
Single head.

Revision ID: 0006_user_feedback
Revises: 0005_preparation_memory_pinning
Create Date: 2026-09-09
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0006_user_feedback"
down_revision = "0005_preparation_memory_pinning"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_feedback",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("surface", sa.String(length=32), nullable=False),
        sa.Column("target_id", sa.String(length=128), nullable=False),
        sa.Column("rating", sa.String(length=16), nullable=False),
        sa.Column("comment", sa.String(length=1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "surface", "target_id", name="uq_user_feedback_target"),
    )
    op.create_index("ix_user_feedback_user_id", "user_feedback", ["user_id"])
    op.create_index("ix_user_feedback_surface", "user_feedback", ["surface"])


def downgrade() -> None:
    op.drop_index("ix_user_feedback_surface", table_name="user_feedback")
    op.drop_index("ix_user_feedback_user_id", table_name="user_feedback")
    op.drop_table("user_feedback")
