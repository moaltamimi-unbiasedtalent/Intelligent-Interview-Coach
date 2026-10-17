"""P10C-D: PostgreSQL execution evidence for migration 0038, the country importers and the resolver. Runs ONLY against an ISOLATED throwaway server named by ``P5B_PG_ADMIN_URL`` (each module
run creates and drops its own ``p5b_*`` database); skipped without it. Synthetic structural data only."""

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
MAPS = dict(statistic_map={"MED": ("median", 0)}, period_map={"HR": "hourly", "MES": "monthly"})


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


def _world(pg, tag):
    from src.knowledge_foundation.aliases import AliasStore
    from src.knowledge_foundation.compensation.country_import import import_taxonomy_nodes
    from src.knowledge_foundation.compensation.store import CompensationStoreV2
    from src.knowledge_foundation.graph import OccupationGraph
    from src.knowledge_foundation.registry import SourceRegistry
    from src.knowledge_foundation.taxonomy import TaxonomyCatalogue
    from src.persistence import make_engine, make_session_factory
    sf = make_session_factory(make_engine(pg.url))
    tax, reg, g, a = TaxonomyCatalogue(sf), SourceRegistry(sf), OccupationGraph(sf), AliasStore(sf)
    tax.seed()
    tax.ensure("sinco", f"fx-{tag}", status="unknown", acquisition_status="not_acquired", code_pattern="[0-9]{4}")
    reg.register(f"pg_t_{tag}", origin="synthetic_fixture", publisher="P", dataset_name="D")
    reg.register(f"pg_c_{tag}", origin="synthetic_fixture", publisher="Synthetic publisher", dataset_name="Synthetic dataset", precedence_category="national_official_occupation_statistics")
    import_taxonomy_nodes(g, a, reg, [{"code": "9301", "label": "Synthetic PG MX", "labels": [{"text": f"syn pg mx {tag}", "language": "es"}]}], scheme="sinco", edition=f"fx-{tag}", source_ref=f"pg_t_{tag}", mode="fixture")
    return sf, reg, g, a, CompensationStoreV2(sf, reg, g)


def _rows(**kw):
    base = {"code": "9301", "statistic": "MED", "period": "MES", "value": "12000.5", "concept": "IND", "population": "EMP", "method": "ENC"}
    base.update(kw)
    return base


KW = dict(concept_map={"IND": "individual_earnings", "HOG": "household_income", "SAL": "wage_statistic"}, population_map={"EMP": "employees", "ALL": "all_workers"},
          method_map={"ENC": "survey", "ADM": "administrative_records"}, level_by_code_length={4: "detailed"}, code_pattern="[0-9]{4}", **MAPS)


def test_0038_is_head_with_the_new_columns_checks_and_natural_key(pg):
    from sqlalchemy import inspect, text
    with pg.engine.connect() as c:
        assert c.execute(text("select version_num from alembic_version")).scalar() == "0038_compensation_concepts"
        checks = {r[0] for r in c.execute(text("select conname from pg_constraint where contype = 'c' and conrelid = 'compensation_v2_records'::regclass"))}
        uq = c.execute(text("select pg_get_constraintdef(oid) from pg_constraint where conname = 'uq_comp_v2_natural_key'")).scalar()
    assert {"ck_cv2_earnings_concept", "ck_cv2_population_scope", "ck_cv2_evidence_method", "ck_cv2_not_household_income", "ck_cv2_value_not_zero_or_invented", "ck_cv2_bounds"} <= checks
    assert all(x in uq for x in ("earnings_concept", "population_scope", "evidence_method"))
    assert {"earnings_concept", "population_scope", "evidence_method"} <= {c["name"] for c in inspect(pg.engine).get_columns("compensation_v2_records")}


def test_different_definitions_are_distinct_records_and_household_income_is_refused(pg):
    from sqlalchemy.exc import IntegrityError
    from src.knowledge_foundation.compensation import country_adapters as CA
    from src.persistence import CompensationRecordV2Row, make_engine, make_session_factory
    sf, reg, g, a, store = _world(pg, "a")
    recs, rej = CA.mexico_records([_rows(), _rows(concept="SAL", value="13500"), _rows(population="ALL", value="11000"), _rows(concept="HOG", value="30000")], source_ref="pg_c_a", source_edition="E1",
                                  taxonomy_edition="fx-a", reference_year=2025, **KW)
    rep = store.import_records(recs, source_ref="pg_c_a", source_edition="E1", mode="fixture")
    assert not rej and rep.added == 3 and rep.rejections == {"earnings_concept_not_occupation_compensation": 1}
    assert store.import_records(recs, source_ref="pg_c_a", source_edition="E1", mode="fixture").already_imported
    from sqlalchemy import select
    from src.persistence import GraphOccupation
    with sf() as s:
        oid = s.scalar(select(GraphOccupation.id).where(GraphOccupation.canonical_label.like("Synthetic PG MX%")))
    rows = store.records_for([oid], "MX")
    assert {(r["earnings_concept"], r["population_scope"]) for r in rows} == {("individual_earnings", "employees"), ("wage_statistic", "employees"), ("individual_earnings", "all_workers")}
    assert {r["value"] for r in rows} == {Decimal("12000.5"), Decimal("13500"), Decimal("11000")}
    with make_session_factory(make_engine(pg.url))() as s:
        tid = s.execute(__import__("sqlalchemy").text("select taxonomy_id from compensation_v2_records limit 1")).scalar()
        base = dict(occupation_id=oid, taxonomy_id=tid, country="MX", currency="MXN", pay_period="monthly", pay_basis="unknown", measure="median", percentile=0, value_status="reported",
                    amount_scale=0, value_units=1, source_ref="s", source_edition="e", reference_year=2025, evidence_class="C1", precedence_category="x", provenance={})
        for i, bad in enumerate((dict(earnings_concept="household_income"), dict(earnings_concept="vibes"), dict(population_scope="everyone"), dict(evidence_method="rumour"), dict(value_units=0))):
            s.add(CompensationRecordV2Row(record_key=f"pgd{i}", native_code=f"n{i}", **{**base, **bad}))
            with pytest.raises(IntegrityError):
                s.commit()
            s.rollback()


