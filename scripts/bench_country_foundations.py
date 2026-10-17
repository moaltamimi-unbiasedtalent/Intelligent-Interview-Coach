#!/usr/bin/env python
"""P10C-D country-foundation benchmark on SYNTHETIC corpora in a throwaway SQLite database (never a protected store, never a mutating operation on developer data). Reports batch-import
throughput, idempotent re-import time, concurrent duplicate-import behaviour, resolver latency percentiles, SQL statement counts and peak traced memory for small and large datasets with
two taxonomy editions, national and regional filters, conflicting evidence, missing mappings and unapproved evidence. ``--out`` is validated before any work."""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import tempfile
import threading
import time
import tracemalloc
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src.knowledge_foundation.pathsafe import output_is_protected  # noqa: E402

MAPS = dict(statistic_map={"MED": ("median", 0)}, period_map={"HR": "hourly"})
REGIONS = (None, "ON", "QC", "BC", "AB", "MB")


def build(n_occ: int, tmp: Path):
    import tests.conftest  # noqa: F401
    from sqlalchemy import event
    from src.knowledge_foundation.aliases import AliasStore
    from src.knowledge_foundation.compensation import country_adapters as CA
    from src.knowledge_foundation.compensation.country_import import import_taxonomy_nodes
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
    tax, reg, g, a = TaxonomyCatalogue(sf), SourceRegistry(sf), OccupationGraph(sf), AliasStore(sf)
    tax.seed()
    for ed in ("fx-a", "fx-b"):
        tax.ensure("noc", ed, status="unknown", acquisition_status="not_acquired", code_pattern="[0-9]{5}")
    reg.register("fx_t", origin="synthetic_fixture", publisher="P", dataset_name="D")
    for sid in ("fx_p", "fx_q"):
        reg.register(sid, origin="synthetic_fixture", publisher="P", dataset_name="D", precedence_category="national_official_occupation_statistics")
    store = CompensationStoreV2(sf, reg, g)
    t = time.perf_counter()
    for ed in ("fx-a", "fx-b"):
        import_taxonomy_nodes(g, a, reg, [{"code": f"{10000 + i}", "label": f"Synthetic {ed} {i}"} for i in range(n_occ)], scheme="noc", edition=ed, source_ref="fx_t", mode="fixture")
    nodes_s = round(time.perf_counter() - t, 2)
    rows = [{"code": f"{10000 + i}", "statistic": "MED", "period": "HR", "value": str(20 + i % 40), "basis": "gross", **({"region": r} if r else {})} for i in range(n_occ) for r in REGIONS]
    recs, rej = CA.canada_records(rows, source_ref="fx_p", source_edition="E1", taxonomy_edition="fx-a", reference_year=2025, level_by_code_length={5: "detailed"}, **MAPS)
    t = time.perf_counter()
    rep = store.import_records(recs, source_ref="fx_p", source_edition="E1", mode="fixture")
    import_s = time.perf_counter() - t
    t = time.perf_counter()
    again = store.import_records(recs, source_ref="fx_p", source_edition="E1", mode="fixture")
    reimport_s = time.perf_counter() - t
    # a second national source disagreeing on the first 50 occupations (conflicting evidence)
    q, _ = CA.canada_records([{"code": f"{10000 + i}", "statistic": "MED", "period": "HR", "value": str(90 + i), "basis": "gross"} for i in range(min(n_occ, 50))], source_ref="fx_q", source_edition="E1",
                             taxonomy_edition="fx-a", reference_year=2025, level_by_code_length={5: "detailed"}, **MAPS)
    store.import_records(q, source_ref="fx_q", source_edition="E1", mode="fixture")
    counter = {"n": 0}

    @event.listens_for(engine, "before_cursor_execute")
    def _c(conn, cur, st, par, ctx, many):
        counter["n"] += 1
    stats = {"records": rep.added, "rejected_rows": sum(rej.values()) + rep.rejected, "taxonomy_nodes_import_seconds": nodes_s, "records_import_seconds": round(import_s, 2),
             "records_per_second": int(rep.added / max(import_s, 1e-9)), "idempotent_reimport_seconds": round(reimport_s, 3), "reimport_was_noop": bool(again.already_imported and again.added == 0)}
    return CompensationResolver(store, OccupationResolver(g, a), g, reg), counter, stats, (store, recs)


