#!/usr/bin/env python
"""Record a human review decision on a Feedback Intelligence recommendation (Phase 7G, §72).

APPROVE / REJECT / DEFER are appended to an immutable log in the run directory. NOTHING is
executed: approval does not modify code, prompts, config, the KB, or Git — it only records that an
engineer may consider the recommendation (§36).

Usage:
    python scripts/review_feedback_recommendation.py --run <run-dir> \
        --recommendation R001 --decision approve --reason "worth investigating"
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.copilot.feedback_intelligence.review import record_decision  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Record a Feedback Intelligence review decision.")
    ap.add_argument("--run", required=True, help="run directory under the analysis-output root")
    ap.add_argument("--recommendation", required=True, help="recommendation/experiment id")
    ap.add_argument("--decision", required=True, choices=["approve", "reject", "defer"])
    ap.add_argument("--reviewer", default=None, help="safe admin identifier (never a candidate)")
    ap.add_argument("--reason", default=None)
    args = ap.parse_args(argv)

    try:
        rec = record_decision(args.run, args.recommendation, args.decision,
                              reviewer_id=args.reviewer, reason=args.reason)
    except Exception as exc:  # noqa: BLE001
        print(f"Could not record decision: {type(exc).__name__}: {exc}")
        return 1
    print(f"Recorded: {rec.proposal_id} → {rec.decision.value} (executed={rec.executed}).")
    print("No production change was made. An engineer implements approved items separately.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
