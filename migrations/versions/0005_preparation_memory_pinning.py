"""Preparation-memory pinning (post-Sprint 4 P2 — memory management UX).

Adds ``preparation_memories.pinned`` (BOOLEAN NOT NULL DEFAULT FALSE) so a candidate
can prioritise a memory within otherwise-relevant memories at load time. Pinning is a
deterministic load-priority signal only — it never makes memory an instruction and
never overrides the current request.

Existing rows default to ``pinned = FALSE`` (no memory loss, no behaviour change until
a user pins something). Explicit Alembic operations only; does NOT modify 0001–0004.
Single head.

Revision ID: 0005_preparation_memory_pinning
Revises: 0004_completed_interview_source_session
Create Date: 2026-09-09
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0005_preparation_memory_pinning"
down_revision = "0004_completed_interview_source_session"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # server_default backfills existing rows to FALSE on both SQLite and PostgreSQL.
    op.add_column(
        "preparation_memories",
        sa.Column(
            "pinned",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("preparation_memories", "pinned")
