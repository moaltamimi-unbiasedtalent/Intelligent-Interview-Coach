"""P10C-E: PostgreSQL execution evidence for the wider South America adapter, the ILOSTAT-style contract, the precedence boundary and the resolver on the unchanged schema (no migration exists in
this wave). Runs ONLY against an ISOLATED throwaway server named by ``P5B_PG_ADMIN_URL`` (each module run creates and drops its own ``p5b_*`` database); skipped without it. Synthetic data only."""

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
SAM = dict(statistic_map={"MED": ("median", 0)}, period_map={"MES": "monthly"}, concept_map={"LAB": "employment_income", "SAL": "wage_statistic"}, population_map={"ASAL": "employees"}, method_map={"ENC": "survey"},
           level_by_code_length={4: "detailed"}, code_pattern="[0-9]{4}")


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
    yield NS(url=url, engine=engine)
    engine.dispose()
    with psycopg.connect(ADMIN.replace("postgresql+psycopg://", "postgresql://"), autocommit=True) as c:
        c.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')


def _world(pg):
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
    reg.register("pg_t", origin="synthetic_fixture", publisher="P", dataset_name="D")
    reg.register("pg_n", origin="synthetic_fixture", publisher="Synthetic publisher", dataset_name="Synthetic dataset", precedence_category="national_official_occupation_statistics")
    reg.register("pg_ilo", origin="synthetic_fixture", publisher="Synthetic international publisher", dataset_name="Synthetic dataset", precedence_category="eurostat_harmonised",
                 provenance={"international_family": "ilostat"})
    import_taxonomy_nodes(g, a, reg, [{"code": "9701", "label": "Synthetic PG SA", "labels": [{"text": "syn pg sa", "language": "en"}]}], scheme="isco", edition="08", source_ref="pg_t", mode="fixture")
    return sf, reg, g, a, CompensationStoreV2(sf, reg, g)


def test_the_schema_is_unchanged_and_the_south_america_adapter_stores_exact_decimals(pg):
    from sqlalchemy import select, text
    from src.knowledge_foundation.compensation import country_adapters as CA
    from src.persistence import GraphOccupation
    with pg.engine.connect() as c:
        assert c.execute(text("select version_num from alembic_version")).scalar() == "0039_speech_governance"
    sf, reg, g, a, store = _world(pg)
    recs, rej = CA.south_america_records("CL", [{"code": "9701", "statistic": "MED", "period": "MES", "value": "1234567.50", "concept": "LAB", "population": "ASAL", "method": "ENC", "currency": "CLP", "basis": "gross"},
                                                {"code": "9701", "statistic": "MED", "period": "MES", "value": "1300000", "concept": "SAL", "population": "ASAL", "method": "ENC", "currency": "CLP", "basis": "gross"},
                                                {"code": "9701", "statistic": "MED", "period": "MES", "value": "5", "concept": "LAB", "population": "ASAL", "method": "ENC", "region": "Santiago"}],
                                         source_ref="pg_n", source_edition="E1", taxonomy_edition="08", reference_year=2023, **SAM)
    assert dict(rej) == {"currency_missing": 1}
    rep = store.import_records(recs, source_ref="pg_n", source_edition="E1", mode="fixture")
    assert rep.added == 2 and store.import_records(recs, source_ref="pg_n", source_edition="E1", mode="fixture").already_imported
    with sf() as s:
        oid = s.scalar(select(GraphOccupation.id).where(GraphOccupation.canonical_label.like("Synthetic PG SA%")))
    rows = store.records_for([oid], "CL")
    assert {r["value"] for r in rows} == {Decimal("1234567.5"), Decimal("1300000")} and {r["currency"] for r in rows} == {"CLP"}


