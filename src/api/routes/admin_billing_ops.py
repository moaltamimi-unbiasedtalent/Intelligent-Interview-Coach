"""Admin billing operations (W12.4D-E): diagnostics and CONTROLLED recovery for provider-managed billing. Every route declares an explicit permission.

Reads need ``platform.billing.read``. A recovery action needs ``platform.jobs.manage`` (the existing permission for retrying background work: the
billing admin can inspect but not re-drive processing; no new permission was added and the registry stays at 43). A recovery action re-drives the
EXISTING verified pipeline for one of OUR records: it cannot forge a provider event, edit or delete a financial fact, grant access, accept a caller-supplied
provider id, or run a financial operation. With the runtime Null provider-state reader every action is REFUSED (never reported as success).
"""

from __future__ import annotations

import re
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.api.dependencies import get_audit_repository, get_billing_operations, get_provider_event_service, get_request_id, require_permission
from src.api.rate_limit import enforce, user_key
from src.application import admin_audit as A
from src.application import admin_permissions as perm
from src.billing.operations import BillingOperations, OpsValidationError

router = APIRouter(prefix="/admin/billing/operations", tags=["admin-billing-operations"])
_KEY = re.compile(r"^[A-Za-z0-9_-]{8,64}$")


class Page(BaseModel):
    items: list[dict[str, Any]]
    total: int
    page: int
    page_size: int


class RecoveryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=5, max_length=300)

    @field_validator("reason")
    @classmethod
    def _clean(cls, v: str) -> str:
        v = " ".join(v.split())
        if len(v) < 5 or any(ord(c) < 32 for c in v):
            raise ValueError("A reason of at least 5 plain characters is required.")
        return v


class RecoveryResult(BaseModel):
    reference: str
    action: str
    status: str
    result: str | None = None
    replayed: bool = False


def _guard(fn):
    try:
        return fn()
    except OpsValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("/overview", summary="Billing operations overview (verified local state; no revenue, no provider claim)")
def overview(_p=Depends(require_permission(perm.BILLING_READ)), ops: BillingOperations = Depends(get_billing_operations)) -> dict[str, Any]:
    return ops.overview()


@router.get("/readiness", summary="Truthful provider readiness (booleans and fixed states only)")
def readiness(_p=Depends(require_permission(perm.BILLING_READ)), ops: BillingOperations = Depends(get_billing_operations)) -> dict[str, Any]:
    return ops.readiness()


@router.get("/subscriptions", response_model=Page, summary="Provider-managed subscriptions (masked provider ids, no personal data)")
def subscriptions(state: str | None = None, page: int = Query(default=1, ge=1, le=100000), page_size: int = Query(default=25, ge=1, le=100),
                  _p=Depends(require_permission(perm.BILLING_READ)), ops: BillingOperations = Depends(get_billing_operations)) -> Page:
    return Page(**_guard(lambda: ops.subscriptions(state=state, page=page, page_size=page_size)))


@router.get("/checkouts", response_model=Page, summary="Checkout attempts (no URL, no session id)")
def checkouts(status: str | None = None, page: int = Query(default=1, ge=1, le=100000), page_size: int = Query(default=25, ge=1, le=100),
              _p=Depends(require_permission(perm.BILLING_READ)), ops: BillingOperations = Depends(get_billing_operations)) -> Page:
    return Page(**_guard(lambda: ops.checkouts(status=status, page=page, page_size=page_size)))


@router.get("/events", response_model=Page, summary="Verified webhook events (no body, no signature)")
def events(status: str | None = None, event_type: str | None = None, environment: str | None = None, page: int = Query(default=1, ge=1, le=100000),
           page_size: int = Query(default=25, ge=1, le=100), _p=Depends(require_permission(perm.BILLING_READ)),
           ops: BillingOperations = Depends(get_billing_operations)) -> Page:
    return Page(**_guard(lambda: ops.events(status=status, event_type=event_type, environment=environment, page=page, page_size=page_size)))


