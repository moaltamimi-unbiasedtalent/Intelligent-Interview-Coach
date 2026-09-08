"""Shared builders for interview domain objects used by Phase 10 durability tests.

No provider calls, no disk. Mirrors the small builders in test_session_manager so
durable-store/codec tests can construct realistic SessionData without a real model.
"""

from __future__ import annotations

import os
import tempfile

from src import constants
from src.models import (
    AnswerEvaluation,
    BranchQuestion,
    ExternalServiceUsage,
    FinalInterviewReport,
    InterviewConfiguration,
    InterviewQuestion,
    InterviewStrategy,
    ModelSettings,
    UsageRecord,
)


def config(number_of_questions: int = 2) -> InterviewConfiguration:
    return InterviewConfiguration(
        target_role="Registered Nurse",
        industry_or_sector="healthcare",
        career_level="senior",
        interview_types=["behavioural"],
        interviewer_persona="neutral",
        difficulty="moderate",
        response_detail="standard",
        number_of_questions=number_of_questions,
    )


def settings() -> ModelSettings:
    return ModelSettings(model="openai/gpt-5-mini", prompt_technique="rubric_json")


def strategy() -> InterviewStrategy:
    section = ["item"]
    return InterviewStrategy(
        role_summary="A summary.",
        likely_interview_stages=section,
        critical_competencies=section,
        likely_question_themes=section,
        probable_challenges=section,
        evidence_to_prepare=section,
        technical_or_functional_topics=section,
        behavioural_topics=section,
        questions_for_interviewer=section,
        preparation_priorities=section,
    )


def question(qid: int = 1) -> InterviewQuestion:
    return InterviewQuestion(
        question_id=qid,
        question=f"Question {qid}?",
        question_type="behavioural",
        competency="teamwork",
        difficulty="moderate",
        interviewer_intent="Assess collaboration.",
        expected_answer_elements=["situation", "action", "result"],
    )


def evaluation(score: int = 70) -> AnswerEvaluation:
    return AnswerEvaluation(
        overall_score=score,
        relevance=7,
        structure=7,
        evidence=6,
        role_knowledge=7,
        problem_solving=7,
        communication=7,
        credibility=7,
        strengths=["clear"],
        improvement_areas=["add detail"],
        missing_evidence=["metrics"],
        stronger_answer_structure="STAR",
        improved_example_answer="Example.",
        follow_up_question="What changed?",
    )


def report() -> FinalInterviewReport:
    section = ["item"]
    return FinalInterviewReport(
        overall_readiness_score=68,
        performance_summary="Solid overall.",
        strongest_competencies=section,
        development_priorities=section,
        recurring_answer_patterns=section,
        highest_risk_questions=section,
        evidence_gaps=section,
        recommended_practice_actions=section,
        final_interview_checklist=section,
    )


def usage(reported: float | None = 0.001, calculated: float = 0.0) -> UsageRecord:
    return UsageRecord(
        model="openai/gpt-5-mini",
        prompt_tokens=100,
        completion_tokens=50,
        total_tokens=150,
        reported_cost=reported,
        calculated_cost=calculated,
        cost_source="reported" if reported is not None else "calculated",
        request_duration_seconds=0.5,
    )


def external_usage() -> ExternalServiceUsage:
    return ExternalServiceUsage(
        provider="whisper",
        operation="speech_to_text",
        units=12.5,
        unit_name="audio_seconds",
        cost_usd=0.002,
        cost_source="reported",
    )


def make_durable_store():
    """A DurableInterviewSessionStore over an isolated temp SQLite DB (one per call).

    Used by API tests to exercise the durable path without touching the dev DB. Keep
    ONE instance per test and reuse it (state lives in the DB, not the object).
    """
    from src.interview.session_repository import DurableInterviewSessionStore
    from src.persistence import init_db, make_engine, make_session_factory

    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    engine = make_engine(f"sqlite:///{path}")
    init_db(engine, force=True)
    return DurableInterviewSessionStore(make_session_factory(engine))


def branch_question(qid: int = 1, depth: int = 1, parent_id: int = 1) -> BranchQuestion:
    return BranchQuestion(
        branch_id=f"branch-{parent_id}-1-q{qid}",
        parent_question_id=parent_id,
        question=f"Deeper question {qid}?",
        branch_mode=constants.DEFAULT_BRANCH_MODE,
        focus_area="reasoning",
        interviewer_intent="Probe the reasoning behind the answer.",
        expected_answer_elements=["assumption", "evidence"],
        difficulty="moderate",
        depth=depth,
    )
