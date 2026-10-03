"""Privacy requests, preparation-run ownership index, legal documents/versions and acceptances (P10B-W10.10).

Additive. ``privacy_requests`` (durable queue; closes SEC-W10-04), ``preparation_runs`` (ownership/lifecycle index with NO chat
content and no FK to users, closes PRIV-W9-01 together with the application changes), ``legal_documents`` /
``legal_document_versions`` / ``legal_acceptances`` (closes PRIV-W9-02). No IP, device or fingerprint column exists anywhere.

Seeding is relational only: the three legal document identities and ONE ``baseline-1`` published version each, marked as a
baseline because VERSIONING WAS INTRODUCED HERE (effective date unrecorded, no content hash). NO acceptance is back-filled and no
timestamp is fabricated. This migration never scans or touches the agent checkpoint store: historical preparation runs are
indexed afterwards by a bounded job. Chains from 0019. Single head.

Revision ID: 0020_privacy_legal_admin
Revises: 0019_knowledge_admin
Create Date: 2026-10-03
"""

from __future__ import annotations

from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op

revision = "0020_privacy_legal_admin"
down_revision = "0019_knowledge_admin"
branch_labels = None
depends_on = None

TYPES = ("data_access", "deletion", "correction", "consent_question", "other_privacy")
STATUSES = ("submitted", "acknowledged", "in_progress", "waiting_for_user", "completed", "closed", "rejected")
RESULTS = ("export_provided", "deletion_performed", "correction_made", "information_provided", "no_action_required", "unable_to_verify")
SOURCES = ("candidate_portal", "admin_recorded")
RUN_STATES = ("started", "ready", "failed", "purge_failed")
RUN_SOURCES = ("created", "backfill", "lazy")
DOCS = (("terms", "Terms of use", "/terms"), ("privacy", "Privacy notice", "/privacy"), ("ai_transparency", "AI transparency", "/ai-transparency"))
VERSION_STATES = ("draft", "published", "retired")
ACCEPT_SOURCES = ("signup", "settings", "reacceptance")


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


def _dt(name: str, nullable: bool = True) -> sa.Column:
    return sa.Column(name, sa.DateTime(timezone=True), nullable=nullable)


