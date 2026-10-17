#!/usr/bin/env python
"""GKB-5 existing-compensation inventory (P10C-C). READ-ONLY and metadata-only: opens the local V1 compensation store immutably, prints counts and verdicts (no occupation titles, no
salary values), writes nothing to any store. ``--out`` is validated BEFORE any data is read (never inside data/ or evaluations/, exit 2); missing local data is a controlled exit 3."""

from __future__ import annotations

import argparse
import collections
import json
import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src.knowledge_foundation.pathsafe import output_is_protected  # noqa: E402

_SOC = re.compile(r"^\d{2}-\d{4}$")


def inventory(root: Path) -> dict:
    db = root / "data/knowledge/compensation.db"
    con = sqlite3.connect(f"file:{db.as_posix()}?mode=ro&immutable=1", uri=True)
    try:
        cols = [c[1] for c in con.execute("pragma table_info(compensation_records)")]
        rows = con.execute("select source_id, occupation_code, occupation_title, country, region, industry, year, currency, pay_period, statistic_type, value, lower_bound, upper_bound, "
                           "sample_quality, source_url from compensation_records").fetchall()
    finally:
        con.close()
    by_src: dict[str, list] = collections.defaultdict(list)
    for r in rows:
        by_src[r[0]].append(r)
    per = {}
    for sid, rs in sorted(by_src.items()):
        codes = [r[1] for r in rs]
        per[sid] = {
            "records": len(rs), "distinct_native_codes": len(set(codes)), "duplicate_native_code_rows": len(codes) - len(set(codes)), "countries": sorted({r[3] for r in rs}),
            "currencies": sorted({r[7] for r in rs}), "pay_periods": sorted({r[8] for r in rs}), "statistics": sorted({r[9] for r in rs}), "reference_years": sorted({r[6] for r in rs if r[6]}),
            "sample_quality": dict(collections.Counter(r[13] for r in rs)), "rows_with_value": sum(1 for r in rs if r[10] is not None), "rows_with_bounds": sum(1 for r in rs if r[11] is not None and r[12] is not None),
            "rows_with_title": sum(1 for r in rs if r[2]), "rows_with_region": sum(1 for r in rs if r[4]), "rows_with_industry": sum(1 for r in rs if r[5]), "source_urls": sorted({r[14] for r in rs if r[14]}),
            "native_code_length_distribution": dict(sorted(collections.Counter(len(c or "") for c in codes).items())),
            "codes_in_xx_xxxx_shape": sum(1 for c in codes if _SOC.match(c or "")),
        }
    missing = [f for f in ("taxonomy_scheme", "taxonomy_edition", "source_edition", "pay_basis", "publication_date", "reference_period", "evidence_class", "precedence_category", "provenance",
                           "geography_level", "occupation_level", "qualification_status") if f not in cols]
    reg = json.loads((root / "src/knowledge_foundation/data/source_registry_baseline.json").read_text(encoding="utf-8"))["sources"] if (root / "src/knowledge_foundation/data/source_registry_baseline.json").exists() else []
    relevant = {"bls_oews", "ons_ashe", "onet", "eurostat_earnings", "ba_entgeltatlas", "destatis", "bls_ooh", "cedefop_skills_forecast", "adzuna"}
    sources = {s["source_id"]: {k: s[k] for k in ("publisher", "dataset_name", "dataset_version", "licence_id", "licence_status", "redistribution", "attribution_required", "origin", "approval_status",
                                                  "evidence_class", "precedence_category", "taxonomy")} for s in reg if s["source_id"] in relevant}
    k1 = root / "data/knowledge/governed/k1_de_compensation.json"
    k1_meta = None
    if k1.exists():
        d = json.loads(k1.read_text(encoding="utf-8"))
        k1_meta = {"records": len(d.get("records") or d.get("occupations") or []), "requirement": d.get("requirement"), "jurisdiction": d.get("jurisdiction"), "currency": d.get("currency"),
                   "pay_unit": d.get("pay_unit"), "reference_year": d.get("reference_year"), "classification": "engineering draft (self-declared in the dataset module)"}
    return {"schema": "gkb5_compensation_inventory/1", "note": "Metadata only: counts and verdicts. No titles and no salary values. Produced read-only.",
            "v1_columns": cols, "records": len(rows), "per_source": per, "v1_lacks": missing,
            "v1_limitations": ["pay basis (gross/net) is not recorded", "taxonomy namespace and edition are implicit", "source edition and publication date are not recorded",
                               "bounds carry no declared semantics (the reader uses the published 10th and 90th percentiles)", "values are floating-point REAL", "no occupation title is stored",
                               "no evidence class, precedence, qualification or provenance fields", "retrieval filters by country, year, native code or title substring only"],
            "registry_state_of_relevant_sources": sources, "k1_german_governed_set": k1_meta,
            "eurostat_structured_earnings_available_locally": False,
            "eurostat_note": "the source status records one indexed local document (text chunks) and no normalised records; no structured Eurostat earnings table is present"}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out")
    ap.add_argument("--root", default=str(ROOT))
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()
    if args.out and output_is_protected(args.out, root):
        print("refusing to write inside data/ or evaluations/", file=sys.stderr)
        return 2
    try:
        out = inventory(root)
    except (FileNotFoundError, sqlite3.OperationalError) as exc:
        print(f"inventory unavailable: required local knowledge data is missing ({Path(getattr(exc, 'filename', None) or 'unknown').name}); nothing was written", file=sys.stderr)
        return 3
    text = json.dumps(out, indent=1, sort_keys=True, ensure_ascii=False, default=str) + "\n"
    if args.out:
        dest = Path(args.out).resolve()
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
