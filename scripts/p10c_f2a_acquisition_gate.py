"""P10C-F2A acquisition gate. Read-only: no network, no database, no download.

    python scripts/p10c_f2a_acquisition_gate.py --check

Validates the acquisition manifest and the recorded preconditions, and reports whether the authorised acquisition may proceed.
Exit 0 means the records are internally consistent. ``--verify-hashes`` re-hashes the staged raw files when present. Isolated ingestion is allowed only when
every precondition (including registry lifecycle, L) is MET or MET_WITH_NOTE.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DIR = Path(__file__).resolve().parents[1] / "docs/capstone/p10/p10c_f2a"
AUTHORISED_FILES = {"soc_structure_2018.xlsx", "soc_2018_definitions.xlsx", "oesm25nat.zip", "occupation_definitions_m2025.xlsx"}
OK = {"MET", "MET_WITH_NOTE"}


def evaluate(directory: Path | None = None) -> tuple[list[str], bool, list[str]]:
    """Validate one package directory (default: the P10C-F2A US package). A manifest may declare ``authorised_files`` (else the F2A set), ``official_url_prefixes`` and a
    ``package_authorization`` block; a package whose authorization is not APPROVED may not contain any acquired file."""
    base = Path(directory) if directory else DIR
    errs: list[str] = []
    m = json.loads((base / "acquisition_manifest.json").read_text())
    v = json.loads((base / "source_verification.json").read_text())
    authorised = set(m.get("authorised_files", AUTHORISED_FILES))
    prefixes = tuple(m.get("official_url_prefixes", ["https://www.bls.gov/"]))
    auth = m.get("package_authorization", {"status": "APPROVED"})
    names = {f["original_filename"] for f in m["files"]}
    if names != authorised:
        errs.append(f"manifest files differ from the declared set: {sorted(names ^ authorised)}")
    if auth.get("status") != "APPROVED" and any(f["state"] != "NOT_ACQUIRED" for f in m["files"]):
        errs.append("a file is marked acquired although the package authorization is not APPROVED")
    for f in m["files"]:
        if not f["official_url"].startswith(prefixes):
            errs.append(f"{f['file_id']}: not an official publisher URL for this package")
        if f["state"] == "NOT_ACQUIRED":
            if f["sha256"] or f["acquired_at"] or f["storage_location"] or f["size_bytes"]:
                errs.append(f"{f['file_id']}: acquisition metadata present on a NOT_ACQUIRED file")
        elif f["state"] == "ACQUIRED":
            if not (f["sha256"] and re.fullmatch(r"[0-9a-f]{64}", f["sha256"]) and f["acquired_at"] and f["size_bytes"] and f.get("http_status") == 200):
                errs.append(f"{f['file_id']}: ACQUIRED without a valid SHA-256, timestamp, size and HTTP 200")
            loc = Path(f["storage_location"] or "")
            if REPO in loc.parents or not loc.is_absolute():
                errs.append(f"{f['file_id']}: raw file must be stored outside the repository")
            if f.get("ingestion_state") not in ("NOT_INGESTED", "INGESTED_ISOLATED_NON_PRODUCTION") or f.get("runtime_approval") != "NOT_APPROVED" or f["qualification_status"] != "NOT_QUALIFIED":
                errs.append(f"{f['file_id']}: only isolated non-production ingestion is recorded; qualification and runtime approval must stay open")
            if f.get("ingestion_state") == "INGESTED_ISOLATED_NON_PRODUCTION" and not (f.get("import_batch_id") and f.get("transformation_version")):
                errs.append(f"{f['file_id']}: ingested without an import batch and transformation version")
        else:
            errs.append(f"{f['file_id']}: unknown state")
        if f["qualification_status"] != "NOT_QUALIFIED" and f["state"] != "ACQUIRED":
            errs.append(f"{f['file_id']}: qualified without acquisition")
    pre = {p["id"]: p for p in v["preconditions"]}
    if sorted(pre) != list("ABCDEFGHIJKLMNOP"):
        errs.append("preconditions A-P incomplete")
    blockers = [f"{k}: {p['requirement']} ({p['status']})" for k, p in sorted(pre.items()) if p["status"] not in OK]
    return errs, not blockers, blockers


def verify_hashes(directory: Path | None = None) -> list[str]:
    import hashlib

    errs = []
    for f in json.loads(((Path(directory) if directory else DIR) / "acquisition_manifest.json").read_text())["files"]:
        if f["state"] != "ACQUIRED":
            continue
        p = Path(f["storage_location"] or "")
        if not p.exists():
            errs.append(f"{f['file_id']}: staged file not found")
        elif hashlib.sha256(p.read_bytes()).hexdigest() != f["sha256"] or p.stat().st_size != f["size_bytes"]:
            errs.append(f"{f['file_id']}: hash or size mismatch")
    return errs


def main() -> int:
    directory = Path(sys.argv[sys.argv.index("--dir") + 1]) if "--dir" in sys.argv else None
    errs, allowed, blockers = evaluate(directory)
    wave = json.loads(((directory or DIR) / "acquisition_manifest.json").read_text()).get("wave", "P10C-F2A")
    if "--verify-hashes" in sys.argv:
        errs += verify_hashes(directory)
    print(f"{wave} GATE RECORDS:", "OK" if not errs else "FAIL")
    for e in errs:
        print(" -", e)
    print("preconditions_all_met (ingestion gate):", allowed)
    for b in blockers:
        print(" blocker -", b)
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())
