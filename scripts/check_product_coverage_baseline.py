#!/usr/bin/env python
"""P10C-G product-coverage regression guard. Runs the EXISTING 412-case evaluator (unchanged) in an isolated results directory and compares its per-case outcome with the committed baseline of the
matching ENVIRONMENT PROFILE. It fails (exit 1) on any regression: a case that was sufficient in the baseline and is not now, or a lower sufficient count. It never reports a pass against the 95%
product gate: status is BELOW_GATE (the owner accepted the current baseline for the Capstone engineering scope as an ACCEPTED LIMITATION, not a pass) and is reported separately per profile.

Profiles (the evaluator reads git-ignored local knowledge stores when they exist, so the result depends on the environment and the two are never merged):
  developer_local  : ``data/knowledge/roles.db`` exists (a developer machine with the built knowledge stores)
  clean_checkout   : tracked files only (CI-like)
    python scripts/check_product_coverage_baseline.py [--json PATH] [--update-profile]     (--update-profile rewrites the baseline of the CURRENT profile; never used by CI)
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src.knowledge_foundation.pathsafe import output_is_protected  # noqa: E402

BASELINE = ROOT / "evaluations/product_coverage/baseline_gate_status.json"
GATE_PERCENT, TOTAL = 95, 412


def detect_profile() -> str:
    return "developer_local" if (ROOT / "data/knowledge/roles.db").exists() else "clean_checkout"


def run_evaluator() -> list[dict]:
    out = Path(tempfile.mkdtemp(prefix="ask4mo_pc_guard_"))
    env = {**os.environ, "ASK4MO_EVAL_OUT": str(out)}
    env.pop("ASK4MO_EVAL_WRITE", None)
    proc = subprocess.run([sys.executable, str(ROOT / "scripts/eval_product_coverage.py")], cwd=ROOT, env=env, capture_output=True, text=True, timeout=900)
    if proc.returncode != 0:
        raise SystemExit("the product-coverage evaluator failed to run: " + proc.stderr[-300:])
    with (out / "results.csv").open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def summarise(rows: list[dict]) -> dict:
    bad = sorted(r["id"] for r in rows if r["insufficient_ok"] == "False")
    return {"cases": len(rows), "sufficient": len(rows) - len(bad), "insufficient": len(bad), "insufficient_case_ids": bad}


def compare(current: dict, baseline: dict | None) -> dict:
    need = -(-TOTAL * GATE_PERCENT // 100)
    out = {"required_sufficient_for_gate": need, "gate_percent": GATE_PERCENT, "current": {k: v for k, v in current.items() if k != "insufficient_case_ids"}, "regressions": [], "improvements": [], "baseline_present": baseline is not None}
    if baseline is not None:
        base_bad, now_bad = set(baseline["insufficient_case_ids"]), set(current["insufficient_case_ids"])
        out["regressions"] = sorted(now_bad - base_bad)
        out["improvements"] = sorted(base_bad - now_bad)
        out["baseline_sufficient"] = baseline["sufficient"]
    out["denominator_changed"] = current["cases"] != TOTAL
    out["status"] = "AT_OR_ABOVE_GATE_REPORTED" if current["sufficient"] >= need else "BELOW_GATE"
    out["owner_disposition"] = "ACCEPTED_FOR_CAPSTONE_ENGINEERING_SCOPE (an accepted limitation, not a pass)" if out["status"] == "BELOW_GATE" else "baseline update and owner review required"
    out["ok"] = not out["regressions"] and not out["denominator_changed"] and baseline is not None and current["sufficient"] >= baseline["sufficient"]
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default=None)
    ap.add_argument("--update-profile", action="store_true")
    a = ap.parse_args(argv)
    if a.json and output_is_protected(a.json, ROOT):
        raise SystemExit("refusing to write inside a protected location")
    profile = detect_profile()
    current = summarise(run_evaluator())
    data = json.loads(BASELINE.read_text(encoding="utf-8")) if BASELINE.exists() else {"schema": "p10c-g-product-coverage-baseline/1", "profiles": {}}
    if a.update_profile:
        data["profiles"][profile] = current
        BASELINE.write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8")
        print(f"baseline for profile {profile} updated: {current['sufficient']}/{current['cases']}")
        return 0
    res = compare(current, data["profiles"].get(profile))
    res = {"profile": profile, **res, "note": "The two profiles are different measurements (developer-local git-ignored stores versus tracked files only) and are never combined. Neither is a pass against the 95% gate."}
    if a.json:
        Path(a.json).write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(f"product coverage [{profile}]: {current['sufficient']}/{current['cases']} sufficient ({100 * current['sufficient'] / max(current['cases'], 1):.1f}%) | gate {GATE_PERCENT}% needs {res['required_sufficient_for_gate']} | "
          f"status {res['status']} | regressions {len(res['regressions'])} | improvements {len(res['improvements'])}")
    if res["regressions"]:
        print("REGRESSION: previously sufficient cases are now insufficient:", ", ".join(res["regressions"][:20]))
    if not res["baseline_present"]:
        print(f"no committed baseline for profile {profile}: run with --update-profile once and commit the result")
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
