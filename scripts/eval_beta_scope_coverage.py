"""Beta-scope coverage report (package 02E): BOTH measures side by side. Offline, read-only, deterministic, no provider call.

    python scripts/eval_beta_scope_coverage.py [--json PATH]

Prints the preserved historical gate (read from its recorded baseline, unchanged) and the frozen beta-scope measure (from the approval register),
then checks the invariants below and exits 1 if any fails. It is a REPORT with integrity checks, not a pass/fail of coverage: the beta-scope
measure has no threshold (OD-COVERAGE) and with no approved source its verdict is NO_APPROVED_SCOPE. PG-05 is never claimed.

Invariants: both measures present; the historical record still says 386 of 412 (developer_local) and 258 of 412 (clean_checkout) against 392 and
FAIL; the frozen case set matches its hash and equals its generator; the beta verdict follows the register (empty register -> NO_APPROVED_SCOPE).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.copilot.evaluation import beta_scope_coverage as B  # noqa: E402


def check(report: dict) -> list[str]:
    bad: list[str] = []
    if "historical_gate" not in report or "beta_scope" not in report:
        return ["both_measures_not_reported_together"]
    prof = report["historical_gate"]["profiles"]
    for name, suff in (("developer_local", 386), ("clean_checkout", 258)):
        p = prof.get(name)
        if not p or (p["sufficient"], p["cases"], p["required_for_gate"], p["verdict"]) != (suff, 412, 392, "FAIL"):
            bad.append(f"historical_record_changed:{name}")
    if report["historical_gate"].get("unchanged") is not True:
        bad.append("historical_not_marked_unchanged")
    cases, digest = B.load_cases()
    if B._canonical(B.generate_candidate_cases()) != B.CASES_PATH.read_bytes():
        bad.append("case_set_differs_from_generator")
    beta = report["beta_scope"]
    if beta["dataset"]["sha256"] != digest:
        bad.append("dataset_hash_not_recorded")
    if beta["in_scope_cases"] == 0 and beta["verdict"] != "NO_APPROVED_SCOPE":
        bad.append("empty_scope_not_labelled")
    if beta["verdict"] == "NO_APPROVED_SCOPE" and (beta["percent"] is not None or beta["sufficient"] is not None):
        bad.append("empty_scope_reports_a_figure")
    if report.get("pg_05_claimed") is not False:
        bad.append("pg_05_claimed")
    return bad


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", metavar="PATH", default=None, help="also write the report as JSON")
    args = ap.parse_args(argv)
    report = B.report_both()
    h, b = report["historical_gate"], report["beta_scope"]
    print(report["reporting_rule"])
    print("\nHISTORICAL GATE (preserved unchanged; read from the recorded baseline)")
    for name, p in h["profiles"].items():
        print(f"  {name:15s} {p['sufficient']} of {p['cases']} ({p['percent']}%)  required {p['required_for_gate']}  -> {p['verdict']}")
    print("\nBETA-SCOPE MEASURE (separate; NOT the historical gate)")
    print(f"  approval register: features={len(b['register']['enabled_features'])} markets={len(b['register']['approved_markets'])} "
          f"qualified sources={len(b['register']['qualified_sources'])} problems={b['register']['problems']}")
    print(f"  candidate cases: {b['dataset']['candidate_cases']}  in scope: {b['in_scope_cases']}  verdict: {b['verdict']}")
    print(f"  {b['statement']}")
    print("\nPG-05 is NOT claimed met.")
    problems = check(report)
    if args.json:
        out = Path(args.json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    if problems:
        print("INVARIANT VIOLATIONS: " + ", ".join(problems), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
