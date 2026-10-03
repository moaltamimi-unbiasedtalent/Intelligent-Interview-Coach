"""Mock billing metadata (P10B-W10.5). SCHEMA ONLY: no price, customer, invoice, payment or refund is seeded.

Additive. Versioned commercial terms attached to the W10.4 plan versions (entitlements are NOT duplicated), a bounded second-approver
request table, and MIRRORS of provider data (customers, provider subscriptions, invoices, payments, refunds, normalised events).
Money is integer minor units plus a currency code. There is no card, payment-instrument, bank, tax or raw provider column anywhere.
MOCK BILLING: NOT LIVE. Billing state is never an authority for product access. Chains from 0020. Single head.

Revision ID: 0021_billing_admin
Revises: 0020_privacy_legal_admin
Create Date: 2026-10-03
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0021_billing_admin"
down_revision = "0020_privacy_legal_admin"
branch_labels = None
depends_on = None

INTERVALS = ("month", "year")
VISIBILITIES = ("public", "private", "internal")
TERMS = ("active", "retired")
ACTIONS = ("price_change", "refund")
STATUSES = ("pending", "approved", "rejected", "executed", "failed", "cancelled")
SUB_STATES = ("trialing", "active", "past_due", "cancelled")
INVOICE = ("open", "paid", "past_due", "void")
PAYMENT = ("pending", "succeeded", "failed")
FAILURES = ("declined", "insufficient_funds", "expired", "processing_error", "unknown")
REFUND = ("pending", "succeeded", "failed")
EVENTS = ("customer_created", "subscription_updated", "invoice_opened", "invoice_paid", "payment_succeeded", "payment_failed")
EVENT_STATES = ("received", "processed", "failed")
CUR = "length(currency) = 3 AND currency = upper(currency)"


def _in(column, values):
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


def _dt(name, nullable=True):
    return sa.Column(name, sa.DateTime(timezone=True), nullable=nullable)


def _pk():
    return [sa.Column("id", sa.Integer(), nullable=False), sa.Column("public_id", sa.String(length=32), nullable=False)]


def _pub(table):
    op.create_index(f"ix_{table}_public_id", table, ["public_id"], unique=True)


def upgrade() -> None:
    op.create_table(
        "billing_commercial_terms", *_pk(),
        sa.Column("plan_version_id", sa.Integer(), nullable=False), sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("amount_minor", sa.Integer(), nullable=False), sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("billing_interval", sa.String(length=8), nullable=False), sa.Column("trial_days", sa.Integer(), nullable=True),
        sa.Column("visibility", sa.String(length=10), nullable=False),
        sa.Column("state", sa.String(length=10), server_default="active", nullable=False),
        sa.Column("approval_public_id", sa.String(length=32), nullable=True),
        _dt("created_at", False), _dt("activated_at"), _dt("retired_at"),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["plan_version_id"], ["plan_versions.id"], ondelete="RESTRICT"),
        sa.CheckConstraint("amount_minor >= 0 AND amount_minor <= 100000000", name="ck_bct_amount"),
        sa.CheckConstraint(CUR, name="ck_bct_currency"),
        sa.CheckConstraint(_in("billing_interval", INTERVALS), name="ck_bct_interval"),
        sa.CheckConstraint(_in("visibility", VISIBILITIES), name="ck_bct_visibility"),
        sa.CheckConstraint(_in("state", TERMS), name="ck_bct_state"),
        sa.CheckConstraint("trial_days IS NULL OR (trial_days >= 1 AND trial_days <= 365)", name="ck_bct_trial"),
        sa.UniqueConstraint("plan_version_id", "version", name="uq_bct_plan_version_version"),
    )
    _pub("billing_commercial_terms")
    op.create_index("uq_bct_one_active", "billing_commercial_terms", ["plan_version_id"], unique=True,
                    sqlite_where=sa.text("state = 'active'"), postgresql_where=sa.text("state = 'active'"))

    op.create_table(
        "billing_approval_requests", *_pk(),
        sa.Column("action_type", sa.String(length=16), nullable=False), sa.Column("target_ref", sa.String(length=64), nullable=False),
        sa.Column("proposed_json", sa.JSON(), nullable=False), sa.Column("reason", sa.String(length=300), nullable=False),
        sa.Column("status", sa.String(length=12), server_default="pending", nullable=False),
        sa.Column("requested_by_user_id", sa.Integer(), nullable=True), _dt("requested_at", False),
        sa.Column("decided_by_user_id", sa.Integer(), nullable=True), _dt("decided_at"), _dt("executed_at"),
        sa.Column("execution_ref", sa.String(length=32), nullable=True), sa.Column("failure_category", sa.String(length=24), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["decided_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.CheckConstraint(_in("action_type", ACTIONS), name="ck_bar_action"),
        sa.CheckConstraint(_in("status", STATUSES), name="ck_bar_status"),
        sa.CheckConstraint("decided_by_user_id IS NULL OR requested_by_user_id IS NULL OR decided_by_user_id <> requested_by_user_id",
                           name="ck_bar_no_self_approval"),
    )
    _pub("billing_approval_requests")
    op.create_index("uq_bar_one_pending_per_target", "billing_approval_requests", ["action_type", "target_ref"], unique=True,
                    sqlite_where=sa.text("status = 'pending'"), postgresql_where=sa.text("status = 'pending'"))
    op.create_index("ix_bar_status_created", "billing_approval_requests", ["status", "requested_at"])

    op.create_table(
        "billing_customers", *_pk(),
        sa.Column("provider", sa.String(length=16), nullable=False), sa.Column("provider_customer_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True), sa.Column("workspace_id", sa.Integer(), nullable=True),
        sa.Column("state", sa.String(length=10), server_default="active", nullable=False), _dt("created_at", False), _dt("updated_at", False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.CheckConstraint("(user_id IS NOT NULL AND workspace_id IS NULL) OR (user_id IS NULL AND workspace_id IS NOT NULL)", name="ck_bc_one_subject"),
        sa.CheckConstraint(_in("provider", ("mock",)), name="ck_bc_provider"),
        sa.CheckConstraint(_in("state", ("active", "closed")), name="ck_bc_state"),
        sa.UniqueConstraint("provider", "provider_customer_id", name="uq_bc_provider_customer"),
    )
    _pub("billing_customers")
    op.create_index("uq_bc_user", "billing_customers", ["provider", "user_id"], unique=True,
                    sqlite_where=sa.text("user_id IS NOT NULL"), postgresql_where=sa.text("user_id IS NOT NULL"))
    op.create_index("uq_bc_workspace", "billing_customers", ["provider", "workspace_id"], unique=True,
                    sqlite_where=sa.text("workspace_id IS NOT NULL"), postgresql_where=sa.text("workspace_id IS NOT NULL"))

    op.create_table(
        "billing_provider_subscriptions", *_pk(),
        sa.Column("provider", sa.String(length=16), nullable=False), sa.Column("provider_subscription_id", sa.String(length=64), nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=False), sa.Column("plan_version_id", sa.Integer(), nullable=False),
        sa.Column("commercial_terms_id", sa.Integer(), nullable=True), sa.Column("provider_state", sa.String(length=12), nullable=False),
        _dt("current_period_start"), _dt("current_period_end"), _dt("grace_until"), _dt("created_at", False), _dt("updated_at", False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["customer_id"], ["billing_customers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["plan_version_id"], ["plan_versions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["commercial_terms_id"], ["billing_commercial_terms.id"], ondelete="SET NULL"),
        sa.CheckConstraint(_in("provider_state", SUB_STATES), name="ck_bps_state"),
        sa.UniqueConstraint("provider", "provider_subscription_id", name="uq_bps_provider_sub"),
    )
    _pub("billing_provider_subscriptions")
    op.create_index("ix_bps_customer", "billing_provider_subscriptions", ["customer_id"])

    op.create_table(
        "billing_invoices", *_pk(),
        sa.Column("provider", sa.String(length=16), nullable=False), sa.Column("provider_invoice_id", sa.String(length=64), nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=False), sa.Column("provider_subscription_id", sa.Integer(), nullable=True),
        sa.Column("amount_due_minor", sa.Integer(), nullable=False), sa.Column("amount_paid_minor", sa.Integer(), server_default="0", nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False), sa.Column("state", sa.String(length=10), server_default="open", nullable=False),
        _dt("period_start"), _dt("period_end"), _dt("due_at"), _dt("created_at", False), _dt("updated_at", False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["customer_id"], ["billing_customers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["provider_subscription_id"], ["billing_provider_subscriptions.id"], ondelete="SET NULL"),
        sa.CheckConstraint("amount_due_minor >= 0 AND amount_paid_minor >= 0 AND amount_paid_minor <= amount_due_minor", name="ck_bi_amounts"),
        sa.CheckConstraint(CUR, name="ck_bi_currency"),
        sa.CheckConstraint(_in("state", INVOICE), name="ck_bi_state"),
        sa.UniqueConstraint("provider", "provider_invoice_id", name="uq_bi_provider_invoice"),
    )
    _pub("billing_invoices")
    op.create_index("ix_bi_state_created", "billing_invoices", ["state", "created_at"])
    op.create_index("ix_bi_customer", "billing_invoices", ["customer_id"])

    op.create_table(
        "billing_payments", *_pk(),
        sa.Column("provider", sa.String(length=16), nullable=False), sa.Column("provider_payment_id", sa.String(length=64), nullable=False),
        sa.Column("invoice_id", sa.Integer(), nullable=False), sa.Column("amount_minor", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False), sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("failure_category", sa.String(length=20), nullable=True), _dt("created_at", False), _dt("updated_at", False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["invoice_id"], ["billing_invoices.id"], ondelete="CASCADE"),
        sa.CheckConstraint("amount_minor >= 0", name="ck_bp_amount"),
        sa.CheckConstraint(CUR, name="ck_bp_currency"),
        sa.CheckConstraint(_in("status", PAYMENT), name="ck_bp_status"),
        sa.CheckConstraint("failure_category IS NULL OR " + _in("failure_category", FAILURES), name="ck_bp_failure"),
        sa.UniqueConstraint("provider", "provider_payment_id", name="uq_bp_provider_payment"),
    )
    _pub("billing_payments")
    op.create_index("ix_bp_status_created", "billing_payments", ["status", "created_at"])
    op.create_index("ix_bp_invoice", "billing_payments", ["invoice_id"])

    op.create_table(
        "billing_refunds", *_pk(),
        sa.Column("provider", sa.String(length=16), nullable=False), sa.Column("provider_refund_id", sa.String(length=64), nullable=True),
        sa.Column("payment_id", sa.Integer(), nullable=False), sa.Column("amount_minor", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False), sa.Column("state", sa.String(length=10), server_default="pending", nullable=False),
        sa.Column("approval_request_id", sa.Integer(), nullable=True), sa.Column("idempotency_key", sa.String(length=80), nullable=False),
        _dt("created_at", False), _dt("executed_at"),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["payment_id"], ["billing_payments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["approval_request_id"], ["billing_approval_requests.id"], ondelete="SET NULL"),
        sa.CheckConstraint("amount_minor > 0", name="ck_br_amount"),
        sa.CheckConstraint(CUR, name="ck_br_currency"),
        sa.CheckConstraint(_in("state", REFUND), name="ck_br_state"),
        sa.UniqueConstraint("idempotency_key", name="uq_br_idempotency"),
        sa.UniqueConstraint("provider", "provider_refund_id", name="uq_br_provider_refund"),
    )
    _pub("billing_refunds")
    op.create_index("ix_br_payment", "billing_refunds", ["payment_id"])

    op.create_table(
        "billing_events", *_pk(),
        sa.Column("provider", sa.String(length=16), nullable=False), sa.Column("provider_event_id", sa.String(length=64), nullable=False),
        sa.Column("event_type", sa.String(length=24), nullable=False), sa.Column("normalized_json", sa.JSON(), nullable=False),
        sa.Column("state", sa.String(length=10), server_default="received", nullable=False), _dt("received_at", False), _dt("processed_at"),
        sa.Column("failure_category", sa.String(length=24), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(_in("event_type", EVENTS), name="ck_be_type"),
        sa.CheckConstraint(_in("state", EVENT_STATES), name="ck_be_state"),
        sa.UniqueConstraint("provider", "provider_event_id", name="uq_be_provider_event"),
    )
    _pub("billing_events")
    op.create_index("ix_be_state_received", "billing_events", ["state", "received_at"])


def downgrade() -> None:
    for t in ("billing_events", "billing_refunds", "billing_payments", "billing_invoices", "billing_provider_subscriptions",
              "billing_customers", "billing_approval_requests", "billing_commercial_terms"):
        op.drop_table(t)
