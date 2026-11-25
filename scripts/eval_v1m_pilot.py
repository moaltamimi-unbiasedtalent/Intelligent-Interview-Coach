"""Deterministic/offline-first V1M micro-decision pilot evaluator.

Default mode runs every fixture against the local deterministic baseline and
prints a shadow comparison plan. --live makes at most one synthetic request
per fixture using V1M_PILOT_ENABLED=true and V1M_API_KEY.

No candidate data is sent. Live mode is opt-in and the result never changes
career routing or synthesis.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.copilot.rag.v1m_pilot import (
    V1mDecisionUseCase,
    classify_decision,
)
from src.agent.specialists.router import RoutingContext, recommend_specialists
from src.copilot.rag.translation import heuristic_translation

CASES_PATH = Path(__file__).resolve().parents[1] / "evaluations" / "v1m" / "pilot_cases.json"
MICRO_CASES_PATH = Path(__file__).resolve().parents[1] / "evaluations" / "v1m" / "micro_decision_cases.json"


def _baseline(state: str) -> str:
    translated = heuristic_translation(state)
    return "retrieval_needed" if translated.retrieval_required else "retrieval_not_needed"


def _baseline_for_case(case: dict) -> str:
    use_case = case["use_case"]
    if use_case == "retrieval_need":
        return _baseline(case["state"])
    if use_case == "utterance_type":
        return "smalltalk" if heuristic_translation(case["state"]).intent == "smalltalk" else "candidate_question"
    if use_case == "specialist_call":
        context = case.get("context", {})
        role = context.get("role", "none")
        evidence = context.get("evidence", "none")
        coaching = bool(context.get("coaching"))
        routing = RoutingContext(
            has_job_description=role == "known",
            has_requirements=role == "known",
            has_target_role=role == "known",
            has_owner_evidence=evidence == "approved",
            wants_coaching=coaching,
        )
        recommendations = recommend_specialists(routing)
        return "specialist_needed" if recommendations else "specialist_not_needed"
    if use_case == "role_ambiguity":
        state = case["state"].lower()
        ambiguous_terms = ("product manager", "manager", "developer")
        clear_terms = ("registered nurse", "software engineer")
        if any(term in state for term in ambiguous_terms):
            return "role_ambiguous"
        if any(term in state for term in clear_terms):
            return "role_unambiguous"
        return "role_unambiguous"
    if use_case == "continue_without_clarification":
        context = case.get("context", {})
        if context.get("role_ambiguous") or context.get("missing_required_input"):
            return "needs_clarification"
        return "continue_without_clarification"
    return "uncertain"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true", help="Call V1M for synthetic fixtures only")
    parser.add_argument("--threshold", type=float, default=None)
    parser.add_argument(
        "--use-cases",
        action="store_true",
        help="Evaluate all five closed micro-decision use cases",
    )
    args = parser.parse_args()

    cases_path = MICRO_CASES_PATH if args.use_cases else CASES_PATH
    cases = json.loads(cases_path.read_text(encoding="utf-8"))["cases"]
    matched = 0
    uncertain = 0
    provider_errors = 0

    for case in cases:
        baseline = _baseline_for_case(case) if args.use_cases else _baseline(case["state"])
        if args.live:
            use_case = V1mDecisionUseCase(case["use_case"])
            pilot = classify_decision(
                case["state"],
                use_case,
                enabled=True,
                threshold=args.threshold,
            )
        else:
            pilot = None

        if pilot is None:
            label = "not_run_offline"
        else:
            label = pilot.label
            if pilot.status != "ok":
                provider_errors += 1
            elif pilot.label == "uncertain":
                uncertain += 1
        if pilot is not None and pilot.status == "ok" and label == case["expected"]:
            matched += 1
        agreement = pilot is not None and pilot.status == "ok" and pilot.label == baseline
        print(
            json.dumps({
                "id": case["id"],
                "baseline": baseline,
                "expected": case["expected"],
                "pilot": label,
                "probability": pilot.probability if pilot else None,
                "latency_ms": pilot.latency_ms if pilot else None,
                "agreement": agreement,
            }, sort_keys=True)
        )

    print(json.dumps({
        "mode": "live" if args.live else "offline",
        "cases": len(cases),
        "matched": matched if args.live else None,
        "uncertain": uncertain if args.live else None,
        "provider_errors": provider_errors if args.live else None,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
