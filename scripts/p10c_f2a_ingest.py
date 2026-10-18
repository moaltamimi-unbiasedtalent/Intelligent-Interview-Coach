#!/usr/bin/env python
"""P10C-F2A isolated US ingestion runner (non-production). Reads the four staged BLS files (never downloads), verifies them against the committed manifest and ingests SOC 2018 and
BLS OEWS May 2025 into an ISOLATED PostgreSQL database that this script creates on the loopback server announced through ``P5B_PG_ADMIN_URL`` (the sanctioned test-isolation target:
a database named ``p5b_*``). It refuses anything else, never touches a developer store, never calls an external service and never activates Compensation V2.

    P5B_PG_ADMIN_URL=postgresql+psycopg://user@127.0.0.1:PORT/postgres python scripts/p10c_f2a_ingest.py [--v1-db data/knowledge/compensation.db] [--out DIR]

Source-registry transitions are performed ONLY in the isolated database, through ``SourceRegistry`` (audited edges; no state is written directly), citing the owner authorisation
recorded on 2026-10-18. Registry approval to ``approved_for_runtime_use`` is never performed."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import tests.conftest  # noqa: E402,F401  (standalone-script isolation: must precede every src import)

from src.knowledge_foundation import us_sources as U  # noqa: E402
from src.knowledge_foundation.aliases import AliasStore  # noqa: E402
from src.knowledge_foundation.compensation.resolver import CompensationRequest, CompensationResolver  # noqa: E402
from src.knowledge_foundation.compensation.store import CompensationStoreV2  # noqa: E402
from src.knowledge_foundation.graph import OccupationGraph  # noqa: E402
from src.knowledge_foundation.occupation_resolver import MultilingualRequest, OccupationResolver  # noqa: E402
from src.knowledge_foundation.registry import SourceRegistry  # noqa: E402
from src.knowledge_foundation.taxonomy import TaxonomyCatalogue  # noqa: E402

MANIFEST = ROOT / "docs/capstone/p10/p10c_f2a/acquisition_manifest.json"
AUTH_REASON = "owner authorisation 2026-10-18 (P10C-F2A Package 1; isolated non-production ingestion only)"


def _admin() -> str:
    admin = os.environ.get("P5B_PG_ADMIN_URL")
    if not admin:
        raise SystemExit("P5B_PG_ADMIN_URL is required: an isolated loopback PostgreSQL server announced for this run")
    return admin


def make_database(admin: str, name: str) -> str:
    import psycopg

    if not name.startswith("p5b_"):
        raise SystemExit("the isolated database must be named p5b_*")
    with psycopg.connect(admin.replace("postgresql+psycopg://", "postgresql://"), autocommit=True) as c:
        if not c.execute("select 1 from pg_database where datname=%s", (name,)).fetchone():
            c.execute(f'CREATE DATABASE "{name}"')
    return admin.rsplit("/", 1)[0] + f"/{name}"


def alembic_head(url: str) -> dict:
    env = {**os.environ, "DATABASE_URL": url, "API_ENV": "test"}
    up = subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=ROOT, env=env, capture_output=True, text=True, timeout=600)
    if up.returncode:
        raise SystemExit("alembic upgrade failed: " + up.stderr[-400:])
    cur = subprocess.run([sys.executable, "-m", "alembic", "current"], cwd=ROOT, env=env, capture_output=True, text=True, timeout=120)
    heads = subprocess.run([sys.executable, "-m", "alembic", "heads"], cwd=ROOT, env=env, capture_output=True, text=True, timeout=120)
    return {"current": cur.stdout.strip().split()[0] if cur.stdout.strip() else None, "heads": [h.split()[0] for h in heads.stdout.strip().splitlines() if h.strip()]}


def setup_registry(reg: SourceRegistry, tax: TaxonomyCatalogue, manifest: dict) -> dict:
    files = {f["file_id"]: f for f in manifest["files"]}
    soc_hash = {"structure": files["us_soc_2018_structure"]["sha256"], "definitions": files["us_soc_2018_definitions"]["sha256"]}
    acq = datetime(2026, 10, 18, 11, 34, 14, tzinfo=timezone.utc)
    reg.register(U.SOC_SOURCE, origin="authorised_manual", publisher="U.S. Bureau of Labor Statistics", dataset_name="2018 Standard Occupational Classification", dataset_version="2018",
                 source_url="https://www.bls.gov/soc/2018/home.htm", geographies=["US"], languages=["en"], taxonomy="soc", evidence_category="taxonomy", licence_id="bls-public-domain",
                 licence_status="stated_unverified", precedence_category="national_official_occupation_statistics", validation_status="unvalidated", retrieved_at=acq,
                 provenance={"manifest": "docs/capstone/p10/p10c_f2a/acquisition_manifest.json", "sha256": soc_hash})
    reg.register(U.OEWS_SOURCE, origin="authorised_manual", publisher="U.S. Bureau of Labor Statistics", dataset_name="Occupational Employment and Wage Statistics (OEWS), May 2025 national estimates",
                 dataset_version=U.OEWS_EDITION, source_url="https://www.bls.gov/oes/tables.htm", geographies=["US"], languages=["en"], taxonomy="soc", evidence_category="compensation",
                 licence_id="bls-public-domain", licence_status="stated_unverified", precedence_category="national_official_occupation_statistics", validation_status="unvalidated",
                 retrieved_at=acq, checksum_sha256=files["us_oews_may2025_national"]["sha256"], reference_period="May 2025",
                 provenance={"manifest": "docs/capstone/p10/p10c_f2a/acquisition_manifest.json", "file": "oesm25nat.zip"})
    for sid in (U.SOC_SOURCE, U.OEWS_SOURCE):
        cur = reg.get(sid)["approval_status"]
        if cur == "discovered":
            reg.transition(sid, "licensing_pending", reason=AUTH_REASON)
        if reg.get(sid)["approval_status"] == "licensing_pending":
            reg.set_licence(sid, licence_id="bls-public-domain", licence_status="verified", attribution_required="no", redistribution="yes")
            reg.transition(sid, "licensing_verified", reason="BLS copyright page read 2026-10-18: public domain; citation requested; emblem prohibited")
        if reg.get(sid)["approval_status"] == "licensing_verified":
            reg.transition(sid, "approved_for_ingestion", reason=AUTH_REASON)
    tax.ensure("soc", U.SOC_EDITION, label="US SOC 2018", status="current", acquisition_status="available_locally", code_pattern="[0-9]{2}-[0-9]{4}", geographies=["US"],
               notes="Official 2018 SOC structure and definitions acquired 2026-10-18 (hashes in the acquisition manifest).")
    return {sid: {"approval_status": reg.get(sid)["approval_status"], "licence_status": reg.get(sid)["licence_status"], "events": reg.events(sid)} for sid in (U.SOC_SOURCE, U.OEWS_SOURCE)}


def provenance_audit(sf) -> dict:
    from sqlalchemy import select

    from src.persistence import CompensationRecordV2Row

    need = ("transformation", "manifest_file_id", "archive_sha256", "archive_member", "sheet", "source_rows", "source_field", "emp_prse", "tot_emp")
    n = bad = 0
    with sf() as s:
        for r in s.scalars(select(CompensationRecordV2Row).where(CompensationRecordV2Row.source_ref == U.OEWS_SOURCE)):
            n += 1
            p = r.provenance or {}
            if any(k not in p for k in need) or not r.publisher or not r.dataset_name or not r.source_edition or not r.batch_id or len(str(p.get("archive_sha256", ""))) != 64:
                bad += 1
    return {"records_checked": n, "incomplete_provenance": bad}


def classification_counts(sf) -> dict:
    from sqlalchemy import func, select

    from src.persistence import CompensationRecordV2Row as R

    with sf() as s:
        q = s.execute(select(R.evidence_class, R.occupation_level, R.qualification_status, R.status, func.count()).where(R.source_ref == U.OEWS_SOURCE)
                      .group_by(R.evidence_class, R.occupation_level, R.qualification_status, R.status)).all()
        meas = s.execute(select(R.pay_period, R.measure, R.percentile, func.count()).where(R.source_ref == U.OEWS_SOURCE).group_by(R.pay_period, R.measure, R.percentile)).all()
    return {"by_class_level_qualification_status": [{"evidence_class": a, "occupation_level": b, "qualification_status": c, "status": d, "records": n} for a, b, c, d, n in q],
            "by_measure": [{"pay_period": a, "measure": b, "percentile": c, "records": n} for a, b, c, n in meas]}


def retrieval_checks(sf, reg, g, store, soc_nodes, rows) -> dict:
    occ = OccupationResolver(g, AliasStore(sf), registry=reg)
    res = CompensationResolver(store, occ, g, reg)
    by_code = {r.values["OCC_CODE"]: r.values for r in rows}
    annual_only = next(c for c, v in by_code.items() if str(v.get("ANNUAL")).upper() == "TRUE" and c in {n.code for n in soc_nodes} and c not in U.OEWS_SPECIFIC_CODES)
    hourly_only = next(c for c, v in by_code.items() if str(v.get("HOURLY")).upper() == "TRUE")
    detailed = next(n.code for n in soc_nodes if n.level == "detailed" and n.code in by_code and by_code[n.code].get("A_MEDIAN") not in (None, "*"))
    military = next(n.code for n in soc_nodes if n.code.startswith("55-") and n.level == "detailed")
    dup = "13-1020"

    def ask(code, **kw):
        r = res.resolve(CompensationRequest(occupation=MultilingualRequest(taxonomy_scheme="soc", taxonomy_code=code, taxonomy_edition="2018"), country="US", require_operational=False, **kw))
        return {"outcome": r.outcome.value, "specificity": r.occupation_specificity, "evidence_class": r.evidence_class, "level": r.occupation_level, "measure": r.measure, "pay_period": r.pay_period,
                "abstention_reason": r.abstention_reason, "has_value": r.value is not None, "has_citation": r.citation is not None, "withheld": dict(r.withheld)}

    out = {"exact_detailed_annual_median": ask(detailed, pay_period="annual", measure="median"), "exact_detailed_hourly_p25": ask(detailed, pay_period="hourly", measure="percentile", percentile=25),
           "mean_vs_median_distinct": {"mean": ask(detailed, pay_period="annual", measure="mean")["measure"], "median": ask(detailed, pay_period="annual", measure="median")["measure"]},
           "broad_group_median": ask("13-1020", pay_period="annual", measure="median"), "duplicate_presentation_code": ask(dup, pay_period="annual", measure="median"),
           "annual_only_occupation_annual": ask(annual_only, pay_period="annual", measure="median"), "annual_only_occupation_hourly": ask(annual_only, pay_period="hourly", measure="median"),
           "hourly_only_occupation_hourly": ask(hourly_only, pay_period="hourly", measure="median"), "hourly_only_occupation_annual": ask(hourly_only, pay_period="annual", measure="median"),
           "noncanonical_bls_aggregate": ask("21-1018", pay_period="annual", measure="median"), "invalid_soc_code": ask("99-9999", pay_period="annual", measure="median"),
           "military_occupation_without_wages": ask(military, pay_period="annual", measure="median"),
           "wrong_taxonomy_edition": None}
    r = res.resolve(CompensationRequest(occupation=MultilingualRequest(taxonomy_scheme="soc", taxonomy_code=detailed, taxonomy_edition="2010"), country="US", require_operational=False, pay_period="annual", measure="median"))
    out["wrong_taxonomy_edition"] = {"outcome": r.outcome.value, "abstention_reason": r.abstention_reason}
    r = res.resolve(CompensationRequest(occupation=MultilingualRequest(taxonomy_scheme="soc", taxonomy_code=detailed, taxonomy_edition="2018"), country="US", require_operational=True, pay_period="annual", measure="median"))
    out["operational_mode_unqualified_unapproved"] = {"outcome": r.outcome.value, "abstention_reason": r.abstention_reason, "has_value": r.value is not None, "operational": r.operational, "candidate_presentable": r.candidate_presentable}
    r = res.resolve(CompensationRequest(occupation=MultilingualRequest(taxonomy_scheme="soc", taxonomy_code=detailed, taxonomy_edition="2018"), country="GB", require_operational=False, pay_period="annual", measure="median"))
    out["other_country_never_falls_back"] = {"outcome": r.outcome.value}
    return out


def us_case_assessment(g, res) -> dict:
    """Qualified-source assessment of the US-dependent product-coverage cases that were insufficient. Structural evidence only: it asks whether the OFFICIAL SOC label resolves the case's
    occupation exactly (no alias, no similarity). It changes no evaluation definition and does not feed the runtime evaluator."""
    cases = json.loads((ROOT / "evaluations/product_coverage/cases.json").read_text(encoding="utf-8"))["cases"]
    wanted = ["pc_compensation_183", "pc_compensation_187", "pc_compensation_191", "pc_compensation_195", "pc_compensation_199", "pc_compensation_203", "pc_compensation_207"]
    out = []
    for c in cases:
        if c["id"] not in wanted:
            continue
        title = c.get("occupation") or ""
        exact = g.find_by_label(title)
        soc_exact = [e for e in exact if any(i["scheme"] == "soc" for i in g.identifiers(e["occupation_key"]))]
        r = res.resolve(CompensationRequest(occupation=MultilingualRequest(title=title, title_language="en"), country="US", require_operational=False, pay_period="annual", measure="median"))
        out.append({"case": c["id"], "occupation_title": title, "exact_official_soc_label_matches": len(soc_exact), "resolver_outcome": r.outcome.value, "evidence_class": r.evidence_class,
                    "occupation_status": r.occupation_status, "reason": r.abstention_reason})
    return {"cases": out, "exact_resolutions": sum(1 for o in out if o["exact_official_soc_label_matches"] == 1 and o["resolver_outcome"] == "evidence"),
            "note": "Structural, internal-mode result on the isolated database. It is NOT candidate runtime coverage and the runtime evaluator is unchanged."}


def v1_reconciliation(v1_db: Path, records, quarantined: dict, out_dir: Path) -> dict:
    import sqlite3

    stat = v1_db.stat()
    con = sqlite3.connect(f"file:{v1_db.as_posix()}?mode=ro&immutable=1", uri=True)
    try:
        v1 = con.execute("select occupation_code, year, currency, pay_period, statistic_type, value, lower_bound, upper_bound, country from compensation_records where source_id='bls_oews'").fetchall()
    finally:
        con.close()
    v2 = {}
    for r in records:
        if r.pay_period == "annual" and r.measure == "median":
            v2[r.native_code] = r
    seen: Counter = Counter()
    verdicts: Counter = Counter()
    per = []
    for code, year, cur, period, stat_t, val, lo, hi, country in v1:
        seen[code] += 1
        if seen[code] > 1:
            v, why = "DUPLICATE", "same native code appears more than once in V1"
        elif code in quarantined:
            v, why = "INCOMPATIBLE", "BLS-specific aggregate, not a canonical SOC 2018 code"
        elif code not in v2:
            v, why = "UNRESOLVED", "no published annual median for this code in the official May 2025 national file (or code not in SOC 2018)"
        else:
            r = v2[code]
            same = (year == 2025 and cur == "USD" and period == "annual" and stat_t == "median" and country == "US" and val is not None and Decimal(repr(float(val))) == r.value
                    and ((lo is None and r.lower_value is None) or (lo is not None and r.lower_value is not None and Decimal(repr(float(lo))) == r.lower_value and Decimal(repr(float(hi))) == r.upper_value)))
            v, why = ("QUALIFIED_FOR_V2", "year, statistic and exact values equal the official V2 record") if same else ("REQUIRES_ADDITIONAL_EVIDENCE", "linked code but value, bounds or metadata differ from the official record")
        verdicts[v] += 1
        per.append({"native_code": code, "verdict": v, "reason": why})
    (out_dir / "v1_reconciliation_per_record.json").write_text(json.dumps(per, indent=0), encoding="utf-8")
    after = v1_db.stat()
    return {"v1_records": len(v1), "verdicts": dict(verdicts), "v1_distinct_codes": len(seen), "v1_duplicate_rows": sum(n - 1 for n in seen.values()), "v1_db_modified": (after.st_mtime_ns, after.st_size) != (stat.st_mtime_ns, stat.st_size),
            "note": "QUALIFIED_FOR_V2 means the V1 row matches an ingested official V2 record exactly; it does not set any V2 qualification_status (no reviewer exists). No V1 row was changed."}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db-name", default="p5b_f2a_us")
    ap.add_argument("--v1-db", default=str(ROOT / "data/knowledge/compensation.db"))
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    staging = U.locate_staging(MANIFEST)
    if staging is None:
        print("staging directory not found (set P10CF2A_STAGING_DIR)")
        return 3
    out_dir = Path(a.out) if a.out else staging / "validation"
    if (ROOT in out_dir.resolve().parents) or out_dir.resolve() == ROOT:
        raise SystemExit("--out must be outside the repository")
    status = U.verify_staged_files(manifest, staging)
    if set(status.values()) != {"OK"}:
        print("STOP: staged files do not match the manifest:", status)
        return 4
    report: dict = {"schema": "p10c-f2a-ingestion-report/1", "run_at": datetime.now(timezone.utc).isoformat(), "staged_files": status}
    url = make_database(_admin(), a.db_name)
    from src.persistence import make_engine, make_session_factory

    report["database"] = {"name": a.db_name, "host": "loopback isolated cluster", "alembic": alembic_head(url)}
    sf = make_session_factory(make_engine(url))
    tax, reg, g = TaxonomyCatalogue(sf), SourceRegistry(sf), OccupationGraph(sf)
    tax.seed()
    report["registry"] = setup_registry(reg, tax, manifest)
    files = {f["file_id"]: f for f in manifest["files"]}
    structure = U.parse_soc_structure(staging / "raw/soc_structure_2018.xlsx")
    definitions = U.parse_soc_definitions(staging / "raw/soc_2018_definitions.xlsx")
    report["soc_file_checks"] = U.check_soc_files(structure, definitions)
    hashes = {"structure": files["us_soc_2018_structure"]["sha256"], "definitions": files["us_soc_2018_definitions"]["sha256"]}
    t0 = time.perf_counter()
    report["soc_graph_first"] = U.populate_soc_graph(g, structure, definitions, file_hashes=hashes)
    t1 = time.perf_counter()
    report["soc_graph_reimport"] = U.populate_soc_graph(g, structure, definitions, file_hashes=hashes)
    t2 = time.perf_counter()
    rows, meta = U.parse_oews_national(staging / "extracted/oesm25nat/oesm25nat/national_M2025_dl.xlsx")
    levels = {n.code: n.level for n in structure}
    records, rep = U.oews_v2_records(rows, levels, archive_sha256=files["us_oews_may2025_national"]["sha256"])
    report["oews_transform"] = {k: v for k, v in rep.items()} | {"field_dictionary_fields": len(meta["field_descriptions"])}
    store = CompensationStoreV2(sf, reg, g)
    t3 = time.perf_counter()
    imp = store.import_records(records, source_ref=U.OEWS_SOURCE, source_edition=U.OEWS_EDITION, mode="production", transformation=U.TRANSFORMATION)
    t4 = time.perf_counter()
    imp2 = store.import_records(records, source_ref=U.OEWS_SOURCE, source_edition=U.OEWS_EDITION, mode="production", transformation=U.TRANSFORMATION)
    t5 = time.perf_counter()
    report["oews_import_first"] = imp.__dict__
    report["oews_import_reimport"] = imp2.__dict__
    report["store_counts"] = store.counts()
    report["provenance"] = provenance_audit(sf)
    report["classification"] = classification_counts(sf)
    report["retrieval"] = retrieval_checks(sf, reg, g, store, structure, rows)
    lat = []
    occ = OccupationResolver(g, AliasStore(sf), registry=reg)
    res = CompensationResolver(store, occ, g, reg)
    codes = [n.code for n in structure if n.code in {r.native_code for r in records}][:200]
    for c in codes:
        s0 = time.perf_counter()
        res.resolve(CompensationRequest(occupation=MultilingualRequest(taxonomy_scheme="soc", taxonomy_code=c, taxonomy_edition="2018"), country="US", require_operational=False, pay_period="annual", measure="median"))
        lat.append((time.perf_counter() - s0) * 1000)
    lat.sort()
    report["performance"] = {"soc_graph_population_s": round(t1 - t0, 2), "soc_graph_reimport_s": round(t2 - t1, 2), "oews_import_s": round(t4 - t3, 2), "oews_reimport_s": round(t5 - t4, 2),
                             "records_per_second_import": round(len(records) / max(t4 - t3, 1e-9)), "resolve_p50_ms": round(lat[len(lat) // 2], 1), "resolve_p95_ms": round(lat[int(len(lat) * .95)], 1), "resolve_samples": len(lat)}
    report["us_case_assessment"] = us_case_assessment(g, res)
    if Path(a.v1_db).exists():
        report["v1_reconciliation"] = v1_reconciliation(Path(a.v1_db), records, rep["quarantined_codes"], out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "ingestion_report.json").write_text(json.dumps(report, indent=1, default=str), encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("database", "soc_graph_first", "soc_graph_reimport", "oews_import_first", "oews_import_reimport", "store_counts", "provenance", "performance")}, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
