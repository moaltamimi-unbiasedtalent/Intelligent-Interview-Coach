"""Document failure taxonomy column (P10B Wave 3).

Adds a nullable, bounded ``failure_kind`` tag to ``document_versions`` so a FAILED upload
can be explained with a localized, actionable message (e.g. a scanned/image document that
needs OCR) instead of collapsing every failure into one generic string. Additive and
backward-compatible: existing rows keep NULL (the UI falls back to the stored
``failure_reason`` text). No data is moved and no other table changes. Chains from 0011.
Single head.

Revision ID: 0012_document_failure_kind
Revises: 0011_workspaces_shares
Create Date: 2026-09-26
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0012_document_failure_kind"
down_revision = "0011_workspaces_shares"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "document_versions",
        sa.Column("failure_kind", sa.String(length=32), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("document_versions", "failure_kind")
