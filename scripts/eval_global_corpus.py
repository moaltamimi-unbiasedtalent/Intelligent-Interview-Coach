#!/usr/bin/env python
"""P10C-G global evaluation corpus and regression runner (GKB-16 and GKB-17). Offline and deterministic: it rebuilds throwaway fixture stores from the committed SYNTHETIC corpus, runs the
corpus, the governance and negative-regression checks and the five existing P10C evaluators, repeats the run to prove determinism, writes machine-readable results and disposes of what it
created. Any failure exits 1 (CI fails). It touches no developer store, makes no network call, uses no paid model and approves or qualifies nothing. Exit 0 is NOT a coverage, source-qualification or
production claim: the 412-case product coverage (95% gate) is measured separately by ``check_product_coverage_baseline.py`` and remains BELOW GATE.

    python scripts/eval_global_corpus.py [--repeat N] [--json PATH]
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import tests.conftest  # noqa: E402,F401  (test isolation: temporary databases only, no developer store)

from src.knowledge_foundation import global_eval as G  # noqa: E402
from src.knowledge_foundation.pathsafe import output_is_protected  # noqa: E402

EXISTING = ("eval_knowledge_foundation", "eval_occupation_resolver", "eval_compensation_v2", "eval_country_foundations", "eval_global_fallback")


def run_existing() -> dict:
    out = {}
    for name in EXISTING:
        spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
        mod = importlib.util.module_from_spec(spec)
        t0 = time.perf_counter()
        spec.loader.exec_module(mod)
        result = mod.run()
        checks = result[0] if isinstance(result, tuple) else result      # (checks, meta) or the checks mapping alone
        failed = sorted(k for k, (ok, _d) in checks.items() if not ok)
        out[name] = {"checks": len(checks), "failed": failed, "seconds": round(time.perf_counter() - t0, 2)}
    return out


def latency() -> dict:
    import tempfile

    from src.knowledge_foundation.compensation import fixtures as F
    from src.persistence import init_db, make_engine, make_session_factory

    corpus = G.load_corpus()
    d = Path(tempfile.mkdtemp(prefix="p10cg_lat_"))
    e = make_engine(f"sqlite:///{d / 'l.db'}")
    try:
        init_db(e)
        t0 = time.perf_counter()
        world = F.load_world(make_session_factory(e), corpus)
        rebuild = time.perf_counter() - t0
        xs = []
        for c in corpus["cases"]:
            s0 = time.perf_counter()
            world.resolver.resolve(F._request(c))
            xs.append((time.perf_counter() - s0) * 1000)
        xs.sort()
        return {"fixture_rebuild_seconds": round(rebuild, 3), "resolve_samples": len(xs), "resolve_p50_ms": round(statistics.median(xs), 2), "resolve_p95_ms": round(xs[int(len(xs) * .95)], 2), "resolve_max_ms": round(xs[-1], 2)}
    finally:
        e.dispose()
        import shutil
        shutil.rmtree(d, ignore_errors=True)


def metric_separation() -> dict:
    """The five coverage notions, kept apart. REPORTED figures are read from committed counts-only artifacts; only E is measured by this run."""
    out = {"E_synthetic_evaluation": "measured by this run (see corpus and governance)"}
    base = ROOT / "evaluations/product_coverage/baseline_gate_status.json"
    if base.exists():
        prof = json.loads(base.read_text())["profiles"]
        out["A_candidate_runtime_product_coverage"] = {p: f"{v['sufficient']}/{v['cases']} (BELOW the 95% gate; REPORTED from the committed baseline; measured by check_product_coverage_baseline.py)" for p, v in prof.items()}
    pk = ROOT / "docs/capstone/p10/p10c_f2a/human_review_packet.json"
    if pk.exists():
        d = json.loads(pk.read_text())
        out["B_offline_structural_coverage"] = "5 of 7 US compensation cases resolve in the isolated database (REPORTED from the P10C-F2A packet; internal mode; not candidate coverage)"
        out["C_engineering_checked_evidence"] = f"{d['baseline']['record_states'].get('engineering_checked', 0)} OEWS records and {d['baseline']['alias_states'].get('engineering_checked', 0)} aliases engineering-checked (REPORTED; isolated database)"
        out["D_human_qualified_source_coverage"] = f"{d['baseline']['record_states'].get('qualified', 0)} records and {d['baseline']['alias_states'].get('qualified', 0)} aliases human-qualified (REPORTED)"
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repeat", type=int, default=2)
    ap.add_argument("--json", default=None)
    a = ap.parse_args(argv)
    if a.json and output_is_protected(a.json, ROOT):
        raise SystemExit("refusing to write inside a protected location")
    t0 = time.perf_counter()
    runs = [G.run_all() for _ in range(max(1, a.repeat))]
    first = runs[0]
    hashes = sorted({r["determinism_hash"] for r in runs})
    existing = run_existing()
    existing_ok = all(not v["failed"] for v in existing.values())
    ok = all(r["ok"] for r in runs) and len(hashes) == 1 and existing_ok
    res = {**first, "ok": ok, "repeat": len(runs), "deterministic_across_runs": len(hashes) == 1, "runs_total_seconds": [r["timing_seconds"]["total"] for r in runs], "existing_evaluators": existing,
           "latency": latency(), "metric_separation": metric_separation(), "wall_seconds": round(time.perf_counter() - t0, 2),
           "claims": {"product_ready": False, "human_qualified": False, "source_qualified_globally": False, "runtime_approved": False, "product_coverage_gate_passed": False}}
    if a.json:
        Path(a.json).write_text(json.dumps(res, indent=1), encoding="utf-8")
    c, m = first["corpus"], first["matrix"]
    print(f"global corpus v{first['corpus_version']}: {c['passed']}/{c['total']} cases | governance {sum(g['ok'] for g in first['governance'])}/{len(first['governance'])} | "
          f"required tags {m['exercised']}/{m['required_tags']} | repeat {len(runs)} deterministic={len(hashes) == 1} | existing evaluators {'OK' if existing_ok else 'FAIL'} | {res['wall_seconds']}s")
    for name, v in existing.items():
        print(f"  {name}: {v['checks']} checks, failed {v['failed'] or 'none'}")
    if not ok:
        print("FAIL:", {"integrity": first["fixture_integrity_errors"], "missing_tags": m["missing_tags"], "failing_tags": m["failing_tags"], "failed_cases": [r["id"] for r in c["cases"] if not r["ok"]][:10],
                        "failed_governance": [g["id"] for g in first["governance"] if not g["ok"]], "hashes": hashes, "existing_failed": {k: v["failed"] for k, v in existing.items() if v["failed"]}})
    print("RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
