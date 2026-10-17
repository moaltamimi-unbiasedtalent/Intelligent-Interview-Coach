#!/usr/bin/env python
"""P10C-C Compensation V2 benchmark on SYNTHETIC corpora in a throwaway SQLite database (never a protected store, never a mutating operation on developer data). Reports import
throughput, resolver latency percentiles, SQL statement counts per resolution and peak traced memory for: small and large datasets, multiple countries and source editions, repeated
lookups, conflicting evidence, an unresolvable title and unavailable evidence. ``--out`` is validated before any work (never inside data/ or evaluations/)."""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import tempfile
import time
import tracemalloc
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src.knowledge_foundation.pathsafe import output_is_protected  # noqa: E402

COUNTRIES = ("DE", "FR", "ES", "IT", "NL", "PL", "SE", "AT")


def build(n_occ: int, tmp: Path, editions: int = 1):
    import tests.conftest  # noqa: F401
    from sqlalchemy import event
    from src.knowledge_foundation.aliases import AliasStore
    from src.knowledge_foundation.compensation.resolver import CompensationResolver
    from src.knowledge_foundation.compensation.store import CompensationStoreV2
    from src.knowledge_foundation.graph import OccupationGraph
    from src.knowledge_foundation.occupation_resolver import OccupationResolver
    from src.knowledge_foundation.registry import SourceRegistry
    from src.knowledge_foundation.taxonomy import TaxonomyCatalogue
    from src.persistence import init_db, make_engine, make_session_factory

    engine = make_engine(f"sqlite:///{tmp}/bench.db")
    init_db(engine)
    sf = make_session_factory(engine)
    TaxonomyCatalogue(sf).seed()
    reg, g, a = SourceRegistry(sf), OccupationGraph(sf), AliasStore(sf)
    reg.register("fx_a", origin="synthetic_fixture", publisher="P", dataset_name="D", precedence_category="national_public_employment_service")
    reg.register("fx_b", origin="synthetic_fixture", publisher="P2", dataset_name="D2", precedence_category="national_public_employment_service")
    store = CompensationStoreV2(sf, reg, g)
    keys = []

    def fill(s):
        for i in range(n_occ):
            node = g.add_occupation(f"Synthetic bench {i}", [("isco", "08", f"{i + 1:04d}")], _session=s)
            keys.append(node["occupation_key"])
    g.bulk(fill)
    t = time.perf_counter()
    for ed in range(editions):
        rows = [dict(taxonomy_scheme="isco", taxonomy_edition="08", native_code=f"{i + 1:04d}", occupation_level="detailed", country=c, geography_level="national", currency="EUR", pay_period="annual",
                     pay_basis="gross", measure="median", value=str(30000 + i + j), source_ref="fx_a", source_edition=f"E{ed}", reference_year=2020 + ed) for i in range(n_occ) for j, c in enumerate(COUNTRIES)]
        store.import_records(rows, source_ref="fx_a", source_edition=f"E{ed}", mode="fixture")
    # a second source disagreeing on the first occupations (conflicting evidence)
    store.import_records([dict(taxonomy_scheme="isco", taxonomy_edition="08", native_code=f"{i + 1:04d}", occupation_level="detailed", country="DE", geography_level="national", currency="EUR",
                               pay_period="annual", pay_basis="gross", measure="median", value=str(99999 + i), source_ref="fx_b", source_edition="E0", reference_year=2020 + editions - 1)
                          for i in range(min(n_occ, 50))], source_ref="fx_b", source_edition="E0", mode="fixture")
    imported = round(time.perf_counter() - t, 2)
    counter = {"n": 0}

    @event.listens_for(engine, "before_cursor_execute")
    def _c(conn, cur, st, par, ctx, many):
        counter["n"] += 1
    return CompensationResolver(store, OccupationResolver(g, a), g, reg), keys, counter, imported


def measure(res, keys, counter, fn, n):
    times, queries = [], []
    tracemalloc.start()
    for i in range(n):
        before = counter["n"]
        t = time.perf_counter()
        fn(i)
        times.append((time.perf_counter() - t) * 1000)
        queries.append(counter["n"] - before)
    peak = tracemalloc.get_traced_memory()[1]
    tracemalloc.stop()
    times.sort()
    return {"n": n, "p50_ms": round(statistics.median(times), 3), "p95_ms": round(times[int(0.95 * (len(times) - 1))], 3), "max_ms": round(times[-1], 3), "queries_per_resolution": max(queries),
            "peak_kib": peak // 1024}


def main(argv: list[str] | None = None) -> int:
    from src.knowledge_foundation.compensation.resolver import CompensationRequest
    from src.knowledge_foundation.occupation_resolver import MultilingualRequest
    ap = argparse.ArgumentParser()
    ap.add_argument("--out")
    args = ap.parse_args(argv)
    if args.out and output_is_protected(args.out, ROOT):
        print("refusing to write inside data/ or evaluations/", file=sys.stderr)
        return 2
    report = {"schema": "compensation_v2_benchmark/1", "note": "Synthetic corpora in a throwaway database; no real data; no protected store touched.", "corpora": {}}
    for name, (n_occ, editions) in {"small": (100, 1), "large": (2000, 1), "multi_edition": (500, 3)}.items():
        with tempfile.TemporaryDirectory() as d:
            res, keys, counter, imported = build(n_occ, Path(d), editions)
            req = lambda i, c="FR", **kw: CompensationRequest(occupation=MultilingualRequest(known_occupation_keys=(keys[(i * 7) % n_occ],)), country=c, require_operational=False, **kw)  # noqa: E731
            report["corpora"][name] = {
                "occupations": n_occ, "records_per_edition": n_occ * len(COUNTRIES), "editions": editions, "countries": len(COUNTRIES), "import_seconds": imported,
                "unique_evidence": measure(res, keys, counter, lambda i: res.resolve(req(i)), 100),
                "repeated_lookup": measure(res, keys, counter, lambda i: res.resolve(req(0)), 200),
                "conflicting_evidence": measure(res, keys, counter, lambda i: res.resolve(req(i % 40 if n_occ >= 40 else 0, "DE")), 40),
                "unavailable_evidence_unsupported_market": measure(res, keys, counter, lambda i: res.resolve(req(i, "BE")), 100),
                "unresolvable_title_not_found": measure(res, keys, counter, lambda i: res.resolve(CompensationRequest(occupation=MultilingualRequest(title="bench title nowhere", title_language="en"), country="DE",
                                                                                                     require_operational=False)), 100),
            }
    text = json.dumps(report, indent=1, sort_keys=True) + "\n"
    if args.out:
        dest = Path(args.out).resolve()
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