def test_the_pending_international_family_is_refused_in_production_and_flagged_on_postgresql(pg):
    from src.knowledge_foundation.compensation import international as INTL
    from src.knowledge_foundation.compensation.resolver import CompensationOutcome, CompensationRequest, CompensationResolver
    from src.knowledge_foundation.compensation.store import CompensationSourceNotApproved
    from src.knowledge_foundation.occupation_resolver import MultilingualRequest, OccupationResolver
    sf, reg, g, a, store = _world(pg)
    recs, rej = INTL.ilostat_records([{"ref_area": "ARG", "classif": "9701", "classification": "ISCO-08", "indicator": "EAR", "unit": "LCU", "time": 2022, "value": "800"},
                                      {"ref_area": "ARG", "classif": "9701", "classification": "ISCO-08", "indicator": "GDP", "unit": "USD", "time": 2022, "value": "9"}],
                                     source_ref="pg_ilo", source_edition="E1", indicator_map={"EAR": {"period": "monthly", "measure": "median", "concept": "employment_income", "population": "employees", "method": "survey", "basis": "gross"}},
                                     currency_by_unit={"LCU": None, "USD": "USD"}, local_currency_unit="LCU", currency_by_country={"AR": "ARS"}, classification_map={"ISCO-08": ("isco", "08")})
    assert len(recs) == 1 and rej["unsupported_statistic"] == 1
    with pytest.raises(CompensationSourceNotApproved):
        store.import_records(recs, source_ref="pg_ilo", source_edition="E1", mode="production")
    assert store.import_records(recs, source_ref="pg_ilo", source_edition="E1", mode="fixture").added == 1
    res = CompensationResolver(store, OccupationResolver(g, a, registry=reg), g, reg)
    occ = MultilingualRequest(title="syn pg sa", title_language="en")
    internal = res.resolve(CompensationRequest(occupation=occ, country="AR", require_operational=False))
    assert internal.outcome is CompensationOutcome.EVIDENCE and internal.evidence_class == "C3" and internal.precedence_pending is True and internal.evidence_assessment["state"] == "LIMITED_EVIDENCE"
    op = res.resolve(CompensationRequest(occupation=occ, country="AR"))
    assert op.outcome is CompensationOutcome.ABSTAIN and op.withheld.get("precedence_decision_pending") == 1 and op.value is None
    assert res.resolve(CompensationRequest(occupation=occ, country="BO", require_operational=False)).outcome is CompensationOutcome.ABSTAIN


def test_national_evidence_outranks_a_comparable_international_record_on_postgresql(pg):
    from src.knowledge_foundation.compensation import country_adapters as CA, international as INTL
    from src.knowledge_foundation.compensation.resolver import CompensationOutcome, CompensationRequest, CompensationResolver
    from src.knowledge_foundation.occupation_resolver import MultilingualRequest, OccupationResolver
    sf, reg, g, a, store = _world(pg)
    nat, _ = CA.south_america_records("UY", [{"code": "9701", "statistic": "MED", "period": "MES", "value": "900", "concept": "LAB", "population": "ASAL", "method": "ENC", "currency": "UYU", "basis": "gross"}],
                                      source_ref="pg_n", source_edition="E2", taxonomy_edition="08", reference_year=2023, **SAM)
    intl, _ = INTL.ilostat_records([{"ref_area": "URY", "classif": "9701", "classification": "ISCO-08", "indicator": "EAR", "unit": "LCU", "time": 2023, "value": "870"}], source_ref="pg_ilo", source_edition="E2",
                                   indicator_map={"EAR": {"period": "monthly", "measure": "median", "concept": "employment_income", "population": "employees", "method": "survey", "basis": "gross"}},
                                   currency_by_unit={"LCU": None}, local_currency_unit="LCU", currency_by_country={"UY": "UYU"}, classification_map={"ISCO-08": ("isco", "08")})
    store.import_records(nat, source_ref="pg_n", source_edition="E2", mode="fixture")
    store.import_records(intl, source_ref="pg_ilo", source_edition="E2", mode="fixture")
    res = CompensationResolver(store, OccupationResolver(g, a, registry=reg), g, reg)
    r = res.resolve(CompensationRequest(occupation=MultilingualRequest(title="syn pg sa", title_language="en"), country="UY", require_operational=False))
    assert r.outcome is CompensationOutcome.EVIDENCE and r.evidence_class == "C1" and r.value == "900" and len(r.corroborating) == 1 and r.corroborating[0]["agrees"] is False


def test_concurrent_identical_south_america_imports_yield_one_set_on_postgresql(pg):
    from sqlalchemy import func, select
    from src.knowledge_foundation.compensation import country_adapters as CA
    from src.persistence import CompensationRecordV2Row, make_engine, make_session_factory
    sf, reg, g, a, store = _world(pg)
    recs, _ = CA.south_america_records("PE", [{"code": "9701", "statistic": "MED", "period": "MES", "value": "2500", "concept": "LAB", "population": "ASAL", "method": "ENC", "currency": "PEN", "basis": "gross"}],
                                       source_ref="pg_n", source_edition="E3", taxonomy_edition="08", reference_year=2023, **SAM)
    gate, out = threading.Barrier(6), []

    def go():
        gate.wait()
        try:
            out.append(store.import_records(recs, source_ref="pg_n", source_edition="E3", mode="fixture"))
        except Exception as exc:  # noqa: BLE001
            out.append(type(exc).__name__)
    ts = [threading.Thread(target=go) for _ in range(6)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    with make_session_factory(make_engine(pg.url))() as s:
        assert s.scalar(select(func.count()).select_from(CompensationRecordV2Row).where(CompensationRecordV2Row.source_edition == "E3")) == 1
    assert any(not isinstance(r, str) and r.added == 1 for r in out)
