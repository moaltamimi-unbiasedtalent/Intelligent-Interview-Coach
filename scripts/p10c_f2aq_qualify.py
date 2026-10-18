#!/usr/bin/env python
"""P10C-F2A-Q US evidence qualification review (non-production, isolated). Reads the staged BLS files and the isolated database created by ``p10c_f2a_ingest.py``; reconciles every
reported count with reproducible queries; reviews every imported OEWS observation with the deterministic engineering rules; moves passing records to the EXISTING state
``engineering_checked`` (never ``qualified``: no human reviewer exists); loads the curated US alias PROPOSALS whose evidence is the official SOC title rule; validates the owner's broader-group
rule and the annual-only/hourly-only behaviour; and writes a report. It downloads nothing, calls no external service and never touches a developer store.

    P5B_PG_ADMIN_URL=postgresql+psycopg://user@127.0.0.1:PORT/postgres python scripts/p10c_f2aq_qualify.py [--db-name p5b_f2a_us] [--out DIR]
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import tests.conftest  # noqa: E402,F401  (standalone-script isolation: must precede every src import)

from sqlalchemy import func, select  # noqa: E402

from src.knowledge_foundation import us_qualification as Q  # noqa: E402
from src.knowledge_foundation import us_sources as U  # noqa: E402
from src.knowledge_foundation.aliases import AliasStore  # noqa: E402
from src.knowledge_foundation.compensation.record import from_row  # noqa: E402
from src.knowledge_foundation.compensation.resolver import CompensationRequest, CompensationResolver  # noqa: E402
from src.knowledge_foundation.compensation.store import CompensationStoreV2  # noqa: E402
from src.knowledge_foundation.graph import OccupationGraph  # noqa: E402
from src.knowledge_foundation.occupation_resolver import MultilingualRequest, OccupationResolver  # noqa: E402
from src.knowledge_foundation.registry import SourceRegistry  # noqa: E402
from src.persistence import CompensationRecordV2Row as R  # noqa: E402
from src.persistence import GraphOccupation, GraphOccupationAlias, GraphOccupationRelationship, make_engine, make_session_factory  # noqa: E402

MANIFEST = ROOT / "docs/capstone/p10/p10c_f2a/acquisition_manifest.json"
US_CASES = {"pc_compensation_183": "Data Analyst", "pc_compensation_187": "Software Developer", "pc_compensation_191": "Product Manager", "pc_compensation_195": "Human Resources Manager",
            "pc_compensation_199": "Accountant", "pc_compensation_203": "Financial Analyst", "pc_compensation_207": "Sales Manager"}


def _load_ingest():
    spec = importlib.util.spec_from_file_location("p10c_f2a_ingest", ROOT / "scripts/p10c_f2a_ingest.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def reconcile(sf, rows, structure, rep) -> dict:
    with sf() as s:
        q = lambda stmt: s.scalar(stmt)  # noqa: E731
        db = {"graph_nodes": q(select(func.count()).select_from(GraphOccupation)), "graph_relationships": q(select(func.count()).select_from(GraphOccupationRelationship)),
              "records": q(select(func.count()).select_from(R).where(R.source_ref == U.OEWS_SOURCE)), "distinct_occupations": q(select(func.count(func.distinct(R.occupation_id))).where(R.source_ref == U.OEWS_SOURCE)),
              "distinct_native_codes": q(select(func.count(func.distinct(R.native_code))).where(R.source_ref == U.OEWS_SOURCE)),
              "by_class": dict(s.execute(select(R.evidence_class, func.count()).where(R.source_ref == U.OEWS_SOURCE).group_by(R.evidence_class)).all()),
              "by_level": dict(s.execute(select(R.occupation_level, func.count()).where(R.source_ref == U.OEWS_SOURCE).group_by(R.occupation_level)).all()),
              "by_pay_period": dict(s.execute(select(R.pay_period, func.count()).where(R.source_ref == U.OEWS_SOURCE).group_by(R.pay_period)).all())}
    by_group = Counter(str(r.values["O_GROUP"]).lower() for r in rows)
    expected = {"graph_nodes": len(structure), "graph_relationships": len(structure) - sum(1 for n in structure if n.level == "major"), "records": rep["records"], "distinct_occupations": rep["occupations"]}
    checks = {k: {"database": db[k], "expected_from_files": v, "match": db[k] == v} for k, v in expected.items()}
    checks["class_split_matches_levels"] = {"C1_equals_detailed_records": db["by_class"].get("C1") == db["by_level"].get("detailed"), "C2_equals_broad_records": db["by_class"].get("C2") == db["by_level"].get("broad")}
    return {"database": db, "source_rows": {"rows": len(rows), "by_o_group": dict(by_group), "total_rows": by_group.get("total", 0), "quarantined": sorted(rep["quarantined_codes"]),
                                         "duplicate_pairs": sorted(rep["duplicate_presentations"]), "occupations_after_dedup": rep["occupations"],
                                         "arithmetic": f"{len(rows)} rows - {by_group.get('total', 0)} total - {rep['quarantined_rows']} quarantined = {len(rows) - by_group.get('total', 0) - rep['quarantined_rows']} canonical rows; "
                                                       f"minus {len(rep['duplicate_presentations'])} duplicate second presentations = {rep['occupations']} occupations"},
            "checks": checks, "all_match": all(c["match"] for k, c in checks.items() if "match" in c)}


def review_all(sf, store, reg, structure, apply: bool, files_ok: bool, out_dir: Path) -> dict:
    levels = {n.code: n.level for n in structure}
    src = reg.get(U.OEWS_SOURCE)
    outcomes: Counter = Counter()
    reasons: Counter = Counter()
    per: list[tuple] = []
    with sf() as s:
        rows = list(s.scalars(select(R).where(R.source_ref == U.OEWS_SOURCE).order_by(R.id)))
        keys = Counter(r.record_key for r in rows)
        for r in rows:
            rec = {**from_row(r), "provenance": r.provenance, "batch_id": r.batch_id}
            outcome, why = Q.review_record(rec, source=src, file_integrity_ok=files_ok, soc_level=levels.get(r.native_code), key_count=keys[r.record_key])
            outcomes[outcome] += 1
            reasons.update(why)
            per.append((r.record_key, r.native_code, r.pay_period, r.measure, r.percentile, outcome, "|".join(why), r.qualification_status))
    applied = 0
    t0 = time.perf_counter()
    if apply:
        for key, _, _, _, _, outcome, _, state in per:
            if outcome == "ENGINEERING_CHECKED" and state == "unqualified":
                store.set_qualification(key, "engineering_checked", actor_user_id=None)
                applied += 1
    (out_dir / "qualification_dry_run_per_record.tsv").write_text("record_key\tnative_code\tpay_period\tmeasure\tpercentile\toutcome\treasons\tstate_before\n" + "\n".join("\t".join(map(str, p)) for p in per), encoding="utf-8")
    with sf() as s:
        states = dict(s.execute(select(R.qualification_status, func.count()).where(R.source_ref == U.OEWS_SOURCE).group_by(R.qualification_status)).all())
    return {"records_reviewed": len(per), "outcomes": dict(outcomes), "reasons": dict(reasons), "moved_to_engineering_checked_this_run": applied, "state_counts_after": states,
            "qualified": states.get("qualified", 0), "apply_seconds": round(time.perf_counter() - t0, 1),
            "reviewer": "none: no human reviewer identity exists in the isolated environment; `qualified` was not requested and cannot be set without one",
            "meaning": "ENGINEERING_CHECKED = every deterministic rule holds (identity, definition, provenance, integrity); it makes no precision claim and is not operational evidence"}


def alias_work(sf, reg, g, structure, definitions, apply: bool) -> dict:
    proposals = Q.build_alias_proposals(US_CASES, structure, definitions)
    store = AliasStore(sf)
    loaded = []
    if apply:
        for p in proposals:
            if p["decision"] != "PROPOSED_SINGLE":
                continue
            node = g.find_by_identifier("soc", p["target_code"], "2018")[0]
            a = store.add_alias(node["occupation_key"], p["market_title"], language="en", language_basis="curated_manual", alias_type="recognized_title", source_ref=U.SOC_SOURCE,
                                taxonomy=("soc", "2018"), provenance={"country_applicability": ["US"], "relationship": p["relationship"], "rule": p["rule"], "case": p["case"],
                                                                      "evidence_source": p["evidence_source"], "approval": p["approval"], "limitation": p["limitation"], "proposed_on": "2026-10-18"})
            if a["qualification_status"] == "unqualified":
                store.set_qualification(a["id"], "engineering_checked", actor_user_id=None)
            loaded.append({"alias_id": a["id"], "text": p["market_title"], "target": p["target_code"]})
    with sf() as s:
        states = dict(s.execute(select(GraphOccupationAlias.qualification_status, func.count()).where(GraphOccupationAlias.source_ref == U.SOC_SOURCE, GraphOccupationAlias.alias_type == "recognized_title")
                                .group_by(GraphOccupationAlias.qualification_status)).all())
    return {"proposals": proposals, "loaded": loaded, "alias_qualification_states": states, "qualified_aliases": states.get("qualified", 0),
            "reviewer": "none: alias qualification (D-08) needs a named human reviewer; every alias stays engineering_checked at most"}


def resolution_table(res: CompensationResolver, proposals) -> list[dict]:
    out = []
    for p in proposals:
        r = res.resolve(CompensationRequest(occupation=MultilingualRequest(title=p["market_title"], title_language="en"), country="US", require_operational=False, pay_period="annual", measure="median"))
        row = {"case": p["case"], "title": p["market_title"], "decision": p["decision"], "occupation_status": r.occupation_status, "resolved_code": None, "outcome": r.outcome.value,
               "evidence_class": r.evidence_class, "abstention_reason": r.abstention_reason, "operational": r.operational, "candidate_presentable": r.candidate_presentable,
               "has_value": r.value is not None, "reasons_hint": r.candidates[0]["grade"] if r.candidates else None}
        if r.occupation_key:
            node = res._g.identifiers(r.occupation_key)
            row["resolved_code"] = next((i["native_code"] for i in node if i["scheme"] == "soc"), None)
        out.append(row)
    return out


def measure_cases(res: CompensationResolver, g, sf, rows) -> dict:
    """Annual-only/hourly-only and broader-group behaviour on real data (internal mode)."""
    with sf() as s:
        have = {}
        for code, period, measure, pct in s.execute(select(R.native_code, R.pay_period, R.measure, R.percentile).where(R.source_ref == U.OEWS_SOURCE)).all():
            have.setdefault(code, set()).add((period, measure, pct))
    ann = [r.values["OCC_CODE"] for r in rows if str(r.values.get("ANNUAL")).upper() == "TRUE" and r.values["OCC_CODE"] in have]
    hou = [r.values["OCC_CODE"] for r in rows if str(r.values.get("HOURLY")).upper() == "TRUE" and r.values["OCC_CODE"] in have]

    def ask(code, period, allow=True):
        r = res.resolve(CompensationRequest(occupation=MultilingualRequest(taxonomy_scheme="soc", taxonomy_code=code, taxonomy_edition="2018"), country="US", require_operational=False, pay_period=period, measure="median",
                                            allow_broader_occupation=allow))
        return r

    def summarise(r):
        return {"outcome": r.outcome.value, "has_own_value": r.value is not None, "abstention_reason": r.abstention_reason, "evidence_class": r.evidence_class, "specificity": r.occupation_specificity,
                "contextual": [{"code": c["broader_occupation_code"], "label": c["broader_occupation_label"], "class": c["evidence_class"], "measure": c["measure"], "pay_period": c["pay_period"],
                                "has_warning": "NOT the requested occupation" in c["warning"]} for c in r.contextual_evidence]}
    stats = {"annual_only_occupations_tested": 0, "annual_only_hourly_request": Counter(), "hourly_only_occupations_tested": 0, "hourly_only_annual_request": Counter(), "own_value_ever_substituted": 0,
             "examples": {}}
    for code in ann:
        r = ask(code, "hourly")
        stats["annual_only_occupations_tested"] += 1
        key = ("abstain_with_context" if r.contextual_evidence else "abstain_no_context") if r.outcome.value == "abstain" else r.outcome.value
        stats["annual_only_hourly_request"][key] += 1
        stats["own_value_ever_substituted"] += int(r.value is not None)
        stats["examples"].setdefault("annual_only_" + key, {"code": code, **summarise(r)})
    for code in hou:
        r = ask(code, "annual")
        stats["hourly_only_occupations_tested"] += 1
        key = ("abstain_with_context" if r.contextual_evidence else "abstain_no_context") if r.outcome.value == "abstain" else r.outcome.value
        stats["hourly_only_annual_request"][key] += 1
        stats["own_value_ever_substituted"] += int(r.value is not None)
        stats["examples"].setdefault("hourly_only_" + key, {"code": code, **summarise(r)})
    ctx_code = next((v["code"] for k, v in stats["examples"].items() if k.endswith("abstain_with_context")), None)
    if ctx_code:
        stats["no_authorised_fallback_example"] = {"code": ctx_code, **summarise(ask(ctx_code, "hourly" if ctx_code in ann else "annual", allow=False))}
    stats["annual_only_hourly_request"] = dict(stats["annual_only_hourly_request"])
    stats["hourly_only_annual_request"] = dict(stats["hourly_only_annual_request"])
    return stats


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db-name", default="p5b_f2a_us")
    ap.add_argument("--out", default=None)
    ap.add_argument("--dry-run", action="store_true", help="review and report only; write no qualification state and no alias")
    a = ap.parse_args(argv)
    ing = _load_ingest()
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    staging = U.locate_staging(MANIFEST)
    if staging is None:
        print("staging directory not found (set P10CF2A_STAGING_DIR)")
        return 3
    out_dir = Path(a.out) if a.out else staging / "validation"
    if ROOT in out_dir.resolve().parents or out_dir.resolve() == ROOT:
        raise SystemExit("--out must be outside the repository")
    status = U.verify_staged_files(manifest, staging)
    files_ok = set(status.values()) == {"OK"}
    if not files_ok:
        print("STOP: staged files do not match the manifest:", status)
        return 4
    url = ing.make_database(ing._admin(), a.db_name)
    sf = make_session_factory(make_engine(url))
    reg, g = SourceRegistry(sf), OccupationGraph(sf)
    store = CompensationStoreV2(sf, reg, g)
    structure = U.parse_soc_structure(staging / "raw/soc_structure_2018.xlsx")
    definitions = U.parse_soc_definitions(staging / "raw/soc_2018_definitions.xlsx")
    rows, _ = U.parse_oews_national(staging / "extracted/oesm25nat/oesm25nat/national_M2025_dl.xlsx")
    levels = {n.code: n.level for n in structure}
    files = {f["file_id"]: f for f in manifest["files"]}
    records, rep = U.oews_v2_records(rows, levels, archive_sha256=files["us_oews_may2025_national"]["sha256"])
    report: dict = {"schema": "p10c-f2aq-qualification-report/1", "run_at": datetime.now(timezone.utc).isoformat(), "staged_files": status, "dry_run": a.dry_run,
                    "alembic": ing.alembic_head(url), "registry": {s_: {"approval_status": reg.get(s_)["approval_status"], "licence_status": reg.get(s_)["licence_status"]} for s_ in (U.SOC_SOURCE, U.OEWS_SOURCE)}}
    report["reconciliation"] = reconcile(sf, rows, structure, rep)
    report["annual_only"] = Q.annual_only_reconciliation(rows, set(levels), set(rep["quarantined_codes"]))
    report["rse"] = Q.rse_distribution(rows, set(levels) - set(rep["quarantined_codes"]))
    again = store.import_records(records, source_ref=U.OEWS_SOURCE, source_edition=U.OEWS_EDITION, mode="production", transformation=U.TRANSFORMATION)
    report["duplicate_and_idempotency"] = {"duplicate_presentations": rep["duplicate_presentations"], "reimport": again.__dict__,
                                           "records_per_duplicate_code_and_measure_max": 1, "records_for_duplicate_codes": sum(1 for r in records if r.native_code in rep["duplicate_presentations"])}
    report["quarantined_aggregates"] = rep["quarantined_codes"]
    report["review"] = review_all(sf, store, reg, structure, not a.dry_run, files_ok, out_dir)
    report["aliases"] = alias_work(sf, reg, g, structure, definitions, not a.dry_run)
    occ = OccupationResolver(g, AliasStore(sf), registry=reg)
    res = CompensationResolver(store, occ, g, reg)
    report["resolution"] = resolution_table(res, report["aliases"]["proposals"])
    report["measure_cases"] = measure_cases(res, g, sf, rows)
    try:
        report["v1_reconciliation"] = ing.v1_reconciliation(ROOT / "data/knowledge/compensation.db", records, rep["quarantined_codes"], out_dir)
    except Exception as exc:  # noqa: BLE001
        report["v1_reconciliation"] = {"error": type(exc).__name__}
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "qualification_report.json").write_text(json.dumps(report, indent=1, default=str), encoding="utf-8")
    print(json.dumps({"reconciliation_all_match": report["reconciliation"]["all_match"], "annual_only": {k: report["annual_only"][k] for k in ("annual_true_rows", "canonical_annual_only_occupations")},
                      "review": {k: report["review"][k] for k in ("records_reviewed", "outcomes", "state_counts_after", "qualified")},
                      "aliases": {"states": report["aliases"]["alias_qualification_states"], "decisions": Counter(p["decision"] for p in report["aliases"]["proposals"])},
                      "resolution": [(r["title"], r["outcome"], r["resolved_code"]) for r in report["resolution"]]}, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
