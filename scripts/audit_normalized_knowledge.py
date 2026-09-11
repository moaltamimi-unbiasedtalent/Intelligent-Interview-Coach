#!/usr/bin/env python
"""Audit the canonical NORMALIZED knowledge layer (Phase 7B, §58).

Read-only quality + coverage audit over ``data/normalized/`` produced by
``scripts/knowledge/build_normalized_knowledge.py``. It NEVER writes normalized data and
NEVER touches the runtime stores (``data/knowledge`` / ``data/chroma``). It reports:

* record counts per output and occupations per source;
* geography coverage kept SEPARATE for DE / EU / US / UK (an EU aggregate is never merged
  into Germany, §57) — German compensation being lower-resolution is reported honestly;
* compensation semantics coverage (country / currency / pay period / statistic);
* labour-market metric coverage by geography;
* crosswalk coverage by classification pair;
* provenance completeness (every fact/alias/occupation carries source + source_record_id);
* referential integrity (every fact/alias points at a known canonical occupation);
* the unresolved compensation→occupation linkage rate (honest, no fuzzy matching);
* absolute-path check on ``source_records.raw_file`` (§48 — repo-relative only).

Exit status: 0 when there are no CRITICAL findings (referential/absolute-path/round-trip),
1 otherwise. Warnings (e.g. unlinked compensation) never fail the audit.

Usage:
    python scripts/audit_normalized_knowledge.py
    python scripts/audit_normalized_knowledge.py --json
    python scripts/audit_normalized_knowledge.py --normalized-dir data/normalized
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.copilot.knowledge import canonical as C  # noqa: E402

_MODELS = {
    "occupations": C.CanonicalOccupation,
    "occupation_aliases": C.OccupationAlias,
    "occupation_crosswalks": C.OccupationCrosswalk,
    "compensation": C.CompensationRecord,
    "labour_market": C.LabourMarketRecord,
    "source_records": C.SourceRecord,
    "occupation_skills": C.KnowledgeFact,
    "technology_skills": C.KnowledgeFact,
    "knowledge_areas": C.KnowledgeFact,
    "tasks": C.KnowledgeFact,
    "work_activities": C.KnowledgeFact,
    "education_training": C.KnowledgeFact,
    "responsibilities": C.KnowledgeFact,
    "abilities": C.KnowledgeFact,
    "work_context": C.KnowledgeFact,
    "qualifications": C.KnowledgeFact,
    "credentials": C.KnowledgeFact,
}
_FACT_OUTPUTS = [n for n, m in _MODELS.items() if m is C.KnowledgeFact]


def _load(norm_dir: Path, name: str):
    model = _MODELS[name]
    pq, jl = norm_dir / f"{name}.parquet", norm_dir / f"{name}.jsonl"
    if pq.exists():
        return C.read_parquet(pq, model)
    if jl.exists():
        return C.read_jsonl(jl, model)
    return []


def audit(norm_dir: Path) -> dict:
    report: dict = {"normalized_dir": str(norm_dir), "critical": [], "warnings": [],
                    "counts": {}, "coverage": {}}

    if not norm_dir.is_dir():
        report["critical"].append(f"normalized dir not found: {norm_dir} — run the build first.")
        return report

    data = {name: _load(norm_dir, name) for name in _MODELS}
    for name, recs in data.items():
        if recs:
            report["counts"][name] = len(recs)

    occupations = data["occupations"]
    occ_ids = {o.occupation_id for o in occupations}

    # Occupations per source.
    report["coverage"]["occupations_by_source"] = dict(
        sorted(Counter(o.source for o in occupations).items()))

    # Classification coverage.
    report["coverage"]["occupations_with_classification"] = {
        "esco": sum(1 for o in occupations if o.esco_uri),
        "onet_soc": sum(1 for o in occupations if o.onet_soc_code),
        "isco": sum(1 for o in occupations if o.isco_code),
        "kldb": sum(1 for o in occupations if o.kldb_code),
        "soc": sum(1 for o in occupations if o.soc_code),
    }

    # Crosswalk coverage by classification pair.
    report["coverage"]["crosswalks_by_pair"] = dict(sorted(Counter(
        f"{x.source_classification.value}->{x.target_classification.value}"
        for x in data["occupation_crosswalks"]).items()))

    # --- Compensation coverage (semantics kept explicit) ------------------------------
    comp = data["compensation"]
    comp_geo = Counter()
    for r in comp:
        comp_geo[(r.country or (r.metadata or {}).get("geography_label") or "UNKNOWN")] += 1
    report["coverage"]["compensation"] = {
        "total": len(comp),
        "by_country": dict(sorted(comp_geo.items())),
        "by_currency": dict(sorted(Counter(r.currency for r in comp).items())),
        "by_pay_period": dict(sorted(Counter(
            (r.pay_period.value if r.pay_period else "unspecified") for r in comp).items())),
        "by_statistic": dict(sorted(Counter(
            (r.statistic.value if r.statistic else "unspecified") for r in comp).items())),
        "linked_to_occupation": sum(1 for r in comp if r.occupation_id),
        "unlinked_to_occupation": sum(1 for r in comp if not r.occupation_id),
    }

    # --- Labour-market coverage -------------------------------------------------------
    lm = data["labour_market"]
    lm_geo = Counter()
    for r in lm:
        lm_geo[(r.country or (r.metadata or {}).get("geography_label") or "UNKNOWN")] += 1
    report["coverage"]["labour_market"] = {
        "total": len(lm),
        "by_metric": dict(sorted(Counter(r.metric_type.value for r in lm).items())),
        "by_geography": dict(sorted(lm_geo.items())),
    }

    # --- Explicit DE / EU / US / UK split (§54–57): EU aggregate NEVER merged into DE, and
    # a sub-national region is never counted as its country. Uses the TYPED fields.
    def _bucket(country, region, geography_type, label):
        c = (country or "").upper()
        if c == "DE":
            return "DE"
        if c in ("US", "USA"):
            return "US"
        if c in ("UK", "GB"):
            return "UK"
        if c:
            return "OTHER_COUNTRY"
        lbl = (label or "").lower()
        if any(m in lbl for m in ("european union", "euro area", "european economic area")):
            return "EU_AGGREGATE"
        if region:
            return "SUBNATIONAL_REGION"
        return "OTHER"

    geo_split = {"DE": 0, "EU_AGGREGATE": 0, "US": 0, "UK": 0,
                 "OTHER_COUNTRY": 0, "SUBNATIONAL_REGION": 0, "OTHER": 0}
    for r in comp + lm:
        geo_split[_bucket(r.country, r.region, r.geography_type,
                          (r.metadata or {}).get("geography_label"))] += 1
    report["coverage"]["geography_split"] = geo_split
    report["coverage"]["geography_note"] = (
        "DE, EU_AGGREGATE, US, UK and SUBNATIONAL_REGION are reported separately; an EU "
        "aggregate is never counted as Germany, and a NUTS region is never rolled into its "
        "country. German compensation is comparatively lower-resolution (Eurostat SES; "
        "Destatis not yet acquired) — reported honestly, non-blocking.")

    # --- Competency frameworks --------------------------------------------------------
    comp_file = norm_dir / "competencies.parquet"
    if comp_file.exists():
        # competencies are stored as source Competency rows (no canonical model); count via
        # source_records of record_type=competency for provenance-backed framework coverage.
        fw = Counter(sr.metadata.get("framework") for sr in data["source_records"]
                     if sr.record_type == "competency")
        report["coverage"]["competency_frameworks"] = dict(sorted(
            (k or "unknown", v) for k, v in fw.items()))

    # --- Provenance completeness (§32/§33) --------------------------------------------
    all_facts = [f for name in _FACT_OUTPUTS for f in data[name]]
    prov_missing = sum(1 for f in all_facts if not f.source or not f.source_record_id)
    prov_missing += sum(1 for o in occupations if not o.source or not o.source_record_id)
    prov_missing += sum(1 for a in data["occupation_aliases"] if not a.source or not a.source_record_id)
    report["coverage"]["provenance"] = {
        "facts_total": len(all_facts),
        "records_missing_provenance": prov_missing,
    }
    if prov_missing:
        report["critical"].append(f"{prov_missing} records lack source/source_record_id (§33).")

    # --- Referential integrity: facts/aliases -> known canonical occupation -----------
    orphan_facts = sum(1 for f in all_facts if f.occupation_id not in occ_ids)
    orphan_aliases = sum(1 for a in data["occupation_aliases"]
                         if a.canonical_occupation_id not in occ_ids)
    report["coverage"]["referential_integrity"] = {
        "orphan_facts": orphan_facts, "orphan_aliases": orphan_aliases}
    if orphan_facts:
        report["critical"].append(f"{orphan_facts} facts reference an unknown occupation_id.")
    if orphan_aliases:
        report["critical"].append(f"{orphan_aliases} aliases reference an unknown occupation_id.")

    # --- Absolute-path check on raw_file (§48) ----------------------------------------
    abs_paths = sum(1 for sr in data["source_records"]
                    if sr.raw_file and (sr.raw_file.startswith("/") or sr.raw_file[1:2] == ":"))
    if abs_paths:
        report["critical"].append(f"{abs_paths} source_records carry a machine-absolute raw_file.")

    # --- Unresolved compensation linkage (honest warning, not a failure) --------------
    unlinked = report["coverage"]["compensation"]["unlinked_to_occupation"]
    if unlinked:
        report["warnings"].append(
            f"{unlinked} compensation rows are not yet linked to a canonical occupation "
            "(no official code crosswalk; no fuzzy title matching by design).")

    # --- Round-trip guard on a bounded sample -----------------------------------------
    try:
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            for name in ("occupations", "compensation", "labour_market"):
                if data[name]:
                    p = Path(d) / f"{name}.parquet"
                    C.write_parquet(data[name][:25], p)
                    back = C.read_parquet(p, _MODELS[name])
                    if len(back) != min(25, len(data[name])):
                        report["critical"].append(f"round-trip failed for {name}.")
    except C.ParquetUnavailableError:
        report["warnings"].append("pyarrow unavailable — round-trip check skipped (JSONL path).")

    # --- Build metadata presence ------------------------------------------------------
    bm = norm_dir / "build_metadata.json"
    report["build_metadata_present"] = bm.exists()
    if bm.exists():
        meta = json.loads(bm.read_text(encoding="utf-8"))
        report["build_metadata"] = {
            "schema_version": meta.get("canonical_schema_version"),
            "pipeline_version": meta.get("pipeline_version"),
            "sources": len(meta.get("source_versions", {})),
            "fingerprints": len(meta.get("source_checksums", [])),
        }
    else:
        report["warnings"].append("build_metadata.json missing — run the build.")

    report["status"] = "READY" if not report["critical"] else "ATTENTION"
    return report


def _print_human(rep: dict) -> None:
    print("NORMALIZED KNOWLEDGE AUDIT")
    print(f"  dir: {rep['normalized_dir']}")
    print(f"  status: {rep.get('status', 'ATTENTION')}")
    if rep.get("counts"):
        print("  record counts:")
        for k in sorted(rep["counts"]):
            print(f"    {k:<24} {rep['counts'][k]:>8}")
    cov = rep.get("coverage", {})
    if "occupations_by_source" in cov:
        print("  occupations by source:", cov["occupations_by_source"])
    if "compensation" in cov:
        c = cov["compensation"]
        print(f"  compensation: {c['total']} | countries={c['by_country']} "
              f"| periods={c['by_pay_period']} | linked={c['linked_to_occupation']} "
              f"unlinked={c['unlinked_to_occupation']}")
    if "labour_market" in cov:
        print(f"  labour_market: {cov['labour_market']['total']} "
              f"| metrics={cov['labour_market']['by_metric']}")
    if "geography_split" in cov:
        print(f"  geography split (DE/EU/US/UK separate): {cov['geography_split']}")
    if "competency_frameworks" in cov:
        print(f"  competency frameworks: {cov['competency_frameworks']}")
    if "crosswalks_by_pair" in cov:
        print(f"  crosswalks: {cov['crosswalks_by_pair']}")
    if rep.get("build_metadata"):
        print(f"  build metadata: {rep['build_metadata']}")
    for w in rep.get("warnings", []):
        print(f"  WARNING: {w}")
    for c in rep.get("critical", []):
        print(f"  CRITICAL: {c}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Audit the normalized knowledge layer.")
    ap.add_argument("--normalized-dir", default="data/normalized")
    ap.add_argument("--json", action="store_true", help="Emit the report as JSON.")
    args = ap.parse_args(argv)

    rep = audit(Path(args.normalized_dir))
    if args.json:
        print(json.dumps(rep, indent=2))
    else:
        _print_human(rep)
    return 0 if not rep["critical"] else 1


if __name__ == "__main__":
    sys.exit(main())
