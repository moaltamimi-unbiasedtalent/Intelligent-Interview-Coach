"""Completed-history crash idempotency (Sprint 4 Phase 10 correction).

Adds ``interviews.source_session_id`` (the durable interview session a completed
history row was saved from) plus a user-scoped UNIQUE INDEX
``(user_id, source_session_id)`` so a crash between the history commit and the
durable-session save can never create a duplicate completed-history row on retry.

A unique INDEX (not a table constraint) keeps NULLs distinct on both SQLite and
PostgreSQL, so existing rows (``source_session_id = NULL``) remain valid and never
collide. Explicit Alembic operations only; does NOT modify 0001/0002/0003. Single
head.

Revision ID: 0004_completed_interview_source_session
Revises: 0003_interview_sessions
Create Date: 2026-09-08
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0004_completed_interview_source_session"
down_revision = "0003_interview_sessions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "interviews",
        sa.Column("source_session_id", sa.String(length=64), nullable=True),
    )
    op.create_index(
        "uq_interviews_user_source_session",
        "interviews",
        ["user_id", "source_session_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_interviews_user_source_session", table_name="interviews")
    op.drop_column("interviews", "source_session_id")
