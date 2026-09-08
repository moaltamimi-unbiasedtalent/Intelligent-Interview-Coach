"""Explicit, safe SessionData ⇆ JSON codec for durable interview persistence.

Sprint 4 Phase 10. In-progress interview state (``SessionData``) must survive a
browser refresh and a backend restart, so it is stored durably as JSON. This module
is the ONLY place that converts the in-memory dataclass to/from a JSON-compatible
payload.

Design rules:
- **No pickle / marshal / eval / repr-based reconstruction.** Every field is encoded
  and rebuilt explicitly. A malformed payload raises :class:`SessionCodecError`
  (a safe, message-only error), never an arbitrary object.
- Pydantic domain models are dumped with ``model_dump(mode="json")`` and rebuilt with
  ``model_validate`` — the model classes remain the single source of truth for shape
  and validation.
- Enums are stored by value; unknown enum values fail safely on decode.
- Archived Deep Dive branches contain nested Pydantic objects (branch questions and
  evaluations); those are encoded/decoded explicitly too.
- A ``schema_version`` boundary is established: an unknown/future version fails
  safely rather than being silently misinterpreted.

No private candidate content (answers, JD, background) is ever logged here.
"""

from __future__ import annotations

from typing import Any

from src.models import (
    AnswerEvaluation,
    BranchQuestion,
    ExternalServiceUsage,
    FinalInterviewReport,
    InterviewConfiguration,
    InterviewQuestion,
    InterviewStrategy,
    ModelSettings,
    UsageRecord,
)
from src.session_manager import SessionData, SessionState

__all__ = [
    "SESSION_STATE_SCHEMA_VERSION",
    "SessionCodecError",
    "encode_session_data",
    "decode_session_data",
]

# Bump ONLY with a documented, tested payload migration. An older/newer unsupported
# value must fail safely on load (never be silently reinterpreted).
SESSION_STATE_SCHEMA_VERSION = 1


class SessionCodecError(Exception):
    """A SessionData payload could not be encoded or decoded safely.

    Message is safe to surface; it never contains candidate content.
    """


# --- helpers -----------------------------------------------------------------


def _dump(model: Any | None) -> dict | None:
    return None if model is None else model.model_dump(mode="json")


def _dump_list(models: list) -> list[dict]:
    return [m.model_dump(mode="json") for m in (models or [])]


def _load(model_cls, value: Any | None):
    if value is None:
        return None
    try:
        return model_cls.model_validate(value)
    except Exception as exc:  # noqa: BLE001 - never leak raw content; report safely
        raise SessionCodecError(
            f"Could not reconstruct {model_cls.__name__} from stored state."
        ) from exc


def _load_list(model_cls, values: Any) -> list:
    if not values:
        return []
    if not isinstance(values, list):
        raise SessionCodecError(f"Expected a list of {model_cls.__name__} in stored state.")
    return [_load(model_cls, v) for v in values]


def _encode_branch(branch: dict) -> dict:
    """Encode ONE archived branch (nested Pydantic questions/evaluations)."""
    return {
        "branch_id": branch.get("branch_id"),
        "parent_question_id": branch.get("parent_question_id"),
        "mode": branch.get("mode"),
        "questions": _dump_list(branch.get("questions") or []),
        "answers": list(branch.get("answers") or []),
        "evaluations": _dump_list(branch.get("evaluations") or []),
    }


def _decode_branch(branch: Any) -> dict:
    if not isinstance(branch, dict):
        raise SessionCodecError("Malformed archived Deep Dive branch in stored state.")
    return {
        "branch_id": branch.get("branch_id"),
        "parent_question_id": branch.get("parent_question_id"),
        "mode": branch.get("mode"),
        "questions": _load_list(BranchQuestion, branch.get("questions")),
        "answers": list(branch.get("answers") or []),
        "evaluations": _load_list(AnswerEvaluation, branch.get("evaluations")),
    }


def _state_value(state: Any) -> str:
    return getattr(state, "value", state)


def _decode_state(value: Any) -> SessionState:
    try:
        return SessionState(value)
    except ValueError as exc:
        raise SessionCodecError(f"Unknown interview state {value!r} in stored state.") from exc


# --- public API --------------------------------------------------------------


