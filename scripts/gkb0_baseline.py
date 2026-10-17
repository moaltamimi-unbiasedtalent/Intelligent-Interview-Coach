#!/usr/bin/env python
"""GKB-0 baseline characterization (P10C-A). READ-ONLY: opens the local knowledge stores immutably, writes nothing to them. Prints the baseline JSON, or writes it to ``--out``
(refuses a path inside ``data/`` or ``evaluations/``)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", help="write the JSON here (never inside data/ or evaluations/)")
    args = ap.parse_args()
    from src.knowledge_foundation.baseline import build_baseline

    text = json.dumps(build_baseline(ROOT), indent=1, sort_keys=True, ensure_ascii=False) + "\n"
    if args.out:
        out = Path(args.out).resolve()
        if any(part in (ROOT / "data", ROOT / "evaluations") or str(out).startswith(str(ROOT / d) + "/") for part in (out,) for d in ("data", "evaluations")):
            print("refusing to write inside data/ or evaluations/", file=sys.stderr)
            return 2
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
