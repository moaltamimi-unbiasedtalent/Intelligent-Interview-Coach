"""Multi-model embedding benchmark runner CLI (package 02E). DRY RUN by default: no network, no key read, no file written.

    python scripts/run_embedding_benchmark.py                       # dry run: embedding calls and estimated tokens per model, from the dataset
    python scripts/run_embedding_benchmark.py --models PATH         # a different candidate list (default: evaluations/retrieval_quality/benchmark_models.json)
    python scripts/run_embedding_benchmark.py --run --store-dir DIR [--write PATH] [--reindex]
        # a LIVE run through OpenRouter's embeddings endpoint. REFUSED (exit 2) unless the 05C governor's approved-budget marker AI_BUDGET_APPROVED_MARKER
        # (OD-BUDGET:<ref>) is present, the 02B guard (ASK4MO_ALLOW_PAID_EMBEDDINGS=1, ASK4MO_EMBEDDING_BUDGET_MARKER, ASK4MO_EMBEDDING_MAX_CALLS) is satisfied,
        # and the planned calls fit the ceiling. Never set by the repository, CI or an agent.
    python scripts/run_embedding_benchmark.py --rollback KEY --store-dir DIR   # make the previous index version of a model current again (no provider call)

This script selects no model and claims no quality. Exit codes: 0 ran / printed; 2 refused.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.copilot.evaluation import embedding_benchmark as EB  # noqa: E402
from src.copilot.evaluation import multilingual_retrieval as ML  # noqa: E402
from src.copilot.index_manifest import IndexIncompatibleError  # noqa: E402


def _live_factory(spec: EB.ModelSpec):
    """Build the provider-abstraction embedder for one candidate (OpenAI-compatible client against the configured OpenRouter base URL). Reads credentials
    only here, i.e. only after the approval gates have passed."""
    from src.copilot.config import load_config
    from src.copilot.embeddings import OpenAIEmbedder

    cfg = load_config().model_copy(update={"embedding_model": spec.model, "embedding_provider": "openai", "embedding_dimensions": spec.dimensions,
                                           "embedding_version": spec.version, "embedding_base_url": spec.base_url or load_config().embedding_base_url})
    return OpenAIEmbedder(cfg)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--models", metavar="PATH", default=None)
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--store-dir", metavar="DIR", default=None)
    ap.add_argument("--write", metavar="PATH", default=None)
    ap.add_argument("--reindex", action="store_true")
    ap.add_argument("--rollback", metavar="KEY", default=None)
    ap.add_argument("--seed", type=int, default=20260101)
    args = ap.parse_args(argv)

    try:
        models = EB.load_models(Path(args.models) if args.models else None)
    except EB.BenchmarkRefused as exc:
        print(f"REFUSED: {', '.join(exc.codes)}", file=sys.stderr)
        return 2

    if args.rollback:
        if not args.store_dir:
            print("REFUSED: --store-dir is required", file=sys.stderr)
            return 2
        try:
            n = EB.ModelIndexStore(args.store_dir).rollback(args.rollback)
        except IndexIncompatibleError as exc:
            print(f"REFUSED: {', '.join(exc.codes)}", file=sys.stderr)
            return 2
        print(f"{args.rollback}: current index version is now v{n:04d}")
        return 0

    ds, neg = ML.load_dataset(), EB.load_abstention()
    if not args.run:
        plan = EB.plan_run(models, ds, neg)
        print("DRY RUN: no network, no credentials read, no file written.")
        for m in plan["models"]:
            cost = "cost unknown (no price configured)" if m["estimated_cost_usd"] is None else f"about USD {m['estimated_cost_usd']}"
            print(f"  {m['key']:24s} {m['model']:40s} calls={m['embedding_calls']:4d} est.tokens={m['estimated_tokens']:7d}  {cost}")
        print(f"  TOTAL calls={plan['total_embedding_calls']} est.tokens={plan['total_estimated_tokens']} ({plan['documents']} passages, {plan['questions']} questions per model)")
        print("A live run needs the 05C governor marker AI_BUDGET_APPROVED_MARKER, the 02B paid-embedding guard and a ceiling >= total calls.")
        return 0

    if not args.store_dir:
        print("REFUSED: --store-dir is required for --run", file=sys.stderr)
        return 2
    try:
        result = EB.run_embedding_benchmark(models, _live_factory, store_root=args.store_dir, dataset=ds, abstention=neg, seed=args.seed, reindex=args.reindex)
    except EB.BenchmarkRefused as exc:
        print(f"REFUSED before any provider call: {', '.join(exc.codes)}", file=sys.stderr)
        return 2
    text = json.dumps(result, indent=1, sort_keys=True, ensure_ascii=False) + "\n"
    if args.write:
        out = Path(args.write)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        print(f"result written to {out}")
    print(result["label"])
    for row in result["comparison_informational"]:
        print(f"  {row['key']:24s} mrr={row['mrr_mixed']} recall@5={row['recall@5_mixed']} cross-language@5={row['cross_language_retrieval_rate@5']}")
    for f in result["failed_models"]:
        print(f"  FAILED {f['key']}: {', '.join(f['codes'])}")
    print("No production embedder is selected by this run (owner decision OD-EMBED).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
