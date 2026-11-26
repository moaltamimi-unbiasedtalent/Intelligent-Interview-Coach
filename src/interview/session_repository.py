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
- **Operation lease** — the existing version advances on acquisition and the lease
  value binds saves/releases to that generation. An undispatched lease is reclaimable.
- **Setup intent** — committed in the existing lease column before yielding setup.
  Possible dispatches and uncertain outcomes remain held across expiry and restart.

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


def _error_category(exc: BaseException) -> str:
    """Sanitized diagnostic code for an interview mutation failure (never the raw message)."""
    name = type(exc).__name__
    if name == "SessionConflictError":
        return "occ_conflict"
    if name in ("OperationInProgressError", "SetupInProgressError"):
        return "lease_conflict"
    if name == "SessionNotFoundError":
        return "not_found"
    try:
        from src.observability.sanitizer import error_category
        return error_category(exc)
    except Exception:  # noqa: BLE001
        return "unknown_error"


from src.interview.session_codec import (  # noqa: E402
    SESSION_STATE_SCHEMA_VERSION,
    decode_session_data,
    encode_session_data,
)
from src.persistence import InterviewSession, utcnow
from src.session_manager import NAMESPACE, SessionData, SessionManager, SessionState


def begin_write_transaction(db) -> None:
    """Serialize short SQLite writes; PostgreSQL uses explicit row locks instead.

    Call only on a fresh session, before any query. No provider I/O belongs here.
    SQLite's legacy driver otherwise does not begin a transaction for a SELECT.
    """
    if db.get_bind().dialect.name == "sqlite":
        db.connection().exec_driver_sql("BEGIN IMMEDIATE")

