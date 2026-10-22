#!/usr/bin/env python3
"""Migration rollback rehearsal (package 05B): upgrade, fail-closed downgrade, clean downgrade, re-upgrade and a pre-migration restore on an ISOLATED SQLite database in a
temporary directory, recorded as JSON and markdown.

    python scripts/rollback_rehearsal.py --record-dir docs/production/execution/evidence/drills --label offline --commit-sha <sha>

Never touches a development or hosted database. Exit: 0 PASS, 1 FAIL, 3 PARTIAL (a step was NOT RUN, none failed).
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--record-dir", required=True)
    p.add_argument("--label", default="rehearsal")
    p.add_argument("--commit-sha")
    a = p.parse_args(argv)
    from src.backup_set.rollback import run_rehearsal

    with tempfile.TemporaryDirectory(prefix="a4mr-rehearsal-") as t:
        res = run_rehearsal(work_dir=Path(t) / "work", record_dir=a.record_dir, label=a.label, commit_sha=a.commit_sha)
    print(json.dumps({"drill_id": res.record["drill_id"], "overall": res.overall, "record_json": res.json_name, "record_md": res.md_name,
                      "checks": {c["id"]: c["result"] for c in res.record["checks"]}}, indent=1))
    return 1 if res.overall == "FAIL" else (3 if res.overall == "PARTIAL" else 0)


if __name__ == "__main__":
    raise SystemExit(main())
