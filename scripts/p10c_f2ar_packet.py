#!/usr/bin/env python
"""P10C-F2A-R human-qualification readiness packet (non-production, isolated). Verifies the engineering baseline, partitions the engineering-checked OEWS observations into reviewable
batches with reproducible digests, annotates the five alias proposals with an evidence review, analyses all 26 insufficient product-coverage cases and writes the packet. It performs NO
human decision: no record, alias or source is qualified, no reviewer identity is created, and nothing in a developer store is written (the developer database is opened read-only and only
role COUNTS are read).

    P5B_PG_ADMIN_URL=postgresql+psycopg://user@127.0.0.1:PORT/postgres python scripts/p10c_f2ar_packet.py [--out DIR]
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import sqlite3
import sys
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import tests.conftest  # noqa: E402,F401  (standalone-script isolation: must precede every src import)

from sqlalchemy import func, select  # noqa: E402

from src.application.admin_permissions import permissions_for_role  # noqa: E402
from src.knowledge_foundation import us_alias_review as AR  # noqa: E402
from src.knowledge_foundation import us_sources as U  # noqa: E402
from src.knowledge_foundation.aliases import AliasStore  # noqa: E402
from src.knowledge_foundation.compensation.resolver import CompensationRequest, CompensationResolver  # noqa: E402
from src.knowledge_foundation.compensation.store import CompensationStoreV2  # noqa: E402
from src.knowledge_foundation.graph import OccupationGraph  # noqa: E402
from src.knowledge_foundation.occupation_resolver import MultilingualRequest, OccupationResolver  # noqa: E402
from src.knowledge_foundation.qualification_review import REVIEWER_ROLES, BatchScope, QualificationReviewService, appointment_readiness  # noqa: E402
from src.knowledge_foundation.registry import SourceRegistry  # noqa: E402
from src.persistence import CompensationRecordV2Row as R  # noqa: E402
from src.persistence import GraphOccupation, GraphOccupationAlias, GraphOccupationRelationship, User, make_engine, make_session_factory  # noqa: E402

MANIFEST = ROOT / "docs/capstone/p10/p10c_f2a/acquisition_manifest.json"
WIRING = {"pc_compensation_187", "pc_compensation_199", "pc_compensation_203", "pc_compensation_195", "pc_compensation_207", "pc_compensation_188", "pc_compensation_200",
          "pc_compensation_204", "pc_compensation_196", "pc_compensation_208", "pc_education_083", "pc_future_growth_235", "pc_annual_openings_299"}
US_COMP = ["pc_compensation_183", "pc_compensation_187", "pc_compensation_191", "pc_compensation_195", "pc_compensation_199", "pc_compensation_203", "pc_compensation_207"]
ALIAS_TITLES = {"Software Developer": "15-1252", "Human Resources Manager": "11-3121", "Sales Manager": "11-2022", "Accountant": "13-2011", "Financial Analyst": "13-2051"}


def _ingest():
    spec = importlib.util.spec_from_file_location("p10c_f2a_ingest", ROOT / "scripts/p10c_f2a_ingest.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def baseline(sf, reg) -> dict:
    with sf() as s:
        out = {"soc_nodes": s.scalar(select(func.count()).select_from(GraphOccupation)), "soc_relationships": s.scalar(select(func.count()).select_from(GraphOccupationRelationship)),
               "records": s.scalar(select(func.count()).select_from(R).where(R.source_ref == U.OEWS_SOURCE)),
               "record_states": dict(s.execute(select(R.qualification_status, func.count()).where(R.source_ref == U.OEWS_SOURCE).group_by(R.qualification_status)).all()),
               "aliases": s.scalar(select(func.count()).select_from(GraphOccupationAlias).where(GraphOccupationAlias.alias_type == "recognized_title")),
               "alias_states": dict(s.execute(select(GraphOccupationAlias.qualification_status, func.count()).where(GraphOccupationAlias.alias_type == "recognized_title")
                                              .group_by(GraphOccupationAlias.qualification_status)).all()),
               "users_in_isolated_database": s.scalar(select(func.count()).select_from(User))}
    out["sources"] = {sid: reg.get(sid)["approval_status"] for sid in (U.SOC_SOURCE, U.OEWS_SOURCE)}
    out["runtime_approved_sources"] = [x["source_id"] for x in reg.list(approval_status="approved_for_runtime_use")]
    return out


def batches(svc: QualificationReviewService, sf, out_dir: Path) -> dict:
    groups = []
    for level in ("detailed", "broad"):
        for period in ("annual", "hourly"):
            for measure in ("mean", "median", "percentile"):
                scope = BatchScope(U.OEWS_SOURCE, U.OEWS_EDITION, level, period, measure)
                v = svc.validate_batch(scope)
                if v["records"] == 0:
                    continue
                with sf() as s:
                    rows = list(s.scalars(select(R).where(R.source_ref == U.OEWS_SOURCE, R.source_edition == U.OEWS_EDITION, R.occupation_level == level, R.pay_period == period, R.measure == measure).order_by(R.id)))
                    classes = Counter(r.evidence_class for r in rows)
                    with_rse = sum(1 for r in rows if isinstance((r.provenance or {}).get("mean_prse"), (int, float)) and measure == "mean")
                    dup = sum(1 for r in rows if len((r.provenance or {}).get("source_o_groups", [])) > 1)
                    pick = [rows[0], rows[len(rows) // 2], rows[-1]]
                    samples = [{"native_code": r.native_code, "pay_period": r.pay_period, "measure": r.measure, "percentile": r.percentile, "value": str(Decimal(r.value_units).scaleb(-r.amount_scale)),
                                "source_file": "oesm25nat.zip/" + (r.provenance or {}).get("archive_member", ""), "source_rows": (r.provenance or {}).get("source_rows"), "source_field": (r.provenance or {}).get("source_field"),
                                "emp_prse": (r.provenance or {}).get("emp_prse"), "mean_prse": (r.provenance or {}).get("mean_prse"), "evidence_class": r.evidence_class} for r in pick]
                eligible_for_batch = v["records"] == v["eligible_records"] and len(classes) == 1
                groups.append({"group": f"{level}/{period}/{measure}", "scope": scope.as_dict(), "records": v["records"], "outcomes": v["outcomes"], "eligible_records": v["eligible_records"],
                               "exceptions": len(v["exceptions"]), "evidence_class": dict(classes), "published_rse": ("mean wage RSE published for every record" if measure == "mean" and with_rse == v["records"]
                                                                                                                         else "BLS publishes no RSE for this statistic: the qualification claim excludes precision"),
                               "duplicate_presentation_records": dup, "digest": v["digest"], "batch_review_eligible": eligible_for_batch,
                               "review_route": "batch review with sample confirmation" if eligible_for_batch else "individual assessment of the exceptions", "samples": samples})
    total = sum(g["records"] for g in groups)
    tsv = out_dir / "measurement_review_per_record.tsv"
    with tsv.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, delimiter="\t")
        w.writerow(["record_key", "native_code", "occupation_level", "pay_period", "measure", "percentile", "evidence_class", "source_edition", "reference_period", "source_rows", "source_field", "archive_sha256",
                    "transformation", "emp_prse", "mean_prse", "rse_status", "engineering_recommendation", "state_now", "reviewer_decision", "reviewer_user_id", "review_timestamp", "audit_ref"])
        with sf() as s:
            for r in s.scalars(select(R).where(R.source_ref == U.OEWS_SOURCE).order_by(R.id)):
                p = r.provenance or {}
                rse = "mean_rse_published" if r.measure == "mean" else "no_published_rse_for_this_statistic"
                w.writerow([r.record_key, r.native_code, r.occupation_level, r.pay_period, r.measure, r.percentile, r.evidence_class, r.source_edition, r.reference_period, p.get("source_rows"), p.get("source_field"),
                            p.get("archive_sha256"), p.get("transformation"), p.get("emp_prse"), p.get("mean_prse"), rse, "QUALIFY_RECOMMENDED" if r.qualification_status == "engineering_checked" else "NONE", r.qualification_status, "", "", "", ""])
    return {"groups": groups, "records_in_groups": total, "groups_batch_eligible": sum(1 for g in groups if g["batch_review_eligible"]), "groups_needing_individual_assessment": sum(1 for g in groups if not g["batch_review_eligible"]),
            "per_record_file": "kept in the isolated staging area (not committed): " + tsv.name}


def alias_reviews(sf, structure, definitions) -> dict:
    rv = AR.build_alias_reviews(structure, definitions)
    store = AliasStore(sf)
    with sf() as s:
        ids = {(a.alias_text): a.id for a in s.scalars(select(GraphOccupationAlias).where(GraphOccupationAlias.alias_type == "recognized_title"))}
    for a in rv["aliases"]:
        aid = ids.get(a["title"])
        if aid is None:
            continue
        lim = None if a["relationship"] == "exact" else ("The official occupation is Accountants and Auditors: the figure covers both." if a["target"] == "13-2011" else
                                                          "The official occupation is Financial and Investment Analysts; the title may denote adjacent occupations (budget, credit, risk analysts) in practice.")
        store.annotate_scope(aid, relationship=a["relationship"], limitation=lim)
        store.add_review_note(aid, {"version": AR.REVIEW_VERSION, "recommendation": a["recommendation"], "relationship": a["relationship"], "competing": a["competing"], "status": a["status"]})
        a["alias_id"] = aid
    return rv


def gap_matrix(sf, reg, g, store, staging: Path, reviews: dict) -> dict:
    cases = {c["id"]: c for c in json.loads((ROOT / "evaluations/product_coverage/cases.json").read_text(encoding="utf-8"))["cases"]}
    before = {r["id"]: r for r in csv.DictReader(open(staging / "validation/coverage_before_results.csv", encoding="utf-8"))}
    insufficient = [i for i, r in before.items() if r["insufficient_ok"] == "False"]
    res = CompensationResolver(store, OccupationResolver(g, AliasStore(sf), registry=reg), g, reg)
    rec = {a["title"]: a["recommendation"] for a in reviews["aliases"]} | {u["title"]: u["recommendation"] for u in reviews["unresolved_titles"]}
    rows = []
    for cid in insufficient:
        c = cases[cid]
        fam, geo, title = c["question_family"], c.get("geography"), c.get("occupation")
        lane_src = c.get("expected_source_family", [])
        root = ("wiring" if cid in WIRING else "ambiguous_title")
        row = {"case": cid, "country": geo or "(none)", "requested_occupation": title, "requested_evidence": fam, "expected_sources": lane_src, "failure_reason": "missing_source: the candidate runtime has no production source for this slice (evidence 0)",
               "occupation_root_cause": root, "alias_recommendation": rec.get(title), "official_source_available": None, "structural_result_isolated": None, "source_qualification_dependency": None,
               "runtime_dependency": "Compensation V2 / runtime wiring is disabled and out of scope", "expected_improvement_after_human_qualification": 0, "remaining_blocker": None, "category": None}
        if fam == "compensation" and geo == "US":
            r = res.resolve(CompensationRequest(occupation=MultilingualRequest(title=title, title_language="en"), country="US", require_operational=False, pay_period="annual", measure="median"))
            row.update(official_source_available="BLS OEWS May 2025 (acquired, ingested in isolation)", structural_result_isolated=r.outcome.value + (f" via SOC alias, class {r.evidence_class}" if r.value else ""),
                       source_qualification_dependency="measurement batch review and alias review by named human reviewers")
            if r.value is not None:
                row.update(expected_improvement_after_human_qualification=1, category="needs_reviewer_approval_and_runtime_activation",
                           remaining_blocker="human qualification of the alias and measurements; runtime activation; RB-LIC-1 for commercial use outside the US")
            else:
                row.update(category="needs_new_evidence_or_owner_policy", remaining_blocker="no authoritative evidence for the title (ambiguous or unsupported); needs an approved occupational-title source or candidate context plus an owner ambiguity policy")
        elif fam == "compensation" and geo == "UK":
            row.update(official_source_available="ONS ASHE (not authorised: Package 2)", structural_result_isolated="not applicable: no UK data ingested", source_qualification_dependency="Package 2 acquisition, UK SOC 2020 taxonomy and UK alias evidence",
                       category="needs_another_country_package", remaining_blocker="Package 2 (UK) is unapproved; D-03, D-22 and the UK SOC 2020 edition check are open")
        else:
            row.update(official_source_available="BLS employment projections / Occupational Outlook Handbook (explicitly excluded from Package 1)" if lane_src and ("bls_projections" in lane_src or "bls_ooh" in lane_src) else "not identified",
                       structural_result_isolated="not applicable: no outlook, projections or education source ingested", source_qualification_dependency="a separate source package for OOH / projections",
                       category="needs_additional_source_package", remaining_blocker="BLS OOH and employment projections are outside Package 1; occupation identity: " + (
                           "ambiguous title (see the alias evidence review)" if root == "ambiguous_title" else ("alias reviewed: " + rec[title] if rec.get(title) else "wiring not assessed in this wave (no alias evidence review exists for this title)")))
        rows.append(row)
    cat = Counter(r["category"] for r in rows)
    us_ok = sum(1 for r in rows if r["category"] == "needs_reviewer_approval_and_runtime_activation")
    base = 412 - len(insufficient)
    need = -(-412 * 95 // 100)
    scenarios = [
        {"id": "A", "name": "current candidate runtime coverage (observed)", "sufficient": base, "percent": round(100 * base / 412, 2), "meets_gate": base >= need, "basis": "the 412-case evaluator, observed"},
        {"id": "B", "name": "isolated structural coverage of the US compensation cases (observed, internal mode, aliases engineering-checked, not approved, not runtime)", "sufficient_us_cases": us_ok, "of": len(US_COMP),
         "basis": "structural resolution in the isolated database; not candidate coverage"},
        {"id": "C1", "name": "potential: the five US aliases and the OEWS measurements human-approved AND runtime activated", "sufficient": base + us_ok, "percent": round(100 * (base + us_ok) / 412, 2), "meets_gate": base + us_ok >= need,
         "assumptions": ["a named reviewer approves all five aliases and the measurement batches", "runtime wiring and activation of Compensation V2 for US compensation", "RB-LIC-1 resolved for the deployment markets", "the evaluator counts the new evidence as sufficient"]},
        {"id": "C2", "name": "C1 plus Package 2 (UK) for the five resolvable UK titles", "sufficient": base + us_ok + 5, "percent": round(100 * (base + us_ok + 5) / 412, 2), "meets_gate": base + us_ok + 5 >= need,
         "assumptions": ["Package 2 authorised, acquired, qualified and runtime-activated", "UK SOC 2020 alias evidence exists for the same five titles (not yet reviewed)"]},
        {"id": "C3", "name": "C1 plus one legitimately resolved Data Analyst or Product Manager title", "sufficient": base + us_ok + 1, "percent": round(100 * (base + us_ok + 1) / 412, 2), "meets_gate": base + us_ok + 1 >= need,
         "assumptions": ["an approved occupational-title source or an owner-adopted context policy evidences a unique occupation for that title (NOT currently available)"]}]
    return {"insufficient_cases": len(insufficient), "baseline_sufficient": base, "gate_percent": 95, "minimum_sufficient_for_gate": need, "improvement_needed": need - base, "cases": rows, "by_category": dict(cat),
            "by_root_cause": dict(Counter(r["occupation_root_cause"] for r in rows)), "scenarios": scenarios,
            "gap_statement": f"{need} sufficient cases are required; the baseline is {base}; the maximum legitimate gain from Package 1 with the current evidence is {us_ok}, giving {base + us_ok}: {need - base - us_ok} short."}


def dev_account_counts() -> dict:
    p = ROOT / "data/interview_studio.db"
    if not p.exists():
        return {"available": False}
    st = p.stat()
    con = sqlite3.connect(f"file:{p.as_posix()}?mode=ro&immutable=1", uri=True)
    try:
        rows = con.execute("select platform_role, status, count(*) from users group by 1, 2").fetchall()
    finally:
        con.close()
    after = p.stat()
    eligible = {role: sum(n for pr, stt, n in rows if stt == "active" and need <= permissions_for_role(pr)) for role, need in REVIEWER_ROLES.items()}
    return {"available": True, "read": "role and status COUNTS only; no identity, email or secret was read", "accounts_by_role_status": {f"{r}/{s}": n for r, s, n in rows},
            "accounts_whose_current_role_could_serve": eligible, "developer_database_modified": (st.st_mtime_ns, st.st_size) != (after.st_mtime_ns, after.st_size),
            "caveat": "whether any of these accounts is a real, named human (rather than a seeded test account) is NOT VERIFIED and must be confirmed by the owner"}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db-name", default="p5b_f2a_us")
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    ing = _ingest()
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    staging = U.locate_staging(MANIFEST)
    if staging is None:
        print("staging directory not found (set P10CF2A_STAGING_DIR)")
        return 3
    out_dir = Path(a.out) if a.out else staging / "validation"
    if ROOT in out_dir.resolve().parents or out_dir.resolve() == ROOT:
        raise SystemExit("--out must be outside the repository")
    status = U.verify_staged_files(manifest, staging)
    if set(status.values()) != {"OK"}:
        print("STOP: staged files do not match the manifest:", status)
        return 4
    url = ing.make_database(ing._admin(), a.db_name)
    sf = make_session_factory(make_engine(url))
    reg, g = SourceRegistry(sf), OccupationGraph(sf)
    store = CompensationStoreV2(sf, reg, g)
    structure = U.parse_soc_structure(staging / "raw/soc_structure_2018.xlsx")
    definitions = U.parse_soc_definitions(staging / "raw/soc_2018_definitions.xlsx")
    levels = {n.code: n.level for n in structure}
    svc = QualificationReviewService(sf, reg, lambda: levels, lambda: True)
    out_dir.mkdir(parents=True, exist_ok=True)
    packet: dict = {"schema": "p10c-f2ar-packet/1", "generated_at": datetime.now(timezone.utc).isoformat(), "staged_files": status}
    packet["baseline"] = baseline(sf, reg)
    packet["official_source"] = {"publisher": "U.S. Bureau of Labor Statistics", "dataset": "OEWS May 2025 national estimates (2018 SOC)", "reference_period": "May 2025", "edition": U.OEWS_EDITION,
                                 "archive_sha256": next(f["sha256"] for f in manifest["files"] if f["file_id"] == "us_oews_may2025_national"),
                                 "methodology": "straight-time gross wage excluding premium pay; employees only; national cross-industry; annual values per BLS (hourly x 2,080 where BLS derived them)"}
    packet["measurement_batches"] = batches(svc, sf, out_dir)
    packet["alias_evidence_review"] = alias_reviews(sf, structure, definitions)
    packet["coverage_gap"] = gap_matrix(sf, reg, g, store, staging, packet["alias_evidence_review"])
    with sf() as s:
        isolated = appointment_readiness(s)
    packet["appointment_readiness"] = {"isolated_database": isolated, "developer_database": dev_account_counts()}
    (out_dir / "human_review_packet.json").write_text(json.dumps(packet, indent=1, default=str), encoding="utf-8")
    print(json.dumps({"baseline": packet["baseline"], "groups": [(g_["group"], g_["records"], g_["exceptions"], g_["batch_review_eligible"]) for g_ in packet["measurement_batches"]["groups"]],
                      "alias_counts": packet["alias_evidence_review"]["counts"], "gap": packet["coverage_gap"]["gap_statement"], "by_category": packet["coverage_gap"]["by_category"],
                      "dev": packet["appointment_readiness"]["developer_database"]}, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
