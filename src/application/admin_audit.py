"""Canonical admin audit event names and the fail-closed audit builder (P10B-W10.1, SEC-W10-02/03).

Privileged admin changes are audited in the SAME database transaction as the state change (see the
``audit=`` parameter on ``AccountRepository.set_*``): if the audit row cannot be written, the mutation
rolls back. Events carry actor, target, result, reason (optional), the ``X-Request-Id`` and a SAFE
before/after summary; never a secret, a token, an email body or any candidate content.

Existing event names are kept stable (history and ``eval_platform_admin`` rely on them).
"""

from __future__ import annotations

import logging
from typing import Any, Final

log = logging.getLogger("ask4mo.admin.audit")

ADMIN_PLATFORM_ROLE_CHANGE: Final = "admin.platform_role_change"
ADMIN_ENTITLEMENT_CHANGE: Final = "admin.entitlement_change"
ADMIN_ACCOUNT_STATUS_CHANGE: Final = "admin.account_status_change"
PLATFORM_PAUSE_TOGGLED: Final = "platform.pause_toggled"
ADMIN_ACCESS_DENIED: Final = "admin.access.denied"
# W10.2
ADMIN_SESSIONS_REVOKED: Final = "admin.sessions_revoked"
ADMIN_WORKSPACE_MEMBER_ADDED: Final = "admin.workspace_member_added"
ADMIN_WORKSPACE_MEMBER_REMOVED: Final = "admin.workspace_member_removed"
ADMIN_WORKSPACE_MEMBER_ROLE_CHANGED: Final = "admin.workspace_member_role_changed"

ADMIN_EVENT_NAMES: Final[frozenset[str]] = frozenset({
    ADMIN_PLATFORM_ROLE_CHANGE, ADMIN_ENTITLEMENT_CHANGE, ADMIN_ACCOUNT_STATUS_CHANGE,
    PLATFORM_PAUSE_TOGGLED, ADMIN_ACCESS_DENIED, ADMIN_SESSIONS_REVOKED,
    ADMIN_WORKSPACE_MEMBER_ADDED, ADMIN_WORKSPACE_MEMBER_REMOVED, ADMIN_WORKSPACE_MEMBER_ROLE_CHANGED,
})

# Context keys that may never be written (defence in depth against a careless caller).
_FORBIDDEN_CONTEXT_FRAGMENTS = (
    "password", "secret", "token", "api_key", "apikey", "cookie", "authorization",
    "cv", "document", "answer", "conversation", "memory", "evidence", "transcript", "prompt",
)


def build_audit(*, event_type: str, actor_user_id: int | None, request_id: str | None,
                target_type: str | None = None, target_id: str | int | None = None,
                result: str = "success", reason: str | None = None,
                before: Any = None, after: Any = None, **context: Any) -> dict:
    """Validate the event name and context and return the row spec for an atomic audit write."""
    if event_type not in ADMIN_EVENT_NAMES:
        raise ValueError(f"Unknown admin audit event name: {event_type!r}")
    ctx: dict[str, Any] = {k: v for k, v in context.items() if v is not None}
    if reason:
        ctx["reason"] = str(reason)[:200]
    if before is not None:
        ctx["before"] = before
    if after is not None:
        ctx["after"] = after
    for key in ctx:
        low = key.lower()
        if any(f in low for f in _FORBIDDEN_CONTEXT_FRAGMENTS):
            raise ValueError(f"Audit context key not allowed: {key!r}")
    return {
        "event_type": event_type, "actor_user_id": actor_user_id,
        "target_type": target_type, "target_id": None if target_id is None else str(target_id),
        "result": result, "request_id": request_id or None, "context": ctx or None,
    }


def record_denial(audit_repo: Any, *, actor_user_id: int | None, request_id: str | None,
                  permission: str, method: str, path: str, reason: str) -> bool:
    """Best-effort denial audit. Returns whether it was written. A failure is logged and NEVER
    changes the outcome: access stays denied whether or not this succeeds."""
    try:
        spec = build_audit(event_type=ADMIN_ACCESS_DENIED, actor_user_id=actor_user_id,
                           request_id=request_id, target_type="permission", target_id=permission,
                           result="denied", reason=reason, method=method, path=path[:200])
        audit_repo.record(**spec)
        return True
    except Exception:  # noqa: BLE001 - denial stays denied; never raise out of an auth check
        log.warning("admin denial audit could not be written (access still denied)")
        return False
