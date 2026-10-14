"""Admin-managed provider credentials, encrypted at rest (W12.4B). SCHEMA ONLY: nothing is seeded or imported.

Additive. ``managed_secrets`` holds one authenticated-encryption record (AES-256-GCM ciphertext + nonce + key id) per code-defined
(integration, credential slot). It never holds plaintext, a mask, a prefix or suffix, a fingerprint or a history, and the encryption key lives
in deployment configuration, never in this database. Environment credentials are NOT copied in; with the table empty every integration keeps
resolving from the environment exactly as before. Chains from 0025. Single head.

Revision ID: 0026_managed_secrets
Revises: 0025_security_audit_incidents
Create Date: 2026-10-14
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0026_managed_secrets"
down_revision = "0025_security_audit_incidents"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "managed_secrets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("integration_code", sa.String(length=40), nullable=False),
        sa.Column("slot", sa.String(length=32), nullable=False),
        sa.Column("ciphertext", sa.LargeBinary(), nullable=False),
        sa.Column("nonce", sa.LargeBinary(length=12), nullable=False),
        sa.Column("key_id", sa.String(length=16), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_by_user_id", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("integration_code", "slot", name="uq_managed_secrets_slot"),
        sa.CheckConstraint("revision >= 1", name="ck_managed_secrets_revision"),
    )


def downgrade() -> None:
    op.drop_table("managed_secrets")
