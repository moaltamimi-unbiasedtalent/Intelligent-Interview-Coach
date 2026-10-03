"""Durable jobs and worker presence (P10B-W10.9).

Additive. ``jobs`` is the DB-backed queue and its operational history; ``job_workers`` records worker presence for
diagnostics. No secret, header, stack trace, provider response or private candidate content is stored: payloads are
validated per code-defined job type and reference records by id. A partial unique index enforces at most ONE ACTIVE
(queued or running) job per (job_type, idempotency_key). Chains from 0017. Single head.

Revision ID: 0018_jobs
Revises: 0017_integrations
Create Date: 2026-10-03
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0018_jobs"
down_revision = "0017_integrations"
branch_labels = None
depends_on = None

STATES = ("queued", "running", "succeeded", "failed", "cancelled")
PRIORITIES = ("low", "normal", "high")
CATEGORIES = ("transient", "timeout", "rate_limited", "unavailable", "invalid_payload", "configuration_error",
              "unsupported", "unknown_job_type", "lease_expired", "internal_error")
WORKER_STATUSES = ("running", "stopped")
ACTIVE = "idempotency_key IS NOT NULL AND state IN ('queued', 'running')"


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


def upgrade() -> None:
    op.create_table(
        "jobs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("public_id", sa.String(length=32), nullable=False),
        sa.Column("job_type", sa.String(length=48), nullable=False),
        sa.Column("state", sa.String(length=16), server_default="queued", nullable=False),
        sa.Column("priority", sa.String(length=8), server_default="normal", nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("payload_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("idempotency_key", sa.String(length=120), nullable=True),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("max_attempts", sa.Integer(), server_default="3", nullable=False),
        sa.Column("manual_retries", sa.Integer(), server_default="0", nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lease_owner", sa.String(length=40), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_category", sa.String(length=24), nullable=True),
        sa.Column("last_error_message_safe", sa.String(length=200), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.CheckConstraint(_in("state", STATES), name="ck_jobs_state"),
        sa.CheckConstraint(_in("priority", PRIORITIES), name="ck_jobs_priority"),
        sa.CheckConstraint("attempts >= 0", name="ck_jobs_attempts_nonneg"),
        sa.CheckConstraint("max_attempts >= 1", name="ck_jobs_max_attempts_pos"),
        sa.CheckConstraint("attempts <= max_attempts", name="ck_jobs_attempts_le_max"),
        sa.CheckConstraint("manual_retries >= 0", name="ck_jobs_manual_retries_nonneg"),
        sa.CheckConstraint(
            "(state = 'running' AND lease_owner IS NOT NULL AND lease_expires_at IS NOT NULL) "
            "OR (state <> 'running' AND lease_owner IS NULL AND lease_expires_at IS NULL)",
            name="ck_jobs_lease_matches_state"),
        sa.CheckConstraint("last_error_category IS NULL OR " + _in("last_error_category", CATEGORIES),
                           name="ck_jobs_error_category"),
    )
    op.create_index("ix_jobs_public_id", "jobs", ["public_id"], unique=True)
    op.create_index("uq_jobs_active_idempotency", "jobs", ["job_type", "idempotency_key"], unique=True,
                    sqlite_where=sa.text(ACTIVE), postgresql_where=sa.text(ACTIVE))
    op.create_index("ix_jobs_claim", "jobs", ["state", "available_at", "priority"])
    op.create_index("ix_jobs_lease_expiry", "jobs", ["state", "lease_expires_at"])
    op.create_index("ix_jobs_type_state", "jobs", ["job_type", "state"])
    op.create_index("ix_jobs_created", "jobs", ["created_at"])

    op.create_table(
        "job_workers",
        sa.Column("worker_id", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=12), server_default="running", nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("jobs_succeeded", sa.Integer(), server_default="0", nullable=False),
        sa.Column("jobs_failed", sa.Integer(), server_default="0", nullable=False),
        sa.PrimaryKeyConstraint("worker_id"),
        sa.CheckConstraint(_in("status", WORKER_STATUSES), name="ck_job_workers_status"),
    )


def downgrade() -> None:
    op.drop_table("job_workers")
    for name in ("ix_jobs_created", "ix_jobs_type_state", "ix_jobs_lease_expiry", "ix_jobs_claim",
                 "uq_jobs_active_idempotency", "ix_jobs_public_id"):
        op.drop_index(name, table_name="jobs")
    op.drop_table("jobs")
