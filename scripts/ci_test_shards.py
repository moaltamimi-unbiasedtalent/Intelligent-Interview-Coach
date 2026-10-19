"""Deterministic backend-test sharding and inventory integrity for CI (W12.4F CI hotfix).

Standard library only. The partition is by test FILE so each pytest invocation keeps module-level isolation. It never filters, deselects or skips a test:

* ``list``      prints the test files of one shard (weights from ``scripts/ci/test_shard_weights.json``; files without a weight get the median weight).
* ``verify``    fails unless every discovered test file is in exactly one of the N shards and the plan is deterministic.
* ``summarize`` reads a JUnit file and writes a small JSON (shard, tests, failures, errors, skipped) used by ``reconcile``.
* ``reconcile`` fails unless the number of shard summaries equals the expected shard count, no shard reports a failure or error, and the sum of tests executed equals the
  number of tests collected from the whole suite (``--expected``). A missing shard, a shard-generation error or an uncollected test therefore fails CI.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEIGHTS = ROOT / "scripts" / "ci" / "test_shard_weights.json"
DEFAULT_WEIGHT = 5.0


def discover() -> list[str]:
    """Every file pytest would collect under ``tests/`` (default patterns ``test_*.py`` and ``*_test.py``)."""
    files = {p for pat in ("test_*.py", "*_test.py") for p in (ROOT / "tests").rglob(pat) if "__pycache__" not in p.parts}
    return sorted(p.relative_to(ROOT).as_posix() for p in files)


def load_weights() -> dict[str, float]:
    try:
        return {k: float(v) for k, v in json.loads(WEIGHTS.read_text(encoding="utf-8")).items()}
    except FileNotFoundError:
        return {}


def plan(shards: int) -> list[list[str]]:
    """Longest-processing-time-first assignment: deterministic for a given file set and weights file."""
    if shards < 1:
        raise ValueError("shards must be >= 1")
    files, weights = discover(), load_weights()
    known = [weights[f] for f in files if f in weights]
    fallback = statistics.median(known) if known else DEFAULT_WEIGHT
    order = sorted(files, key=lambda f: (-weights.get(f, fallback), f))
    buckets: list[list[str]] = [[] for _ in range(shards)]
    loads = [0.0] * shards
    for f in order:
        i = min(range(shards), key=lambda k: (loads[k], k))
        buckets[i].append(f)
        loads[i] += weights.get(f, fallback)
    return [sorted(b) for b in buckets]


def verify(shards: int) -> list[str]:
    errors: list[str] = []
    files = discover()
    if not files:
        errors.append("no test files discovered")
    parts = plan(shards)
    flat = [f for p in parts for f in p]
    missing = sorted(set(files) - set(flat))
    dupes = sorted({f for f in flat if flat.count(f) > 1})
    extra = sorted(set(flat) - set(files))
    if missing:
        errors.append(f"files missing from every shard: {missing[:5]}")
    if dupes:
        errors.append(f"files in more than one shard: {dupes[:5]}")
    if extra:
        errors.append(f"unknown files in a shard: {extra[:5]}")
    if any(not p for p in parts):
        errors.append("an empty shard was generated")
    if plan(shards) != parts:
        errors.append("the plan is not deterministic")
    return errors


def summarize(junit: Path, shard: str) -> dict:
    root = ET.parse(junit).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.iter("testsuite"))
    total = {"tests": 0, "failures": 0, "errors": 0, "skipped": 0}
    for s in suites:
        for k in total:
            total[k] += int(s.get(k, 0))
    return {"shard": shard, **total}


def reconcile(summaries: list[dict], shards: int, expected: int) -> list[str]:
    errors: list[str] = []
    ids = sorted(s["shard"] for s in summaries)
    if ids != sorted(str(i) for i in range(1, shards + 1)):
        errors.append(f"expected summaries for shards 1..{shards}, found {ids}")
    for s in summaries:
        if s["failures"] or s["errors"]:
            errors.append(f"shard {s['shard']} reports {s['failures']} failures and {s['errors']} errors")
    executed = sum(s["tests"] for s in summaries)
    if executed != expected:
        errors.append(f"tests executed across shards ({executed}) != tests collected from the whole suite ({expected})")
    return errors


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("list"); p.add_argument("--shards", type=int, required=True); p.add_argument("--index", type=int, required=True, help="1-based")
    p = sub.add_parser("verify"); p.add_argument("--shards", type=int, required=True)
    p = sub.add_parser("summarize"); p.add_argument("--junit", type=Path, required=True); p.add_argument("--shard", required=True); p.add_argument("--out", type=Path, required=True)
    p = sub.add_parser("reconcile"); p.add_argument("--shards", type=int, required=True); p.add_argument("--expected", type=int, required=True); p.add_argument("--dir", type=Path, required=True)
    a = ap.parse_args(argv)
    if a.cmd == "list":
        if not 1 <= a.index <= a.shards:
            print("index out of range", file=sys.stderr)
            return 2
        print("\n".join(plan(a.shards)[a.index - 1]))
        return 0
    if a.cmd == "verify":
        errs = verify(a.shards)
        print("\n".join(errs) if errs else f"OK: {len(discover())} test files, each in exactly one of {a.shards} shards")
        return 1 if errs else 0
    if a.cmd == "summarize":
        a.out.write_text(json.dumps(summarize(a.junit, a.shard)), encoding="utf-8")
        return 0
    summaries = [json.loads(f.read_text(encoding="utf-8")) for f in sorted(a.dir.rglob("shard-*.json"))]
    errs = reconcile(summaries, a.shards, a.expected)
    print("\n".join(errs) if errs else f"OK: {sum(s['tests'] for s in summaries)} tests executed across {len(summaries)} shards == {a.expected} collected")
    return 1 if errs else 0


if __name__ == "__main__":
    raise SystemExit(main())
PROBE = "sk-or-ABCDEFGH1234XYZ"
