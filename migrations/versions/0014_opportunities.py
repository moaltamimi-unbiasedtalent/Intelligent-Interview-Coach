"""Candidate Opportunity model (P10B Wave 6).

Additive and backward-compatible. Introduces the missing candidate-preparation domain concept:
an **Opportunity** = one specific job a candidate is preparing for (role + company + optional JD),
the organising home for Company Intelligence, Prepare, Practice, reports and progress. It is
owner-scoped and private by default; it is DISTINCT from a Workspace (collaboration/sharing) and
never auto-creates one.

Adds:
- table `opportunities` (owner-scoped; FK users.id ON DELETE CASCADE; optional JD FK to
  candidate_documents ON DELETE SET NULL so a deleted JD never leaves inaccessible content).
- `interviews.opportunity_id` and `interview_sessions.opportunity_id` — nullable FKs
  (ON DELETE SET NULL) so completed history and in-progress sessions reference an Opportunity
  OPTIONALLY. Existing standalone/legacy rows stay valid with a NULL link; NO data is moved,
  fabricated or destroyed. Chains from 0013. Single head.

Revision ID: 0014_opportunities
Revises: 0013_onboarding_personalisation
Create Date: 2026-09-27
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0014_opportunities"
down_revision = "0013_onboarding_personalisation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "opportunities",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("target_role", sa.String(length=200), nullable=False, server_default=""),
        sa.Column("company_name", sa.String(length=200), nullable=True),
        sa.Column("company_location", sa.String(length=200), nullable=True),
        sa.Column("company_country", sa.String(length=2), nullable=True),
        sa.Column("company_domain", sa.String(length=500), nullable=True),
        sa.Column("job_description_document_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="active"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["job_description_document_id"], ["candidate_documents.id"],
                                ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_opportunities_user_id", "opportunities", ["user_id"])
    op.create_index("ix_opportunities_user_status", "opportunities", ["user_id", "status"])
    op.create_index("ix_opportunities_jd_doc", "opportunities",
                    ["job_description_document_id"])

    # Add the optional link columns. On SQLite an FK cannot be added to an existing table via
    # ALTER (no batch mode is used in this project); the column + index are added and the FK is
    # created only on databases that support it (e.g. PostgreSQL). Fresh schemas built from the
    # ORM (`Base.metadata.create_all`) carry the FK inline. Values are always nullable.
    is_sqlite = op.get_bind().dialect.name == "sqlite"

    op.add_column("interviews", sa.Column("opportunity_id", sa.Integer(), nullable=True))
    op.create_index("ix_interviews_opportunity_id", "interviews", ["opportunity_id"])
    if not is_sqlite:
        op.create_foreign_key("fk_interviews_opportunity", "interviews", "opportunities",
                              ["opportunity_id"], ["id"], ondelete="SET NULL")

    op.add_column("interview_sessions", sa.Column("opportunity_id", sa.Integer(), nullable=True))
    op.create_index("ix_interview_sessions_opportunity_id", "interview_sessions",
                    ["opportunity_id"])
    if not is_sqlite:
        op.create_foreign_key("fk_interview_sessions_opportunity", "interview_sessions",
                              "opportunities", ["opportunity_id"], ["id"], ondelete="SET NULL")


def downgrade() -> None:
    is_sqlite = op.get_bind().dialect.name == "sqlite"

    if not is_sqlite:
        op.drop_constraint("fk_interview_sessions_opportunity", "interview_sessions",
                           type_="foreignkey")
    op.drop_index("ix_interview_sessions_opportunity_id", table_name="interview_sessions")
    op.drop_column("interview_sessions", "opportunity_id")

    if not is_sqlite:
        op.drop_constraint("fk_interviews_opportunity", "interviews", type_="foreignkey")
    op.drop_index("ix_interviews_opportunity_id", table_name="interviews")
    op.drop_column("interviews", "opportunity_id")

    op.drop_index("ix_opportunities_jd_doc", table_name="opportunities")
    op.drop_index("ix_opportunities_user_status", table_name="opportunities")
    op.drop_index("ix_opportunities_user_id", table_name="opportunities")
    op.drop_table("opportunities")