def encode_session_data(data: SessionData) -> dict:
    """Encode a :class:`SessionData` into a JSON-compatible payload (no version key;
    the store persists :data:`SESSION_STATE_SCHEMA_VERSION` alongside it)."""
    return {
        "state": _state_value(data.state),
        "config": _dump(data.config),
        "settings": _dump(data.settings),
        "prompt_technique": data.prompt_technique,
        "strategy": _dump(data.strategy),
        "chat_messages": [dict(m) for m in (data.chat_messages or [])],
        "questions": _dump_list(data.questions),
        "answers": list(data.answers or []),
        "evaluations": _dump_list(data.evaluations),
        "report": _dump(data.report),
        "current_question_number": int(data.current_question_number or 0),
        "usage_records": _dump_list(data.usage_records),
        "cumulative_cost_usd": float(data.cumulative_cost_usd or 0.0),
        "transcription_usage": _dump_list(data.transcription_usage),
        "voice_metrics": [dict(m) for m in (data.voice_metrics or [])],
        "visual_metrics": [dict(m) for m in (data.visual_metrics or [])],
        "branch_active": bool(data.branch_active),
        "active_branch_id": data.active_branch_id,
        "branch_parent_question_id": data.branch_parent_question_id,
        "branch_mode": data.branch_mode,
        "branch_depth": int(data.branch_depth or 0),
        "branch_questions": _dump_list(data.branch_questions),
        "branch_answers": list(data.branch_answers or []),
        "branch_evaluations": _dump_list(data.branch_evaluations),
        "branch_started_at": data.branch_started_at,
        "branches": [_encode_branch(b) for b in (data.branches or [])],
        "error": data.error,
        "previous_state": _state_value(data.previous_state) if data.previous_state else None,
        "interview_start_time": data.interview_start_time,
        "active_operation": data.active_operation,
        "saved_report_id": data.saved_report_id,
        "save_failed": bool(data.save_failed),
        "preferences": dict(data.preferences or {}),
    }


def decode_session_data(payload: dict, *, schema_version: int) -> SessionData:
    """Rebuild a validated :class:`SessionData` from a stored payload.

    Fails safely (raises :class:`SessionCodecError`) for an unsupported schema
    version or a malformed payload — never silently misinterprets old state.
    """
    if schema_version != SESSION_STATE_SCHEMA_VERSION:
        raise SessionCodecError(
            f"Unsupported interview session schema version {schema_version} "
            f"(this build supports {SESSION_STATE_SCHEMA_VERSION})."
        )
    if not isinstance(payload, dict):
        raise SessionCodecError("Stored interview state is not a valid object.")

    prev = payload.get("previous_state")
    return SessionData(
        state=_decode_state(payload.get("state", SessionState.SETUP.value)),
        config=_load(InterviewConfiguration, payload.get("config")),
        settings=_load(ModelSettings, payload.get("settings")),
        prompt_technique=payload.get("prompt_technique"),
        strategy=_load(InterviewStrategy, payload.get("strategy")),
        chat_messages=[dict(m) for m in (payload.get("chat_messages") or [])],
        questions=_load_list(InterviewQuestion, payload.get("questions")),
        answers=list(payload.get("answers") or []),
        evaluations=_load_list(AnswerEvaluation, payload.get("evaluations")),
        report=_load(FinalInterviewReport, payload.get("report")),
        current_question_number=int(payload.get("current_question_number") or 0),
        usage_records=_load_list(UsageRecord, payload.get("usage_records")),
        cumulative_cost_usd=float(payload.get("cumulative_cost_usd") or 0.0),
        transcription_usage=_load_list(ExternalServiceUsage, payload.get("transcription_usage")),
        voice_metrics=[dict(m) for m in (payload.get("voice_metrics") or [])],
        visual_metrics=[dict(m) for m in (payload.get("visual_metrics") or [])],
        branch_active=bool(payload.get("branch_active")),
        active_branch_id=payload.get("active_branch_id"),
        branch_parent_question_id=payload.get("branch_parent_question_id"),
        branch_mode=payload.get("branch_mode"),
        branch_depth=int(payload.get("branch_depth") or 0),
        branch_questions=_load_list(BranchQuestion, payload.get("branch_questions")),
        branch_answers=list(payload.get("branch_answers") or []),
        branch_evaluations=_load_list(AnswerEvaluation, payload.get("branch_evaluations")),
        branch_started_at=payload.get("branch_started_at"),
        branches=[_decode_branch(b) for b in (payload.get("branches") or [])],
        error=payload.get("error"),
        previous_state=_decode_state(prev) if prev else None,
        interview_start_time=payload.get("interview_start_time"),
        active_operation=payload.get("active_operation"),
        saved_report_id=payload.get("saved_report_id"),
        save_failed=bool(payload.get("save_failed")),
        preferences=dict(payload.get("preferences") or {}),
    )
