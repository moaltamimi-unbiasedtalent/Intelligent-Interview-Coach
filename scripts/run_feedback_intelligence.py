#!/usr/bin/env python
"""Run the OFFLINE Feedback Intelligence workflow (Phase 7G).

Default: DETERMINISTIC analysis only — collect safe signals → findings → recommendations →
experiments → persist → STOP for human review. No network, no LLM, no paid call. Optional LLM
synthesis (narrative only) requires BOTH --synthesize AND --allow-paid; --estimate-only reports
scope with no model call.

Usage:
    python scripts/run_feedback_intelligence.py
    python scripts/run_feedback_intelligence.py --json
    python scripts/run_feedback_intelligence.py --synthesize --estimate-only
    python scripts/run_feedback_intelligence.py --synthesize --allow-paid   # opt-in narrative
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.copilot.feedback_intelligence.service import run  # noqa: E402
from src.copilot.feedback_intelligence.signals import (  # noqa: E402
    FixtureAdapter, KnowledgeCoverageAdapter, RagasEvalAdapter, RetrievalEvalAdapter)

FIXTURES = "evaluations/feedback_intelligence/fixtures/signals.json"


def _adapters(fixtures: str):
    # Deterministic, offline sources: synthetic fixtures + any committed reviewed eval artifacts.
    return [FixtureAdapter(fixtures), RetrievalEvalAdapter(), RagasEvalAdapter(),
            KnowledgeCoverageAdapter()]


def _build_synthesizer(allow_paid: bool):
    """Return an LLM narrative synthesiser, or None. Paid authorization is REQUIRED (§44):
    credentials alone are insufficient. Not run in this phase (no --allow-paid in CI/tests)."""
    if not allow_paid:
        return None

    def _synthesize(payload: dict) -> str:  # pragma: no cover - opt-in paid path
        from src.copilot.config import load_config
        from src.copilot.rag.responder import build_openrouter_responder
        cfg = load_config()
        responder = build_openrouter_responder(cfg)
        prompt = ("Summarise these SAFE aggregate findings into a short engineering brief. "
                  "You are given only IDs/counts/labels — never candidate data. Do not invent "
                  "numbers.\n" + json.dumps(payload)[:6000])
        return responder([{"role": "user", "content": prompt}])
    return _synthesize


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Offline Feedback Intelligence workflow.")
    ap.add_argument("--fixtures", default=FIXTURES)
    ap.add_argument("--output-dir", default=None)
    ap.add_argument("--no-persist", action="store_true")
    ap.add_argument("--synthesize", action="store_true", help="add optional LLM narrative (paid)")
    ap.add_argument("--allow-paid", action="store_true", help="authorize paid LLM synthesis")
    ap.add_argument("--estimate-only", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    if args.estimate_only:
        # No model call: report scope only (§45).
        res = run(_adapters(args.fixtures), persist=False)
        recs = len(res.recommendations)
        print("FEEDBACK INTELLIGENCE — LLM SYNTHESIS ESTIMATE (no calls made)")
        print(f"  findings: {len(res.findings)}  recommendations: {recs}")
        print("  estimated model calls: ~1 (single batched narrative over safe summaries)")
        print("  model: project Balanced profile (via provider config)")
        print("  cost: unknown (provider pricing not queried)")
        print("  To execute: --synthesize --allow-paid")
        return 0

    if args.synthesize and not args.allow_paid:
        print("LLM SYNTHESIS: NOT RUN — paid synthesis not authorized (add --allow-paid).")
    synth = _build_synthesizer(args.allow_paid) if args.synthesize else None

    result = run(_adapters(args.fixtures), output_dir=args.output_dir,
                 persist=not args.no_persist, synthesize_fn=synth)

    payload = {
        "signals": result.snapshot.signal_count, "sources": result.snapshot.signal_sources,
        "findings": len(result.findings), "recommendations": len(result.recommendations),
        "experiments": len(result.experiments), "review_status": result.review_status,
        "synthesis_used": result.synthesis_used, "output_directory": result.output_directory,
        "git_dirty": result.snapshot.git_dirty, "warnings": result.warnings,
    }
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print("FEEDBACK INTELLIGENCE (offline, deterministic)")
        print(f"  signals: {payload['signals']}  sources: {payload['sources']}")
        print(f"  findings: {payload['findings']}  recommendations: {payload['recommendations']}  "
              f"experiments: {payload['experiments']}")
        print(f"  review status: {result.review_status} (AWAITING HUMAN REVIEW — nothing changes)")
        for r in result.recommendations[:5]:
            print(f"    P{r.priority} [{r.change_area.value}] {r.title}")
        if result.output_directory:
            print(f"  wrote: {result.output_directory}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
