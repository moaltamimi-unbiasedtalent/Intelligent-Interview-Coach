"""Durable, user-scoped store for IN-PROGRESS interview sessions (Sprint 4 Phase 10).

Replaces the transitional in-process ``InMemorySessionStore`` as the production path
for the FastAPI Interview routes. In-progress interview state (the serialised
``SessionData``) is persisted in the ``interview_sessions`` table so a candidate can
refresh the browser or the backend can restart without losing an interview.

Boundaries this module owns (and nothing above it re-implements):
- **Serialisation** via :mod:`src.interview.session_codec` (explicit JSON, no pickle).
- **User isolation** — every read/write is scoped to ``user_id``; an unknown id and a
  foreign id are indistinguishable (both raise ``SessionNotFoundError``).
- **Optimistic concurrency** — each mutation saves with the loaded ``version`` and
  bumps it; a stale write updates zero rows and raises ``SessionConflictError``.
- **Durable idempotency** — a ``(user_id, idempotency_key)`` maps to one session and
  survives a restart (unlike the Phase 9 in-memory mapping).
- **Operation lease** — a bounded, recoverable claim around provider-backed mutations
  so a duplicate concurrent request cannot launch the same paid call twice; a stale
  lease (crashed worker) is reclaimable.

The interview STATE MACHINE (``SessionManager``) is unchanged: this store loads a
payload, hands a ``SessionManager`` over a temporary mapping to the caller, then
serialises the mutated ``SessionData`` back. No scoring/question/transition logic
lives here. No candidate content is ever logged.
"""

from __future__ import annotations

import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Callable, Iterator

from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from src import constants
from src.interview.session_codec import (
    SESSION_STATE_SCHEMA_VERSION,
    decode_session_data,
    encode_session_data,
)
from src.persistence import InterviewSession, utcnow
from src.session_manager import NAMESPACE, SessionData, SessionManager, SessionState

__all__ = [
    "DurableInterviewSessionStore",
    "SessionNotFoundError",
    "SessionConflictError",
    "OperationInProgressError",
    "SessionSummary",
]


class SessionNotFoundError(KeyError):
    """The session id is unknown, or is not owned by the requesting user.

    The two cases are deliberately indistinguishable so ownership failures never leak
    the existence of another user's session.
    """


class SessionConflictError(Exception):
    """A save lost an optimistic-concurrency race; the caller must reload and retry."""


class OperationInProgressError(Exception):
    """A provider-backed operation is already in flight for this session (a fresh
    lease is held); the caller should not launch a duplicate."""


@dataclass
class SessionSummary:
    """Safe summary for active-session discovery (never JD/background/answers)."""

    session_id: str
    target_role: str | None
    state: str
    question_number: int
    questions_planned: int | None
    updated_at: str | None


