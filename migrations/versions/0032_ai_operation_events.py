"""AI operation ledger (W12.4D-P2-A). SCHEMA ONLY: nothing is seeded or back-filled.

Additive. ``ai_operation_events`` records ONE LOGICAL candidate AI operation (Practice or Career) with the provider attempts it needed, bounded status,
KNOWN token and cost figures (NULL when unknown, never 0), latency and whether the per-user limit was exceeded in OBSERVE mode. It stores no prompt, answer,
document, transcript, model response or credential. ``user_id`` cascades on account deletion. With the table empty nothing changes for any candidate.
Downgrade drops the table (it holds operational metering only, no financial or candidate content). Chains from 0031. Single head.

Revision ID: 0032_ai_operation_events
Revises: 0031_account_closure
Create Date: 2026-10-16
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0032_ai_operation_events"
down_revision = "0031_account_closure"
branch_labels = None
depends_on = None


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


def upgrade() -> None:
    op.create_table(
        "ai_operation_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("op_key", sa.String(length=120), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("workflow", sa.String(length=12), nullable=False),
        sa.Column("operation", sa.String(length=32), nullable=False),
        sa.Column("provider", sa.String(length=16), server_default="openrouter", nullable=False),
        sa.Column("model_profile", sa.String(length=12), nullable=True),
        sa.Column("model_id", sa.String(length=80), nullable=True),
        sa.Column("status", sa.String(length=12), nullable=False),
        sa.Column("failure_category", sa.String(length=32), nullable=True),
        sa.Column("provider_attempts", sa.Integer(), nullable=True),
        sa.Column("attempt_coverage", sa.String(length=10), server_default="none", nullable=False),
        sa.Column("calls_ok", sa.Integer(), server_default="0", nullable=False),
        sa.Column("calls_failed", sa.Integer(), server_default="0", nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("total_tokens", sa.Integer(), nullable=True),
        sa.Column("token_coverage", sa.String(length=8), server_default="unknown", nullable=False),
        sa.Column("cost_usd_micros", sa.BigInteger(), nullable=True),
        sa.Column("cost_source", sa.String(length=12), server_default="unavailable", nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("limit_observed", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("op_key", name="uq_aiop_key"),
        sa.CheckConstraint(_in("workflow", ("practice", "career")), name="ck_aiop_workflow"),
        sa.CheckConstraint(_in("status", ("succeeded", "failed")), name="ck_aiop_status"),
        sa.CheckConstraint(_in("attempt_coverage", ("exact", "calls_only", "none")), name="ck_aiop_attempt_cov"),
        sa.CheckConstraint(_in("token_coverage", ("known", "partial", "unknown")), name="ck_aiop_token_cov"),
        sa.CheckConstraint(_in("cost_source", ("reported", "calculated", "unavailable")), name="ck_aiop_cost_source"),
        sa.CheckConstraint("provider_attempts IS NULL OR provider_attempts >= 0", name="ck_aiop_attempts"),
        sa.CheckConstraint("calls_ok >= 0 AND calls_failed >= 0", name="ck_aiop_calls"),
        sa.CheckConstraint("(input_tokens IS NULL OR input_tokens >= 0) AND (output_tokens IS NULL OR output_tokens >= 0) "
                           "AND (total_tokens IS NULL OR total_tokens >= 0)", name="ck_aiop_tokens"),
        sa.CheckConstraint("cost_usd_micros IS NULL OR cost_usd_micros >= 0", name="ck_aiop_cost"),
        sa.CheckConstraint("cost_source <> 'unavailable' OR cost_usd_micros IS NULL", name="ck_aiop_unavailable_is_null"),
        sa.CheckConstraint("latency_ms IS NULL OR latency_ms >= 0", name="ck_aiop_latency"),
    )
    op.create_index("ix_aiop_user_time", "ai_operation_events", ["user_id", "started_at"])
    op.create_index("ix_aiop_workflow_time", "ai_operation_events", ["workflow", "started_at"])


def downgrade() -> None:
    op.drop_index("ix_aiop_workflow_time", table_name="ai_operation_events")
    op.drop_index("ix_aiop_user_time", table_name="ai_operation_events")
    op.drop_table("ai_operation_events")
