"""Strict Admin Users actions (03C, REQ-OWN-03). Every route declares an EXISTING permission, requires a reason and the account ``expected_revision``, and writes
its audit row in the same transaction as the change (see ``src/admin_users/actions.py``). Metadata only: no candidate content, no secret, no impersonation.
Roles are never changed here: a role change stays the W10.13 two-person flow (``/admin/role-changes``). There is no bulk action (OD-BULK-ACTIONS is open)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from src.admin_repository import AdminNotFound
from src.admin_users.actions import UserActions
from src.admin_users.guards import AdminForbidden
from src.api.dependencies import get_auth_service, get_repository, get_request_id, require_permission
from src.api.rate_limit import enforce, user_key
from src.api.schemas.admin_users import ActionBody, ActionResult, AssignPlanBody
from src.application import admin_audit as A
from src.application import admin_permissions as perm
from src.entitlements import PLAN_CODES
from src.persistence import ACCOUNT_STATUS_ACTIVE, ACCOUNT_STATUS_DEACTIVATED
from src.privacy.requests import PrivacyConflict, PrivacyNotFound, PrivacyValidationError

router = APIRouter(prefix="/admin/users/{user_id}/actions", tags=["admin-users"])


def _actions(repo=Depends(get_repository)) -> UserActions:
    return UserActions(repo.session_factory)


def _guard(fn):
    try:
        return fn()
    except AdminNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except PrivacyNotFound:
        raise HTTPException(status_code=404, detail="Account not found.")
    except AdminForbidden as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except PrivacyConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except PrivacyValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


def _audit(request: Request, principal, event: str, target_type: str, target, body: ActionBody, **ctx) -> dict:
    return A.build_audit(event_type=event, actor_user_id=principal.user_id, request_id=get_request_id(request), target_type=target_type, target_id=target,
                         reason=body.reason.strip(), **ctx)


def _result(actions: UserActions, user_id: int, action: str, changed: bool, **extra) -> ActionResult:
    extras = actions.detail_extras(user_id)
    return ActionResult(user_id=user_id, action=action, changed=changed, revision=(extras or {}).get("revision", ""), **extra)


def _status(user_id: int, target: str, body: ActionBody, principal, actions: UserActions, audit: dict) -> ActionResult:
    out = _guard(lambda: actions.set_status(user_id, target, actor_user_id=principal.user_id, expected_revision=body.expected_revision, audit=audit))
    return _result(actions, user_id, "deactivate" if target == ACCOUNT_STATUS_DEACTIVATED else "reactivate", out["changed"], sessions_revoked=out["sessions_revoked"])


@router.post("/deactivate", response_model=ActionResult, summary="Deactivate the account: sessions end in the same transaction (reason and revision required)")
def deactivate(user_id: int, body: ActionBody, request: Request, principal=Depends(require_permission(perm.USERS_MANAGE)), actions=Depends(_actions)) -> ActionResult:
    audit = _audit(request, principal, A.ADMIN_ACCOUNT_STATUS_CHANGE, "user", user_id, body, after=ACCOUNT_STATUS_DEACTIVATED, status=ACCOUNT_STATUS_DEACTIVATED)
    return _status(user_id, ACCOUNT_STATUS_DEACTIVATED, body, principal, actions, audit)


@router.post("/reactivate", response_model=ActionResult, summary="Reactivate the account; earlier sessions are NOT revived (reason and revision required)")
def reactivate(user_id: int, body: ActionBody, request: Request, principal=Depends(require_permission(perm.USERS_MANAGE)), actions=Depends(_actions)) -> ActionResult:
    audit = _audit(request, principal, A.ADMIN_ACCOUNT_STATUS_CHANGE, "user", user_id, body, after=ACCOUNT_STATUS_ACTIVE, status=ACCOUNT_STATUS_ACTIVE)
    return _status(user_id, ACCOUNT_STATUS_ACTIVE, body, principal, actions, audit)


@router.post("/force-signout", response_model=ActionResult, summary="Revoke every live session of the account (reason and revision required)")
def force_signout(user_id: int, body: ActionBody, request: Request, principal=Depends(require_permission(perm.USERS_SESSIONS_REVOKE)),
                  actions=Depends(_actions)) -> ActionResult:
    audit = _audit(request, principal, A.ADMIN_SESSIONS_REVOKED, "user", user_id, body)
    n = _guard(lambda: actions.force_signout(user_id, actor_user_id=principal.user_id, expected_revision=body.expected_revision, audit=audit))
    return _result(actions, user_id, "force_signout", n > 0, sessions_revoked=n)


@router.post("/assign-plan", response_model=ActionResult, summary="Assign a plan through the entitlements domain (reason and revision required)")
def assign_plan(user_id: int, body: AssignPlanBody, request: Request, principal=Depends(require_permission(perm.SUBSCRIPTIONS_MANAGE)),
                actions=Depends(_actions)) -> ActionResult:
    if body.plan_code not in PLAN_CODES:
        raise HTTPException(status_code=422, detail="Unknown plan.")
    audit = _audit(request, principal, A.ADMIN_SUBSCRIPTION_ASSIGNED, "user", user_id, body, after=body.plan_code)
    out = _guard(lambda: actions.assign_plan(user_id, body.plan_code, actor_user_id=principal.user_id, expected_revision=body.expected_revision, audit=audit))
    return _result(actions, user_id, "assign_plan", out["changed"], plan_code=out["plan_code"])


@router.post("/resend-verification", response_model=ActionResult,
             summary="Resend the account's email-verification link through the existing identity flow (reason and revision required)")
def resend_verification(user_id: int, body: ActionBody, request: Request, principal=Depends(require_permission(perm.USERS_MANAGE)),
                        actions=Depends(_actions), auth=Depends(get_auth_service)) -> ActionResult:
    enforce("auth_verify_resend_cooldown", user_key(user_id))
    enforce("auth_verify_resend", user_key(user_id))
    audit = _audit(request, principal, A.ADMIN_USER_VERIFICATION_RESENT, "user", user_id, body)
    _guard(lambda: actions.begin_verification_resend(user_id, actor_user_id=principal.user_id, expected_revision=body.expected_revision, audit=audit))
    sent = auth.send_verification(user_id=user_id, request_id=get_request_id(request))
    return _result(actions, user_id, "resend_verification", sent is not None and sent.accepted, mail_accepted=bool(sent and sent.accepted))


@router.post("/expire-verification", response_model=ActionResult, summary="Invalidate outstanding verification links (reason and revision required)")
def expire_verification(user_id: int, body: ActionBody, request: Request, principal=Depends(require_permission(perm.USERS_MANAGE)),
                        actions=Depends(_actions)) -> ActionResult:
    audit = _audit(request, principal, A.ADMIN_USER_VERIFICATION_EXPIRED, "user", user_id, body)
    out = _guard(lambda: actions.expire_verification(user_id, actor_user_id=principal.user_id, expected_revision=body.expected_revision, audit=audit))
    return _result(actions, user_id, "expire_verification", out["changed"], links_expired=out["links_expired"])


@router.post("/request-deletion", response_model=ActionResult,
             summary="Record an account-deletion request through the existing privacy-request pipeline; execution stays in /admin/privacy (reason and revision required)")
def request_deletion(user_id: int, body: ActionBody, request: Request, principal=Depends(require_permission(perm.PRIVACY_EXECUTE)),
                     actions=Depends(_actions)) -> ActionResult:
    audit = _audit(request, principal, A.ADMIN_USER_DELETION_REQUESTED, "privacy_request", None, body, subject_user_id=user_id)
    out = _guard(lambda: actions.request_deletion(user_id, actor_user_id=principal.user_id, expected_revision=body.expected_revision, audit=audit))
    return _result(actions, user_id, "request_deletion", out["created"], request_id=out["request_id"])
