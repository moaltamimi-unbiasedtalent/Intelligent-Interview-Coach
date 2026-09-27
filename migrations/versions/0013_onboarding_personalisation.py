"""First-run onboarding lifecycle + Mo personalisation preferences (P10B Wave 2).

Additive and backward-compatible. Adds:
- users.onboarding_completed_at (nullable) + users.onboarding_step (default 0) — the first-run
  onboarding lifecycle. NULL completed_at = onboarding pending.
- user_preferences.coaching_style (default 'balanced') + career_geography (default '') +
  target_role (default '') — bounded, low-sensitivity account defaults.

**Existing-user backfill (safety):** every existing account is set to onboarding-completed
(`onboarding_completed_at = now`) so no current user is ever blocked behind onboarding. New accounts
insert with NULL (pending) and enter onboarding. No data is moved or destroyed; device-level
preferences (dictation locale, voice/profile) stay in the browser and are NOT added here. Chains
from 0012. Single head.

Revision ID: 0013_onboarding_personalisation
Revises: 0012_document_failure_kind
Create Date: 2026-09-27
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0013_onboarding_personalisation"
down_revision = "0012_document_failure_kind"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("onboarding_completed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("onboarding_step", sa.Integer(), nullable=False, server_default="0"))

    op.add_column("user_preferences", sa.Column("coaching_style", sa.String(length=16), nullable=False, server_default="balanced"))
    op.add_column("user_preferences", sa.Column("career_geography", sa.String(length=32), nullable=False, server_default=""))
    op.add_column("user_preferences", sa.Column("target_role", sa.String(length=200), nullable=False, server_default=""))

    # Backfill: existing accounts are treated as onboarding-completed so they retain access.
    op.execute("UPDATE users SET onboarding_completed_at = CURRENT_TIMESTAMP WHERE onboarding_completed_at IS NULL")


def downgrade() -> None:
    op.drop_column("user_preferences", "target_role")
    op.drop_column("user_preferences", "career_geography")
    op.drop_column("user_preferences", "coaching_style")
    op.drop_column("users", "onboarding_step")
    op.drop_column("users", "onboarding_completed_at")
