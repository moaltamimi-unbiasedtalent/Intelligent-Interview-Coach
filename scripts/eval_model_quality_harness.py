#!/usr/bin/env python
"""W12.4D-P2-C: offline validation of the blinded model-profile comparison FRAMEWORK. Deterministic, 0 provider calls, 0 paid calls, 0 candidate data.

This validates the HARNESS (scenario coverage, blinding, aggregation, unknown-stays-unknown, no verdict without evidence). It is NOT model-quality evidence and
says nothing about whether Fast, Balanced or Advanced is adequate; a mocked runner cannot prove that."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import tests.conftest  # noqa: E402,F401  (isolation guard: temp DB, no .env)

from src.model_quality import harness as H  # noqa: E402


def _valid_output(task: str) -> dict:
    if task == "question_generation":
        return {"question_id": 1, "question": "Describe a time you handled a difficult situation.", "question_type": "behavioural", "competency": "Resilience",
                "difficulty": "easy", "interviewer_intent": "Look for a clear example.", "expected_answer_elements": ["situation", "action", "result"]}
    return {"overall_score": 70, "relevance": 7, "structure": 7, "evidence": 6, "role_knowledge": 6, "problem_solving": 7, "communication": 7, "credibility": 7,
            "strengths": ["clear"], "improvement_areas": ["add detail"], "missing_evidence": ["numbers"], "stronger_answer_structure": "Use situation, action, result.",
            "improved_example_answer": "Illustrative only.", "follow_up_question": "What would you do differently?"}


def run() -> dict[str, tuple[bool, str]]:
    out: dict[str, tuple[bool, str]] = {}

    def check(name: str, ok: bool, detail: str = "") -> None:
        out[name] = (bool(ok), detail)

    scenarios = H.load_scenarios()
    check("scenario_set_is_synthetic_diverse_and_clean", H.validate_scenarios(scenarios) == [], f"{len(scenarios)} scenarios")
    check("profiles_are_exactly_fast_balanced_advanced", H.PROFILES == ("fast", "balanced", "advanced"), str(H.PROFILES))

    def fake(profile: str, s: H.Scenario, task: str) -> H.RunResult:        # deterministic stand-in: proves mechanics only
        if profile == "fast" and s.id == "MQ-01" and task == "answer_feedback":
            return H.RunResult(ok=False, error_category="timeout", attempts=2)
        if profile == "balanced" and task == "question_generation" and s.id == "MQ-02":
            return H.RunResult(ok=True, output={"question": "incomplete"}, latency_ms=900, attempts=1)
        return H.RunResult(ok=True, output=_valid_output(task), latency_ms=100 + 50 * H.PROFILES.index(profile), attempts=1,
                           input_tokens=None if s.id == "MQ-03" else 200, output_tokens=None if s.id == "MQ-03" else 100, cost_usd=None)

    cells = H.run_benchmark(fake, scenarios)
    agg = H.aggregate(cells)
    check("every_profile_scenario_and_task_is_run", len(cells) == len(scenarios) * len(H.TASKS) * 3, f"{len(cells)} cells")
    check("failures_and_structural_invalidity_are_counted", agg["fast"]["failure_rate"] > 0 and agg["balanced"]["structural_invalid_rate"] > 0, "")
    check("unknown_tokens_and_cost_stay_unknown", agg["fast"]["tokens_unknown_runs"] > 0 and agg["fast"]["cost_usd_known_total"] is None and agg["fast"]["cost_known_runs"] == 0, "no zero and no assumed price")
    sheet, key = H.blind(cells, seed=7)
    check("rating_sheet_hides_profile_names", all("profile" not in row for row in sheet) and "fast" not in str(sheet).lower().replace("fast-paced", ""), "")
    check("blinding_is_reproducible_by_seed_and_varies_by_seed", H.blind(cells, seed=7)[1] == key and H.blind(cells, seed=8)[1] != key, "")
    check("no_verdict_without_ratings_or_approved_thresholds", H.evaluate_gate(agg, None, None)["verdict"] == "NOT_EVALUATED"
          and H.evaluate_gate(agg, {"fast|question_relevance": 5.0}, None)["verdict"] == "NOT_EVALUATED", "mocked evidence can never qualify a profile")
    return out


def main() -> int:
    print("ASK4MO - MODEL PROFILE QUALITY FRAMEWORK VALIDATION (FRAMEWORK ONLY; NO QUALITY EVIDENCE; NO LIVE CALLS)\n")
    res = run()
    failed = False
    for name in sorted(res):
        ok, detail = res[name]
        failed |= not ok
        print(f"  {name:62s} {'PASS' if ok else 'FAIL'}  {detail}")
    print("\nPaid LLM calls: 0   Live calls: 0")
    print("\nRESULT: " + ("FAIL" if failed else "PASS (framework mechanics only; Fast quality is NOT established)"))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
