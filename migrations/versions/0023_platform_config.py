"""Durable platform pause state and feature-flag overrides (P10B-W10.11). SCHEMA ONLY: nothing is seeded.

Additive. ``platform_pause_states`` holds explicit pause/resume rows per (environment, capability); ``feature_flag_overrides`` holds explicit
enabled/disabled overrides per (environment, flag key). With both tables empty every capability and flag resolves to its pre-W10.11 baseline
(the ``PAUSED_CAPABILITIES`` environment seed and the existing environment flags), so upgrading changes no behaviour. Flag keys are code-defined and
validated by the service, not by a DB CHECK. Chains from 0022. Single head.

Revision ID: 0023_platform_config
Revises: 0022_ai_model_admin
Create Date: 2026-10-04
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0023_platform_config"
down_revision = "0022_ai_model_admin"
branch_labels = None
depends_on = None

ENVS = ("development", "staging", "production")


def _in(column, values):
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


def _dt(name, nullable=True):
    return sa.Column(name, sa.DateTime(timezone=True), nullable=nullable)


def upgrade() -> None:
    op.create_table(
        "platform_pause_states",
        sa.Column("id", sa.Integer(), nullable=False), sa.Column("environment", sa.String(length=12), nullable=False),
        sa.Column("capability", sa.String(length=32), nullable=False), sa.Column("paused", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"), _dt("paused_at"),
        sa.Column("paused_by_user_id", sa.Integer(), nullable=True), _dt("resumed_at"), sa.Column("resumed_by_user_id", sa.Integer(), nullable=True),
        _dt("updated_at", False), sa.Column("reason", sa.String(length=200), nullable=False, server_default=""),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["paused_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["resumed_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("environment", "capability", name="uq_pps_env_capability"),
        sa.CheckConstraint(_in("environment", ENVS), name="ck_pps_env"),
        sa.CheckConstraint("revision >= 0", name="ck_pps_revision"),
    )
    op.create_table(
        "feature_flag_overrides",
        sa.Column("id", sa.Integer(), nullable=False), sa.Column("environment", sa.String(length=12), nullable=False),
        sa.Column("flag_key", sa.String(length=48), nullable=False), sa.Column("enabled", sa.Boolean(), nullable=True),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"), sa.Column("updated_by_user_id", sa.Integer(), nullable=True),
        _dt("updated_at", False), sa.Column("reason", sa.String(length=200), nullable=False, server_default=""),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("environment", "flag_key", name="uq_ffo_env_key"),
        sa.CheckConstraint(_in("environment", ENVS), name="ck_ffo_env"),
        sa.CheckConstraint("revision >= 0", name="ck_ffo_revision"),
    )


def downgrade() -> None:
    op.drop_table("feature_flag_overrides")
    op.drop_table("platform_pause_states")
