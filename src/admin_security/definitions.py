"""Code-defined vocabulary for W10.13: security-event classification, incident lifecycle, alert categories and thresholds."""

from __future__ import annotations

from typing import Final

from src.application import admin_audit as A
from src.persistence import ALERT_CATEGORIES, INCIDENT_SERVICES, INCIDENT_SEVERITIES, INCIDENT_STATUSES  # noqa: F401  (re-exported)

# --- security events: event_type -> (category, severity). A TYPED PROJECTION of audit_events; there is no second log. ---
SECURITY_EVENT_TYPES: Final[dict[str, tuple[str, str]]] = {
    "account.login": ("authentication", "low"),                  # only result != success is projected
    "account.reset_request": ("password_reset", "low"),
    "account.reset_complete": ("password_reset", "medium"),
    A.ADMIN_ACCESS_DENIED: ("authorization", "medium"),
    A.ADMIN_PLATFORM_ROLE_CHANGE: ("role_change", "high"),       # legacy direct-change events (pre-W10.13 history)
    A.ADMIN_ROLE_CHANGE_REQUESTED: ("role_change", "high"),
    A.ADMIN_ROLE_CHANGE_APPROVED: ("role_change", "high"),
    A.ADMIN_ROLE_CHANGE_REJECTED: ("role_change", "medium"),
    A.ADMIN_ROLE_CHANGE_CANCELLED: ("role_change", "low"),
    A.ADMIN_ROLE_CHANGE_STALE: ("role_change", "medium"),
    A.ADMIN_SESSIONS_REVOKED: ("session_revocation", "medium"),
    A.ADMIN_ACCOUNT_STATUS_CHANGE: ("account_status", "medium"),
    A.ADMIN_STEP_UP_SUCCEEDED: ("step_up", "low"),
    A.ADMIN_STEP_UP_FAILED: ("step_up", "medium"),
    A.ADMIN_AUDIT_EXPORTED: ("audit_export", "medium"),
}
SECURITY_CATEGORIES: Final[tuple[str, ...]] = tuple(sorted({c for c, _ in SECURITY_EVENT_TYPES.values()}))
SECURITY_SEVERITIES: Final[tuple[str, ...]] = ("low", "medium", "high", "critical")
EVENT_PERIODS: Final[dict[str, int]] = {"24h": 24 * 3600, "7d": 7 * 86400, "30d": 30 * 86400, "90d": 90 * 86400}

# --- deterministic anomaly rules (no classifier, no new tracking: counts of existing audit rows per KNOWN account) ---
AUTH_FAILURE_BURST_THRESHOLD: Final = 5
DENIED_BURST_THRESHOLD: Final = 5
BURST_WINDOW_SECONDS: Final = 15 * 60

# --- incidents ---
INCIDENT_TRANSITIONS: Final[dict[str, tuple[str, ...]]] = {
    "open": ("investigating", "monitoring", "resolved"),
    "investigating": ("open", "monitoring", "resolved"),
    "monitoring": ("investigating", "resolved"),
    "resolved": ("investigating", "closed"),   # reopen, or close
    "closed": (),
}
MAX_TITLE: Final = 160
MAX_NARRATIVE: Final = 1000
INCIDENT_PAGE_MAX: Final = 100

# --- alerts: only categories with a real emission seam today. Others are documented as NOT implemented. ---
ALERT_DEFINITIONS: Final[dict[str, dict]] = {
    "auth_failure_burst": {"severity": "high", "source_type": "account", "title": "Repeated failed sign-ins for one account"},
    "admin_access_denied_burst": {"severity": "medium", "source_type": "account", "title": "Repeated denied Admin access by one account"},
    "job_failed": {"severity": "medium", "source_type": "job", "title": "A background job failed terminally"},
}
ALERT_NOT_IMPLEMENTED: Final[tuple[str, ...]] = (
    "provider_outage", "error_rate", "failed_payments", "stale_knowledge_source", "indexing_failure", "support_sla_breach",
    "deletion_deadline", "release_evaluator_failure", "job_backlog",
)

# --- audit export ---
EXPORT_MAX_ROWS: Final = 5000
EXPORT_MAX_DAYS: Final = 90
EXPORT_FORMATS: Final = ("csv", "json")
EXPORT_MIN_REASON: Final = 8
