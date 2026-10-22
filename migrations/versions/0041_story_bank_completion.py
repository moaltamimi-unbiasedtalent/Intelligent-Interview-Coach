"""Story Bank completion (package 04A, REQ-OWN-06). Additive and data-preserving.

Adds, and changes nothing else:
- ``candidate_stories.archived_at`` (reversible archive), ``candidate_stories.opportunity_id`` (optional link to the candidate's own Opportunity; plain column and
  index on SQLite, FK ON DELETE SET NULL elsewhere, the application also unlinks explicitly) and ``candidate_stories.confirmed_at`` (the candidate's own
  "I confirm this is accurate" timestamp, a self-attestation that is never presented as evidence). All nullable; every existing row stays valid and unchanged.
- table ``story_answer_links`` (a story referenced to one of the candidate's own practice answers; a reference only, no answer text).
- table ``story_uses`` (ids only: which story the candidate explicitly chose for which Practice session; used for attribution and so that deleting a story can
  find and strip the text it copied into a session).

Why a migration is genuinely needed: archive, the Opportunity link, self-confirmation, answer evidence and use attribution have no existing column or table, and
packing them into the ``competencies`` JSON would be neither queryable nor honest. The privacy-schema evaluator allows this file (and only this file, only these
tables) through an explicit reviewed exception, see ``scripts/eval_privacy_controls.py``.

The downgrade is FAIL-CLOSED: it refuses (deleting nothing) while any story is archived, linked to an Opportunity or confirmed, or any answer link or use row exists,
because dropping those columns and tables would destroy candidate-authored state. Un-archive, unlink and remove those deliberately first.

Revision ID: 0041_story_bank_completion
Revises: 0040_knowledge_alert_categories
Create Date: 2026-10-22
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0041_story_bank_completion"
down_revision = "0040_knowledge_alert_categories"
branch_labels = None
depends_on = None


def upgrade() -> None:
    is_sqlite = op.get_bind().dialect.name == "sqlite"
    op.add_column("candidate_stories", sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("candidate_stories", sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("candidate_stories", sa.Column("opportunity_id", sa.Integer(), nullable=True))
    op.create_index("ix_candidate_stories_opportunity_id", "candidate_stories", ["opportunity_id"])
    if not is_sqlite:
        op.create_foreign_key("fk_candidate_stories_opportunity", "candidate_stories", "opportunities", ["opportunity_id"], ["id"], ondelete="SET NULL")

    op.create_table(
        "story_answer_links",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("story_id", sa.Integer(), nullable=False),
        sa.Column("answer_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["story_id"], ["candidate_stories.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["answer_id"], ["answers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("story_id", "answer_id", name="uq_story_answer_link"),
    )
    op.create_index("ix_story_answer_links_story_id", "story_answer_links", ["story_id"])
    op.create_index("ix_story_answer_links_answer_id", "story_answer_links", ["answer_id"])

    op.create_table(
        "story_uses",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("story_id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["story_id"], ["candidate_stories.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_story_uses_user_id", "story_uses", ["user_id"])
    op.create_index("ix_story_uses_story_id", "story_uses", ["story_id"])


def _count(bind, sql: str) -> int:
    return int(bind.execute(sa.text(sql)).scalar() or 0)


def downgrade() -> None:
    """FAIL CLOSED: refuses (deleting nothing) while the new columns or tables hold candidate-authored state."""
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"
    held = {
        "archived or confirmed or Opportunity-linked stories": _count(
            bind, "SELECT COUNT(*) FROM candidate_stories WHERE archived_at IS NOT NULL OR confirmed_at IS NOT NULL OR opportunity_id IS NOT NULL"),
        "story answer links": _count(bind, "SELECT COUNT(*) FROM story_answer_links"),
        "story use records": _count(bind, "SELECT COUNT(*) FROM story_uses"),
    }
    blocking = {k: v for k, v in held.items() if v}
    if blocking:
        raise RuntimeError(f"Refusing to downgrade 0041_story_bank_completion: candidate-authored state exists ({blocking}). Remove or reset it deliberately first.")
    op.drop_index("ix_story_uses_story_id", table_name="story_uses")
    op.drop_index("ix_story_uses_user_id", table_name="story_uses")
    op.drop_table("story_uses")
    op.drop_index("ix_story_answer_links_answer_id", table_name="story_answer_links")
    op.drop_index("ix_story_answer_links_story_id", table_name="story_answer_links")
    op.drop_table("story_answer_links")
    if not is_sqlite:
        op.drop_constraint("fk_candidate_stories_opportunity", "candidate_stories", type_="foreignkey")
    op.drop_index("ix_candidate_stories_opportunity_id", table_name="candidate_stories")
    op.drop_column("candidate_stories", "opportunity_id")
    op.drop_column("candidate_stories", "confirmed_at")
    op.drop_column("candidate_stories", "archived_at")
