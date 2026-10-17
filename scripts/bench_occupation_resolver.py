#!/usr/bin/env python
"""P10C-B resolver benchmark on SYNTHETIC corpora in a throwaway SQLite database (never a protected store, never a mutating operation on developer data). The 'inventory shape' corpus
matches the SIZE of the existing legacy inventory (8,035 occupations, 23,579 aliases) with generated labels - it contains no real content. Reports latency percentiles and peak traced
memory. ``--out`` is validated before any work (never inside data/ or evaluations/)."""

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


def build(n_occ: int, n_alias: int, shared: int, tmp: Path):
    import tests.conftest  # noqa: F401
    from src.knowledge_foundation.aliases import AliasStore
    from src.knowledge_foundation.graph import OccupationGraph
    from src.knowledge_foundation.occupation_resolver import OccupationResolver
    from src.knowledge_foundation.registry import SourceRegistry
    from src.knowledge_foundation.taxonomy import TaxonomyCatalogue
    from src.persistence import init_db, make_engine, make_session_factory

    engine = make_engine(f"sqlite:///{tmp}/bench.db")
    init_db(engine)
    sf = make_session_factory(engine)
    TaxonomyCatalogue(sf).seed()
    SourceRegistry(sf).register("fx_bench", origin="synthetic_fixture")
    g, a = OccupationGraph(sf), AliasStore(sf)
    per = max(1, n_alias // n_occ)

    def fill(s):
        for i in range(n_occ):
            node = g.add_occupation(f"Synthetic bench occupation {i}", [("onet_soc", "31.0", f"99-{i:05d}.00"[:13])] if False else [("esco", "1.2.1", f"http://data.europa.eu/esco/occupation/{i:08x}-0000-0000-0000-000000000000")], _session=s)
            for j in range(per):
                a.add_alias(node["occupation_key"], f"bench label {i} variant {j}", language="en", language_basis="fixture_declared", alias_type="source_synonym", source_ref="fx_bench", _session=s)
            if i < shared:
                a.add_alias(node["occupation_key"], "generic bench title", language="en", language_basis="fixture_declared", alias_type="recognized_title", source_ref="fx_bench", _session=s)
    g.bulk(fill)
    return OccupationResolver(g, a), g, a


def measure(fn, n: int) -> dict:
    times = []
    tracemalloc.start()
    for i in range(n):
        t = time.perf_counter()
        fn(i)
        times.append((time.perf_counter() - t) * 1000)
    peak = tracemalloc.get_traced_memory()[1]
    tracemalloc.stop()
    times.sort()
    return {"n": n, "p50_ms": round(statistics.median(times), 3), "p95_ms": round(times[int(0.95 * (len(times) - 1))], 3), "max_ms": round(times[-1], 3), "peak_kib": peak // 1024}


def main(argv: list[str] | None = None) -> int:
    from src.knowledge_foundation.occupation_resolver import MultilingualRequest
    ap = argparse.ArgumentParser()
    ap.add_argument("--out")
    args = ap.parse_args(argv)
    if args.out and output_is_protected(args.out, ROOT):
        print("refusing to write inside data/ or evaluations/", file=sys.stderr)
        return 2
    report = {"schema": "resolver_benchmark/1", "note": "Synthetic corpora in a throwaway database; sizes mirror the legacy inventory; no real content; no protected store touched.", "corpora": {}}
    for name, (n_occ, n_alias, shared) in {"small": (500, 1500, 5), "medium": (3000, 9000, 50), "inventory_shape": (8035, 23579, 200)}.items():
        with tempfile.TemporaryDirectory() as d:
            t = time.perf_counter()
            r, _g, _a = build(n_occ, n_alias, shared, Path(d))
            built = round(time.perf_counter() - t, 1)
            step = max(1, n_occ // 100)
            report["corpora"][name] = {
                "occupations": n_occ, "aliases": n_alias + shared, "build_seconds": built,
                "unique_exact": measure(lambda i: r.resolve(MultilingualRequest(title=f"bench label {(i * step) % n_occ} variant 0", title_language="en")), 100),
                "unique_folded_fallback": measure(lambda i: r.resolve(MultilingualRequest(title=f"Bénch label {(i * step) % n_occ} variant 0", title_language="en")), 50),
                "high_ambiguity_generic_title": measure(lambda i: r.resolve(MultilingualRequest(title="generic bench title", title_language="en")), 20),
                "repeated_lookup_same_title": measure(lambda i: r.resolve(MultilingualRequest(title="bench label 7 variant 0", title_language="en")), 200),
                "unknown_alias": measure(lambda i: r.resolve(MultilingualRequest(title=f"no such title {i}", title_language="en")), 100),
                "unknown_identifier": measure(lambda i: r.resolve(MultilingualRequest(taxonomy_scheme="esco", taxonomy_code=f"http://data.europa.eu/esco/occupation/ffffffff-0000-0000-0000-{i:012d}")), 100),
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
