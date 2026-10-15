"""Subscription-aware account closure case (W12.4D-F1R).

Additive. ``billing_account_closures`` is the single durable case that exists while a provider-managed subscription is unresolved at account closure: it keeps
the obligations in separate fields (closure requested, subscription resolution, provider cancellation, personal-data erasure) and holds NO personal data and
no provider identifier. One ACTIVE case per user (partial unique index). Nothing is deleted or rewritten. The downgrade is FAIL-CLOSED: it refuses while any
case exists, because the table is the only record of closure obligations. Chains from 0030. Single head.

Revision ID: 0031_account_closure
Revises: 0030_billing_recovery
Create Date: 2026-10-16
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0031_account_closure"
down_revision = "0030_billing_recovery"
branch_labels = None
depends_on = None

STATUSES = ("requested", "awaiting_provider", "resolved", "completed", "erased_reference_retained", "withdrawn", "needs_review")
RESOLUTION = ("not_required", "required", "pending_confirmation", "confirmed", "unavailable")
CANCELLATION = ("not_requested", "guided", "confirmed", "contract_unverified")
ERASURE = ("not_requested", "requested", "fulfilled", "restricted")
ACTIVE = "status IN ('requested', 'awaiting_provider', 'resolved', 'erased_reference_retained', 'needs_review') AND user_id IS NOT NULL"


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


def upgrade() -> None:
    op.create_table(
        "billing_account_closures",
        sa.Column("id", sa.Integer(), nullable=False), sa.Column("public_id", sa.String(length=32), nullable=False), sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=28), server_default="requested", nullable=False),
        sa.Column("subscription_resolution", sa.String(length=24), server_default="required", nullable=False),
        sa.Column("provider_cancellation", sa.String(length=24), server_default="guided", nullable=False),
        sa.Column("erasure_status", sa.String(length=16), server_default="not_requested", nullable=False),
        sa.Column("retention_basis", sa.String(length=40), nullable=True), sa.Column("review_required", sa.Boolean(), server_default=sa.text("0"), nullable=False),
        sa.Column("failure_category", sa.String(length=40), nullable=True), sa.Column("privacy_request_public_id", sa.String(length=32), nullable=True),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False), sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.CheckConstraint(_in("status", STATUSES), name="ck_bac_status"),
        sa.CheckConstraint(_in("subscription_resolution", RESOLUTION), name="ck_bac_resolution"),
        sa.CheckConstraint(_in("provider_cancellation", CANCELLATION), name="ck_bac_cancellation"),
        sa.CheckConstraint(_in("erasure_status", ERASURE), name="ck_bac_erasure"),
    )
    op.create_index("ix_billing_account_closures_public_id", "billing_account_closures", ["public_id"], unique=True)
    op.create_index("uq_bac_one_active_per_user", "billing_account_closures", ["user_id"], unique=True,
                    sqlite_where=sa.text(ACTIVE), postgresql_where=sa.text(ACTIVE))
    op.create_index("ix_bac_status", "billing_account_closures", ["status", "requested_at"])


def downgrade() -> None:
    """FAIL CLOSED: refuses (deleting nothing) while any closure case exists. Operator procedure: verified backup; export the table; resolve each case; only then repeat."""
    count = op.get_bind().execute(sa.text("SELECT COUNT(*) FROM billing_account_closures")).scalar() or 0
    if count:
        raise RuntimeError(f"Refusing to downgrade 0031_account_closure: {count} account-closure case(s) exist and are the only record of closure obligations. "
                           "Take a verified backup, export billing_account_closures, resolve the cases, and only then repeat the downgrade.")
    op.drop_table("billing_account_closures")
