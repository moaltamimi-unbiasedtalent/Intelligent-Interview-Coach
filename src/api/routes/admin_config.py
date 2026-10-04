"""Admin durable platform pause and feature flags (P10B-W10.11). Every route declares an explicit permission.

* Pause (``/admin/pause``): reads need ``platform.flags.read``; a change needs ``platform.config.manage`` (the W10.0 owner of the pause switches). The
  state is DURABLE and shared by every process; a change carries the expected revision (optimistic concurrency), a required internal reason and is
  audited in the same transaction. The environment is the SERVER's own; no request field can choose it.
* Flags (``/admin/flags``): the keys are CODE-DEFINED; an unknown key is rejected and there is no create route. A flag only restricts availability; it
  never grants authorization, an entitlement, a billing change or an AI/model change.
* There is deliberately NO generic key/value, JSON or environment editor.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from src.api.dependencies import get_feature_flag_service, get_pause_service, get_request_id, require_permission
from src.api.schemas.admin import FlagChangeRequest, FlagsOverview, FlagStateView, PauseChangeRequest, PauseOverview, PauseStateView
from src.application import admin_audit as A
from src.application import admin_permissions as perm
from src.application.pause import (
    PAUSABLE_CAPABILITIES, PauseConflict, PauseUnsupportedEnvironment, PauseValidationError,
)
from src.platform_config.flags import NOT_MUTABLE, FlagConflict, FlagUnsupportedEnvironment, FlagValidationError

router = APIRouter(prefix="/admin", tags=["admin-config"])

PAUSE_SCOPE_NOTE = ("Pausing a capability refuses NEW candidate activity of that kind (a fixed, code-defined list). It does not lock out Admin recovery, privacy and "
                    "account controls, legal pages or saved data, and it does not stop the background job worker.")


@router.get("/pause", response_model=PauseOverview, summary="Durable operator pause state (shared by every process; survives restart)")
def pause_state(_p=Depends(require_permission(perm.FLAGS_READ)), svc=Depends(get_pause_service)) -> PauseOverview:
    return PauseOverview(environment=svc.environment or "unsupported", durable=True, items=[PauseStateView(**v) for v in svc.snapshot().values()],
                         protected_scope=list(PAUSABLE_CAPABILITIES), note=PAUSE_SCOPE_NOTE)


@router.post("/pause/{capability}", response_model=PauseStateView,
             summary="Pause or resume one capability (expected revision, required reason, same-transaction audit)")
def set_pause(capability: str, body: PauseChangeRequest, request: Request, principal=Depends(require_permission(perm.CONFIG_MANAGE)),
              svc=Depends(get_pause_service)) -> PauseStateView:
    audit = A.build_audit(event_type=A.ADMIN_PLATFORM_PAUSED if body.paused else A.ADMIN_PLATFORM_RESUMED, actor_user_id=principal.user_id,
                          request_id=get_request_id(request), target_type="capability", reason=body.reason[:200])
    try:
        return PauseStateView(**svc.set_paused(capability, body.paused, expected_revision=body.expected_revision, reason=body.reason,
                                               actor_user_id=principal.user_id, audit=audit))
    except PauseValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except (PauseConflict, PauseUnsupportedEnvironment) as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.get("/flags", response_model=FlagsOverview, summary="Code-defined feature flags with their durable overrides")
def list_flags(_p=Depends(require_permission(perm.FLAGS_READ)), svc=Depends(get_feature_flag_service)) -> FlagsOverview:
    return FlagsOverview(environment=svc.environment or "unsupported", items=[FlagStateView(**s) for s in svc.states()], not_mutable=NOT_MUTABLE,
                         note="Only the flags listed here exist. A flag can only restrict availability; it never grants permission, entitlement, billing or AI changes.")


@router.put("/flags/{key}", response_model=FlagStateView,
            summary="Set a flag override (true/false) or reset it to inherit (null). Unknown keys are rejected; there is no create route")
def set_flag(key: str, body: FlagChangeRequest, request: Request, principal=Depends(require_permission(perm.FLAGS_MANAGE)),
             svc=Depends(get_feature_flag_service)) -> FlagStateView:
    def audit_for(new_state: str) -> dict:
        event = {"enabled_override": A.ADMIN_FLAG_OVERRIDE_ENABLED, "disabled_override": A.ADMIN_FLAG_OVERRIDE_DISABLED}.get(new_state, A.ADMIN_FLAG_OVERRIDE_RESET)
        return A.build_audit(event_type=event, actor_user_id=principal.user_id, request_id=get_request_id(request), target_type="feature_flag",
                             reason=body.reason[:200])
    try:
        return FlagStateView(**svc.set_override(key[:48], body.enabled, expected_revision=body.expected_revision, reason=body.reason,
                                                actor_user_id=principal.user_id, audit_for=audit_for))
    except FlagValidationError as exc:
        raise HTTPException(status_code=422 if "Unknown" not in str(exc) else 404, detail=str(exc))
    except (FlagConflict, FlagUnsupportedEnvironment) as exc:
        raise HTTPException(status_code=409, detail=str(exc))
