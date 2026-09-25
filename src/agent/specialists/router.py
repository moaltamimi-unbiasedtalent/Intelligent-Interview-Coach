"""Deterministic, bounded specialist router (Capstone P5).

A pure function that recommends WHICH specialists are worth invoking for a given
context, in a sensible order, using transparent boolean signals only — no model, no
recursion, no unbounded loop. Mo remains the orchestrator: Mo decides whether to act on
the recommendation by calling the corresponding allowlisted tool. The router never
executes a specialist; it only returns validated :class:`SpecialistName` values from the
fixed allowlist, so it can also drive the reviewer diagnostic.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.agent.specialists.registry import SpecialistName

__all__ = ["RoutingContext", "recommend_specialists"]


@dataclass(frozen=True)
class RoutingContext:
    """Boolean signals derived from safe run state (never raw candidate text)."""

    has_job_description: bool = False
    has_requirements: bool = False
    has_target_role: bool = False
    has_owner_evidence: bool = False  # the caller is an authenticated owner with a user_id
    wants_coaching: bool = False       # the goal asks for preparation/coaching/answers


def recommend_specialists(ctx: RoutingContext) -> list[SpecialistName]:
    """Return an ordered, de-duplicated, bounded list of recommended specialists.

    Ordering reflects the natural pipeline (understand the role → gather the candidate's
    evidence → build a strategy), but each step is independent and skipped when its
    inputs are absent. At most the three specialists, each at most once.
    """
    out: list[SpecialistName] = []

    # A. Role & Opportunity — whenever there is a role to analyse.
    if ctx.has_job_description or ctx.has_requirements or ctx.has_target_role:
        out.append(SpecialistName.ROLE_OPPORTUNITY)

    # B. Candidate Evidence — only for an authenticated owner (private evidence exists).
    if ctx.has_owner_evidence and (ctx.wants_coaching or ctx.has_requirements or ctx.has_target_role):
        out.append(SpecialistName.CANDIDATE_EVIDENCE)

    # C. Interview Strategy — coaching that ties a known role to gathered evidence.
    if ctx.wants_coaching and (ctx.has_job_description or ctx.has_requirements or ctx.has_target_role):
        out.append(SpecialistName.INTERVIEW_STRATEGY)

    # De-dupe while preserving order; hard cap at the number of specialists (bounded).
    seen: set[SpecialistName] = set()
    ordered = [s for s in out if not (s in seen or seen.add(s))]
    return ordered[: len(SpecialistName)]