class DurableInterviewSessionStore:
    """Durable equivalent of ``InMemorySessionStore`` with load→mutate→save semantics."""

    def __init__(
        self,
        session_factory: sessionmaker,
        *,
        clock: Callable[[], float] | None = None,
        lease_seconds: int = constants.INTERVIEW_OPERATION_LEASE_SECONDS,
    ) -> None:
        self._session_factory = session_factory
        self._clock = clock
        self._lease_seconds = lease_seconds

    # -- internal helpers -----------------------------------------------------

    def _new_id(self) -> str:
        return uuid.uuid4().hex

    def _manager_from_payload(self, payload: dict, schema_version: int) -> SessionManager:
        data = decode_session_data(payload, schema_version=schema_version)
        store: dict[str, Any] = {NAMESPACE: data}
        if self._clock is not None:
            return SessionManager(store=store, clock=self._clock)
        return SessionManager(store=store)

    @staticmethod
    def _status_of(data: SessionData) -> str:
        return getattr(data.state, "value", str(data.state))

    # -- creation -------------------------------------------------------------

    def create(self, user_id: Any) -> str:
        """Create a fresh empty durable session and return its opaque id."""
        session_id = self._new_id()
        payload = encode_session_data(SessionData())
        now = utcnow()
        with self._session_factory() as db:
            db.add(InterviewSession(
                session_id=session_id, user_id=user_id, idempotency_key=None,
                state_payload=payload, state_schema_version=SESSION_STATE_SCHEMA_VERSION,
                version=1, status=SessionState.SETUP.value,
                created_at=now, updated_at=now, last_accessed_at=now))
            db.commit()
        return session_id

    def create_or_get(self, user_id: Any, idempotency_key: str) -> tuple[str, bool]:
        """Return ``(session_id, created)`` for a user-scoped idempotency key.

        Durable: a repeat with the same ``(user_id, idempotency_key)`` returns the
        SAME session (``created=False``) even after a backend restart. A different key
        or user yields a distinct session. Concurrent first-creates race safely on the
        unique constraint (the loser re-reads the winner's row).
        """
        with self._session_factory() as db:
            existing = db.execute(
                select(InterviewSession.session_id).where(
                    InterviewSession.user_id == user_id,
                    InterviewSession.idempotency_key == idempotency_key,
                )
            ).scalar_one_or_none()
            if existing is not None:
                return existing, False

            session_id = self._new_id()
            payload = encode_session_data(SessionData())
            now = utcnow()
            db.add(InterviewSession(
                session_id=session_id, user_id=user_id, idempotency_key=idempotency_key,
                state_payload=payload, state_schema_version=SESSION_STATE_SCHEMA_VERSION,
                version=1, status=SessionState.SETUP.value,
                created_at=now, updated_at=now, last_accessed_at=now))
            try:
                db.commit()
            except IntegrityError:
                db.rollback()
                # A concurrent create won the unique (user_id, idempotency_key); use it.
                won = db.execute(
                    select(InterviewSession.session_id).where(
                        InterviewSession.user_id == user_id,
                        InterviewSession.idempotency_key == idempotency_key,
                    )
                ).scalar_one_or_none()
                if won is None:
                    raise
                return won, False
        return session_id, True

    # -- read-only load -------------------------------------------------------

    def load_state(self, session_id: str, user_id: Any) -> SessionManager:
        """Load a session for READ (no save). Touches ``last_accessed_at``.

        Ownership enforced; unknown/foreign → ``SessionNotFoundError``.
        """
        with self._session_factory() as db:
            row = self._row_for(db, session_id, user_id)
            manager = self._manager_from_payload(row.state_payload, row.state_schema_version)
            row.last_accessed_at = utcnow()
            db.commit()
            return manager

    @staticmethod
    def _row_for(db, session_id: str, user_id: Any) -> InterviewSession:
        row = db.get(InterviewSession, session_id)
        if row is None or row.user_id != user_id:
            raise SessionNotFoundError(session_id)
        return row

    # -- mutation boundary ----------------------------------------------------

    @contextmanager
    def mutate(
        self, session_id: str, user_id: Any, *, operation: str | None = None
    ) -> Iterator[SessionManager]:
        """Load → yield a SessionManager to mutate → serialise + save (OCC).

        When ``operation`` is given, a durable lease is claimed first (raising
        ``OperationInProgressError`` if a fresh lease is already held) and released on
        exit, guarding paid provider calls against concurrent duplication. On an
        unexpected error the lease is released and no partial state is saved; a
        stale-version save raises ``SessionConflictError``.
        """
        # 1. Load current version + payload (ownership enforced).
        with self._session_factory() as db:
            row = self._row_for(db, session_id, user_id)
            expected_version = row.version
            manager = self._manager_from_payload(row.state_payload, row.state_schema_version)

        # 2. Claim the operation lease (atomic, recoverable) if requested.
        if operation is not None:
            self._claim_lease(session_id, user_id, operation)

        # 3. Let the caller mutate via SessionManager, then persist.
        try:
            yield manager
            self._save(session_id, user_id, manager.data, expected_version=expected_version)
        except Exception:
            if operation is not None:
                self._release_lease(session_id, user_id, operation)
            raise

    def _claim_lease(self, session_id: str, user_id: Any, operation: str) -> None:
        now = utcnow()
        stale_cutoff = now - timedelta(seconds=self._lease_seconds)
        with self._session_factory() as db:
            # Confirm ownership/existence first (indistinguishable failure otherwise).
            self._row_for(db, session_id, user_id)
            result = db.execute(
                update(InterviewSession)
                .where(
                    InterviewSession.session_id == session_id,
                    InterviewSession.user_id == user_id,
                    (InterviewSession.active_operation.is_(None))
                    | (InterviewSession.operation_leased_at <= stale_cutoff),
                )
                .values(active_operation=operation, operation_leased_at=now)
            )
            db.commit()
            if result.rowcount == 0:
                raise OperationInProgressError(
                    "Another operation is already in progress for this interview.")

    def _release_lease(self, session_id: str, user_id: Any, operation: str) -> None:
        try:
            with self._session_factory() as db:
                db.execute(
                    update(InterviewSession)
                    .where(
                        InterviewSession.session_id == session_id,
                        InterviewSession.user_id == user_id,
                        InterviewSession.active_operation == operation,
                    )
                    .values(active_operation=None, operation_leased_at=None)
                )
                db.commit()
        except Exception:  # noqa: BLE001 - lease release is best-effort; never mask the real error
            pass

    def _save(self, session_id: str, user_id: Any, data: SessionData, *, expected_version: int) -> None:
        payload = encode_session_data(data)
        now = utcnow()
        with self._session_factory() as db:
            result = db.execute(
                update(InterviewSession)
                .where(
                    InterviewSession.session_id == session_id,
                    InterviewSession.user_id == user_id,
                    InterviewSession.version == expected_version,
                )
                .values(
                    state_payload=payload,
                    state_schema_version=SESSION_STATE_SCHEMA_VERSION,
                    version=expected_version + 1,
                    status=self._status_of(data),
                    active_operation=None,
                    operation_leased_at=None,
                    updated_at=now,
                    last_accessed_at=now,
                )
            )
            db.commit()
            if result.rowcount == 0:
                # Either the row vanished (foreign/deleted) or another writer advanced
                # the version. Both are surfaced as a conflict for the caller to reload.
                raise SessionConflictError(
                    "This interview session was changed by another request.")

    # -- discovery / cleanup --------------------------------------------------

    def discard(self, session_id: str, user_id: Any) -> None:
        """Delete a user-owned in-progress session (no error if absent/foreign)."""
        with self._session_factory() as db:
            row = db.get(InterviewSession, session_id)
            if row is not None and row.user_id == user_id:
                db.delete(row)
                db.commit()

    def count_stale_sessions(self, before) -> int:
        """Count durable sessions not accessed since ``before`` (dry-run helper)."""
        with self._session_factory() as db:
            return int(db.execute(
                select(func.count()).select_from(InterviewSession)
                .where(InterviewSession.last_accessed_at < before)
            ).scalar_one())

    def cleanup_stale_sessions(self, before) -> int:
        """Delete IN-PROGRESS sessions untouched since ``before``; return the count.

        Operational retention only — this NEVER touches completed interview history
        (a separate, user-owned store). Recent/active interviews (accessed on or after
        ``before``) are preserved. The caller derives ``before`` from a retention
        policy (e.g. ``constants.INTERVIEW_SESSION_RETENTION_DAYS``).
        """
        n = self.count_stale_sessions(before)
        if n:
            with self._session_factory() as db:
                db.execute(
                    delete(InterviewSession).where(InterviewSession.last_accessed_at < before)
                )
                db.commit()
        return n

    def list_active(self, user_id: Any) -> list[SessionSummary]:
        """Safe summaries of a user's resumable sessions (newest first).

        Excludes finished interviews (report already generated) — those live in
        completed history. Returns only safe fields (never JD/background/answers).
        """
        terminal = {SessionState.REPORT_READY.value}
        with self._session_factory() as db:
            rows = db.execute(
                select(InterviewSession)
                .where(InterviewSession.user_id == user_id)
                .order_by(InterviewSession.updated_at.desc())
            ).scalars().all()
            summaries: list[SessionSummary] = []
            for row in rows:
                if row.status in terminal:
                    continue
                payload = row.state_payload or {}
                config = payload.get("config") or {}
                summaries.append(SessionSummary(
                    session_id=row.session_id,
                    target_role=(config or {}).get("target_role"),
                    state=row.status,
                    question_number=int(payload.get("current_question_number") or 0),
                    questions_planned=(config or {}).get("number_of_questions"),
                    updated_at=row.updated_at.isoformat() if row.updated_at else None,
                ))
            return summaries
