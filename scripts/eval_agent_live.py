#!/usr/bin/env python
"""LIVE MODEL EVALUATION runner — real-model tool/retrieval/HITL decisions.

MANUAL / PAID. Never run in CI. Nothing calls a provider unless you explicitly opt in
with ``--allow-paid`` (or ``RUN_PAID_EVAL=1``). Without opt-in it exits safely after
validating configuration. Results can be recorded as sanitised traces and re-scored
offline with ``--evaluate-recorded`` (no provider calls).

    python scripts/eval_agent_live.py                     # safe: no paid call
    python scripts/eval_agent_live.py --allow-paid --profile balanced --record
    python scripts/eval_agent_live.py --evaluate-recorded  # offline re-scoring

This is separate from the deterministic scripted regression
(`python scripts/eval_agent.py`). It measures the actual model's decisions on a
bounded held-out sample; it is not an "LLM accuracy" score.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.agent.live_eval import (  # noqa: E402
    aggregate,
    classify,
    load_live_cases,
    load_traces,
    observation_from_result,
    save_trace,
)

PROFILES = {"fast": "FAST", "balanced": "BALANCED", "advanced": "ADVANCED"}


def _paid_opt_in(args) -> bool:
    return bool(args.allow_paid or os.environ.get("RUN_PAID_EVAL") == "1")


def _print_metrics(title: str, metrics: dict) -> None:
    print(title)
    print("=" * 60)
    for k, v in metrics.items():
        print(f"  {k:<28} {v}")
    print("=" * 60)


def _run_live(profile: str, cases: list[dict], record: bool, limit: int | None):
    from src.agent.models import AgentRunRequest
    from src.application.agent_service import AgentApplicationService, _default_career_service
    from src.copilot.config import load_config
    from src.copilot.llm.openrouter import build_chat_model
    from src.llm.models import ModelProfile, model_id, spec

    prof = ModelProfile[PROFILES[profile]]
    if not spec(prof).supports_tools:
        print(f"Profile {profile} does not support tool calling; aborting.")
        return 2
    slug = model_id(prof)
    career = _default_career_service()

    results = []
    if limit:
        cases = cases[:limit]
    for case in cases:
        svc = AgentApplicationService(
            model_factory=lambda: build_chat_model(load_config(), model=slug),
            career_service=career)
        t0 = time.perf_counter()
        res = svc.run(AgentRunRequest(goal=case["goal"], user_id="live-eval"))
        latency = int((time.perf_counter() - t0) * 1000)
        obs = observation_from_result(case["id"], profile, res, latency)
        if record:
            save_trace(obs)
        results.append(classify(case, obs))
    _print_metrics(f"LIVE MODEL EVALUATION (profile={profile}, cases={len(results)})", aggregate(results))
    return 0


def _evaluate_recorded() -> int:
    cases = {c["id"]: c for c in load_live_cases()}
    traces = load_traces()
    if not traces:
        print("No recorded traces found in evaluations/agent_live/traces/. Run with "
              "--allow-paid --record first.")
        return 1
    results = [classify(cases[t.case_id], t) for t in traces if t.case_id in cases]
    _print_metrics(f"LIVE MODEL EVALUATION — recorded ({len(results)} traces)", aggregate(results))
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Live real-model agent decision benchmark (manual/paid).")
    p.add_argument("--allow-paid", action="store_true", help="opt in to real provider calls (costs money)")
    p.add_argument("--profile", choices=list(PROFILES), default="balanced")
    p.add_argument("--record", action="store_true", help="save sanitised traces for offline re-scoring")
    p.add_argument("--evaluate-recorded", action="store_true", help="re-score recorded traces offline (no provider)")
    p.add_argument("--limit", type=int, default=None, help="limit number of cases (e.g. a 2-case smoke)")
    args = p.parse_args(argv)

    if args.evaluate_recorded:
        return _evaluate_recorded()

    cases = load_live_cases()
    if not _paid_opt_in(args):
        print("LIVE MODEL EVALUATION is manual/paid and did NOT run (no --allow-paid / RUN_PAID_EVAL=1).")
        print(f"Configuration OK: {len(cases)} cases, profile={args.profile}.")
        print("Re-run with --allow-paid to execute, or --evaluate-recorded to score saved traces.")
        return 0
    return _run_live(args.profile, cases, args.record, args.limit)


if __name__ == "__main__":
    sys.exit(main())
