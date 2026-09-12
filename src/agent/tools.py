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

from src.agent.errors import (
    TOOL_FAILURE_EXECUTION_FAILED,
    TOOL_FAILURE_INVALID_ARGUMENTS,
    TOOL_FAILURE_MISSING_PREREQUISITE,
    AgentToolError,
)
from src.agent.human import (
    approve_handoff_action,
    approve_memory_action,
    confirm_role_action,
)
from src.agent.tooling import ToolContext, ToolOutcome

Handler = Callable[[BaseModel, ToolContext], ToolOutcome]


def _require(value: Any, message: str) -> Any:
    # A missing required input/prior result is a prerequisite failure, not a crash.
    if not value:
        raise AgentToolError(message, category=TOOL_FAILURE_MISSING_PREREQUISITE)
    return value


def _ok(call) -> Any:
    if not getattr(call, "ok", False) or call.value is None:
        raise AgentToolError("The tool could not produce a valid result.",
                             category=TOOL_FAILURE_EXECUTION_FAILED)
    return call.value


# --- 1. Job Description Analyzer (LLM-backed) --------------------------------


class AnalyzeJobDescription(BaseModel):
    """Analyse a job description into structured role requirements and interview
    themes. Use when the user provides a job description or asks what a specific job
    requires."""

    job_description: str | None = Field(default=None, max_length=12000, description="The job description text (optional if already provided).")


