#!/usr/bin/env python
"""Purge preparation-chat checkpoint data whose owner account no longer exists (package 05E, W9.8-D1a / W9.8-D10).

Why: account deletion removes the SQL rows in one transaction and purges the checkpoint threads afterwards (SQL and the checkpoint store cannot be atomic). If the
process stopped in between, or the checkpoint store was unavailable, the ownership-index rows (``preparation_runs``) of the deleted account remain and are the ONLY
handle on that data. This operator script finds them with one indexed JOIN (an index row whose owner no longer exists) and purges each thread through the saver's
official ``delete_thread``. It NEVER lists or scans the checkpoint store: a chat that was never indexed cannot be found and is a documented limit.

Safety: dry-run by default (counts only, no store is opened for writing); ``--execute`` is required to purge. Idempotent and resumable (an index row is removed only
after its purge succeeded; run it again after a failure). Prints counts only, never a run id, an owner id or content.

Usage:
    python scripts/privacy_sweep_orphan_runs.py                 # dry-run
    python scripts/privacy_sweep_orphan_runs.py --execute --limit 500
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Purge checkpoint data of preparation runs whose owner account was deleted.")
    parser.add_argument("--execute", action="store_true", help="Purge (otherwise dry-run: counts only).")
    parser.add_argument("--limit", type=int, default=500, help="Maximum runs per invocation (default 500, maximum 5000).")
    parser.add_argument("--database-url", default=None, help="Override DATABASE_URL.")
    args = parser.parse_args(argv)

    from src import constants
    from src.persistence import make_engine, make_session_factory
    from src.privacy.preparation import PreparationRunIndex, sweep_orphaned_runs

    db_url = args.database_url or os.environ.get("DATABASE_URL") or constants.DEFAULT_DATABASE_URL
    sf = make_session_factory(make_engine(db_url))
    index = PreparationRunIndex(sf)
    adapter = None
    if args.execute:
        from src.config import load_config
        from src.privacy.wiring import build_privacy_runtime

        adapter = build_privacy_runtime(sf, load_config()).adapter
        if adapter is None:
            print("The checkpoint store is not available: nothing was purged.")
            return 1
    out = sweep_orphaned_runs(index, adapter, limit=args.limit, execute=args.execute)
    print(f"orphaned runs found: {out['orphaned']}; purged: {out['purged']}; failed: {out['failed']}" + ("" if args.execute else " (dry-run; re-run with --execute to purge)"))
    return 1 if out["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
