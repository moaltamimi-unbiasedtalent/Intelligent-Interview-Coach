"""One database transaction for completed History, runtime, shares and audit.

Lock order is runtime -> completed History -> shares -> audit. Runtime-backed
History saves use the same order. SQLite takes its write lock before any reads;
PostgreSQL locks rows. No model, notification or other external I/O runs here.
"""
from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError

from src.application.errors import UnavailableServiceError
from src.interview.session_repository import (
    OperationInProgressError, SessionConflictError, SessionNotFoundError,
    SetupOutcomeUncertainError, begin_write_transaction,
)
from src.persistence import AuditEvent, Interview, InterviewSession, ShareGrant


def _common_factory(repo, store, sharing, audit):
    factories = [getattr(value, "session_factory", None) for value in (repo, store, sharing, audit)]
    engine = getattr(factories[0], "kw", {}).get("bind")
    if engine is None or engine.dialect.name not in {"sqlite", "postgresql"} or any(
        getattr(sf, "kw", {}).get("bind") is not engine or getattr(sf, "kw", {}).get("binds")
        for sf in factories
    ):
        raise UnavailableServiceError("Coordinated deletion is unavailable for these stores.")
    return factories[0], engine


def _confirmed_commit(sf, user_id, report_id, source_id, audit_id, attempt_id):
    """Read back this exact attempted audit after a lost commit acknowledgement."""
    try:
        with sf() as db:
            event = db.get(AuditEvent, audit_id)
            return bool(
                event is not None and event.actor_user_id == user_id
                and event.request_id == attempt_id
                and event.event_type == "interview.deleted" and event.result == "success"
                and event.target_type == "interview" and event.target_id == str(report_id)
                and db.get(Interview, report_id) is None
                and (source_id is None or db.get(InterviewSession, source_id) is None)
                and not db.scalar(select(func.count()).select_from(ShareGrant).where(
                    ShareGrant.owner_user_id == user_id, ShareGrant.resource_type == "interview_report",
                    ShareGrant.resource_id == str(report_id), ShareGrant.status == "active"))
            )
    except Exception:  # noqa: BLE001 - unknown commit outcome must never become success
        return False


def delete_completed_interview(*, repo, store, sharing, audit, user_id: int, report_id: int) -> bool:
    sf, engine = _common_factory(repo, store, sharing, audit)
    audit_id = None
    commit_attempted = False
    source_id = None
    # Existing audit column; independent of reusable SQLite row ids and HTTP ids.
    attempt_id = uuid.uuid4().hex
    try:
        # Freeze identifiers/version/lease only. A later change must cause refusal,
        # not a refreshed snapshot that silently authorizes deletion of new work.
        with sf() as read:
            target = repo.deletion_target_in_transaction(read, user_id, report_id)
            if target is None:
                return False
            source_id = target.source_session_id
            expected = store.deletion_identity(read, source_id) if source_id is not None else None
        with sf() as db:
            for model in (InterviewSession, Interview, ShareGrant, AuditEvent):
                if db.get_bind(mapper=model) is not engine:
                    raise UnavailableServiceError("Coordinated deletion is unavailable for these stores.")
            begin_write_transaction(db)
            row = (store.lock_for_history_deletion(db, source_id, user_id, expected)
                   if source_id is not None else None)
            current = repo.deletion_target_in_transaction(db, user_id, report_id, lock=True)
            if current is None:
                return False
            if current.source_session_id != source_id:
                raise SessionConflictError("This interview changed before deletion.")
            store.discard_in_transaction(db, row, user_id)
            repo.delete_interview_in_transaction(db, user_id, report_id)
            sharing.invalidate_in_transaction(db, owner_user_id=user_id, resource_id=str(report_id))
            audit_id = audit.record_interview_deletion_in_transaction(
                db, actor_user_id=user_id, interview_id=report_id, attempt_id=attempt_id)
            commit_attempted = True
            db.commit()
        return True
    except (OperationInProgressError, SessionConflictError, SessionNotFoundError, SetupOutcomeUncertainError):
        raise
    except OperationalError as exc:
        # A competing SQLite writer is a controlled conflict, not permission to
        # retry the transaction automatically or to commit a partial deletion.
        if engine.dialect.name == "sqlite" and getattr(exc.orig, "sqlite_errorcode", None) in {5, 6, 517}:
            raise SessionConflictError("This interview is being changed. Reload before retrying.") from None
        if commit_attempted and audit_id is not None and _confirmed_commit(sf, user_id, report_id, source_id, audit_id, attempt_id):
            return True
        raise UnavailableServiceError("Deletion could not be confirmed. Reload before retrying.") from None
    except Exception:  # noqa: BLE001 - never expose SQL, bindings or injected exception text
        if commit_attempted and audit_id is not None and _confirmed_commit(sf, user_id, report_id, source_id, audit_id, attempt_id):
            return True
        raise UnavailableServiceError("Deletion could not be confirmed. Reload before retrying.") from None
