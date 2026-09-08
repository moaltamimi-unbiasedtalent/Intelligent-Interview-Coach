#!/usr/bin/env python
"""Operator cleanup for durable runtime data (Sprint 4 Phase 11).

Removes only stale durable runtime interview-session rows — those whose
``last_accessed_at`` is older than the retention window (the ``interview_sessions``
table holds only resumable runtime state). It NEVER deletes completed interview history
(user-owned durable data), agent checkpoints, or approved preparation memory — those
have their own lifecycles (see docs/sprint4_security_privacy.md).

Dry-run by default (reports COUNTS only, never interview contents):

    python scripts/cleanup_runtime_data.py --dry-run          # default
    python scripts/cleanup_runtime_data.py --apply            # actually delete
    python scripts/cleanup_runtime_data.py --retention-days 30 --apply

Exit code 0 on success.
"""

from __future__ import annotations

import argparse
import sys
from datetime import timedelta

from src import constants
from src.config import load_config
from src.interview.session_repository import DurableInterviewSessionStore
from src.persistence import make_engine, make_session_factory, utcnow


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Clean up stale in-progress interview sessions.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="report counts only (default)")
    mode.add_argument("--apply", action="store_true", help="actually delete stale sessions")
    parser.add_argument("--retention-days", type=int,
                        default=constants.INTERVIEW_SESSION_RETENTION_DAYS,
                        help="delete in-progress sessions untouched for more than this many days")
    args = parser.parse_args(argv)
    apply = args.apply  # dry-run is the default whenever --apply is absent

    cutoff = utcnow() - timedelta(days=args.retention_days)
    engine = make_engine(load_config().database_url)
    store = DurableInterviewSessionStore(make_session_factory(engine))

    if apply:
        removed = store.cleanup_stale_sessions(before=cutoff)
        print(f"[apply] deleted {removed} in-progress interview session(s) "
              f"untouched since {cutoff.isoformat()} (retention_days={args.retention_days}).")
    else:
        stale = store.count_stale_sessions(before=cutoff)
        print(f"[dry-run] {stale} in-progress interview session(s) are stale as of "
              f"{cutoff.isoformat()} (retention_days={args.retention_days}). "
              f"Re-run with --apply to delete. Completed history is never affected.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
