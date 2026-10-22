"""Invitation-only private beta registration (package 04E, REQ-BETA-01). Additive: one table, nothing seeded, no existing row touched.

``registration_invitations`` holds one row per invitation: ONLY the SHA-256 hash of a 256-bit random code (never the code), an optional salted email-binding hash and a
masked display hint, expiry, redemption and revocation timestamps (state is derived from them), and the issuing, redeeming and revoking account ids (all SET NULL, so
deleting an account anonymises the linkage). Existing users are unaffected; sign-in is unchanged.

The downgrade is FAIL-CLOSED: it refuses (deleting nothing) while any invitation is live, meaning pending (unredeemed, unrevoked, unexpired) or redeemed, because those
rows are the only record of who may still register and of which registrations were invited. Revoke or let pending ones expire, and export what you need, first.
Chains from 0040. Single head.

Revision ID: 0041_registration_invitations
Revises: 0040_knowledge_alert_categories
Create Date: 2026-10-22
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0041_registration_invitations"
down_revision = "0040_knowledge_alert_categories"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "registration_invitations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("email_hash", sa.String(length=64), nullable=True),
        sa.Column("email_hint", sa.String(length=64), nullable=True),
        sa.Column("issued_by_user_id", sa.Integer(), nullable=True),
        sa.Column("redeemed_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("redeemed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_by_user_id", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["issued_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["redeemed_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["revoked_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("code_hash", name="uq_registration_invitations_code_hash"),
        sa.CheckConstraint("expires_at > created_at", name="ck_registration_invitations_expiry"),
    )
    op.create_index("ix_registration_invitations_expires", "registration_invitations", ["expires_at"])


def downgrade() -> None:
    """FAIL CLOSED: refuses (deleting nothing) while any invitation is pending or redeemed."""
    bind = op.get_bind()
    # Pending = not revoked, not redeemed, not yet expired; redeemed = redeemed and not revoked. Typed Core columns so the timestamp binds the way the ORM stores it.
    t = sa.table("registration_invitations", sa.column("revoked_at", sa.DateTime(timezone=True)), sa.column("redeemed_at", sa.DateTime(timezone=True)),
                 sa.column("expires_at", sa.DateTime(timezone=True)))
    live = bind.execute(sa.select(sa.func.count()).select_from(t).where(
        t.c.revoked_at.is_(None), sa.or_(t.c.redeemed_at.is_not(None), t.c.expires_at > _utcnow()))).scalar() or 0
    if live:
        raise RuntimeError(
            f"Refusing to downgrade 0041_registration_invitations: {live} live invitation(s) (pending or redeemed) exist and are the only record of who may register. "
            "Revoke or let pending ones expire, and export what you need, deliberately first.")
    op.drop_index("ix_registration_invitations_expires", table_name="registration_invitations")
    op.drop_table("registration_invitations")


def _utcnow():
    from datetime import datetime, timezone

    return datetime.now(timezone.utc)
