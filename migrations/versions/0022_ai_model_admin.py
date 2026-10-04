"""Governed AI configuration metadata (P10B-W10.7). SCHEMA ONLY: nothing is seeded and nothing is activated.

Additive. With these tables empty the runtime resolves models exactly as before (environment override, then the code default), so
upgrading changes no behaviour. A configuration version is hash-pinned; an evaluation is bound to one hash and can record no live call; an
approval can never be decided by its requester; activations are append-only with at most one open row per environment.
Chains from 0021. Single head.

Revision ID: 0022_ai_model_admin
Revises: 0021_billing_admin
Create Date: 2026-10-04
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0022_ai_model_admin"
down_revision = "0021_billing_admin"
branch_labels = None
depends_on = None

STATES = ("draft", "validated", "evaluated", "evaluation_failed", "approved", "rejected", "retired")
EVAL = ("queued", "running", "passed", "failed", "error")
APPROVAL = ("pending", "approved", "rejected")
ENVS = ("staging", "production")
KINDS = ("activate", "rollback", "revert_to_code")


def _in(column, values):
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


def _dt(name, nullable=True):
    return sa.Column(name, sa.DateTime(timezone=True), nullable=nullable)


def _pk():
    return [sa.Column("id", sa.Integer(), nullable=False), sa.Column("public_id", sa.String(length=32), nullable=False)]


def upgrade() -> None:
    op.create_table(
        "ai_config_versions", *_pk(),
        sa.Column("version", sa.Integer(), nullable=False), sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("notes", sa.String(length=300), nullable=False, server_default=""),
        sa.Column("state", sa.String(length=20), nullable=False, server_default="draft"),
        sa.Column("config_json", sa.JSON(), nullable=False), sa.Column("config_hash", sa.String(length=64), nullable=False),
        sa.Column("catalogue_version", sa.String(length=24), nullable=False), sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("base_version_id", sa.Integer(), nullable=True), sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        _dt("created_at", False), _dt("validated_at"), sa.Column("validation_json", sa.JSON(), nullable=True), _dt("retired_at"),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["base_version_id"], ["ai_config_versions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.CheckConstraint(_in("state", STATES), name="ck_aicv_state"),
        sa.CheckConstraint("length(config_hash) = 64", name="ck_aicv_hash"),
        sa.UniqueConstraint("version", name="uq_aicv_version"),
    )
    op.create_index("ix_ai_config_versions_public_id", "ai_config_versions", ["public_id"], unique=True)
    op.create_index("ix_aicv_state_created", "ai_config_versions", ["state", "created_at"])

    op.create_table(
        "ai_config_evaluations", *_pk(),
        sa.Column("config_version_id", sa.Integer(), nullable=False), sa.Column("config_hash", sa.String(length=64), nullable=False),
        sa.Column("evaluator_version", sa.String(length=24), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False, server_default="queued"),
        sa.Column("checks_json", sa.JSON(), nullable=True), sa.Column("summary_json", sa.JSON(), nullable=True),
        sa.Column("live_calls", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failure_category", sa.String(length=24), nullable=True), sa.Column("requested_by_user_id", sa.Integer(), nullable=True),
        _dt("created_at", False), _dt("finished_at"),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["config_version_id"], ["ai_config_versions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.CheckConstraint(_in("status", EVAL), name="ck_aice_status"),
        sa.CheckConstraint("live_calls = 0", name="ck_aice_no_live_calls"),
    )
    op.create_index("ix_ai_config_evaluations_public_id", "ai_config_evaluations", ["public_id"], unique=True)
    op.create_index("ix_aice_version", "ai_config_evaluations", ["config_version_id", "created_at"])

    op.create_table(
        "ai_config_approvals", *_pk(),
        sa.Column("config_version_id", sa.Integer(), nullable=False), sa.Column("config_hash", sa.String(length=64), nullable=False),
        sa.Column("evaluation_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False, server_default="pending"),
        sa.Column("requested_by_user_id", sa.Integer(), nullable=True), _dt("requested_at", False),
        sa.Column("decided_by_user_id", sa.Integer(), nullable=True), _dt("decided_at"),
        sa.Column("reason", sa.String(length=300), nullable=False, server_default=""),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["config_version_id"], ["ai_config_versions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["evaluation_id"], ["ai_config_evaluations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["decided_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.CheckConstraint(_in("status", APPROVAL), name="ck_aica_status"),
        sa.CheckConstraint("decided_by_user_id IS NULL OR requested_by_user_id IS NULL OR decided_by_user_id <> requested_by_user_id",
                           name="ck_aica_no_self_approval"),
    )
    op.create_index("ix_ai_config_approvals_public_id", "ai_config_approvals", ["public_id"], unique=True)
    op.create_index("uq_aica_one_pending", "ai_config_approvals", ["config_version_id"], unique=True,
                    sqlite_where=sa.text("status = 'pending'"), postgresql_where=sa.text("status = 'pending'"))

    op.create_table(
        "ai_config_activations", *_pk(),
        sa.Column("environment", sa.String(length=12), nullable=False), sa.Column("config_version_id", sa.Integer(), nullable=True),
        sa.Column("config_hash", sa.String(length=64), nullable=True), sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("approval_id", sa.Integer(), nullable=True), sa.Column("activated_by_user_id", sa.Integer(), nullable=True),
        _dt("activated_at", False), _dt("deactivated_at"), sa.Column("reason", sa.String(length=300), nullable=False, server_default=""),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["config_version_id"], ["ai_config_versions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["approval_id"], ["ai_config_approvals.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["activated_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.CheckConstraint(_in("environment", ENVS), name="ck_aicact_env"),
        sa.CheckConstraint(_in("kind", KINDS), name="ck_aicact_kind"),
    )
    op.create_index("ix_ai_config_activations_public_id", "ai_config_activations", ["public_id"], unique=True)
    op.create_index("uq_aicact_one_open", "ai_config_activations", ["environment"], unique=True,
                    sqlite_where=sa.text("deactivated_at IS NULL"), postgresql_where=sa.text("deactivated_at IS NULL"))
    op.create_index("ix_aicact_env_time", "ai_config_activations", ["environment", "activated_at"])


def downgrade() -> None:
    op.drop_table("ai_config_activations")
    op.drop_table("ai_config_approvals")
    op.drop_table("ai_config_evaluations")
    op.drop_table("ai_config_versions")
