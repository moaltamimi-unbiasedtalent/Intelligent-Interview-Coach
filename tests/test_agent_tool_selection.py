"""Deterministic agent-orchestration regression over the synthetic case set.

This is NOT a live LLM benchmark — each case scripts the model's tool calls, so it
measures routing/prerequisites/state-carry/rejection deterministically without any
provider call (see src/agent/eval.py).
"""

from __future__ import annotations

from types import SimpleNamespace

from src.agent.eval import evaluate, load_cases
from src.copilot.tools.schemas import (
    GapAllocation,
    GapAnalysisResult,
    InterviewQuestionSet,
    MatchStats,
    PreparationPlan,
    PriorityGap,
    QuestionCategory,
    RoleRequirements,
)


def _call(value):
    return SimpleNamespace(ok=True, value=value, error=None,
                           execution=SimpleNamespace(tool_name="x", status="ok", error=None))


class FakeCareer:
    def analyze_job_description(self, jd):
        return _call(RoleRequirements(role_title="Senior Product Manager", seniority="senior", required_skills=["Roadmapping"]))

    def analyze_candidate_gaps(self, bg, role):
        return _call(GapAnalysisResult(matched=["Discovery"], partially_matched=[], missing=["Exec comms"], strengths=["Discovery"],
                                       priority_gaps=[PriorityGap(requirement="Exec comms", category="c", severity="high", reason="r")],
                                       stats=MatchStats(total_requirements=3, matched=1, partial=0, missing=2, match_percentage=33, weighted_match_percentage=30)))

    def build_preparation_plan(self, gaps, days, hours):
        return _call(PreparationPlan(days_until_interview=days, hours_per_week=hours, total_available_hours=float(days) / 7 * hours,
                                     allocations=[GapAllocation(requirement="Exec comms", severity="high", allocated_hours=6, share_percentage=100, actions=["x"])], weekly_structure=[], notes=[]))

    def generate_questions(self, role, reqs, focus):
        return _call(InterviewQuestionSet(role=role, categories=[QuestionCategory(name="Behavioural", questions=["Q1?"])]))


def test_tool_selection_regression_metrics():
    cases = load_cases()
    assert len(cases) >= 20
    metrics = evaluate(cases, FakeCareer())

    # Every case's required tools all executed (missing-prereq/adversarial expect none).
    assert metrics["required_tool_recall"] == 1.0
    # No tool executed outside the expected set for any case.
    assert metrics["unnecessary_tool_rate"] == 0.0
    # The two adversarial cases (shell_command, search_career_knowledge) were rejected.
    assert metrics["unregistered_tool_attempts"] >= 2
    # Every run terminated cleanly (no crash).
    assert metrics["completion_rate"] == 1.0
