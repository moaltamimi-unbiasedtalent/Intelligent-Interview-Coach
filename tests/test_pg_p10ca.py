"""P10C-A: PostgreSQL execution evidence for migration 0035 and the foundation services. Runs ONLY against an ISOLATED throwaway server named by ``P5B_PG_ADMIN_URL`` (each module run
creates and drops its own ``p5b_*`` database); skipped without it. Synthetic structural data only."""

from __future__ import annotations

from tests._alembic_head import repository_head
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
NEW = ("global_sources", "global_source_events", "occupation_taxonomies", "graph_occupations", "graph_occupation_identifiers", "graph_occupation_relationships", "geography_coverage")


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


def test_0035_is_head_creates_the_seven_empty_tables_and_the_constraints(pg):
    from sqlalchemy import inspect, text
    insp = inspect(pg.engine)
    assert set(NEW) <= set(insp.get_table_names())
    with pg.engine.connect() as c:
        assert c.execute(text("select version_num from alembic_version")).scalar() == repository_head()
        for t in ("global_sources", "occupation_taxonomies", "graph_occupations", "graph_occupation_identifiers", "graph_occupation_relationships", "geography_coverage"):
            assert c.execute(text(f"select count(*) from {t}")).scalar() == 0
        checks = {r[0] for r in c.execute(text("select conname from pg_constraint where contype = 'c' and conrelid::regclass::text like any (array['global_sources','graph_occupation_relationships'])"))}
    assert any("verified_needs_source" in n for n in checks)
    assert any(u["name"] == "uq_graph_identifier" for u in insp.get_unique_constraints("graph_occupation_identifiers"))


def test_the_services_run_on_postgresql_and_the_database_enforces_the_rules(pg):
    from sqlalchemy import select
    from sqlalchemy.exc import IntegrityError
    from src.knowledge_foundation.graph import IdentityConflict, OccupationGraph
    from src.knowledge_foundation.registry import SourceRegistry, RegistryError
    from src.knowledge_foundation.taxonomy import TaxonomyCatalogue
    from src.persistence import GlobalSource, make_engine, make_session_factory
    sf = make_session_factory(make_engine(pg.url))
    TaxonomyCatalogue(sf).seed()
    reg, g = SourceRegistry(sf), OccupationGraph(sf)
    reg.register("pg_src", origin="official_local")
    a = g.add_occupation("Synthetic A", [("isco", "08", "2512")])
    b = g.add_occupation("Synthetic B", [("isco", "08", "2511")])
    rel = g.add_relationship(a["occupation_key"], b["occupation_key"], relationship_type="related", basis="curated_manual", mapping_status="unknown", limitations="pg test",
                             from_taxonomy=("isco", "08"), to_taxonomy=("isco", "08"))
    assert rel["mapping_status"] == "unknown"
    with pytest.raises(IdentityConflict):
        g.add_occupation("Other", [("isco", "08", "2512")], occupation_key="ask4mo:occ:other")
    with pytest.raises(RegistryError):
        reg.transition("pg_src", "approved_for_ingestion")
    with sf() as s:
        s.add(GlobalSource(source_id="bad", geographies=[], languages=[], provenance={}, approval_status="approved_for_ingestion", licence_status="unknown", origin="official_local"))
        with pytest.raises(IntegrityError):
            s.commit()
        s.rollback()
        assert s.scalar(select(GlobalSource).where(GlobalSource.source_id == "bad")) is None


def test_concurrent_registration_on_postgresql_yields_one_node(pg):
    from src.knowledge_foundation.graph import GraphError, IdentityConflict, OccupationGraph
    from src.persistence import make_engine, make_session_factory
    g = OccupationGraph(make_session_factory(make_engine(pg.url)))
    gate, out = threading.Barrier(6), []

    def go():
        gate.wait()
        try:
            out.append(g.add_occupation("Concurrent", [("isco", "08", "2221")])["occupation_key"])
        except (IdentityConflict, GraphError):
            out.append("conflict")
    ts = [threading.Thread(target=go) for _ in range(6)]
    [t.start() for t in ts]; [t.join() for t in ts]
    assert len({k for k in out if k != "conflict"}) == 1 and len(out) == 6
    assert len(g.find_by_identifier("isco", "2221")) == 1


def test_downgrade_one_step_and_reupgrade_on_postgresql(pg):
    from sqlalchemy import inspect
    _alembic(pg, "downgrade", "0034_preparation_packs")
    names = set(inspect(pg.engine).get_table_names())
    assert not set(NEW) & names and "preparation_packs" in names
    _alembic(pg, "upgrade", "head")
    assert set(NEW) <= set(inspect(pg.engine).get_table_names())
