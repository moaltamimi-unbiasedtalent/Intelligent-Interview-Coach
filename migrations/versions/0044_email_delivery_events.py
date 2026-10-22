"""Verified email delivery-event evidence (package 05D, PG-02). Additive: three nullable columns, one CHECK and one index on ``email_attempts``.

``delivery_state`` (delivered, soft_bounced, blocked, hard_bounced, complained) is a SEPARATE fact from ``status`` (what the provider said when it ACCEPTED a
submission, which is not delivery and is never rewritten). It is set only by an authenticated provider webhook and collection stays behind the code gate
``src.mail.webhook.DELIVERY_EVENTS_AUTHORIZED`` (False), so after this migration every existing and new row keeps NULL until the owner authorises it. The
columns hold no recipient, token, link or content: ``delivery_event_at`` is the provider's event time and ``delivery_event_digest`` a one-way hash that makes a
replay a no-op. Nothing existing is changed or backfilled.

The downgrade is FAIL-CLOSED: it refuses (deleting nothing) while any row carries a delivery state, because that is verified delivery evidence that the
downgrade would silently destroy. Export what you need and clear it deliberately first.
Chains from 0043.

Revision ID: 0044_email_delivery_events
Revises: 0043_story_bank_completion
Create Date: 2026-10-22
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0044_email_delivery_events"
down_revision = "0043_story_bank_completion"
branch_labels = None
depends_on = None

_STATES = ("delivered", "soft_bounced", "blocked", "hard_bounced", "complained")
_CHECK = "delivery_state IS NULL OR delivery_state IN (" + ", ".join(repr(v) for v in _STATES) + ")"


def upgrade() -> None:
    with op.batch_alter_table("email_attempts") as batch:
        batch.add_column(sa.Column("delivery_state", sa.String(length=16), nullable=True))
        batch.add_column(sa.Column("delivery_event_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("delivery_event_digest", sa.String(length=64), nullable=True))
        batch.create_check_constraint("ck_email_attempts_delivery_state", _CHECK)
    op.create_index("ix_email_attempts_message_ref", "email_attempts", ["provider_message_ref"])


def downgrade() -> None:
    """FAIL CLOSED: refuses (deleting nothing) while any attempt carries verified delivery evidence."""
    bind = op.get_bind()
    held = bind.execute(sa.text("SELECT COUNT(*) FROM email_attempts WHERE delivery_state IS NOT NULL")).scalar() or 0
    if held:
        raise RuntimeError(
            f"Refusing to downgrade 0044_email_delivery_events: {held} email attempt(s) carry verified delivery evidence that would be destroyed. "
            "Export what you need and clear it deliberately first.")
    op.drop_index("ix_email_attempts_message_ref", table_name="email_attempts")
    with op.batch_alter_table("email_attempts") as batch:
        batch.drop_constraint("ck_email_attempts_delivery_state", type_="check")
        batch.drop_column("delivery_event_digest")
        batch.drop_column("delivery_event_at")
        batch.drop_column("delivery_state")
