"""Worker-side privacy operations (P10B-W10.10): execution of an Admin-requested account deletion, bounded preparation-run backfill and
checkpoint purge retries. Everything delegates to the SAME domain services candidates use (``AccountDeletionService``): there is no
separate admin deletion engine. Every step is replay-safe (a job can run again after a crash)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable

from sqlalchemy import select

from src.application import admin_audit as A
from src.application.account_deletion_service import AccountDeletionService, DeletionIncomplete
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
    # W12.4D-F1R: erasure is never postponed by an unresolved provider subscription. Personal and content data are erased; only the minimum billing reference
    # needed to finish the provider obligation is retained (recorded with a basis code and flagged for legal review), and purged when every subscription is terminal.
    from src.billing.closure import ClosureService
    preserve = ClosureService(rt.session_factory).begin_retained_erasure(subject, request_public_id)
    try:
        summary = service.delete_account(subject, preserve_billing_reference=preserve)       # idempotent: a missing user is a no-op
    except DeletionIncomplete:
        raise RetryableJobError("unavailable")                               # a private file could not be deleted: nothing was committed, the run is repeatable
    # 05E: purge EVERY run still indexed for this owner, whatever its state. A crash between the SQL commit and the checkpoint purge leaves rows in state
    # "started"/"ready" (not only "purge_failed"); looking at purge_failed alone would loop on them until the attempts ran out.
    pending = [(rid, subject) for rid in index.run_ids_for_owner(subject)] + [(rid, subject) for rid in summary.purge_failed_run_ids]
    pending = list(dict.fromkeys(pending))
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
    # 05E: completion requires the VERIFIED erasure: no row anywhere in the schema may still reference the account (the retained anonymised billing shell and this very
    # request row are the documented exceptions). A deterministic residual is not "completed": it fails visibly after the bounded attempts.
    from src.privacy import erasure

    residual = erasure.residual_for_user(rt.session_factory, subject, retain_billing=preserve, retain_requests=True)
    if residual:
        log.warning("privacy deletion residual references remain: %s", sorted(residual))      # table.column names and counts only
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
