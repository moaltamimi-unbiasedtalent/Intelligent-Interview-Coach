#!/usr/bin/env python
"""Build the isolated SYNTHETIC Pilot knowledge fixture into an explicit throwaway directory (P2-02).

Usage:
    python scripts/pilot/build_isolated_knowledge.py --output-dir /tmp/ask4mo-pilot2-kb [--validate] [--reset]

Fails closed (non-zero exit) for any output directory inside the repository, over the developer Chroma location, or otherwise unsafe.
Starts nothing, calls no provider and makes no network request. See docs/capstone/p10/pilot2/P2_02_ISOLATED_KNOWLEDGE_FIXTURE.md.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import isolated_knowledge as ik  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the isolated synthetic Pilot knowledge fixture.")
    parser.add_argument("--output-dir", required=True, help="Explicit throwaway directory (outside the repository).")
    parser.add_argument("--validate", action="store_true", help="Also validate through the production retrieval boundary.")
    parser.add_argument("--reset", action="store_true", help="Rebuild the collection inside an existing fixture directory only.")
    args = parser.parse_args(argv)
    try:
        report = ik.build(args.output_dir, reset=args.reset)
    except ik.UnsafeOutputError as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2
    print("SYNTHETIC PILOT TEST DATA: not an official, statistical, framework or industry source.")
    print("\n".join(report.lines()))
    print(f"\nBackend environment (set BEFORE the backend starts):\n  COPILOT_CHROMA_DIR={report.chroma_dir}\n  COPILOT_EMBEDDING_PROVIDER=local")
    if args.validate:
        result = ik.validate(args.output_dir)
        for name, ok in result.checks.items():
            print(f"  {'PASS' if ok else 'FAIL'}  {name}")
        print(f"validation: {'PASS' if result.ok else 'FAIL'}")
        return 0 if result.ok else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