def upgrade() -> None:
    op.create_table(
        "privacy_requests",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("public_id", sa.String(length=32), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("subject_user_id", sa.Integer(), nullable=True),
        sa.Column("request_type", sa.String(length=24), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="submitted", nullable=False),
        sa.Column("source", sa.String(length=20), server_default="candidate_portal", nullable=False),
        sa.Column("request_note", sa.String(length=1000), nullable=True),
        sa.Column("assigned_user_id", sa.Integer(), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("result_category", sa.String(length=24), nullable=True),
        sa.Column("related_job_public_id", sa.String(length=32), nullable=True),
        _dt("created_at", False), _dt("acknowledged_at"), _dt("completed_at"), _dt("closed_at"), _dt("updated_at", False),
        sa.PrimaryKeyConstraint("id"),
        *[sa.ForeignKeyConstraint([c], ["users.id"], ondelete="SET NULL") for c in ("user_id", "assigned_user_id", "created_by_user_id")],
        sa.CheckConstraint(_in("request_type", TYPES), name="ck_privacy_requests_type"),
        sa.CheckConstraint(_in("status", STATUSES), name="ck_privacy_requests_status"),
        sa.CheckConstraint(_in("source", SOURCES), name="ck_privacy_requests_source"),
        sa.CheckConstraint("result_category IS NULL OR " + _in("result_category", RESULTS), name="ck_privacy_requests_result"),
        sa.CheckConstraint("status <> 'completed' OR (result_category IS NOT NULL AND completed_at IS NOT NULL)",
                           name="ck_privacy_requests_completed_evidence"),
    )
    op.create_index("ix_privacy_requests_public_id", "privacy_requests", ["public_id"], unique=True)
    op.create_index("ix_privacy_requests_status_created", "privacy_requests", ["status", "created_at"])
    op.create_index("ix_privacy_requests_user", "privacy_requests", ["user_id"])
    op.create_index("ix_privacy_requests_assignee_status", "privacy_requests", ["assigned_user_id", "status"])
    op.create_index("ix_privacy_requests_type", "privacy_requests", ["request_type"])

    op.create_table(
        "preparation_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(length=16), server_default="started", nullable=False),
        sa.Column("source", sa.String(length=12), server_default="created", nullable=False),
        sa.Column("coverage_version", sa.Integer(), server_default="1", nullable=False),
        _dt("created_at", False), _dt("updated_at", False),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(_in("state", RUN_STATES), name="ck_preparation_runs_state"),
        sa.CheckConstraint(_in("source", RUN_SOURCES), name="ck_preparation_runs_source"),
        sa.CheckConstraint("coverage_version >= 1", name="ck_preparation_runs_coverage"),
    )
    op.create_index("ix_preparation_runs_run_id", "preparation_runs", ["run_id"], unique=True)
    op.create_index("ix_preparation_runs_owner_state", "preparation_runs", ["owner_user_id", "state"])

    op.create_table(
        "legal_documents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=24), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        _dt("created_at", False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
        sa.CheckConstraint(_in("code", tuple(d[0] for d in DOCS)), name="ck_legal_documents_code"),
    )
    op.create_table(
        "legal_document_versions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("version", sa.String(length=32), nullable=False),
        sa.Column("state", sa.String(length=12), server_default="draft", nullable=False),
        sa.Column("is_baseline", sa.Boolean(), server_default="0", nullable=False),
        sa.Column("content_ref", sa.String(length=300), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=True),
        _dt("effective_at"), _dt("published_at"),
        sa.Column("published_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        _dt("created_at", False), _dt("updated_at", False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["document_id"], ["legal_documents.id"]),
        sa.ForeignKeyConstraint(["published_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.CheckConstraint(_in("state", VERSION_STATES), name="ck_ldv_state"),
        sa.CheckConstraint("content_hash IS NULL OR length(content_hash) = 64", name="ck_ldv_hash"),
        sa.CheckConstraint("state = 'draft' OR published_at IS NOT NULL", name="ck_ldv_published_at"),
        sa.CheckConstraint("state <> 'published' OR is_baseline = 1 OR content_hash IS NOT NULL", name="ck_ldv_published_hash"),
        sa.UniqueConstraint("document_id", "version", name="uq_ldv_document_version"),
    )
    published = sa.text("state = 'published'")
    op.create_index("uq_ldv_one_published", "legal_document_versions", ["document_id"], unique=True,
                    sqlite_where=published, postgresql_where=published)
    op.create_table(
        "legal_acceptances",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("version_id", sa.Integer(), nullable=False),
        _dt("accepted_at", False),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["version_id"], ["legal_document_versions.id"]),
        sa.CheckConstraint(_in("source", ACCEPT_SOURCES), name="ck_legal_acceptances_source"),
        sa.UniqueConstraint("user_id", "version_id", name="uq_legal_acceptance_user_version"),
    )
    op.create_index("ix_legal_acceptances_version", "legal_acceptances", ["version_id"])

    # Relational seed only: document identities + one baseline version each. No acceptance rows, no invented dates.
    now = datetime.now(timezone.utc)
    docs = sa.table("legal_documents", sa.column("code"), sa.column("title"), sa.column("created_at"))
    op.bulk_insert(docs, [{"code": c, "title": t, "created_at": now} for c, t, _ in DOCS])
    conn = op.get_bind()
    ids = {row[1]: row[0] for row in conn.execute(sa.text("SELECT id, code FROM legal_documents"))}
    versions = sa.table("legal_document_versions", sa.column("document_id"), sa.column("version"), sa.column("state"),
                        sa.column("is_baseline"), sa.column("content_ref"), sa.column("published_at"),
                        sa.column("created_at"), sa.column("updated_at"))
    op.bulk_insert(versions, [{"document_id": ids[c], "version": "baseline-1", "state": "published", "is_baseline": True,
                               "content_ref": ref, "published_at": now, "created_at": now, "updated_at": now} for c, _, ref in DOCS])


def downgrade() -> None:
    op.drop_index("ix_legal_acceptances_version", table_name="legal_acceptances")
    op.drop_table("legal_acceptances")
    op.drop_index("uq_ldv_one_published", table_name="legal_document_versions")
    op.drop_table("legal_document_versions")
    op.drop_table("legal_documents")
    op.drop_index("ix_preparation_runs_owner_state", table_name="preparation_runs")
    op.drop_index("ix_preparation_runs_run_id", table_name="preparation_runs")
    op.drop_table("preparation_runs")
    for name in ("ix_privacy_requests_type", "ix_privacy_requests_assignee_status", "ix_privacy_requests_user",
                 "ix_privacy_requests_status_created", "ix_privacy_requests_public_id"):
        op.drop_index(name, table_name="privacy_requests")
    op.drop_table("privacy_requests")
