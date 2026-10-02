"""Customer support and ticketing (P10B-W10.3).

Additive. Three tables with distinct data boundaries:
- support_tickets: the operational record (owner, category, priority, status, assignment, safe source context).
- support_messages: the CUSTOMER-VISIBLE thread (candidate and support authors).
- support_internal_notes: ADMIN-ONLY notes, physically separate so no candidate query can reach them.

Candidate-owned rows cascade from users (account deletion also deletes them explicitly: SQLite does not
enforce FK cascades). Operator references (assignee, message/note author) are SET NULL so an operator's
removal never destroys a candidate's thread. No SLA columns (no SLA policy is approved) and no attachment
table (attachments are deferred). Chains from 0014. Single head.

Revision ID: 0015_support_ticketing
Revises: 0014_opportunities
Create Date: 2026-10-03
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0015_support_ticketing"
down_revision = "0014_opportunities"
branch_labels = None
depends_on = None

CATEGORIES = ("account_login", "opportunity", "prepare", "practice_interview", "documents", "ai_response",
              "billing", "privacy", "accessibility", "technical", "data_issue", "other")
PRIORITIES = ("low", "normal", "high", "urgent")
STATUSES = ("new", "triaged", "in_progress", "waiting_for_customer", "resolved", "closed")
AUTHOR_KINDS = ("candidate", "support")


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


def upgrade() -> None:
    op.create_table(
        "support_tickets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("public_id", sa.String(length=32), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("priority", sa.String(length=16), nullable=False, server_default="normal"),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="new"),
        sa.Column("subject", sa.String(length=200), nullable=False),
        sa.Column("assigned_user_id", sa.Integer(), nullable=True),
        sa.Column("initial_request_id", sa.String(length=64), nullable=True),
        sa.Column("source_route", sa.String(length=200), nullable=True),
        sa.Column("source_environment", sa.String(length=24), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["assigned_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.CheckConstraint(_in("category", CATEGORIES), name="ck_support_tickets_category"),
        sa.CheckConstraint(_in("priority", PRIORITIES), name="ck_support_tickets_priority"),
        sa.CheckConstraint(_in("status", STATUSES), name="ck_support_tickets_status"),
    )
    op.create_index("ix_support_tickets_public_id", "support_tickets", ["public_id"], unique=True)
    op.create_index("ix_support_tickets_owner_updated", "support_tickets", ["owner_user_id", "updated_at"])
    op.create_index("ix_support_tickets_status_updated", "support_tickets", ["status", "updated_at"])
    op.create_index("ix_support_tickets_assignee_status", "support_tickets", ["assigned_user_id", "status"])

    op.create_table(
        "support_messages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ticket_id", sa.Integer(), nullable=False),
        sa.Column("author_user_id", sa.Integer(), nullable=True),
        sa.Column("author_kind", sa.String(length=16), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("request_id", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["ticket_id"], ["support_tickets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["author_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.CheckConstraint(_in("author_kind", AUTHOR_KINDS), name="ck_support_messages_author_kind"),
    )
    op.create_index("ix_support_messages_ticket", "support_messages", ["ticket_id", "id"])

    op.create_table(
        "support_internal_notes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ticket_id", sa.Integer(), nullable=False),
        sa.Column("author_user_id", sa.Integer(), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("request_id", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["ticket_id"], ["support_tickets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["author_user_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_support_internal_notes_ticket", "support_internal_notes", ["ticket_id", "id"])


def downgrade() -> None:
    op.drop_index("ix_support_internal_notes_ticket", table_name="support_internal_notes")
    op.drop_table("support_internal_notes")
    op.drop_index("ix_support_messages_ticket", table_name="support_messages")
    op.drop_table("support_messages")
    op.drop_index("ix_support_tickets_assignee_status", table_name="support_tickets")
    op.drop_index("ix_support_tickets_status_updated", table_name="support_tickets")
    op.drop_index("ix_support_tickets_owner_updated", table_name="support_tickets")
    op.drop_index("ix_support_tickets_public_id", table_name="support_tickets")
    op.drop_table("support_tickets")
