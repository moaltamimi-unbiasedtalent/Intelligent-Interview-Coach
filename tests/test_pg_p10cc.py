"""P10C-C: PostgreSQL execution evidence for migration 0037, the Compensation V2 constraints, the importer and the resolver. Runs ONLY against an ISOLATED throwaway server named by
``P5B_PG_ADMIN_URL`` (each module run creates and drops its own ``p5b_*`` database); skipped without it. Synthetic structural data only."""

from __future__ import annotations

import os
import subprocess
import sys
import threading
import uuid
from decimal import Decimal
from pathlib import Path

import pytest

ADMIN = os.environ.get("P5B_PG_ADMIN_URL")
pytestmark = pytest.mark.skipif(not ADMIN, reason="P5B_PG_ADMIN_URL not set: no isolated PostgreSQL server for this run")
ROOT = Path(__file__).resolve().parents[1]
NEW = ("compensation_v2_records", "compensation_import_batches")


class NS:
    def __init__(self, **kw):
        self.__dict__.update(kw)


@pytest.fixture(scope="module")
def pg():
    import psycopg
    from sqlalchemy import create_engine
    name = f"p5b_{uuid.uuid4().hex[:10]}"
    with psycopg.connect(ADMIN.replace("postgresql+psycopg://", "postgresql://"), autocommit=True) as c:
        c.execute(f'CREATE DATABASE "{name}"')
    url = ADMIN.rsplit("/", 1)[0] + f"/{name}"
    env = {**os.environ, "DATABASE_URL": url, "API_ENV": "test"}
    out = subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=ROOT, env=env, capture_output=True, text=True, timeout=300)
    assert out.returncode == 0, out.stderr[-800:]
    engine = create_engine(url, future=True)
    yield NS(url=url, engine=engine, env=env)
    engine.dispose()
    with psycopg.connect(ADMIN.replace("postgresql+psycopg://", "postgresql://"), autocommit=True) as c:
        c.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')


def _alembic(pg, *args):
    out = subprocess.run([sys.executable, "-m", "alembic", *args], cwd=ROOT, env=pg.env, capture_output=True, text=True, timeout=300)
    assert out.returncode == 0, out.stderr[-600:]


def _world(pg):
    from src.knowledge_foundation.graph import OccupationGraph
    from src.knowledge_foundation.registry import SourceRegistry
    from src.knowledge_foundation.taxonomy import TaxonomyCatalogue
    from src.knowledge_foundation.compensation.store import CompensationStoreV2
    from src.persistence import make_engine, make_session_factory
    sf = make_session_factory(make_engine(pg.url))
    TaxonomyCatalogue(sf).seed()
    reg, g = SourceRegistry(sf), OccupationGraph(sf)
    reg.register("pg_fx", origin="synthetic_fixture", publisher="Synthetic publisher", dataset_name="Synthetic dataset", precedence_category="national_official_occupation_statistics")
    node = g.add_occupation("Synthetic PG compensation occupation", [("isco", "08", "9961")])["occupation_key"]
    return sf, reg, g, CompensationStoreV2(sf, reg, g), node


def _rec(**kw):
    base = dict(taxonomy_scheme="isco", taxonomy_edition="08", native_code="9961", occupation_level="detailed", country="DE", geography_level="national", currency="EUR", pay_period="annual",
                pay_basis="gross", measure="median", value="48000.25", source_ref="pg_fx", source_edition="E1", reference_year=2025)
    base.update(kw)
    return base


def test_0037_is_head_with_empty_tables_indexes_and_constraints(pg):
    from sqlalchemy import inspect, text
    insp = inspect(pg.engine)
    assert set(NEW) <= set(insp.get_table_names())
    with pg.engine.connect() as c:
        assert c.execute(text("select version_num from alembic_version")).scalar() == "0037_compensation_v2"
        for t in NEW:
            assert c.execute(text(f"select count(*) from {t}")).scalar() == 0
        checks = {r[0] for r in c.execute(text("select conname from pg_constraint where contype = 'c' and conrelid = 'compensation_v2_records'::regclass"))}
        idx = {r[0] for r in c.execute(text("select indexname from pg_indexes where tablename = 'compensation_v2_records'"))}
        col = c.execute(text("select data_type from information_schema.columns where table_name = 'compensation_v2_records' and column_name = 'value_units'")).scalar()
    assert {"ck_cv2_value_not_zero_or_invented", "ck_cv2_percentile", "ck_cv2_bounds", "ck_cv2_evidence_class", "ck_cv2_provenance_present", "ck_cv2_currency"} <= checks
    assert {"ix_comp_v2_lookup", "ix_comp_v2_source", "uq_comp_v2_natural_key", "uq_comp_v2_record_key"} <= idx and col == "bigint"


