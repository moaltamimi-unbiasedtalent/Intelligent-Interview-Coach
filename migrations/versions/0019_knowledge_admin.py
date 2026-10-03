"""Governed knowledge administration (P10B-W10.8).

Additive. ``knowledge_sources`` (stable identity), ``knowledge_source_versions`` (immutable uploaded versions with
provenance, authority, licence class, scan status, bounded preview, approval evidence and lifecycle state) and
``knowledge_index_records`` (what a version wrote to the governed vector collection). No full document text is
stored (only a bounded preview), no vector data, and nothing candidate-private. A partial unique index allows at
most one ACTIVE version per source. This migration NEVER touches Chroma or the legacy corpus. Chains from 0018.

Revision ID: 0019_knowledge_admin
Revises: 0018_jobs
Create Date: 2026-10-03
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0019_knowledge_admin"
down_revision = "0018_jobs"
branch_labels = None
depends_on = None

STATES = ("queued", "processing", "review_required", "approved", "indexing", "indexed", "active", "rejected", "failed", "retired")
LICENCES = ("public_official", "explicit_permissive", "internal_owned", "permission_recorded", "unclear", "restricted")
SCANS = ("not_scanned", "scan_passed", "scan_failed", "scan_unavailable")
LANGS = ("en", "de", "fr", "es", "it", "pt", "nl")
REASONS = ("provenance_insufficient", "licence_not_permitted", "quality_insufficient", "out_of_scope", "unsafe_content", "duplicate", "other")
INDEX_STATES = ("built", "removed", "removal_failed")


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


def _dt(name: str, nullable: bool = True) -> sa.Column:
    return sa.Column(name, sa.DateTime(timezone=True), nullable=nullable)


def upgrade() -> None:
    op.create_table(
        "knowledge_sources",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("public_id", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        _dt("created_at", False), _dt("updated_at", False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_knowledge_sources_public_id", "knowledge_sources", ["public_id"], unique=True)

    user_fk = lambda n: sa.Column(n, sa.Integer(), nullable=True)  # noqa: E731
    op.create_table(
        "knowledge_source_versions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("public_id", sa.String(length=32), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(length=20), server_default="queued", nullable=False),
        sa.Column("language", sa.String(length=2), nullable=False),
        sa.Column("authority_level", sa.Integer(), nullable=False),
        sa.Column("publisher", sa.String(length=200), server_default="", nullable=False),
        sa.Column("source_url", sa.String(length=500), nullable=True),
        sa.Column("provenance_note", sa.String(length=500), server_default="", nullable=False),
        sa.Column("licence_class", sa.String(length=24), server_default="unclear", nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("storage_key", sa.String(length=128), nullable=True),
        sa.Column("media_type", sa.String(length=64), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=False),
        sa.Column("scan_status", sa.String(length=20), server_default="not_scanned", nullable=False),
        sa.Column("scanner_name", sa.String(length=24), nullable=True),
        sa.Column("preview_text", sa.String(length=4100), nullable=True),
        sa.Column("extracted_chars", sa.Integer(), nullable=True),
        sa.Column("chunk_count", sa.Integer(), nullable=True),
        sa.Column("failed_stage", sa.String(length=8), nullable=True),
        sa.Column("failure_category", sa.String(length=24), nullable=True),
        sa.Column("parse_job_public_id", sa.String(length=32), nullable=True),
        sa.Column("index_job_public_id", sa.String(length=32), nullable=True),
        user_fk("approved_by_user_id"), _dt("approved_at"),
        user_fk("rejected_by_user_id"), _dt("rejected_at"), sa.Column("rejection_reason", sa.String(length=32), nullable=True),
        _dt("indexed_at"),
        user_fk("activated_by_user_id"), _dt("activated_at"),
        user_fk("retired_by_user_id"), _dt("retired_at"),
        user_fk("created_by_user_id"),
        _dt("created_at", False), _dt("updated_at", False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["source_id"], ["knowledge_sources.id"], ondelete="CASCADE"),
        *[sa.ForeignKeyConstraint([c], ["users.id"], ondelete="SET NULL") for c in (
            "approved_by_user_id", "rejected_by_user_id", "activated_by_user_id", "retired_by_user_id", "created_by_user_id")],
        sa.CheckConstraint(_in("state", STATES), name="ck_ksv_state"),
        sa.CheckConstraint("authority_level IN (1, 2, 3)", name="ck_ksv_authority"),
        sa.CheckConstraint(_in("language", LANGS), name="ck_ksv_language"),
        sa.CheckConstraint(_in("licence_class", LICENCES), name="ck_ksv_licence"),
        sa.CheckConstraint(_in("scan_status", SCANS), name="ck_ksv_scan"),
        sa.CheckConstraint("length(checksum_sha256) = 64", name="ck_ksv_checksum"),
        sa.CheckConstraint("version >= 1", name="ck_ksv_version"),
        sa.CheckConstraint("byte_size >= 0", name="ck_ksv_size"),
        sa.CheckConstraint("rejection_reason IS NULL OR " + _in("rejection_reason", REASONS), name="ck_ksv_rejection"),
        sa.CheckConstraint(
            "state NOT IN ('approved', 'indexing', 'indexed', 'active') "
            "OR (approved_by_user_id IS NOT NULL AND approved_at IS NOT NULL)", name="ck_ksv_approval_evidence"),
        sa.UniqueConstraint("source_id", "version", name="uq_ksv_source_version"),
        sa.UniqueConstraint("source_id", "checksum_sha256", name="uq_ksv_source_checksum"),
    )
    active = sa.text("state = 'active'")
    op.create_index("ix_knowledge_source_versions_public_id", "knowledge_source_versions", ["public_id"], unique=True)
    op.create_index("uq_ksv_one_active", "knowledge_source_versions", ["source_id"], unique=True,
                    sqlite_where=active, postgresql_where=active)
    op.create_index("ix_ksv_state", "knowledge_source_versions", ["state", "updated_at"])
    op.create_index("ix_ksv_source", "knowledge_source_versions", ["source_id", "version"])

    op.create_table(
        "knowledge_index_records",
        sa.Column("version_id", sa.Integer(), nullable=False),
        sa.Column("collection", sa.String(length=64), nullable=False),
        sa.Column("embedder", sa.String(length=64), nullable=False),
        sa.Column("chunk_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("state", sa.String(length=16), server_default="built", nullable=False),
        _dt("built_at"), _dt("removed_at"), _dt("updated_at", False),
        sa.PrimaryKeyConstraint("version_id"),
        sa.ForeignKeyConstraint(["version_id"], ["knowledge_source_versions.id"], ondelete="CASCADE"),
        sa.CheckConstraint(_in("state", INDEX_STATES), name="ck_kir_state"),
        sa.CheckConstraint("chunk_count >= 0", name="ck_kir_chunks"),
    )


def downgrade() -> None:
    op.drop_table("knowledge_index_records")
    for name in ("ix_ksv_source", "ix_ksv_state", "uq_ksv_one_active", "ix_knowledge_source_versions_public_id"):
        op.drop_index(name, table_name="knowledge_source_versions")
    op.drop_table("knowledge_source_versions")
    op.drop_index("ix_knowledge_sources_public_id", table_name="knowledge_sources")
    op.drop_table("knowledge_sources")
