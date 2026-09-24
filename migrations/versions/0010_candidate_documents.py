"""Private candidate documents, claims & story bank (Capstone P4/E2/E3).

Adds owner-scoped tables for private candidate documents and their versions,
provenance-bearing extracted claims, and a reusable story/evidence bank. All cascade
from ``users.id`` (so account deletion removes them) and from their parent document
(so document deletion removes derived claims and, via story_evidence, unlinks stories).
Candidate documents are DATA, never public knowledge. Additive only; chains from 0009.
Single head.

Revision ID: 0010_candidate_documents
Revises: 0009_locale_preferences
Create Date: 2026-09-24
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0010_candidate_documents"
down_revision = "0009_locale_preferences"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "candidate_documents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False, server_default="other"),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="uploaded"),
        sa.Column("current_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_candidate_documents_user_id", "candidate_documents", ["user_id"])
    op.create_index("ix_candidate_documents_user_status", "candidate_documents", ["user_id", "status"])

    op.create_table(
        "document_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("storage_key", sa.String(length=128), nullable=False),
        sa.Column("mime_type", sa.String(length=128), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("extraction_origin", sa.String(length=16), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="uploaded"),
        sa.Column("failure_reason", sa.String(length=255), nullable=True),
        sa.Column("language_hint", sa.String(length=8), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["candidate_documents.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("storage_key", name="uq_document_versions_storage_key"),
    )
    op.create_index("ix_document_versions_document", "document_versions", ["document_id"])

    op.create_table(
        "document_claims",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("version_id", sa.Integer(), nullable=False),
        sa.Column("claim_type", sa.String(length=32), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("edited_text", sa.Text(), nullable=True),
        sa.Column("source_page", sa.Integer(), nullable=True),
        sa.Column("source_section", sa.String(length=120), nullable=True),
        sa.Column("review_state", sa.String(length=16), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_id"], ["candidate_documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["version_id"], ["document_versions.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_document_claims_user", "document_claims", ["user_id"])
    op.create_index("ix_document_claims_document_id", "document_claims", ["document_id"])

    op.create_table(
        "candidate_stories",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("situation", sa.Text(), nullable=True),
        sa.Column("task", sa.Text(), nullable=True),
        sa.Column("action", sa.Text(), nullable=True),
        sa.Column("result", sa.Text(), nullable=True),
        sa.Column("competencies", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="user_created"),
        sa.Column("evidence_state", sa.String(length=24), nullable=False, server_default="none"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_candidate_stories_user", "candidate_stories", ["user_id"])

    op.create_table(
        "story_evidence",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("story_id", sa.Integer(), nullable=False),
        sa.Column("claim_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["story_id"], ["candidate_stories.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["claim_id"], ["document_claims.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("story_id", "claim_id", name="uq_story_evidence"),
    )
    op.create_index("ix_story_evidence_story_id", "story_evidence", ["story_id"])
    op.create_index("ix_story_evidence_claim_id", "story_evidence", ["claim_id"])


def downgrade() -> None:
    op.drop_table("story_evidence")
    op.drop_index("ix_candidate_stories_user", table_name="candidate_stories")
    op.drop_table("candidate_stories")
    op.drop_index("ix_document_claims_document_id", table_name="document_claims")
    op.drop_index("ix_document_claims_user", table_name="document_claims")
    op.drop_table("document_claims")
    op.drop_index("ix_document_versions_document", table_name="document_versions")
    op.drop_table("document_versions")
    op.drop_index("ix_candidate_documents_user_status", table_name="candidate_documents")
    op.drop_index("ix_candidate_documents_user_id", table_name="candidate_documents")
    op.drop_table("candidate_documents")
