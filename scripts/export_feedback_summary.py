#!/usr/bin/env python
"""Export aggregate candidate-feedback metrics for HUMAN review (post-Sprint 4 P5).

The feedback learning loop is a controlled engineering process, not autonomous
self-modification: this script surfaces recurring patterns for a human to turn into new
evaluation cases and (human-reviewed, regression-tested) prompt/policy changes.

Default output is AGGREGATE ONLY (counts + helpful rate, by surface). Comments are
included only with an explicit ``--include-comments`` flag, and even then the export
carries NO email, user name, JD, answer, evaluation or report content — feedback stores
only references, a rating and a bounded comment.

    python scripts/export_feedback_summary.py                 # aggregate only
    python scripts/export_feedback_summary.py --days 7        # last 7 days
    python scripts/export_feedback_summary.py --include-comments   # explicit opt-in

Exit code 0 on success.
"""

from __future__ import annotations

import argparse
import json
import sys

from src.config import load_config
from src.persistence import make_engine, make_session_factory
from src.repository import FeedbackRepository


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export aggregate feedback metrics for human review.")
    parser.add_argument("--days", type=int, default=None,
                        help="only include feedback from the last N days")
    parser.add_argument("--include-comments", action="store_true",
                        help="EXPLICITLY include bounded comment text (still no identities/content joins)")
    args = parser.parse_args(argv)

    engine = make_engine(load_config().database_url)
    repo = FeedbackRepository(make_session_factory(engine))

    since = None
    if args.days:
        from datetime import timedelta

        from src.persistence import utcnow
        since = utcnow() - timedelta(days=args.days)

    report: dict = {"metrics": repo.metrics(since=since)}

    if args.include_comments:
        # Bounded comment text ONLY, tagged by surface + safe target reference. No user
        # id/name/email, no JD/answer/report/memory joins.
        report["comments"] = [
            {"surface": item.surface, "target_id": item.target_id,
             "rating": item.rating, "comment": item.comment}
            for item in repo.list_all()
            if item.comment
        ]

    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
