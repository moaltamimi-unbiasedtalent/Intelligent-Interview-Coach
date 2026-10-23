"""Multilingual retrieval, attribution and abstention harness evaluator (package 06D, LG-06). OFFLINE: the LOCAL lexical hash embedder over the frozen datasets.

    python scripts/eval_multilingual_pairs.py [--write PATH]

Runs the 49-pair (question language x source language) grid and checks the HARNESS invariants: 49 pairs with 7 questions each, every pair carries a sample size and
an interval warning, every citation maps to a retrieved source, every cross-language citation gets the translation notice with the original wording quoted
verbatim, and every abstention is in the question's language with no citation. The result is labelled "harness proof, not retrieval quality": it claims no
retrieval quality, not LG-06, and the data is engineering-authored (not independent, not native-reviewed). Writes only to a temporary directory unless
``--write`` is given. Exit 0 = every harness invariant holds, 1 = one does not.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import tests.conftest  # noqa: E402,F401  (test isolation: temp DB, no .env)

from src.copilot.embeddings import LocalHashEmbedder  # noqa: E402
from src.copilot.evaluation import multilingual_pairs as MP  # noqa: E402


def invariant_failures(result: dict) -> list[str]:
    bad: list[str] = []
    if result["label"] != MP.LABEL:
        bad.append("label")
    if len(result["pairs"]) != 49:
        bad.append("pair_count")
    if any(e["n"] != 7 or not e["warnings"] for e in result["pairs"].values()):
        bad.append("sample_size_or_warning_missing")
    if result["retrieval_quality_claimed"] or result["lg06_met"] or result["native_reviewed"] or result["independent_data"]:
        bad.append("claims")
    a, s = result["attribution_summary"], result["abstention_summary"]
    if not (a["all_citations_map_to_retrieved_sources"] and a["source_language_always_named"] and a["original_quote_always_verbatim"]
            and a["notices_expected"] == a["notices_present"] == 42):
        bad.append("attribution")
    if not (s["language_correct_everywhere"] and s["no_citation_on_abstention_everywhere"]):
        bad.append("abstention")
    return bad


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--write", metavar="PATH", default=None)
    args = ap.parse_args(argv)
    result = MP.run_pair_evaluation(LocalHashEmbedder())
    bad = invariant_failures(result)
    print(f"{result['label'].upper()} (local lexical embedder; synthetic engineering-authored data; LG-06 NOT claimed)")
    for name in ("same_language", "cross_language"):
        r = result["rollups"][name]
        print(f"  {name:15s} pairs={r['pairs']:2d} n={r['n']:3d} mrr={r['mrr']} recall@3={r['recall@3']} ndcg@3={r['ndcg@3']} cross-language@3={r['cross_language_rate@3']}")
    print(f"  attribution: {result['attribution_summary']}")
    print(f"  abstention : cases={result['abstention_summary']['cases']} abstained={result['abstention_summary']['abstained']} "
          f"language_correct={result['abstention_summary']['language_correct_everywhere']}")
    print("  live multilingual benchmark: NOT RUN (needs the 05C governor marker and an owner ceiling)")
    if args.write:
        p = Path(args.write)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(result, indent=1, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"written to {p}")
    if bad:
        print(f"FAIL: {', '.join(bad)}", file=sys.stderr)
        return 1
    print("PASS: harness invariants hold")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
