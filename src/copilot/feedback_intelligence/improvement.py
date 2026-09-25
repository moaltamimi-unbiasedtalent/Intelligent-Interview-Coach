"""Improvement-candidate lifecycle (Capstone P6/E7, §23/§24/§25).

Turns aggregated, category-classified feedback signals into GOVERNED improvement
candidates with an explicit lifecycle. This is governed IMPROVEMENT, not autonomous
self-learning: a candidate can be PROPOSED → TRIAGED → EXPERIMENTING → ACCEPTED /
REJECTED, and only a human review can mark it IMPLEMENTED — nothing here edits a prompt,
routing, model policy, knowledge or code, and no transition happens automatically from an
evaluation result.

Candidates carry only SAFE aggregate metadata (category, counts, surface, opaque example
refs) — never raw candidate content.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from src.feedback_taxonomy import CATEGORY_TO_CHANGE_AREA, FeedbackCategory

__all__ = [
    "ImprovementStatus", "ImprovementCandidate", "LifecycleError",
    "build_improvement_candidates", "transition", "ALLOWED_TRANSITIONS",
]


class ImprovementStatus(str, Enum):
    PROPOSED = "proposed"
    TRIAGED = "triaged"
    EXPERIMENTING = "experimenting"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    IMPLEMENTED = "implemented"


# Human-driven transitions only. IMPLEMENTED is reachable ONLY from ACCEPTED and is never
# set automatically by any aggregation/evaluation step (§24).
ALLOWED_TRANSITIONS: dict[ImprovementStatus, set[ImprovementStatus]] = {
    ImprovementStatus.PROPOSED: {ImprovementStatus.TRIAGED, ImprovementStatus.REJECTED},
    ImprovementStatus.TRIAGED: {ImprovementStatus.EXPERIMENTING, ImprovementStatus.REJECTED},
    ImprovementStatus.EXPERIMENTING: {ImprovementStatus.ACCEPTED, ImprovementStatus.REJECTED},
    ImprovementStatus.ACCEPTED: {ImprovementStatus.IMPLEMENTED, ImprovementStatus.REJECTED},
    ImprovementStatus.REJECTED: set(),
    ImprovementStatus.IMPLEMENTED: set(),
}


class LifecycleError(Exception):
    """An illegal lifecycle transition."""


class LifecycleEvent(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    at: datetime
    to_status: ImprovementStatus
    actor_id: str = Field(max_length=64)      # safe admin id — never a candidate
    reason: str | None = Field(default=None, max_length=1000)


class ImprovementCandidate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    candidate_id: str = Field(max_length=64)
    problem_category: FeedbackCategory
    change_area: str = Field(max_length=32)
    support_count: int = Field(ge=0)
    affected_surface: str | None = Field(default=None, max_length=64)
    example_refs: list[str] = Field(default_factory=list, max_length=20)
    hypothesis: str = Field(max_length=1000)
    proposed_experiment: str = Field(max_length=1000)
    status: ImprovementStatus = ImprovementStatus.PROPOSED
    created_at: datetime
    history: list[LifecycleEvent] = Field(default_factory=list)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def build_improvement_candidates(
    signals: list[dict], *, min_support: int = 2
) -> list[ImprovementCandidate]:
    """Aggregate NEGATIVE, category-classified feedback signals into improvement candidates.

    ``signals`` are safe dicts with keys: ``category`` (taxonomy value), ``surface``,
    ``ref`` (opaque id), ``rating`` (helpful/not_helpful). Only ``not_helpful`` signals
    contribute. A category reaching ``min_support`` becomes ONE PROPOSED candidate.
    Deterministic (stable ordering by category) and content-free.
    """
    by_cat: dict[FeedbackCategory, list[dict]] = {}
    for s in signals:
        if (s.get("rating") or "").lower() != "not_helpful":
            continue
        cat = FeedbackCategory.from_value(s.get("category"))
        by_cat.setdefault(cat, []).append(s)

    candidates: list[ImprovementCandidate] = []
    for cat in sorted(by_cat, key=lambda c: c.value):
        items = by_cat[cat]
        if len(items) < min_support:
            continue
        surfaces = Counter(s.get("surface") for s in items if s.get("surface"))
        top_surface = surfaces.most_common(1)[0][0] if surfaces else None
        refs = [str(s["ref"]) for s in items if s.get("ref")][:20]
        change_area = CATEGORY_TO_CHANGE_AREA.get(cat, "evaluation")
        candidates.append(ImprovementCandidate(
            candidate_id=f"ic-{cat.value}",
            problem_category=cat,
            change_area=change_area,
            support_count=len(items),
            affected_surface=top_surface,
            example_refs=refs,
            hypothesis=f"Repeated '{cat.value}' feedback on {top_surface or 'multiple surfaces'} "
                       f"suggests a {change_area} improvement may help.",
            proposed_experiment=f"Prompt Lab experiment varying {change_area} config, evaluated "
                                f"against fixed deterministic cases; human decision required.",
            status=ImprovementStatus.PROPOSED,
            created_at=_now(),
        ))
    return candidates


def transition(
    candidate: ImprovementCandidate, to_status: ImprovementStatus, *,
    actor_id: str, reason: str | None = None,
) -> ImprovementCandidate:
    """Apply a HUMAN-driven lifecycle transition, validating it is allowed.

    Raises :class:`LifecycleError` for an illegal transition. ``IMPLEMENTED`` is only
    reachable from ``ACCEPTED`` and always requires an explicit actor — it is never set by
    an automated step. Returns an updated copy (append-only history).
    """
    if not actor_id:
        raise LifecycleError("A human actor id is required for a transition.")
    allowed = ALLOWED_TRANSITIONS.get(candidate.status, set())
    if to_status not in allowed:
        raise LifecycleError(
            f"Illegal transition {candidate.status.value} → {to_status.value}.")
    event = LifecycleEvent(at=_now(), to_status=to_status, actor_id=actor_id, reason=reason)
    return candidate.model_copy(update={
        "status": to_status, "history": [*candidate.history, event],
    })
