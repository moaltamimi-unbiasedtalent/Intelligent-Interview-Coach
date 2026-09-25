"""Teams / workspaces, memberships, invitations, explicit share grants + feedback category
(Capstone P6.5).

Adds bounded collaboration tables — all cascade from ``users.id`` / ``workspaces.id`` so
account/workspace deletion removes them — plus an optional ``category`` column on
``user_feedback`` for the P6 feedback taxonomy. Additive only; chains from 0010. Single head.

Revision ID: 0011_workspaces_shares
Revises: 0010_candidate_documents
Create Date: 2026-09-25
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0011_workspaces_shares"
down_revision = "0010_candidate_documents"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workspaces",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_workspaces_owner", "workspaces", ["owner_user_id"])

    op.create_table(
        "workspace_memberships",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=24), nullable=False, server_default="workspace_member"),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("workspace_id", "user_id", name="uq_workspace_member"),
    )
    op.create_index("ix_workspace_memberships_user", "workspace_memberships", ["user_id"])
    op.create_index("ix_workspace_memberships_workspace", "workspace_memberships", ["workspace_id"])

    op.create_table(
        "workspace_invitations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("inviter_user_id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("token_hash", sa.String(length=128), nullable=False),
        sa.Column("role", sa.String(length=24), nullable=False, server_default="workspace_member"),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="pending"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["inviter_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["accepted_user_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_workspace_invitations_workspace", "workspace_invitations", ["workspace_id"])
    op.create_index("ix_workspace_invitations_token", "workspace_invitations", ["token_hash"])

    op.create_table(
        "share_grants",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("resource_type", sa.String(length=32), nullable=False),
        sa.Column("resource_id", sa.String(length=128), nullable=False),
        sa.Column("permission", sa.String(length=16), nullable=False, server_default="view"),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "owner_user_id", "workspace_id", "resource_type", "resource_id",
            name="uq_share_grant",
        ),
    )
    op.create_index("ix_share_grants_workspace", "share_grants", ["workspace_id"])
    op.create_index("ix_share_grants_owner", "share_grants", ["owner_user_id"])

    # Optional bounded feedback category (P6 taxonomy). Nullable so simple ratings stay easy.
    op.add_column("user_feedback", sa.Column("category", sa.String(length=32), nullable=True))


def downgrade() -> None:
    op.drop_column("user_feedback", "category")
    op.drop_index("ix_share_grants_owner", table_name="share_grants")
    op.drop_index("ix_share_grants_workspace", table_name="share_grants")
    op.drop_table("share_grants")
    op.drop_index("ix_workspace_invitations_token", table_name="workspace_invitations")
    op.drop_index("ix_workspace_invitations_workspace", table_name="workspace_invitations")
    op.drop_table("workspace_invitations")
    op.drop_index("ix_workspace_memberships_workspace", table_name="workspace_memberships")
    op.drop_index("ix_workspace_memberships_user", table_name="workspace_memberships")
    op.drop_table("workspace_memberships")
    op.drop_index("ix_workspaces_owner", table_name="workspaces")
    op.drop_table("workspaces")
