"""Admin integrations and API connections (P10B-W10.6). Every route declares an explicit permission.

Metadata only: whether a credential is configured and where it comes from, never its value, prefix, suffix or a
mask. The integration set is code-defined (no custom integrations, no admin-entered URL). Connection tests run
only when an operator asks, against an adapter-defined destination, with a bounded timeout. Credential
replacement exists only for a SecretStore that supports writes; the environment store is externally managed.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select

from src.api.dependencies import get_audit_repository, get_integration_service, get_request_id, require_permission
from src.api.schemas.admin import IntegrationDetail, IntegrationList, IntegrationTestResult
from src.application import admin_audit as A
from src.application import admin_permissions as perm
from src.integrations import IntegrationNotFound, IntegrationTestUnsupported
from src.persistence import AuditEvent
from src.secret_store import SecretStoreReadOnly

router = APIRouter(prefix="/admin/integrations", tags=["admin-integrations"])
log = logging.getLogger("ask4mo.admin.integrations")


def _find(fn):
    try:
        return fn()
    except IntegrationNotFound:
        raise HTTPException(status_code=404, detail="Integration not found.")


@router.get("", response_model=IntegrationList, summary="Integration inventory: configuration, runtime and health are separate")
def list_integrations(_p=Depends(require_permission(perm.INTEGRATIONS_READ)),
                      service=Depends(get_integration_service)) -> IntegrationList:
    return IntegrationList(items=service.list())


@router.get("/{code}", response_model=IntegrationDetail, summary="One integration (never a secret value)")
def integration_detail(code: str, _p=Depends(require_permission(perm.INTEGRATIONS_READ)),
                       service=Depends(get_integration_service), audit=Depends(get_audit_repository)) -> IntegrationDetail:
    d = _find(lambda: service.get(code))
    with audit._session_factory() as s:   # recent integration-management events for THIS integration
        rows = s.scalars(select(AuditEvent).where(
            AuditEvent.target_type == "integration", AuditEvent.target_id == code,
            AuditEvent.event_type.like("admin.%")).order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc()).limit(15)).all()
        events = [{"event_type": e.event_type, "result": e.result, "actor_user_id": e.actor_user_id,
                   "request_id": e.request_id, "created_at": e.created_at.isoformat() if e.created_at else None,
                   "context": e.context} for e in rows]
    return IntegrationDetail(**d, audit=events)


@router.post("/{code}/test", response_model=IntegrationTestResult,
             summary="Run ONE manual connection test (explicit action; bounded; adapter-defined destination)")
def run_test(code: str, request: Request, principal=Depends(require_permission(perm.INTEGRATIONS_MANAGE)),
             service=Depends(get_integration_service)) -> IntegrationTestResult:
    audit = A.build_audit(event_type=A.ADMIN_INTEGRATION_TEST_RUN, actor_user_id=principal.user_id,
                          request_id=get_request_id(request), target_type="integration", target_id=code)
    try:
        return IntegrationTestResult(**_find(lambda: service.run_test(code, actor_user_id=principal.user_id, audit=audit)))
    except IntegrationTestUnsupported:
        raise HTTPException(status_code=409, detail="A manual connection test is not available for this integration.")


@router.post("/{code}/credentials/{slot}",
             summary="Replace a credential (WRITE-ONLY; only when the active SecretStore supports writes)")
async def replace_credential(code: str, slot: str, request: Request,
                             principal=Depends(require_permission(perm.SECRET_ROTATE)),
                             service=Depends(get_integration_service), audit_repo=Depends(get_audit_repository)) -> dict:
    """The body is parsed by hand so a submitted value can never be echoed by a validation error. The value is
    passed to the store and discarded: it is not returned, logged, audited or persisted. Audit is NOT atomic
    with the store write (different systems), so it is requested, then succeeded or failed: no rollback is claimed."""
    _find(lambda: service.credential_slot(code, slot))
    rid = get_request_id(request)

    def audit(event: str, result: str = "success", **ctx):
        spec = A.build_audit(event_type=event, actor_user_id=principal.user_id, request_id=rid, target_type="integration",
                             target_id=code, result=result, slot=slot, **ctx)
        audit_repo.record(**spec)

    try:
        payload = await request.json()
        value = payload.get("value") if isinstance(payload, dict) and set(payload) == {"value"} else None
        value = service.validate_credential_shape(value)
    except Exception:  # noqa: BLE001 - never echo the input
        raise HTTPException(status_code=422, detail="The credential must be 8 to 4096 characters with no whitespace.")
    try:
        audit(A.ADMIN_CREDENTIAL_REPLACEMENT_REQUESTED)           # fail closed: no write without the request audited
    except Exception:  # noqa: BLE001
        raise HTTPException(status_code=503, detail="Audit unavailable; nothing was changed.")
    try:
        service.write_credential(code, slot, value)
    except SecretStoreReadOnly:
        _best_effort(audit, A.ADMIN_CREDENTIAL_REPLACEMENT_FAILED, "failure", reason="read_only_store")
        raise HTTPException(status_code=409, detail="This credential is managed outside Ask4Mo and cannot be changed here.")
    except Exception:  # noqa: BLE001 - exception text may embed the value; discard it
        _best_effort(audit, A.ADMIN_CREDENTIAL_REPLACEMENT_FAILED, "failure", reason="store_error")
        log.warning("credential replacement failed for %s/%s", code, slot)
        raise HTTPException(status_code=502, detail="The credential could not be saved.")
    _best_effort(audit, A.ADMIN_CREDENTIAL_REPLACEMENT_SUCCEEDED)
    return {"integration": code, "slot": slot, "configured": True}


def _best_effort(audit, event: str, result: str = "success", **ctx) -> None:
    try:
        audit(event, result, **ctx)
    except Exception:  # noqa: BLE001
        log.warning("integration audit write failed after the store operation")
