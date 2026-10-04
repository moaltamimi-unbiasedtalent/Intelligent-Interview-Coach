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
# W10.3 (support). Payloads carry ids and enum before/after only, never message or note text.
# W10.4 (plans and subscriptions). Payloads carry plan codes, version numbers, subject ids and entitlement KEY
# names only; there is no payment data.
ADMIN_PLAN_VERSION_CREATED: Final = "admin.plan_version_created"
ADMIN_PLAN_VERSION_UPDATED: Final = "admin.plan_version_updated"
ADMIN_PLAN_VERSION_ACTIVATED: Final = "admin.plan_version_activated"
ADMIN_PLAN_VERSION_RETIRED: Final = "admin.plan_version_retired"
ADMIN_SUBSCRIPTION_ASSIGNED: Final = "admin.subscription_assigned"
# W10.6 (integrations). Payloads: integration code, credential SLOT, outcome and category; never a secret value,
# an upstream response or a URL.
ADMIN_INTEGRATION_TEST_RUN: Final = "admin.integration_test_run"
ADMIN_CREDENTIAL_REPLACEMENT_REQUESTED: Final = "admin.credential_replacement_requested"
ADMIN_CREDENTIAL_REPLACEMENT_SUCCEEDED: Final = "admin.credential_replacement_succeeded"
ADMIN_CREDENTIAL_REPLACEMENT_FAILED: Final = "admin.credential_replacement_failed"
# W10.9 (jobs). Payloads: job public id, job type and old/new state; never a job payload, an error body or a secret.
ADMIN_JOB_ENQUEUED: Final = "admin.job_enqueued"
ADMIN_JOB_RETRY_REQUESTED: Final = "admin.job_retry_requested"
ADMIN_JOB_CANCELLED: Final = "admin.job_cancelled"
# W10.8 (knowledge). Payloads: source/version public ids, version number, old/new state, authority, language, licence class and
# a bounded rejection reason CATEGORY; never document text, a preview, a file name or a provenance note.
ADMIN_KNOWLEDGE_VERSION_UPLOADED: Final = "admin.knowledge_version_uploaded"
ADMIN_KNOWLEDGE_VERSION_UPDATED: Final = "admin.knowledge_version_updated"
ADMIN_KNOWLEDGE_VERSION_APPROVED: Final = "admin.knowledge_version_approved"
ADMIN_KNOWLEDGE_VERSION_REJECTED: Final = "admin.knowledge_version_rejected"
ADMIN_KNOWLEDGE_INDEX_REQUESTED: Final = "admin.knowledge_index_requested"
ADMIN_KNOWLEDGE_VERSION_ACTIVATED: Final = "admin.knowledge_version_activated"
ADMIN_KNOWLEDGE_VERSION_RETIRED: Final = "admin.knowledge_version_retired"
ADMIN_KNOWLEDGE_VERSION_DELETED: Final = "admin.knowledge_version_deleted"
ADMIN_KNOWLEDGE_REPROCESS_REQUESTED: Final = "admin.knowledge_reprocess_requested"
# W10.10 (privacy/legal). Payloads: request/document/version ids, old/new state, result category; never exported data, request
# text, a candidate's content, an IP or a device identifier.
ADMIN_PRIVACY_REQUEST_RECORDED: Final = "admin.privacy_request_recorded"
ADMIN_PRIVACY_REQUEST_ASSIGNED: Final = "admin.privacy_request_assigned"
ADMIN_PRIVACY_REQUEST_STATUS_CHANGED: Final = "admin.privacy_request_status_changed"
ADMIN_PRIVACY_DELETION_INITIATED: Final = "admin.privacy_deletion_initiated"
ADMIN_PRIVACY_DELETION_COMPLETED: Final = "admin.privacy_deletion_completed"
ADMIN_PRIVACY_BACKFILL_REQUESTED: Final = "admin.privacy_preparation_backfill_requested"
ADMIN_LEGAL_VERSION_CREATED: Final = "admin.legal_version_created"
ADMIN_LEGAL_VERSION_UPDATED: Final = "admin.legal_version_updated"
ADMIN_LEGAL_VERSION_PUBLISHED: Final = "admin.legal_version_published"
# W10.5 (mock billing). Payloads: approval/plan-version/terms/payment/refund ids, amounts in minor units, currency and states; never a payment
# instrument, a provider payload or a candidate's content. MOCK: no real money moves.
ADMIN_BILLING_PRICE_CHANGE_REQUESTED: Final = "admin.billing_price_change_requested"
ADMIN_BILLING_PRICE_CHANGE_APPROVED: Final = "admin.billing_price_change_approved"
ADMIN_BILLING_PRICE_CHANGE_REJECTED: Final = "admin.billing_price_change_rejected"
ADMIN_BILLING_PRICE_ACTIVATED: Final = "admin.billing_price_activated"
ADMIN_BILLING_REFUND_REQUESTED: Final = "admin.billing_refund_requested"
ADMIN_BILLING_REFUND_APPROVED: Final = "admin.billing_refund_approved"
ADMIN_BILLING_REFUND_REJECTED: Final = "admin.billing_refund_rejected"
ADMIN_BILLING_REFUND_EXECUTED: Final = "admin.billing_refund_executed"
ADMIN_BILLING_REFUND_FAILED: Final = "admin.billing_refund_failed"
# W10.7 (AI and model administration). Payloads: config version/evaluation/approval ids, the config hash, environment and states; never a prompt,
# a candidate's content or a provider payload.
ADMIN_AI_CONFIG_CREATED: Final = "admin.ai_config_created"
ADMIN_AI_CONFIG_UPDATED: Final = "admin.ai_config_updated"
ADMIN_AI_CONFIG_VALIDATED: Final = "admin.ai_config_validated"
ADMIN_AI_EVALUATION_REQUESTED: Final = "admin.ai_evaluation_requested"
ADMIN_AI_EVALUATION_COMPLETED: Final = "admin.ai_evaluation_completed"
ADMIN_AI_APPROVAL_REQUESTED: Final = "admin.ai_approval_requested"
ADMIN_AI_APPROVED: Final = "admin.ai_approved"
ADMIN_AI_REJECTED: Final = "admin.ai_rejected"
ADMIN_AI_ACTIVATED: Final = "admin.ai_activated"
ADMIN_AI_ROLLED_BACK: Final = "admin.ai_rolled_back"
ADMIN_AI_RETIRED: Final = "admin.ai_retired"
# W10.11 (durable platform pause and feature flags). Payloads: environment, capability or flag key, old/new state and effective value, revision. Never a
# secret or candidate content; the pause reason is internal admin metadata.
ADMIN_PLATFORM_PAUSED: Final = "admin.platform_paused"
ADMIN_PLATFORM_RESUMED: Final = "admin.platform_resumed"
ADMIN_FLAG_OVERRIDE_ENABLED: Final = "admin.flag_override_enabled"
ADMIN_FLAG_OVERRIDE_DISABLED: Final = "admin.flag_override_disabled"
ADMIN_FLAG_OVERRIDE_RESET: Final = "admin.flag_override_reset"
ADMIN_SUPPORT_TICKET_ASSIGNED: Final = "admin.support_ticket_assigned"
ADMIN_SUPPORT_TICKET_STATUS_CHANGED: Final = "admin.support_ticket_status_changed"
ADMIN_SUPPORT_TICKET_PRIORITY_CHANGED: Final = "admin.support_ticket_priority_changed"
ADMIN_SUPPORT_REPLY_SENT: Final = "admin.support_reply_sent"
ADMIN_SUPPORT_INTERNAL_NOTE_CREATED: Final = "admin.support_internal_note_created"