def test_the_resolver_never_combines_definitions_on_postgresql(pg):
    from src.knowledge_foundation.compensation import country_adapters as CA
    from src.knowledge_foundation.compensation.resolver import CompensationOutcome, CompensationRequest, CompensationResolver
    from src.knowledge_foundation.occupation_resolver import MultilingualRequest, OccupationResolver
    sf, reg, g, a, store = _world(pg, "b")
    recs, _ = CA.mexico_records([_rows(), _rows(concept="SAL", value="13500"), _rows(region="JAL", value="14000")], source_ref="pg_c_b", source_edition="E1", taxonomy_edition="fx-b", reference_year=2025, **KW)
    store.import_records(recs, source_ref="pg_c_b", source_edition="E1", mode="fixture")
    res = CompensationResolver(store, OccupationResolver(g, a, registry=reg), g, reg)
    occ = MultilingualRequest(title="syn pg mx b", title_language="es")
    assert res.resolve(CompensationRequest(occupation=occ, country="MX", require_operational=False)).outcome is CompensationOutcome.CONFLICT
    ok = res.resolve(CompensationRequest(occupation=occ, country="MX", earnings_concept="wage_statistic", require_operational=False))
    assert ok.outcome is CompensationOutcome.EVIDENCE and ok.value == "13500" and ok.currency == "MXN" and ok.pay_period == "monthly" and ok.geography_level == "national"
    reg_r = res.resolve(CompensationRequest(occupation=occ, country="MX", region="jal", require_operational=False))
    assert reg_r.value == "14000" and reg_r.region == "MX-JAL" and reg_r.geography_level == "regional"
    assert res.resolve(CompensationRequest(occupation=occ, country="MX", require_operational=True)).abstention_reason == "evidence_exists_but_is_not_operational"


def test_concurrent_identical_country_imports_yield_one_set_on_postgresql(pg):
    from sqlalchemy import func, select
    from src.knowledge_foundation.compensation import country_adapters as CA
    from src.persistence import CompensationRecordV2Row, make_engine, make_session_factory
    sf, reg, g, a, store = _world(pg, "c")
    recs, _ = CA.mexico_records([_rows(), _rows(value="12100", region="JAL")], source_ref="pg_c_c", source_edition="E1", taxonomy_edition="fx-c", reference_year=2025, **KW)
    gate, out = threading.Barrier(6), []

    def go():
        gate.wait()
        try:
            out.append(store.import_records(recs, source_ref="pg_c_c", source_edition="E1", mode="fixture"))
        except Exception as exc:  # noqa: BLE001
            out.append(type(exc).__name__)
    ts = [threading.Thread(target=go) for _ in range(6)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    with make_session_factory(make_engine(pg.url))() as s:
        assert s.scalar(select(func.count()).select_from(CompensationRecordV2Row).where(CompensationRecordV2Row.source_ref == "pg_c_c")) == 2
    assert any(not isinstance(r, str) and r.added == 2 for r in out)


def test_downgrade_refuses_when_definition_distinct_rows_exist_then_preserves_rows_and_reupgrades(pg):
    from sqlalchemy import inspect, text
    out = subprocess.run([sys.executable, "-m", "alembic", "downgrade", "0037_compensation_v2"], cwd=ROOT, env=pg.env, capture_output=True, text=True, timeout=300)
    assert out.returncode != 0 and "downgrade refused" in out.stderr
    with pg.engine.connect() as c:
        assert c.execute(text("select version_num from alembic_version")).scalar() == "0038_compensation_concepts"                 # nothing changed
        assert c.execute(text("select count(*) from compensation_v2_records")).scalar() >= 6
    with pg.engine.begin() as c:                                                                                               # the operator archives the definition-distinct rows
        c.execute(text("delete from compensation_v2_records where source_ref in ('pg_c_a', 'pg_c_b')"))
    _alembic(pg, "downgrade", "0037_compensation_v2")
    cols = {c["name"] for c in inspect(pg.engine).get_columns("compensation_v2_records")}
    assert "earnings_concept" not in cols and "value_units" in cols
    with pg.engine.connect() as c:
        assert c.execute(text("select count(*) from compensation_v2_records where source_ref = 'pg_c_c'")).scalar() == 2         # the remaining rows survive
    _alembic(pg, "upgrade", "head")
    with pg.engine.connect() as c:
        row = c.execute(text("select earnings_concept, population_scope, evidence_method from compensation_v2_records where source_ref = 'pg_c_c' limit 1")).one()
    assert tuple(row) == ("unknown", "unknown", "unknown")                                                                      # definition detail is only restored by re-import
