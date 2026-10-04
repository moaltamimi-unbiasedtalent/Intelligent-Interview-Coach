"""Reporting telemetry and AI usage facts (P10B-W10.12). SCHEMA ONLY: nothing is seeded or back-filled.

Additive. ``operational_metric_events`` holds bounded operational facts (request / provider-call / retrieval outcomes) with no identity, path, query, body or
exception text. ``ai_usage_facts`` holds one canonical AI usage unit per Agent run (cumulative, upserted) or Practice operation: unknown tokens and cost are NULL
(never 0), cost is integer micro-USD, and the rows are deleted with the account (FK CASCADE). With both tables empty every report shows "not captured", so
upgrading changes no behaviour. Chains from 0023. Single head.

Revision ID: 0024_reporting_analytics
Revises: 0023_platform_config
Create Date: 2026-10-05
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0024_reporting_analytics"
down_revision = "0023_platform_config"
branch_labels = None
depends_on = None

TYPES = ("request", "provider_call", "retrieval")
OUTCOMES = ("success", "client_error", "server_error", "unavailable", "hit", "abstained", "error")
WORKFLOWS = ("agent", "practice")
COST = ("reported", "calculated", "unavailable")
COV = ("complete", "partial", "unknown")


def _in(column, values):
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


def upgrade() -> None:
    op.create_table(
        "operational_metric_events",
        sa.Column("id", sa.Integer(), nullable=False), sa.Column("event_type", sa.String(length=16), nullable=False),
        sa.Column("subsystem", sa.String(length=24), nullable=False), sa.Column("operation", sa.String(length=40), nullable=False),
        sa.Column("outcome", sa.String(length=16), nullable=False), sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("error_category", sa.String(length=32), nullable=True), sa.Column("provider", sa.String(length=24), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(_in("event_type", TYPES), name="ck_ome_type"), sa.CheckConstraint(_in("outcome", OUTCOMES), name="ck_ome_outcome"),
        sa.CheckConstraint("duration_ms IS NULL OR duration_ms >= 0", name="ck_ome_duration"),
    )
    op.create_index("ix_ome_occurred", "operational_metric_events", ["occurred_at"])
    op.create_index("ix_ome_type_time", "operational_metric_events", ["event_type", "occurred_at"])
    op.create_index("ix_ome_subsystem_time", "operational_metric_events", ["subsystem", "occurred_at"])

    op.create_table(
        "ai_usage_facts",
        sa.Column("id", sa.Integer(), nullable=False), sa.Column("usage_key", sa.String(length=80), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True), sa.Column("workflow", sa.String(length=12), nullable=False),
        sa.Column("operation", sa.String(length=32), nullable=False), sa.Column("model_profile", sa.String(length=12), nullable=True),
        sa.Column("model_id", sa.String(length=80), nullable=True), sa.Column("model_calls", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("input_tokens", sa.Integer(), nullable=True), sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("total_tokens", sa.Integer(), nullable=True), sa.Column("cost_usd_micros", sa.BigInteger(), nullable=True),
        sa.Column("cost_source", sa.String(length=12), nullable=False, server_default="unavailable"),
        sa.Column("token_coverage", sa.String(length=8), nullable=False, server_default="unknown"),
        sa.Column("cost_coverage", sa.String(length=8), nullable=False, server_default="unknown"),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("usage_key", name="uq_aiuf_usage_key"),
        sa.CheckConstraint(_in("workflow", WORKFLOWS), name="ck_aiuf_workflow"), sa.CheckConstraint(_in("cost_source", COST), name="ck_aiuf_cost_source"),
        sa.CheckConstraint(_in("token_coverage", COV), name="ck_aiuf_token_cov"), sa.CheckConstraint(_in("cost_coverage", COV), name="ck_aiuf_cost_cov"),
        sa.CheckConstraint("model_calls >= 0", name="ck_aiuf_calls"),
        sa.CheckConstraint("(input_tokens IS NULL OR input_tokens >= 0) AND (output_tokens IS NULL OR output_tokens >= 0) AND (total_tokens IS NULL OR total_tokens >= 0)",
                           name="ck_aiuf_tokens"),
        sa.CheckConstraint("total_tokens IS NULL OR input_tokens IS NULL OR output_tokens IS NULL OR total_tokens = input_tokens + output_tokens", name="ck_aiuf_total"),
        sa.CheckConstraint("cost_usd_micros IS NULL OR cost_usd_micros >= 0", name="ck_aiuf_cost"),
        sa.CheckConstraint("cost_source <> 'unavailable' OR cost_usd_micros IS NULL", name="ck_aiuf_unavailable_is_null"),
    )
    op.create_index("ix_aiuf_occurred", "ai_usage_facts", ["occurred_at"])
    op.create_index("ix_aiuf_workflow_time", "ai_usage_facts", ["workflow", "occurred_at"])
    op.create_index("ix_aiuf_model", "ai_usage_facts", ["model_id"])
    op.create_index("ix_aiuf_user", "ai_usage_facts", ["user_id"])


def downgrade() -> None:
    op.drop_table("ai_usage_facts")
    op.drop_table("operational_metric_events")
