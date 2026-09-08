"""Durable in-progress interview sessions (Sprint 4 Phase 10).

Adds the ``interview_sessions`` table: operational, resumable state (the serialised
``SessionData``) for interviews a candidate is still taking, so a browser refresh or
a backend restart never loses an in-progress interview. This is DISTINCT from the
completed interview record in ``interviews``/``reports``.

Explicit Alembic operations only; does NOT import live model metadata and does NOT
modify 0001_initial or 0002_preparation_memory. Portable across SQLite and
PostgreSQL. Single head.

Revision ID: 0003_interview_sessions
Revises: 0002_preparation_memory
Create Date: 2026-09-08
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003_interview_sessions"
down_revision = "0002_preparation_memory"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "interview_sessions",
        sa.Column("session_id", sa.String(length=64), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=200), nullable=True),
        sa.Column("state_payload", sa.JSON(), nullable=False),
        sa.Column("state_schema_version", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("active_operation", sa.String(length=64), nullable=True),
        sa.Column("operation_leased_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_accessed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "user_id", "idempotency_key", name="uq_interview_sessions_user_idem"
        ),
    )
    op.create_index(
        "ix_interview_sessions_user_id", "interview_sessions", ["user_id"]
    )
    op.create_index(
        "ix_interview_sessions_user_status",
        "interview_sessions",
        ["user_id", "status"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_interview_sessions_user_status", table_name="interview_sessions"
    )
    op.drop_index(
        "ix_interview_sessions_user_id", table_name="interview_sessions"
    )
    op.drop_table("interview_sessions")
