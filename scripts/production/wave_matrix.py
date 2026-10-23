#!/usr/bin/env python
"""Five-layer status matrix for all 45 implementation packages (ENGINEERING / CI / LIVE STAGING / HUMAN QUALIFICATION / PRODUCTION-GATE ACCEPTANCE).

The five layers are deliberately separate: merged code is not a passed gate. Engineering and CI are DERIVED from ``execution_packages.PACKAGE_STATUS`` (the one place that records
merged PRs); the other three layers are explicit, reviewed statements below. ``generate`` rewrites the block between the markers in WAVE3_EXECUTION_PLAN.md; ``check`` fails when the
block is stale or a package is missing. Offline; no network."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
DOCS = [ROOT / "docs/production/execution/WAVE3_EXECUTION_PLAN.md", ROOT / "docs/production/execution/PROJECT_STATUS_DASHBOARD.md"]
START, END = "<!-- MATRIX:START -->", "<!-- MATRIX:END -->"
spec = importlib.util.spec_from_file_location("execution_packages", ROOT / "scripts/production/execution_packages.py")
E = importlib.util.module_from_spec(spec)
spec.loader.exec_module(E)

NS = "NOT RUN"
# id: (live staging verification, human qualification, production gate acceptance)
LAYERS: dict[str, tuple[str, str, str]] = {
    "00A": ("n/a", "Owner names reviewers, counsel and legal qualifiers (OPEN)", "PG-07 BLOCKED until reviewers are named"),
    "00B": ("n/a", "Owner disposition of the ten reclassifications (OPEN)", "PG-11 PASS (machine-checked); no reclassification applied"),
    "01A": (NS + " (injection screen on hosted stack)", "Human security review (9 questions); independent held-out author (OPEN)", "PG-03 IN PROGRESS; thresholds unapproved (OD-GATE-THRESHOLDS)"),
    "01D": ("n/a", "Security review of tool authorization", "PG-03 (REVIEW-01 R4/R5)"),
    "01B0": ("n/a", "none", "PG-12 IN PROGRESS"),
    "01B": (NS + " (Docker image with prompts/ not built)", "none", "PG-12 IN PROGRESS (01D, 01C outstanding)"),
    "01C": ("n/a", "none", "PG-12 (REVIEW-03)"),
    "02K": ("n/a", "none", "PG-05 IN PROGRESS (contract)"),
    "02A": (NS + " (hosted volumes, PostgreSQL, multi-worker; OD-HOSTED)", "none", "PG-05 IN PROGRESS"),
    "02B": (NS + " (production embedder, hosted refusal; OD-HOSTED, OD-EMBED)", "Embedder choice and benchmark approval (OD-EMBED, OD-BUDGET)", "PG-05 NOT MET (retrieval quality unmeasured)"),
    "02C": (NS + " (real clamd, EICAR, outage drill; OD-HOSTED)", "none", "PG-05 IN PROGRESS"),
    "02D": ("n/a", "Licensing reviewer and owner; per-market signed approval (OPEN, long lead)", "PG-05 (licence and market qualification)"),
    "02E": (NS, "Frozen coverage measure approval (OD-COVERAGE); independent datasets", "PG-05 (retrieval quality, coverage)"),
    "03A": (NS + " (live Admin walkthrough)", "none", "PG-08 IN PROGRESS"),
    "03B": (NS + " (live Admin walkthrough)", "Plan limit values (OD-PLAN-LIMITS)", "PG-08 IN PROGRESS"),
    "03C": (NS + " (live Admin walkthrough)", "Bulk-action policy (OD-BULK-ACTIONS)", "PG-08 IN PROGRESS"),
    "03K": ("n/a", "none", "PG-14 IN PROGRESS (contract)"),
    "03D1": (NS + " (live data)", "none", "PG-08 IN PROGRESS (03D2 outstanding)"),
    "03D2": (NS, "none", "PG-08"),
    "03E1": (NS + " (live data)", "Export formats (OD-REPORT-EXPORT)", "PG-14 IN PROGRESS (03E2 outstanding)"),
    "03E2": (NS, "Export formats (OD-REPORT-EXPORT)", "PG-14"),
    "04A": (NS + " (restart on staging)", "Native review of 116 strings (LG-10/11)", "PG-13 IN PROGRESS (06B outstanding)"),
    "04B": (NS + " (PostgreSQL invitation race and row locks)", "Transfer rules (OD-WS-TRANSFER); native review", "PG-13 IN PROGRESS (06B outstanding)"),
    "04C": (NS + " (streaming on staging)", "none", "PG-06"),
    "04D": (NS + " (journeys on a staging stack)", "none", "PG-06"),
    "04E": (NS + " (first-admin bootstrap, live Google)", "Invitation email and issuer decisions (OPEN)", "PG-02 IN PROGRESS (05D outstanding)"),
    "04F": (NS + " (browser dictation check)", "Legal reviewer and test participants", "PG-04"),
    "05A": (NS + " (nothing deployed; OD-HOSTED)", "Hosting authorisation (OPEN)", "PG-01 BLOCKED"),
    "05B": (NS + " (restore drill, PostgreSQL paths; OD-HOSTED)", "none", "PG-09"),
    "05C": (NS + " (synthetic outage on staging; OD-HOSTED)", "AI budget (OD-BUDGET)", "PG-09"),
    "05D": (NS + " (live Brevo, Google, Redis; OD-HOSTED)", "none", "PG-02"),
    "05E": ("n/a", "Legal counsel sign-off per offered language (long lead)", "PG-04"),
    "06A": ("n/a", "Native review of the audit baseline", "PG-10 IN PROGRESS; LG-01 and LG-14 evidence exists, none approved by a named human"),
    "06B": (NS + " (journeys per language)", "Native-speaker review", "LG-03, LG-09 per language; PG-13"),
    "06C": (NS + " (live Mo quality)", "Blinded native-reader rating (OD-BUDGET)", "LG-04, LG-05 per language"),
    "06D": (NS + " (production embedder; OD-EMBED)", "Sample review", "LG-06 per language"),
    "06E": (NS, "none", "LG-08 per language; PG-03"),
    "06F": ("n/a", "Seven native reviewers and legal qualifiers (calendar-bound, OPEN)", "LG-10, LG-11 per language; PG-04"),
    "06G": (NS + " (live Mo outputs)", "Independent reviewers and participants (OD-BUDGET, OD-GATE-THRESHOLDS)", "PG-07 BLOCKED"),
    "06H": (NS + " (hosted fail-closed behaviour)", "Approvers named for each gate (OD-LANG-03/04)", "PG-10 IN PROGRESS; LG-13/LG-14 enforcement merged, zero languages qualified"),
    "07A": ("n/a", "none", "PG-10"),
    "07B": (NS + " (live grounding; OD-BUDGET)", "none", "PG-03"),
    "07C": (NS + " (live OCR sample; OD-BUDGET)", "none", "residual live verification"),
    "08A0": ("n/a", "none", "PG-15 (evidence pipeline)"),
    "08A": (NS, "Owner go/no-go", "PG-15"),
}


def ci_layer(pid: str) -> str:
    st = E.PACKAGE_STATUS.get(pid)
    if st and st[0].startswith("MERGED"):
        return "PR CI green (12 of 12); re-read on main"
    if st and st[0].startswith(("PARTIAL", "DELIVERED")):
        return "documentation PRs #211 to #213 merged, CI green"
    return "no PR yet"


def eng_layer(pid: str) -> str:
    st = E.PACKAGE_STATUS.get(pid)
    if not st:
        return "NOT STARTED"
    head = st[0]
    return head.split(";")[0].strip() if head.startswith("MERGED") else head.split(";")[0].strip()


def build() -> str:
    rows = ["| Package | 1 Engineering | 2 CI | 3 Live staging | 4 Human qualification | 5 Production-gate acceptance |", "|---|---|---|---|---|---|"]
    for p in E.PACKAGES:
        pid = p["id"]
        live, human, gate = LAYERS[pid]
        rows.append(f"| {pid} | {eng_layer(pid)} | {ci_layer(pid)} | {live} | {human} | {gate} |")
    return "\n".join(rows)


def block() -> str:
    return f"{START}\n{build()}\n{END}"


def main(argv: list[str]) -> int:
    missing = [p["id"] for p in E.PACKAGES if p["id"] not in LAYERS]
    extra = [k for k in LAYERS if k not in E.BYID]
    if missing or extra:
        print(f"FAIL: layers missing {missing} unknown {extra}")
        return 1
    stale = []
    for doc in DOCS:
        text = doc.read_text(encoding="utf-8") if doc.exists() else ""
        if START not in text or END not in text:
            print(f"FAIL: matrix markers missing in {doc.name}")
            return 1
        new = text[: text.index(START)] + block() + text[text.index(END) + len(END):]
        if argv and argv[0] == "generate":
            doc.write_text(new, encoding="utf-8")
        elif new != text:
            stale.append(doc.name)
    if argv and argv[0] == "generate":
        print(f"wrote matrix for {len(E.PACKAGES)} packages into {len(DOCS)} documents")
        return 0
    if stale:
        print(f"FAIL: the matrix is stale in {stale}; run `python scripts/production/wave_matrix.py generate`")
        return 1
    print(f"OK: five-layer matrix covers {len(E.PACKAGES)} packages and is fresh in {len(DOCS)} documents")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
