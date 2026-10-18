#!/usr/bin/env python
"""P10C-E global-fallback benchmark on SYNTHETIC corpora in a throwaway SQLite database (never a protected store, never a mutating operation on developer data). Eleven wider South American
markets plus an ILOSTAT-style source; reports batch-import throughput, resolver latency percentiles, SQL statement counts and peak traced memory for: country-filtered lookups, occupation
resolution by title, fallback through a verified broader group, conflict evaluation, large evidence sets, cross-country queries, unsupported markets and repeated requests. ``--out`` is
validated before any work (never inside data/ or evaluations/)."""

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

SAM = dict(statistic_map={"MED": ("median", 0)}, period_map={"MES": "monthly"}, concept_map={"LAB": "employment_income"}, population_map={"ASAL": "employees"}, method_map={"ENC": "survey"},
           level_by_code_length={4: "detailed"}, code_pattern="[0-9]{4}")
CUR = {"AR": "ARS", "BO": "BOB", "CL": "CLP", "CO": "COP", "EC": "USD", "GY": "GYD", "PY": "PYG", "PE": "PEN", "SR": "SRD", "UY": "UYU", "VE": "VES"}


def build(n_occ: int, tmp: Path):
    import tests.conftest  # noqa: F401
    from sqlalchemy import event
    from src.knowledge_foundation.aliases import AliasStore
    from src.knowledge_foundation.compensation import country_adapters as CA, international as INTL
    from src.knowledge_foundation.compensation.country_import import import_taxonomy_nodes
    from src.knowledge_foundation.compensation.resolver import CompensationResolver
    from src.knowledge_foundation.compensation.store import CompensationStoreV2
    from src.knowledge_foundation.coverage import CoverageMatrix
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
    reg.register("fx_t", origin="synthetic_fixture", publisher="P", dataset_name="D")
    for sid, prov in (("fx_n1", None), ("fx_n2", None), ("fx_ilo", {"international_family": "ilostat"})):
        reg.register(sid, origin="synthetic_fixture", publisher="P", dataset_name="D", precedence_category="eurostat_harmonised" if sid == "fx_ilo" else "national_official_occupation_statistics", **({"provenance": prov} if prov else {}))
    store = CompensationStoreV2(sf, reg, g)
    cov = CoverageMatrix(sf)
    cov.seed()
    import_taxonomy_nodes(g, a, reg, [{"code": f"{1000 + i}", "label": f"Synthetic {i}", "labels": [{"text": f"bench title {i}", "language": "en"}]} for i in range(n_occ)], scheme="isco", edition="08", source_ref="fx_t", mode="fixture")
    t = time.perf_counter()
    total = 0
    for i, (cc, cur) in enumerate(CUR.items()):
        rows = [{"code": f"{1000 + k}", "statistic": "MED", "period": "MES", "value": str(500 + k + i), "concept": "LAB", "population": "ASAL", "method": "ENC", "currency": cur, "basis": "gross",
                 **({"region": r} if r else {})} for k in range(n_occ) for r in ((None, "A") if cc == "AR" else (None,))]
        recs, _ = CA.south_america_records(cc, rows, source_ref="fx_n1", source_edition="E1", taxonomy_edition="08", reference_year=2023, **SAM)
        total += store.import_records(recs, source_ref="fx_n1", source_edition="E1", mode="fixture").added
    import_s = time.perf_counter() - t
    # a second national source disagreeing for Chile on the first 50 occupations (conflict evaluation)
    rows = [{"code": f"{1000 + k}", "statistic": "MED", "period": "MES", "value": str(900 + k), "concept": "LAB", "population": "ASAL", "method": "ENC", "currency": "CLP", "basis": "gross"} for k in range(min(n_occ, 50))]
    store.import_records(CA.south_america_records("CL", rows, source_ref="fx_n2", source_edition="E1", taxonomy_edition="08", reference_year=2023, **SAM)[0], source_ref="fx_n2", source_edition="E1", mode="fixture")
    # an ILOSTAT-style source for every occupation of Chile (international evidence set)
    ilo, _ = INTL.ilostat_records([{"ref_area": "CHL", "classif": f"{1000 + k}", "classification": "ISCO-08", "indicator": "EAR", "unit": "LCU", "time": 2023, "value": str(480 + k)} for k in range(n_occ)],
                                  source_ref="fx_ilo", source_edition="E1", indicator_map={"EAR": {"period": "monthly", "measure": "median", "concept": "employment_income", "population": "employees", "method": "survey", "basis": "gross"}},
                                  currency_by_unit={"LCU": None}, local_currency_unit="LCU", currency_by_country={"CL": "CLP"}, classification_map={"ISCO-08": ("isco", "08")})
    store.import_records(ilo, source_ref="fx_ilo", source_edition="E1", mode="fixture")
    counter = {"n": 0}

    @event.listens_for(engine, "before_cursor_execute")
    def _c(conn, cur, st, par, ctx, many):
        counter["n"] += 1
    return CompensationResolver(store, OccupationResolver(g, a, coverage=cov), g, reg, coverage=cov), counter, {"records_imported": total, "import_seconds": round(import_s, 2), "records_per_second": int(total / max(import_s, 1e-9))}


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
    return {"n": n, "p50_ms": round(statistics.median(times), 3), "p95_ms": round(times[int(0.95 * (len(times) - 1))], 3), "max_ms": round(times[-1], 3), "queries_per_resolution": max(queries), "peak_kib": peak // 1024}


def main(argv: list[str] | None = None) -> int:
    from src.knowledge_foundation.compensation.resolver import CompensationRequest
    from src.knowledge_foundation.occupation_resolver import MultilingualRequest
    ap = argparse.ArgumentParser()
    ap.add_argument("--out")
    args = ap.parse_args(argv)
    if args.out and output_is_protected(args.out, ROOT):
        print("refusing to write inside data/ or evaluations/", file=sys.stderr)
        return 2
    report = {"schema": "global_fallback_benchmark/1", "note": "Synthetic corpora in a throwaway database; no real data; no protected store touched.", "corpora": {}}
    countries = list(CUR)
    for name, n_occ in {"small": 60, "large": 1000}.items():
        with tempfile.TemporaryDirectory() as d:
            res, counter, stats = build(n_occ, Path(d))

            def req(i, country="CL", **kw):
                return CompensationRequest(occupation=MultilingualRequest(taxonomy_scheme="isco", taxonomy_code=f"{1000 + (i * 7) % n_occ}", taxonomy_edition="08"), country=country, require_operational=False, **kw)
            report["corpora"][name] = {
                "occupations": n_occ, "markets": len(CUR), **stats,
                "country_filtered_lookup": measure(counter, lambda i: res.resolve(req(i, countries[i % len(countries)] if i % len(countries) != 2 else "AR")), 200),
                "title_resolution": measure(counter, lambda i: res.resolve(CompensationRequest(occupation=MultilingualRequest(title=f"bench title {(i * 7) % n_occ}", title_language="en"), country="CO", require_operational=False)), 100),
                "international_evidence_precedence": measure(counter, lambda i: res.resolve(req(i + 60 if n_occ > 120 else i, "CL")), 100),
                "conflict_evaluation": measure(counter, lambda i: res.resolve(CompensationRequest(occupation=MultilingualRequest(taxonomy_scheme="isco", taxonomy_code=f"{1000 + i % 40}", taxonomy_edition="08"), country="CL", require_operational=False)), 40),
                "cross_country_queries": measure(counter, lambda i: [res.resolve(req(i, c)) for c in countries[:4]], 25),
                "unsupported_market": measure(counter, lambda i: res.resolve(req(i, "ZZ")), 100),
                "market_without_evidence": measure(counter, lambda i: res.resolve(req(i, "US")), 100),
                "repeated_request": measure(counter, lambda i: res.resolve(req(0)), 200),
                "default_operational_withhold": measure(counter, lambda i: res.resolve(CompensationRequest(occupation=MultilingualRequest(taxonomy_scheme="isco", taxonomy_code=f"{1000 + i % n_occ}", taxonomy_edition="08"), country="CL")), 100),
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
