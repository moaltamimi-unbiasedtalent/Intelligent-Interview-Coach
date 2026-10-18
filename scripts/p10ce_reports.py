#!/usr/bin/env python
"""P10C-E reports: the global coverage report and the source-approval register. Deterministic over COMMITTED artifacts; reads no local store and acquires nothing. ``--out-dir`` is validated
BEFORE any work (never inside data/ or evaluations/, exit 2)."""

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
    ap.add_argument("--out-dir")
    ap.add_argument("--root", default=str(ROOT))
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()
    if args.out_dir and output_is_protected(Path(args.out_dir) / "x.json", root):
        print("refusing to write inside data/ or evaluations/", file=sys.stderr)
        return 2
    from src.knowledge_foundation.global_reports import approval_register, coverage_report
    reports = {"GLOBAL_COVERAGE_REPORT.json": coverage_report(root), "SOURCE_APPROVAL_REGISTER.json": approval_register(root)}
    for name, rep in reports.items():
        text = json.dumps(rep, indent=1, sort_keys=True, ensure_ascii=False) + "\n"
        if args.out_dir:
            dest = Path(args.out_dir).resolve() / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(text, encoding="utf-8")
        else:
            sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