__all__ = [
    "DurableInterviewSessionStore",
    "SessionNotFoundError",
    "SessionConflictError",
    "OperationInProgressError",
    "SetupInProgressError",
    "SetupOutcomeUncertainError",
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


class SetupInProgressError(OperationInProgressError):
    """A setup with committed dispatch intent is still within its active window."""


class SetupOutcomeUncertainError(Exception):
    """A durable setup intent exists whose outcome needs reconciliation before retry."""


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
        observability: Any | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._clock = clock
        self._lease_seconds = lease_seconds
        # Optional, best-effort telemetry sink (Phase 7D). Defaults to a genuine no-op so the
        # store has zero external dependency; NEVER receives candidate content — only the
        # operation label, opaque session id, status, latency and safe durability signals.
        if observability is None:
            from src.observability.noop import NoOpObservabilitySink
            observability = NoOpObservabilitySink()
        self._obs = observability

    # -- internal helpers -----------------------------------------------------

    @property
    def session_factory(self):
        return self._session_factory

    @staticmethod
    def deletion_identity(db, session_id: str):
        return db.execute(select(
            InterviewSession.user_id, InterviewSession.version,
            InterviewSession.active_operation, InterviewSession.operation_leased_at,
        ).where(InterviewSession.session_id == session_id)).first()

    def lock_for_history_deletion(self, db, session_id: str, user_id: Any, expected):
        """Lock runtime before History; compare the earlier immutable observation."""
        row = db.scalar(select(InterviewSession).where(
            InterviewSession.session_id == session_id).with_for_update())
        if row is None:
            if expected is not None:
                raise SessionConflictError("This interview changed before deletion.")
            return None
        observed = (row.user_id, row.version, row.active_operation, row.operation_leased_at)
        if row.user_id != user_id or expected is None or observed != tuple(expected):
            raise SessionConflictError("This interview changed before deletion.")
        self._guard_setup_intent(row)
        leased_at = row.operation_leased_at
        if leased_at is not None and leased_at.tzinfo is None:
            leased_at = leased_at.replace(tzinfo=utcnow().tzinfo)
        if row.active_operation is not None and (
            leased_at is None or leased_at > utcnow() - timedelta(seconds=self._lease_seconds)
        ):
            raise OperationInProgressError("Another interview operation is in progress.")
        return row

    @staticmethod
    def discard_in_transaction(db, row, user_id: Any) -> None:
        """Fenced deletion using the caller's transaction; never commit or release a lease."""
        if row is None:
            return
        result = db.execute(delete(InterviewSession).where(
            InterviewSession.session_id == row.session_id,
            InterviewSession.user_id == user_id,
            InterviewSession.version == row.version,
            InterviewSession.active_operation == row.active_operation,
            InterviewSession.active_operation.is_(None) | (
                (InterviewSession.active_operation != "create")
                & ~InterviewSession.active_operation.endswith(":dispatch")
                & ~InterviewSession.active_operation.endswith(":hold")
            ),
        ).execution_options(synchronize_session=False))
        if result.rowcount != 1:
            raise SessionConflictError("This interview changed before deletion.")

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

    def _emit(self, operation: str, status: str, *, session_id: str = "",
              duration_ms: int | None = None, failure_category: str | None = None,
              metadata: dict | None = None) -> None:
        """Best-effort interview telemetry. Session id is an opaque uuid; NEVER any candidate
        content, answer text, JD/CV or scores from here (§22/§23). Never raises."""
        try:
            self._obs.interview_event(
                session_id=session_id or "unknown", operation=operation, status=status,
                duration_ms=duration_ms, failure_category=failure_category, metadata=metadata)
        except Exception:  # noqa: BLE001 - telemetry must never affect the interview
            pass

    # -- creation -------------------------------------------------------------

    def create(self, user_id: Any, *, opportunity_id: int | None = None) -> str:
        """Create a fresh empty durable session and return its opaque id.

        ``opportunity_id`` (P10B Wave 6) is an OPTIONAL owner-scoped organising link; the caller
        must have validated ownership. NULL for standalone sessions."""
        session_id = self._new_id()
        payload = encode_session_data(SessionData())
        now = utcnow()
        with self._session_factory() as db:
            db.add(InterviewSession(
                session_id=session_id, user_id=user_id, idempotency_key=None,
                opportunity_id=opportunity_id,
                state_payload=payload, state_schema_version=SESSION_STATE_SCHEMA_VERSION,
                version=1, status=SessionState.SETUP.value,
                created_at=now, updated_at=now, last_accessed_at=now))
            db.commit()
        return session_id

    def create_or_get(self, user_id: Any, idempotency_key: str, *,
                      opportunity_id: int | None = None) -> tuple[str, bool]:
        """Return ``(session_id, created)`` for a user-scoped idempotency key.

        Durable: a repeat with the same ``(user_id, idempotency_key)`` returns the
        SAME session (``created=False``) even after a backend restart. A different key
        or user yields a distinct session. Concurrent first-creates race safely on the
        unique constraint (the loser re-reads the winner's row).
        """
        statement = self._idempotent_session_query(user_id, idempotency_key)
        with self._session_factory() as db:
            existing = db.execute(statement).scalar_one_or_none()
            if existing is not None:
                self._emit("create", "idempotent_hit", session_id=existing,
                           metadata={"idempotency_hit": True})
                return existing, False

            session_id = self._new_id()
            payload = encode_session_data(SessionData())
            now = utcnow()
            db.add(InterviewSession(
                session_id=session_id, user_id=user_id, idempotency_key=idempotency_key,
                opportunity_id=opportunity_id,
                state_payload=payload, state_schema_version=SESSION_STATE_SCHEMA_VERSION,
                version=1, status=SessionState.SETUP.value,
                created_at=now, updated_at=now, last_accessed_at=now))
            try:
                db.commit()
            except IntegrityError:
                db.rollback()
                # A concurrent create won the unique (user_id, idempotency_key); use it.
                won = db.execute(statement).scalar_one_or_none()
                if won is None:
                    raise
                self._emit("create", "idempotent_hit", metadata={"idempotency_hit": True,
                                                                  "race_resolved": True})
                return won, False
        self._emit("create", "created", session_id=session_id, metadata={"idempotency_hit": False})
        return session_id, True

    @staticmethod
    def _idempotent_session_query(user_id: Any, idempotency_key: str):
        return select(InterviewSession.session_id).where(
            InterviewSession.user_id == user_id,
            InterviewSession.idempotency_key == idempotency_key,
        )

    def find_idempotent_session(self, user_id: Any, idempotency_key: str) -> str | None:
        """Look up an existing session by owner and creation key without inserting one."""
        with self._session_factory() as db:
            return db.execute(self._idempotent_session_query(user_id, idempotency_key)).scalar_one_or_none()

    def opportunity_id_for(self, session_id: str, user_id: Any) -> int | None:
        """The owner-scoped Opportunity link for a session, or None (P10B Wave 6). A foreign/
        unknown session returns None (never another user's data)."""
        with self._session_factory() as db:
            row = db.get(InterviewSession, session_id)
            if row is None or row.user_id != user_id:
                return None
            return row.opportunity_id

    # -- read-only load -------------------------------------------------------

    def load_state(self, session_id: str, user_id: Any) -> SessionManager:
        """Load a session for READ (no save). Touches ``last_accessed_at``.

        Ownership enforced; unknown/foreign → ``SessionNotFoundError``.
        """
        with self._session_factory() as db:
            row = self._row_for(db, session_id, user_id)
            self._guard_setup_intent(row)
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
        ``OperationInProgressError`` if a fresh lease is already held). Saves and
        releases match that exact acquisition. A setup dispatch intent is committed
        before yielding. Failure after intent retains a hold and any available
        usage/results. A successful save clears the intent atomically with the state.
        """
        lease = None
        # Every acquisition advances the durable version, fencing earlier owners.
        if operation is not None:
            try:
                lease = self._claim_lease(session_id, user_id, operation)
            except OperationInProgressError:
                self._emit(operation or "mutate", "lease_conflict", session_id=session_id,
                           metadata={"lease_conflict": True})
                raise

        import time as _time
        started = _time.perf_counter()
        try:
            with self._session_factory() as db:
                row = self._row_for(db, session_id, user_id)
                self._guard_setup_intent(row)
                if row.active_operation != lease:
                    raise SessionConflictError("The operation lease changed before loading state.")
                expected_version = row.version
                manager = self._manager_from_payload(row.state_payload, row.state_schema_version)
            usage_before = len(manager.data.usage_records)
            if operation == "create" and manager.data.state == SessionState.SETUP and not manager.data.questions:
                lease = self._begin_setup_dispatch(session_id, user_id, lease, expected_version)
            yield manager
            self._save(session_id, user_id, manager.data, expected_version=expected_version, lease=lease)
            self._record_usage_facts(session_id, user_id, manager.data, usage_before, operation)
        except BaseException as exc:
            uncertain = lease is not None and lease.endswith(":dispatch")
            if uncertain:
                self._retain_setup_hold(session_id, user_id, lease, expected_version, manager.data)
            elif lease is not None:
                self._release_lease(session_id, user_id, lease)
            self._emit(operation or "mutate", "error", session_id=session_id,
                       duration_ms=int((_time.perf_counter() - started) * 1000),
                       failure_category=_error_category(exc),
                       metadata={"occ_conflict": type(exc).__name__ == "SessionConflictError"})
            if uncertain and isinstance(exc, Exception):
                raise SetupOutcomeUncertainError("Practice setup needs reconciliation before another attempt.") from exc
            raise
        self._emit(operation or "mutate", "ok", session_id=session_id,
                   duration_ms=int((_time.perf_counter() - started) * 1000))

    def _record_usage_facts(self, session_id: str, user_id: Any, data: SessionData, before: int, operation: str | None) -> None:
        """P10B-W10.12: record each NEW canonical UsageRecord of this session ONCE (after the state commit). Best-effort; never raises."""
        new = list(data.usage_records[before:])
        if not new:
            return
        try:
            from src.reporting.telemetry import record_practice_usage

            record_practice_usage(self._session_factory, int(user_id), session_id, before, new, operation)
        except Exception:  # noqa: BLE001
            pass

    def _guard_setup_intent(self, row: InterviewSession) -> None:
        """A possible dispatch is never made retryable by lease expiry.

        Old unqualified ``create`` leases have no proof of non-dispatch. New leases
        encode operation and acquisition generation in the existing String(64).
        Only a committed ``:dispatch`` marker permits the setup body to run.
        """
        active = row.active_operation or ""
        if active == "create" or active.endswith((":dispatch", ":hold")):
            if active.endswith(":hold") or row.operation_leased_at is None:
                raise SetupOutcomeUncertainError("The setup outcome is uncertain.")
            leased_at = row.operation_leased_at
            if leased_at.tzinfo is None:
                leased_at = leased_at.replace(tzinfo=utcnow().tzinfo)
            if leased_at <= utcnow() - timedelta(seconds=self._lease_seconds):
                raise SetupOutcomeUncertainError("The setup outcome is uncertain.")
            raise SetupInProgressError("Practice setup is already in progress.")

    def _begin_setup_dispatch(self, session_id: str, user_id: Any, lease: str, expected_version: int) -> str:
        intent = f"{lease}:dispatch"
        with self._session_factory() as db:
            result = db.execute(update(InterviewSession).where(
                InterviewSession.session_id == session_id, InterviewSession.user_id == user_id,
                InterviewSession.version == expected_version, InterviewSession.active_operation == lease,
                InterviewSession.operation_leased_at > utcnow() - timedelta(seconds=self._lease_seconds),
            ).values(active_operation=intent))
            if result.rowcount != 1:
                raise SessionConflictError("The operation lease changed before dispatch.")
            db.commit()
        # A commit failure or lost acknowledgement exits before yielding to the caller.
        return intent

    def _retain_setup_hold(self, session_id: str, user_id: Any, lease: str,
                           expected_version: int, data: SessionData) -> None:
        try:
            with self._session_factory() as db:
                db.execute(update(InterviewSession).where(
                    InterviewSession.session_id == session_id, InterviewSession.user_id == user_id,
                    InterviewSession.version == expected_version, InterviewSession.active_operation == lease,
                ).values(
                    active_operation=lease.removesuffix(":dispatch") + ":hold",
                    state_payload=encode_session_data(data), status=self._status_of(data),
                    version=expected_version + 1, updated_at=utcnow(),
                ))
                db.commit()
        except Exception:  # noqa: BLE001 - the earlier committed intent remains a durable hold
            pass

    def _claim_lease(self, session_id: str, user_id: Any, operation: str) -> str:
        now = utcnow()
        stale_cutoff = now - timedelta(seconds=self._lease_seconds)
        with self._session_factory() as db:
            # Confirm ownership/existence first (indistinguishable failure otherwise).
            row = self._row_for(db, session_id, user_id)
            self._guard_setup_intent(row)
            generation = row.version + 1
            lease = f"{operation}@{generation}"
            if len(lease) + len(":dispatch") > 64:
                raise ValueError("The operation identity exceeds the lease field bound.")
            result = db.execute(
                update(InterviewSession)
                .where(
                    InterviewSession.session_id == session_id,
                    InterviewSession.user_id == user_id,
                    InterviewSession.version == row.version,
                    InterviewSession.active_operation == row.active_operation,
                    (InterviewSession.active_operation.is_(None))
                    | (
                        (InterviewSession.operation_leased_at <= stale_cutoff)
                        & (InterviewSession.active_operation != "create")
                        & ~InterviewSession.active_operation.endswith(":dispatch")
                        & ~InterviewSession.active_operation.endswith(":hold")
                    ),
                )
                .values(active_operation=lease, operation_leased_at=now, version=generation)
                .execution_options(synchronize_session=False)
            )
            db.commit()
            if result.rowcount == 0:
                db.expire_all()
                self._guard_setup_intent(self._row_for(db, session_id, user_id))
                raise OperationInProgressError(
                    "Another operation is already in progress for this interview.")
        return lease

    def _release_lease(self, session_id: str, user_id: Any, lease: str) -> None:
        if lease.endswith((":dispatch", ":hold")):
            return
        try:
            with self._session_factory() as db:
                db.execute(
                    update(InterviewSession)
                    .where(
                        InterviewSession.session_id == session_id,
                        InterviewSession.user_id == user_id,
                        InterviewSession.active_operation == lease,
                    )
                    .values(active_operation=None, operation_leased_at=None)
                )
                db.commit()
        except Exception:  # noqa: BLE001 - lease release is best-effort; never mask the real error
            pass

    def _save(self, session_id: str, user_id: Any, data: SessionData, *, expected_version: int,
              lease: str | None = None) -> None:
        payload = encode_session_data(data)
        now = utcnow()
        with self._session_factory() as db:
            result = db.execute(
                update(InterviewSession)
                .where(
                    InterviewSession.session_id == session_id,
                    InterviewSession.user_id == user_id,
                    InterviewSession.version == expected_version,
                    InterviewSession.active_operation == lease,
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
        """Delete an owned session, preserving unresolved setup intents and holds."""
        with self._session_factory() as db:
            row = db.get(InterviewSession, session_id)
            if row is not None and row.user_id == user_id:
                self._guard_setup_intent(row)
                result = db.execute(delete(InterviewSession).where(
                    InterviewSession.session_id == session_id,
                    InterviewSession.user_id == user_id,
                    InterviewSession.version == row.version,
                    InterviewSession.active_operation == row.active_operation,
                    InterviewSession.active_operation.is_(None) | (
                        (InterviewSession.active_operation != "create")
                        & ~InterviewSession.active_operation.endswith(":dispatch")
                        & ~InterviewSession.active_operation.endswith(":hold")
                    ),
                ).execution_options(synchronize_session=False))
                db.commit()
                if result.rowcount == 0:
                    db.expire_all()
                    current = db.get(InterviewSession, session_id)
                    if current is None or current.user_id != user_id:
                        return
                    self._guard_setup_intent(current)
                    raise SessionConflictError("This interview changed before it could be deleted.")

    def count_stale_sessions(self, before) -> int:
        """Count idle, unleased sessions not accessed since ``before`` (dry-run)."""
        with self._session_factory() as db:
            return int(db.execute(
                select(func.count()).select_from(InterviewSession)
                .where(InterviewSession.last_accessed_at < before, InterviewSession.active_operation.is_(None))
            ).scalar_one())

    def cleanup_stale_sessions(self, before) -> int:
        """Delete stale durable runtime interview-session rows (those whose
        ``last_accessed_at`` is older than ``before``); return the count.

        This is time-based operational retention over the ``interview_sessions`` table,
        which holds only resumable runtime state — it NEVER touches completed interview
        history (a separate, user-owned store). Rows accessed on or after ``before``
        are preserved. The caller derives ``before`` from a retention policy (e.g.
        ``constants.INTERVIEW_SESSION_RETENTION_DAYS``).
        """
        n = self.count_stale_sessions(before)
        if n:
            with self._session_factory() as db:
                db.execute(
                    delete(InterviewSession).where(
                        InterviewSession.last_accessed_at < before, InterviewSession.active_operation.is_(None))
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
                if (row.active_operation or "").endswith((":dispatch", ":hold")) or row.active_operation == "create":
                    continue
                if row.status == SessionState.SETUP.value and not payload.get("questions"):
                    continue
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
