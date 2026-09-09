"""Data-access layer for users and interview history.

The Streamlit UI never issues queries directly; it goes through
:class:`InterviewRepository`. Every read and write is scoped to a ``user_id``,
and cross-user access is impossible: an interview id that belongs to another
user resolves to ``None`` / a no-op delete, never to that user's data.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from src.feedback import FeedbackItem
from src.memory import MemoryItem, normalize_role, normalize_summary
from src.persistence import (
    Answer,
    Interview,
    PreparationMemory,
    Question,
    Report,
    User,
    UserFeedback,
)

__all__ = ["InterviewRepository", "MemoryRepository", "FeedbackRepository"]


def _parse_dt(value) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
    return None


class InterviewRepository:
    """User-scoped persistence for interviews, answers and reports."""

    def __init__(self, session_factory: sessionmaker) -> None:
        self._session_factory = session_factory

    @property
    def session_factory(self) -> sessionmaker:
        """The underlying session factory (so sibling repositories share one DB)."""
        return self._session_factory

    # -- users ----------------------------------------------------------------

    def get_or_create_user(
        self,
        *,
        subject: str,
        provider: str,
        display_name: str | None = None,
        email: str | None = None,
    ) -> int:
        """Return the internal user id for an OIDC identity, creating it once."""
        with self._session_factory() as session:
            user = session.scalar(
                select(User).where(User.subject == subject, User.provider == provider)
            )
            if user is None:
                user = User(
                    subject=subject,
                    provider=provider,
                    display_name=display_name,
                    email=email,
                )
                session.add(user)
            else:
                # Keep the profile fresh without touching identity keys.
                user.display_name = display_name or user.display_name
                user.email = email or user.email
            session.commit()
            return user.id

    # -- writes ---------------------------------------------------------------

    def save_interview(
        self, user_id: int, payload: dict, source_session_id: str | None = None
    ) -> int:
        """Persist a completed interview for a user; returns its id.

        ``payload`` is a plain dict assembled from the session (configuration,
        mode, status, timestamps, questions[] with nested answer, and report).
        Only aggregated visual metrics are accepted — never frames.

        When ``source_session_id`` is given, the save is IDEMPOTENT per
        ``(user_id, source_session_id)``: a repeat (e.g. a crash retry) returns the
        existing interview id instead of inserting a duplicate. A concurrent first
        save is resolved by the DB unique index — the loser re-reads the winner and
        returns the same id. When ``source_session_id`` is None, behaviour is
        unchanged (always insert).
        """
        with self._session_factory() as session:
            if source_session_id is not None:
                existing = session.scalar(
                    select(Interview.id).where(
                        Interview.user_id == user_id,
                        Interview.source_session_id == source_session_id,
                    )
                )
                if existing is not None:
                    return existing
            interview = Interview(
                user_id=user_id,
                source_session_id=source_session_id,
                configuration=payload.get("configuration") or {},
                mode=payload.get("mode"),
                status=payload.get("status", "completed"),
                started_at=_parse_dt(payload.get("started_at")),
                ended_at=_parse_dt(payload.get("ended_at")),
            )
            for index, q in enumerate(payload.get("questions") or []):
                question = Question(
                    position=q.get("position", index),
                    canonical_question=q.get("canonical_question", ""),
                    question_type=q.get("question_type"),
                    difficulty=q.get("difficulty"),
                    timing_guidance=q.get("timing_guidance"),
                    is_deep_dive=bool(q.get("is_deep_dive", False)),
                    parent_position=q.get("parent_position"),
                )
                answer = q.get("answer")
                if answer is not None:
                    question.answer = Answer(
                        text=answer.get("text", ""),
                        evaluation=answer.get("evaluation"),
                        timing_metrics=answer.get("timing_metrics"),
                        visual_metrics=answer.get("visual_metrics"),
                    )
                interview.questions.append(question)

            report_payload = payload.get("report")
            if report_payload is not None:
                interview.report = Report(
                    report=report_payload.get("report"),
                    usage=report_payload.get("usage"),
                    cost_usd=report_payload.get("cost_usd"),
                )
            session.add(interview)
            try:
                session.commit()
            except IntegrityError:
                # A concurrent first save won the unique (user_id, source_session_id);
                # re-read and return the winner's id (no duplicate row).
                session.rollback()
                if source_session_id is not None:
                    existing = session.scalar(
                        select(Interview.id).where(
                            Interview.user_id == user_id,
                            Interview.source_session_id == source_session_id,
                        )
                    )
                    if existing is not None:
                        return existing
                raise
            return interview.id

    # -- reads (all user-scoped) ---------------------------------------------

    def _owned(self, session: Session, user_id: int, interview_id: int) -> Interview | None:
        # Ownership is part of the WHERE clause — another user's id yields None.
        return session.scalar(
            select(Interview).where(
                Interview.id == interview_id, Interview.user_id == user_id
            )
        )

    def list_interviews(self, user_id: int) -> list[dict]:
        """Return summary rows for a user's interviews, newest first."""
        with self._session_factory() as session:
            rows = session.scalars(
                select(Interview)
                .where(Interview.user_id == user_id)
                .order_by(Interview.created_at.desc())
            ).all()
            return [self._summary(interview) for interview in rows]

    def get_interview(self, user_id: int, interview_id: int) -> dict | None:
        """Return one interview in full, or None if not owned by this user."""
        with self._session_factory() as session:
            interview = self._owned(session, user_id, interview_id)
            if interview is None:
                return None
            return self._detail(interview)

    def delete_interview(self, user_id: int, interview_id: int) -> bool:
        """Delete one interview if owned by the user; returns True on success."""
        with self._session_factory() as session:
            interview = self._owned(session, user_id, interview_id)
            if interview is None:
                return False
            session.delete(interview)
            session.commit()
            return True

    def delete_all_for_user(self, user_id: int) -> int:
        """Delete every interview for a user; returns the count removed."""
        with self._session_factory() as session:
            interviews = session.scalars(
                select(Interview).where(Interview.user_id == user_id)
            ).all()
            count = len(interviews)
            for interview in interviews:
                session.delete(interview)
            session.commit()
            return count

    def export_user_data(self, user_id: int) -> dict:
        """Return all of a user's data as a plain dict for download/portability."""
        with self._session_factory() as session:
            user = session.get(User, user_id)
            if user is None:
                return {"user": None, "interviews": []}
            interviews = session.scalars(
                select(Interview)
                .where(Interview.user_id == user_id)
                .order_by(Interview.created_at.asc())
            ).all()
            return {
                "user": {
                    "id": user.id,
                    "provider": user.provider,
                    "display_name": user.display_name,
                    "email": user.email,
                },
                "interviews": [self._detail(i) for i in interviews],
            }

    # -- dashboard ------------------------------------------------------------

    def dashboard_metrics(self, user_id: int) -> dict:
        """Aggregate practice metrics for a user (practice guidance, not a score)."""
        with self._session_factory() as session:
            interviews = session.scalars(
                select(Interview)
                .where(Interview.user_id == user_id)
                .order_by(Interview.created_at.asc())
            ).all()
            evaluations: list[dict] = []
            durations: list[float] = []
            for interview in interviews:
                for question in interview.questions:
                    if question.answer and question.answer.evaluation:
                        evaluations.append(question.answer.evaluation)
                    if question.answer and question.answer.timing_metrics:
                        secs = question.answer.timing_metrics.get(
                            "total_speaking_seconds"
                        )
                        if secs:
                            durations.append(float(secs))

            scores = [e.get("overall_score") for e in evaluations if e.get("overall_score") is not None]
            improvement_counts: dict[str, int] = {}
            for e in evaluations:
                for area in e.get("improvement_areas", []) or []:
                    improvement_counts[area] = improvement_counts.get(area, 0) + 1

            return {
                "interviews_completed": len(interviews),
                "answers_evaluated": len(evaluations),
                "average_practice_score": (
                    round(sum(scores) / len(scores), 1) if scores else None
                ),
                "most_common_improvement_area": (
                    max(improvement_counts, key=improvement_counts.get)
                    if improvement_counts
                    else None
                ),
                "average_answer_seconds": (
                    round(sum(durations) / len(durations), 1) if durations else None
                ),
                "recent_interviews": [
                    self._summary(i)
                    for i in sorted(
                        interviews, key=lambda x: x.created_at, reverse=True
                    )[:5]
                ],
            }

    # -- serialisers ----------------------------------------------------------

    @staticmethod
    def _summary(interview: Interview) -> dict:
        config = interview.configuration or {}
        return {
            "id": interview.id,
            "target_role": config.get("target_role"),
            "mode": interview.mode,
            "status": interview.status,
            "questions": len(interview.questions),
            "created_at": interview.created_at.isoformat()
            if interview.created_at
            else None,
        }

    @staticmethod
    def _detail(interview: Interview) -> dict:
        return {
            "id": interview.id,
            "configuration": interview.configuration,
            "mode": interview.mode,
            "status": interview.status,
            "started_at": interview.started_at.isoformat()
            if interview.started_at
            else None,
            "ended_at": interview.ended_at.isoformat() if interview.ended_at else None,
            "created_at": interview.created_at.isoformat()
            if interview.created_at
            else None,
            "questions": [
                {
                    "position": q.position,
                    "canonical_question": q.canonical_question,
                    "question_type": q.question_type,
                    "difficulty": q.difficulty,
                    "timing_guidance": q.timing_guidance,
                    "is_deep_dive": q.is_deep_dive,
                    "parent_position": q.parent_position,
                    "answer": (
                        {
                            "text": q.answer.text,
                            "evaluation": q.answer.evaluation,
                            "timing_metrics": q.answer.timing_metrics,
                            "visual_metrics": q.answer.visual_metrics,
                        }
                        if q.answer
                        else None
                    ),
                }
                for q in interview.questions
            ],
            "report": (
                {
                    "report": interview.report.report,
                    "usage": interview.report.usage,
                    "cost_usd": interview.report.cost_usd,
                }
                if interview.report
                else None
            ),
        }


