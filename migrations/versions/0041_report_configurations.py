"""Saved Admin report configurations (package 03E1). Additive: one table, nothing seeded.

``report_configurations`` stores a saved report DEFINITION (registered metric ids, window, grouping, filters, chart kind) per owning Admin. It never stores a result, a figure or
candidate data. The downgrade is FAIL-CLOSED: it refuses while any row exists, because those rows are the only record of the Admins' saved definitions.

Revision ID: 0041_report_configurations
Revises: 0040_knowledge_alert_categories
Create Date: 2026-10-22

Chain note: the lead reserved 0042 for this package. ``tests/_alembic_head.py`` requires revision numbers to be contiguous from 0001, so on a base whose head is 0040 a 0042 file
would turn every chain check red; this revision is therefore numbered 0041 (``down_revision`` = the head visible on the branch, 0040). If another package lands 0041 first, the lead
re-chains it: rename the file and ``revision`` to the next free number and set ``down_revision`` to the then-current head (nothing else refers to the number; the tests find it by name).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0041_report_configurations"
down_revision = "0040_knowledge_alert_categories"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "report_configurations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=60), nullable=False),
        sa.Column("report_id", sa.String(length=64), nullable=False),
        sa.Column("definition_json", sa.JSON(), nullable=False),
        sa.Column("definition_hash", sa.String(length=64), nullable=False),
        sa.Column("shared", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("revision", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("owner_user_id", "name", name="uq_rc_owner_name"),
        sa.CheckConstraint("revision >= 1", name="ck_rc_revision"),
        sa.CheckConstraint("length(definition_hash) = 64", name="ck_rc_hash"),
    )
    op.create_index("ix_rc_owner", "report_configurations", ["owner_user_id"])


def downgrade() -> None:
    """FAIL CLOSED: refuses (deleting nothing) while any saved report configuration exists."""
    bind = op.get_bind()
    count = bind.execute(sa.text("SELECT COUNT(*) FROM report_configurations")).scalar() or 0
    if count:
        raise RuntimeError(f"Refusing to downgrade 0041_report_configurations: {count} saved report configuration(s) exist and are the only record of administrators' saved definitions. Export or remove them deliberately first.")
    op.drop_index("ix_rc_owner", table_name="report_configurations")
    op.drop_table("report_configurations")
