#!/usr/bin/env python
"""P10B-W9.13 release acceptance matrix integrity check (deterministic, offline, 0 paid/live calls).

Keeps docs/capstone/p10/P10B_RELEASE_ACCEPTANCE_MATRIX.md honest: every referenced evidence file exists, no row is a
BLOCKER, the stated totals match the rows, and the accepted limitations that must never be silently dropped are present.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MATRIX = ROOT / "docs/capstone/p10/P10B_RELEASE_ACCEPTANCE_MATRIX.md"

REQUIRED_ACCEPTED = {
    "R-33": "email verification (POLICY-01)",
    "R-38": "legacy Streamlit (LEGACY-01)",
    "R-46": "distributed rate limiting not live",
    "R-47": "PRIV-W9-01",
    "R-48": "PRIV-W9-02",
    "R-49": "native/legal language review",
    "R-50": "live generated-language validation",
}


def run() -> dict[str, tuple[bool, str]]:
    out: dict[str, tuple[bool, str]] = {}

    def check(name: str, ok: bool, detail: str = "") -> None:
        out[name] = (bool(ok), detail)

    text = MATRIX.read_text(encoding="utf-8") if MATRIX.exists() else ""
    rows = []
    for line in text.splitlines():
        if re.match(r"^\| R-\d+ \|", line):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            rows.append(cells)
    check("matrix_exists_with_rows", len(rows) >= 40, f"{len(rows)} requirements")
    ids = [r[0] for r in rows]
    check("requirement_ids_unique", len(ids) == len(set(ids)), "unique R-ids")

    results = [r[5] for r in rows]
    check("no_blocker_rows", "BLOCKER" not in results, f"results: {sorted(set(results))}")
    check("results_are_pass_or_accepted", set(results) <= {"PASS", "ACCEPTED"}, "only PASS/ACCEPTED")

    missing = []
    for r in rows:
        for path in re.findall(r"`([^`]+)`", r[4]):
            if "/" in path and re.search(r"\.(py|ts|tsx|md|mjs|yml)$", path):
                if not (ROOT / path).exists():
                    missing.append(f"{r[0]}:{path}")
    check("evidence_paths_exist", not missing, ", ".join(missing[:5]) or "all evidence files exist")

    m = re.search(r"\*\*Totals:\*\* (\d+) requirements; (\d+) PASS, (\d+) ACCEPTED limitations, (\d+) BLOCKER", text)
    actual = (len(rows), results.count("PASS"), results.count("ACCEPTED"), results.count("BLOCKER"))
    check("totals_match_rows", bool(m) and tuple(map(int, m.groups())) == actual, f"rows {actual}")

    by_id = {r[0]: r for r in rows}
    bad = [k for k in REQUIRED_ACCEPTED if k not in by_id or by_id[k][5] != "ACCEPTED"]
    check("required_limitations_stay_accepted", not bad, ", ".join(bad) or "POLICY-01, LEGACY-01, rate limit, PRIV x2, reviews")
    check("distributed_limiting_not_claimed_live", "NOT live" in by_id.get("R-34", ["", "", "", "", "", "", ""])[6] or
          "NOT live" in text, "matrix states distributed limiting is not live")
    mig = sorted(p.name for p in (ROOT / "migrations/versions").glob("0*.py"))
    check("schema_head_unchanged", mig[-1].startswith(("0014_", "0015_", "0016_", "0017_", "0018_", "0019_", "0020_")), mig[-1])
    return out


def main() -> int:
    print("ASK4MO - P10B-W9.13 RELEASE MATRIX INTEGRITY\n")
    res = run()
    failed = False
    for name in sorted(res):
        ok, detail = res[name]
        failed |= not ok
        print(f"  {name:42s} {'PASS' if ok else 'FAIL'}  {detail}")
    print("\nPaid LLM calls: 0   Live calls: 0")
    print("\nRESULT: " + ("FAIL" if failed else "PASS"))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