class MemoryRepository:
    """User-scoped persistence for long-term preparation memory (Phase 7).

    Every read and write is scoped to a ``user_id``; a memory id that belongs to
    another user resolves to ``None`` / a no-op delete, never to that user's data.
    Validation and bounds live in the application service; this layer is pure
    data-access plus deterministic duplicate detection.
    """

    def __init__(self, session_factory: sessionmaker) -> None:
        self._session_factory = session_factory

    @staticmethod
    def _to_item(row: PreparationMemory) -> MemoryItem:
        return MemoryItem(
            id=row.id, user_id=row.user_id, category=row.category,
            summary=row.summary, target_role=row.target_role,
            source_run_id=row.source_run_id,
            created_at=row.created_at, updated_at=row.updated_at,
            pinned=bool(row.pinned),
        )

    def count_for_user(self, user_id: int) -> int:
        with self._session_factory() as session:
            return int(session.scalar(
                select(func.count()).select_from(PreparationMemory)
                .where(PreparationMemory.user_id == user_id)
            ) or 0)

    def find_duplicate(
        self, user_id: int, category: str, summary: str, target_role: str | None,
        *, exclude_id: int | None = None,
    ) -> MemoryItem | None:
        """Return an existing equivalent memory (same user/category/normalized
        summary/role), or None. Deterministic — no fuzzy/LLM matching.

        ``exclude_id`` skips one memory (the one being edited) so an update that does
        not change the dedupe key is never flagged as colliding with itself.
        """
        norm_summary = normalize_summary(summary)
        norm_role = normalize_role(target_role)
        with self._session_factory() as session:
            rows = session.scalars(
                select(PreparationMemory).where(
                    PreparationMemory.user_id == user_id,
                    PreparationMemory.category == category,
                )
            ).all()
            for row in rows:
                if exclude_id is not None and row.id == exclude_id:
                    continue
                if (normalize_summary(row.summary) == norm_summary
                        and normalize_role(row.target_role) == norm_role):
                    return self._to_item(row)
        return None

    def create(
        self, user_id: int, *, category: str, summary: str,
        target_role: str | None = None, source_run_id: str | None = None,
    ) -> MemoryItem:
        with self._session_factory() as session:
            row = PreparationMemory(
                user_id=user_id, category=category, summary=summary,
                target_role=target_role, source_run_id=source_run_id,
            )
            session.add(row)
            session.commit()
            return self._to_item(row)

    def update(
        self, user_id: int, memory_id: int, *, fields: dict
    ) -> MemoryItem | None:
        """Apply already-validated field changes to a user's memory (user-scoped).

        Ownership is part of the WHERE clause — a foreign/unknown id returns None (a
        not-found), never another user's row. Only the given keys are changed;
        ``updated_at`` refreshes via the column's ``onupdate``.
        """
        allowed = {"category", "summary", "target_role", "pinned"}
        with self._session_factory() as session:
            row = session.scalar(
                select(PreparationMemory).where(
                    PreparationMemory.id == memory_id,
                    PreparationMemory.user_id == user_id,
                )
            )
            if row is None:
                return None
            for key, value in fields.items():
                if key in allowed:
                    setattr(row, key, value)
            session.commit()
            session.refresh(row)
            return self._to_item(row)

    def list_for_user(
        self, user_id: int, *, category: str | None = None,
        target_role: str | None = None,
    ) -> list[MemoryItem]:
        """Return a user's memories, newest first (optional category/role filter)."""
        with self._session_factory() as session:
            stmt = select(PreparationMemory).where(
                PreparationMemory.user_id == user_id
            )
            if category is not None:
                stmt = stmt.where(PreparationMemory.category == category)
            if target_role is not None:
                stmt = stmt.where(PreparationMemory.target_role == target_role)
            rows = session.scalars(
                stmt.order_by(PreparationMemory.created_at.desc(),
                              PreparationMemory.id.desc())
            ).all()
            return [self._to_item(r) for r in rows]

    def get(self, user_id: int, memory_id: int) -> MemoryItem | None:
        with self._session_factory() as session:
            row = session.scalar(
                select(PreparationMemory).where(
                    PreparationMemory.id == memory_id,
                    PreparationMemory.user_id == user_id,
                )
            )
            return self._to_item(row) if row is not None else None

    def delete(self, user_id: int, memory_id: int) -> bool:
        with self._session_factory() as session:
            row = session.scalar(
                select(PreparationMemory).where(
                    PreparationMemory.id == memory_id,
                    PreparationMemory.user_id == user_id,
                )
            )
            if row is None:
                return False
            session.delete(row)
            session.commit()
            return True


