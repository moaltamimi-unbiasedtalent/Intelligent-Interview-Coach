"""Compensation evidence definitions (P10C-D). SCHEMA ONLY: nothing is seeded and no compensation value is created.

Adds three explicit columns to ``compensation_v2_records``: ``earnings_concept`` (individual earnings, employment income, wage statistic, household income, formal-sector compensation,
unknown), ``population_scope`` (who the figure covers) and ``evidence_method`` (survey, administrative records, census, other documented, unknown). They become part of the natural key so
figures that measure different things are never one record, and a CHECK refuses household income as occupation compensation. Existing rows (none exist in any environment: nothing was ever
ingested) keep ``unknown`` for all three, which preserves the behaviour of the P10C-C records. The migration uses batch mode so SQLite rebuilds the table (SQLite reflects the CHECK constraints, so they
survive and the new ones are created and dropped by name); PostgreSQL uses plain ALTER. Downgrade removes the columns and restores the previous natural key, and REFUSES (before changing anything) when records that differ only by these columns exist. Chains from 0037. Single head.

Revision ID: 0038_compensation_concepts
Revises: 0037_compensation_v2
Create Date: 2026-10-18
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0038_compensation_concepts"
down_revision = "0037_compensation_v2"
branch_labels = None
depends_on = None


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


CONCEPTS = ("unknown", "individual_earnings", "employment_income", "wage_statistic", "household_income", "formal_sector_compensation")
POPULATIONS = ("unknown", "all_workers", "employees", "formal_sector", "full_time_employees")
METHODS = ("unknown", "survey", "administrative_records", "census", "other_documented")
OLD_KEY = ["source_ref", "source_edition", "taxonomy_id", "native_code", "country", "region_key", "reference_year", "pay_period", "currency", "pay_basis", "measure", "percentile", "data_vintage"]
NEW_KEY = OLD_KEY + ["earnings_concept", "population_scope", "evidence_method"]


def _new_checks() -> list[sa.CheckConstraint]:
    return [
        sa.CheckConstraint(_in("earnings_concept", CONCEPTS), name="ck_cv2_earnings_concept"),
        sa.CheckConstraint(_in("population_scope", POPULATIONS), name="ck_cv2_population_scope"),
        sa.CheckConstraint(_in("evidence_method", METHODS), name="ck_cv2_evidence_method"),
        sa.CheckConstraint("earnings_concept <> 'household_income'", name="ck_cv2_not_household_income"),
    ]


def upgrade() -> None:
    with op.batch_alter_table("compensation_v2_records") as b:
        b.add_column(sa.Column("earnings_concept", sa.String(length=28), server_default="unknown", nullable=False))
        b.add_column(sa.Column("population_scope", sa.String(length=20), server_default="unknown", nullable=False))
        b.add_column(sa.Column("evidence_method", sa.String(length=24), server_default="unknown", nullable=False))
        b.drop_constraint("uq_comp_v2_natural_key", type_="unique")
        b.create_unique_constraint("uq_comp_v2_natural_key", NEW_KEY)
        for c in _new_checks():                                           # applied after the columns exist, on both dialects
            b.create_check_constraint(c.name, c.sqltext)


def downgrade() -> None:
    dup = op.get_bind().execute(sa.text(f"SELECT COUNT(*) FROM (SELECT 1 FROM compensation_v2_records GROUP BY {', '.join(OLD_KEY)} HAVING COUNT(*) > 1) AS d")).scalar()
    if dup:                                                                      # refuse BEFORE touching anything: no data is deleted or merged by this migration
        raise RuntimeError("downgrade refused: some Compensation V2 records differ only by earnings concept, population scope or evidence method and would violate the earlier natural key; "
                           "archive or remove them first")
    with op.batch_alter_table("compensation_v2_records") as b:
        for c in _new_checks():                                            # SQLite reflects CHECK constraints, so they must go before their columns do
            b.drop_constraint(c.name, type_="check")
        b.drop_constraint("uq_comp_v2_natural_key", type_="unique")
        b.create_unique_constraint("uq_comp_v2_natural_key", OLD_KEY)
        b.drop_column("evidence_method")
        b.drop_column("population_scope")
        b.drop_column("earnings_concept")
