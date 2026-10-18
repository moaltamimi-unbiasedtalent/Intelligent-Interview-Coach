"""P10C-F1 dossier validator and Markdown renderer. Read-only: no network, no database, no dataset access.

    python scripts/p10c_f1_dossier.py --check     validate the dossier and that the committed Markdown matches its rendering
    python scripts/p10c_f1_dossier.py --write     re-render the Markdown documents from the dossier
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOSSIER = ROOT / "docs/capstone/p10/p10c_f1/source_dossier.json"
BASELINE = ROOT / "src/knowledge_foundation/data/source_registry_baseline.json"
REGISTER = ROOT / "docs/capstone/p10/p10c_e/SOURCE_APPROVAL_REGISTER.json"
DOCS = {"approval": ROOT / "docs/capstone/p10/P10C_F1_SOURCE_APPROVAL_REGISTER.md", "packages": ROOT / "docs/capstone/p10/P10C_F1_ACQUISITION_PACKAGES.md"}
AUTHORIZED_ENTRIES = {"us_soc_2018", "us_bls_oews"}      # P10C-F2A owner authorisation, 2026-10-18 (acquisition and isolated ingestion only)
RECORDED_DECISIONS = {"D-04": "APPROVED", "D-12": "APPROVED", "D-13": "APPROVED", "D-15": "APPROVED", "D-09": "DEFERRED", "D-20": "DEFERRED"}
AUTH_NOTE = "(owner-authorised for acquisition, 2026-10-18)"
STATUSES = {"VERIFIED_OFFICIAL_PAGE", "CORROBORATED_SECONDARY", "NOT_VERIFIED"}


def load() -> dict:
    return json.loads(DOSSIER.read_text(encoding="utf-8"))


def validate(d: dict) -> list[str]:
    errs: list[str] = []
    ents = d["entries"]
    ids = [e["id"] for e in ents]
    if len(ids) != len(set(ids)):
        errs.append("duplicate entry ids")
    covered = {r for e in ents for r in e["registry_ids"]}
    base = {s["source_id"] for s in json.loads(BASELINE.read_text())["sources"]}
    if base - covered:
        errs.append(f"registry sources missing from dossier: {sorted(base - covered)}")
    rcovered = {r for e in ents for r in e["register_ids"]}
    reg = {e["register_id"] for e in json.loads(REGISTER.read_text())["entries"]}
    if reg - rcovered:
        errs.append(f"P10C-E register entries missing from dossier: {sorted(reg - rcovered)}")
    for e in ents:
        if e["runtime_authorized"]:
            errs.append(f"{e['id']}: runtime authorisation is not permitted")
        if e["id"] in AUTHORIZED_ENTRIES:
            if e["approval_status"] != "ACQUISITION_AUTHORIZED_RUNTIME_NOT_APPROVED" or not e["acquisition_authorized"]:
                errs.append(f"{e['id']}: expected the recorded Package 1 acquisition authorisation")
        elif e["approval_status"] != "NOT_APPROVED" or e["acquisition_authorized"]:
            errs.append(f"{e['id']}: approval state is not NOT_APPROVED")
        for k in ("edition", "reference_period", "machine_access", "update_frequency", "geography", "classification"):
            if e[k]["status"] not in STATUSES:
                errs.append(f"{e['id']}.{k}: bad status")
        if e["licence"]["legal_review_needed"] and not e["licence"]["legal_review_reason"]:
            errs.append(f"{e['id']}: legal review without reason")
        if e["licence"]["terms_clear"] == "clear" and not (e["licence"]["statement_found"] and e["licence"]["corroborated_against_publisher"]):
            errs.append(f"{e['id']}: clear licence without a corroborated statement")
        if e["proposal"]["evidence_class"].startswith("C4"):
            errs.append(f"{e['id']}: C4 is abstain, not a source class")
    dec = [x["id"] for x in d["owner_decisions"]]
    for i in range(1, 20):
        if f"D-{i:02d}" not in dec:
            errs.append(f"decision D-{i:02d} missing")
    for x in d["owner_decisions"]:
        want = RECORDED_DECISIONS.get(x["id"])
        got = (x["owner_decision"] or {}).get("decision")
        if got != want:
            errs.append(f"{x['id']}: recorded decision {got!r} differs from the owner-authorised {want!r}")
    used = {x for e in ents for x in e["decisions"]}
    if used - set(dec):
        errs.append(f"entries reference unknown decisions: {sorted(used - set(dec))}")
    pk = d["acquisition_packages"]
    if [p["package"] for p in pk] != list(range(1, 8)) or [p["approved"] for p in pk] != [True] + [False] * 6:
        errs.append("acquisition packages must be 1..7 with only package 1 owner-authorised")
    for p in pk:
        if set(p["sources"]) - set(ids):
            errs.append(f"package {p['package']} references unknown entries")
    if [x["id"] for x in d.get("owner_policies", [])] != ["POLICY-A", "POLICY-B", "POLICY-C", "POLICY-D", "POLICY-E", "POLICY-F", "POLICY-G", "POLICY-H", "POLICY-I", "POLICY-J", "POLICY-K"]:
        errs.append("owner policies A-K (2026-10-18) must be recorded")
    pc = d["product_coverage"]
    if len(pc["wiring_class"]["cases"]) != 13 or len(pc["ambiguity_class"]["cases"]) != 13:
        errs.append("product-coverage case split must be 13 + 13")
    return errs


def row(*cells: str) -> str:
    return "| " + " | ".join(str(c).replace("|", "/").replace("\n", " ") for c in cells) + " |"


def render_approval(d: dict) -> str:
    out = ["# P10C-F1 Source Approval Register", "", "*Generated from `docs/capstone/p10/p10c_f1/source_dossier.json` by `scripts/p10c_f1_dossier.py`. Package 1 (SOC 2018 and OEWS May 2025) carries a recorded owner authorisation for acquisition and isolated ingestion only (2026-10-18); every other source is NOT_APPROVED and nothing is runtime-authorised.*", "",
           "Verification vocabulary: statement found / corroborated against the publisher / terms clear. Verification is not approval. `legal` marks sources where qualified legal review is needed.", "",
           row("Entry", "Publisher / dataset", "Edition (status)", "Licence", "Redistribution", "Commercial", "Attribution", "Legal review", "Proposed class", "Precedence", "Package", "Decisions", "State"),
           row(*["---"] * 13)]
    for e in d["entries"]:
        l = e["licence"]
        out.append(row(e["id"], f"{e['publisher']}: {e['dataset']}", f"{e['edition']['value'][:90]} ({e['edition']['status']})", f"{(l['name'] or 'NOT VERIFIED')[:100]} [{l['terms_clear']}]", l["redistribution"], l["commercial_use"], l["attribution"],
                       "yes" if l["legal_review_needed"] else "no", e["proposal"]["evidence_class"][:60], e["proposal"]["precedence_category"], e["package"] or "n/a", ", ".join(e["decisions"]), e["approval_status"]))
    out += ["", "## Sources needing qualified legal review", ""]
    for e in d["entries"]:
        if e["licence"]["legal_review_needed"]:
            out.append(f"- **{e['id']}**: {e['licence']['legal_review_reason']}")
    out += ["", "## Sources ready for owner consideration (clear terms; still NOT approved)", ""]
    out += [f"- **{e['id']}** ({e['licence']['name']})" for e in d["entries"] if e["licence"]["terms_clear"] == "clear" and not e["licence"]["legal_review_needed"]]
    out += ["", "## Blocked or unverified sources", ""]
    out += [f"- **{e['id']}**: licence {e['licence']['terms_clear']}" for e in d["entries"] if e["licence"]["terms_clear"] in ("not_verified", "unclear")]
    return "\n".join(out) + "\n"


def render_packages(d: dict) -> str:
    out = ["# P10C-F1 Acquisition Packages", "", "*Generated from the dossier. Seven independently approvable packages; only Package 1 (US core) has a recorded owner authorisation, for acquisition and isolated non-production ingestion; no data has been downloaded.*", ""]
    for p in d["acquisition_packages"]:
        out += [f"## Package {p['package']}: {p['title']}", "", f"- **Sources:** {', '.join(p['sources'])}", f"- **Why needed:** {p['why_needed']}", f"- **Capability:** {p['capability_unlocked']}",
                f"- **Licensing status:** {json.dumps(p['licensing_status'])}", "- **Acquisition requirements:** " + "; ".join(p["acquisition_requirements"]), "- **Engineering dependencies:** " + "; ".join(p["engineering_dependencies"]),
                "- **Qualification tests:** " + "; ".join(p["qualification_tests"]), "- **Owner approval needed:** " + ", ".join(p["owner_approval_needed"]),
                "- **Legal review sources:** " + (", ".join(p["legal_review_sources"]) or "none identified"), f"- **Ready for owner consideration:** {p['ready_for_owner_consideration']} {AUTH_NOTE if p['approved'] else '(not approved)'}", "- **Limitations:**"]
        out += [f"  - {x}" for x in p["limitations"]] + [""]
    return "\n".join(out)


def main() -> int:
    d = load()
    errs = validate(d)
    if "--write" in sys.argv:
        DOCS["approval"].write_text(render_approval(d), encoding="utf-8")
        DOCS["packages"].write_text(render_packages(d), encoding="utf-8")
    if "--check" in sys.argv:
        for k, fn in (("approval", render_approval), ("packages", render_packages)):
            if not DOCS[k].exists() or DOCS[k].read_text(encoding="utf-8") != fn(d):
                errs.append(f"{DOCS[k].name} does not match the dossier rendering")
    print("P10C-F1 DOSSIER:", "OK" if not errs else "FAIL")
    for e in errs:
        print(" -", e)
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())
