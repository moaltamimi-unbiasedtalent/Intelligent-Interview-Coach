"""Global knowledge foundation (P10C-A). SCHEMA ONLY: nothing is seeded by the migration and no external dataset is ingested.

Additive. Seven tables: a governed source registry with an audited approval lifecycle (``global_sources``, ``global_source_events``), taxonomy namespace plus edition
(``occupation_taxonomies``), the canonical occupation graph (``graph_occupations``, ``graph_occupation_identifiers``, ``graph_occupation_relationships``) and the country-level
coverage matrix (``geography_coverage``). Constraints enforce the integrity rules: a synthetic fixture can never be approved, an approved source must have a verified licence,
a VERIFIED mapping must name a source-provided basis, a code is unique only within one taxonomy edition, and a relationship type is separate from its mapping status.
With the tables empty nothing changes for any candidate. Downgrade drops them (registry and graph metadata only). Chains from 0034. Single head.

Revision ID: 0035_knowledge_foundation
Revises: 0034_preparation_packs
Create Date: 2026-10-18
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0035_knowledge_foundation"
down_revision = "0034_preparation_packs"
branch_labels = None
depends_on = None


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


APPROVAL = ("discovered", "licensing_pending", "licensing_verified", "approved_for_ingestion", "approved_for_runtime_use", "restricted", "rejected", "superseded")
LICENCE = ("unknown", "stated_unverified", "verified", "conflicting")
TRI = ("unknown", "yes", "no")
ORIGIN = ("unknown", "official_local", "official_api", "authorized_api", "authorised_manual", "synthetic_fixture")
PRECEDENCE = ("unknown", "national_official_occupation_statistics", "national_public_employment_service", "eurostat_harmonised", "cedefop_intelligence", "authorized_secondary",
              "insufficient_evidence")
VALIDATION = ("unknown", "unvalidated", "engineering_draft", "human_reviewed")
SCHEMES = ("esco", "isco", "onet_soc", "soc", "uk_soc", "kldb", "noc", "sinco", "cbo")
TAX_STATUS = ("current", "historical", "deprecated", "unknown")
ACQUISITION = ("available_locally", "referenced_indirectly", "identified_externally", "not_acquired", "unverified")
OCC_STATUS = ("active", "deprecated", "superseded")
ID_STATUS = ("current", "deprecated", "unknown")
REL_TYPES = ("equivalent", "broader", "narrower", "related")
REL_BASES = ("source_provided", "curated_manual", "derived_rule")
MAPPING = ("verified", "partial", "ambiguous", "unsupported", "unknown")
QUAL = ("unqualified", "engineering_checked", "qualified")
LEVELS = ("unsupported", "targeted", "source_identified", "data_available", "implemented", "qualified")
GROUPS = ("eu27", "uk", "eea_non_eu", "switzerland", "us", "canada", "mexico", "brazil", "south_america_other")


def upgrade() -> None:
    op.create_table(
        "global_sources",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_id", sa.String(length=64), nullable=False),
        sa.Column("publisher", sa.String(length=200), nullable=True),
        sa.Column("dataset_name", sa.String(length=200), nullable=True),
        sa.Column("dataset_version", sa.String(length=64), nullable=True),
        sa.Column("source_url", sa.String(length=500), nullable=True),
        sa.Column("geographies", sa.JSON(), nullable=False),
        sa.Column("languages", sa.JSON(), nullable=False),
        sa.Column("taxonomy", sa.String(length=16), nullable=True),
        sa.Column("evidence_category", sa.String(length=40), nullable=True),
        sa.Column("publication_date", sa.String(length=32), nullable=True),
        sa.Column("reference_period", sa.String(length=64), nullable=True),
        sa.Column("update_cadence", sa.String(length=32), nullable=True),
        sa.Column("precedence_category", sa.String(length=48), server_default="unknown", nullable=False),
        sa.Column("evidence_class", sa.String(length=2), nullable=True),
        sa.Column("licence_id", sa.String(length=120), nullable=True),
        sa.Column("licence_status", sa.String(length=20), server_default="unknown", nullable=False),
        sa.Column("attribution_required", sa.String(length=8), server_default="unknown", nullable=False),
        sa.Column("redistribution", sa.String(length=8), server_default="unknown", nullable=False),
        sa.Column("origin", sa.String(length=24), server_default="unknown", nullable=False),
        sa.Column("approval_status", sa.String(length=32), server_default="discovered", nullable=False),
        sa.Column("operational_status", sa.String(length=32), server_default="unknown", nullable=False),
        sa.Column("validation_status", sa.String(length=20), server_default="unknown", nullable=False),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=True),
        sa.Column("provenance", sa.JSON(), nullable=False),
        sa.Column("superseded_by", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_id", name="uq_global_source_id"),
        sa.CheckConstraint(_in("approval_status", APPROVAL), name="ck_gs_approval"),
        sa.CheckConstraint(_in("licence_status", LICENCE), name="ck_gs_licence_status"),
        sa.CheckConstraint(_in("attribution_required", TRI), name="ck_gs_attribution"),
        sa.CheckConstraint(_in("redistribution", TRI), name="ck_gs_redistribution"),
        sa.CheckConstraint(_in("origin", ORIGIN), name="ck_gs_origin"),
        sa.CheckConstraint(_in("precedence_category", PRECEDENCE), name="ck_gs_precedence"),
        sa.CheckConstraint(_in("validation_status", VALIDATION), name="ck_gs_validation"),
        sa.CheckConstraint("evidence_class IS NULL OR evidence_class IN ('C1', 'C2', 'C3')", name="ck_gs_evidence_class"),
        sa.CheckConstraint("origin <> 'synthetic_fixture' OR approval_status NOT IN ('approved_for_ingestion', 'approved_for_runtime_use')", name="ck_gs_synthetic_never_approved"),
        sa.CheckConstraint("approval_status NOT IN ('approved_for_ingestion', 'approved_for_runtime_use') OR licence_status = 'verified'", name="ck_gs_approval_needs_licence"),
    )
    op.create_table(
        "global_source_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_row_id", sa.Integer(), nullable=False),
        sa.Column("from_status", sa.String(length=32), nullable=True),
        sa.Column("to_status", sa.String(length=32), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("reason", sa.String(length=300), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["source_row_id"], ["global_sources.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(_in("to_status", APPROVAL), name="ck_gse_to_status"),
    )
    op.create_index("ix_global_source_events_source_row_id", "global_source_events", ["source_row_id"])
    op.create_table(
        "occupation_taxonomies",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("scheme", sa.String(length=16), nullable=False),
        sa.Column("edition", sa.String(length=32), server_default="unknown", nullable=False),
        sa.Column("label", sa.String(length=200), nullable=True),
        sa.Column("status", sa.String(length=16), server_default="unknown", nullable=False),
        sa.Column("acquisition_status", sa.String(length=24), server_default="not_acquired", nullable=False),
        sa.Column("code_pattern", sa.String(length=120), nullable=True),
        sa.Column("geographies", sa.JSON(), nullable=False),
        sa.Column("source_row_id", sa.Integer(), nullable=True),
        sa.Column("superseded_by_id", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["source_row_id"], ["global_sources.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["superseded_by_id"], ["occupation_taxonomies.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("scheme", "edition", name="uq_occupation_taxonomy"),
        sa.CheckConstraint(_in("scheme", SCHEMES), name="ck_ot_scheme"),
        sa.CheckConstraint(_in("status", TAX_STATUS), name="ck_ot_status"),
        sa.CheckConstraint(_in("acquisition_status", ACQUISITION), name="ck_ot_acquisition"),
    )
    op.create_table(
        "graph_occupations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("occupation_key", sa.String(length=64), nullable=False),
        sa.Column("canonical_label", sa.String(length=300), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="active", nullable=False),
        sa.Column("legacy_keys", sa.JSON(), nullable=False),
        sa.Column("superseded_by_key", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("occupation_key", name="uq_graph_occupation_key"),
        sa.CheckConstraint(_in("status", OCC_STATUS), name="ck_go_status"),
    )
    op.create_table(
        "graph_occupation_identifiers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("occupation_id", sa.Integer(), nullable=False),
        sa.Column("taxonomy_id", sa.Integer(), nullable=False),
        sa.Column("native_code", sa.String(length=64), nullable=False),
        sa.Column("native_label", sa.String(length=300), nullable=True),
        sa.Column("status", sa.String(length=12), server_default="current", nullable=False),
        sa.Column("source_ref", sa.String(length=64), server_default="", nullable=False),
        sa.Column("provenance", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["occupation_id"], ["graph_occupations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["taxonomy_id"], ["occupation_taxonomies.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("taxonomy_id", "native_code", name="uq_graph_identifier"),
        sa.CheckConstraint(_in("status", ID_STATUS), name="ck_gi_status"),
    )
    op.create_index("ix_graph_identifier_occupation", "graph_occupation_identifiers", ["occupation_id"])
    op.create_table(
        "graph_occupation_relationships",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("from_occupation_id", sa.Integer(), nullable=False),
        sa.Column("to_occupation_id", sa.Integer(), nullable=False),
        sa.Column("from_taxonomy_id", sa.Integer(), nullable=False),
        sa.Column("to_taxonomy_id", sa.Integer(), nullable=False),
        sa.Column("relationship_type", sa.String(length=12), nullable=False),
        sa.Column("basis", sa.String(length=16), nullable=False),
        sa.Column("mapping_status", sa.String(length=12), server_default="unknown", nullable=False),
        sa.Column("qualification_status", sa.String(length=20), server_default="unqualified", nullable=False),
        sa.Column("source_ref", sa.String(length=64), server_default="", nullable=False),
        sa.Column("limitations", sa.Text(), nullable=True),
        sa.Column("superseded", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["from_occupation_id"], ["graph_occupations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["to_occupation_id"], ["graph_occupations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["from_taxonomy_id"], ["occupation_taxonomies.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["to_taxonomy_id"], ["occupation_taxonomies.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("from_occupation_id", "to_occupation_id", "relationship_type", "source_ref", name="uq_graph_relationship"),
        sa.CheckConstraint(_in("relationship_type", REL_TYPES), name="ck_gr_type"),
        sa.CheckConstraint(_in("basis", REL_BASES), name="ck_gr_basis"),
        sa.CheckConstraint(_in("mapping_status", MAPPING), name="ck_gr_status"),
        sa.CheckConstraint(_in("qualification_status", QUAL), name="ck_gr_qualification"),
        sa.CheckConstraint("from_occupation_id <> to_occupation_id", name="ck_gr_not_self"),
        sa.CheckConstraint("mapping_status <> 'verified' OR (source_ref <> '' AND basis = 'source_provided')", name="ck_gr_verified_needs_source"),
    )
    op.create_index("ix_graph_relationship_to", "graph_occupation_relationships", ["to_occupation_id"])
    op.create_table(
        "geography_coverage",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("geography_code", sa.String(length=8), nullable=False),
        sa.Column("label", sa.String(length=80), nullable=False),
        sa.Column("coverage_group", sa.String(length=24), nullable=False),
        sa.Column("taxonomy_level", sa.String(length=16), server_default="targeted", nullable=False),
        sa.Column("crosswalk_level", sa.String(length=16), server_default="targeted", nullable=False),
        sa.Column("compensation_level", sa.String(length=16), server_default="targeted", nullable=False),
        sa.Column("outlook_level", sa.String(length=16), server_default="targeted", nullable=False),
        sa.Column("source_languages", sa.JSON(), nullable=False),
        sa.Column("source_ids", sa.JSON(), nullable=False),
        sa.Column("limitations", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("geography_code", name="uq_geography_coverage_code"),
        sa.CheckConstraint(_in("coverage_group", GROUPS), name="ck_gc_group"),
        sa.CheckConstraint(_in("taxonomy_level", LEVELS), name="ck_gc_taxonomy"),
        sa.CheckConstraint(_in("crosswalk_level", LEVELS), name="ck_gc_crosswalk"),
        sa.CheckConstraint(_in("compensation_level", LEVELS), name="ck_gc_compensation"),
        sa.CheckConstraint(_in("outlook_level", LEVELS), name="ck_gc_outlook"),
    )


def downgrade() -> None:
    op.drop_table("geography_coverage")
    op.drop_index("ix_graph_relationship_to", table_name="graph_occupation_relationships")
    op.drop_table("graph_occupation_relationships")
    op.drop_index("ix_graph_identifier_occupation", table_name="graph_occupation_identifiers")
    op.drop_table("graph_occupation_identifiers")
    op.drop_table("graph_occupations")
    op.drop_table("occupation_taxonomies")
    op.drop_index("ix_global_source_events_source_row_id", table_name="global_source_events")
    op.drop_table("global_source_events")
    op.drop_table("global_sources")
