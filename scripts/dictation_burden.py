#!/usr/bin/env python
"""04F dictation correction-burden HARNESS (protocol and scoring tool). It makes NO measurement claim.

A human tester dictates a fixed set of synthetic prompts in each language through the browser dictation control, then edits the dictated text until it says what was intended.
This tool (1) prepares a blank session sheet, (2) validates a filled sheet, and (3) computes the word-level edits the tester had to make.

Definitions (all word level, after normalisation: Unicode NFC, case-folded, leading and trailing punctuation removed from each token, empty tokens dropped):
  raw      the text the browser engine produced, copied BEFORE any edit
  final    the text after the tester finished correcting it
  edits    the minimum word insertions, deletions and substitutions that turn ``raw`` into ``final`` (Levenshtein over words)
  correction burden   = edits / words in ``final`` * 100  (edit operations per 100 intended words; lower is better; 0 = no correction needed)
  per-word edit distance = edits / words in ``final`` (the same value as a fraction)
  residual error      = edits that turn ``final`` into the printed prompt; non-zero means the tester left a mismatch (reported, never hidden)

Evidence boundary: a result file carries ``data_origin``. ``synthetic_example`` (worked example, invented data) and ``human_session`` (a real run with appointed participants). Nothing printed
here is a quality claim, no acceptance threshold is built in (the owner decides it) and a small participant count is reported as such. No audio is read, recorded or stored: the sheet holds
text only and participants are pseudonymous codes (an email-like code is rejected).

Usage:
  python scripts/dictation_burden.py template --language de-DE --participant P01 --browser "Chrome 130" -o sheet.json
  python scripts/dictation_burden.py score sheet.json -o results.json      # fails closed on an invalid sheet
  python scripts/dictation_burden.py example -o /path/to/dir                # fake-data worked example (writes sheet.json and results.json)
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROMPTS_PATH = ROOT / "evaluations/dictation_burden/prompts_v1.json"
DATA_ORIGINS = ("synthetic_example", "human_session")
LANGUAGES = ("en-US", "de-DE", "fr-FR", "es-ES", "it-IT", "pt-PT", "nl-NL")   # the seven speech languages; Russian is not offered
BANNER = ("NOT A MEASUREMENT CLAIM. This is harness output. Only a run with data_origin=human_session by appointed participants is evidence, and even then it carries no acceptance "
          "threshold: the owner sets that.")


class SheetError(ValueError):
    """The session sheet is invalid (the scorer fails closed rather than guess)."""


def load_prompts(path: Path = PROMPTS_PATH) -> dict[str, list[str]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data["languages"]


def normalise(text: str) -> list[str]:
    """Tokenise for scoring: NFC, case-fold, strip punctuation at token edges (keeps internal hyphens and apostrophes), drop empties."""
    def is_punct(ch: str) -> bool:
        return unicodedata.category(ch)[0] in ("P", "S")

    tokens = []
    for tok in unicodedata.normalize("NFC", text or "").casefold().split():
        start, end = 0, len(tok)
        while start < end and is_punct(tok[start]):
            start += 1
        while end > start and is_punct(tok[end - 1]):
            end -= 1
        if end > start:
            tokens.append(tok[start:end])
    return tokens


def edit_ops(a: list[str], b: list[str]) -> dict[str, int]:
    """Minimum word edits turning ``a`` into ``b``: {"insertions", "deletions", "substitutions", "distance"}.

    The distance is unique; when several minimal alignments exist the split between the three kinds uses a fixed preference (substitute, then delete, then insert) so results are reproducible.
    """
    n, m = len(a), len(b)
    d = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        d[i][0] = i
    for j in range(m + 1):
        d[0][j] = j
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            d[i][j] = min(d[i - 1][j - 1] + (a[i - 1] != b[j - 1]), d[i - 1][j] + 1, d[i][j - 1] + 1)
    ins = dele = sub = 0
    i, j = n, m
    while i > 0 or j > 0:
        if i > 0 and j > 0 and d[i][j] == d[i - 1][j - 1] + (a[i - 1] != b[j - 1]):
            sub += a[i - 1] != b[j - 1]
            i, j = i - 1, j - 1
        elif i > 0 and d[i][j] == d[i - 1][j] + 1:
            dele += 1
            i -= 1
        else:
            ins += 1
            j -= 1
    return {"insertions": ins, "deletions": dele, "substitutions": sub, "distance": d[n][m]}


def score_trial(trial: dict, prompts: dict[str, list[str]]) -> dict:
    raw, final = normalise(trial["raw"]), normalise(trial["final"])
    reference = normalise(prompts[trial["language"]][trial["prompt_index"]])
    ops = edit_ops(raw, final)
    residual = edit_ops(final, reference)["distance"]
    words = len(final)
    burden = round(100.0 * ops["distance"] / words, 2) if words else None
    return {"participant": trial["participant"], "language": trial["language"], "browser": trial["browser"], "prompt_index": trial["prompt_index"], "final_words": words,
            "raw_words": len(raw), **ops, "edit_distance_per_word": round(ops["distance"] / words, 4) if words else None, "correction_burden": burden,
            "residual_errors_vs_prompt": residual}


def validate_sheet(sheet: dict, prompts: dict[str, list[str]] | None = None) -> list[dict]:
    """Return the trial list or raise SheetError. Strict: an unknown language, an out-of-range prompt, a missing field or an email-like participant code fails the whole sheet."""
    prompts = prompts or load_prompts()
    if sheet.get("data_origin") not in DATA_ORIGINS:
        raise SheetError(f"data_origin must be one of {DATA_ORIGINS}")
    trials = sheet.get("trials")
    if not isinstance(trials, list) or not trials:
        raise SheetError("trials must be a non-empty list")
    for k, t in enumerate(trials):
        if not isinstance(t, dict):
            raise SheetError(f"trial {k} is not an object")
        for field in ("participant", "language", "browser", "prompt_index", "raw", "final"):
            if field not in t:
                raise SheetError(f"trial {k} is missing {field}")
        if t["language"] not in LANGUAGES or t["language"] not in prompts:
            raise SheetError(f"trial {k}: language {t['language']!r} is not one of the seven speech languages")
        if not isinstance(t["prompt_index"], int) or isinstance(t["prompt_index"], bool) or not 0 <= t["prompt_index"] < len(prompts[t["language"]]):
            raise SheetError(f"trial {k}: prompt_index out of range")
        if not all(isinstance(t[f], str) for f in ("participant", "browser", "raw", "final")):
            raise SheetError(f"trial {k}: participant, browser, raw and final must be text")
        if re.search(r"@|\s", t["participant"]) or not t["participant"]:
            raise SheetError(f"trial {k}: participant must be a pseudonymous code (no email, no spaces)")
    return trials


def summarise(scored: list[dict]) -> dict:
    """Per language and overall: counts and the burden spread. No pass/fail verdict is produced."""
    def block(rows: list[dict]) -> dict:
        burdens = [r["correction_burden"] for r in rows if r["correction_burden"] is not None]
        words = sum(r["final_words"] for r in rows)
        edits = sum(r["distance"] for r in rows)
        return {"trials": len(rows), "participants": len({r["participant"] for r in rows}), "final_words": words, "edits": edits,
                "insertions": sum(r["insertions"] for r in rows), "deletions": sum(r["deletions"] for r in rows), "substitutions": sum(r["substitutions"] for r in rows),
                "pooled_burden_per_100_words": round(100.0 * edits / words, 2) if words else None,
                "median_trial_burden": round(statistics.median(burdens), 2) if burdens else None,
                "min_trial_burden": min(burdens) if burdens else None, "max_trial_burden": max(burdens) if burdens else None,
                "trials_with_residual_error": sum(1 for r in rows if r["residual_errors_vs_prompt"] > 0)}
    return {"overall": block(scored), "by_language": {lang: block([r for r in scored if r["language"] == lang]) for lang in sorted({r["language"] for r in scored})}}


def score_sheet(sheet: dict, prompts: dict[str, list[str]] | None = None) -> dict:
    prompts = prompts or load_prompts()
    trials = validate_sheet(sheet, prompts)
    scored = [score_trial(t, prompts) for t in trials]
    return {"banner": BANNER, "data_origin": sheet["data_origin"], "prompt_set": sheet.get("prompt_set", "prompts_v1"), "trials": scored, "summary": summarise(scored),
            "limits": ["no audio is captured or scored", "word level only: punctuation is ignored by normalisation, so punctuation correction effort is NOT counted",
                       "burden depends on the tester's accent, microphone, room, browser engine and version: pool only like with like",
                       "no acceptance threshold is defined here; a small participant count is reported, never extrapolated"]}


def blank_sheet(language: str, participant: str, browser: str, prompts: dict[str, list[str]] | None = None) -> dict:
    prompts = prompts or load_prompts()
    if language not in LANGUAGES:
        raise SheetError(f"language must be one of {LANGUAGES}")
    return {"data_origin": "human_session", "prompt_set": "prompts_v1",
            "instructions": ["Read each prompt aloud ONCE, naturally, using the product dictation control (microphone button) with this language selected.",
                             "Copy the field text EXACTLY as dictated into `raw` before touching it.",
                             "Then correct the field until it says what the prompt says and copy the result into `final`.",
                             "Do not record audio. Use only your pseudonymous code. Record the browser name and version."],
            "trials": [{"participant": participant, "language": language, "browser": browser, "prompt_index": i, "prompt": text, "raw": "", "final": ""}
                       for i, text in enumerate(prompts[language])]}


def worked_example() -> dict:
    """FAKE data: invented dictation outputs for invented participants. Demonstrates the arithmetic only."""
    prompts = load_prompts()
    en = prompts["en-US"]
    de = prompts["de-DE"]
    trials = [
        # en, prompt 1: engine drops "the" and changes "interviewer" -> final restores both (1 insertion, 1 substitution)
        {"participant": "FAKE-A", "language": "en-US", "browser": "FakeBrowser 1.0", "prompt_index": 1,
         "raw": "I would start by asking interviewer which three customer problem matter most for the first year", "final": en[1]},
        # en, prompt 3: perfect dictation (0 edits)
        {"participant": "FAKE-A", "language": "en-US", "browser": "FakeBrowser 1.0", "prompt_index": 3, "raw": en[3], "final": en[3]},
        # de, prompt 1: one substitution ("Interviewerin" heard as "Interview") and one deletion of a stray word
        {"participant": "FAKE-B", "language": "de-DE", "browser": "FakeBrowser 1.0", "prompt_index": 1,
         "raw": "Ich würde zuerst äh die Interview fragen welche drei Kundenprobleme im ersten Jahr am wichtigsten sind", "final": de[1]},
    ]
    return {"data_origin": "synthetic_example", "prompt_set": "prompts_v1", "trials": trials}


def _write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("template", help="write a blank session sheet for one participant and language")
    t.add_argument("--language", required=True, choices=LANGUAGES)
    t.add_argument("--participant", required=True)
    t.add_argument("--browser", required=True)
    t.add_argument("-o", "--out", required=True)
    s = sub.add_parser("score", help="score a filled session sheet")
    s.add_argument("sheet")
    s.add_argument("-o", "--out")
    e = sub.add_parser("example", help="run the FAKE-data worked example (writes sheet.json and results.json into --out)")
    e.add_argument("-o", "--out", required=True, help="existing or new directory")
    args = ap.parse_args(argv)
    try:
        if args.cmd == "template":
            sheet = blank_sheet(args.language, args.participant, args.browser)
            if re.search(r"@|\s", args.participant):
                raise SheetError("participant must be a pseudonymous code (no email, no spaces)")
            _write(Path(args.out), sheet)
            print(f"wrote {args.out} ({len(sheet['trials'])} prompts, language {args.language})")
        elif args.cmd == "score":
            result = score_sheet(json.loads(Path(args.sheet).read_text(encoding="utf-8")))
            if args.out:
                _write(Path(args.out), result)
            print(BANNER)
            print(f"data_origin={result['data_origin']} trials={result['summary']['overall']['trials']}")
            print(json.dumps(result["summary"], ensure_ascii=False, indent=2))
        else:
            out = Path(args.out)
            sheet = worked_example()
            _write(out / "sheet.json", sheet)
            result = score_sheet(sheet)
            _write(out / "results.json", result)
            print(BANNER)
            print("data_origin=synthetic_example (FAKE data; arithmetic demonstration only)")
            print(json.dumps(result["summary"]["overall"], ensure_ascii=False, indent=2))
    except (SheetError, json.JSONDecodeError, KeyError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
