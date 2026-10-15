"""Operator recovery evidence for provider billing records (W12.4D-E).

Additive only. ``billing_recovery_actions`` is the append-only record of one operator recovery action (who, what, why, bounded result; unique idempotency
key). ``billing_provider_events`` gains ``attempt_limit`` and ``operator_retries`` so an operator retry can allow a bounded number of extra processing
attempts WITHOUT erasing ``attempt_count`` (the true history). Nothing is deleted or rewritten. The downgrade is FAIL-CLOSED: it refuses while any
recovery action exists, because that table is the only record of operator interventions on financial records. Chains from 0029. Single head.

Revision ID: 0030_billing_recovery
Revises: 0029_provider_webhooks
Create Date: 2026-10-16
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0030_billing_recovery"
down_revision = "0029_provider_webhooks"
branch_labels = None
depends_on = None

ACTIONS = ("retry_event", "requeue_lease", "reconcile_link")
STATUSES = ("requested", "completed", "failed", "refused")


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


def upgrade() -> None:
    op.add_column("billing_provider_events", sa.Column("attempt_limit", sa.Integer(), server_default="6", nullable=False))
    op.add_column("billing_provider_events", sa.Column("operator_retries", sa.Integer(), server_default="0", nullable=False))
    op.create_table(
        "billing_recovery_actions",
        sa.Column("id", sa.Integer(), nullable=False), sa.Column("public_id", sa.String(length=32), nullable=False),
        sa.Column("action", sa.String(length=16), nullable=False), sa.Column("event_id", sa.Integer(), nullable=True), sa.Column("link_id", sa.Integer(), nullable=True),
        sa.Column("actor_user_id", sa.Integer(), nullable=True), sa.Column("reason", sa.String(length=300), nullable=False),
        sa.Column("idempotency_key", sa.String(length=64), nullable=False), sa.Column("status", sa.String(length=12), server_default="requested", nullable=False),
        sa.Column("result_category", sa.String(length=40), nullable=True), sa.Column("previous_status", sa.String(length=16), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["event_id"], ["billing_provider_events.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["link_id"], ["billing_provider_links.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.CheckConstraint(_in("action", ACTIONS), name="ck_bra_action"),
        sa.CheckConstraint(_in("status", STATUSES), name="ck_bra_status"),
        sa.UniqueConstraint("idempotency_key", name="uq_bra_idempotency"),
    )
    op.create_index("ix_billing_recovery_actions_public_id", "billing_recovery_actions", ["public_id"], unique=True)
    op.create_index("ix_bra_created", "billing_recovery_actions", ["created_at"])


def downgrade() -> None:
    """FAIL CLOSED: refuses (deleting nothing) while any operator recovery action exists. See the W12.4D-E documentation for the operator procedure."""
    bind = op.get_bind()
    count = bind.execute(sa.text("SELECT COUNT(*) FROM billing_recovery_actions")).scalar() or 0
    if count:
        raise RuntimeError(
            f"Refusing to downgrade 0030_billing_recovery: {count} operator recovery action(s) exist and are the only record of interventions on financial "
            "records. Take a verified backup, export billing_recovery_actions, and only then clear it deliberately before repeating the downgrade.")
    op.drop_table("billing_recovery_actions")
    with op.batch_alter_table("billing_provider_events") as batch:
        batch.drop_column("operator_retries")
        batch.drop_column("attempt_limit")
