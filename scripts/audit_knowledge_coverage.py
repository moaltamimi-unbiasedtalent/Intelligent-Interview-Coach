#!/usr/bin/env python
"""Audit runtime knowledge COVERAGE (Phase 7C, §44).

Read-only. Measures how much of the runtime occupation corpus is backed by each evidence
domain (skills / tasks / knowledge / technology / activities / attributes / compensation /
labour-market / credentials), plus geography coverage kept separate (DE / EU / US / UK), and
— when a retrieval-evaluation report is available — folds in the retrieval-derived quality
metrics (evidence coverage, no-evidence rate, citation completeness, geography correctness,
unknown-role safety).

Never writes runtime data. Exit 0 always (reporting tool); pass ``--json`` for machine output.

Usage:
    python scripts/audit_knowledge_coverage.py
    python scripts/audit_knowledge_coverage.py --json
    python scripts/audit_knowledge_coverage.py --retrieval evaluations/knowledge/retrieval_after.json
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.copilot import constants  # noqa: E402

ROLE_DB = constants.ROLE_DB_PATH
COMP_DB = constants.COMPENSATION_DB_PATH
LM_DB = constants.LABOUR_MARKET_DB_PATH
COMPE_DB = constants.COMPETENCY_DB_PATH
CRED_DB = constants.CREDENTIAL_DB_PATH


def _conn(path):
    return sqlite3.connect(path) if Path(path).is_file() else None


def _distinct_occ(conn, table, col="occupation_code") -> set:
    try:
        return {r[0] for r in conn.execute(f"SELECT DISTINCT {col} FROM {table}")}
    except Exception:  # noqa: BLE001
        return set()


def audit() -> dict:
    report: dict = {"stores_present": {}, "coverage": {}, "geography": {}, "retrieval": None}
    roles = _conn(ROLE_DB)
    if roles is None:
        report["error"] = f"roles store missing at {ROLE_DB} — build the runtime first."
        return report

    total = roles.execute("SELECT COUNT(*) FROM occupations").fetchone()[0]
    report["canonical_occupations"] = total
    report["aliases"] = roles.execute("SELECT COUNT(*) FROM occupation_aliases").fetchone()[0]

    # Occupations backed by each domain (distinct occupation_code with ≥1 row).
    domain_tables = {
        "skills": "occupation_skills", "tasks": "occupation_tasks",
        "knowledge": "occupation_knowledge", "activities": "occupation_activities",
        "relationships": "occupation_relationships", "attributes": "occupation_attributes",
    }
    cov = {}
    for name, table in domain_tables.items():
        n = len(_distinct_occ(roles, table))
        cov[name] = {"occupations": n, "pct": round(100 * n / total, 1) if total else 0.0}
    # technology + education are subsets stored with a type flag.
    try:
        tech = {r[0] for r in roles.execute(
            "SELECT DISTINCT occupation_code FROM occupation_skills WHERE skill_type='technology'")}
        cov["technology"] = {"occupations": len(tech),
                             "pct": round(100 * len(tech) / total, 1) if total else 0.0}
    except Exception:  # noqa: BLE001
        pass
    try:
        edu = {r[0] for r in roles.execute(
            "SELECT DISTINCT occupation_code FROM occupation_attributes "
            "WHERE attr_type IN ('entry_education','on_the_job_training')")}
        cov["education_training"] = {"occupations": len(edu),
                                     "pct": round(100 * len(edu) / total, 1) if total else 0.0}
    except Exception:  # noqa: BLE001
        pass

    # Compensation / labour-market / credentials totals (occupation-linkage where meaningful).
    comp = _conn(COMP_DB)
    if comp:
        report["stores_present"]["compensation"] = True
        crows = comp.execute("SELECT COUNT(*) FROM compensation_records").fetchone()[0]
        by_country = dict(comp.execute(
            "SELECT COALESCE(NULLIF(country,''),'UNKNOWN'), COUNT(*) "
            "FROM compensation_records GROUP BY 1").fetchall())
        cov["compensation"] = {"records": crows, "by_country": by_country}
        report["geography"]["compensation_by_country"] = by_country
        comp.close()
    lm = _conn(LM_DB)
    if lm:
        report["stores_present"]["labour_market"] = True
        lm_counts = {}
        for t in ("labour_market_forecasts", "labour_market_openings",
                  "labour_shortages", "labour_vacancies"):
            try:
                lm_counts[t] = lm.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            except Exception:  # noqa: BLE001
                lm_counts[t] = 0
        cov["labour_market"] = lm_counts
        lm.close()
    compe = _conn(COMPE_DB)
    if compe:
        report["stores_present"]["competencies"] = True
        cov["competencies"] = {"total": compe.execute(
            "SELECT COUNT(*) FROM competencies").fetchone()[0],
            "by_framework": dict(compe.execute(
                "SELECT framework, COUNT(*) FROM competencies GROUP BY framework").fetchall())}
        compe.close()
    cred = _conn(CRED_DB)
    if cred:
        report["stores_present"]["credentials"] = True
        cov["credentials"] = {
            "certifications": cred.execute("SELECT COUNT(*) FROM certifications").fetchone()[0],
            "licences": cred.execute("SELECT COUNT(*) FROM occupational_licences").fetchone()[0]}
        cred.close()
    roles.close()

    # Vector passages.
    try:
        cc = sqlite3.connect(str(Path(constants.CHROMA_PERSIST_DIR) / "chroma.sqlite3"))
        report["vector_passages"] = cc.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0]
        cc.close()
    except Exception:  # noqa: BLE001
        report["vector_passages"] = None

    report["coverage"] = cov

    # Runtime build metadata (provenance of this runtime).
    bm = Path(constants.KNOWLEDGE_DIR if hasattr(constants, "KNOWLEDGE_DIR")
              else "data/knowledge") / "build_metadata.json"
    if bm.is_file():
        m = json.loads(bm.read_text(encoding="utf-8"))
        report["runtime_build"] = {k: m.get(k) for k in
                                   ("runtime_pipeline_version", "git_commit",
                                    "built_at", "normalized_pipeline_version")}
    return report


def _fold_retrieval(report: dict, path: str) -> None:
    p = Path(path)
    if not p.is_file():
        return
    data = json.loads(p.read_text(encoding="utf-8"))
    s = data.get("summary", data)
    report["retrieval"] = {k: s.get(k) for k in (
        "cases", "pass_rate", "safety_pass_rate", "occupation_resolution_rate",
        "evidence_coverage_rate", "citation_completeness_rate", "geography_correctness_rate",
        "unknown_role_safety_rate", "no_evidence_rate")}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Audit runtime knowledge coverage.")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--retrieval", default="evaluations/knowledge/retrieval_after.json",
                    help="Optional retrieval-eval report to fold in.")
    args = ap.parse_args(argv)

    report = audit()
    if "error" not in report:
        _fold_retrieval(report, args.retrieval)

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print("RUNTIME KNOWLEDGE COVERAGE AUDIT")
        if "error" in report:
            print(f"  ERROR: {report['error']}")
            return 0
        print(f"  canonical occupations: {report['canonical_occupations']}")
        print(f"  aliases: {report['aliases']}   vector passages: {report.get('vector_passages')}")
        print("  domain coverage (occupations backed / %):")
        for name, v in report["coverage"].items():
            if isinstance(v, dict) and "pct" in v:
                print(f"    {name:<18} {v['occupations']:>6}  ({v['pct']}%)")
        print(f"  compensation: {report['coverage'].get('compensation')}")
        print(f"  labour_market: {report['coverage'].get('labour_market')}")
        print(f"  competencies: {report['coverage'].get('competencies')}")
        print(f"  credentials: {report['coverage'].get('credentials')}")
        if report.get("retrieval"):
            print(f"  retrieval: {report['retrieval']}")
        if report.get("runtime_build"):
            print(f"  runtime build: {report['runtime_build']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
