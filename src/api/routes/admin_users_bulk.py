"""Previewed, authorised, audited bulk Admin Users actions (03C; OD-BULK-ACTIONS is a PROVISIONAL recommendation, not an approval). Two actions only, both
low-harm and reversible: ``force-signout`` and ``expire-verification``. Each needs the SAME existing permission as its single-user action (registry stays 44).
GET preview returns counts and per-reason exclusion counts only; POST execute needs the preview revision, a reason, an Idempotency-Key and runs per subject
(see ``src/admin_users/bulk.py``). Plan assignment already has its own bulk route (03B) and is not duplicated."""

from __future__ import annotations

import re

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request

from src.admin_users.bulk import ACTIONS, BulkAuditFailure, BulkUserActions
from src.admin_users.guards import AdminForbidden
from src.api.dependencies import get_repository, get_request_id, require_permission
from src.api.rate_limit import enforce, user_key
from src.api.schemas.admin_users_bulk import BulkExecuteBody, BulkPreview, BulkResult
from src.application import admin_audit as A
from src.application import pause

router = APIRouter(prefix="/admin/users/bulk", tags=["admin-users-bulk"])
_KEY = re.compile(r"^[A-Za-z0-9_-]{8,64}$")


def _svc(repo=Depends(get_repository)) -> BulkUserActions:
    return BulkUserActions(repo.session_factory)


def _guard(fn):
    try:
        return fn()
    except AdminForbidden as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except BulkAuditFailure as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


def _platform_state_readable() -> None:
    """The batch is a mutation: refuse it (503 ``platform_state_unavailable``) when the durable pause store cannot be read. The pause list itself covers candidate
    capabilities only, so no capability pauses an Admin recovery action; an unreadable platform state is still never treated as healthy."""
    svc = pause._installed
    if svc is not None:
        svc.snapshot()


def _ids(ids: str) -> list[int]:
    try:
        return [int(x) for x in ids.split(",") if x.strip()]
    except ValueError:
        raise HTTPException(status_code=422, detail="Account ids must be whole numbers.")


def _make_preview(action: str):
    perm_code = ACTIONS[action].permission

    def preview(ids: str = Query(min_length=1, max_length=900, description="Comma-separated account ids (at most 100)"),
                principal=Depends(require_permission(perm_code)), svc=Depends(_svc)) -> BulkPreview:
        return BulkPreview(**_guard(lambda: svc.preview(action, _ids(ids), actor_user_id=principal.user_id)))

    def execute(body: BulkExecuteBody, request: Request, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
                principal=Depends(require_permission(perm_code)), svc=Depends(_svc)) -> BulkResult:
        if not idempotency_key or not _KEY.match(idempotency_key):
            raise HTTPException(status_code=422, detail="An Idempotency-Key of 8 to 64 letters, digits, underscores or hyphens is required.")
        _platform_state_readable()
        done = _guard(lambda: svc.replay(action, body.account_ids, body.preview_revision, body.reason, actor_user_id=principal.user_id,
                                         idempotency_key=idempotency_key))
        if done is not None:           # a replay returns the FIRST result and consumes no rate budget
            return BulkResult(**done)
        enforce("admin_bulk_user_actions", user_key(principal.user_id))
        return BulkResult(**_guard(lambda: svc.execute(action, body.account_ids, preview_revision=body.preview_revision, reason=body.reason,
                                                       actor_user_id=principal.user_id, idempotency_key=idempotency_key, request_id=get_request_id(request),
                                                       batch_event=A.ADMIN_USER_BULK_ACTION)))

    preview.__name__, execute.__name__ = f"preview_{action.replace('-', '_')}", f"execute_{action.replace('-', '_')}"
    router.add_api_route(f"/{action}/preview", preview, methods=["GET"], response_model=BulkPreview,
                         summary=f"Preview a bulk {action} as counts only (needs the same permission as the single action)")
    router.add_api_route(f"/{action}/execute", execute, methods=["POST"], response_model=BulkResult,
                         summary=f"Apply a bulk {action} (preview revision, reason and Idempotency-Key required; at most 100; per-subject outcome)")


for _action in ACTIONS:
    _make_preview(_action)
