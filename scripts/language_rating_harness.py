#!/usr/bin/env python
"""Blinded native-reader rating harness (06C; LG-04 and LG-05 evidence package). Offline: no model call, no network, no credential.

Subcommands
  selftest   run the whole protocol end to end on FAKE outputs and FAKE raters in a temporary directory; exits non-zero on any protocol defect.
  sample     build the reviewer packet and the private key from an outputs JSONL file (one {"prompt_id", "language", "response"} per line, produced elsewhere by a governed live run).
             ``--fake`` uses fake outputs instead (self-test data, labelled; never send it to a reviewer).
  prompts    print the synthetic prompt list that the live run must answer (JSONL), so the outputs file can be produced.
  aggregate  read completed rating sheets and the private key and write summary.json and summary.md. It never approves anything.

The harness cannot spend money: it has no provider code. Live generation and the native rating need the owner's budget marker and NAMED reviewers (OD-BUDGET, OD-LANG-03); until
then the result is NOT RUN / OPEN and LG-04 / LG-05 stay unapproved (06H needs a named approver, an evidence reference, a date and a release SHA).
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.language_quality import rating as R  # noqa: E402


def selftest(out: Path | None = None) -> dict:
    """Full protocol on fake data. Returns the summary; raises AssertionError on a protocol defect."""
    with tempfile.TemporaryDirectory(prefix="ask4mo_rating_selftest_") as tmp:
        base = Path(out) if out else Path(tmp)
        packet, ratings = base / "packet", base / "ratings"
        manifest = R.build_packet(R.fake_outputs(), packet, seed="selftest-seed", raters=2, fake=True)
        files = R.reviewer_files(packet)
        assert not any(f.startswith("private") for f in files), "private data in the reviewer packet"
        assert sum(f.endswith("rating_sheet.csv") for f in files) == len(R.LANGUAGES) * 2
        R.fake_ratings(packet, ratings)
        summary = R.aggregate(packet, ratings)
        assert summary["fake"] and summary["status"] == "SELFTEST_ONLY" and summary["approved"] is False
        assert all(v["status"] == "READY_FOR_HUMAN_REVIEW" for v in summary["languages"].values()), "fake ratings must complete every language"
        assert manifest["items_per_sheet"] == R.SAMPLING_PLAN["items_per_rater_sheet"]
        if out:
            (base / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
        return summary


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("selftest")
    s.add_argument("--out", type=Path)
    p = sub.add_parser("sample")
    p.add_argument("--outputs", type=Path)
    p.add_argument("--fake", action="store_true")
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--seed")
    p.add_argument("--raters", type=int, default=2)
    sub.add_parser("prompts")
    a = sub.add_parser("aggregate")
    a.add_argument("--packet", type=Path, required=True)
    a.add_argument("--ratings", type=Path, required=True)
    a.add_argument("--out", type=Path, required=True)
    a.add_argument("--reviewers", type=Path, help="optional JSON {language: name} supplied by the owner (OD-LANG-03)")
    args = ap.parse_args(argv)

    if args.cmd == "selftest":
        summary = selftest(args.out)
        print(f"selftest OK: {len(summary['languages'])} languages, status {summary['status']}, approved={summary['approved']}")
        return 0
    if args.cmd == "prompts":
        for item in R.prompt_items():
            print(json.dumps({k: item[k] for k in ("prompt_id", "language", "prompt")}, ensure_ascii=False))
        return 0
    if args.cmd == "sample":
        if args.fake == bool(args.outputs):
            ap.error("give exactly one of --outputs FILE or --fake")
        rows = R.fake_outputs() if args.fake else [json.loads(line) for line in args.outputs.read_text(encoding="utf-8").splitlines() if line.strip()]
        manifest = R.build_packet(rows, args.out, seed=args.seed, raters=args.raters, fake=args.fake)
        print(f"packet written: {manifest['items_per_sheet']} items per sheet, {manifest['raters_per_language']} raters per language; send ONLY {args.out / 'reviewer'} to reviewers")
        return 0
    reviewers = json.loads(args.reviewers.read_text(encoding="utf-8")) if args.reviewers else None
    summary = R.aggregate(args.packet, args.ratings, reviewers=reviewers)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
    (args.out / "summary.md").write_text(R.render_summary_md(summary), encoding="utf-8")
    print(f"status {summary['status']} (never an approval); wrote {args.out / 'summary.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
