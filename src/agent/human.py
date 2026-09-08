"""Human-in-the-loop types for the LangGraph agent (Sprint 4 Phase 8).

Defines the FIXED set of human action types the application allows, a safe
:class:`PendingHumanAction` (the only agent state the client sees when a run
pauses), and deterministic validation of a human decision against the pending
action. The model can only cause a *known* approval path to be requested — it can
never invent an action type or smuggle arbitrary state changes through a decision.

Everything here is provider-free and UI-free; a human response is treated as
UNTRUSTED input and validated/bounded before it can affect the graph.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class HumanActionType(str, Enum):
    """The closed set of decisions that pause the graph for a human."""

    CONFIRM_ROLE = "confirm_role"                       # ambiguous target occupation
    APPROVE_MEMORY = "approve_memory"                   # persist a proposed memory
    APPROVE_PRACTICE_HANDOFF = "approve_practice_handoff"  # hand off to Interview Practice


# Decision verbs, per action type.
DECISION_SELECT = "select"
DECISION_APPROVE = "approve"
DECISION_REJECT = "reject"

_MAX_OPTIONS = 6
_MAX_MESSAGE = 300


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class PendingHumanAction:
    """Safe, user-visible description of what the agent is waiting for.

    Contains ONLY safe fields (an id, the action type, a short message, bounded
    options and a small safe data dict). It must never carry a system prompt,
    chain-of-thought, provider payload, raw checkpoint, raw CV/JD, or DB ids.
    """

    type: HumanActionType
    message: str
    options: list[str] = field(default_factory=list)
    data: dict[str, Any] = field(default_factory=dict)
    action_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    created_at: str = field(default_factory=_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_id": self.action_id,
            "type": self.type.value,
            "message": self.message[:_MAX_MESSAGE],
            "options": [str(o) for o in self.options][:_MAX_OPTIONS],
            "data": self.data,
            "created_at": self.created_at,
        }


def confirm_role_action(candidates: list[str]) -> dict[str, Any]:
    """Pending action for an ambiguous occupation — bounded candidate titles."""
    options = [c for c in dict.fromkeys(candidates) if c][:_MAX_OPTIONS]
    return PendingHumanAction(
        type=HumanActionType.CONFIRM_ROLE,
        message="I found more than one possible occupation. Which one are you preparing for?",
        options=options,
    ).to_dict()


def approve_memory_action(*, category: str, summary: str, target_role: str | None) -> dict[str, Any]:
    """Pending action showing EXACTLY what would be persisted (nothing hidden)."""
    return PendingHumanAction(
        type=HumanActionType.APPROVE_MEMORY,
        message="Would you like me to remember this for future preparation?",
        options=[DECISION_APPROVE, DECISION_REJECT],
        data={"category": category, "summary": summary, "target_role": target_role},
    ).to_dict()


def approve_handoff_action(*, target_role: str | None, priority_count: int,
                           question_count: int | None = None) -> dict[str, Any]:
    """Pending action to approve handing off into Interview Practice."""
    data: dict[str, Any] = {"target_role": target_role, "priority_count": priority_count}
    if question_count is not None:
        data["question_count"] = question_count
    return PendingHumanAction(
        type=HumanActionType.APPROVE_PRACTICE_HANDOFF,
        message="Ready to practise the areas we've identified?",
        options=[DECISION_APPROVE, DECISION_REJECT],
        data=data,
    ).to_dict()


class InvalidHumanDecision(ValueError):
    """A human decision that does not validate against the pending action."""


def validate_decision(pending: dict[str, Any] | None, decision: dict[str, Any]) -> dict[str, Any]:
    """Validate an untrusted human decision against the current pending action.

    Returns a NORMALISED decision (only known keys) to pass to ``Command(resume=)``.
    Raises :class:`InvalidHumanDecision` for any mismatch — the caller keeps the
    graph paused and returns a safe validation error (no state mutation).
    """
    if not pending:
        raise InvalidHumanDecision("There is no pending decision for this run.")
    if not isinstance(decision, dict):
        raise InvalidHumanDecision("A decision object is required.")

    action_id = decision.get("action_id")
    if not action_id or action_id != pending.get("action_id"):
        raise InvalidHumanDecision("This decision does not match the pending request.")

    try:
        atype = HumanActionType(pending.get("type"))
    except ValueError as exc:  # pragma: no cover - pending is server-built
        raise InvalidHumanDecision("Unknown pending action type.") from exc

    verdict = decision.get("decision")
    normalised: dict[str, Any] = {"action_id": action_id, "type": atype.value}

    if atype is HumanActionType.CONFIRM_ROLE:
        if verdict not in (DECISION_SELECT, DECISION_REJECT):
            raise InvalidHumanDecision("Decision must be 'select' or 'reject'.")
        if verdict == DECISION_SELECT:
            selected = decision.get("selected_role")
            if not selected or selected not in (pending.get("options") or []):
                raise InvalidHumanDecision("Select one of the offered role options.")
            normalised["selected_role"] = selected
        normalised["decision"] = verdict
    else:  # APPROVE_MEMORY / APPROVE_PRACTICE_HANDOFF
        if verdict not in (DECISION_APPROVE, DECISION_REJECT):
            raise InvalidHumanDecision("Decision must be 'approve' or 'reject'.")
        normalised["decision"] = verdict

    return normalised
