"""Identity & platform foundation (Capstone P1/E1).

Replaces the transitional ``X-User-Subject`` boundary's data model with a durable
identity/authorization foundation, WITHOUT orphaning any existing user-scoped data.

The existing ``users`` table remains the OWNER/principal (every candidate resource
already references ``users.id``), so no owned resource is re-keyed. This migration:

* adds ``platform_role`` / ``status`` / ``email_verified`` to ``users``;
* adds ``account_identities`` (login methods linked to a user) and BACKFILLS one
  row per existing user from its transitional ``(provider, subject)`` so existing
  lookups keep resolving to the same owner;
* adds ``password_credentials``, ``auth_sessions``, ``auth_tokens`` (auth);
* adds ``product_entitlements`` and BACKFILLS a ``basic`` tier for every user;
* adds ``audit_events``.

Legacy-data preservation: no DELETE/UPDATE of candidate rows; every ``user_id``
foreign key target is unchanged. Downgrade drops the new tables/columns only.

Deterministic: the backfill reads existing rows and inserts derived rows in a fixed
order; re-running upgrade→downgrade→upgrade reproduces the same state.

Revision ID: 0007_identity_platform
Revises: 0006_user_feedback
Create Date: 2026-09-24
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0007_identity_platform"
down_revision = "0006_user_feedback"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1) Principal columns on the existing users table (server_default so existing
    #    rows get a value without a data migration; role default is the safe 'user').
    op.add_column(
        "users",
        sa.Column("platform_role", sa.String(length=32), nullable=False, server_default="user"),
    )
    op.add_column(
        "users",
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
    )
    op.add_column(
        "users",
        sa.Column("email_verified", sa.Boolean(), nullable=False, server_default=sa.text("0")),
    )

    # 2) account_identities — one login method per row, linked to the owner.
    op.create_table(
        "account_identities",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("provider_subject", sa.String(length=320), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("email_verified", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("provider", "provider_subject", name="uq_identity_provider_subject"),
    )
    op.create_index("ix_account_identities_user_id", "account_identities", ["user_id"])
    op.create_index("ix_account_identities_email", "account_identities", ["email"])

    # 3) password_credentials — bcrypt hash, one row per user (created on register).
    op.create_table(
        "password_credentials",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", name="uq_password_credentials_user"),
    )
    op.create_index("ix_password_credentials_user_id", "password_credentials", ["user_id"])

    # 4) auth_sessions — server-side sessions; PK is the token hash (never the token).
    op.create_table(
        "auth_sessions",
        sa.Column("token_hash", sa.String(length=64), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("user_agent", sa.String(length=256), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_auth_sessions_user", "auth_sessions", ["user_id"])

    # 5) auth_tokens — single-use, expiring verification/reset tokens (hash only).
    op.create_table(
        "auth_tokens",
        sa.Column("token_hash", sa.String(length=64), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("purpose", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_auth_tokens_user_purpose", "auth_tokens", ["user_id", "purpose"])

    # 6) product_entitlements — tier per user (foundation only, no billing).
    op.create_table(
        "product_entitlements",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("tier", sa.String(length=32), nullable=False, server_default="basic"),
        sa.Column("source", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", name="uq_product_entitlements_user"),
    )
    op.create_index("ix_product_entitlements_user_id", "product_entitlements", ["user_id"])

    # 7) audit_events — bounded security/privacy audit log.
    op.create_table(
        "audit_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("target_type", sa.String(length=64), nullable=True),
        sa.Column("target_id", sa.String(length=128), nullable=True),
        sa.Column("result", sa.String(length=32), nullable=False, server_default="success"),
        sa.Column("request_id", sa.String(length=64), nullable=True),
        sa.Column("context", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_audit_events_actor", "audit_events", ["actor_user_id"])
    op.create_index("ix_audit_events_type", "audit_events", ["event_type"])

    # --- deterministic backfill (preserve existing ownership) -----------------
    _backfill()


def _backfill() -> None:
    """Backfill identities + entitlements for existing users (no candidate data touched)."""
    bind = op.get_bind()
    users = sa.table(
        "users",
        sa.column("id", sa.Integer),
        sa.column("subject", sa.String),
        sa.column("provider", sa.String),
        sa.column("email", sa.String),
    )
    identities = sa.table(
        "account_identities",
        sa.column("user_id", sa.Integer),
        sa.column("provider", sa.String),
        sa.column("provider_subject", sa.String),
        sa.column("email", sa.String),
        sa.column("email_verified", sa.Boolean),
        sa.column("created_at", sa.DateTime),
        sa.column("updated_at", sa.DateTime),
    )
    entitlements = sa.table(
        "product_entitlements",
        sa.column("user_id", sa.Integer),
        sa.column("tier", sa.String),
        sa.column("source", sa.String),
        sa.column("created_at", sa.DateTime),
        sa.column("updated_at", sa.DateTime),
    )
    now = sa.func.now()
    rows = list(bind.execute(sa.select(users.c.id, users.c.subject, users.c.provider, users.c.email)))
    for user_id, subject, provider, email in rows:
        bind.execute(
            identities.insert().values(
                user_id=user_id,
                provider=provider,
                provider_subject=subject,
                email=email,
                email_verified=False,
                created_at=now,
                updated_at=now,
            )
        )
        bind.execute(
            entitlements.insert().values(
                user_id=user_id,
                tier="basic",
                source="backfill",
                created_at=now,
                updated_at=now,
            )
        )


def downgrade() -> None:
    op.drop_index("ix_audit_events_type", table_name="audit_events")
    op.drop_index("ix_audit_events_actor", table_name="audit_events")
    op.drop_table("audit_events")

    op.drop_index("ix_product_entitlements_user_id", table_name="product_entitlements")
    op.drop_table("product_entitlements")

    op.drop_index("ix_auth_tokens_user_purpose", table_name="auth_tokens")
    op.drop_table("auth_tokens")

    op.drop_index("ix_auth_sessions_user", table_name="auth_sessions")
    op.drop_table("auth_sessions")

    op.drop_index("ix_password_credentials_user_id", table_name="password_credentials")
    op.drop_table("password_credentials")

    op.drop_index("ix_account_identities_email", table_name="account_identities")
    op.drop_index("ix_account_identities_user_id", table_name="account_identities")
    op.drop_table("account_identities")

    op.drop_column("users", "email_verified")
    op.drop_column("users", "status")
    op.drop_column("users", "platform_role")