def measure(counter, fn, n):
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


def concurrent_duplicate_import(store, recs, threads: int = 6) -> dict:
    """Identical imports issued concurrently: exactly one batch must win and no record may be duplicated."""
    out = []
    gate = threading.Barrier(threads)
    sample = [r.model_copy(update={"source_edition": "E-concurrent"}) for r in recs[:300]]

    def go():
        gate.wait()
        try:
            out.append(store.import_records(sample, source_ref="fx_p", source_edition="E-concurrent", mode="fixture"))
        except Exception as exc:  # noqa: BLE001
            out.append(type(exc).__name__)
    t = time.perf_counter()
    ts = [threading.Thread(target=go) for _ in range(threads)]
    [x.start() for x in ts]
    [x.join() for x in ts]
    return {"threads": threads, "rows_each": len(sample), "seconds": round(time.perf_counter() - t, 2), "winners": sum(1 for r in out if not isinstance(r, str) and r.added == len(sample)),
            "errors": sum(1 for r in out if isinstance(r, str))}


def main(argv: list[str] | None = None) -> int:
    from src.knowledge_foundation.compensation.resolver import CompensationRequest
    from src.knowledge_foundation.occupation_resolver import MultilingualRequest
    ap = argparse.ArgumentParser()
    ap.add_argument("--out")
    args = ap.parse_args(argv)
    if args.out and output_is_protected(args.out, ROOT):
        print("refusing to write inside data/ or evaluations/", file=sys.stderr)
        return 2
    report = {"schema": "country_foundations_benchmark/1", "note": "Synthetic corpora in a throwaway database; no real data; no protected store touched.", "corpora": {}}
    for name, n_occ in {"small": 100, "large": 2000}.items():
        with tempfile.TemporaryDirectory() as d:
            res, counter, stats, (store, recs) = build(n_occ, Path(d))

            def req(i, region=None, **kw):
                return CompensationRequest(occupation=MultilingualRequest(taxonomy_scheme="noc", taxonomy_code=f"{10000 + (i * 7) % n_occ}", taxonomy_edition="fx-a"), country="CA", region=region, require_operational=False, **kw)
            report["corpora"][name] = {
                "occupations_per_edition": n_occ, "taxonomy_editions": 2, "regions_per_occupation": len(REGIONS), **stats,
                "national_lookup": measure(counter, lambda i: res.resolve(req(i)), 100),
                "regional_filter": measure(counter, lambda i: res.resolve(req(i, "QC")), 100),
                "repeated_lookup": measure(counter, lambda i: res.resolve(req(0)), 200),
                "conflicting_national_sources": measure(counter, lambda i: res.resolve(req(i % 40 if n_occ >= 40 else 0)), 40),
                "second_edition_no_evidence": measure(counter, lambda i: res.resolve(CompensationRequest(occupation=MultilingualRequest(taxonomy_scheme="noc", taxonomy_code=f"{10000 + i % n_occ}", taxonomy_edition="fx-b"),
                                                                                                         country="CA", require_operational=False)), 100),
                "missing_mapping": measure(counter, lambda i: res.resolve(CompensationRequest(occupation=MultilingualRequest(taxonomy_scheme="noc", taxonomy_code="99999", taxonomy_edition="fx-a"), country="CA", require_operational=False)), 100),
                "unapproved_evidence_default_withheld": measure(counter, lambda i: res.resolve(CompensationRequest(occupation=MultilingualRequest(taxonomy_scheme="noc", taxonomy_code=f"{10000 + i % n_occ}",
                                                                                                                                              taxonomy_edition="fx-a"), country="CA")), 100),
                "concurrent_duplicate_import": concurrent_duplicate_import(store, recs),
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
