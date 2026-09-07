"""Real Career agent tools — THIN adapters over the existing capabilities.

Each tool wraps a ``CareerApplicationService`` method (which owns the existing
Career business logic and security guards); no Career logic, prompts, calculations
or validation are duplicated here. Tools enforce prerequisites from prior steps via
:class:`ToolContext` and never fabricate missing inputs.

Tool → implementation → nature:
- AnalyzeJobDescription  → career_service.analyze_job_description  → LLM-backed
- AnalyzeCandidateGaps   → career_service.analyze_candidate_gaps   → deterministic
- BuildPreparationPlan   → career_service.build_preparation_plan   → deterministic
- GenerateInterviewQuestions → career_service.generate_questions   → LLM-backed

The Pydantic arg-model CLASS NAME is the tool name the model calls (and the
registry key), keeping bind_tools and the allowlist in sync.

NOTE: career retrieval is intentionally NOT an agent tool — that is Phase 6
(Agentic RAG).
"""

from __future__ import annotations

from typing import Any, Callable

from pydantic import BaseModel, Field

from src.agent.errors import AgentToolError
from src.agent.tooling import ToolContext, ToolOutcome

Handler = Callable[[BaseModel, ToolContext], ToolOutcome]


def _require(value: Any, message: str) -> Any:
    if not value:
        raise AgentToolError(message)
    return value


def _ok(call) -> Any:
    if not getattr(call, "ok", False) or call.value is None:
        raise AgentToolError("The tool could not produce a valid result.")
    return call.value


# --- 1. Job Description Analyzer (LLM-backed) --------------------------------


class AnalyzeJobDescription(BaseModel):
    """Analyse a job description into structured role requirements and interview
    themes. Use when the user provides a job description or asks what a specific job
    requires."""

    job_description: str | None = Field(default=None, max_length=12000, description="The job description text (optional if already provided).")


def _analyze_job_description(career_service) -> Handler:
    def handler(args: AnalyzeJobDescription, ctx: ToolContext) -> ToolOutcome:
        jd = (args.job_description or ctx.job_description or "").strip()
        _require(jd, "A job description is required to analyse the role.")
        role = _ok(career_service.analyze_job_description(jd))
        data = role.model_dump()
        return ToolOutcome(
            result=data,
            state_patch={"requirements": data, "target_role": role.role_title or ctx.target_role, "job_description": jd},
            summary=f"role={role.role_title or 'n/a'}, seniority={role.seniority or 'n/a'}",
            source_count=len(role.required_skills or []),
        )

    return handler


# --- 2. Candidate Gap Analyzer (deterministic) ------------------------------


class AnalyzeCandidateGaps(BaseModel):
    """Compare structured candidate evidence with the role requirements from a
    prior job-description analysis. Use only after a job description has been
    analysed and the candidate's background is available."""

    candidate_background: str | None = Field(default=None, max_length=12000, description="A few lines about the candidate's experience (optional if already provided).")


def _analyze_candidate_gaps(career_service) -> Handler:
    def handler(args: AnalyzeCandidateGaps, ctx: ToolContext) -> ToolOutcome:
        _require(ctx.requirements, "Analyse a job description first so requirements exist.")
        bg = (args.candidate_background or ctx.candidate_background or "").strip()
        _require(bg, "The candidate's background is required to compare gaps.")
        from src.copilot.tools.schemas import RoleRequirements

        role = RoleRequirements(**ctx.requirements)
        gaps = _ok(career_service.analyze_candidate_gaps(bg, role))
        data = gaps.model_dump()
        return ToolOutcome(
            result=data,
            state_patch={"gaps": data, "candidate_background": bg},
            summary=f"match={gaps.stats.match_percentage}%, priorities={len(gaps.priority_gaps or [])}",
            source_count=len(gaps.priority_gaps or []),
        )

    return handler


# --- 3. Preparation Plan Calculator (deterministic) -------------------------


class BuildPreparationPlan(BaseModel):
    """Create a deterministic preparation plan from the priority gaps found by a
    prior gap analysis, the days until the interview and the weekly hours available.
    Use after a gap analysis."""

    days_until_interview: int = Field(ge=1, le=365, description="Days until the interview.")
    hours_per_week: float = Field(gt=0, le=80, description="Hours available to prepare each week.")


def _build_preparation_plan(career_service) -> Handler:
    def handler(args: BuildPreparationPlan, ctx: ToolContext) -> ToolOutcome:
        priority = (ctx.gaps or {}).get("priority_gaps") if ctx.gaps else None
        _require(priority, "Run a gap analysis first to identify priority gaps.")
        from src.copilot.tools.schemas import PriorityGap

        pgs = [PriorityGap(**g) for g in priority]
        plan = _ok(career_service.build_preparation_plan(pgs, args.days_until_interview, args.hours_per_week))
        data = plan.model_dump()
        return ToolOutcome(
            result=data,
            state_patch={"preparation_plan": data},
            summary=f"total_hours={plan.total_available_hours}, allocations={len(plan.allocations or [])}",
            source_count=len(plan.allocations or []),
        )

    return handler


# --- 4. Interview Question Generator (LLM-backed) ---------------------------


class GenerateInterviewQuestions(BaseModel):
    """Generate interview questions grounded in the known role requirements and
    preparation context. Use when the user asks for practice questions."""

    focus: list[str] = Field(default_factory=list, description="Optional focus categories.")


def _generate_interview_questions(career_service) -> Handler:
    def handler(args: GenerateInterviewQuestions, ctx: ToolContext) -> ToolOutcome:
        role = (ctx.target_role or (ctx.requirements or {}).get("role_title") or "").strip()
        _require(role, "A target role is required — analyse a job description or name the role.")
        reqs: list[str] = []
        if ctx.requirements:
            reqs = list(ctx.requirements.get("required_skills") or []) + list(ctx.requirements.get("technologies") or [])
        qset = _ok(career_service.generate_questions(role, reqs, list(args.focus or [])))
        data = qset.model_dump()
        count = sum(len(c.questions) for c in qset.categories)
        return ToolOutcome(
            result=data,
            state_patch={"questions": data},
            summary=f"questions={count}, categories={len(qset.categories)}",
            source_count=count,
        )

    return handler


def build_career_tools(career_service) -> list[tuple[type[BaseModel], Handler]]:
    """The four real Career tools, bound to a CareerApplicationService."""
    return [
        (AnalyzeJobDescription, _analyze_job_description(career_service)),
        (AnalyzeCandidateGaps, _analyze_candidate_gaps(career_service)),
        (BuildPreparationPlan, _build_preparation_plan(career_service)),
        (GenerateInterviewQuestions, _generate_interview_questions(career_service)),
    ]
