#!/usr/bin/env python3
"""Restore drill (package 05B): back up a source, restore it into a SEPARATE environment, verify it and write a drill record (JSON and markdown).

    python scripts/restore_drill.py --synthetic --record-dir docs/production/execution/evidence/drills --label offline --commit-sha <sha>
    python scripts/restore_drill.py --from-environment --work-dir NEW --record-dir DIR --label staging [--encrypt]      # operator drill against YOUR configured source

``--synthetic`` builds a throwaway synthetic environment in a temporary directory (no real data, no development store) and drills it: it proves the tool and the procedure
and is recorded as ``offline_synthetic`` with ``hosted_verification: NOT RUN (OD-HOSTED)``. ``--from-environment`` reads the source exactly like the API and worker
(DATABASE_URL, DOCUMENT_STORAGE_DIR, COPILOT_DATA_DIR) and restores into ``--work-dir`` (a NEW directory); the record says ``operator_supplied``. The source is only read.
Keys come only from the environment (BACKUP_ENCRYPTION_KEY, BACKUP_SIGNING_KEY); a record never holds a path, key, URL or candidate data. Exit: 0 PASS, 1 FAIL or PARTIAL-with-failure,
3 PARTIAL (a check was NOT RUN, none failed), 2 usage.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--synthetic", action="store_true")
    g.add_argument("--from-environment", action="store_true")
    p.add_argument("--record-dir", required=True)
    p.add_argument("--label", default="drill")
    p.add_argument("--work-dir", help="a NEW directory (default for --synthetic: a temporary directory removed afterwards)")
    p.add_argument("--commit-sha")
    p.add_argument("--encrypt", action="store_true", help="seal the drill's set with BACKUP_ENCRYPTION_KEY")
    p.add_argument("--target-database-url", help="PostgreSQL source only: an EMPTY disposable database named *restore*, *staging* or *drill*")
    a = p.parse_args(argv)
    from src.backup_set import crypto
    from src.backup_set.drill import run_drill

    enc = crypto.key_from_env(crypto.ENCRYPTION_KEY_ENV) if a.encrypt else None
    sig = crypto.key_from_env(crypto.SIGNING_KEY_ENV) if os.environ.get(crypto.SIGNING_KEY_ENV) else None
    try:
        if a.synthetic:
            from src.backup_set.fixture import build_synthetic_environment

            with tempfile.TemporaryDirectory(prefix="a4md-") as t:
                src = build_synthetic_environment(Path(t) / "source", use_alembic=True)
                res = run_drill(src, work_dir=Path(a.work_dir) if a.work_dir else Path(t) / "work", record_dir=a.record_dir, label=a.label, kind="offline_synthetic",
                                encryption_key=enc, signing_key=sig, commit_sha=a.commit_sha, api_env="test")
        else:
            from src.backup_set.runtime import source_from_environment

            if not a.work_dir:
                raise SystemExit("--work-dir is required with --from-environment")
            res = run_drill(source_from_environment(), work_dir=Path(a.work_dir), record_dir=a.record_dir, label=a.label, kind="operator_supplied", encryption_key=enc,
                            signing_key=sig, commit_sha=a.commit_sha, api_env=os.environ.get("API_ENV"), target_database_url=a.target_database_url)
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001 - fixed code only
        print(json.dumps({"ok": False, "codes": [str(getattr(exc, "code", None) or type(exc).__name__)]}))
        return 1
    print(json.dumps({"drill_id": res.record["drill_id"], "overall": res.overall, "record_json": res.json_name, "record_md": res.md_name,
                      "checks": {c["id"]: c["result"] for c in res.record["checks"]}}, indent=1))
    failed = any(c["result"] == "FAIL" for c in res.record["checks"])
    return 1 if failed else (3 if res.overall == "PARTIAL" else 0)


if __name__ == "__main__":
    raise SystemExit(main())
