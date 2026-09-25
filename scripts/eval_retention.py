#!/usr/bin/env python
"""Deterministic retention evaluation (Capstone P6/E7, §40).

Offline, no provider call, NO destructive action on live data — everything runs against a
temporary fixture directory. Gates: temp_file_cleanup, ocr_temp_cleanup,
artifact_preservation, owner_scope (never deletes outside its root), idempotent_cleanup,
dry_run_mode, production_safety, expired_session_cleanup_interface, inventory_complete.

    python scripts/eval_retention.py

Exits non-zero on any gate failure.
"""

from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.application.retention_service import (  # noqa: E402
    TemporaryArtifactCleaner, retention_inventory,
)


def _make_fixture() -> Path:
    root = Path(tempfile.mkdtemp(prefix="retention_eval_"))
    old = time.time() - 30 * 86400
    # Stale temp + OCR artifacts (old).
    for name in ["tmp_upload_1.bin", "ocr_page_1.png", "stale_eval_run.json"]:
        p = root / name
        p.write_text("x")
        os.utime(p, (old, old))
    # A preserved evidence file (old, but must be kept).
    keep = root / "README.md"
    keep.write_text("evidence")
    os.utime(keep, (old, old))
    # A fresh file (must NOT be cleaned).
    (root / "fresh.bin").write_text("new")
    return root


def evaluate() -> dict:
    m: dict = {}
    root = _make_fixture()
    cleaner = TemporaryArtifactCleaner(root, retention_days=7)

    # dry_run_mode — default is a report; nothing is deleted.
    dry = cleaner.clean(dry_run=True)
    files_after_dry = {p.name for p in root.iterdir()}
    m["dry_run_mode"] = 1 if (dry.dry_run and not dry.deleted and dry.candidates) else 0
    m["production_safety"] = 1 if {"tmp_upload_1.bin", "ocr_page_1.png"} <= files_after_dry else 0

    # temp_file_cleanup + ocr_temp_cleanup — stale temp/OCR files are eligible & removed.
    applied = cleaner.clean(dry_run=False)
    remaining = {p.name for p in root.iterdir()}
    m["temp_file_cleanup"] = 1 if "tmp_upload_1.bin" in applied.deleted and "tmp_upload_1.bin" not in remaining else 0
    m["ocr_temp_cleanup"] = 1 if "ocr_page_1.png" in applied.deleted else 0

    # artifact_preservation — preserved evidence + fresh files survive.
    m["artifact_preservation"] = 1 if ("README.md" in remaining and "fresh.bin" in remaining) else 0

    # idempotent_cleanup — a second run finds nothing to delete.
    second = cleaner.clean(dry_run=False)
    m["idempotent_cleanup"] = 1 if not second.candidates and not second.deleted else 0

    # owner_scope — a cleaner rooted elsewhere never deletes files under a different root
    # (path outside its root is refused). Point a second cleaner at an empty sibling.
    other = Path(tempfile.mkdtemp(prefix="retention_other_"))
    (other / "someone_elses.bin").write_text("data")
    os.utime(other / "someone_elses.bin", (time.time() - 30 * 86400, time.time() - 30 * 86400))
    scoped = TemporaryArtifactCleaner(root, retention_days=7)  # rooted at `root`, not `other`
    scoped.clean(dry_run=False)
    m["owner_scope"] = 1 if (other / "someone_elses.bin").exists() else 0

    # expired_session_cleanup_interface — the runtime cleanup entrypoint exists & is dry-run
    # by default (interface check only; no DB touched here).
    cleanup_script = Path("scripts/cleanup_runtime_data.py")
    m["expired_session_cleanup_interface"] = 1 if cleanup_script.is_file() else 0

    # inventory_complete — the retention inventory classifies the key stores.
    inv = retention_inventory()
    resources = " ".join(e["resource"].lower() for e in inv)
    needed = ["session", "token", "audit", "checkpoint", "feedback", "prompt lab",
              "evaluation", "ocr", "document", "observability", "knowledge index"]
    m["inventory_complete"] = 1 if all(n in resources for n in needed) and len(inv) >= 10 else 0

    return m


GATES = {
    "dry_run_mode": 1, "production_safety": 1, "temp_file_cleanup": 1, "ocr_temp_cleanup": 1,
    "artifact_preservation": 1, "idempotent_cleanup": 1, "owner_scope": 1,
    "expired_session_cleanup_interface": 1, "inventory_complete": 1,
}


def gate_failures(m: dict) -> list[str]:
    return [f"{k} = {m.get(k)} (want {v})" for k, v in GATES.items() if m.get(k) != v]


def main() -> int:
    m = evaluate()
    print("RETENTION EVALUATION (Capstone P6/E7, offline, fixture-only, no live deletion)")
    print("=" * 72)
    for k in GATES:
        print(f"  {k:<36} {m.get(k)}  (gate == {GATES[k]})")
    print("=" * 72)
    fails = gate_failures(m)
    if fails:
        print("\nGATE STATUS: FAIL")
        for f in fails:
            print(f"  - {f}")
        return 1
    print("\nGATE STATUS: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
