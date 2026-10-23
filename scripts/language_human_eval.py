#!/usr/bin/env python
"""Independent human AI evaluation harness (06G; PG-07). Extends scripts/language_rating_harness.py (06C). Offline except the guarded ``generate --live``.

  selftest             the whole protocol end to end on FAKE outputs, FAKE raters and FAKE declarations in a temporary directory; exits non-zero on any defect
  prompts              print the synthetic prompts the sample needs (JSONL; 12 roles x 5 task kinds x 7 languages = 420 lines; ``--base`` for the 06C 210)
  generate             produce outputs.jsonl. ``--offline`` writes labelled FAKE replies. ``--live`` is the ONLY path that can spend money: it refuses unless an approved budget marker,
                       a ceiling (``--ceiling-usd``) and the 05C governor are all present (see src/language_quality/human_eval_generate.py, which calls src.llm.budget.script_guard);
                       engineering never runs it
  sample               build the blinded reviewer packet and the private key from an outputs file (or ``--fake``), at least 3 raters per language
  report               aggregate returned sheets (+ optional ``--declarations DIR`` with completed conflict-of-interest declarations) into results.json and report.md. Never a PASS.
  declaration-template write a BLANK conflict-of-interest declaration for a language and rater slot
  validate-declaration report whether a completed declaration is complete / needs an owner decision
  sync                 ``--write`` regenerates, ``--check`` verifies: the sample-size guidance document, the results schema and the declaration template

Nothing here approves a language, names a reviewer or sets a threshold (OD-GATE-THRESHOLDS, OD-LANG-03). The budget (OD-BUDGET) is the owner's.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import tests.conftest  # noqa: E402,F401  (test isolation: temp DB, no .env)

from src.language_quality import human_eval as H  # noqa: E402
from src.language_quality import human_eval_generate as G  # noqa: E402
from src.language_quality import rating as R  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
GUIDANCE_PATH = ROOT / "docs" / "production" / "execution" / "evidence" / "06G_SAMPLE_SIZE_GUIDANCE.md"


def sync_targets() -> dict[Path, str]:
    return {GUIDANCE_PATH: H.render_guidance_md(), H.SCHEMA_FILE: H.schema_text(),
            H.DECLARATION_TEMPLATE_FILE: json.dumps(H.declaration_template(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"}


def write_report(report: dict, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    for lang, rec in report["languages"].items():
        problems = H.validate_result(rec)
        if problems:
            raise AssertionError(f"result record for {lang} violates the schema: {problems[:3]}")
    (out / "results.json").write_text(json.dumps(report, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
    (out / "report.md").write_text(H.render_report_md(report), encoding="utf-8")


def selftest(out: Path | None = None) -> dict:
    """Full protocol on fake data. Raises AssertionError on a protocol defect."""
    with tempfile.TemporaryDirectory(prefix="ask4mo_human_eval_selftest_") as tmp:
        base = Path(out) if out else Path(tmp)
        base.mkdir(parents=True, exist_ok=True)
        prompts = H.prompt_items()
        rows = G.generate_outputs(prompts, G.fake_responder, max_requests=len(prompts), out_path=base / "outputs.jsonl")
        assert G.covers_bank(rows), "generation did not cover the bank"
        packet, ratings, decls = base / "packet", base / "ratings", base / "declarations"
        manifest = H.build_evaluation_packet(G.to_outputs_rows(rows), packet, seed="selftest-seed", raters=H.MIN_RATERS, fake=True)
        files = R.reviewer_files(packet)
        assert not any(f.startswith("private") for f in files), "private data in the reviewer packet"
        assert sum(f.endswith("rating_sheet.csv") for f in files) == len(H.LANGUAGES) * H.MIN_RATERS
        H.fake_correlated_ratings(packet, ratings)
        H.fake_declarations(decls)
        report = H.analyse(packet, ratings, declarations_dir=decls)
        assert report["fake"] and report["status"] == "SELFTEST_ONLY" and report["approved"] is False
        for lang, rec in report["languages"].items():
            assert rec["status"] == "SELFTEST_ONLY" and not H.validate_result(rec), lang
            assert rec["independence"]["ok"], f"{lang}: fake declarations must be independent"
            assert all(rec["agreement"][d]["krippendorff_alpha_ordinal"] is not None for d in H.DIMENSIONS), f"{lang}: alpha undefined"
        assert manifest["items_per_sheet"] == 12 * 5 + len(R.POLICY_SENTENCE_KEYS) + R.SAMPLING_PLAN["control_items_per_sheet"], "unexpected sheet size"
        write_report(report, base / "result")
        assert "PASS" not in (base / "result" / "report.md").read_text(encoding="utf-8")
        return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("selftest")
    s.add_argument("--out", type=Path)
    p = sub.add_parser("prompts")
    p.add_argument("--base", action="store_true", help="the 06C base roles only")
    g = sub.add_parser("generate")
    mode = g.add_mutually_exclusive_group(required=True)
    mode.add_argument("--offline", action="store_true")
    mode.add_argument("--live", action="store_true")
    g.add_argument("--out", type=Path, required=True)
    g.add_argument("--ceiling-usd")
    g.add_argument("--profile", default="balanced", choices=("fast", "balanced", "advanced"))
    g.add_argument("--max-requests", type=int)
    g.add_argument("--base", action="store_true")
    sm = sub.add_parser("sample")
    sm.add_argument("--outputs", type=Path)
    sm.add_argument("--fake", action="store_true")
    sm.add_argument("--out", type=Path, required=True)
    sm.add_argument("--seed")
    sm.add_argument("--raters", type=int, default=H.MIN_RATERS)
    sm.add_argument("--base", action="store_true")
    r = sub.add_parser("report")
    r.add_argument("--packet", type=Path, required=True)
    r.add_argument("--ratings", type=Path, required=True)
    r.add_argument("--declarations", type=Path)
    r.add_argument("--out", type=Path, required=True)
    d = sub.add_parser("declaration-template")
    d.add_argument("--language", required=True, choices=H.LANGUAGES)
    d.add_argument("--slot", required=True)
    d.add_argument("--out", type=Path, required=True)
    v = sub.add_parser("validate-declaration")
    v.add_argument("file", type=Path)
    y = sub.add_parser("sync")
    y.add_argument("--write", action="store_true")
    y.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)

    if args.cmd == "selftest":
        report = selftest(args.out)
        print(f"selftest OK: {len(report['languages'])} languages, status {report['status']}, approved={report['approved']}")
        return 0
    if args.cmd == "prompts":
        for item in H.prompt_items(not args.base):
            print(json.dumps({k: item[k] for k in ("prompt_id", "language", "prompt")}, ensure_ascii=False))
        return 0
    if args.cmd == "generate":
        prompts = H.prompt_items(not args.base)
        if args.offline:
            rows = G.generate_outputs(prompts, G.fake_responder, max_requests=len(prompts), out_path=args.out)
            print(f"wrote {len(rows)} FAKE replies to {args.out} (self-test data; never send a packet built from it to a reviewer)")
            return 0
        try:
            G.require_governed_generation(ceiling_usd=args.ceiling_usd)
            cap = args.max_requests if args.max_requests is not None else len(prompts)
            rows = G.generate_outputs(prompts, G.live_responder(args.profile), max_requests=cap, out_path=args.out)
        except G.GenerationRefused as exc:
            print(f"REFUSED ({exc.reason}): {exc}", file=sys.stderr)
            return G.REFUSED_EXIT
        print(f"wrote {len(rows)} replies to {args.out}")
        return 0
    if args.cmd == "sample":
        if args.fake == bool(args.outputs):
            ap.error("give exactly one of --outputs FILE or --fake")
        rows = G.to_outputs_rows([json.loads(x) for x in args.outputs.read_text(encoding="utf-8").splitlines() if x.strip()]) if args.outputs else \
            G.to_outputs_rows([{"prompt_id": q["prompt_id"], "language": q["language"], "response": G.fake_responder(q)} for q in H.prompt_items(not args.base)])
        m = H.build_evaluation_packet(rows, args.out, seed=args.seed, raters=args.raters, fake=args.fake, extended=not args.base)
        print(f"packet written: {m['items_per_sheet']} items per sheet, {m['raters_per_language']} raters per language; send ONLY {args.out / 'reviewer'} to reviewers")
        return 0
    if args.cmd == "report":
        report = H.analyse(args.packet, args.ratings, declarations_dir=args.declarations)
        write_report(report, args.out)
        print(f"status {report['status']} (never an approval); wrote {args.out / 'results.json'} and report.md")
        return 0
    if args.cmd == "declaration-template":
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(H.declaration_template(args.language, args.slot), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"wrote a BLANK declaration to {args.out}")
        return 0
    if args.cmd == "validate-declaration":
        status, problems = H.validate_declaration(json.loads(args.file.read_text(encoding="utf-8")))
        print(status)
        for pr in problems:
            print(" -", pr)
        return 0 if status == "ELIGIBLE_FOR_OWNER_APPOINTMENT" else 1
    # sync
    targets = sync_targets()
    if args.write:
        for path, text in targets.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
            print(f"wrote {path.relative_to(ROOT)}")
    stale = [p for p, t in targets.items() if not p.exists() or p.read_text(encoding="utf-8") != t] if args.check else []
    for pth in stale:
        print("STALE:", pth.relative_to(ROOT))
    if args.check:
        print("06G artefacts stale (run sync --write)" if stale else "06G artefacts current")
    print("Paid LLM calls: 0   Live calls: 0")
    return 1 if stale else 0


if __name__ == "__main__":
    raise SystemExit(main())
