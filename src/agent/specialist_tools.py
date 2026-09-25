"""Bounded specialist TOOLS behind Mo (Capstone P5 + E4).

Mo stays the single orchestrator; each specialist is reached ONLY through one
allowlisted tool here, so the existing ReAct loop, ``bind_tools`` allowlist, HITL,
output guard and eval invariants are all preserved automatically — no graph node
changes. Each tool:
- takes Pydantic-validated arguments (the class name IS the tool name / registry key);
- runs a bounded, side-effect-free specialist runtime;
- returns a schema-validated structured output as safe DATA for Mo to synthesise;
- stores a safe projection in the state patch for later specialists / the diagnostic.

Privacy: the Candidate Evidence tool reads the owner's private evidence using the
TRUSTED ``ctx.user_id`` from run state — never a model-supplied id — through the
owner-scoped :class:`EvidenceAccessService`. No specialist sets ``retrieval_used`` (that
invariant stays owned by ``SearchCareerKnowledge``), and none has side effects, writes
memory or starts Practice.
"""

from __future__ import annotations

from typing import Callable

from pydantic import BaseModel, Field

from src.agent.errors import TOOL_FAILURE_MISSING_PREREQUISITE, AgentToolError
from src.agent.specialists import (
    run_coaching_specialist,
    run_evidence_specialist,
    run_role_specialist,
)
from src.agent.specialists.schemas import (
    CoachingInput,
    EvidenceRequest,
    EvidenceSelection,
    RoleAnalysisInput,
    RoleBrief,
)
from src.agent.tooling import ToolContext, ToolOutcome

Handler = Callable[[BaseModel, ToolContext], ToolOutcome]


# --- A. Role & Opportunity specialist tool -----------------------------------


class AnalyzeRoleOpportunity(BaseModel):
    """Ask the Role & Opportunity specialist for a structured brief of a role: its key
    competencies, likely interview themes and priorities. Use when the candidate wants
    to understand what a role/job description demands. Reuses a prior job analysis when
    one exists; otherwise analyses the provided job description."""

    target_role: str | None = Field(default=None, max_length=200)
    job_description: str | None = Field(default=None, max_length=12000)


def _analyze_role_opportunity(career_service) -> Handler:
    def handler(args: AnalyzeRoleOpportunity, ctx: ToolContext) -> ToolOutcome:
        from src.agent.usage import capture_tool_usage

        request = RoleAnalysisInput(
            target_role=args.target_role or ctx.target_role,
            job_description=args.job_description or ctx.job_description,
            requirements=ctx.requirements,
        )
        # Reuses the governed, usage-captured JD-analysis op when it runs; a deterministic
        # brief from existing requirements carries no usage (never fabricated).
        brief, usage = capture_tool_usage(
            "AnalyzeRoleOpportunity",
            lambda: run_role_specialist(request, career_service=career_service))
        data = brief.model_dump()
        return ToolOutcome(
            result=data,
            state_patch={"role_brief": data},
            summary=f"role={brief.role_title or 'n/a'}, competencies={len(brief.key_competencies)}, "
                    f"source={brief.source}",
            source_count=len(brief.key_competencies),
            usage=usage,
        )

    return handler


# --- B. Candidate Evidence specialist tool (deterministic, owner-scoped) ------


class FindCandidateEvidence(BaseModel):
    """Ask the Candidate Evidence specialist to find the candidate's OWN approved
    evidence (accepted CV claims and verified stories) that supports a stated need or
    set of competencies. Returns only the signed-in candidate's approved evidence — it
    never sees another user's data and never reads raw documents. Use it to ground
    coaching in real, candidate-approved examples."""

    need: str = Field(default="", max_length=2000, description="What evidence is needed.")
    competencies: list[str] = Field(default_factory=list, max_length=30)
    limit: int = Field(default=8, ge=1, le=20)


def _find_candidate_evidence(evidence_service) -> Handler:
    def handler(args: FindCandidateEvidence, ctx: ToolContext) -> ToolOutcome:
        request = EvidenceRequest(need=args.need, competencies=list(args.competencies or []),
                                  limit=args.limit)
        # The owner id is TRUSTED run state, never a model argument.
        selection = run_evidence_specialist(
            request, user_id=ctx.user_id, evidence_service=evidence_service)
        data = selection.model_dump()
        # Deterministic op: NO usage, and it does NOT set retrieval_used (owned by
        # SearchCareerKnowledge). Stored for the coaching specialist + diagnostic.
        return ToolOutcome(
            result=data,
            state_patch={"evidence_selection": data},
            summary=f"claims={selection.claim_count}, stories={selection.story_count}, "
                    f"covered={len(selection.covered_competencies)}",
            source_count=len(selection.items),
        )

    return handler


# --- C. Interview Strategy / Coach specialist tool ---------------------------


class BuildCoachingStrategy(BaseModel):
    """Ask the Interview Strategy specialist to turn a known role brief and the
    candidate's gathered evidence into coaching: what to emphasise (with supporting
    evidence), strengths, gaps, and clarifying questions where evidence is missing.
    Analyse the role first (and, for the signed-in candidate, gather evidence first)."""

    focus: list[str] = Field(default_factory=list, max_length=20)


def _build_coaching_strategy(reasoner=None) -> Handler:
    def handler(args: BuildCoachingStrategy, ctx: ToolContext) -> ToolOutcome:
        if not ctx.role_brief:
            raise AgentToolError(
                "Analyse the role first so coaching can be grounded in real requirements.",
                category=TOOL_FAILURE_MISSING_PREREQUISITE)
        brief = RoleBrief(**ctx.role_brief)
        evidence = EvidenceSelection(**ctx.evidence_selection) if ctx.evidence_selection else EvidenceSelection()
        request = CoachingInput(role_brief=brief, evidence=evidence, gaps=ctx.gaps)
        plan = run_coaching_specialist(request, reasoner=reasoner)
        data = plan.model_dump()
        return ToolOutcome(
            result=data,
            state_patch={"coaching_plan": data},
            summary=f"recs={len(plan.recommendations)}, strengths={len(plan.strengths)}, "
                    f"gaps={len(plan.gaps)}, clarifications={len(plan.clarifications)}",
            source_count=len(plan.recommendations),
        )

    return handler


def build_specialist_tools(
    career_service, *, evidence_service=None, coaching_reasoner=None
) -> list[tuple[type[BaseModel], Handler]]:
    """The three bounded specialist tools behind Mo.

    ``evidence_service`` (owner-scoped approved-evidence access) may be None in
    environments without candidate documents — the evidence tool then returns an empty,
    safe selection. ``coaching_reasoner`` is an optional injectable structured reasoner;
    None keeps the deterministic (zero paid call) coaching path.
    """
    return [
        (AnalyzeRoleOpportunity, _analyze_role_opportunity(career_service)),
        (FindCandidateEvidence, _find_candidate_evidence(evidence_service)),
        (BuildCoachingStrategy, _build_coaching_strategy(coaching_reasoner)),
    ]
