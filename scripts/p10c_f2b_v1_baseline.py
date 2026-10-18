#!/usr/bin/env python
"""P10C-F2B UK V1 baseline (READ-ONLY, metadata only). Opens the local V1 compensation store immutably and reports counts for the ``ons_ashe`` rows: no titles, no pay values. Writes nothing to any
store; ``--out`` is validated before any data is read (never inside data/ or evaluations/). Missing local data is a controlled exit 3."""

from __future__ import annotations

import argparse
import collections
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src.knowledge_foundation.pathsafe import output_is_protected  # noqa: E402


def baseline(db: Path) -> dict:
    st = db.stat()
    con = sqlite3.connect(f"file:{db.as_posix()}?mode=ro&immutable=1", uri=True)
    try:
        rows = con.execute("select occupation_code, country, region, industry, year, currency, pay_period, statistic_type, sample_quality, source_url, occupation_title from compensation_records where source_id='ons_ashe'").fetchall()
    finally:
        con.close()
    codes = [r[0] for r in rows]
    nonnull = [c for c in codes if c]
    dup = [c for c, n in collections.Counter(nonnull).items() if n > 1]
    after = db.stat()
    return {"schema": "p10c_f2b_uk_v1_baseline/1", "note": "Metadata only: counts and verdicts. No titles and no pay values. Produced read-only.", "records": len(rows),
            "rows_without_occupation_code": len(codes) - len(nonnull), "distinct_codes": len(set(nonnull)), "duplicate_code_rows": sum(collections.Counter(nonnull)[c] - 1 for c in dup),
            "code_length_distribution": dict(sorted(collections.Counter(len(c) for c in nonnull).items())), "codes_all_digits": all(c.isdigit() for c in nonnull),
            "countries": sorted({r[1] for r in rows}), "currencies": sorted({r[5] for r in rows}), "pay_periods": sorted({r[6] for r in rows}), "statistics": sorted({r[7] for r in rows}),
            "reference_years": sorted({r[4] for r in rows if r[4]}), "sample_quality": dict(collections.Counter(r[8] for r in rows)), "rows_with_region": sum(1 for r in rows if r[2]),
            "rows_with_industry": sum(1 for r in rows if r[3]), "rows_with_title": sum(1 for r in rows if r[10]), "source_urls": sorted({r[9] for r in rows if r[9]}),
            "v1_lacks": ["classification edition (SOC 2010 or 2020)", "dataset table and edition (Table 14.1a, provisional or revised)", "population (full-time) and pay basis", "provenance and file hash"],
            "store_modified_by_this_run": (st.st_mtime_ns, st.st_size) != (after.st_mtime_ns, after.st_size)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(ROOT / "data/knowledge/compensation.db"))
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    if a.out and output_is_protected(a.out, ROOT):
        print("refusing to write inside a protected location")
        return 2
    db = Path(a.db)
    if not db.exists():
        print("local V1 store not found")
        return 3
    out = baseline(db)
    text = json.dumps(out, indent=1)
    if a.out:
        Path(a.out).write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
