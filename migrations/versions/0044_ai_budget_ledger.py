"""Production AI budget governor ledger (package 05C). Additive: two new tables, nothing seeded, no existing table touched.

``ai_budget_controls`` holds the atomic counters (one row per scope: ``global`` kill switch, ``class:<class>``, ``cat:<class>:<category>``) that make admission multi-process safe.
``ai_budget_entries`` holds one row per provider call (budget class, category, model id, a content-free SHA-256 request fingerprint, integer micro-USD, tokens, latency). Neither table
holds a prompt, a response, a key, a user identifier or provider text. Unknown tokens and costs are NULL.

Why a migration is needed: the demonstration ledger is a private SQLite file for one harness; a production governor must be DURABLE in the application database and SAFE across the API,
the worker and evaluation processes, and that cannot be done without a table.

The downgrade is FAIL-CLOSED: it refuses while any entry or counter row exists, because those rows are the only record of what was spent.

Revision ID: 0044_ai_budget_ledger
Revises: 0043_story_bank_completion
Create Date: 2026-10-22
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0044_ai_budget_ledger"
down_revision = "0043_story_bank_completion"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_budget_controls",
        sa.Column("scope_key", sa.String(length=96), nullable=False),
        sa.Column("held_micro_usd", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("requests", sa.Integer(), server_default="0", nullable=False),
        sa.Column("killed", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("kill_reason", sa.String(length=64), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("scope_key"),
        sa.CheckConstraint("held_micro_usd >= 0", name="ck_aibc_held"),
        sa.CheckConstraint("requests >= 0", name="ck_aibc_requests"),
    )
    op.create_table(
        "ai_budget_entries",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_ts", sa.Float(), nullable=False),
        sa.Column("settled_ts", sa.Float(), nullable=True),
        sa.Column("budget_class", sa.String(length=24), nullable=False),
        sa.Column("category", sa.String(length=24), nullable=False),
        sa.Column("operation", sa.String(length=48), nullable=False),
        sa.Column("model", sa.String(length=160), nullable=False),
        sa.Column("endpoint", sa.String(length=24), nullable=False),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("state", sa.String(length=12), nullable=False),
        sa.Column("reserved_micro_usd", sa.BigInteger(), nullable=False),
        sa.Column("committed_micro_usd", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("est_cost_micro_usd", sa.BigInteger(), nullable=True),
        sa.Column("provider_cost_micro_usd", sa.BigInteger(), nullable=True),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("error_category", sa.String(length=32), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("state IN ('reserved','settled','rejected','unknown')", name="ck_aibe_state"),
        sa.CheckConstraint("reserved_micro_usd >= 0", name="ck_aibe_reserved"),
    )
    op.create_index("ix_aibe_class_state", "ai_budget_entries", ["budget_class", "state"])
    op.create_index("ix_aibe_fingerprint", "ai_budget_entries", ["fingerprint", "created_ts"])
    op.create_index("uq_aibe_inflight_fingerprint", "ai_budget_entries", ["fingerprint"], unique=True,
                    sqlite_where=sa.text("state = 'reserved'"), postgresql_where=sa.text("state = 'reserved'"))


def downgrade() -> None:
    """FAIL CLOSED: refuses (deleting nothing) while any ledger entry or counter row exists."""
    bind = op.get_bind()
    entries = bind.execute(sa.text("SELECT COUNT(*) FROM ai_budget_entries")).scalar() or 0
    controls = bind.execute(sa.text("SELECT COUNT(*) FROM ai_budget_controls")).scalar() or 0
    if entries or controls:
        raise RuntimeError(f"Refusing to downgrade 0044_ai_budget_ledger: {entries} ledger entr(ies) and {controls} counter row(s) exist and are the only record of AI spend. Export them deliberately first.")
    op.drop_index("uq_aibe_inflight_fingerprint", table_name="ai_budget_entries")
    op.drop_index("ix_aibe_fingerprint", table_name="ai_budget_entries")
    op.drop_index("ix_aibe_class_state", table_name="ai_budget_entries")
    op.drop_table("ai_budget_entries")
    op.drop_table("ai_budget_controls")
