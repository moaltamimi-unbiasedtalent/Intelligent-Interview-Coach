"""History & persistence application boundary (Streamlit-free).

Callable operations over the existing :class:`InterviewRepository` for saving a
completed interview and reading history. The production-hardening behaviour is
preserved exactly: duplicate-save protection, archived Deep Dive persistence,
safe failure handling (a bounded ``save_failed`` flag, never a raw DB error), and
retry capability. No schema change, no new migration, no repository redesign.

The interview payload assembly moved here unchanged except that the practice
``mode`` is now an explicit argument instead of being read from
``st.session_state`` — so a future API can persist without Streamlit.
"""

from __future__ import annotations

import dataclasses
import logging
from typing import Any

from src import timing
from src.application.factories import build_repository
from src.config import AppConfig
from src.session_manager import SessionData, SessionManager

logger = logging.getLogger(__name__)


def build_interview_payload(data: SessionData, *, mode: str | None = None) -> dict:
    """Assemble a persistence payload from the session (appropriate data only)."""
    questions: list[dict] = []
    for i, question in enumerate(data.questions):
        answer_text = data.answers[i] if i < len(data.answers) else ""
        evaluation = (
            data.evaluations[i].model_dump() if i < len(data.evaluations) else None
        )
        guidance = timing.guidance_for_question(question)
        timing_metrics = data.voice_metrics[i] if i < len(data.voice_metrics) else None
        visual_metrics = data.visual_metrics[i] if i < len(data.visual_metrics) else None
        questions.append(
            {
                "position": i,
                "canonical_question": question.question,
                "question_type": question.question_type,
                "difficulty": question.difficulty,
                "timing_guidance": dataclasses.asdict(guidance),
                "is_deep_dive": False,
                "parent_position": None,
                "answer": (
                    {
                        "text": answer_text,
                        "evaluation": evaluation,
                        "timing_metrics": timing_metrics,
                        "visual_metrics": visual_metrics,
                    }
                    if (answer_text or evaluation)
                    else None
                ),
            }
        )
    # Deep Dive branches — serialise BOTH archived branches and any still-active
    # one, otherwise finished Deep Dives are silently dropped from history.
    base = len(data.questions)
    default_parent = base - 1 if base else None
    position = base

    def _branch_records(questions_list, answers, evaluations, parent_id):
        nonlocal position
        parent_pos = parent_id if isinstance(parent_id, int) else default_parent
        for j, branch in enumerate(questions_list):
            answer_text = answers[j] if j < len(answers) else ""
            evaluation = evaluations[j] if j < len(evaluations) else None
            evaluation = evaluation.model_dump() if evaluation is not None else None
            questions.append(
                {
                    "position": position,
                    "canonical_question": branch.question,
                    "question_type": getattr(branch, "question_type", "behavioural"),
                    "difficulty": branch.difficulty,
                    "timing_guidance": None,
                    "is_deep_dive": True,
                    "parent_position": parent_pos,
                    "answer": (
                        {"text": answer_text, "evaluation": evaluation}
                        if (answer_text or evaluation)
                        else None
                    ),
                }
            )
            position += 1

    for archived in getattr(data, "branches", []):
        _branch_records(
            archived.get("questions", []), archived.get("answers", []),
            archived.get("evaluations", []), archived.get("parent_question_id"))
    _branch_records(
        data.branch_questions, data.branch_answers, data.branch_evaluations,
        data.branch_parent_question_id)
    report = None
    if data.report is not None:
        report = {
            "report": data.report.model_dump(),
            "usage": {
                "total_tokens": sum(r.total_tokens for r in data.usage_records),
                "requests": len(data.usage_records),
            },
            "cost_usd": round(data.cumulative_cost_usd, 6),
        }
    return {
        "configuration": data.config.model_dump() if data.config else {},
        "mode": mode,
        "status": "completed",
        "questions": questions,
        "report": report,
    }


def resolve_user_id(config: AppConfig, repo) -> int | None:
    """Resolve the signed-in (or anonymous dev) user to an internal id."""
    from src import auth

    user = auth.current_user(config)
    if user is None:
        return None
    return repo.get_or_create_user(
        subject=user.subject,
        provider=user.provider,
        display_name=user.display_name,
        email=user.email,
    )


def save_completed_interview(
    session: SessionManager,
    config: AppConfig,
    *,
    repo: Any | None = None,
    mode: str | None = None,
    user_id: int | None = None,
    source_session_id: str | None = None,
) -> None:
    """Save a completed interview once per interview (safe on failure).

    The saved-report id lives on the session data, so a reset lets a second
    interview save too. A save failure records a bounded ``save_failed`` flag and
    logs safely; the raw DB error is never surfaced.

    ``user_id`` may be passed explicitly (the API resolves identity itself); when
    omitted it is resolved from the Streamlit-side auth (unchanged UI behaviour).

    ``source_session_id`` (the durable interview session) makes the save
    CRASH-IDEMPOTENT: if the history row was already committed for this session but a
    later durable save of ``saved_report_id`` failed, a retry finds the existing row
    (via the repository's user-scoped uniqueness) and REPAIRS ``saved_report_id``
    rather than inserting a duplicate.
    """
    data = session.data
    if data.saved_report_id:
        return
    try:
        repo = repo or build_repository(config)
        if user_id is None:
            user_id = resolve_user_id(config, repo)
        if user_id is None:
            return
        interview_id = repo.save_interview(
            user_id, build_interview_payload(data, mode=mode),
            source_session_id=source_session_id,
        )
        # interview_id is a brand-new row OR the pre-existing row for this durable
        # session (idempotent) — either way SessionData is repaired truthfully.
        data.saved_report_id = interview_id
        data.save_failed = False
    except Exception as exc:  # noqa: BLE001 - persistence must not break the report
        data.save_failed = True
        # SAFE METADATA ONLY. A raw DB exception (SQLAlchemy StatementError/
        # OperationalError) can carry the SQL statement + bound parameters — which may
        # include the JD, candidate background, answers, evaluations or report content
        # — plus the DB URL/credentials. Never log the exception string, a traceback
        # (no exc_info) or repr; only the exception CLASS NAME as a coarse category.
        logger.warning(
            "Interview persistence failed", extra={"error_category": type(exc).__name__}
        )


def list_interview_reports(repo, user_id: int):
    """List a user's saved interviews (repository passthrough)."""
    return repo.list_interviews(user_id)


def get_interview_report(repo, user_id: int, interview_id: int):
    """Fetch one saved interview's detail, scoped to ``user_id``.

    The repository filters by ``user_id``, so one user can never read another
    user's report (returns ``None`` when the id is not theirs).
    """
    return repo.get_interview(user_id, interview_id)
