"""Checkout foundation (W12.4D-C): provider price mappings and candidate checkout attempts. SCHEMA ONLY: nothing is seeded.

Additive. ``billing_provider_prices`` maps ONE immutable commercial-terms row to a provider product and price id per provider environment
(snapshotting amount, currency and interval); ``billing_checkout_sessions`` records a candidate's checkout ATTEMPT with durable idempotency
(unique user + key, at most one open attempt per user and plan version) and NO paid or completed state: those arrive only with authenticated
webhook evidence in a later wave. No card or payment data, credential or webhook secret is stored. With both tables empty no plan is
purchasable, so upgrading changes no behaviour. Chains from 0027. Single head.

Revision ID: 0028_checkout_sessions
Revises: 0027_email_attempts
Create Date: 2026-10-15
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0028_checkout_sessions"
down_revision = "0027_email_attempts"
branch_labels = None
depends_on = None

ENVS = ("sandbox", "live")
STATUSES = ("pending_creation", "open", "canceled", "expired", "failed")
INTERVALS = ("month", "year")


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


def upgrade() -> None:
    op.create_table(
        "billing_provider_prices",
        sa.Column("id", sa.Integer(), nullable=False), sa.Column("public_id", sa.String(length=32), nullable=False),
        sa.Column("commercial_terms_id", sa.Integer(), nullable=False), sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("environment", sa.String(length=8), nullable=False), sa.Column("provider_product_id", sa.String(length=80), nullable=False),
        sa.Column("provider_price_id", sa.String(length=80), nullable=False), sa.Column("amount_minor", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False), sa.Column("billing_interval", sa.String(length=8), nullable=False),
        sa.Column("status", sa.String(length=10), server_default="active", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["commercial_terms_id"], ["billing_commercial_terms.id"], ondelete="RESTRICT"),
        sa.CheckConstraint(_in("provider", ("stripe_managed_payments",)), name="ck_bpp_provider"),
        sa.CheckConstraint(_in("environment", ENVS), name="ck_bpp_environment"),
        sa.CheckConstraint(_in("status", ("active", "retired")), name="ck_bpp_status"),
        sa.CheckConstraint("length(currency) = 3 AND currency = upper(currency)", name="ck_bpp_currency"),
        sa.CheckConstraint(_in("billing_interval", INTERVALS), name="ck_bpp_interval"),
        sa.CheckConstraint("amount_minor >= 0 AND amount_minor <= 100000000", name="ck_bpp_amount"),
        sa.UniqueConstraint("provider", "environment", "provider_price_id", name="uq_bpp_provider_price"),
    )
    op.create_index("ix_billing_provider_prices_public_id", "billing_provider_prices", ["public_id"], unique=True)
    op.create_index("uq_bpp_one_active", "billing_provider_prices", ["commercial_terms_id", "provider", "environment"], unique=True,
                    sqlite_where=sa.text("status = 'active'"), postgresql_where=sa.text("status = 'active'"))

    op.create_table(
        "billing_checkout_sessions",
        sa.Column("id", sa.Integer(), nullable=False), sa.Column("public_id", sa.String(length=32), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False), sa.Column("plan_version_id", sa.Integer(), nullable=False),
        sa.Column("commercial_terms_id", sa.Integer(), nullable=False), sa.Column("price_mapping_id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False), sa.Column("environment", sa.String(length=8), nullable=False),
        sa.Column("provider_session_id", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=16), server_default="pending_creation", nullable=False),
        sa.Column("idempotency_key", sa.String(length=80), nullable=False), sa.Column("checkout_url", sa.String(length=1024), nullable=True),
        sa.Column("provider_attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("failure_category", sa.String(length=24), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True), sa.Column("browser_returned_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["plan_version_id"], ["plan_versions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["commercial_terms_id"], ["billing_commercial_terms.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["price_mapping_id"], ["billing_provider_prices.id"], ondelete="RESTRICT"),
        sa.CheckConstraint(_in("status", STATUSES), name="ck_bcs_status"),
        sa.CheckConstraint(_in("provider", ("stripe_managed_payments",)), name="ck_bcs_provider"),
        sa.CheckConstraint(_in("environment", ENVS), name="ck_bcs_environment"),
        sa.UniqueConstraint("user_id", "idempotency_key", name="uq_bcs_user_idempotency"),
        sa.UniqueConstraint("provider", "provider_session_id", name="uq_bcs_provider_session"),
    )
    op.create_index("ix_billing_checkout_sessions_public_id", "billing_checkout_sessions", ["public_id"], unique=True)
    op.create_index("uq_bcs_one_open_per_user_plan", "billing_checkout_sessions", ["user_id", "plan_version_id"], unique=True,
                    sqlite_where=sa.text("status IN ('pending_creation', 'open')"), postgresql_where=sa.text("status IN ('pending_creation', 'open')"))
    op.create_index("ix_bcs_user_created", "billing_checkout_sessions", ["user_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_bcs_user_created", table_name="billing_checkout_sessions")
    op.drop_index("uq_bcs_one_open_per_user_plan", table_name="billing_checkout_sessions")
    op.drop_index("ix_billing_checkout_sessions_public_id", table_name="billing_checkout_sessions")
    op.drop_table("billing_checkout_sessions")
    op.drop_index("uq_bpp_one_active", table_name="billing_provider_prices")
    op.drop_index("ix_billing_provider_prices_public_id", table_name="billing_provider_prices")
    op.drop_table("billing_provider_prices")
