"""P10C-B: PostgreSQL execution evidence for migration 0036, the alias constraints and the resolver. Runs ONLY against an ISOLATED throwaway server named by ``P5B_PG_ADMIN_URL`` (each module
run creates and drops its own ``p5b_*`` database); skipped without it. Synthetic structural data only."""

from __future__ import annotations

import os
import subprocess
import sys
import threading
import uuid
from pathlib import Path

import pytest

ADMIN = os.environ.get("P5B_PG_ADMIN_URL")
pytestmark = pytest.mark.skipif(not ADMIN, reason="P5B_PG_ADMIN_URL not set: no isolated PostgreSQL server for this run")
ROOT = Path(__file__).resolve().parents[1]
NEW = ("graph_occupation_aliases", "language_coverage")


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
    from src.knowledge_foundation.aliases import AliasStore
    from src.knowledge_foundation.graph import OccupationGraph
    from src.knowledge_foundation.registry import SourceRegistry
    from src.knowledge_foundation.taxonomy import TaxonomyCatalogue
    from src.persistence import make_engine, make_session_factory
    sf = make_session_factory(make_engine(pg.url))
    TaxonomyCatalogue(sf).seed()
    return sf, SourceRegistry(sf), OccupationGraph(sf), AliasStore(sf)


def test_0036_is_head_with_empty_tables_indexes_and_constraints(pg):
    from sqlalchemy import inspect, text
    insp = inspect(pg.engine)
    assert set(NEW) <= set(insp.get_table_names())
    with pg.engine.connect() as c:
        assert c.execute(text("select version_num from alembic_version")).scalar() == "0038_compensation_concepts"
        for t in NEW:
            assert c.execute(text(f"select count(*) from {t}")).scalar() == 0
        checks = {r[0] for r in c.execute(text("select conname from pg_constraint where contype = 'c' and conrelid = 'graph_occupation_aliases'::regclass"))}
        idx = {r[0] for r in c.execute(text("select indexname from pg_indexes where tablename = 'graph_occupation_aliases'"))}
    assert {"ck_ga_language_evidence", "ck_ga_official_needs_source", "ck_ga_type"} <= checks and {"ix_graph_alias_normalized", "ix_graph_alias_folded", "uq_graph_alias"} <= idx


def test_alias_rules_and_the_resolver_run_on_postgresql(pg):
    from sqlalchemy.exc import IntegrityError
    from src.knowledge_foundation.aliases import AliasError
    from src.knowledge_foundation.occupation_resolver import MultilingualRequest, OccupationResolver, ResolutionOutcome
    from src.persistence import GraphOccupation, GraphOccupationAlias, make_engine, make_session_factory
    sf, reg, g, a = _world(pg)
    reg.register("pg_fx", origin="synthetic_fixture")
    n1 = g.add_occupation("Synthetic PG one", [("isco", "08", "9951")])["occupation_key"]
    n2 = g.add_occupation("Synthetic PG two", [("isco", "08", "9952")])["occupation_key"]
    for k in (n1, n2):
        a.add_alias(k, "Gift", language="de", language_basis="fixture_declared", alias_type="source_synonym", source_ref="pg_fx")
    a.add_alias(n1, "Año", language="es", language_basis="fixture_declared", alias_type="source_synonym", source_ref="pg_fx")
    a.add_alias(n2, "Ano", language="es", language_basis="fixture_declared", alias_type="source_synonym", source_ref="pg_fx")
    r = OccupationResolver(g, a)
    assert r.resolve(MultilingualRequest(title="gift", title_language="de")).outcome is ResolutionOutcome.AMBIGUOUS
    assert r.resolve(MultilingualRequest(title="AÑO", title_language="es")).candidates[0].occupation_key == n1
    assert r.resolve(MultilingualRequest(title="Áno", title_language="es")).outcome is ResolutionOutcome.AMBIGUOUS
    with pytest.raises(AliasError):
        a.add_alias(n1, "Official", language="en", language_basis="fixture_declared", alias_type="official_preferred", source_ref="")
    with make_session_factory(make_engine(pg.url))() as s:
        oid = s.query(GraphOccupation.id).first()[0]
        base = dict(occupation_id=oid, alias_text="x", normalized_text="x", folded_text="x", normalization_version="n1", context_terms=[], provenance={})
        for bad in ({"language": "en", "language_basis": "unknown"}, {"alias_type": "official_preferred", "source_ref": ""}, {"alias_type": "made_up"}):
            s.add(GraphOccupationAlias(**{**base, **bad}))
            with pytest.raises(IntegrityError):
                s.commit()
            s.rollback()


def test_concurrent_identical_alias_registration_yields_one_row(pg):
    from src.knowledge_foundation.aliases import AliasError
    from src.persistence import GraphOccupationAlias, make_engine, make_session_factory
    from sqlalchemy import func, select
    sf, reg, g, a = _world(pg)
    reg.register("pg_fx2", origin="synthetic_fixture")
    k = g.add_occupation("Synthetic PG concurrent", [("isco", "08", "9953")])["occupation_key"]
    gate, out = threading.Barrier(6), []

    def go():
        gate.wait()
        try:
            out.append(a.add_alias(k, "Concurrent label", language="en", language_basis="fixture_declared", alias_type="source_synonym", source_ref="pg_fx2")["id"])
        except AliasError:
            out.append("conflict")
    ts = [threading.Thread(target=go) for _ in range(6)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert len(out) == 6 and len({i for i in out if i != "conflict"}) >= 1
    with make_session_factory(make_engine(pg.url))() as s:
        assert s.scalar(select(func.count()).select_from(GraphOccupationAlias).where(GraphOccupationAlias.normalized_text == "concurrent label")) == 1


def test_downgrade_one_step_keeps_p10c_a_and_reupgrades_on_postgresql(pg):
    from sqlalchemy import inspect
    _alembic(pg, "downgrade", "0035_knowledge_foundation")
    names = set(inspect(pg.engine).get_table_names())
    assert not set(NEW) & names and {"graph_occupations", "global_sources", "geography_coverage"} <= names
    _alembic(pg, "upgrade", "head")
    assert set(NEW) <= set(inspect(pg.engine).get_table_names())
