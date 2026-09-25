"""Interview Strategy / Answer Coach specialist — bounded synthesis (Capstone P5).

Given a structured :class:`RoleBrief` and a bounded, owner-scoped
:class:`EvidenceSelection`, it produces a :class:`CoachingPlan`: what to emphasise
(with supporting evidence), genuine strengths, gaps, and — crucially — explicit
CLARIFICATION_NEEDED prompts wherever a competency has no supporting evidence. It
NEVER invents metrics, outcomes or achievements: a missing example becomes a question
to ask the candidate, not a fabricated success.

The E4 policy declares SPECIALIST_COACHING as an LLM (STRUCTURED) operation, and this
runtime accepts an injectable ``reasoner`` for that path. Because a live coaching model
is UNVALIDATED in this phase (mirroring the OCR / OIDC live-path precedent), the
DETERMINISTIC fallback owns the path today — so every test and the offline eval run
with zero paid calls. When a reasoner IS supplied, its output is schema-validated AND
every model-produced evidence id is re-validated against the provided evidence set
(the model can never introduce or assert an id the owner-scoped selection did not
contain). Advisory only: no side effects, no auto-memory, cannot start Practice.
"""

from __future__ import annotations

from typing import Callable

from src.agent.specialists._matching import overlap_score, tokens
from src.agent.specialists.schemas import (
    CoachingInput,
    CoachingPlan,
    CoachingRecommendation,
    EvidenceItem,
)

__all__ = ["run_coaching_specialist", "CoachingReasoner"]

# An injectable structured reasoner: input CoachingInput → a dict shaped like
# CoachingPlan. It must make NO unbounded call; the caller wires timeouts/retries via
# the E4 policy. None (the default) selects the deterministic fallback.
CoachingReasoner = Callable[[CoachingInput], dict]


def run_coaching_specialist(
    request: CoachingInput, *, reasoner: CoachingReasoner | None = None
) -> CoachingPlan:
    """Produce a coaching plan. Deterministic by default; validates any reasoner output."""
    if reasoner is not None:
        plan = _from_reasoner(request, reasoner)
        if plan is not None:
            return plan
    return _deterministic_plan(request)


def _valid_evidence_ids(evidence_items: list[EvidenceItem]) -> set[int]:
    return {int(i.id) for i in evidence_items}


def _from_reasoner(request: CoachingInput, reasoner: CoachingReasoner) -> CoachingPlan | None:
    """Validate + sanitise a reasoner's structured output; None on any failure."""
    try:
        raw = reasoner(request)
        plan = CoachingPlan(**raw) if isinstance(raw, dict) else None
    except Exception:  # noqa: BLE001 - a bad/failed reasoner falls back deterministically
        return None
    if plan is None:
        return None
    valid_ids = _valid_evidence_ids(request.evidence.items)
    # Server-validate every model-produced id: drop any id not in the owner-scoped set.
    clean_recs = [
        rec.model_copy(update={
            "supporting_evidence_ids": [i for i in rec.supporting_evidence_ids if i in valid_ids]
        })
        for rec in plan.recommendations
    ]
    return plan.model_copy(update={"recommendations": clean_recs})


def _deterministic_plan(request: CoachingInput) -> CoachingPlan:
    """Map approved evidence to the role's competencies by transparent keyword overlap.

    Covered competency → a strength + a recommendation citing the supporting evidence
    ids. Uncovered competency → a gap + a CLARIFICATION_NEEDED prompt (never a
    fabricated example).
    """
    brief = request.role_brief
    items = request.evidence.items
    competencies = _dedupe(list(brief.key_competencies) + list(brief.priorities))

    recommendations: list[CoachingRecommendation] = []
    strengths: list[str] = []
    gaps: list[str] = []
    clarifications: list[str] = []

    for comp in competencies:
        ctoks = tokens(comp)
        supporting = [
            it.id for it in items
            if overlap_score(ctoks, it.text) > 0
            or overlap_score(ctoks, " ".join(it.competencies)) > 0
            or overlap_score(ctoks, it.label) > 0
        ]
        if supporting:
            strengths.append(comp)
            recommendations.append(CoachingRecommendation(
                recommendation=f"Lead with your evidence for {comp}; structure it as a STAR example.",
                competency=comp,
                supporting_evidence_ids=supporting[:20],
            ))
        else:
            gaps.append(comp)
            clarifications.append(
                f"No approved evidence covers '{comp}'. Can you share a concrete example "
                f"(situation, your action, the measurable result) demonstrating it?"
            )

    # Competencies the evidence specialist already flagged uncovered → clarifications too.
    for comp in request.evidence.uncovered_competencies:
        if comp not in gaps:
            gaps.append(comp)
            clarifications.append(f"Consider preparing an example for '{comp}'.")

    if not competencies:
        clarifications.append(
            "Provide a job description or target role so coaching can be grounded in "
            "real requirements.")

    covered = len(strengths)
    total = max(len(competencies), 1)
    ratio = covered / total
    confidence = "high" if ratio >= 0.66 and competencies else ("medium" if ratio >= 0.33 else "low")

    return CoachingPlan(
        recommendations=recommendations[:20],
        strengths=strengths[:20],
        gaps=gaps[:20],
        clarifications=clarifications[:20],
        confidence=confidence,
    )


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for it in items:
        key = (it or "").strip().lower()
        if key and key not in seen:
            seen.add(key)
            out.append(it)
    return out
