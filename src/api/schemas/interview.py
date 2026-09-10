"""Interview API schemas over InterviewApplicationService + the session state.

The interview state machine is unchanged; these schemas describe it over HTTP. A
session is created from either an explicit ``configuration`` or a
``preparation_context`` handoff (role precedence preserved, no extra LLM call).
Evaluations and the final report are safe candidate-facing feedback, returned as
already-validated domain dicts.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class InterviewConfigIn(BaseModel):
    target_role: str = Field(min_length=1, max_length=200)
    industry_or_sector: str = Field(min_length=1, max_length=200)
    career_level: str = Field(min_length=1, max_length=100)
    interview_types: list[str] = Field(default_factory=lambda: ["behavioural"])
    interviewer_persona: str = "neutral"
    difficulty: str = "moderate"
    response_detail: str = "standard"
    number_of_questions: int | None = Field(default=None, ge=1, le=20)
    company_context: str | None = Field(default=None, max_length=4000)
    job_description: str | None = Field(default=None, max_length=12000)
    candidate_background: str | None = Field(default=None, max_length=12000)


class PreparationContextIn(BaseModel):
    """The typed handoff contract, mirrored for the API (see PreparationContext)."""

    target_role: str = Field(min_length=1, max_length=200)
    industry: str | None = Field(default=None, max_length=200)
    company_context: str | None = Field(default=None, max_length=4000)
    job_description: str | None = Field(default=None, max_length=12000)
    seniority: str | None = Field(default=None, max_length=100)
    required_skills: list[str] = Field(default_factory=list)
    key_responsibilities: list[str] = Field(default_factory=list)
    leadership_expectations: list[str] = Field(default_factory=list)
    candidate_strengths: list[str] = Field(default_factory=list)
    candidate_gaps: list[str] = Field(default_factory=list)
    likely_interview_topics: list[str] = Field(default_factory=list)
    priority_competencies: list[str] = Field(default_factory=list)


class CreateInterviewRequest(BaseModel):
    """Create from an explicit configuration OR a preparation-context handoff.

    When ``preparation_context`` is provided, role/industry/level/JD/background are
    derived from it (role precedence preserved); the interview-style fields below
    still apply (with defaults).
    """

    configuration: InterviewConfigIn | None = None
    preparation_context: PreparationContextIn | None = None
    # Interview-style fields + gap-fillers for the preparation-context path
    # (required config fields the context may not carry — never fabricated).
    industry_or_sector: str | None = Field(default=None, max_length=200)
    career_level: str | None = Field(default=None, max_length=100)
    interview_types: list[str] = Field(default_factory=lambda: ["behavioural"])
    interviewer_persona: str = "neutral"
    difficulty: str = "moderate"
    response_detail: str = "standard"
    number_of_questions: int | None = Field(default=None, ge=1, le=20)


class QuestionOut(BaseModel):
    question_id: int
    question: str
    question_type: str
    competency: str
    difficulty: str


class EvaluationOut(BaseModel):
    """Candidate-safe, typed answer feedback (mirrors AnswerEvaluation exactly — no
    invented fields). Practice feedback only; never a hiring decision."""

    overall_score: int
    relevance: int
    structure: int
    evidence: int
    role_knowledge: int
    problem_solving: int
    communication: int
    credibility: int
    strengths: list[str] = Field(default_factory=list)
    improvement_areas: list[str] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    stronger_answer_structure: str = ""
    improved_example_answer: str = ""
    follow_up_question: str = ""


class BranchQuestionOut(BaseModel):
    """Candidate-safe view of the current Deep Dive branch question."""

    branch_id: str
    parent_question_id: int
    question: str
    branch_mode: str
    focus_area: str
    difficulty: str
    depth: int


class DeepDiveStateOut(BaseModel):
    """Candidate-safe Deep Dive (branch) state — never raw archived structures."""

    active: bool = False
    mode: str | None = None
    depth: int = 0
    max_depth: int = 0
    parent_question_id: int | None = None
    current_branch_question: BranchQuestionOut | None = None
    last_branch_evaluation: EvaluationOut | None = None
    can_go_deeper: bool = False


class InterviewStateResponse(BaseModel):
    session_id: str
    state: str
    question_number: int
    questions_planned: int | None = None
    current_question: QuestionOut | None = None
    report_available: bool = False
    last_evaluation: EvaluationOut | None = None
    # Sprint 4 Phase 3C: the resolved target role, so the frontend Practice page can
    # show the session's role/context. Additive + optional (backward-compatible).
    target_role: str | None = None
    # Sprint 4 Phase 10 additive, candidate-safe fields.
    deep_dive: DeepDiveStateOut | None = None
    error: str | None = None
    error_recoverable: bool = False
    # Cumulative practice cost (USD) if the product chooses to display it; never a
    # provider key, DB id, raw payload or operation token.
    cumulative_cost_usd: float | None = None


class ActiveSessionSummary(BaseModel):
    """Safe summary for resumable-session discovery (never JD/background/answers)."""

    session_id: str
    target_role: str | None = None
    state: str
    question_number: int = 0
    questions_planned: int | None = None
    updated_at: str | None = None


class ActiveSessionsResponse(BaseModel):
    sessions: list[ActiveSessionSummary] = Field(default_factory=list)


class AnswerRequest(BaseModel):
    answer: str = Field(min_length=1, max_length=20000)


class DeepDiveRequest(BaseModel):
    mode: str = Field(min_length=1, max_length=64)


class ReportResponse(BaseModel):
    session_id: str
    report: dict
    saved_report_id: int | None = None
    save_failed: bool = False


class InterviewOptionsResponse(BaseModel):
    """Safe interview-configuration taxonomies (the single source of truth for a
    frontend completion form; never a duplicated client-side list)."""

    career_levels: list[str] = Field(default_factory=list)
    interview_types: list[str] = Field(default_factory=list)
    # Backend-owned difficulty taxonomy so the frontend never maintains its own list.
    difficulty_levels: list[str] = Field(default_factory=list)
    # Backend-owned Deep Dive taxonomy so the frontend never maintains its own list.
    deep_dive_modes: list[str] = Field(default_factory=list)
