#!/usr/bin/env python
"""P10C-D source-readiness report. Deterministic over COMMITTED artifacts; reads no local store and acquires nothing. ``--out`` is validated BEFORE any work (never inside data/ or
evaluations/, exit 2)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src.knowledge_foundation.pathsafe import output_is_protected  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out")
    ap.add_argument("--root", default=str(ROOT))
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()
    if args.out and output_is_protected(args.out, root):
        print("refusing to write inside data/ or evaluations/", file=sys.stderr)
        return 2
    from src.knowledge_foundation.readiness import assess
    text = json.dumps(assess(root), indent=1, sort_keys=True, ensure_ascii=False) + "\n"
    if args.out:
        dest = Path(args.out).resolve()
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
