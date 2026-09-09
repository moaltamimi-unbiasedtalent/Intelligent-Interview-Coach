"""Exact feedback-target verifiers (P5.1).

A feedback target is accepted only when the EXACT rated output exists AND belongs to the
current user — owning the parent run/session is necessary but not sufficient:

* ``agent_answer``      → an assistant message with that ``response_id`` is present in the
  owned run's safe candidate-visible conversation.
* ``interview_evaluation`` → the owned session has a COMPLETED evaluation at the target's
  question position (Deep-Dive evaluations are out of scope — the UI shows no feedback
  control there).
* ``final_report``      → the owned session has GENERATED its final report.

Each verifier FAILS CLOSED: any parse error, service failure, foreign/unknown resource,
or missing evaluation/report returns ``False`` (a not-found), never an ownership grant.
These builders take the services as arguments so they are pure and unit-testable; the
FastAPI wiring supplies the real services (feedback_service.py stays provider-agnostic).
"""

from __future__ import annotations

from typing import Any, Callable

TargetVerifier = Callable[[str, int], bool]

__all__ = [
    "agent_answer_verifier",
    "interview_evaluation_verifier",
    "final_report_verifier",
]


def agent_answer_verifier(agent_service: Any) -> TargetVerifier:
    """True iff ``<run_id>:<index>`` is a real assistant answer in the owned run."""

    def verify(target_id: str, user_id: int) -> bool:
        run_id, sep, index = (target_id or "").partition(":")
        if not sep or not run_id or not index.isdigit() or int(index) < 1:
            return False
        try:
            result = agent_service.get_run(run_id, str(user_id))
        except Exception:  # noqa: BLE001 - foreign/unknown/unavailable → not-found
            return False
        return any(
            m.get("role") == "assistant" and m.get("response_id") == target_id
            for m in (getattr(result, "conversation", None) or [])
        )

    return verify


def interview_evaluation_verifier(session_store: Any) -> TargetVerifier:
    """True iff ``<session_id>:<position>`` is an evaluated question in the owned session."""

    def verify(target_id: str, user_id: int) -> bool:
        session_id, sep, position = (target_id or "").partition(":")
        if not sep or not session_id or not position.isdigit() or int(position) < 1:
            return False
        try:
            manager = session_store.load_state(session_id, user_id)
        except Exception:  # noqa: BLE001 - foreign/unknown/unreadable → not-found
            return False
        evaluations = getattr(manager.data, "evaluations", None) or []
        return len(evaluations) >= int(position)

    return verify


def final_report_verifier(session_store: Any) -> TargetVerifier:
    """True iff the target is EXACTLY an owned session id whose final report exists.

    The final-report target is the bare session id used by the report UI — no suffix,
    no second component. A session id is an opaque ``uuid4().hex`` (no colon), so any
    target containing ``:`` is rejected rather than silently reduced to a prefix (which
    would let ``<owned_session>:anything`` be accepted).
    """

    def verify(target_id: str, user_id: int) -> bool:
        session_id = (target_id or "").strip()
        if not session_id or ":" in session_id:
            return False
        try:
            manager = session_store.load_state(session_id, user_id)
        except Exception:  # noqa: BLE001 - foreign/unknown/unreadable → not-found
            return False
        return getattr(manager.data, "report", None) is not None

    return verify
