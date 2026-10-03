"""Integration manual-test state (P10B-W10.6).

Additive. One small table holding ONLY the safe result of an explicit manual connection test per integration
(timestamp, success/failure, a bounded category, latency, and who ran it). It stores no secret, no credential
identifier, no URL and no upstream response. All integration CONFIGURATION stays code- and environment-owned (the
registry is code-defined and credentials are externally managed), so nothing else needs persistence. Chains from
0016. Single head.

Revision ID: 0017_integrations
Revises: 0016_plans_entitlements
Create Date: 2026-10-03
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0017_integrations"
down_revision = "0016_plans_entitlements"
branch_labels = None
depends_on = None

OUTCOMES = ("success", "failure")
CATEGORIES = ("ok", "unauthorized", "timeout", "unavailable", "configuration_error", "rate_limited", "unknown")


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


def upgrade() -> None:
    op.create_table(
        "integration_states",
        sa.Column("integration_code", sa.String(length=40), nullable=False),
        sa.Column("last_test_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_test_outcome", sa.String(length=16), nullable=True),
        sa.Column("last_test_category", sa.String(length=24), nullable=True),
        sa.Column("last_test_latency_ms", sa.Integer(), nullable=True),
        sa.Column("last_test_by_user_id", sa.Integer(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("integration_code"),
        sa.ForeignKeyConstraint(["last_test_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.CheckConstraint(_in("last_test_outcome", OUTCOMES), name="ck_integration_states_outcome"),
        sa.CheckConstraint(_in("last_test_category", CATEGORIES), name="ck_integration_states_category"),
    )


def downgrade() -> None:
    op.drop_table("integration_states")
