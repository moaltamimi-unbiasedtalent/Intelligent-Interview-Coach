#!/usr/bin/env python
"""06F review packs (LG-10, LG-11): generate, check, freeze, diff and validate a completed form. Offline: no model call, no network, no credential.

  --write                      regenerate docs/production/language_review/ (per-language packs and FREEZE_MANIFEST.json)
  --check                      fail (exit 1) when the committed packs or manifest differ from what the code generates
  --freeze --release-sha SHA --out DIR
                               write DIR/FREEZE_SNAPSHOT.json: per-item digests of every language at the release SHA the owner named (never run by engineering)
  --diff --baseline FILE [--language L] --out DIR
                               write DIR/CHANGES_SINCE_REVIEW_<language>.md listing only what changed since the frozen snapshot (incremental re-review)
  --validate-form FILE --gate LG-11|LG-10
                               report what a COMPLETED sign-off form is missing; prints the language_readiness.json fields it maps to when it is complete. Writes nothing.

Needs node and the frontend dependencies (the catalogue is bundled with esbuild into the OS temp dir). Nothing here records a review, names a reviewer or approves a language.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import tests.conftest  # noqa: E402,F401  (test isolation: temp DB, no .env)

from src.language_quality import review_pack as P  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--freeze", action="store_true")
    ap.add_argument("--release-sha")
    ap.add_argument("--diff", action="store_true")
    ap.add_argument("--baseline", type=Path)
    ap.add_argument("--language", choices=P.LANGUAGES)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--validate-form", type=Path)
    ap.add_argument("--gate", choices=P.FORM_GATES)
    args = ap.parse_args(argv)

    if args.validate_form:
        if not args.gate:
            ap.error("--validate-form needs --gate")
        form = json.loads(args.validate_form.read_text(encoding="utf-8"))
        expected = None
        try:
            _, _, contents = P.build_all()
            expected = P.content_digest(contents[form.get("language")]) if form.get("language") in contents else None
        except RuntimeError as exc:
            print(f"note: the current pack digest could not be computed ({exc}); the digest comparison is skipped")
        problems = P.validate_form(form, args.gate, expected_digest=expected)
        if problems:
            print("FORM INCOMPLETE OR INVALID:")
            for p in problems:
                print(" -", p)
            return 1
        print("FORM COMPLETE. Nothing was recorded. If the owner accepts it, these are the language_readiness.json fields (see OWNER_READINESS_CHECKLIST.md):")
        print(json.dumps({"language": form["language"], "gate": args.gate, "fields": P.gate_fragment(form, args.gate)}, indent=2, ensure_ascii=False))
        return 0

    packs, manifest, contents = P.build_all()
    if args.freeze:
        if not (args.release_sha and args.out):
            ap.error("--freeze needs --release-sha and --out")
        snap = P.build_snapshot(contents, manifest, args.release_sha)
        args.out.mkdir(parents=True, exist_ok=True)
        path = args.out / "FREEZE_SNAPSHOT.json"
        path.write_text(json.dumps(snap, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        print(f"wrote {path}; this records a freeze, not a review")
        return 0
    if args.diff:
        if not (args.baseline and args.out):
            ap.error("--diff needs --baseline and --out")
        snap = json.loads(args.baseline.read_text(encoding="utf-8"))
        args.out.mkdir(parents=True, exist_ok=True)
        for lang in ([args.language] if args.language else list(P.LANGUAGES)):
            d = P.diff_against(snap, contents[lang])
            (args.out / f"CHANGES_SINCE_REVIEW_{lang}.md").write_text(P.render_changes_md(d, contents[lang]), encoding="utf-8")
            print(f"{lang}: {d['needs_rereview']} item(s) need re-review, {d['unchanged']} unchanged")
        return 0
    if args.write:
        written = P.write_all(packs, manifest)
        print(f"wrote {len(written)} files under {P.PACK_DIR.relative_to(P.ROOT)}")
    else:
        with tempfile.TemporaryDirectory() as d:
            written = P.write_all(packs, manifest, Path(d))
            print(f"generated {len(written)} files in a temporary directory (nothing written to the repository)")
    code = 0
    if args.check:
        stale = P.check_all(packs, manifest)
        for s in stale:
            print("STALE:", s)
        print("review packs stale (run --write)" if stale else "review packs current")
        code = 1 if stale else 0
    print("Paid LLM calls: 0   Live calls: 0   Sign-offs recorded: 0")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
