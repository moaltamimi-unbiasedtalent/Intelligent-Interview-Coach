#!/usr/bin/env python
"""Validate an isolated Pilot knowledge fixture through the PRODUCTION retrieval boundary (P2-02).

Usage:
    python scripts/pilot/validate_isolated_knowledge.py --knowledge-dir /tmp/ask4mo-pilot2-kb

Deterministic and offline: local hash embeddings, no provider key, no network, no synthesis model. Exits non-zero on any failed check.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import isolated_knowledge as ik  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate an isolated Pilot knowledge fixture.")
    parser.add_argument("--knowledge-dir", required=True)
    args = parser.parse_args(argv)
    try:
        result = ik.validate(args.knowledge_dir)
    except ik.UnsafeOutputError as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2
    for name, ok in result.checks.items():
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
    print("details:", {k: v for k, v in result.details.items()})
    print(f"validation: {'PASS' if result.ok else 'FAIL: ' + ', '.join(result.failed())}")
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
