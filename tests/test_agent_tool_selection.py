"""Deterministic agent-orchestration regression over the synthetic case set.

This is NOT a live LLM benchmark — each case scripts the model's tool calls, so it
measures routing/prerequisites/state-carry/rejection deterministically without any
provider call (see src/agent/eval.py).
"""

from __future__ import annotations

from types import SimpleNamespace

from src.agent.eval import (
    build_eval_career,
    evaluate,
    gate_failures,
    hitl_and_isolation_probe,
    load_cases,
)
from src.copilot.models import Citation, KnowledgeEvidence
from src.copilot.service import KnowledgeRetrievalResult
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

    def search_knowledge(self, req, *, progress=None):
        # The retrieval-ONLY operation the SearchCareerKnowledge tool wraps (no
        # Career tools, no final synthesis).
        return KnowledgeRetrievalResult(
            evidence=[KnowledgeEvidence(evidence_id="e1", text="band", source_id="esco", source_title="ESCO", source_url="https://esco", evidence_type="compensation", geography="DE", occupation_title="Product manager", reference_year=2024)],
            citations=[Citation(marker="[1]", doc_id="d1", chunk_id="c1", title="ESCO", source="ESCO", source_url="https://esco", page=None)],
            resolved_occupation="Product manager", resolved_geography="DE",
            retrieval_lane="compensation", retrieval_strategy="structured",
            source_count=1, insufficient_evidence=False,
        )


def test_tool_selection_regression_metrics():
    cases = load_cases()
    assert len(cases) >= 50  # held-out orchestration dataset finalised in Phase 11
    metrics = evaluate(cases, FakeCareer())

    # Every case's required tools all executed (missing-prereq/adversarial expect none).
    assert metrics["required_tool_recall"] == 1.0
    # No tool executed outside the expected set for any case.
    assert metrics["unnecessary_tool_rate"] == 0.0
    # Adversarial cases (shell_command + low-level RAG store names) were rejected.
    assert metrics["unregistered_tool_attempts"] >= 5
    # Every run terminated cleanly (no crash).
    assert metrics["completion_rate"] == 1.0

    # --- agentic-RAG (Phase 6) ---
    # Retrieval happened for every case that needed external evidence …
    assert metrics["required_retrieval_recall"] == 1.0
    # … and never for a case that did not.
    assert metrics["unnecessary_retrieval_rate"] == 0.0
    # Citations only ever came from an actual retrieval with sources.
    assert metrics["citation_validity"] == 1.0
    # The retrieval_used flag always matched an executed retrieval tool.
    assert metrics["retrieval_sequence_validity"] == 1.0


def test_release_gates_pass_on_held_out_dataset():
    # The deterministic release gates (src/agent/eval.GATES) must pass — this is the
    # same check scripts/eval_agent.py enforces in CI.
    metrics = evaluate(load_cases(), build_eval_career())
    assert gate_failures(metrics) == []


def test_hitl_and_isolation_probe_invariants():
    probe = hitl_and_isolation_probe()
    assert probe["hitl_trigger_recall"] == 1.0          # ambiguous role paused for a human
    assert probe["cross_user_access_failures"] == 0     # no cross-user leak
