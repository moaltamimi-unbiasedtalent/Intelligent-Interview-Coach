#!/usr/bin/env python
"""P10C-G product-coverage regression guard. Runs the EXISTING 412-case evaluator (unchanged) in an isolated results directory and compares its per-case outcome with the committed baseline of the
matching ENVIRONMENT PROFILE. It reports TWO separate judgments and never merges them:

  REGRESSION STATUS      PASS or FAIL  - a case that was sufficient in the baseline and is not now (even when the total is unchanged), a lower sufficient count, a changed denominator or case-id
                                         set, a missing or malformed baseline, an unknown or ambiguous environment, an evaluator failure or malformed output are all FAIL (exit 1).
  PRODUCT COVERAGE GATE  BELOW_GATE or AT_OR_ABOVE_GATE_REPORTED against the unchanged 95% threshold (392 of 412). A regression PASS never implies the gate passed; the owner accepted the current
                         BELOW_GATE baselines for the Capstone engineering scope as an ACCEPTED LIMITATION, not a pass.

Environment profiles (the evaluator reads git-ignored local knowledge stores when they exist, so the result depends on the environment; profiles are never combined):
  developer_local  all of the local stores below exist
  clean_checkout   none of the local stores below exists (tracked files only, CI-like)
  anything else (a mix) is AMBIGUOUS and fails safely; an explicit ``--profile`` (or ``ASK4MO_COVERAGE_PROFILE``) must agree with the detected stores or the run fails. CI sets clean_checkout explicitly.

A normal run is READ-ONLY. ``--update-profile`` is an explicit maintenance action: it requires ``--reason``, is refused in CI, records the change (previous and new counts and ids, added and resolved
failures, whether it weakens the baseline, the reason) in the baseline ``history`` and, when it would WEAKEN the baseline, is refused unless ``--owner-authorization`` names an existing tracked
document (its path and SHA-256 are recorded; no approval is ever fabricated). Every baseline change is therefore visible in the pull-request diff.

    python scripts/check_product_coverage_baseline.py [--profile P] [--json PATH] [--report-md PATH]
    python scripts/check_product_coverage_baseline.py --update-profile --reason "..." [--owner-authorization docs/...]      (maintenance; never CI)
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src.knowledge_foundation.pathsafe import output_is_protected  # noqa: E402

BASELINE = ROOT / "evaluations/product_coverage/baseline_gate_status.json"
# P10D-R1: the SOURCE-BACKED coverage baseline (a different, versioned measurement). The legacy baseline above keeps its historical meaning and is never rewritten by it.
BASELINE_V2 = ROOT / "evaluations/product_coverage/baseline_source_backed_v2.json"
V2_SCHEMA = "p10d-r1-source-backed-coverage-baseline/1"
CASES = ROOT / "evaluations/product_coverage/cases.json"
GATE_PERCENT, TOTAL = 95, 412
PROFILES = ("developer_local", "clean_checkout")
STORES = ("data/knowledge/roles.db", "data/knowledge/compensation.db", "data/knowledge/labour_market.db", "data/knowledge/competencies.db", "data/knowledge/credentials.db", "data/chroma/chroma.sqlite3")


class GuardError(Exception):
    """A safe failure: the guard could not (or must not) reach a verdict. Carries no case content."""


def store_report(root: Path = ROOT) -> dict[str, bool]:
    return {s: (root / s).exists() for s in STORES}


def detect_profile(stores: dict[str, bool]) -> str:
    present = [k for k, v in stores.items() if v]
    if len(present) == len(stores):
        return "developer_local"
    if not present:
        return "clean_checkout"
    raise GuardError("the environment is ambiguous: some local knowledge stores exist and some do not (" + ", ".join(sorted(present)) + " present); refusing to choose a baseline")


def resolve_profile(requested: str | None, stores: dict[str, bool]) -> str:
    if requested is not None and requested != "auto" and requested not in PROFILES:
        raise GuardError(f"unknown environment profile {requested!r}")
    detected = detect_profile(stores)
    if requested in PROFILES and requested != detected:
        raise GuardError(f"profile {requested} was requested but the detected stores indicate {detected}")
    return detected


def case_ids(path: Path = CASES) -> list[str]:
    return sorted(c["id"] for c in json.loads(path.read_text(encoding="utf-8"))["cases"])


def ids_digest(ids: list[str]) -> str:
    return hashlib.sha256("\n".join(sorted(ids)).encode()).hexdigest()


def parse_results(rows: list[dict], expected_ids: list[str]) -> dict:
    """Validate the evaluator output and summarise it. Anything malformed is a GuardError (fail safe)."""
    if not rows:
        raise GuardError("the evaluator produced no rows")
    for r in rows:
        if "id" not in r or r.get("insufficient_ok") not in ("True", "False"):
            raise GuardError("malformed evaluator output: a row lacks an id or a True/False insufficient_ok value")
    ids = [r["id"] for r in rows]
    if len(ids) != len(set(ids)):
        raise GuardError("malformed evaluator output: duplicate case ids")
    if sorted(ids) != sorted(expected_ids):
        raise GuardError("the evaluated case identifiers differ from cases.json")
    bad = sorted(r["id"] for r in rows if r["insufficient_ok"] == "False")
    return {"cases": len(rows), "sufficient": len(rows) - len(bad), "insufficient": len(bad), "insufficient_case_ids": bad, "case_ids_sha256": ids_digest(ids)}


def parse_results_v2(rows: list[dict], expected_ids: list[str]) -> dict:
    """The V2 (source-backed) summary of the SAME evaluator rows. A row without a True/False ``source_backed_ok`` is malformed output (fail safe, never a skipped check)."""
    for r in rows:
        if r.get("source_backed_ok") not in ("True", "False") or r.get("coverage_basis") is None:
            raise GuardError("malformed evaluator output: a row lacks the V2 source-backed columns (source_backed_ok, coverage_basis)")
    legacy = parse_results(rows, expected_ids)               # also validates ids, uniqueness and the denominator
    bad = sorted(r["id"] for r in rows if r["source_backed_ok"] == "False")
    basis: dict[str, int] = {}
    for r in rows:
        basis[r["coverage_basis"]] = basis.get(r["coverage_basis"], 0) + 1
    return {"cases": len(rows), "sufficient": len(rows) - len(bad), "insufficient": len(bad), "insufficient_case_ids": bad, "case_ids_sha256": legacy["case_ids_sha256"], "basis": dict(sorted(basis.items()))}


def run_evaluator() -> list[dict]:
    out = Path(tempfile.mkdtemp(prefix="ask4mo_pc_guard_"))
    env = {**os.environ, "ASK4MO_EVAL_OUT": str(out)}
    env.pop("ASK4MO_EVAL_WRITE", None)
    proc = subprocess.run([sys.executable, str(ROOT / "scripts/eval_product_coverage.py")], cwd=ROOT, env=env, capture_output=True, text=True, timeout=900)
    if proc.returncode != 0:
        raise GuardError("the product-coverage evaluator failed to run (exit " + str(proc.returncode) + ")")
    path = out / "results.csv"
    if not path.exists():
        raise GuardError("the evaluator wrote no results.csv")
    with path.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def compare(current: dict, baseline: dict | None) -> dict:
    """Pure comparison (no I/O). ``regression_status`` and ``product_coverage_gate`` are separate fields; ``ok`` is the regression verdict only."""
    need = -(-TOTAL * GATE_PERCENT // 100)
    out = {"required_sufficient_for_gate": need, "gate_percent": GATE_PERCENT, "current": {k: v for k, v in current.items() if k != "insufficient_case_ids"}, "regressions": [], "improvements": [],
           "baseline_present": baseline is not None, "denominator_changed": current["cases"] != TOTAL, "case_ids_changed": False, "failures": []}
    if baseline is None:
        out["failures"].append("no committed baseline for this environment profile")
    else:
        base_bad, now_bad = set(baseline["insufficient_case_ids"]), set(current["insufficient_case_ids"])
        out["regressions"] = sorted(now_bad - base_bad)
        out["improvements"] = sorted(base_bad - now_bad)
        out["baseline_sufficient"] = baseline["sufficient"]
        out["case_ids_changed"] = bool(baseline.get("case_ids_sha256")) and baseline["case_ids_sha256"] != current.get("case_ids_sha256")
        if out["regressions"]:
            out["failures"].append(f"{len(out['regressions'])} previously sufficient case(s) are now insufficient")
        if current["sufficient"] < baseline["sufficient"]:
            out["failures"].append("the sufficient count is lower than the baseline")
    if out["denominator_changed"]:
        out["failures"].append("the denominator changed")
    if out["case_ids_changed"]:
        out["failures"].append("the case identifiers changed")
    out["regression_status"] = "PASS" if not out["failures"] else "FAIL"
    out["ok"] = out["regression_status"] == "PASS"
    out["product_coverage_gate"] = "AT_OR_ABOVE_GATE_REPORTED" if current["sufficient"] >= need else "BELOW_GATE"
    out["status"] = out["product_coverage_gate"]                                   # kept for earlier consumers: the GATE status, never the regression verdict
    out["owner_disposition"] = ("ACCEPTED_FOR_CAPSTONE_ENGINEERING_SCOPE (an accepted limitation, not a pass)" if out["product_coverage_gate"] == "BELOW_GATE"
                                else "baseline update and owner review required")
    return out


def commit_sha() -> str:
    sha = os.environ.get("GITHUB_SHA")
    if sha:
        return sha
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, timeout=20).stdout.strip() or "unknown"
    except Exception:  # noqa: BLE001
        return "unknown"


def tracked_files_modified() -> bool | None:
    try:
        return subprocess.run(["git", "diff", "--quiet", "HEAD"], cwd=ROOT, capture_output=True, timeout=30).returncode != 0
    except Exception:  # noqa: BLE001
        return None


def report(profile: str, stores: dict[str, bool], current: dict, res: dict) -> dict:
    return {"schema": "p10c-g-product-coverage-status/2", "profile": profile, "commit": commit_sha(), "tracked_files_modified_since_commit": tracked_files_modified(), "executed_at": datetime.now(timezone.utc).isoformat(), "store_availability": stores,
            "corpus": {"cases_file": "evaluations/product_coverage/cases.json", "case_ids_sha256": current["case_ids_sha256"], "cases": current["cases"]}, "total_cases": current["cases"],
            "sufficient": current["sufficient"], "insufficient": current["insufficient"], **{k: res[k] for k in ("regressions", "improvements", "required_sufficient_for_gate", "gate_percent", "regression_status", "product_coverage_gate", "owner_disposition",
                                                                                                                       "failures", "baseline_present", "denominator_changed", "case_ids_changed")},
            "note": "REGRESSION STATUS and PRODUCT COVERAGE GATE are separate judgments. The profiles (developer_local, clean_checkout) are different measurements and are never combined; neither is a pass against the 95% gate."}


def render_md(rep: dict) -> str:
    present = [k for k, v in rep["store_availability"].items() if v]
    stores = ", ".join(present) if present else "none (tracked files only)"
    return "\n".join([f"# Product coverage status ({rep['profile']})", "", f"- commit `{rep['commit']}`, executed {rep['executed_at']}", f"- environment profile: **{rep['profile']}**; local stores present: {stores}",
                      f"- cases {rep['total_cases']}, sufficient {rep['sufficient']}, insufficient {rep['insufficient']}, threshold {rep['gate_percent']}% = {rep['required_sufficient_for_gate']} sufficient required",
                      f"- **REGRESSION STATUS: {rep['regression_status']}** (regressions {len(rep['regressions'])}, improvements {len(rep['improvements'])})", f"- **PRODUCT COVERAGE GATE: {rep['product_coverage_gate']}**",
                      f"- owner disposition: {rep['owner_disposition']}", "", rep["note"], ""])


# ------------------------------------------------------------------------------------------------------------------------------------------ maintenance
def plan_update(profile: str, current: dict, data: dict, reason: str | None, owner_authorization: str | None, root: Path = ROOT, env: dict | None = None) -> dict:
    """Pure decision for a baseline update. Raises GuardError when the update must be refused; returns the history record when it may proceed."""
    env = os.environ if env is None else env
    if env.get("GITHUB_ACTIONS") or env.get("CI"):
        raise GuardError("baseline updates are never performed in CI")
    if profile not in PROFILES:
        raise GuardError("unknown environment profile")
    if not (reason or "").strip():
        raise GuardError("a baseline update requires --reason")
    prev = data.get("profiles", {}).get(profile)
    prev_ids = prev["insufficient_case_ids"] if prev else []
    added, resolved = sorted(set(current["insufficient_case_ids"]) - set(prev_ids)), sorted(set(prev_ids) - set(current["insufficient_case_ids"]))
    weakens = bool(prev) and (bool(added) or current["sufficient"] < prev["sufficient"] or current["cases"] != prev["cases"])
    auth = None
    if weakens:
        if not owner_authorization:
            raise GuardError("this update WEAKENS the baseline: it is refused without --owner-authorization naming a tracked document")
        p = (root / owner_authorization).resolve()
        if root.resolve() not in p.parents or not p.is_file() or subprocess.run(["git", "ls-files", "--error-unmatch", owner_authorization], cwd=root, capture_output=True).returncode != 0:
            raise GuardError("the owner authorization must be an existing document tracked in this repository")
        auth = {"path": owner_authorization, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
    return {"recorded_on": datetime.now(timezone.utc).date().isoformat(), "profile": profile, "reason": reason.strip(), "previous_sufficient": prev["sufficient"] if prev else None, "new_sufficient": current["sufficient"],
            "previous_insufficient_case_ids": prev_ids, "new_insufficient_case_ids": current["insufficient_case_ids"], "added_failures": added, "resolved_failures": resolved, "weakens_baseline": weakens,
            "owner_authorization": auth}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default=None)
    ap.add_argument("--report-md", default=None)
    ap.add_argument("--profile", default=os.environ.get("ASK4MO_COVERAGE_PROFILE") or "auto")
    ap.add_argument("--update-profile", action="store_true")
    ap.add_argument("--metric", choices=("legacy", "source_backed"), default="legacy", help="which baseline --update-profile maintains (the two metrics are separate and never merged)")
    ap.add_argument("--reason", default=None)
    ap.add_argument("--owner-authorization", default=None)
    a = ap.parse_args(argv)
    for out in (a.json, a.report_md):
        if out and output_is_protected(out, ROOT):
            print("refusing to write inside a protected location")
            return 2
    try:
        stores = store_report()
        profile = resolve_profile(a.profile, stores)
        data = json.loads(BASELINE.read_text(encoding="utf-8")) if BASELINE.exists() else {"schema": "p10c-g-product-coverage-baseline/2", "profiles": {}, "history": []}
        eval_rows = run_evaluator()
        current = parse_results(eval_rows, case_ids())
        data_v2 = json.loads(BASELINE_V2.read_text(encoding="utf-8")) if BASELINE_V2.exists() else {"schema": V2_SCHEMA, "profiles": {}, "history": []}
        if a.update_profile:
            if a.metric == "source_backed":
                cur2 = parse_results_v2(eval_rows, case_ids())
                rec = plan_update(profile, cur2, data_v2, a.reason, a.owner_authorization)
                data_v2["profiles"][profile] = {**cur2, "recorded_on": rec["recorded_on"], "environment_stores": stores}
                data_v2.setdefault("history", []).append(rec)
                BASELINE_V2.write_text(json.dumps(data_v2, indent=1) + "\n", encoding="utf-8")
                print(f"SOURCE-BACKED baseline for profile {profile} updated: {cur2['sufficient']}/{cur2['cases']} (weakens: {rec['weakens_baseline']}); review the diff")
                return 0
            rec = plan_update(profile, current, data, a.reason, a.owner_authorization)
            data["profiles"][profile] = {**current, "recorded_on": rec["recorded_on"], "environment_stores": stores}
            data.setdefault("history", []).append(rec)
            BASELINE.write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8")
            print(f"baseline for profile {profile} updated: {current['sufficient']}/{current['cases']} (weakens: {rec['weakens_baseline']}); review the diff")
            return 0
        res = compare(current, data.get("profiles", {}).get(profile))
        cur2 = parse_results_v2(eval_rows, case_ids())
        res2 = compare(cur2, data_v2.get("profiles", {}).get(profile))               # independent regression checks for the source-backed measurement
    except GuardError as exc:
        print("GUARD FAILURE (fail safe):", exc)
        return 1
    rep = report(profile, stores, current, res)
    rep["source_backed"] = {"baseline_file": "evaluations/product_coverage/baseline_source_backed_v2.json", "sufficient": cur2["sufficient"], "insufficient": cur2["insufficient"], "basis": cur2["basis"],
                            **{k: res2[k] for k in ("regressions", "improvements", "regression_status", "product_coverage_gate", "failures", "baseline_present", "denominator_changed", "case_ids_changed")},
                            "note": "A different measurement from the legacy count: it counts only real-origin, country-applicable, provenance-complete evidence (or an accepted abstention). Never merged with the legacy figure."}
    if a.json:
        Path(a.json).write_text(json.dumps(rep, indent=1), encoding="utf-8")
    if a.report_md:
        Path(a.report_md).write_text(render_md(rep), encoding="utf-8")
    print(f"product coverage [{profile}]: {current['sufficient']}/{current['cases']} sufficient ({100 * current['sufficient'] / current['cases']:.1f}%) | gate {GATE_PERCENT}% needs {res['required_sufficient_for_gate']} | "
          f"REGRESSION STATUS {res['regression_status']} | PRODUCT COVERAGE GATE {res['product_coverage_gate']} | regressions {len(res['regressions'])} | improvements {len(res['improvements'])}")
    for f in res["failures"]:
        print("FAIL:", f)
    if res["regressions"]:
        print("REGRESSED CASES:", ", ".join(res["regressions"][:20]))
    print(f"source-backed coverage [{profile}]: {cur2['sufficient']}/{cur2['cases']} sufficient ({100 * cur2['sufficient'] / cur2['cases']:.1f}%) basis {cur2['basis']} | gate {GATE_PERCENT}% needs {res2['required_sufficient_for_gate']} | "
          f"REGRESSION STATUS {res2['regression_status']} | PRODUCT COVERAGE GATE {res2['product_coverage_gate']} | regressions {len(res2['regressions'])} | improvements {len(res2['improvements'])}")
    for f in res2["failures"]:
        print("FAIL (source-backed):", f)
    if res2["regressions"]:
        print("REGRESSED CASES (source-backed):", ", ".join(res2["regressions"][:20]))
    return 0 if (res["ok"] and res2["ok"]) else 1


if __name__ == "__main__":
    sys.exit(main())