def _analyze_job_description(career_service) -> Handler:
    def handler(args: AnalyzeJobDescription, ctx: ToolContext) -> ToolOutcome:
        from src.agent.usage import capture_tool_usage

        jd = (args.job_description or ctx.job_description or "").strip()
        _require(jd, "A job description is required to analyse the role.")
        # Capture this model-backed tool's provider usage at the agent boundary (the
        # usage callback auto-hooks the nested structured-output call); no Sprint-3 change.
        call, usage = capture_tool_usage(
            "AnalyzeJobDescription", lambda: career_service.analyze_job_description(jd))
        role = _ok(call)
        data = role.model_dump()
        return ToolOutcome(
            result=data,
            state_patch={"requirements": data, "target_role": role.role_title or ctx.target_role, "job_description": jd},
            summary=f"role={role.role_title or 'n/a'}, seniority={role.seniority or 'n/a'}",
            source_count=len(role.required_skills or []),
            usage=usage,
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
    preparation context. Use when the user asks for practice questions.

    Role handling: prefer the role already established in this conversation's
    structured state (a confirmed role, an analysed job description). Only when the
    candidate has EXPLICITLY named a target role in the conversation AND no structured
    role is known yet, pass that role in ``target_role``. Never invent a role the
    candidate did not state."""

    focus: list[str] = Field(default_factory=list, description="Optional focus categories.")
    target_role: str | None = Field(
        default=None,
        max_length=200,
        description="The target role to generate questions for — supply ONLY when the "
        "candidate explicitly named it in the conversation and no structured role is "
        "known yet. Leave empty if the role is already established. Never invent a role.",
    )


def _generate_interview_questions(career_service) -> Handler:
    def handler(args: GenerateInterviewQuestions, ctx: ToolContext) -> ToolOutcome:
        # Conservative role precedence: a role the user CONFIRMED (HITL) or that is
        # already in structured state always wins over a role the model supplied from
        # conversation, so the question tool never silently overrides an established
        # role. The model-supplied ``target_role`` is a fallback ONLY when no
        # structured role exists (e.g. the role was named in conversation but no job
        # description was analysed and no target_role was set on the run).
        structured_role = (
            (ctx.confirmed_target_role or "").strip()
            or (ctx.target_role or "").strip()
            or ((ctx.requirements or {}).get("role_title") or "").strip()
        )
        arg_role = (args.target_role or "").strip()
        role = structured_role or arg_role
        _require(role, "A target role is required — analyse a job description or name the role.")
        reqs: list[str] = []
        if ctx.requirements:
            reqs = list(ctx.requirements.get("required_skills") or []) + list(ctx.requirements.get("technologies") or [])
        from src.agent.usage import capture_tool_usage

        call, usage = capture_tool_usage(
            "GenerateInterviewQuestions",
            lambda: career_service.generate_questions(role, reqs, list(args.focus or [])))
        qset = _ok(call)
        data = qset.model_dump()
        count = sum(len(c.questions) for c in qset.categories)
        patch: dict[str, Any] = {"questions": data}
        # Persist a fallback role into state ONLY when it came from the model argument
        # because structured role state was absent — so later turns retain the
        # now-known role. Never overwrite an existing/confirmed structured role.
        if arg_role and not structured_role:
            patch["target_role"] = arg_role
        return ToolOutcome(
            result=data,
            state_patch=patch,
            summary=f"questions={count}, categories={len(qset.categories)}",
            source_count=count,
            usage=usage,
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
# Bounded per-thread retrieval cache: at most this many distinct queries are kept
# (FIFO eviction), so process memory stays bounded over a long conversation (§30).
_RETRIEVAL_CACHE_MAX = 8


def _normalise_query(query: str) -> str:
    """The structured cache key for a retrieval query.

    Case- and whitespace-normalised query text. The normalised query is the COMPLETE
    key material: the deterministic pipeline derives geography (detect_country),
    occupation and lane (route_question) from the query text itself, so a different
    country / role / seniority / recency in the request produces different query text
    → a different key → a cache miss (Germany→France, PM→EM, mid→senior, 2025→current
    all re-retrieve). Job description / candidate background never influence which
    lanes or sources are retrieved, so they are correctly absent from the key.
    """
    return " ".join((query or "").lower().split())


def _search_career_knowledge(career_service) -> Handler:
    def handler(args: SearchCareerKnowledge, ctx: ToolContext) -> ToolOutcome:
        query = (args.query or "").strip()
        _require(query, "A search query is required.")

        # Duplicate-retrieval protection (§28): an equivalent factual request already
        # answered in THIS thread reuses the cached evidence instead of paying for the
        # deterministic pipeline again. The cache is bounded and thread-scoped (never
        # shared across users or runs). A materially different question (different
        # country/role/seniority/recency) has different query text ⇒ a different key ⇒
        # a miss (see _normalise_query).
        key = _normalise_query(query)
        cache = list(ctx.retrieval_cache or [])
        hit = next((e for e in cache if e.get("key") == key), None)
        if hit is not None:
            ev = list(hit.get("evidence") or [])
            cit = list(hit.get("citations") or [])
            return ToolOutcome(
                result={"has_evidence": bool(ev), "sources": ev, "citations": cit,
                        "reused": True, "insufficient_evidence": hit.get("insufficient", not ev)},
                state_patch={"retrieval_used": True, "last_retrieval_query": query,
                             "evidence": ev, "citations": cit,
                             "resolved_occupation": hit.get("resolved_occupation"),
                             "resolved_geography": hit.get("resolved_geography")},
                summary=f"reused prior retrieval ({len(ev)} sources)",
                source_count=len(ev),
                cache="hit",
            )

        # Delegate to the RETRIEVAL-ONLY operation (deterministic router, hybrid +
        # structured retrieval, geographic precedence, evidence, citations,
        # security). It executes NO other Career tools and NO answer synthesis — the
        # agent, not this tool, decides what to do with the retrieved evidence.
        from src.agent.usage import capture_tool_usage
        from src.application.errors import ApplicationError
        from src.application.models import KnowledgeSearchRequest

        retrieval_usage = None
        try:
            # Retrieval routing is deterministic; capture usage ONLY if a real model
            # call actually happens inside it (e.g. query translation) — never fabricate.
            result, retrieval_usage = capture_tool_usage(
                "SearchCareerKnowledge",
                lambda: career_service.search_knowledge(KnowledgeSearchRequest(
                    query=query,
                    job_description=ctx.job_description,
                    candidate_background=ctx.candidate_background,
                )))
        except ApplicationError as exc:
            raise AgentToolError("Career knowledge is temporarily unavailable.",
                                 category=TOOL_FAILURE_EXECUTION_FAILED) from exc
        except Exception as exc:  # noqa: BLE001 - never leak a raw retrieval/provider error
            raise AgentToolError("Career knowledge could not be searched.",
                                 category=TOOL_FAILURE_EXECUTION_FAILED) from exc

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
                usage=retrieval_usage,
                cache="miss",  # the pipeline was invoked; nothing cacheable is stored
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
        patch = {
            "evidence": sources,
            "citations": citations,
            "retrieval_used": True,
            "last_retrieval_query": query,
            "resolved_occupation": getattr(result, "resolved_occupation", None) or None,
            "resolved_geography": getattr(result, "resolved_geography", None),
        }
        # Agentic HITL (Phase 8): when the DETERMINISTIC pipeline reports an ambiguous
        # occupation, don't guess — pause for the user to confirm the role. The
        # candidates come from the pipeline trace (public occupation titles).
        candidates = list(getattr(getattr(result, "trace", None), "occupation_candidates", []) or [])
        clarifying = bool(getattr(result, "clarify", None)) and len(candidates) > 1 and not ctx.confirmed_target_role
        if clarifying:
            observation["clarify"] = result.clarify
            patch["pending_action"] = confirm_role_action(candidates)
        else:
            # Store the resolved evidence in the bounded thread cache so an equivalent
            # request later in the thread is served without a second pipeline call. We
            # do NOT cache an ambiguous (clarify) result — it is not yet resolved. Only
            # safe, already-bounded evidence/citations are stored (never keys are logged).
            entry = {
                "key": key,
                "evidence": sources,
                "citations": citations,
                "resolved_occupation": patch["resolved_occupation"],
                "resolved_geography": patch["resolved_geography"],
                "insufficient": observation["insufficient_evidence"],
            }
            patch["retrieval_cache"] = (cache + [entry])[-_RETRIEVAL_CACHE_MAX:]
        return ToolOutcome(
            result=observation,
            state_patch=patch,
            summary=f"lane={getattr(result, 'retrieval_lane', None)}, strategy={getattr(result, 'retrieval_strategy', None)}, sources={len(sources)}",
            source_count=len(sources),
            usage=retrieval_usage,
            cache="miss",
        )

    return handler


# --- 6. Propose preparation memory (HITL action tool, Phase 8) ---------------


class ProposePreparationMemory(BaseModel):
    """Propose ONE concise, genuinely reusable preparation fact for the user to
    approve saving (a recurring gap, strength, completed topic, preference, goal or
    target role). This does NOT save anything — it asks the user for approval. Use it
    sparingly, never for ordinary facts, whole analyses, job descriptions or chatter."""

    category: str = Field(description="One of the fixed preparation-memory categories.")
    summary: str = Field(max_length=500, description="A concise fact to remember (not a transcript/JD/CV).")
    target_role: str | None = Field(default=None, max_length=200, description="Optional role this relates to.")


def _propose_preparation_memory(career_service) -> Handler:
    def handler(args: ProposePreparationMemory, ctx: ToolContext) -> ToolOutcome:
        from src.memory import MemoryCategory

        try:
            category = MemoryCategory.from_value(args.category).value
        except ValueError as exc:
            raise AgentToolError("That memory category is not allowed.",
                                 category=TOOL_FAILURE_INVALID_ARGUMENTS) from exc
        summary = (args.summary or "").strip()
        _require(summary, "A memory summary is required to propose it.")
        role = (args.target_role or "").strip() or None
        # Propose ONLY — no persistence here. The human-review node persists on approval.
        candidate = {"category": category, "summary": summary, "target_role": role}
        return ToolOutcome(
            result={"proposed": True, "awaiting_approval": True, **candidate},
            state_patch={
                "memory_candidate": candidate,
                "pending_action": approve_memory_action(
                    category=category, summary=summary, target_role=role),
            },
            summary=f"proposed memory: category={category}",
            source_count=0,
        )

    return handler


# --- 7. Request Interview Practice handoff (HITL action tool, Phase 8) -------


class RequestPracticeHandoff(BaseModel):
    """Ask the user to approve moving from preparation into Interview Practice. Use
    only once a preparation plan / requirements exist. This does NOT start an
    interview — it requests approval; the existing interview endpoint creates the
    session afterwards."""

    ready: bool = Field(default=True, description="Set true when preparation is ready to practise.")


def _request_practice_handoff(career_service) -> Handler:
    def handler(args: RequestPracticeHandoff, ctx: ToolContext) -> ToolOutcome:
        requirements = ctx.requirements or {}
        role = (ctx.target_role or requirements.get("role_title") or "").strip()
        _require(role, "A target role and a preparation plan are needed before a handoff.")
        priorities = (ctx.gaps or {}).get("priority_gaps") if ctx.gaps else None
        priority_count = len(priorities or [])
        return ToolOutcome(
            result={"handoff_requested": True, "awaiting_approval": True, "target_role": role},
            state_patch={
                "pending_action": approve_handoff_action(
                    target_role=role, priority_count=priority_count),
            },
            summary=f"handoff requested: priorities={priority_count}",
            source_count=0,
        )

    return handler


class ResearchCurrentMarket(BaseModel):
    """Retrieve bounded, CURRENT job-market or explicit company-site evidence when the answer
    depends on recent information not reliably available in local career knowledge — current
    openings, live advertised salary, whether a company is hiring, or what a company's own public
    page (given its URL) says. Uses ONLY approved market APIs and validated official/company
    public URLs. Prefer SearchCareerKnowledge for occupation facts, skills, responsibilities,
    education and official historical/statistical compensation; use this ONLY for time-sensitive
    or company-specific needs."""

    intent: str = Field(description="One of: job_market, advertised_salary, current_vacancies, "
                        "company_context, hiring_activity.")
    role: str | None = Field(default=None, max_length=120, description="Occupation/role, if any.")
    location_country: str | None = Field(default=None, max_length=40,
                                         description="Country name or ISO-2 (e.g. Germany/DE).")
    location_city: str | None = Field(default=None, max_length=80)
    company: str | None = Field(default=None, max_length=120)
    company_url: str | None = Field(default=None, max_length=500,
                                    description="Explicit public company URL (company_context only).")
    industry: str | None = Field(default=None, max_length=120)
    results_limit: int = Field(default=10, ge=1, le=25)


_COUNTRY_ALIASES = {"germany": "DE", "deutschland": "DE", "united states": "US", "usa": "US",
                    "united kingdom": "UK", "uk": "UK", "great britain": "UK"}
_MARKET_EVIDENCE_MAX = 6


def _research_current_market(research_service) -> Handler:
    def handler(args: ResearchCurrentMarket, ctx: ToolContext) -> ToolOutcome:
        from src.copilot.research.models import (
            CurrentMarketResearchRequest, Geography, ResearchIntent, ResearchStatus)

        try:
            intent = ResearchIntent(args.intent.strip().lower())
        except ValueError:
            raise AgentToolError(
                "intent must be one of: job_market, advertised_salary, current_vacancies, "
                "company_context, hiring_activity.", category=TOOL_FAILURE_INVALID_ARGUMENTS) from None

        country = (args.location_country or "").strip()
        country = _COUNTRY_ALIASES.get(country.lower(), country.upper() if len(country) == 2 else country)
        geo = Geography(country=country or None, city=(args.location_city or None)) \
            if (country or args.location_city) else None
        request = CurrentMarketResearchRequest(
            intent=intent, role=(args.role or None), location=geo,
            company=(args.company or None), company_url=(args.company_url or None),
            industry=(args.industry or None), results_limit=args.results_limit)

        try:
            result = research_service.research(request)
        except Exception as exc:  # noqa: BLE001 - never leak a raw provider/network error
            raise AgentToolError("Current-market research is temporarily unavailable.",
                                 category=TOOL_FAILURE_EXECUTION_FAILED) from exc

        # Compact, safe evidence for the model (no raw payloads); labelled by source type.
        ev_dicts = []
        for e in result.evidence[:_MARKET_EVIDENCE_MAX]:
            ev_dicts.append({
                "title": e.title, "source_url": e.public_url,
                "evidence_type": _EVIDENCE_TYPE_OF.get(e.source_type.value, "current_market"),
                "geography": e.country or (e.region or None),
                "occupation_title": e.role, "reference_year": None,
                "provider": e.provider, "company": e.company,
                "advertised_salary": (e.advertised_salary.model_dump() if e.advertised_salary else None),
                "self_reported": bool(e.metadata.get("self_reported")),
            })
        observation = {
            "status": result.status.value, "intent": intent.value, "provider": result.provider,
            "source_category": (result.source_category.value if result.source_category else None),
            "result_count": result.result_count,
            "provider_reported_total": result.provider_reported_total,
            "retrieved_at": (result.retrieved_at.isoformat() if result.retrieved_at else None),
            "effective_as_of": result.effective_as_of,
            "summary_facts": result.summary_facts,
            "sample_statistic": (result.sample_statistic.model_dump(mode="json")
                                 if result.sample_statistic else None),
            "sources": ev_dicts, "warnings": result.warnings,
            "insufficient_evidence": result.status in (
                ResearchStatus.INSUFFICIENT_EVIDENCE, ResearchStatus.UNAVAILABLE,
                ResearchStatus.RATE_LIMITED),
        }
        # Surface external sources to the candidate via the EXISTING evidence projection, with
        # distinct evidence_type labels — WITHOUT setting retrieval_used (that stays owned by
        # SearchCareerKnowledge, keeping the deterministic agent gate/metrics unchanged).
        merged_evidence = list(ctx.evidence or []) + ev_dicts
        patch = {"evidence": merged_evidence,
                 "external_research_used": True,
                 "external_research_status": result.status.value}
        return ToolOutcome(
            result=observation, state_patch=patch,
            summary=(f"external_research={result.status.value}, provider={result.provider}, "
                     f"sources={result.result_count}"),
            source_count=result.result_count,
            cache=("hit" if result.cache_hit else "miss"),
        )
    return handler


# ExternalEvidence source category → candidate-facing evidence_type label (§40/§41).
_EVIDENCE_TYPE_OF = {
    "authorized_market_api": "advertised_market",
    "company_official_web": "company_web",
    "official_public_web": "official_web",
}


def build_career_tools(career_service, research_service=None) -> list[tuple[type[BaseModel], Handler]]:
    """The six real Career tools, bound to a CareerApplicationService (+ an external-research
    service for the sixth, bounded current-market tool)."""
    if research_service is None:
        from src.copilot.research.service import default_research_service
        research_service = default_research_service()
    return [
        (AnalyzeJobDescription, _analyze_job_description(career_service)),
        (AnalyzeCandidateGaps, _analyze_candidate_gaps(career_service)),
        (BuildPreparationPlan, _build_preparation_plan(career_service)),
        (GenerateInterviewQuestions, _generate_interview_questions(career_service)),
        (SearchCareerKnowledge, _search_career_knowledge(career_service)),
        (ResearchCurrentMarket, _research_current_market(research_service)),
    ]


def build_human_action_tools(career_service) -> list[tuple[type[BaseModel], Handler]]:
    """HITL action tools (Phase 8) — SEPARATE from the five Career evidence tools.

    These do not analyse, calculate or persist anything; they PROPOSE a decision
    that pauses the graph for human approval (memory proposal, practice handoff).
    Role confirmation is triggered deterministically inside SearchCareerKnowledge.
    """
    return [
        (ProposePreparationMemory, _propose_preparation_memory(career_service)),
        (RequestPracticeHandoff, _request_practice_handoff(career_service)),
    ]
