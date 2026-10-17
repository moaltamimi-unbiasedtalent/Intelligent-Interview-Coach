"""Usage-quota counters and reservations (W12.4D-P4-A). SCHEMA ONLY: nothing is seeded, no allowance is stored, enforcement stays disabled.

Additive. ``usage_quota_counters`` holds consumed units per user, feature and UTC period; ``usage_quota_reservations`` holds one row per LOGICAL operation
(unique ``op_key``) so retries never consume twice and an interrupted operation can be recovered. Neither table holds candidate content. ``user_id`` cascades
on account deletion. With both tables empty nothing changes for any candidate. Downgrade drops both (operational accounting only). Chains from 0032.

Revision ID: 0033_usage_quotas
Revises: 0032_ai_operation_events
Create Date: 2026-10-17
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0033_usage_quotas"
down_revision = "0032_ai_operation_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "usage_quota_counters",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("feature", sa.String(length=32), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used", sa.Integer(), server_default="0", nullable=False),
        sa.Column("policy_version", sa.String(length=24), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "feature", "period_start", name="uq_quota_counter"),
        sa.CheckConstraint("used >= 0", name="ck_quota_counter_used"),
    )
    op.create_table(
        "usage_quota_reservations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("op_key", sa.String(length=120), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("feature", sa.String(length=32), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("state", sa.String(length=10), server_default="reserved", nullable=False),
        sa.Column("policy_version", sa.String(length=24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("op_key", name="uq_quota_reservation_key"),
        sa.CheckConstraint("state IN ('reserved', 'committed', 'released')", name="ck_quota_reservation_state"),
    )
    op.create_index("ix_quota_reservation_state_expiry", "usage_quota_reservations", ["state", "expires_at"])


def downgrade() -> None:
    op.drop_index("ix_quota_reservation_state_expiry", table_name="usage_quota_reservations")
    op.drop_table("usage_quota_reservations")
    op.drop_table("usage_quota_counters")
