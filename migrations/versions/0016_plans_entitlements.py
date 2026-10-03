"""Plans, subscriptions and entitlements (P10B-W10.4).

Additive. Introduces the plan/version/entitlement/subscription model that replaces the tier-to-capability map as
the product-access authority. NO billing: no price, provider, invoice or payment state. The legacy
``product_entitlements.tier`` column is kept (compatibility/display) and is not altered.

Seeds and backfills (deterministic, no access change):
- plan versions ``basic`` v1 and ``premium`` v1 (both ACTIVE) with entitlements equal to the pre-W10.4
  tier-to-capability map (basic: market research, standard history/progress/model profiles; premium: the same
  plus premium_preview);
- one ACTIVE ``migration`` subscription per existing user, from the user's current tier (premium -> premium v1;
  basic or no tier row -> basic v1). Workspaces get no row: a workspace subscription is optional until used.

One active subscription per user/workspace and one active/draft version per plan code are enforced with partial
unique indexes (PostgreSQL and SQLite); exactly one subject per subscription is a CHECK. Chains from 0015.

Revision ID: 0016_plans_entitlements
Revises: 0015_support_ticketing
Create Date: 2026-10-03
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0016_plans_entitlements"
down_revision = "0015_support_ticketing"
branch_labels = None
depends_on = None

KEYS = ("current_market_research", "standard_history", "standard_progress", "standard_model_profiles", "premium_preview")
BASIC = {"current_market_research", "standard_history", "standard_progress", "standard_model_profiles"}
PLANS = (("basic", "Basic", BASIC), ("premium", "Premium (preview)", BASIC | {"premium_preview"}))


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


def upgrade() -> None:
    op.create_table(
        "plan_versions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("plan_code", sa.String(length=32), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("display_name", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("plan_code", "version", name="uq_plan_versions_code_version"),
        sa.CheckConstraint(_in("status", ("draft", "active", "retired")), name="ck_plan_versions_status"),
    )
    op.create_index("uq_plan_versions_one_active", "plan_versions", ["plan_code"], unique=True,
                    sqlite_where=sa.text("status = 'active'"), postgresql_where=sa.text("status = 'active'"))
    op.create_index("uq_plan_versions_one_draft", "plan_versions", ["plan_code"], unique=True,
                    sqlite_where=sa.text("status = 'draft'"), postgresql_where=sa.text("status = 'draft'"))

    op.create_table(
        "plan_entitlements",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("plan_version_id", sa.Integer(), nullable=False),
        sa.Column("entitlement_key", sa.String(length=64), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("limit_value", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["plan_version_id"], ["plan_versions.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("plan_version_id", "entitlement_key", name="uq_plan_entitlements_key"),
        sa.CheckConstraint("limit_value IS NULL OR (limit_value >= 1 AND enabled = 1)", name="ck_plan_entitlements_limit"),
    )

    op.create_table(
        "subscriptions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("workspace_id", sa.Integer(), nullable=True),
        sa.Column("plan_version_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("source", sa.String(length=24), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["plan_version_id"], ["plan_versions.id"], ondelete="RESTRICT"),
        sa.CheckConstraint(
            "(user_id IS NOT NULL AND workspace_id IS NULL) OR (user_id IS NULL AND workspace_id IS NOT NULL)",
            name="ck_subscriptions_one_subject"),
        sa.CheckConstraint(_in("status", ("active", "ended")), name="ck_subscriptions_status"),
        sa.CheckConstraint(_in("source", ("system_default", "migration", "admin")), name="ck_subscriptions_source"),
    )
    op.create_index("ix_subscriptions_user_id", "subscriptions", ["user_id"])
    op.create_index("ix_subscriptions_workspace_id", "subscriptions", ["workspace_id"])
    op.create_index("ix_subscriptions_plan_version", "subscriptions", ["plan_version_id", "status"])
    op.create_index("uq_subscriptions_one_active_user", "subscriptions", ["user_id"], unique=True,
                    sqlite_where=sa.text("status = 'active' AND user_id IS NOT NULL"),
                    postgresql_where=sa.text("status = 'active' AND user_id IS NOT NULL"))
    op.create_index("uq_subscriptions_one_active_workspace", "subscriptions", ["workspace_id"], unique=True,
                    sqlite_where=sa.text("status = 'active' AND workspace_id IS NOT NULL"),
                    postgresql_where=sa.text("status = 'active' AND workspace_id IS NOT NULL"))

    # --- seed the two real plan versions (identical to src.entitlements.DEFAULT_PLANS) -------------------
    bind = op.get_bind()
    ids: dict[str, int] = {}
    for code, name, enabled in PLANS:
        bind.execute(sa.text(
            "INSERT INTO plan_versions (plan_code, version, display_name, status, created_at, activated_at) "
            "VALUES (:c, 1, :n, 'active', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"), {"c": code, "n": name})
        ids[code] = bind.execute(sa.text("SELECT id FROM plan_versions WHERE plan_code = :c AND version = 1"),
                                 {"c": code}).scalar_one()
        for key in KEYS:
            bind.execute(sa.text(
                "INSERT INTO plan_entitlements (plan_version_id, entitlement_key, enabled, limit_value) "
                "VALUES (:p, :k, :e, NULL)"), {"p": ids[code], "k": key, "e": key in enabled})

    # --- backfill: every existing user keeps exactly the access their tier gave them ----------------------
    bind.execute(sa.text(
        "INSERT INTO subscriptions (user_id, workspace_id, plan_version_id, status, source, started_at) "
        "SELECT u.id, NULL, CASE WHEN pe.tier = 'premium' THEN :premium ELSE :basic END, 'active', 'migration', CURRENT_TIMESTAMP "
        "FROM users u LEFT JOIN product_entitlements pe ON pe.user_id = u.id"),
        {"premium": ids["premium"], "basic": ids["basic"]})


def downgrade() -> None:
    op.drop_index("uq_subscriptions_one_active_workspace", table_name="subscriptions")
    op.drop_index("uq_subscriptions_one_active_user", table_name="subscriptions")
    op.drop_index("ix_subscriptions_plan_version", table_name="subscriptions")
    op.drop_index("ix_subscriptions_workspace_id", table_name="subscriptions")
    op.drop_index("ix_subscriptions_user_id", table_name="subscriptions")
    op.drop_table("subscriptions")
    op.drop_table("plan_entitlements")
    op.drop_index("uq_plan_versions_one_draft", table_name="plan_versions")
    op.drop_index("uq_plan_versions_one_active", table_name="plan_versions")
    op.drop_table("plan_versions")
