"""Allow-list enforcement for audit and incident context (05E, W9.8-D9 / W10.10-AUDIT-CTX).

``audit_events.context`` and ``incident_events.meta`` are small JSON objects that must carry METADATA only: identifiers, enum states, counts, field NAMES, flags.
Until 05E this was call-site discipline: ``build_audit`` screened admin events by forbidden key fragments, but candidate, auth and incident writers built the
object themselves, so a careless key (``note``, ``email``, ``text``) would have been persisted. This module is the single choke point, installed as a SQLAlchemy
``before_insert`` listener on both models, so EVERY write path (``AuditRepository.record``, the atomic ``_stage_audit`` helpers, the invitation and foundation
writers, the incident history) is checked at the last moment before the row is written.

Rules (all code-defined; no setting can widen them):

* every key, at any depth, must be on ``ALLOWED_CONTEXT_KEYS`` (incident ``meta``: ``ALLOWED_INCIDENT_META_KEYS``) and look like a code identifier, so a key built from
  user text fails;
* a few keys that could be abused to carry free text have a closed set of values (``VALUE_SPECS``);
* values are bounded: strings at most ``MAX_STRING`` characters (``reason`` is an operator reason, bounded at 200), lists at most ``MAX_ITEMS``, depth at most
  ``MAX_DEPTH``, the whole object at most ``MAX_JSON_CHARS`` characters;
* STRICT mode (tests, evaluators, development: ``AUDIT_CONTEXT_STRICT=1``, set by ``tests/conftest.py``) raises ``AuditContextRejected`` naming the offending
  KEY paths, so a new free-text key fails the suite at the call site. In every other environment the offending entries are DROPPED (never stored) and a
  ``dropped_keys`` count is recorded: an audited operation is never broken by a logging mistake, and nothing outside the allow-list ever reaches the database.

Adding a legitimate key is a deliberate, reviewed edit of ``ALLOWED_CONTEXT_KEYS`` (the static scan test lists every key the source can emit and fails on an
unlisted one). The allow-list is not a promise that a value is free of personal data, only that the shape is metadata; free-text fields are not on it.
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Final

log = logging.getLogger("ask4mo.audit.allowlist")

MAX_STRING: Final = 200
MAX_ITEMS: Final = 50
MAX_DEPTH: Final = 4
MAX_JSON_CHARS: Final = 4000
_KEY = re.compile(r"^[a-z][a-z0-9_]{0,63}$")

ALLOWED_CONTEXT_KEYS: Final[frozenset[str]] = frozenset({
    "action", "actor", "affected_service", "after", "after_assignee", "after_plan", "after_version", "alert_public_id", "alias_id", "amount_minor",
    "approval_public_id", "assignment_source", "authority_level", "batch_size", "before", "before_assignee", "before_plan", "before_role", "before_version", "bulk",
    "capability", "career_geography", "category", "changed", "changed_fields", "changed_keys", "channel", "checkpoints_failed", "checkpoints_purged",
    "coaching_style", "complete", "config_hash", "config_id", "config_version", "consent", "conversation_language", "copied_from", "count", "currency", "decision",
    "display_name", "document", "elevation", "eligible", "email_bound", "email_submitted", "environment", "evaluation_public_id", "exceptions", "failed_checks",
    "fields_changed", "files_purged", "filters", "flag_key", "format", "from", "grouped_by", "incident_public_id", "integration", "interface_locale",
    "invitation_id", "invitations_removed", "job_public_id", "job_type", "language", "licence_class", "links_expired", "member_user_id", "members_removed",
    "message_id", "message_type", "method", "metric_count", "new", "new_effective", "new_override", "new_owner", "new_state", "new_status", "note_id", "old",
    "old_effective", "old_hash", "old_override", "old_state", "old_status", "origin", "outcome", "owner_admin_user_id", "path", "payment_public_id", "plan_code",
    "plan_version_id", "previous_activation_public_id", "provider", "reason", "reason_category", "reason_code", "reasons", "records", "refund_public_id", "replaced_version",
    "replaced_version_public_id", "report_id", "request_public_id", "request_type", "requested_role", "resource_type", "response_detail", "result_category",
    "retired_version", "revision", "revoked_ref", "role", "rollback_of", "row_count", "scope", "sessions_revoked", "severity", "shared", "shares_revoked", "slot",
    "source", "source_edition", "source_id", "source_public_id", "state", "status", "step", "subject_type", "subject_user_id", "target", "target_role",
    "target_user_id", "terms_version", "ticket_id", "ticket_public_id", "to", "ttl_days", "validation_digest", "version", "version_id", "version_public_id", "via",
    "visible_to_members", "window", "window_seconds",
    # nested keys seen inside the objects above (a scope, a before/after summary, a setting snapshot)
    "browser_tts_allowed", "measure", "occupation_level", "pay_period", "period", "source_ref", "stt_enabled",
    # 03C bulk user actions: batch counters, the request hash (a hex digest) and the closed reason-code vocabulary used as keys of ``skipped_by_reason`` / ``failed_by_reason``
    # (src/admin_users/bulk.py: SELF, HIGHER, LAST_ADMIN, NOT_FOUND, NO_SESSIONS, NO_LINKS, APPLY_ERROR). All are identifiers or counts; no free text.
    "applied", "apply_error", "batch_id", "failed", "failed_by_reason", "higher_authority", "last_active_platform_admin", "no_live_sessions", "no_pending_verification",
    "not_found", "request_hash", "requested", "self", "skipped", "skipped_by_reason", "unique",
    # this module's own marker
    "dropped_keys",
})

ALLOWED_INCIDENT_META_KEYS: Final[frozenset[str]] = frozenset({"affected_service", "fields_changed", "severity", "ticket_public_id", "dropped_keys"})

# The code-defined platform roles (``admin_permissions.ROLE_*``); a test pins this set to the real presets so it cannot drift.
_PLATFORM_ROLES: Final = frozenset({"user", "platform_admin", "support_operator", "billing_admin", "knowledge_admin", "security_privacy_admin", "operations_admin"})

# The code-defined workspace roles (``persistence.WORKSPACE_ROLES``): ``target_role`` is also the workspace role of a removed or re-roled member.
_WORKSPACE_ROLES: Final = frozenset({"workspace_owner", "workspace_admin", "workspace_member"})

# Keys that could otherwise carry free text: closed value sets. ``None`` is always allowed.
VALUE_SPECS: Final[dict[str, frozenset[str]]] = {
    "display_name": frozenset({"set"}),                       # the value is the user's name: only the fact that it was set
    "target_role": frozenset({"set"}) | _PLATFORM_ROLES | _WORKSPACE_ROLES,       # in preferences the value is user text: only "set"; otherwise a platform or workspace role
    "document": frozenset({"terms", "privacy", "ai_transparency"}),
}


class AuditContextRejected(ValueError):
    """Strict mode: the context contains a key or value shape that is not allowed. The message lists KEY PATHS only, never a value."""


def strict_mode() -> bool:
    return os.environ.get("AUDIT_CONTEXT_STRICT", "").strip().lower() in ("1", "true", "yes")


def _scalar_ok(key: str | None, value: Any) -> bool:
    if value is None or isinstance(value, (bool, int, float)):
        return True
    if isinstance(value, str):
        spec = VALUE_SPECS.get(key or "")
        if spec is not None:
            return value in spec
        return len(value) <= MAX_STRING
    return False


def _clean(value: Any, key: str | None, allowed: frozenset[str], path: str, depth: int, problems: list[str]) -> Any:
    """Return the allowed projection of ``value``; every dropped entry appends its key path (never its value) to ``problems``."""
    if depth > MAX_DEPTH:
        problems.append(f"{path or 'context'}: too deep")
        return None
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for k, v in value.items():
            where = f"{path}.{k}" if path else str(k)
            if not isinstance(k, str) or not _KEY.match(k) or k not in allowed:
                problems.append(f"{where}: key not allowed")
                continue
            if isinstance(v, (dict, list, tuple)):
                cleaned = _clean(v, k, allowed, where, depth + 1, problems)
                out[k] = cleaned
            elif _scalar_ok(k, v):
                out[k] = v
            else:
                problems.append(f"{where}: value not allowed")
        return out
    if isinstance(value, (list, tuple)):
        if len(value) > MAX_ITEMS:
            problems.append(f"{path or 'context'}: too many items")
            value = list(value)[:MAX_ITEMS]
        items: list[Any] = []
        for i, v in enumerate(value):
            where = f"{path}[{i}]"
            if isinstance(v, (dict, list, tuple)):
                items.append(_clean(v, key, allowed, where, depth + 1, problems))
            elif _scalar_ok(key, v):
                items.append(v)
            else:
                problems.append(f"{where}: value not allowed")
        return items
    if _scalar_ok(key, value):
        return value
    problems.append(f"{path or 'context'}: value not allowed")
    return None


def sanitize(context: Any, allowed: frozenset[str] = ALLOWED_CONTEXT_KEYS, *, strict: bool | None = None) -> tuple[Any, list[str]]:
    """Validate and project ``context``. Returns (clean_context, problems). In strict mode a problem raises ``AuditContextRejected``."""
    if context is None:
        return None, []
    if not isinstance(context, dict):
        problems = ["context: not an object"]
        if strict if strict is not None else strict_mode():
            raise AuditContextRejected("; ".join(problems))
        return None, problems
    problems: list[str] = []
    clean = _clean(context, None, allowed, "", 0, problems)
    if len(json.dumps(clean, default=str)) > MAX_JSON_CHARS:
        problems.append("context: too large")
        clean = {}
    if problems:
        if strict if strict is not None else strict_mode():
            raise AuditContextRejected("; ".join(problems[:10]))
        log.warning("audit context entries dropped (%d); key paths only: %s", len(problems), "; ".join(problems[:5]))
        clean = {**(clean or {}), "dropped_keys": len(problems)}
    return (clean or None), problems


def _before_insert_audit(_mapper, _connection, target) -> None:
    clean, _ = sanitize(target.context, ALLOWED_CONTEXT_KEYS)
    target.context = clean


def _before_insert_incident(_mapper, _connection, target) -> None:
    clean, _ = sanitize(target.meta, ALLOWED_INCIDENT_META_KEYS)
    target.meta = clean


def install(audit_model: Any, incident_model: Any) -> None:
    """Register the listeners (called once from ``src.persistence``). Idempotent."""
    from sqlalchemy import event

    if not event.contains(audit_model, "before_insert", _before_insert_audit):
        event.listen(audit_model, "before_insert", _before_insert_audit)
    if not event.contains(incident_model, "before_insert", _before_insert_incident):
        event.listen(incident_model, "before_insert", _before_insert_incident)
