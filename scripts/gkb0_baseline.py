#!/usr/bin/env python
"""GKB-0 baseline characterization (P10C-A). READ-ONLY: opens the local knowledge stores immutably, writes nothing to them. Prints the baseline JSON, or writes it to ``--out``.
The output destination is validated BEFORE any local data is read: it may never resolve inside ``data/`` or ``evaluations/`` (exit 2). Missing local data is a controlled error (exit 3);
nothing is fabricated and no partial baseline is written."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
PROTECTED = ("data", "evaluations")


def output_is_protected(out: str | Path, root: Path) -> bool:
    """True when ``out`` resolves (symlinks, ``..`` and relative paths followed; the file need not exist) inside a protected directory of ``root``."""
    base = Path(root).resolve()
    target = Path(out)
    resolved = (target if target.is_absolute() else Path.cwd() / target).resolve()
    rel = (base / target).resolve() if not target.is_absolute() else resolved          # a relative path is also judged against the repository root
    return any(candidate == (base / d).resolve() or (base / d).resolve() in candidate.parents for candidate in (resolved, rel) for d in PROTECTED)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", help="write the JSON here (never inside data/ or evaluations/)")
    ap.add_argument("--root", default=str(ROOT), help="repository root to characterise (default: this repository)")
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()
    if args.out and output_is_protected(args.out, root):                                 # validated before ANY data access
        print("refusing to write inside data/ or evaluations/", file=sys.stderr)
        return 2
    from src.knowledge_foundation.baseline import build_baseline

    try:
        text = json.dumps(build_baseline(root), indent=1, sort_keys=True, ensure_ascii=False) + "\n"
    except FileNotFoundError as exc:
        print(f"baseline unavailable: required local knowledge data is missing ({Path(exc.filename).name if exc.filename else 'unknown file'}); nothing was written", file=sys.stderr)
        return 3
    if args.out:
        out = Path(args.out).resolve()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
