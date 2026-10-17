"""Verified provider events, provider-managed subscription links and entitlement decision evidence (W12.4D-D).

Additive, plus ONE widened constraint (the downgrade is FAIL-CLOSED and deletes nothing: it refuses while any provider-managed record exists): ``subscriptions.source`` may now also be ``provider`` (written only by the billing entitlement bridge); the
meaning of ``system_default``, ``migration`` and ``admin`` is unchanged. ``billing_provider_events`` is the durable outbox of authenticated webhook
events (unique per provider, environment and event id; allow-listed normalised fields only, no raw body or signature), ``billing_provider_links``
binds ONE provider subscription to ONE candidate through a trusted checkout record, and ``billing_entitlement_decisions`` is the append-only evidence
of each evaluation. With the tables empty and no approved paid-entitlement policy, upgrading changes no behaviour. Chains from 0028. Single head.

Revision ID: 0029_provider_webhooks
Revises: 0028_checkout_sessions
Create Date: 2026-10-15
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0029_provider_webhooks"
down_revision = "0028_checkout_sessions"
branch_labels = None
depends_on = None

ENVS = ("sandbox", "live")
EVENT_STATUSES = ("received", "processing", "processed", "ignored", "failed", "quarantined", "needs_review")
LINK_STATES = ("incomplete", "incomplete_expired", "trialing", "active", "past_due", "unpaid", "paused", "canceled")
INVOICE = ("none", "open", "paid", "failed", "action_required")
REFUND = ("none", "partial", "full")
DISPUTE = ("none", "open", "won", "lost")
DECISIONS = ("grant", "revoke", "keep", "none", "hold", "policy_unapproved", "skipped_manual_assignment", "refused")
OLD_SOURCES = ("system_default", "migration", "admin")
NEW_SOURCES = OLD_SOURCES + ("provider",)
LIVE_LINK = "provider_state NOT IN ('canceled', 'incomplete_expired')"


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


def _swap_source_check(values: tuple[str, ...]) -> None:
    with op.batch_alter_table("subscriptions") as batch:
        batch.drop_constraint("ck_subscriptions_source", type_="check")
        batch.create_check_constraint("ck_subscriptions_source", _in("source", values))


def upgrade() -> None:
    _swap_source_check(NEW_SOURCES)

    op.create_table(
        "billing_provider_links",
        sa.Column("id", sa.Integer(), nullable=False), sa.Column("public_id", sa.String(length=32), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False), sa.Column("environment", sa.String(length=8), nullable=False),
        sa.Column("provider_subscription_id", sa.String(length=80), nullable=False), sa.Column("provider_customer_id", sa.String(length=80), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False), sa.Column("checkout_session_id", sa.Integer(), nullable=True),
        sa.Column("plan_version_id", sa.Integer(), nullable=False), sa.Column("commercial_terms_id", sa.Integer(), nullable=False),
        sa.Column("price_mapping_id", sa.Integer(), nullable=False),
        sa.Column("provider_state", sa.String(length=20), nullable=False),
        sa.Column("cancel_at_period_end", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("latest_invoice_state", sa.String(length=16), server_default="none", nullable=False),
        sa.Column("refund_state", sa.String(length=8), server_default="none", nullable=False),
        sa.Column("dispute_state", sa.String(length=8), server_default="none", nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reconcile_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("review_category", sa.String(length=40), nullable=True),
        sa.Column("entitlement_decision", sa.String(length=28), server_default="none", nullable=False),
        sa.Column("entitlement_subscription_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["checkout_session_id"], ["billing_checkout_sessions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["plan_version_id"], ["plan_versions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["commercial_terms_id"], ["billing_commercial_terms.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["price_mapping_id"], ["billing_provider_prices.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["entitlement_subscription_id"], ["subscriptions.id"], ondelete="SET NULL"),
        sa.CheckConstraint(_in("provider", ("stripe_managed_payments",)), name="ck_bpl_provider"),
        sa.CheckConstraint(_in("environment", ENVS), name="ck_bpl_environment"),
        sa.CheckConstraint(_in("provider_state", LINK_STATES), name="ck_bpl_state"),
        sa.CheckConstraint(_in("latest_invoice_state", INVOICE), name="ck_bpl_invoice"),
        sa.CheckConstraint(_in("refund_state", REFUND), name="ck_bpl_refund"),
        sa.CheckConstraint(_in("dispute_state", DISPUTE), name="ck_bpl_dispute"),
        sa.CheckConstraint(_in("entitlement_decision", DECISIONS), name="ck_bpl_decision"),
        sa.UniqueConstraint("provider", "environment", "provider_subscription_id", name="uq_bpl_subscription"),
    )
    op.create_index("ix_billing_provider_links_public_id", "billing_provider_links", ["public_id"], unique=True)
    op.create_index("uq_bpl_one_live_per_user", "billing_provider_links", ["user_id", "environment"], unique=True,
                    sqlite_where=sa.text(LIVE_LINK), postgresql_where=sa.text(LIVE_LINK))
    op.create_index("ix_bpl_customer", "billing_provider_links", ["provider", "environment", "provider_customer_id"])
    op.create_index("ix_billing_provider_links_user_id", "billing_provider_links", ["user_id"])

    op.create_table(
        "billing_provider_events",
        sa.Column("id", sa.Integer(), nullable=False), sa.Column("public_id", sa.String(length=32), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False), sa.Column("environment", sa.String(length=8), nullable=False),
        sa.Column("provider_event_id", sa.String(length=80), nullable=False), sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("api_version", sa.String(length=32), nullable=True), sa.Column("provider_object_id", sa.String(length=80), nullable=True),
        sa.Column("provider_created_at", sa.DateTime(timezone=True), nullable=True), sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="received", nullable=False),
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("failure_category", sa.String(length=40), nullable=True),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True), sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lease_until", sa.DateTime(timezone=True), nullable=True), sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("link_id", sa.Integer(), nullable=True), sa.Column("normalized_json", sa.JSON(), nullable=False),
        sa.Column("reconciliation_json", sa.JSON(), nullable=True), sa.Column("correlation_id", sa.String(length=40), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["link_id"], ["billing_provider_links.id"], ondelete="SET NULL"),
        sa.CheckConstraint(_in("provider", ("stripe_managed_payments",)), name="ck_bpe_provider"),
        sa.CheckConstraint(_in("environment", ENVS), name="ck_bpe_environment"),
        sa.CheckConstraint(_in("status", EVENT_STATUSES), name="ck_bpe_status"),
        sa.UniqueConstraint("provider", "environment", "provider_event_id", name="uq_bpe_event"),
    )
    op.create_index("ix_billing_provider_events_public_id", "billing_provider_events", ["public_id"], unique=True)
    op.create_index("ix_bpe_status_received", "billing_provider_events", ["status", "received_at"])

    op.create_table(
        "billing_entitlement_decisions",
        sa.Column("id", sa.Integer(), nullable=False), sa.Column("link_id", sa.Integer(), nullable=False), sa.Column("event_id", sa.Integer(), nullable=True),
        sa.Column("decision", sa.String(length=28), nullable=False), sa.Column("reason", sa.String(length=60), nullable=False),
        sa.Column("policy_id", sa.String(length=60), nullable=False), sa.Column("provider_state", sa.String(length=20), nullable=False),
        sa.Column("applied", sa.Boolean(), server_default=sa.false(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["link_id"], ["billing_provider_links.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["event_id"], ["billing_provider_events.id"], ondelete="SET NULL"),
        sa.CheckConstraint(_in("decision", DECISIONS), name="ck_bed_decision"),
    )
    op.create_index("ix_bed_link_created", "billing_entitlement_decisions", ["link_id", "created_at"])


PROVIDER_TABLES = ("billing_entitlement_decisions", "billing_provider_events", "billing_provider_links")


def downgrade() -> None:
    """FAIL CLOSED. This downgrade drops the only record of verified provider events, subscription links and entitlement decisions and the
    ``provider`` subscription rows that carry paid access; none of that is stored anywhere else. It therefore refuses to run if ANY such row exists and
    deletes nothing. It runs only on an empty provider surface (for example a database where W12.4D-D was never operationally used)."""
    bind = op.get_bind()
    found = {name: bind.execute(sa.text(f"SELECT COUNT(*) FROM {name}")).scalar() or 0 for name in PROVIDER_TABLES}
    found["subscriptions with source = 'provider'"] = bind.execute(sa.text("SELECT COUNT(*) FROM subscriptions WHERE source = 'provider'")).scalar() or 0
    if any(found.values()):
        listing = ", ".join(f"{k}: {v}" for k, v in found.items() if v)
        raise RuntimeError(
            "Refusing to downgrade 0029_provider_webhooks: provider-managed billing records exist (" + listing + "). Downgrading would destroy financial and "
            "entitlement history that is stored nowhere else. Operator procedure: take a verified database backup; export the rows of the four tables above; "
            "decide with the owner how each provider-managed subscription is to be handled (end it through the entitlement bridge or reassign it deliberately); "
            "only then, on an empty provider surface, repeat the downgrade. See docs/capstone/billing/W12_04D_D_WEBHOOK_RECONCILIATION_ENTITLEMENTS.md.")
    for name in PROVIDER_TABLES:
        op.drop_table(name)
    _swap_source_check(OLD_SOURCES)
