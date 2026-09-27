"""Opportunity domain vocabulary & bounds (P10B Wave 6).

An Opportunity is a candidate's private preparation context for ONE specific job (role + company
+ optional JD). This module holds the bounded, UI-agnostic vocabulary and validation helpers; the
ORM lives in ``src/persistence.py`` and the owner-scoped orchestration in
``src/application/opportunity_service.py``. Nothing here makes a model or provider call.
"""

from __future__ import annotations

__all__ = [
    "OPPORTUNITY_STATUSES",
    "ACTIVE_STATUSES",
    "DEFAULT_STATUS",
    "ARCHIVED_STATUS",
    "MAX_TITLE",
    "MAX_ROLE",
    "MAX_COMPANY",
    "MAX_LOCATION",
    "MAX_DOMAIN",
    "MAX_NOTES",
    "is_valid_status",
    "derive_title",
]

# Bounded lifecycle. This is a candidate-preparation product, NOT an ATS - keep it small.
DEFAULT_STATUS = "active"
ARCHIVED_STATUS = "archived"
OPPORTUNITY_STATUSES: tuple[str, ...] = (
    "active",        # preparing / pursuing
    "interviewing",  # actively interviewing
    "offer",         # offer stage
    "closed",        # no longer pursuing (kept for reference)
    "archived",      # hidden from the active list
)
# Statuses that appear in the default (non-archived) list.
ACTIVE_STATUSES: tuple[str, ...] = ("active", "interviewing", "offer", "closed")

MAX_TITLE = 200
MAX_ROLE = 200
MAX_COMPANY = 200
MAX_LOCATION = 200
MAX_DOMAIN = 500
MAX_NOTES = 4000


def is_valid_status(status: str) -> bool:
    return status in OPPORTUNITY_STATUSES


def derive_title(*, target_role: str, company_name: str | None, company_location: str | None) -> str:
    """A deterministic display label from role/company/location (no model call).

    "Senior PM - Acme - Berlin" style, bounded. Never fabricates content: only joins the parts
    the candidate actually provided. Falls back to the role, then a generic label.
    """
    parts = [p.strip() for p in (target_role, company_name, company_location) if p and p.strip()]
    if not parts:
        return "Untitled opportunity"
    return " - ".join(parts)[:MAX_TITLE]
