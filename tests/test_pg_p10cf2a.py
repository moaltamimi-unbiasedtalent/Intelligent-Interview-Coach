"""P10C-F2A: PostgreSQL execution evidence for the US SOC graph population and the OEWS import path (synthetic workbooks only; no official data). Runs ONLY against an ISOLATED throwaway
server named by ``P5B_PG_ADMIN_URL`` (the module creates and drops its own ``p5b_*`` database); skipped without it."""

from __future__ import annotations

import os
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

ADMIN = os.environ.get("P5B_PG_ADMIN_URL")
pytestmark = pytest.mark.skipif(not ADMIN, reason="P5B_PG_ADMIN_URL not set: no isolated PostgreSQL server for this run")
ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def pgurl():
    import psycopg

    name = f"p5b_{uuid.uuid4().hex[:10]}"
    with psycopg.connect(ADMIN.replace("postgresql+psycopg://", "postgresql://"), autocommit=True) as c:
        c.execute(f'CREATE DATABASE "{name}"')
    url = ADMIN.rsplit("/", 1)[0] + f"/{name}"
    out = subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=ROOT, env={**os.environ, "DATABASE_URL": url, "API_ENV": "test"}, capture_output=True, text=True, timeout=300)
    assert out.returncode == 0, out.stderr[-600:]
    yield url
    with psycopg.connect(ADMIN.replace("postgresql+psycopg://", "postgresql://"), autocommit=True) as c:
        c.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')


def test_soc_population_and_oews_import_on_postgresql(pgurl, tmp_path):
    from sqlalchemy import func, select

    from src.knowledge_foundation import us_sources as U
    from src.knowledge_foundation.compensation.store import CompensationStoreV2
    from src.knowledge_foundation.graph import OccupationGraph
    from src.knowledge_foundation.registry import SourceRegistry
    from src.knowledge_foundation.taxonomy import TaxonomyCatalogue
    from src.persistence import CompensationRecordV2Row, make_engine, make_session_factory
    from tests import test_us_sources_p10cf2a as T

    s, d, o = tmp_path / "s.xlsx", tmp_path / "d.xlsx", tmp_path / "o.xlsx"
    T._structure(s)
    T._definitions(d)
    T._oews(o, [T._row("11-1010", "broad"), T._row("11-1010", "detailed"), T._row("11-1011", "detailed"), T._row("21-1018", "detailed")])
    sf = make_session_factory(make_engine(pgurl))
    tax, reg, g = TaxonomyCatalogue(sf), SourceRegistry(sf), OccupationGraph(sf)
    tax.seed()
    tax.ensure("soc", "2018", status="current", acquisition_status="available_locally", code_pattern="[0-9]{2}-[0-9]{4}")
    for sid in (U.SOC_SOURCE, U.OEWS_SOURCE):
        reg.register(sid, origin="authorised_manual", publisher="Synthetic official publisher", dataset_name="Synthetic dataset", dataset_version="E", precedence_category="national_official_occupation_statistics")
    T._approve(reg, U.OEWS_SOURCE)
    st, defs = U.parse_soc_structure(s), U.parse_soc_definitions(d)
    assert U.populate_soc_graph(g, st, defs)["nodes_total"] == 11 and U.populate_soc_graph(g, st, defs)["nodes_added"] == 0
    rows, _ = U.parse_oews_national(o)
    recs, rep = U.oews_v2_records(rows, {n.code: n.level for n in st}, archive_sha256="f" * 64)
    store = CompensationStoreV2(sf, reg, g)
    assert store.import_records(recs, source_ref=U.OEWS_SOURCE, source_edition="May 2025", mode="production").added == len(recs)
    assert store.import_records(recs, source_ref=U.OEWS_SOURCE, source_edition="May 2025", mode="production").already_imported
    with sf() as s2:
        assert s2.scalar(select(func.count()).select_from(CompensationRecordV2Row)) == len(recs) == rep["records"]
