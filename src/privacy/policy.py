"""Static vocabulary for privacy requests, preparation-run indexing and legal documents (P10B-W10.10). Code-defined."""

from __future__ import annotations

# ---- privacy requests: only types that map to workflows that exist today ----
REQUEST_TYPES = ("data_access", "deletion", "correction", "consent_question", "other_privacy")
REQUEST_TYPE_LABEL = {
    "data_access": "Data access or export", "deletion": "Account or data deletion", "correction": "Correction of my data",
    "consent_question": "Question about a consent or preference", "other_privacy": "Other privacy question",
}
STATUSES = ("submitted", "acknowledged", "in_progress", "waiting_for_user", "completed", "closed", "rejected")
# Operational states only: they carry no legal conclusion.
TRANSITIONS = {
    "submitted": {"acknowledged", "rejected"},
    "acknowledged": {"in_progress", "waiting_for_user", "completed", "rejected"},
    "in_progress": {"waiting_for_user", "completed", "rejected"},
    "waiting_for_user": {"in_progress", "completed", "rejected", "closed"},
    "completed": {"closed"},
    "rejected": {"closed"},
    "closed": set(),
}
RESULT_CATEGORIES = ("export_provided", "deletion_performed", "correction_made", "information_provided", "no_action_required", "unable_to_verify")
SOURCES = ("candidate_portal", "admin_recorded")
OPEN_STATUSES = ("submitted", "acknowledged", "in_progress", "waiting_for_user")
MAX_NOTE = 1000

# ---- preparation-run ownership index ----
RUN_STATES = ("started", "ready", "failed", "purge_failed")
RUN_SOURCES = ("created", "backfill", "lazy")
COVERAGE_VERSION = 1

# ---- legal documents (the three that exist as product surfaces) ----
LEGAL_DOCUMENTS = {
    "terms": ("Terms of use", "/terms"),
    "privacy": ("Privacy notice", "/privacy"),
    "ai_transparency": ("AI transparency", "/ai-transparency"),
}
LEGAL_VERSION_STATES = ("draft", "published", "retired")
ACCEPTANCE_SOURCES = ("signup", "settings", "reacceptance")   # code-defined; only "settings" is wired today
BASELINE_VERSION = "baseline-1"
MAX_VERSION_LABEL = 32
JOB_ACCOUNT_DELETE = "privacy_account_delete"
JOB_BACKFILL = "privacy_preparation_backfill"
JOB_PURGE = "privacy_preparation_purge"
BACKFILL_BATCH = 500
