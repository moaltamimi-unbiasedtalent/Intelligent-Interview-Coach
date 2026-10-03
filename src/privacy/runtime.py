"""Worker-side privacy operations (P10B-W10.10): execution of an Admin-requested account deletion, bounded preparation-run backfill and
checkpoint purge retries. Everything delegates to the SAME domain services candidates use (``AccountDeletionService``): there is no
separate admin deletion engine. Every step is replay-safe (a job can run again after a crash)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable

from sqlalchemy import select

from src.application import admin_audit as A
from src.application.account_deletion_service import AccountDeletionService
from src.jobs.registry import PermanentJobError, RetryableJobError
from src.persistence import PrivacyRequest as R, User, utcnow
from src.privacy import policy as P
from src.privacy.preparation import PreparationRunIndex, backfill_batch
from src.privacy.requests import PrivacyRequestService

log = logging.getLogger("ask4mo.privacy.runtime")


@dataclass
class PrivacyRuntime:
    session_factory: Any
    adapter: Any = None            # CheckpointAdapter (purge_run / delete_run / owner_of)
    doc_store: Any = None
    audit_repository: Any = None
    jobs: Any = None               # JobService (to chain backfill batches)
    clock: Callable = utcnow


def _rt(ctx) -> PrivacyRuntime:
    rt = getattr(ctx.services, "privacy", None) if ctx.services is not None else None
    if rt is None:
        raise PermanentJobError("configuration_error")
    return rt


def _completion_audit(rt: PrivacyRuntime, ctx, public_id: str, event: str, **context) -> dict | None:
    return A.build_audit(event_type=event, actor_user_id=ctx.created_by_user_id, request_id=None, target_type="privacy_request",
                         target_id=public_id, **context)


def run_account_delete(request_public_id: str, ctx) -> None:
    rt = _rt(ctx)
    requests = PrivacyRequestService(rt.session_factory, rt.clock)
    with rt.session_factory() as s:
        r = s.scalar(select(R).where(R.public_id == request_public_id))
        if r is None or r.request_type != "deletion":
            raise PermanentJobError("invalid_payload")
        if r.status in ("completed", "closed"):
            return                                                          # replay after completion: nothing to do
        subject = r.subject_user_id
        if subject is None:
            raise PermanentJobError("invalid_payload")
        user = s.get(User, subject)
        if user is not None and user.platform_role != "user":
            raise PermanentJobError("unsupported")                           # admin accounts are never deleted through a request
    index = PreparationRunIndex(rt.session_factory, rt.clock)
    service = AccountDeletionService(rt.session_factory, document_store=rt.doc_store, agent_service=rt.adapter,
                                     audit_repository=rt.audit_repository, preparation_index=index,
                                     retain_privacy_requests=True)
    summary = service.delete_account(subject)                                # idempotent: a missing user is a no-op
    pending = index.pending_purge(subject) + [(rid, subject) for rid in summary.purge_failed_run_ids]
    leftover = []
    for run_id, _ in pending:
        try:
            if rt.adapter is None or not rt.adapter.purge_run(run_id):
                raise RuntimeError("not purged")
            index.remove(run_id)
        except Exception:  # noqa: BLE001 - never record text; keep the row for the next attempt
            index.mark(run_id, "purge_failed")
            leftover.append(run_id)
    if leftover:
        raise RetryableJobError("unavailable")                               # NOT complete: some checkpoint data is still there
    leftover_known = index.run_ids_for_owner(subject)
    if leftover_known:
        raise RetryableJobError("unavailable")
    requests.complete_system(request_public_id, "deletion_performed",
                             audit=_completion_audit(rt, ctx, request_public_id, A.ADMIN_PRIVACY_DELETION_COMPLETED))


def run_backfill(after_id: int, ctx) -> None:
    rt = _rt(ctx)
    if rt.adapter is None:
        raise PermanentJobError("configuration_error")
    index = PreparationRunIndex(rt.session_factory, rt.clock)
    out = backfill_batch(index, rt.adapter, rt.session_factory, after_memory_id=after_id)
    log.info("preparation backfill batch: %s", {k: v for k, v in out.items() if k != "next_after_id"})
    if out["next_after_id"] is not None and rt.jobs is not None:             # chain the next bounded batch (idempotent key)
        rt.jobs.enqueue(P.JOB_BACKFILL, {"after_id": out["next_after_id"]}, idempotency_key=f"backfill:{out['next_after_id']}",
                        actor_user_id=ctx.created_by_user_id)


def run_purge(run_id: str, ctx) -> None:
    rt = _rt(ctx)
    index = PreparationRunIndex(rt.session_factory, rt.clock)
    if index.owner_of(run_id) is None:
        return                                                                # already purged and un-indexed
    try:
        if rt.adapter is None or not rt.adapter.purge_run(run_id):
            raise RuntimeError("not purged")
    except Exception:  # noqa: BLE001
        index.mark(run_id, "purge_failed")
        raise RetryableJobError("unavailable")
    index.remove(run_id)
