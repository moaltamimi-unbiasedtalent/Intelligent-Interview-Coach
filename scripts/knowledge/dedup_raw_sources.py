#!/usr/bin/env python
"""Deduplicate the raw knowledge tree safely (Phase 7A.1).

Phase 7A found ~300 MB of duplicated raw files (O*NET, ESCO, BLS OEWS copied across
several folders). This tool finds EXACT byte-duplicate groups by SHA-256 and removes the
redundant copies, keeping one canonical copy per group.

Canonical selection is **reader-safe**: the copy a `src/copilot/knowledge/local_readers.py`
reader already points at is always kept (deleting it would break Phase 7B ingestion). When
no copy is reader-anchored, the most organized/versioned path wins. Because every deletion
is a byte-identical duplicate, a canonical copy always survives — the file's content is
never lost. Uncertain / non-identical files are NEVER deleted here.

Writes ``data/raw_deduplication_report.json`` (repo-relative paths only). Dry-run by
default; pass ``--apply`` to actually delete. Re-verifies the canonical copy's SHA-256
before removing any redundant copy.

Usage:
    python scripts/knowledge/dedup_raw_sources.py            # dry-run + report
    python scripts/knowledge/dedup_raw_sources.py --apply    # delete redundant copies
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

RAW_ROOT = "data/raw"
ARCHIVE_ROOT = "data/_archive/duplicates_review"
REPORT_PATH = "data/raw_deduplication_report.json"

# Paths that `local_readers.py` reads from — always kept as canonical (dir prefixes and
# exact files). Kept in sync with the reader defaults.
_READER_DIRS = (
    "data/raw/db_31_0_excel/",
    "data/raw/ESCO dataset - v1.2.1 - classification - en - csv/",
    "data/raw/oesm25nat/",
    "data/raw/ashetable142025provisional/",
)
_READER_FILES = (
    "data/raw/ISCO-08 EN Structure and definitions.xlsx",
    "data/raw/Systematisches-Verzeichnis-KldB-2020.xlsx",
    "data/raw/OOH xml-compilation.xml",
    "data/raw/occupation.xlsx",
    "data/raw/NICE Framework Components v2.2.0.xlsx",
    "data/raw/2026_cedefop_labour_skills_shortage_index_clssi_dataset.xlsx",
    "data/raw/jvs_a_isco3_r1$defaultview_spreadsheet.xlsx",
    "data/raw/DigComp 2.2 ESCO Skills Mapping.xlsx",
)
# Organized/versioned prefixes preferred when no reader anchor is in a group.
_ORGANIZED = (
    "data/raw/onet/", "data/raw/esco/", "data/raw/bls/", "data/raw/cedefop/",
    "data/raw/isco/", "data/raw/kldb/", "data/raw/ons/", "data/raw/eurostat/",
    "data/raw/nice/", "data/raw/digcomp/", "data/raw/eqf/", "data/raw/destatis/",
)


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _reader_anchored(rel: str) -> bool:
    return rel in _READER_FILES or any(rel.startswith(d) for d in _READER_DIRS)


def _score(rel: str) -> tuple:
    """Higher is more canonical: reader-anchored > organized > loose; shorter path wins."""
    return (
        1 if _reader_anchored(rel) else 0,
        1 if rel.startswith(_ORGANIZED) else 0,
        -len(rel),
    )


def _scan() -> tuple[dict[str, list[tuple[str, int]]], int, int]:
    by_hash: dict[str, list[tuple[str, int]]] = defaultdict(list)
    n = 0
    total = 0
    for dp, _dirs, fns in os.walk(RAW_ROOT):
        if os.sep + "_archive" in dp:
            continue
        for fn in fns:
            if fn == ".DS_Store":
                continue
            p = os.path.join(dp, fn)
            if not os.path.isfile(p):
                continue
            rel = os.path.relpath(p, ".")
            try:
                sz = os.path.getsize(p)
            except OSError:
                continue
            n += 1
            total += sz
            by_hash[_sha256(p)].append((rel, sz))
    return by_hash, n, total


def build_report(apply: bool) -> dict:
    by_hash, n_before, bytes_before = _scan()
    groups = {h: fs for h, fs in by_hash.items() if len(fs) > 1}

    entries = []
    removed = 0
    removed_bytes = 0
    for h, fs in groups.items():
        ranked = sorted(fs, key=lambda t: _score(t[0]), reverse=True)
        canonical_path, _ = ranked[0]
        for rel, sz in ranked[1:]:
            action = "kept"
            reason = "exact_duplicate_of_canonical"
            if apply:
                # Re-verify the canonical copy is present and identical before deleting.
                if os.path.isfile(canonical_path) and _sha256(canonical_path) == h and os.path.isfile(rel):
                    try:
                        os.remove(rel)
                        action = "deleted_exact_duplicate"
                        removed += 1
                        removed_bytes += sz
                    except OSError as exc:
                        # e.g. a sandbox/permission denial — never crash the run; flag it.
                        action = "requires_review"
                        reason = f"could_not_delete:{type(exc).__name__}"
                elif not os.path.isfile(rel):
                    action = "already_absent"
                    reason = "redundant_copy_not_present"
                else:
                    action = "requires_review"
                    reason = "canonical_copy_missing_or_mismatch"
            else:
                action = "would_delete_exact_duplicate"
                removed += 1
                removed_bytes += sz
            entries.append({
                "original_path": rel, "canonical_path": canonical_path,
                "classification": "EXACT_DUPLICATE", "sha256": h, "size_bytes": sz,
                "action": action, "reason": reason,
            })
        entries.append({
            "original_path": canonical_path, "canonical_path": canonical_path,
            "classification": "EXACT_DUPLICATE", "sha256": h,
            "size_bytes": ranked[0][1], "action": "kept", "reason": "canonical",
        })

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "applied": apply,
        "raw_root": RAW_ROOT,
        "files_before": n_before,
        "files_after": n_before - (removed if apply else 0),
        "bytes_before": bytes_before,
        "bytes_after": bytes_before - (removed_bytes if apply else 0),
        "exact_duplicate_groups": len(groups),
        "redundant_copies": sum(len(fs) - 1 for fs in groups.values()),
        "redundant_bytes": sum(fs[0][1] * (len(fs) - 1) for fs in groups.values()),
        "removed": removed if apply else 0,
        "removed_bytes": removed_bytes if apply else 0,
        "logical_duplicates_archived": 0,
        "uncertain": 0,
        "entries": sorted(entries, key=lambda e: (-e["size_bytes"], e["original_path"])),
    }
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Deduplicate the raw knowledge tree.")
    ap.add_argument("--apply", action="store_true", help="Delete redundant exact copies.")
    args = ap.parse_args(argv)

    report = build_report(args.apply)
    Path(REPORT_PATH).write_text(json.dumps(report, indent=2), encoding="utf-8")

    verb = "DELETED" if args.apply else "would delete (dry-run)"
    print("ASK4MO RAW DEDUPLICATION\n")
    print(f"files before: {report['files_before']}")
    print(f"exact-duplicate groups: {report['exact_duplicate_groups']}")
    print(f"redundant copies: {report['redundant_copies']} "
          f"({report['redundant_bytes'] / 1048576:.1f} MB)")
    print(f"{verb}: {report['removed'] or report['redundant_copies']} copies "
          f"(~{(report['removed_bytes'] or report['redundant_bytes']) / 1048576:.1f} MB)")
    print(f"files after: {report['files_after']}")
    print(f"report: {REPORT_PATH}")
    if not args.apply:
        print("\n(dry-run — re-run with --apply to delete)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
