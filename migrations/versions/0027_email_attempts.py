"""Transactional email attempt records (W12.4C). SCHEMA ONLY: nothing is seeded or back-filled.

Additive. ``email_attempts`` records what the email provider answered when a transactional message was SUBMITTED: message type, provider,
a bounded status, a bounded failure category, an optional provider message reference, the locale and a request id. It stores no recipient
address, token, link, subject, body, credential or header, and ``delivered`` / ``bounced`` states do not exist (no delivery-event evidence is
collected). ``user_id`` is SET NULL on account deletion. Old rows are purged by the application's retention window. With the table empty every
Admin view says "no attempts recorded", so upgrading changes no behaviour. Chains from 0026. Single head.

Revision ID: 0027_email_attempts
Revises: 0026_managed_secrets
Create Date: 2026-10-14
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0027_email_attempts"
down_revision = "0026_managed_secrets"
branch_labels = None
depends_on = None

TYPES = ("email_verification", "password_reset", "account_notice", "admin_test")
STATUSES = ("provider_accepted", "failed", "not_configured", "delivery_unknown", "captured")


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


def upgrade() -> None:
    op.create_table(
        "email_attempts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("message_type", sa.String(length=24), nullable=False),
        sa.Column("provider", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("failure_category", sa.String(length=24), nullable=True),
        sa.Column("provider_message_ref", sa.String(length=80), nullable=True),
        sa.Column("locale", sa.String(length=5), nullable=True),
        sa.Column("request_id", sa.String(length=64), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.CheckConstraint(_in("message_type", TYPES), name="ck_email_attempts_type"),
        sa.CheckConstraint(_in("status", STATUSES), name="ck_email_attempts_status"),
    )
    op.create_index("ix_email_attempts_created", "email_attempts", ["created_at"])
    op.create_index("ix_email_attempts_type_created", "email_attempts", ["message_type", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_email_attempts_type_created", table_name="email_attempts")
    op.drop_index("ix_email_attempts_created", table_name="email_attempts")
    op.drop_table("email_attempts")
