"""Multilingual occupation aliases and language coverage (P10C-B). SCHEMA ONLY: nothing is seeded by the migration, no alias or translation is shipped, and no external dataset is
ingested.

Additive. Two tables on top of the P10C-A graph: ``graph_occupation_aliases`` (language-aware, provenance-bearing labels of a canonical occupation; the original text is preserved,
uniqueness never forces distinct occupations to merge, an unknown language carries an unknown basis, an official alias type requires a source) and ``language_coverage`` (language
coverage reported separately from country coverage). With the tables empty nothing changes for any candidate. Downgrade drops them (alias and coverage metadata only; P10C-A
tables and the legacy knowledge stores are untouched). Chains from 0035. Single head.

Revision ID: 0036_multilingual_aliases
Revises: 0035_knowledge_foundation
Create Date: 2026-10-18
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0036_multilingual_aliases"
down_revision = "0035_knowledge_foundation"
branch_labels = None
depends_on = None


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


ALIAS_TYPES = ("official_preferred", "official_alternative", "source_synonym", "recognized_title", "legacy_alias", "unknown")
LANGUAGE_BASES = ("unknown", "source_declared", "source_file", "fixture_declared", "curated_manual")
QUAL = ("unqualified", "engineering_checked", "qualified")
ALIAS_STATUS = ("current", "deprecated", "superseded")
LEVELS = ("unsupported", "targeted", "source_identified", "data_available", "implemented", "qualified")


def upgrade() -> None:
    op.create_table(
        "graph_occupation_aliases",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("occupation_id", sa.Integer(), nullable=False),
        sa.Column("alias_text", sa.String(length=300), nullable=False),
        sa.Column("normalized_text", sa.String(length=300), nullable=False),
        sa.Column("folded_text", sa.String(length=300), nullable=False),
        sa.Column("normalization_version", sa.String(length=16), nullable=False),
        sa.Column("language", sa.String(length=16), server_default="und", nullable=False),
        sa.Column("language_basis", sa.String(length=20), server_default="unknown", nullable=False),
        sa.Column("script", sa.String(length=16), nullable=True),
        sa.Column("alias_type", sa.String(length=24), server_default="unknown", nullable=False),
        sa.Column("source_ref", sa.String(length=64), server_default="", nullable=False),
        sa.Column("taxonomy_id", sa.Integer(), nullable=True),
        sa.Column("edition_ref", sa.String(length=64), server_default="", nullable=False),
        sa.Column("qualification_status", sa.String(length=20), server_default="unqualified", nullable=False),
        sa.Column("status", sa.String(length=12), server_default="current", nullable=False),
        sa.Column("context_terms", sa.JSON(), nullable=False),
        sa.Column("provenance", sa.JSON(), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("valid_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["occupation_id"], ["graph_occupations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["taxonomy_id"], ["occupation_taxonomies.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("occupation_id", "normalized_text", "language", "alias_type", "source_ref", "edition_ref", name="uq_graph_alias"),
        sa.CheckConstraint(_in("alias_type", ALIAS_TYPES), name="ck_ga_type"),
        sa.CheckConstraint(_in("language_basis", LANGUAGE_BASES), name="ck_ga_language_basis"),
        sa.CheckConstraint(_in("qualification_status", QUAL), name="ck_ga_qualification"),
        sa.CheckConstraint(_in("status", ALIAS_STATUS), name="ck_ga_status"),
        sa.CheckConstraint("(language = 'und' AND language_basis = 'unknown') OR (language <> 'und' AND language_basis <> 'unknown')", name="ck_ga_language_evidence"),
        sa.CheckConstraint("alias_type NOT IN ('official_preferred', 'official_alternative') OR source_ref <> ''", name="ck_ga_official_needs_source"),
    )
    op.create_index("ix_graph_alias_normalized", "graph_occupation_aliases", ["normalized_text", "language"])
    op.create_index("ix_graph_alias_folded", "graph_occupation_aliases", ["folded_text"])
    op.create_index("ix_graph_alias_occupation", "graph_occupation_aliases", ["occupation_id"])

    op.create_table(
        "language_coverage",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("language", sa.String(length=16), nullable=False),
        sa.Column("label", sa.String(length=60), nullable=False),
        sa.Column("ui_supported", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("taxonomy_level", sa.String(length=16), server_default="targeted", nullable=False),
        sa.Column("alias_data_level", sa.String(length=16), server_default="targeted", nullable=False),
        sa.Column("alias_qualified", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("resolver_level", sa.String(length=16), server_default="targeted", nullable=False),
        sa.Column("source_ids", sa.JSON(), nullable=False),
        sa.Column("limitations", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("language", name="uq_language_coverage_language"),
        sa.CheckConstraint(_in("taxonomy_level", LEVELS), name="ck_lc_taxonomy"),
        sa.CheckConstraint(_in("alias_data_level", LEVELS), name="ck_lc_alias_data"),
        sa.CheckConstraint(_in("resolver_level", LEVELS), name="ck_lc_resolver"),
    )


def downgrade() -> None:
    op.drop_table("language_coverage")
    op.drop_index("ix_graph_alias_occupation", table_name="graph_occupation_aliases")
    op.drop_index("ix_graph_alias_folded", table_name="graph_occupation_aliases")
    op.drop_index("ix_graph_alias_normalized", table_name="graph_occupation_aliases")
    op.drop_table("graph_occupation_aliases")
