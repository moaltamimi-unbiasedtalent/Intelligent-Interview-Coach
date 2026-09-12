#!/usr/bin/env python
"""Deterministic knowledge-retrieval evaluation (Phase 7C, §43).

Runs the real deterministic retrieval layer (``CareerIntelligenceService.retrieve_evidence``)
over a held-out case set and scores it WITHOUT any LLM/provider call. It measures the
properties Phase 7C cares about: occupation/alias resolution, expected domain, evidence
presence, citation completeness, geography correctness, source-family correctness, and — most
importantly — SAFE behaviour on unknown occupations and unsupported geographies (no fabricated
citations, insufficient-evidence is a valid success).

Cases: ``evaluations/knowledge/retrieval_cases.json``.

Exit status: 0 if the pass rate meets --min-pass (default 0.80) AND every safety case passes;
1 otherwise. Safety cases (unknown role / unsupported geography) are hard gates — any failure
fails the run regardless of overall pass rate.

Usage:
    python scripts/eval_knowledge_retrieval.py
    python scripts/eval_knowledge_retrieval.py --json
    python scripts/eval_knowledge_retrieval.py --cases evaluations/knowledge/retrieval_cases.json
    python scripts/eval_knowledge_retrieval.py --out evaluations/knowledge/retrieval_after.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.application.factories import build_career_service  # noqa: E402
from src.copilot.config import CopilotConfig  # noqa: E402

DEFAULT_CASES = "evaluations/knowledge/retrieval_cases.json"


def _evidence_view(res) -> list[dict]:
    out = []
    for e in getattr(res, "evidence", []) or []:
        out.append({
            "source_id": getattr(e, "source_id", "") or "",
            "source_title": getattr(e, "source_title", "") or "",
            "geography": getattr(e, "geography", None),
            "country": getattr(e, "country", None),
            "evidence_type": getattr(e, "evidence_type", None),
        })
    return out


def _score_case(case: dict, res) -> dict:
    """Return per-case checks. Only checks relevant to the case are counted."""
    ev = _evidence_view(res)
    src_families = {e["source_id"] for e in ev if e["source_id"]}
    n = int(getattr(res, "source_count", 0) or 0)
    citations = list(getattr(res, "citations", None) or [])
    insufficient = bool(getattr(res, "insufficient_evidence", False))
    grounded = bool(getattr(res, "occupation_grounded", False))
    general = bool(getattr(res, "general_evidence", False))
    resolved = (getattr(res, "resolved_occupation", "") or "").strip()
    geo = getattr(res, "resolved_geography", None)

    checks: dict[str, bool] = {}
    is_safety = case.get("category") in ("unknown", "unsupported_geography") or case.get("expect_insufficient")

    if case.get("expect_insufficient"):
        # Unknown role: MUST NOT present occupation-specific evidence. Safe outcomes are
        # (a) insufficient/no evidence, or (b) evidence explicitly flagged GENERAL (not
        # occupation-grounded) — never occupation-grounded evidence for an unknown role (§40).
        checks["safe_not_grounded"] = (not grounded) and (
            (insufficient and n == 0 and len(citations) == 0) or general)
    else:
        if case.get("expect_resolution"):
            checks["resolution"] = bool(resolved)
        if not case.get("allow_insufficient"):
            checks["evidence_present"] = n > 0 and not insufficient
        # citation completeness: one citation per evidence item, each with a real source.
        if n > 0:
            checks["citation_complete"] = (
                len(citations) == n
                and all(e["source_title"] and e["source_id"] for e in ev))
        exp_geo = case.get("expected_geography")
        if exp_geo and n > 0:
            # Evidence may be same-country or supra-national/EU context (§18), but NEVER
            # another nation's official statistics (US BLS / UK ONS for a DE query, etc.).
            supra = {"", "EU", "EU27", "EU28", "EA", "EUROPE", "EUROPEAN UNION"}
            allowed = {exp_geo.upper()} | supra
            if exp_geo.upper() == "UK":
                allowed |= {"GB"}
            if exp_geo.upper() == "DE":
                allowed |= supra  # EU aggregates are acceptable broader context for Germany
            wrong = [e for e in ev
                     if str(e["country"] or e["geography"] or "").upper() not in allowed]
            checks["geography_correct"] = len(wrong) == 0
        fams = case.get("expected_source_families")
        if fams and not case.get("allow_insufficient"):
            checks["source_family"] = bool(src_families & set(fams))
        forbidden = case.get("forbidden_source_families")
        if forbidden:
            checks["no_forbidden_source"] = not (src_families & set(forbidden))

    # No fabricated citation ever (a citation without a source is a hard fail).
    checks["no_fabricated_citation"] = all(
        (c.title or c.source) for c in citations) if citations else True

    passed = all(checks.values())
    return {
        "case_id": case["case_id"], "category": case.get("category"), "query": case["query"],
        "passed": passed, "is_safety": is_safety, "checks": checks,
        "observed": {"resolved": resolved, "geography": geo, "lane": getattr(res, "retrieval_lane", ""),
                     "source_count": n, "insufficient": insufficient,
                     "source_families": sorted(src_families)},
    }


def evaluate(cases: list[dict]) -> dict:
    service = build_career_service(CopilotConfig())
    results = []
    for case in cases:
        res = service.retrieve_evidence(case["query"])
        results.append(_score_case(case, res))

    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    safety = [r for r in results if r["is_safety"]]
    safety_passed = sum(1 for r in safety if r["passed"])

    def _rate(pred):
        rel = [r for r in results if pred(r)]
        return round(sum(1 for r in rel if r["passed"]) / len(rel), 4) if rel else None

    # Aggregate metric rates over the checks that applied.
    def _check_rate(name):
        rel = [r for r in results if name in r["checks"]]
        return round(sum(1 for r in rel if r["checks"][name]) / len(rel), 4) if rel else None

    summary = {
        "cases": total, "passed": passed,
        "pass_rate": round(passed / total, 4) if total else 0.0,
        "safety_cases": len(safety), "safety_passed": safety_passed,
        "safety_pass_rate": round(safety_passed / len(safety), 4) if safety else 1.0,
        "occupation_resolution_rate": _check_rate("resolution"),
        "evidence_coverage_rate": _check_rate("evidence_present"),
        "citation_completeness_rate": _check_rate("citation_complete"),
        "geography_correctness_rate": _check_rate("geography_correct"),
        "source_family_rate": _check_rate("source_family"),
        "unknown_role_safety_rate": _rate(lambda r: r["category"] == "unknown"),
        "unsupported_geography_safety_rate": _rate(lambda r: r["category"] == "unsupported_geography"),
        "no_fabricated_citation_rate": _check_rate("no_fabricated_citation"),
        "no_evidence_rate": round(sum(1 for r in results if r["observed"]["insufficient"]) / total, 4) if total else 0.0,
        "by_category": {},
    }
    cats = sorted({r["category"] for r in results if r["category"]})
    for cat in cats:
        rel = [r for r in results if r["category"] == cat]
        summary["by_category"][cat] = {
            "cases": len(rel), "passed": sum(1 for r in rel if r["passed"])}
    return {"summary": summary, "results": results}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Deterministic knowledge-retrieval evaluation.")
    ap.add_argument("--cases", default=DEFAULT_CASES)
    ap.add_argument("--min-pass", type=float, default=0.80)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--out", default=None, help="Write the full report JSON to this path.")
    args = ap.parse_args(argv)

    cases = json.loads(Path(args.cases).read_text(encoding="utf-8"))
    report = evaluate(cases)
    s = report["summary"]

    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(report, indent=2), encoding="utf-8")

    if args.json:
        print(json.dumps(s, indent=2))
    else:
        print("KNOWLEDGE RETRIEVAL EVALUATION")
        print(f"  cases: {s['cases']}  passed: {s['passed']}  pass_rate: {s['pass_rate']}")
        print(f"  safety: {s['safety_passed']}/{s['safety_cases']} (rate {s['safety_pass_rate']})")
        for k in ("occupation_resolution_rate", "evidence_coverage_rate", "citation_completeness_rate",
                  "geography_correctness_rate", "source_family_rate", "unknown_role_safety_rate",
                  "unsupported_geography_safety_rate", "no_fabricated_citation_rate", "no_evidence_rate"):
            print(f"  {k}: {s[k]}")
        print(f"  by_category: {s['by_category']}")
        # show failures
        fails = [r for r in report["results"] if not r["passed"]]
        if fails:
            print(f"\n  {len(fails)} FAILING case(s):")
            for r in fails[:40]:
                bad = [k for k, v in r["checks"].items() if not v]
                print(f"    [{r['category']}] {r['case_id']}: failed {bad} | obs={r['observed']}")

    ok = s["pass_rate"] >= args.min_pass and s["safety_pass_rate"] >= 1.0
    print(f"\nGATE: {'PASS' if ok else 'FAIL'} (min_pass={args.min_pass}, safety must be 1.0)")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