def test_the_importer_stores_exact_decimals_and_the_database_refuses_invented_rows(pg):
    from sqlalchemy.exc import IntegrityError
    from src.persistence import CompensationRecordV2Row, make_engine, make_session_factory
    sf, reg, g, store, node = _world(pg)
    rep = store.import_records([_rec(lower_value="40000.10", upper_value="60000.99")], source_ref="pg_fx", source_edition="E1", mode="fixture")
    assert rep.added == 1 and store.import_records([_rec(lower_value="40000.10", upper_value="60000.99")], source_ref="pg_fx", source_edition="E1", mode="fixture").already_imported
    from sqlalchemy import select
    from src.persistence import GraphOccupation
    with sf() as s:
        oid = s.scalar(select(GraphOccupation.id).where(GraphOccupation.occupation_key == node))
    r = store.records_for([oid], "DE")[0]
    assert r["value"] == Decimal("48000.25") and r["lower_value"] == Decimal("40000.10") and isinstance(r["value"], Decimal)
    changed = store.import_records([_rec(value="99999")], source_ref="pg_fx", source_edition="E1", mode="fixture")
    assert changed.rejections == {"conflicting_value_for_same_measurement": 1}
    with make_session_factory(make_engine(pg.url))() as s:
        tid = s.execute(__import__("sqlalchemy").text("select taxonomy_id from compensation_v2_records")).scalar()
        base = dict(occupation_id=oid, taxonomy_id=tid, country="DE", currency="EUR", pay_period="annual", pay_basis="gross", measure="median", percentile=0, value_status="reported", amount_scale=0,
                    value_units=1, source_ref="s", source_edition="e", reference_year=2025, evidence_class="C1", precedence_category="x", provenance={})
        for i, bad in enumerate((dict(value_units=0), dict(value_units=None), dict(lower_units=5), dict(lower_units=5, upper_units=3), dict(percentile=50), dict(evidence_class="C4"), dict(currency="EU"),
                                 dict(value_status="suppressed", value_units=5), dict(source_edition=""), dict(amount_scale=9))):
            s.add(CompensationRecordV2Row(record_key=f"pgbad{i}", native_code=f"n{i}", **{**base, **bad}))
            with pytest.raises(IntegrityError):
                s.commit()
            s.rollback()


def test_concurrent_identical_imports_yield_one_set_on_postgresql(pg):
    from sqlalchemy import func, select
    from src.persistence import CompensationRecordV2Row, make_engine, make_session_factory
    sf, reg, g, store, node = _world(pg)
    gate, out = threading.Barrier(6), []

    def go():
        gate.wait()
        try:
            out.append(store.import_records([_rec(reference_year=2020), _rec(reference_year=2019)], source_ref="pg_fx", source_edition="E1", mode="fixture"))
        except Exception as exc:  # noqa: BLE001
            out.append(type(exc).__name__)
    ts = [threading.Thread(target=go) for _ in range(6)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    with make_session_factory(make_engine(pg.url))() as s:
        assert s.scalar(select(func.count()).select_from(CompensationRecordV2Row).where(CompensationRecordV2Row.reference_year.in_((2019, 2020)))) == 2
    assert any(not isinstance(r, str) and r.added == 2 for r in out)


def test_the_resolver_runs_on_postgresql_and_withholds_by_default(pg):
    from src.knowledge_foundation.aliases import AliasStore
    from src.knowledge_foundation.compensation.resolver import CompensationOutcome, CompensationRequest, CompensationResolver
    from src.knowledge_foundation.occupation_resolver import MultilingualRequest, OccupationResolver
    sf, reg, g, store, node = _world(pg)
    store.import_records([_rec(reference_year=2018)], source_ref="pg_fx", source_edition="E1", mode="fixture")
    a = AliasStore(sf)
    a.add_alias(node, "pg compensation title", language="en", language_basis="curated_manual", alias_type="recognized_title")
    res = CompensationResolver(store, OccupationResolver(g, a, registry=reg), g, reg)
    q = dict(occupation=MultilingualRequest(title="pg compensation title", title_language="en"), country="DE")
    dflt = res.resolve(CompensationRequest(**q))
    assert dflt.outcome is CompensationOutcome.ABSTAIN and dflt.value is None and dflt.abstention_reason == "evidence_exists_but_is_not_operational"
    internal = res.resolve(CompensationRequest(require_operational=False, **q))
    assert internal.outcome is CompensationOutcome.EVIDENCE and internal.value == "48000.25" and internal.candidate_presentable is False and internal.currency == "EUR"
    assert res.resolve(CompensationRequest(require_operational=False, occupation=q["occupation"], country="FR")).outcome is CompensationOutcome.ABSTAIN


def test_downgrade_one_step_keeps_earlier_tables_and_reupgrades_on_postgresql(pg):
    from sqlalchemy import inspect
    _alembic(pg, "downgrade", "0036_multilingual_aliases")
    names = set(inspect(pg.engine).get_table_names())
    assert not set(NEW) & names and {"graph_occupation_aliases", "language_coverage", "graph_occupations", "global_sources"} <= names
    _alembic(pg, "upgrade", "head")
    assert set(NEW) <= set(inspect(pg.engine).get_table_names())