ADMIN_EVENT_NAMES: Final[frozenset[str]] = frozenset({
    ADMIN_PLATFORM_ROLE_CHANGE, ADMIN_ENTITLEMENT_CHANGE, ADMIN_ACCOUNT_STATUS_CHANGE,
    PLATFORM_PAUSE_TOGGLED, ADMIN_ACCESS_DENIED, ADMIN_SESSIONS_REVOKED,
    ADMIN_WORKSPACE_MEMBER_ADDED, ADMIN_WORKSPACE_MEMBER_REMOVED, ADMIN_WORKSPACE_MEMBER_ROLE_CHANGED,
    ADMIN_SUPPORT_TICKET_ASSIGNED, ADMIN_SUPPORT_TICKET_STATUS_CHANGED, ADMIN_SUPPORT_TICKET_PRIORITY_CHANGED,
    ADMIN_SUPPORT_REPLY_SENT, ADMIN_SUPPORT_INTERNAL_NOTE_CREATED,
    ADMIN_PLAN_VERSION_CREATED, ADMIN_PLAN_VERSION_UPDATED, ADMIN_PLAN_VERSION_ACTIVATED,
    ADMIN_PLAN_VERSION_RETIRED, ADMIN_SUBSCRIPTION_ASSIGNED,
    ADMIN_INTEGRATION_TEST_RUN, ADMIN_CREDENTIAL_REPLACEMENT_REQUESTED, ADMIN_CREDENTIAL_REPLACEMENT_SUCCEEDED,
    ADMIN_CREDENTIAL_REPLACEMENT_FAILED, ADMIN_JOB_ENQUEUED, ADMIN_JOB_RETRY_REQUESTED, ADMIN_JOB_CANCELLED,
    ADMIN_KNOWLEDGE_VERSION_UPLOADED, ADMIN_KNOWLEDGE_VERSION_UPDATED, ADMIN_KNOWLEDGE_VERSION_APPROVED,
    ADMIN_KNOWLEDGE_VERSION_REJECTED, ADMIN_KNOWLEDGE_INDEX_REQUESTED, ADMIN_KNOWLEDGE_VERSION_ACTIVATED,
    ADMIN_KNOWLEDGE_VERSION_RETIRED, ADMIN_KNOWLEDGE_VERSION_DELETED, ADMIN_KNOWLEDGE_REPROCESS_REQUESTED,
    ADMIN_PRIVACY_REQUEST_RECORDED, ADMIN_PRIVACY_REQUEST_ASSIGNED, ADMIN_PRIVACY_REQUEST_STATUS_CHANGED,
    ADMIN_PRIVACY_DELETION_INITIATED, ADMIN_PRIVACY_DELETION_COMPLETED, ADMIN_PRIVACY_BACKFILL_REQUESTED,
    ADMIN_LEGAL_VERSION_CREATED, ADMIN_LEGAL_VERSION_UPDATED, ADMIN_LEGAL_VERSION_PUBLISHED,
    ADMIN_BILLING_PRICE_CHANGE_REQUESTED, ADMIN_BILLING_PRICE_CHANGE_APPROVED, ADMIN_BILLING_PRICE_CHANGE_REJECTED,
    ADMIN_BILLING_PRICE_ACTIVATED, ADMIN_BILLING_REFUND_REQUESTED, ADMIN_BILLING_REFUND_APPROVED, ADMIN_BILLING_REFUND_REJECTED,
    ADMIN_BILLING_REFUND_EXECUTED, ADMIN_BILLING_REFUND_FAILED,
    ADMIN_PLATFORM_PAUSED, ADMIN_PLATFORM_RESUMED, ADMIN_FLAG_OVERRIDE_ENABLED, ADMIN_FLAG_OVERRIDE_DISABLED, ADMIN_FLAG_OVERRIDE_RESET,
    ADMIN_AI_CONFIG_CREATED, ADMIN_AI_CONFIG_UPDATED, ADMIN_AI_CONFIG_VALIDATED, ADMIN_AI_EVALUATION_REQUESTED, ADMIN_AI_EVALUATION_COMPLETED, ADMIN_AI_APPROVAL_REQUESTED, ADMIN_AI_APPROVED, ADMIN_AI_REJECTED, ADMIN_AI_ACTIVATED, ADMIN_AI_ROLLED_BACK, ADMIN_AI_RETIRED,
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