@router.get("/events/{reference}", summary="One event: lifecycle, attempts, failure category and reconciliation outcome (no raw payload)")
def event_detail(reference: str, request: Request, principal=Depends(require_permission(perm.BILLING_READ)),
                 ops: BillingOperations = Depends(get_billing_operations), audit=Depends(get_audit_repository)) -> dict[str, Any]:
    out = ops.event_detail(reference[:64])
    if out is None:
        raise HTTPException(status_code=404, detail="Not found.")
    _record_view(audit, principal, request, reference)         # viewing one financial event is audited (best effort; never changes the response)
    return out


@router.get("/reconciliation", summary="Reconciliation status and items that need attention")
def reconciliation(_p=Depends(require_permission(perm.BILLING_READ)), ops: BillingOperations = Depends(get_billing_operations)) -> dict[str, Any]:
    return ops.reconciliation()


@router.get("/recovery-actions", response_model=Page, summary="Operator recovery history")
def recovery_actions(page: int = Query(default=1, ge=1, le=100000), page_size: int = Query(default=25, ge=1, le=100),
                     _p=Depends(require_permission(perm.BILLING_READ)), ops: BillingOperations = Depends(get_billing_operations)) -> Page:
    return Page(**_guard(lambda: ops.recovery_actions(page=page, page_size=page_size)))


def _record_view(audit_repo, principal, request: Request, reference: str) -> None:
    try:
        audit_repo.record(**A.build_audit(event_type=A.ADMIN_BILLING_EVENT_VIEWED, actor_user_id=principal.user_id, request_id=get_request_id(request),
                                          target_type="billing_provider_event", target_id=reference[:64]))
    except Exception:  # noqa: BLE001
        pass


def _audit(request: Request, principal, action: str, reference: str, reason: str) -> dict:
    return A.build_audit(event_type=A.ADMIN_BILLING_RECOVERY, actor_user_id=principal.user_id, request_id=get_request_id(request),
                         target_type="billing_provider_link" if action == "reconcile_link" else "billing_provider_event", target_id=reference[:64], reason=reason)


def _recover(action: str, reference: str, body: RecoveryRequest, key: str | None, principal, svc, audit: dict) -> RecoveryResult:
    if not key or not _KEY.match(key):
        raise HTTPException(status_code=422, detail="An Idempotency-Key of 8 to 64 letters, digits, underscores or hyphens is required.")
    enforce("billing_recovery_user", user_key(principal.user_id))
    from src.billing.reconcile import RecoveryKeyConflict
    try:
        out = svc.recover(action, reference[:64], actor_user_id=principal.user_id, reason=body.reason, idempotency_key=key, audit=audit)
    except RecoveryKeyConflict:
        raise HTTPException(status_code=409, detail="That Idempotency-Key was already used for a different request.")
    return RecoveryResult(reference=out["public_id"], action=out["action"], status=out["status"], result=out["result"], replayed=out["replayed"])


@router.post("/events/{reference}/retry", response_model=RecoveryResult, summary="Re-drive a failed, quarantined or review-needed event through the verified pipeline")
def retry_event(reference: str, request: Request, body: RecoveryRequest, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
                principal=Depends(require_permission(perm.JOBS_MANAGE)), svc=Depends(get_provider_event_service)) -> RecoveryResult:
    return _recover("retry_event", reference, body, idempotency_key, principal, svc, audit=_audit(request, principal, "retry_event", reference, body.reason))


@router.post("/events/{reference}/requeue", response_model=RecoveryResult, summary="Release an ABANDONED processing lease (expired) and re-drive the event")
def requeue_event(reference: str, request: Request, body: RecoveryRequest, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
                  principal=Depends(require_permission(perm.JOBS_MANAGE)), svc=Depends(get_provider_event_service)) -> RecoveryResult:
    return _recover("requeue_lease", reference, body, idempotency_key, principal, svc, audit=_audit(request, principal, "requeue_lease", reference, body.reason))


@router.post("/subscriptions/{reference}/reconcile", response_model=RecoveryResult, summary="Re-read one of OUR subscription links from the provider (needs a wired reader)")
def reconcile_subscription(reference: str, request: Request, body: RecoveryRequest, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
                           principal=Depends(require_permission(perm.JOBS_MANAGE)), svc=Depends(get_provider_event_service)) -> RecoveryResult:
    return _recover("reconcile_link", reference, body, idempotency_key, principal, svc, audit=_audit(request, principal, "reconcile_link", reference, body.reason))