class FeedbackRepository:
    """User-scoped persistence for candidate feedback (post-Sprint 4 P5).

    Every read/write is scoped to ``user_id``; a feedback row that belongs to another
    user resolves to ``None`` / a no-op. One current rating per
    ``(user_id, surface, target_id)`` (an upsert). Stores references + rating +
    optional comment only — never a copy of any rated content.
    """

    def __init__(self, session_factory: sessionmaker) -> None:
        self._session_factory = session_factory

    @staticmethod
    def _to_item(row: UserFeedback) -> FeedbackItem:
        return FeedbackItem(
            id=row.id, user_id=row.user_id, surface=row.surface,
            target_id=row.target_id, rating=row.rating, comment=row.comment,
            created_at=row.created_at, updated_at=row.updated_at,
        )

    def get(self, user_id: int, surface: str, target_id: str) -> FeedbackItem | None:
        with self._session_factory() as session:
            row = session.scalar(
                select(UserFeedback).where(
                    UserFeedback.user_id == user_id,
                    UserFeedback.surface == surface,
                    UserFeedback.target_id == target_id,
                )
            )
            return self._to_item(row) if row is not None else None

    def upsert(self, user_id: int, *, surface: str, target_id: str, rating: str,
               comment: str | None) -> FeedbackItem:
        """Create or update the single rating for this (user, surface, target).

        A rating change (helpful ↔ not_helpful) updates the SAME row — never a duplicate.
        """
        with self._session_factory() as session:
            row = session.scalar(
                select(UserFeedback).where(
                    UserFeedback.user_id == user_id,
                    UserFeedback.surface == surface,
                    UserFeedback.target_id == target_id,
                )
            )
            if row is None:
                row = UserFeedback(user_id=user_id, surface=surface, target_id=target_id,
                                   rating=rating, comment=comment)
                session.add(row)
                try:
                    session.commit()
                except IntegrityError:
                    # A concurrent insert won the unique key; update that row instead.
                    session.rollback()
                    row = session.scalar(
                        select(UserFeedback).where(
                            UserFeedback.user_id == user_id,
                            UserFeedback.surface == surface,
                            UserFeedback.target_id == target_id,
                        )
                    )
                    if row is None:
                        raise
                    row.rating = rating
                    row.comment = comment
                    session.commit()
            else:
                row.rating = rating
                row.comment = comment
                session.commit()
            session.refresh(row)
            return self._to_item(row)

    def delete(self, user_id: int, surface: str, target_id: str) -> bool:
        with self._session_factory() as session:
            row = session.scalar(
                select(UserFeedback).where(
                    UserFeedback.user_id == user_id,
                    UserFeedback.surface == surface,
                    UserFeedback.target_id == target_id,
                )
            )
            if row is None:
                return False
            session.delete(row)
            session.commit()
            return True

    def metrics(self, *, since: datetime | None = None) -> dict:
        """Aggregate feedback metrics across ALL users (no raw comments, no identities).

        Returns totals + per-surface breakdown + helpful_rate. ``since`` bounds by
        ``created_at`` (e.g. last 7 days). Deterministic; safe to log/export.
        """
        with self._session_factory() as session:
            stmt = select(UserFeedback.surface, UserFeedback.rating, func.count())
            if since is not None:
                stmt = stmt.where(UserFeedback.created_at >= since)
            rows = session.execute(stmt.group_by(UserFeedback.surface, UserFeedback.rating)).all()
        surfaces: dict[str, dict[str, int]] = {}
        total = helpful = not_helpful = 0
        for surface, rating, count in rows:
            count = int(count)
            bucket = surfaces.setdefault(surface, {"helpful": 0, "not_helpful": 0})
            if rating in bucket:
                bucket[rating] += count
            total += count
            if rating == "helpful":
                helpful += count
            elif rating == "not_helpful":
                not_helpful += count
        by_surface = {
            s: {
                "feedback_count": b["helpful"] + b["not_helpful"],
                "helpful_count": b["helpful"],
                "not_helpful_count": b["not_helpful"],
                "helpful_rate": round(b["helpful"] / (b["helpful"] + b["not_helpful"]), 3)
                if (b["helpful"] + b["not_helpful"]) else None,
            }
            for s, b in surfaces.items()
        }
        return {
            "feedback_count": total,
            "helpful_count": helpful,
            "not_helpful_count": not_helpful,
            "helpful_rate": round(helpful / total, 3) if total else None,
            "by_surface": by_surface,
        }

    def list_all(self, *, surface: str | None = None) -> list[FeedbackItem]:
        """All feedback rows (for the human-review export). Comment inclusion/redaction
        is decided by the caller — the repository just returns the rows."""
        with self._session_factory() as session:
            stmt = select(UserFeedback)
            if surface is not None:
                stmt = stmt.where(UserFeedback.surface == surface)
            rows = session.scalars(stmt.order_by(UserFeedback.created_at.asc())).all()
            return [self._to_item(r) for r in rows]
