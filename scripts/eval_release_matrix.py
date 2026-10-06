#!/usr/bin/env python
"""P10B integrated release acceptance matrix integrity check (W9.13, extended by W11; deterministic, offline, 0 paid/live calls).

Keeps docs/capstone/p10/P10B_RELEASE_ACCEPTANCE_MATRIX.md honest: unique ids, only the PASS / ACCEPTED / BLOCKER vocabulary, every referenced evidence file exists, no BLOCKER
for a green verdict, ACCEPTED rows carry a rationale, totals recompute from the rows (nothing is hard-coded), the historical W9.13 origin and the W10.14 / W11 evidence are
linked and present, the closed PRIV-W9 findings are not still described as open, and the limitations that must never be silently dropped stay visible.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
MATRIX = ROOT / "docs/capstone/p10/P10B_RELEASE_ACCEPTANCE_MATRIX.md"

# Limitations that must remain ACCEPTED (with a rationale) until separately closed by evidence.
REQUIRED_ACCEPTED = {
    "R-33": "email verification (POLICY-01)", "R-38": "legacy Streamlit (LEGACY-01)", "R-46": "distributed rate limiting not live",
    "R-49": "native/legal language review", "R-50": "live generated-language validation", "R-51": "metadata localization and bundle optimisation",
    "R-93": "support attachments", "R-94": "Admin workspace deactivation / universal search", "R-95": "live billing, secret vault, external paging",
    "R-96": "PostgreSQL-only paths not exercised live", "R-97": "Google OIDC live behaviour"
}
# Rows that were ACCEPTED in W9.13 and are now evidence-closed: they must be PASS and say where they were closed.
CLOSED_SINCE_W913 = {"R-47": "W10.10", "R-48": "W10.10", "R-52": "W11"}


def run() -> dict[str, tuple[bool, str]]:
    out: dict[str, tuple[bool, str]] = {}

    def check(name: str, ok: bool, detail: str = "") -> None:
        out[name] = (bool(ok), detail)

    text = MATRIX.read_text(encoding="utf-8") if MATRIX.exists() else ""
    rows = []
    for line in text.splitlines():
        if re.match(r"^\| R-\d+ \|", line):
            rows.append([c.strip() for c in line.strip().strip("|").split("|")])
    check("matrix_exists_with_rows", len(rows) >= 90 and all(len(r) == 7 for r in rows), f"{len(rows)} requirements x 7 columns")
    ids = [r[0] for r in rows]
    check("requirement_ids_unique", len(ids) == len(set(ids)), "unique R-ids")
    nums = sorted(int(i[2:]) for i in ids)
    check("requirement_ids_contiguous_and_historical_range_preserved", nums == list(range(1, len(nums) + 1)) and nums[:52] == list(range(1, 53)), f"R-01..R-{len(nums):02d}")

    results = [r[5] for r in rows]
    check("every_row_has_a_result", all(results), "no silent missing result")
    check("results_use_only_the_pass_accepted_blocker_vocabulary", set(results) <= {"PASS", "ACCEPTED", "BLOCKER"}, f"results: {sorted(set(results))}")
    check("no_blocker_rows_for_a_green_verdict", "BLOCKER" not in results, "0 BLOCKER")
    check("accepted_rows_carry_a_rationale", all(len(r[6]) >= 20 for r in rows if r[5] == "ACCEPTED"), "every ACCEPTED row states why it is acceptable")

    missing = []
    for r in rows:
        for path in re.findall(r"`([^`]+)`", r[4]):
            if "/" in path and re.search(r"\.(py|ts|tsx|md|mjs|yml|json)$", path) and "*" not in path:
                if not (ROOT / path).exists():
                    missing.append(f"{r[0]}:{path}")
    check("evidence_paths_exist", not missing, ", ".join(missing[:5]) or "all evidence files exist")

    m = re.search(r"\*\*Totals:\*\* (\d+) requirements; (\d+) PASS, (\d+) ACCEPTED limitations, (\d+) BLOCKER", text)
    actual = (len(rows), results.count("PASS"), results.count("ACCEPTED"), results.count("BLOCKER"))
    check("totals_match_rows", bool(m) and tuple(map(int, m.groups())) == actual, f"rows {actual}")

    by_id = {r[0]: r for r in rows}
    bad = [k for k in REQUIRED_ACCEPTED if k not in by_id or by_id[k][5] != "ACCEPTED"]
    check("required_limitations_stay_accepted", not bad, ", ".join(bad) or "POLICY-01, LEGACY-01, rate limiting, reviews, Admin and live-validation limitations")
    bad = [k for k, w in CLOSED_SINCE_W913.items() if k not in by_id or by_id[k][5] != "PASS" or w not in by_id[k][6]]
    check("rows_closed_since_w9_13_are_pass_and_say_where", not bad, ", ".join(bad) or "R-47, R-48 (W10.10) and R-52 (W11)")
    check("priv_w9_findings_not_described_as_open", "Closed in W10.10; historical W9.13 result was ACCEPTED." in by_id.get("R-47", ["", "", "", "", "", "", ""])[6]
          and "Closed in W10.10; historical W9.13 result was ACCEPTED." in by_id.get("R-48", ["", "", "", "", "", "", ""])[6]
          and not re.search(r"PRIV-W9-0[12][^|]*\|[^|]*\|[^|]*\|[^|]*\|\s*ACCEPTED", text))
    r98 = by_id.get("R-98", ["", "", "", "", "", "", ""])
    check("layout_w11_01_history_preserved_and_corrected", r98[5] == "PASS" and "LAYOUT-W11-01" in r98[6] and "42px" in r98[6] and "lg" in r98[6], "found in W11, corrected by a bounded owner-approved fix; finding history kept")
    check("distributed_limiting_not_claimed_live", "NOT live" in by_id.get("R-34", ["", "", "", "", "", "", ""])[6] or "NOT live" in text, "matrix states distributed limiting is not live")
    check("historical_w9_13_origin_linked_and_present", "w9/P10B_W9_13_FULL_REQUALIFICATION.md" in text and (ROOT / "docs/capstone/p10/w9/P10B_W9_13_FULL_REQUALIFICATION.md").exists(), "W9.13 history preserved")
    check("w10_14_and_w11_evidence_present", (ROOT / "docs/capstone/admin/W10_14_FULL_ADMIN_QUALIFICATION.md").exists() and (ROOT / "docs/capstone/p10/P10B_W11_INTEGRATED_REQUALIFICATION.md").exists()
          and all(k in by_id for k in ("R-53", "R-81", "R-88", "R-90")), "W10.14 + W11 documents and rows")
    mig = sorted(p.name for p in (ROOT / "migrations/versions").glob("0*.py"))
    check("schema_head_matches_the_matrix", mig[-1].startswith("0025_security_audit_incidents") and "0025_security_audit_incidents" in by_id.get("R-39", ["", "", "", "", "", "", ""])[3], mig[-1])
    check("no_rc_p10_003_created", not (ROOT / "artifacts/capstone/p10/RC-P10-003").exists() and "RC-P10-003" not in "".join(p.name for p in (ROOT / "artifacts/capstone/p10").glob("*")), "W11 does not create the RC")
    return out


def main() -> int:
    print("ASK4MO - P10B INTEGRATED RELEASE MATRIX INTEGRITY\n")
    res = run()
    failed = False
    for name in sorted(res):
        ok, detail = res[name]
        failed |= not ok
        print(f"  {name:62s} {'PASS' if ok else 'FAIL'}  {detail}")
    print("\nPaid LLM calls: 0   Live calls: 0")
    print("\nRESULT: " + ("FAIL" if failed else "PASS"))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
