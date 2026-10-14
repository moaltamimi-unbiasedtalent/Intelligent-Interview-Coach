"""Admin integrations and API connections (P10B-W10.6). Every route declares an explicit permission.

Metadata only: whether a credential is configured and where it comes from, never its value, prefix, suffix or a
mask. The integration set is code-defined (no custom integrations, no admin-entered URL). Connection tests run
only when an operator asks, against an adapter-defined destination, with a bounded timeout. Credential
write/remove (W12.4B) exist only for a SecretStore that supports writes (the encrypted store); the environment layer is
externally managed and is never changed. Both need ``platform.integrations.secret.rotate`` AND a fresh password step-up
of THIS session (not MFA), and the audit event is written in the same transaction as the change.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select

from src.api.dependencies import (
    _session_cookie_name, get_audit_repository, get_integration_service, get_repository, get_request_id, require_permission)
from src.api.schemas.admin import IntegrationDetail, IntegrationList, IntegrationTestResult
from src.application import admin_audit as A
from src.application import admin_permissions as perm
from src.integrations import IntegrationNotFound, IntegrationTestUnsupported
from src.persistence import AuditEvent
from src.admin_security.stepup import StepUpService
from src.secret_store import SecretStoreReadOnly, SecretStoreStale, SecretStoreUnavailable

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


_UNAVAILABLE_COPY = {
    "key_missing": "The secure credential store is unavailable: its encryption key is not configured in the deployment.",
    "key_malformed": "The secure credential store is unavailable: its encryption key is not valid.",
    "store_error": "The secure credential store is unavailable right now.",
    "not_bound": "The secure credential store is unavailable right now.",
}
_SHAPE_COPY = "The credential must be within the allowed length with no whitespace."


async def _json_body(request: Request) -> dict:
    """Parsed by hand so a submitted value can never be echoed by a validation error."""
    try:
        payload = await request.json()
    except Exception:  # noqa: BLE001
        return {}
    return payload if isinstance(payload, dict) else {}


def _revision(payload: dict) -> int | None:
    rev = payload.get("expected_revision")
    return rev if isinstance(rev, int) and not isinstance(rev, bool) and rev >= 0 else None


# The body is parsed by hand (so no validation error can echo it); this documents the contract and marks the value write-only.
_WRITE_ONLY_BODY = {"requestBody": {"required": True, "content": {"application/json": {"schema": {
    "type": "object", "required": ["value"], "additionalProperties": False,
    "properties": {"value": {"type": "string", "format": "password", "writeOnly": True, "minLength": 8, "maxLength": 4096},
                   "expected_revision": {"type": "integer", "minimum": 0}}}}}}}


@router.post("/{code}/credentials/{slot}", openapi_extra=_WRITE_ONLY_BODY,
             summary="Configure or replace a credential (WRITE-ONLY; fresh step-up; only for a writable SecretStore)")
async def replace_credential(code: str, slot: str, request: Request,
                             principal=Depends(require_permission(perm.SECRET_ROTATE)),
                             service=Depends(get_integration_service), audit_repo=Depends(get_audit_repository),
                             repo=Depends(get_repository)) -> dict:
    """The value is passed to the store and discarded: it is not returned, logged, audited or persisted in the clear.
    The encrypted store writes the ciphertext and the audit event in ONE transaction (an audit failure stores nothing)."""
    cred = _find(lambda: service.credential_slot(code, slot))
    rid = get_request_id(request)
    StepUpService(repo.session_factory).require(request.cookies.get(_session_cookie_name(request)))   # 403 step_up_required
    payload = await _json_body(request)
    if not set(payload) <= {"value", "expected_revision"} or "value" not in payload:
        raise HTTPException(status_code=422, detail=_SHAPE_COPY)
    try:
        value = service.validate_credential_shape(payload.get("value"), cred)
    except Exception:  # noqa: BLE001 - never echo the input
        raise HTTPException(status_code=422, detail=_SHAPE_COPY)
    audit = A.build_audit(event_type=A.ADMIN_CREDENTIAL_REPLACEMENT_SUCCEEDED, actor_user_id=principal.user_id, request_id=rid,
                          target_type="integration", target_id=code, slot=slot)
    try:
        out = service.write_credential(code, slot, value, actor_user_id=principal.user_id, expected_revision=_revision(payload),
                                       audit=audit if service.atomic_audit else None)
    except SecretStoreReadOnly:
        _best_effort(audit_repo, A.ADMIN_CREDENTIAL_REPLACEMENT_FAILED, principal, rid, code, slot, reason="read_only_store")
        raise HTTPException(status_code=409, detail="This credential is managed outside Ask4Mo and cannot be changed here.")
    except SecretStoreStale:
        _best_effort(audit_repo, A.ADMIN_CREDENTIAL_REPLACEMENT_FAILED, principal, rid, code, slot, reason="stale_revision")
        raise HTTPException(status_code=409, detail="This credential changed since you opened it. Reload and try again.")
    except SecretStoreUnavailable as exc:
        _best_effort(audit_repo, A.ADMIN_CREDENTIAL_REPLACEMENT_FAILED, principal, rid, code, slot, reason=exc.reason)
        raise HTTPException(status_code=503, detail=_UNAVAILABLE_COPY.get(exc.reason, _UNAVAILABLE_COPY["store_error"]))
    except Exception:  # noqa: BLE001 - exception text may embed the value; discard it
        _best_effort(audit_repo, A.ADMIN_CREDENTIAL_REPLACEMENT_FAILED, principal, rid, code, slot, reason="store_error")
        log.warning("credential write failed for %s/%s", code, slot)
        raise HTTPException(status_code=502, detail="The credential could not be saved.")
    if not service.atomic_audit:   # non-transactional (test-only) stores: the success event is written after the change
        _best_effort(audit_repo, A.ADMIN_CREDENTIAL_REPLACEMENT_SUCCEEDED, principal, rid, code, slot)
    return {"integration": code, "slot": slot, "configured": True, "action": out.get("action"), "revision": out.get("revision")}


@router.post("/{code}/credentials/{slot}/remove",
             summary="Remove an Admin-managed credential (fresh step-up; explicit confirmation; the environment layer is untouched)")
async def remove_credential(code: str, slot: str, request: Request,
                            principal=Depends(require_permission(perm.SECRET_ROTATE)),
                            service=Depends(get_integration_service), audit_repo=Depends(get_audit_repository),
                            repo=Depends(get_repository)) -> dict:
    _find(lambda: service.credential_slot(code, slot))
    rid = get_request_id(request)
    StepUpService(repo.session_factory).require(request.cookies.get(_session_cookie_name(request)))
    payload = await _json_body(request)
    if not set(payload) <= {"confirm", "expected_revision"} or payload.get("confirm") is not True:
        raise HTTPException(status_code=422, detail="Confirm that you want to remove the managed credential.")
    audit = A.build_audit(event_type=A.ADMIN_CREDENTIAL_REMOVED, actor_user_id=principal.user_id, request_id=rid,
                          target_type="integration", target_id=code, slot=slot)
    try:
        service.remove_credential(code, slot, actor_user_id=principal.user_id, expected_revision=_revision(payload),
                                  audit=audit if service.atomic_audit else None)
    except SecretStoreReadOnly:
        raise HTTPException(status_code=409, detail="This credential is managed outside Ask4Mo and cannot be changed here.")
    except SecretStoreStale:
        raise HTTPException(status_code=409, detail="There is no managed credential at that revision. Reload and try again.")
    except SecretStoreUnavailable as exc:
        raise HTTPException(status_code=503, detail=_UNAVAILABLE_COPY.get(exc.reason, _UNAVAILABLE_COPY["store_error"]))
    except Exception:  # noqa: BLE001
        log.warning("credential removal failed for %s/%s", code, slot)
        raise HTTPException(status_code=502, detail="The credential could not be removed.")
    if not service.atomic_audit:
        _best_effort(audit_repo, A.ADMIN_CREDENTIAL_REMOVED, principal, rid, code, slot)
    return {"integration": code, "slot": slot, "removed": True}


def _best_effort(audit_repo, event: str, principal, rid, code, slot, result: str | None = None, **ctx) -> None:
    """Failure audits and test-store audits are written after the fact; a failed audit write never changes the outcome."""
    try:
        audit_repo.record(**A.build_audit(event_type=event, actor_user_id=principal.user_id, request_id=rid, target_type="integration",
                                          target_id=code, result=result or ("failure" if event.endswith("failed") else "success"),
                                          slot=slot, **ctx))
    except Exception:  # noqa: BLE001
        log.warning("integration audit write failed after the store operation")
