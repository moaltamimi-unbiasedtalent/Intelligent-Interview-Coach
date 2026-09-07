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

Phase 6 (Agentic RAG) adds a fifth tool, ``SearchCareerKnowledge``, a thin adapter
over the RETRIEVAL-ONLY operation (``CareerApplicationService.search_knowledge`` →
``CareerIntelligenceService.retrieve_evidence``). The AGENT decides *whether* to
retrieve; the existing DETERMINISTIC router still decides *which* lanes/sources are
queried — the model never sees low-level stores. The tool runs retrieval ONLY: it
does not execute the other Career tools and does not perform final answer synthesis
(the LangGraph agent owns those decisions), so it returns evidence + citations, not
a synthesized answer.
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


# --- 5. Career knowledge retrieval (Agentic RAG, Phase 6) -------------------


class SearchCareerKnowledge(BaseModel):
    """Search trusted career and labour-market knowledge when the request needs
    factual external evidence about occupations, competencies, compensation, labour
    markets, credentials or established role expectations. Do NOT use it when the
    answer comes from information the user already provided or from an existing
    Career tool result (e.g. rewriting text, or building a plan from known gaps)."""

    query: str = Field(max_length=4000, description="What to look up in career knowledge.")


_MAX_EVIDENCE = 6


def _search_career_knowledge(career_service) -> Handler:
    def handler(args: SearchCareerKnowledge, ctx: ToolContext) -> ToolOutcome:
        query = (args.query or "").strip()
        _require(query, "A search query is required.")

        # Duplicate-retrieval protection: same query within a run reuses evidence.
        # Cache identity is the normalized QUERY alone, and that is correct AND
        # complete: retrieval depends only on the query — the deterministic pipeline
        # derives geography (detect_country), occupation and lane (route_question)
        # from the query text, and job_description/candidate_background do NOT
        # influence which lanes/sources are retrieved. A different question produces
        # a different query and is retrieved afresh (see the retrieval tests).
        if ctx.last_retrieval_query and query.lower() == ctx.last_retrieval_query.lower() and ctx.evidence is not None:
            return ToolOutcome(
                result={"has_evidence": bool(ctx.evidence), "sources": ctx.evidence,
                        "citations": ctx.citations or [], "reused": True,
                        "insufficient_evidence": not ctx.evidence},
                state_patch={},
                summary=f"reused prior retrieval ({len(ctx.evidence)} sources)",
                source_count=len(ctx.evidence),
            )

        # Delegate to the RETRIEVAL-ONLY operation (deterministic router, hybrid +
        # structured retrieval, geographic precedence, evidence, citations,
        # security). It executes NO other Career tools and NO answer synthesis — the
        # agent, not this tool, decides what to do with the retrieved evidence.
        from src.application.errors import ApplicationError
        from src.application.models import KnowledgeSearchRequest

        try:
            result = career_service.search_knowledge(KnowledgeSearchRequest(
                query=query,
                job_description=ctx.job_description,
                candidate_background=ctx.candidate_background,
            ))
        except ApplicationError as exc:
            raise AgentToolError("Career knowledge is temporarily unavailable.") from exc
        except Exception as exc:  # noqa: BLE001 - never leak a raw retrieval/provider error
            raise AgentToolError("Career knowledge could not be searched.") from exc

        # A blocked retrieval (the query itself tripped the injection guard) is safe
        # DATA for the agent, not a tool crash.
        if getattr(result, "blocked", False):
            observation = {
                "has_evidence": False, "insufficient_evidence": True,
                "sources": [], "citations": [],
                "note": "The request could not be searched safely.",
            }
            return ToolOutcome(
                result=observation,
                state_patch={"retrieval_used": True, "last_retrieval_query": query,
                             "evidence": [], "citations": []},
                summary="blocked=true, sources=0",
                source_count=0,
            )

        sources = [
            {
                "title": e.source_title,
                "source_url": e.source_url,
                "evidence_type": e.evidence_type,
                "geography": e.geography,
                "occupation_title": e.occupation_title,
                "reference_year": e.reference_year,
            }
            for e in (result.evidence or [])[:_MAX_EVIDENCE]
        ]
        citations = [
            {"marker": c.marker, "title": c.title, "source": c.source, "page": c.page}
            for c in (result.citations or [])
        ]
        has_evidence = bool(sources or citations)
        # NOTE: no synthesized answer here — retrieval returns evidence only; the
        # LangGraph agent decides how to use/explain it.
        observation = {
            "has_evidence": has_evidence,
            "insufficient_evidence": bool(getattr(result, "insufficient_evidence", not has_evidence)),
            "sources": sources,
            "citations": citations,
        }
        if getattr(result, "clarify", None):
            observation["clarify"] = result.clarify
        patch = {
            "evidence": sources,
            "citations": citations,
            "retrieval_used": True,
            "last_retrieval_query": query,
            "resolved_occupation": getattr(result, "resolved_occupation", None) or None,
            "resolved_geography": getattr(result, "resolved_geography", None),
        }
        return ToolOutcome(
            result=observation,
            state_patch=patch,
            summary=f"lane={getattr(result, 'retrieval_lane', None)}, strategy={getattr(result, 'retrieval_strategy', None)}, sources={len(sources)}",
            source_count=len(sources),
        )

    return handler


def build_career_tools(career_service) -> list[tuple[type[BaseModel], Handler]]:
    """The five real Career tools, bound to a CareerApplicationService."""
    return [
        (AnalyzeJobDescription, _analyze_job_description(career_service)),
        (AnalyzeCandidateGaps, _analyze_candidate_gaps(career_service)),
        (BuildPreparationPlan, _build_preparation_plan(career_service)),
        (GenerateInterviewQuestions, _generate_interview_questions(career_service)),
        (SearchCareerKnowledge, _search_career_knowledge(career_service)),
    ]
