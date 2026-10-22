"""Workspace ownership transfers (package 04B completion, REQ-OWN-07). Additive and data-preserving.

Adds ONE new table, ``workspace_ownership_transfers``, and changes nothing else: a pending two-step ownership transfer (proposer, recipient, the role the former
owner keeps, a SHA-256 hash of the acceptance token, a SHA-256 hash of the recipient's verified address, status, expiry). A partial unique index allows at most
ONE ``pending`` row per workspace, so two concurrent proposals cannot both succeed. No existing table or column is altered; every existing workspace, membership,
invitation and share stays valid and unchanged.

Why a migration is genuinely needed: a pending transfer has an expiry, a hashed one-time token and a state machine that must survive restarts and be race-safe;
there is no existing column or table that can hold it (the owner is a column of ``workspaces`` and a role of a membership, not a pending proposal).

The table only REFERENCES ``workspaces`` and ``users`` through foreign keys (ON DELETE CASCADE, so a transfer is removed with its workspace or account); it
neither reads nor alters them.

The downgrade is FAIL-CLOSED: it refuses (deleting nothing) while ANY transfer row exists, whatever its state, because the rows are the state record of an ownership
decision. Remove them deliberately first.

Revision ID: 0044_workspace_ownership_transfers
Revises: 0043_story_bank_completion
Create Date: 2026-10-22
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0044_workspace_ownership_transfers"
down_revision = "0043_story_bank_completion"
branch_labels = None
depends_on = None

_TABLE = "workspace_ownership_transfers"


def upgrade() -> None:
    op.create_table(
        _TABLE,
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("proposer_user_id", sa.Integer(), nullable=False),
        sa.Column("recipient_user_id", sa.Integer(), nullable=False),
        sa.Column("former_owner_role", sa.String(length=24), nullable=False),
        sa.Column("token_hash", sa.String(length=128), nullable=False),
        sa.Column("recipient_email_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decided_reason", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["proposer_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["recipient_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("status IN ('pending','accepted','declined','cancelled','expired')", name="ck_ownership_transfer_status"),
        sa.CheckConstraint("former_owner_role IN ('workspace_admin','workspace_member')", name="ck_ownership_transfer_former_role"),
    )
    op.create_index("uq_ownership_transfer_one_open", _TABLE, ["workspace_id"], unique=True,
                    sqlite_where=sa.text("status = 'pending'"), postgresql_where=sa.text("status = 'pending'"))
    op.create_index("ix_ownership_transfers_token", _TABLE, ["token_hash"], unique=True)
    op.create_index("ix_ownership_transfers_proposer", _TABLE, ["proposer_user_id"])
    op.create_index("ix_ownership_transfers_recipient", _TABLE, ["recipient_user_id"])


def downgrade() -> None:
    """FAIL CLOSED: refuses (deleting nothing) while any transfer row exists."""
    bind = op.get_bind()
    held = int(bind.execute(sa.text(f"SELECT COUNT(*) FROM {_TABLE}")).scalar() or 0)
    if held:
        raise RuntimeError(f"Refusing to downgrade 0044_workspace_ownership_transfers: {held} ownership transfer record(s) exist. "
                           "They are the state record of an ownership decision; remove them deliberately first.")
    op.drop_index("ix_ownership_transfers_recipient", table_name=_TABLE)
    op.drop_index("ix_ownership_transfers_proposer", table_name=_TABLE)
    op.drop_index("ix_ownership_transfers_token", table_name=_TABLE)
    op.drop_index("uq_ownership_transfer_one_open", table_name=_TABLE)
    op.drop_table(_TABLE)
