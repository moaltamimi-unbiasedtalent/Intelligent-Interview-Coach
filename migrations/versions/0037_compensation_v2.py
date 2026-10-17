"""Compensation V2 foundation (P10C-C). SCHEMA ONLY: nothing is seeded by the migration, no compensation value is shipped and no external dataset is ingested.

Additive. Two tables BESIDE the V1 compensation store (which is a gitignored SQLite file and is untouched): ``compensation_import_batches`` (audit of each import) and
``compensation_v2_records`` (source-referenced measurements linked to canonical occupations). Money is stored as exact scaled integers; a reported value must be positive and a missing
value is NULL with an explicit status (never zero); a percentile is only valid for the percentile measure; every row names its source and edition. With the tables empty nothing changes
for any candidate. Downgrade drops them (V2 evidence only; P10C-A/B tables and every V1 store are untouched). Chains from 0036. Single head.

Revision ID: 0037_compensation_v2
Revises: 0036_multilingual_aliases
Create Date: 2026-10-18
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0037_compensation_v2"
down_revision = "0036_multilingual_aliases"
branch_labels = None
depends_on = None


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


PERIODS = ("hourly", "daily", "weekly", "monthly", "annual")
BASES = ("gross", "net", "unknown")
MEASURES = ("median", "mean", "percentile", "unknown")
VALUE_STATUS = ("reported", "suppressed", "not_available")
OCC_LEVELS = ("detailed", "broad", "unknown")
GEO_LEVELS = ("national", "regional", "eu_aggregate", "unknown")
LINKS = ("native_code_exact", "verified_crosswalk", "curated_manual")
CLASSES = ("C1", "C2", "C3")
QUAL = ("unqualified", "engineering_checked", "qualified")
REC_STATUS = ("current", "superseded")
MODES = ("production", "fixture")


def upgrade() -> None:
    op.create_table(
        "compensation_import_batches",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("batch_key", sa.String(length=64), nullable=False),
        sa.Column("source_ref", sa.String(length=64), nullable=False),
        sa.Column("source_edition", sa.String(length=64), nullable=False),
        sa.Column("mode", sa.String(length=12), nullable=False),
        sa.Column("records_added", sa.Integer(), server_default="0", nullable=False),
        sa.Column("records_existing", sa.Integer(), server_default="0", nullable=False),
        sa.Column("rows_rejected", sa.Integer(), server_default="0", nullable=False),
        sa.Column("rejection_summary", sa.JSON(), nullable=False),
        sa.Column("transformation", sa.String(length=300), nullable=True),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("batch_key", name="uq_comp_import_batch_key"),
        sa.CheckConstraint(_in("mode", MODES), name="ck_cib_mode"),
    )
    op.create_table(
        "compensation_v2_records",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("record_key", sa.String(length=64), nullable=False),
        sa.Column("occupation_id", sa.Integer(), nullable=False),
        sa.Column("taxonomy_id", sa.Integer(), nullable=False),
        sa.Column("native_code", sa.String(length=64), nullable=False),
        sa.Column("occupation_level", sa.String(length=10), server_default="unknown", nullable=False),
        sa.Column("link_basis", sa.String(length=24), server_default="native_code_exact", nullable=False),
        sa.Column("country", sa.String(length=8), nullable=False),
        sa.Column("region_key", sa.String(length=80), server_default="", nullable=False),
        sa.Column("geography_level", sa.String(length=14), server_default="unknown", nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("pay_period", sa.String(length=10), nullable=False),
        sa.Column("pay_basis", sa.String(length=10), server_default="unknown", nullable=False),
        sa.Column("measure", sa.String(length=12), server_default="unknown", nullable=False),
        sa.Column("percentile", sa.Integer(), server_default="0", nullable=False),
        sa.Column("value_status", sa.String(length=14), server_default="reported", nullable=False),
        sa.Column("amount_scale", sa.Integer(), server_default="0", nullable=False),
        sa.Column("value_units", sa.BigInteger(), nullable=True),
        sa.Column("lower_units", sa.BigInteger(), nullable=True),
        sa.Column("upper_units", sa.BigInteger(), nullable=True),
        sa.Column("bounds_semantic", sa.String(length=24), server_default="unknown", nullable=False),
        sa.Column("source_ref", sa.String(length=64), nullable=False),
        sa.Column("source_edition", sa.String(length=64), nullable=False),
        sa.Column("publisher", sa.String(length=200), nullable=True),
        sa.Column("dataset_name", sa.String(length=200), nullable=True),
        sa.Column("source_url", sa.String(length=500), nullable=True),
        sa.Column("reference_year", sa.Integer(), nullable=False),
        sa.Column("reference_period", sa.String(length=32), nullable=True),
        sa.Column("publication_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("data_vintage", sa.String(length=32), server_default="", nullable=False),
        sa.Column("evidence_class", sa.String(length=2), nullable=False),
        sa.Column("precedence_category", sa.String(length=40), nullable=False),
        sa.Column("qualification_status", sa.String(length=20), server_default="unqualified", nullable=False),
        sa.Column("status", sa.String(length=12), server_default="current", nullable=False),
        sa.Column("limitations", sa.Text(), nullable=True),
        sa.Column("provenance", sa.JSON(), nullable=False),
        sa.Column("batch_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["occupation_id"], ["graph_occupations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["taxonomy_id"], ["occupation_taxonomies.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["batch_id"], ["compensation_import_batches.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("record_key", name="uq_comp_v2_record_key"),
        sa.UniqueConstraint("source_ref", "source_edition", "taxonomy_id", "native_code", "country", "region_key", "reference_year", "pay_period", "currency", "pay_basis", "measure",
                            "percentile", "data_vintage", name="uq_comp_v2_natural_key"),
        sa.CheckConstraint("length(currency) = 3", name="ck_cv2_currency"),
        sa.CheckConstraint(_in("pay_period", PERIODS), name="ck_cv2_pay_period"),
        sa.CheckConstraint(_in("pay_basis", BASES), name="ck_cv2_pay_basis"),
        sa.CheckConstraint(_in("measure", MEASURES), name="ck_cv2_measure"),
        sa.CheckConstraint(_in("value_status", VALUE_STATUS), name="ck_cv2_value_status"),
        sa.CheckConstraint(_in("occupation_level", OCC_LEVELS), name="ck_cv2_occ_level"),
        sa.CheckConstraint(_in("geography_level", GEO_LEVELS), name="ck_cv2_geo_level"),
        sa.CheckConstraint(_in("link_basis", LINKS), name="ck_cv2_link_basis"),
        sa.CheckConstraint(_in("evidence_class", CLASSES), name="ck_cv2_evidence_class"),
        sa.CheckConstraint(_in("qualification_status", QUAL), name="ck_cv2_qualification"),
        sa.CheckConstraint(_in("status", REC_STATUS), name="ck_cv2_status"),
        sa.CheckConstraint("amount_scale >= 0 AND amount_scale <= 6", name="ck_cv2_scale"),
        sa.CheckConstraint("(value_status = 'reported' AND value_units IS NOT NULL AND value_units > 0) OR (value_status <> 'reported' AND value_units IS NULL)",
                           name="ck_cv2_value_not_zero_or_invented"),
        sa.CheckConstraint("(lower_units IS NULL AND upper_units IS NULL) OR (lower_units IS NOT NULL AND upper_units IS NOT NULL AND lower_units > 0 AND upper_units >= lower_units)", name="ck_cv2_bounds"),
        sa.CheckConstraint("(measure = 'percentile' AND percentile > 0 AND percentile < 100) OR (measure <> 'percentile' AND percentile = 0)", name="ck_cv2_percentile"),
        sa.CheckConstraint("source_ref <> '' AND source_edition <> '' AND native_code <> ''", name="ck_cv2_provenance_present"),
        sa.CheckConstraint("reference_year >= 1900 AND reference_year <= 2200", name="ck_cv2_reference_year"),
    )
    op.create_index("ix_comp_v2_lookup", "compensation_v2_records", ["occupation_id", "country", "reference_year"])
    op.create_index("ix_comp_v2_source", "compensation_v2_records", ["source_ref", "source_edition"])


def downgrade() -> None:
    op.drop_index("ix_comp_v2_source", table_name="compensation_v2_records")
    op.drop_index("ix_comp_v2_lookup", table_name="compensation_v2_records")
    op.drop_table("compensation_v2_records")
    op.drop_table("compensation_import_batches")
