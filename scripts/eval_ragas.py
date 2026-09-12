"""Optional RAGAS generation-quality evaluation CLI (never runs in normal CI).

Thin interface over the shared runner in
``src/copilot/evaluation/ragas_runner.py`` — the Streamlit Evaluation page uses
the same runner, so there is one evaluation implementation. Without evaluator
credentials this prints a clean NOT RUN and exits 0. A live run (``--live``)
generates answers over the PUBLIC held-out cases, scores them with RAGAS, and
writes a unique run directory for COMPLETE/PARTIAL runs; a FAILED run (no valid
scores) writes nothing and exits 2.

Usage:
    python scripts/eval_ragas.py                      # NOT RUN (no creds)
    python scripts/eval_ragas.py --live               # full live run
    python scripts/eval_ragas.py --live --limit 10    # small baseline
    python scripts/eval_ragas.py --live --category role_responsibilities
    python scripts/eval_ragas.py --require-live        # non-zero if it cannot run

Credentials (never printed):
    RAGAS_EVAL_API_KEY   (required for --live)   evaluator model key
    RAGAS_EVAL_BASE_URL, RAGAS_EVAL_MODEL, RAGAS_EVAL_EMBEDDING_MODEL  (optional)
    COPILOT_API_KEY / OpenRouter key             to generate answers (--live)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.copilot.evaluation import ragas_adapter as ra  # noqa: E402
from src.copilot.evaluation import ragas_runner as runner  # noqa: E402

_NOT_RUN = "RAGAS evaluation not run — evaluator credentials not configured."


_JUDGE_SUBSET_PATH = "evaluations/ragas/judge_case_ids.json"


def _load_judge_subset() -> list[str]:
    import json
    from pathlib import Path
    p = Path(_JUDGE_SUBSET_PATH)
    if not p.is_file():
        return []
    return json.loads(p.read_text(encoding="utf-8")).get("case_ids", [])


def _run_provenance() -> dict:
    import subprocess
    from datetime import datetime, timezone
    sha = None
    try:
        sha = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"],  # noqa: S603,S607
                                      stderr=subprocess.DEVNULL, timeout=3).decode().strip()
    except Exception:  # noqa: BLE001
        pass
    ragas_version = None
    try:
        from importlib.metadata import version
        ragas_version = version("ragas")
    except Exception:  # noqa: BLE001
        pass
    return {"git_sha": sha, "ragas_version": ragas_version,
            "generated_at": datetime.now(timezone.utc).isoformat(), "mode": "deterministic"}


def _run_deterministic(json_out: bool, output: str | None = None) -> int:
    """FREE, no-network deterministic RAG evaluation: ID-based context precision/recall over
    the public cases, plus the judge NOT-RUN notice. Makes NO paid/LLM call (§4A/§5/§28)."""
    import json
    from pathlib import Path

    from src.copilot.evaluation import rag_id_metrics as idm

    cases = idm.load_ragas_cases()
    try:
        retrieve = idm.default_retrieve_fn()
    except Exception as exc:  # noqa: BLE001 - never crash the free eval on a KB/setup issue
        print(f"Deterministic evaluation could not build retrieval ({type(exc).__name__}); "
              "is the runtime knowledge base built? See scripts/check_demo_knowledge.py.")
        return 0
    report = idm.compute_id_metrics(cases, retrieve)
    payload = {**_run_provenance(), **report.to_dict()}
    if output:
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        Path(output).write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"Wrote deterministic RAG evaluation to {output}")
    if json_out:
        print(json.dumps(payload, indent=2))
    else:
        print("RAGAS DETERMINISTIC (FREE) EVALUATION")
        print(f"  cases: {report.case_count}  dataset_hash: {report.dataset_hash}")
        print(f"  ID context precision (mean): {report.precision_mean} "
              f"[{report.precision_applicable} applicable]")
        print(f"  ID context recall (mean):    {report.recall_mean} "
              f"[{report.recall_applicable} applicable]")
        print(f"  not-applicable cases: {report.not_applicable}")
        print("\nLLM-JUDGED METRICS:\n  NOT RUN — paid evaluation not authorized")
        print("  Estimate a paid run: python scripts/eval_ragas.py --mode judge --estimate-only")
        print("  Authorize a paid run: python scripts/eval_ragas.py --mode judge --subset reviewer --allow-paid")
    return 0


def _estimate_judge(subset_ids: list[str], all_cases: int) -> int:
    """Print a cost estimate for a paid judge run — makes NO model call (§6/§29)."""
    n = len(subset_ids) if subset_ids else all_cases
    # 4 metrics; context_recall only on referenced cases — estimate ~4 judge calls/case.
    metrics = ["faithfulness", "response_relevancy", "context_precision", "context_recall"]
    est_calls = n * len(metrics)
    evaluator = ra.evaluator_config_from_env(allow_chat_fallback=False)
    model = evaluator.model if evaluator else "gpt-4o-mini (default; RAGAS_EVAL_MODEL)"
    print("RAGAS JUDGE COST ESTIMATE (no calls made)")
    print(f"  judge cases: {n}")
    print(f"  metrics: {', '.join(metrics)}")
    print(f"  estimated judge calls: ~{est_calls} (≈{len(metrics)}/case; recall only on referenced cases)")
    print(f"  judge model: {model}")
    print("  estimated input/output volume: a few hundred tokens per call (short case Q/contexts)")
    print("  cost: unknown (provider pricing not queried; run with pricing metadata to compute)")
    print("  To execute: add --allow-paid (requires RAGAS_EVAL_API_KEY + a chat credential).")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Optional RAGAS generation-quality evaluation.")
    parser.add_argument("--mode", choices=["deterministic", "judge"], default=None,
                        help="deterministic (free, default) or judge (LLM, opt-in/paid)")
    parser.add_argument("--live", action="store_true",
                        help="run the live LLM judge (paid authorization; == --mode judge --allow-paid)")
    parser.add_argument("--allow-paid", action="store_true",
                        help="explicitly authorize paid judge calls (required for --mode judge)")
    parser.add_argument("--estimate-only", action="store_true",
                        help="print a judge cost estimate; make NO model calls")
    parser.add_argument("--subset", choices=["reviewer"], default=None,
                        help="use the fixed reviewer judge subset (evaluations/ragas/judge_case_ids.json)")
    parser.add_argument("--require-live", action="store_true",
                        help="exit non-zero if the live run cannot proceed")
    parser.add_argument("--category", default=None, help="filter to one category")
    parser.add_argument("--limit", type=int, default=None, help="cap the number of cases")
    parser.add_argument("--output-dir", default=None, help="override the run directory")
    parser.add_argument("--json", action="store_true", help="machine-readable deterministic output")
    parser.add_argument("--allow-chat-fallback", action="store_true",
                        help="opt in to reuse the production chat key as the evaluator key")
    args = parser.parse_args(argv)

    def _skip(msg: str) -> int:
        print(msg)
        return 1 if args.require_live else 0

    # --- Mode routing -------------------------------------------------------
    judge_mode = args.live or args.mode == "judge" or args.require_live
    subset_ids = _load_judge_subset() if args.subset == "reviewer" else []

    if args.estimate_only:
        from src.copilot.evaluation import rag_id_metrics as idm
        return _estimate_judge(subset_ids, len(idm.load_ragas_cases()))

    if not judge_mode:
        # DEFAULT = free deterministic evaluation (no paid calls, §5/§28).
        return _run_deterministic(args.json, output=args.output_dir)

    # Judge mode requires explicit paid authorization (§4B/§5): --allow-paid or the
    # legacy --live flag. --mode judge WITHOUT authorization never spends.
    if not (args.allow_paid or args.live):
        print("LLM-JUDGED METRICS:\n  NOT RUN — paid evaluation not authorized")
        print("  Re-run with --allow-paid to authorize paid judge calls, or use "
              "--estimate-only for a cost estimate.")
        return 1 if args.require_live else 0

    # Preconditions (safe checks; no secret values).
    if not ra.ragas_available():
        return _skip("RAGAS is not installed. Install with: pip install -e \".[evaluation]\"")
    evaluator = ra.evaluator_config_from_env(allow_chat_fallback=args.allow_chat_fallback)
    if evaluator is None:
        return _skip(_NOT_RUN)

    from src.copilot.config import load_config

    config = load_config()
    if not config.is_configured:
        return _skip("RAGAS live run needs a chat credential to generate answers "
                     "(COPILOT_API_KEY). Not configured — nothing was run.")

    print(f"Generating answers and scoring via the shared RAGAS runner "
          f"(limit={args.limit or 'all'}, category={args.category or 'all'})…")
    result = runner.run_live_ragas(
        config=config, evaluator_config=evaluator,
        limit=args.limit, category=args.category, case_ids=subset_ids or None,
        output_dir=args.output_dir)

    # HARD STOP: an all-invalid run is never persisted as a normal result.
    if result.is_failed:
        print("RAGAS RUN FAILED — evaluator returned no valid scores.")
        print("No evaluation artifacts were written.")
        print("Check evaluator configuration: RAGAS_EVAL_API_KEY, RAGAS_EVAL_BASE_URL, "
              "RAGAS_EVAL_MODEL and RAGAS_EVAL_EMBEDDING_MODEL.")
        print(f"  Evaluator base URL: {'configured' if evaluator.base_url else 'default'}")
        print(f"  Evaluator model: {evaluator.model}")
        print(f"  Embedding model: {evaluator.embedding_model}")
        return 2

    print(f"Execution status: {result.status} · valid scores "
          f"{result.valid_score_count}/{result.expected_score_count} "
          f"({round(result.score_coverage * 100, 1)}% coverage)")
    if result.status == ra.STATUS_PARTIAL:
        print("PARTIAL run — some evaluator jobs returned no valid score; "
              "aggregates use only valid scores.")
    print(f"Wrote {result.output_directory}/results.json, results.csv, summary.md, "
          "run_config.json")
    for name, value in result.metrics.items():
        print(f"  {name}: {value if value is not None else 'n/a'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
