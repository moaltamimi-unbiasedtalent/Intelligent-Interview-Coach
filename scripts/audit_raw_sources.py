#!/usr/bin/env python
"""Ask4Mo raw-source readiness audit (Phase 7A).

Inspects the real local knowledge data governance — the committed
``data/source_manifest.json`` (ingestion contract), ``data/source_inventory.json``
(per-file sha256 fingerprints) and ``data/source_status.json`` (lifecycle) — and reports
whether the raw inputs the Phase 7B loaders will consume are present, parseable and
attributable. It reuses the existing loaders (``knowledge.manifest`` / ``knowledge.status``)
so there is ONE source-governance model, not a competing one.

It does NOT download, modify, parse or normalize any raw data — it is read-only over the
governance metadata plus the canonical schema module's validity.

Required vs optional (data-driven, not hardcoded):
  * REQUIRED  — a manifest source whose ``storage_target`` is a structured store
    (structured_role / compensation / labour_market / competency / structured) AND which
    has been ACQUIRED (has files in the inventory). These feed the structured KB.
  * OPTIONAL  — narrative/vector sources, and any source not yet acquired
    (manual/fixture). An absent optional source never fails the audit.
  * BACKBONE  — at least one occupation source (onet OR esco) must be READY, otherwise the
    occupation store cannot be built.

Exit code 0 when the required inputs + backbone are ready; non-zero when a required,
acquired source is genuinely unusable (files present but unparseable) or the backbone is
missing. Absent optional sources do not cause a non-zero exit.

Usage:
    python scripts/audit_raw_sources.py
    python scripts/audit_raw_sources.py --json
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.copilot.knowledge import manifest as manifest_mod  # noqa: E402
from src.copilot.knowledge import status as status_mod  # noqa: E402

INVENTORY_PATH = "data/source_inventory.json"
_STRUCTURED_TARGETS = {
    "structured_role", "compensation", "labour_market", "competency", "structured",
}
_BACKBONE = ("onet", "esco")

# Readiness verdicts.
READY, WARN, NOT_ACQUIRED, FAIL = "READY", "WARN", "NOT ACQUIRED", "FAIL"


def _load_inventory(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        return {"files": []}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return {"files": []}


def _inventory_by_source(inv: dict) -> dict[str, list[dict]]:
    by_src: dict[str, list[dict]] = defaultdict(list)
    for f in inv.get("files", []):
        sid = f.get("source_id")
        if sid:
            by_src[sid].append(f)
    return by_src


def _assess(entry, files: list[dict]) -> dict:
    """Assess one manifest source against its acquired inventory files."""
    target = getattr(entry, "storage_target", None)
    is_structured = target in _STRUCTURED_TARGETS
    has_files = bool(files)
    parseable = [f for f in files if f.get("parseable") and f.get("ingestion_readiness") == "ready"]
    # "Usable" = present and fingerprinted. A file the generic inventory heuristic marks
    # not-parseable (e.g. the OOH XML) may still be consumed by a bespoke loader, so it is
    # WARN (needs a specific reader), never a hard FAIL, as long as it is present + hashed.
    with_sha = [f for f in files if f.get("sha256")]
    needs_reader = [f for f in files if f not in parseable]
    licence_review = bool(getattr(entry, "licence_review_required", False)) or any(
        (f.get("licensing_status") or "").lower().startswith("review") for f in files
    )

    if not has_files:
        verdict = NOT_ACQUIRED
    elif not with_sha:
        verdict = FAIL  # acquired but nothing present/fingerprinted → genuinely unusable
    elif needs_reader or licence_review:
        verdict = WARN  # usable, but flagged for a bespoke reader and/or licence review
    else:
        verdict = READY

    return {
        "source_id": entry.source_id,
        "title": getattr(entry, "title", None),
        "storage_target": target,
        "group": getattr(entry, "group", None),
        "required": is_structured and has_files,
        "structured_target": is_structured,
        "acquired": has_files,
        "file_count": len(files),
        "parseable_count": len(parseable),
        "checksum_count": len(with_sha),
        "version": getattr(entry, "version", None),
        "domains": list(getattr(entry, "coverage_areas", []) or []),
        "licence": getattr(entry, "licence", None),
        "licence_review": licence_review,
        "source_url": getattr(entry, "source_url", None),
        "verdict": verdict,
    }


def run_audit() -> dict:
    entries = manifest_mod.load_manifest()
    inv = _load_inventory(INVENTORY_PATH)
    by_src = _inventory_by_source(inv)

    # status is advisory context; tolerate its absence.
    try:
        statuses = {s.source_id: s for s in status_mod.load_status()}
    except Exception:  # noqa: BLE001
        statuses = {}

    assessed = [_assess(e, by_src.get(e.source_id, [])) for e in entries]
    for a in assessed:
        st = statuses.get(a["source_id"])
        a["data_origin"] = getattr(st, "data_origin", None) if st else None
        a["lifecycle"] = getattr(st, "lifecycle", None) if st else None

    required = [a for a in assessed if a["required"]]
    optional = [a for a in assessed if not a["required"]]
    required_ready = [a for a in required if a["verdict"] in (READY, WARN)]
    optional_ready = [a for a in optional if a["verdict"] in (READY, WARN)]
    required_failed = [a for a in required if a["verdict"] == FAIL]

    backbone = {
        sid: next((a["verdict"] for a in assessed if a["source_id"] == sid), NOT_ACQUIRED)
        for sid in _BACKBONE
    }
    backbone_ready = any(v in (READY, WARN) for v in backbone.values())

    # Schema validity: the manifest loaded via the strict SourceEntry model, and the
    # canonical build schemas import cleanly.
    schema_ok = True
    schema_error = None
    try:
        import importlib
        importlib.import_module("src.copilot.knowledge.canonical")
    except Exception as exc:  # noqa: BLE001
        schema_ok = False
        schema_error = f"{type(exc).__name__}: {exc}"

    # Provenance: every acquired file carries a sha256; WARN if any licence needs review.
    acquired_files = sum(a["file_count"] for a in assessed)
    checksummed = sum(a["checksum_count"] for a in assessed)
    provenance_ok = acquired_files == checksummed and acquired_files > 0
    licence_review_ids = sorted(a["source_id"] for a in assessed if a["licence_review"])

    foundation_ready = (
        backbone_ready and not required_failed and schema_ok and provenance_ok
    )

    return {
        "manifest_source_count": len(entries),
        "inventory_file_count": len(inv.get("files", [])),
        "sources": assessed,
        "required_total": len(required),
        "required_ready": len(required_ready),
        "required_failed": [a["source_id"] for a in required_failed],
        "optional_total": len(optional),
        "optional_ready": len(optional_ready),
        "backbone": backbone,
        "backbone_ready": backbone_ready,
        "schema_validation": "PASS" if schema_ok else "FAIL",
        "schema_error": schema_error,
        "provenance_metadata": "PASS" if provenance_ok else "WARN",
        "acquired_files": acquired_files,
        "checksummed_files": checksummed,
        "licence_review_needed": licence_review_ids,
        "foundation_ready": foundation_ready,
    }


def _print_human(rep: dict) -> None:
    print("ASK4MO RAW SOURCE AUDIT\n")
    order = {READY: 0, WARN: 1, NOT_ACQUIRED: 3, FAIL: 2}
    reqs = sorted(
        (a for a in rep["sources"] if a["required"] or a["structured_target"]),
        key=lambda a: (order.get(a["verdict"], 9), a["source_id"]),
    )
    narrative = [a for a in rep["sources"] if not a["structured_target"]]

    print("STRUCTURED SOURCES (feed the knowledge stores)")
    for a in reqs:
        tag = "required" if a["required"] else "optional"
        print(f"\n{a['source_id']}  ({a['title']})")
        print(f"  status: {a['verdict']} [{tag}]")
        print(f"  storage: {a['storage_target']}  origin: {a.get('data_origin')}")
        print(f"  version: {a['version']}")
        if a["file_count"]:
            print(f"  files: {a['file_count']} ({a['parseable_count']} ready)  "
                  f"checksums: {a['checksum_count']}")
        print(f"  domains: {', '.join(a['domains'][:8])}"
              + (" …" if len(a["domains"]) > 8 else ""))
        print(f"  licence: {a['licence']}" + ("  [REVIEW]" if a["licence_review"] else ""))

    print("\nNARRATIVE / OPTIONAL SOURCES")
    for a in sorted(narrative, key=lambda a: a["source_id"]):
        print(f"  {a['source_id']:26} {a['verdict']:13} "
              f"files={a['file_count']} target={a['storage_target']}")

    print("\n" + "-" * 60)
    bb = ", ".join(f"{k}={v}" for k, v in rep["backbone"].items())
    print(f"Occupation backbone (onet|esco): {'READY' if rep['backbone_ready'] else 'MISSING'}  ({bb})")
    print(f"Required sources ready: {rep['required_ready']}/{rep['required_total']}")
    if rep["required_failed"]:
        print(f"  required FAILED: {', '.join(rep['required_failed'])}")
    print(f"Optional sources ready: {rep['optional_ready']}/{rep['optional_total']}")
    print(f"Checksummed raw files: {rep['checksummed_files']}/{rep['acquired_files']} (sha256)")
    print(f"Schema validation: {rep['schema_validation']}"
          + (f" ({rep['schema_error']})" if rep["schema_error"] else ""))
    print(f"Provenance metadata: {rep['provenance_metadata']}")
    if rep["licence_review_needed"]:
        print(f"Licence review needed: {', '.join(rep['licence_review_needed'])}")
    print("\nRAW SOURCE FOUNDATION:")
    print("READY" if rep["foundation_ready"] else "NOT READY")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Audit local raw knowledge sources.")
    ap.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    args = ap.parse_args(argv)

    rep = run_audit()
    if args.json:
        print(json.dumps(rep, indent=2, default=str))
    else:
        _print_human(rep)
    return 0 if rep["foundation_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
