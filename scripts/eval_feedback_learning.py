#!/usr/bin/env python
"""Deterministic feedback-learning evaluation (Capstone P6/E7).

Offline, no provider call, no cost. Gates the governed feedback→learning loop:
feedback_capture, taxonomy, aggregation, privacy, improvement_candidate_creation,
human_triage, experiment_link, no_auto_change, status_lifecycle.

    python scripts/eval_feedback_learning.py

Exits non-zero on any gate failure.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.copilot.feedback_intelligence.improvement import (  # noqa: E402
    ImprovementStatus, LifecycleError, build_improvement_candidates, transition,
)
from src.copilot.feedback_intelligence.models import ReviewDecision, ReviewOutcome  # noqa: E402
from src.feedback import FeedbackRating, FeedbackSurface  # noqa: E402
from src.feedback_taxonomy import FeedbackCategory, normalize_category  # noqa: E402

_SIGNALS = [
    {"category": "too_verbose", "surface": "agent_answer", "ref": "a1", "rating": "not_helpful"},
    {"category": "too_verbose", "surface": "agent_answer", "ref": "a2", "rating": "not_helpful"},
    {"category": "missing_evidence", "surface": "agent_answer", "ref": "a3", "rating": "not_helpful"},
    {"category": "missing_evidence", "surface": "agent_answer", "ref": "a4", "rating": "not_helpful"},
    {"category": "too_brief", "surface": "final_report", "ref": "a5", "rating": "helpful"},
]


def evaluate() -> dict:
    m: dict = {}

    # 1. feedback_capture — bounded surfaces + binary rating vocabulary exist.
    m["feedback_capture"] = 1 if (
        {s.value for s in FeedbackSurface} == {"agent_answer", "interview_evaluation", "final_report"}
        and {r.value for r in FeedbackRating} == {"helpful", "not_helpful"}
    ) else 0

    # 2. taxonomy — the 11 categories exist and unknown/blank falls back to 'other'.
    cats = {c.value for c in FeedbackCategory}
    expected = {"incorrect", "irrelevant", "too_verbose", "too_brief", "missing_evidence",
                "poor_source", "tool_choice", "language_quality", "retrieval_problem",
                "practice_quality", "other"}
    m["taxonomy"] = 1 if (cats == expected and normalize_category("nonsense") == "other") else 0

    # 3/5. aggregation + improvement_candidate_creation — negative signals aggregate by
    # category to PROPOSED candidates (positive signals ignored; below-threshold dropped).
    candidates = build_improvement_candidates(_SIGNALS, min_support=2)
    cand_cats = {c.problem_category.value for c in candidates}
    m["aggregation"] = 1 if cand_cats == {"too_verbose", "missing_evidence"} else 0
    m["improvement_candidate_creation"] = 1 if (
        candidates and all(c.status is ImprovementStatus.PROPOSED for c in candidates)
        and all(c.support_count >= 2 for c in candidates)
    ) else 0

    # 4. privacy — candidates carry only safe aggregate metadata (extra=forbid; no raw
    # content field), and a raw-content field cannot be smuggled in at construction.
    from src.copilot.feedback_intelligence.improvement import ImprovementCandidate
    smuggle_blocked = 0
    try:
        ImprovementCandidate(
            candidate_id="x", problem_category=FeedbackCategory.OTHER, change_area="ux",
            support_count=1, hypothesis="h", proposed_experiment="e",
            created_at=__import__("datetime").datetime.now(),
            raw_comment="secret candidate content",  # type: ignore[call-arg]
        )
    except Exception:  # noqa: BLE001 - extra=forbid rejects the smuggled private field
        smuggle_blocked = 1
    dumped_ok = all("comment" not in c.model_dump() for c in candidates)
    m["privacy"] = 1 if (smuggle_blocked and dumped_ok) else 0

    # 6. human_triage — a transition requires a human actor id.
    triaged = transition(candidates[0], ImprovementStatus.TRIAGED, actor_id="admin1", reason="ok")
    no_actor_blocked = 0
    try:
        transition(candidates[0], ImprovementStatus.TRIAGED, actor_id="")
    except LifecycleError:
        no_actor_blocked = 1
    m["human_triage"] = 1 if (triaged.status is ImprovementStatus.TRIAGED and no_actor_blocked) else 0

    # 7. experiment_link — every candidate references a Prompt Lab experiment plan.
    m["experiment_link"] = 1 if all(
        "Prompt Lab" in c.proposed_experiment for c in candidates) else 0

    # 8. no_auto_change — a 7G review decision never executes; aggregation never yields an
    # ACCEPTED/IMPLEMENTED candidate; IMPLEMENTED is unreachable without ACCEPTED.
    rd = ReviewDecision(proposal_id="p1", decision=ReviewOutcome.APPROVE,
                        reviewed_at=__import__("datetime").datetime.now())
    illegal_blocked = 0
    try:
        transition(candidates[0], ImprovementStatus.IMPLEMENTED, actor_id="admin1")
    except LifecycleError:
        illegal_blocked = 1
    m["no_auto_change"] = 1 if (
        rd.executed is False
        and all(c.status is ImprovementStatus.PROPOSED for c in candidates)
        and illegal_blocked
    ) else 0

    # 9. status_lifecycle — the full legal path works end to end.
    c = candidates[0]
    try:
        for to in (ImprovementStatus.TRIAGED, ImprovementStatus.EXPERIMENTING,
                   ImprovementStatus.ACCEPTED, ImprovementStatus.IMPLEMENTED):
            c = transition(c, to, actor_id="admin1")
        lifecycle_ok = c.status is ImprovementStatus.IMPLEMENTED and len(c.history) == 4
    except LifecycleError:
        lifecycle_ok = False
    m["status_lifecycle"] = 1 if lifecycle_ok else 0

    return m


GATES = {
    "feedback_capture": 1, "taxonomy": 1, "aggregation": 1, "privacy": 1,
    "improvement_candidate_creation": 1, "human_triage": 1, "experiment_link": 1,
    "no_auto_change": 1, "status_lifecycle": 1,
}


def gate_failures(m: dict) -> list[str]:
    return [f"{k} = {m.get(k)} (want {v})" for k, v in GATES.items() if m.get(k) != v]


def main() -> int:
    m = evaluate()
    print("FEEDBACK LEARNING EVALUATION (Capstone P6/E7, offline, no paid calls)")
    print("=" * 68)
    for k in GATES:
        print(f"  {k:<32} {m.get(k)}  (gate == {GATES[k]})")
    print("=" * 68)
    fails = gate_failures(m)
    if fails:
        print("\nGATE STATUS: FAIL")
        for f in fails:
            print(f"  - {f}")
        return 1
    print("\nGATE STATUS: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
