"""Deterministic candidate-journey + handoff-provenance derivation (post-Sprint 4, P4).

Two PURE projections over the agent's safe state — no model call, no chain-of-thought,
no raw tool arguments / checkpoint / system prompt:

* :func:`derive_journey` — the UNDERSTAND → PREPARE → PRACTISE lifecycle, with each
  stage's status derived ONLY from real completed application state (never from "the
  UI was opened" or "a spinner finished"). It also carries the per-tool booleans the
  UI's observable preparation checklist reads.
* :func:`derive_handoff_summary` — a candidate-safe explanation of WHAT will be carried
  into Interview Practice, WHERE each piece came from and the question count. It is an
  explanatory projection of the existing PreparationContext handoff, never a competing
  data object, and it only names sources that genuinely exist (no fabricated metadata).

These make the sophistication already in the backend understandable — they add no new
agent, tool, retrieval, memory or interview behaviour.
"""

from __future__ import annotations

from typing import Any

__all__ = ["STAGE_NOT_STARTED", "STAGE_IN_PROGRESS", "STAGE_COMPLETE",
           "derive_journey", "derive_handoff_summary"]

STAGE_NOT_STARTED = "not_started"
STAGE_IN_PROGRESS = "in_progress"
STAGE_COMPLETE = "complete"

# How many focus areas / gap labels we surface in a handoff summary (bounded, safe).
_MAX_FOCUS = 6


def _nonempty(value: Any) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    return bool(value)


def _role_value(state: dict) -> str | None:
    confirmed = (state.get("confirmed_target_role") or "").strip()
    target = (state.get("target_role") or "").strip()
    role_title = ((state.get("requirements") or {}).get("role_title") or "").strip()
    return confirmed or target or role_title or None


def derive_journey(state: dict) -> dict[str, Any]:
    """Derive the UNDERSTAND → PREPARE → PRACTISE journey from safe agent state.

    Each stage status is one of ``not_started`` / ``in_progress`` / ``complete`` and is
    derived only from real structured outputs — never fabricated. The booleans expose
    exactly which controlled steps have produced state (used by the UI checklist); no
    raw requirements/gaps/plan content is included.
    """
    requirements_known = _nonempty(state.get("requirements"))
    gaps_known = _nonempty(state.get("gaps"))
    plan_known = _nonempty(state.get("preparation_plan"))
    questions_known = _nonempty(state.get("questions"))
    evidence_used = bool(state.get("retrieval_used"))
    role_known = _role_value(state) is not None
    handoff_approved = bool(state.get("handoff_approved"))
    pending = state.get("pending_action") or {}
    handoff_pending = isinstance(pending, dict) and pending.get("type") == "approve_practice_handoff"

    # UNDERSTAND: the opportunity is established (role + JD analysis or evidence).
    if role_known and (requirements_known or evidence_used):
        understand = STAGE_COMPLETE
    elif role_known or requirements_known or evidence_used:
        understand = STAGE_IN_PROGRESS
    else:
        understand = STAGE_NOT_STARTED

    # PREPARE: concrete preparation material has been produced (a plan or questions).
    if questions_known or plan_known:
        prepare = STAGE_COMPLETE
    elif gaps_known:
        prepare = STAGE_IN_PROGRESS
    else:
        prepare = STAGE_NOT_STARTED

    # PRACTISE: the handoff was approved (complete) or is awaiting approval (in progress).
    if handoff_approved:
        practise = STAGE_COMPLETE
    elif handoff_pending:
        practise = STAGE_IN_PROGRESS
    else:
        practise = STAGE_NOT_STARTED

    return {
        "understand": {
            "status": understand,
            "role_known": role_known,
            "requirements_known": requirements_known,
            "evidence_used": evidence_used,
        },
        "prepare": {
            "status": prepare,
            "gaps_known": gaps_known,
            "plan_known": plan_known,
            "questions_known": questions_known,
        },
        "practise": {
            "status": practise,
            "handoff_approved": handoff_approved,
        },
    }


def _question_count(questions: Any) -> int:
    if not isinstance(questions, dict):
        return 0
    total = 0
    for cat in questions.get("categories") or []:
        if isinstance(cat, dict):
            total += len(cat.get("questions") or [])
    return total


def _focus_areas(state: dict) -> list[dict[str, str]]:
    """Focus areas from the gap analysis (preferred) or the preparation plan."""
    gaps = state.get("gaps") or {}
    priority = gaps.get("priority_gaps") if isinstance(gaps, dict) else None
    if priority:
        out = []
        for g in priority[:_MAX_FOCUS]:
            label = (g.get("requirement") if isinstance(g, dict) else None) or ""
            if label.strip():
                out.append({"value": label.strip(), "source": "gap_analysis"})
        if out:
            return out
    plan = state.get("preparation_plan") or {}
    allocations = plan.get("allocations") if isinstance(plan, dict) else None
    if allocations:
        out = []
        for a in allocations[:_MAX_FOCUS]:
            label = (a.get("requirement") if isinstance(a, dict) else None) or ""
            if label.strip():
                out.append({"value": label.strip(), "source": "preparation_plan"})
        return out
    return []


def derive_handoff_summary(state: dict) -> dict[str, Any] | None:
    """Return a candidate-safe explanation of the Practice handoff, or None.

    Only fields that genuinely exist are returned, each with a truthful ``source`` —
    never a fabricated role, focus area, count or origin. This is a projection of the
    existing PreparationContext; it does not create a competing handoff object.
    """
    role_value = _role_value(state)
    if role_value is None:
        return None  # nothing meaningful to hand off yet

    confirmed = (state.get("confirmed_target_role") or "").strip()
    requirements_known = _nonempty(state.get("requirements"))
    role_source = "confirmed_role" if confirmed else ("job_analysis" if requirements_known else "confirmed_role")

    summary: dict[str, Any] = {
        "target_role": {"value": role_value, "source": role_source},
    }
    focus = _focus_areas(state)
    if focus:
        summary["focus_areas"] = focus
    q_count = _question_count(state.get("questions"))
    if q_count:
        summary["question_count"] = q_count
        summary["question_source"] = "question_generator"
    return summary
