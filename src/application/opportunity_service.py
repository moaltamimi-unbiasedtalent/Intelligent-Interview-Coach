"""Owner-scoped Opportunity orchestration (P10B Wave 6).

Validates and bounds candidate input, derives a display title, enforces JD ownership (a foreign or
non-JD document is rejected), and exposes a bounded CONTEXT projection that Prepare/Practice
pre-populate from. It orchestrates existing services rather than cloning them: candidate evidence
stays in the evidence system, company research stays in the Wave 5 engine, interview history stays
in its own store. Nothing here makes a model or provider call.

Errors: invalid input raises ValidationError (route -> 422); a foreign/unknown id returns None
(route -> 404). All access is owner-scoped by the trusted ``user_id`` (never client-supplied).
"""

from __future__ import annotations

from typing import Any

from src.application.errors import ValidationError
from src.opportunity import (
    ARCHIVED_STATUS,
    MAX_COMPANY,
    MAX_DOMAIN,
    MAX_LOCATION,
    MAX_NOTES,
    MAX_ROLE,
    MAX_TITLE,
    derive_title,
    is_valid_status,
)
from src.opportunity_repository import OpportunityRepository

__all__ = ["OpportunityApplicationService"]


def _clean(value: str | None, *, max_len: int) -> str | None:
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    if len(value) > max_len:
        raise ValidationError("A field exceeds its maximum length.")
    return value


def _clean_country(value: str | None) -> str | None:
    v = _clean(value, max_len=2)
    if v is None:
        return None
    if len(v) != 2 or not v.isalpha():
        raise ValidationError("Country must be a 2-letter code.")
    return v.upper()


class OpportunityApplicationService:
    def __init__(self, repo: OpportunityRepository) -> None:
        self._repo = repo

    # -- create / read -----------------------------------------------------

    def create(self, user_id: int, *, target_role: str, title: str | None = None,
               company_name: str | None = None, company_location: str | None = None,
               company_country: str | None = None, company_domain: str | None = None,
               job_description_document_id: int | None = None,
               notes: str | None = None) -> dict[str, Any]:
        role = _clean(target_role, max_len=MAX_ROLE)
        if not role:
            raise ValidationError("A target role is required.")
        company = _clean(company_name, max_len=MAX_COMPANY)
        location = _clean(company_location, max_len=MAX_LOCATION)
        country = _clean_country(company_country)
        domain = _clean(company_domain, max_len=MAX_DOMAIN)
        notes_clean = _clean(notes, max_len=MAX_NOTES)
        label = _clean(title, max_len=MAX_TITLE) or derive_title(
            target_role=role, company_name=company, company_location=location)

        self._validate_jd(user_id, job_description_document_id)

        return self._repo.create(
            user_id, title=label, target_role=role, company_name=company,
            company_location=location, company_country=country, company_domain=domain,
            job_description_document_id=job_description_document_id, notes=notes_clean)

    def list(self, user_id: int, *, include_archived: bool = False) -> list[dict[str, Any]]:
        return self._repo.list_for_user(user_id, include_archived=include_archived)

    def get(self, user_id: int, opportunity_id: int) -> dict[str, Any] | None:
        return self._repo.get(user_id, opportunity_id)

    # -- update / lifecycle ------------------------------------------------

    def update(self, user_id: int, opportunity_id: int, *, patch: dict[str, Any]) -> dict[str, Any] | None:
        """Partial update. Only owner-settable fields are honoured; each is validated/bounded."""
        fields: dict[str, Any] = {}
        if "target_role" in patch:
            role = _clean(patch["target_role"], max_len=MAX_ROLE)
            if not role:
                raise ValidationError("A target role is required.")
            fields["target_role"] = role
        if "title" in patch:
            fields["title"] = _clean(patch["title"], max_len=MAX_TITLE) or None
        if "company_name" in patch:
            fields["company_name"] = _clean(patch["company_name"], max_len=MAX_COMPANY)
        if "company_location" in patch:
            fields["company_location"] = _clean(patch["company_location"], max_len=MAX_LOCATION)
        if "company_country" in patch:
            fields["company_country"] = _clean_country(patch["company_country"])
        if "company_domain" in patch:
            fields["company_domain"] = _clean(patch["company_domain"], max_len=MAX_DOMAIN)
        if "notes" in patch:
            fields["notes"] = _clean(patch["notes"], max_len=MAX_NOTES)
        if "job_description_document_id" in patch:
            jd = patch["job_description_document_id"]
            self._validate_jd(user_id, jd)
            fields["job_description_document_id"] = jd
        if "status" in patch:
            status = patch["status"]
            if not is_valid_status(status):
                raise ValidationError("Unknown opportunity status.")
            # Status changes go through set_status so archived_at stays consistent.
            if not fields:
                return self._repo.set_status(user_id, opportunity_id, status)
            fields["status"] = status
            if status == ARCHIVED_STATUS:
                from datetime import datetime, timezone
                fields["archived_at"] = datetime.now(timezone.utc)
            else:
                fields["archived_at"] = None
        if "title" in fields and fields["title"] is None:
            # Re-derive a title if it was cleared, using the current + patched values.
            current = self._repo.get(user_id, opportunity_id)
            if current is None:
                return None
            fields["title"] = derive_title(
                target_role=fields.get("target_role", current["target_role"]),
                company_name=fields.get("company_name", current["company_name"]),
                company_location=fields.get("company_location", current["company_location"]))
        if not fields:
            return self._repo.get(user_id, opportunity_id)
        return self._repo.update(user_id, opportunity_id, fields=fields)

    def archive(self, user_id: int, opportunity_id: int) -> dict[str, Any] | None:
        return self._repo.set_status(user_id, opportunity_id, ARCHIVED_STATUS)

    def set_status(self, user_id: int, opportunity_id: int, status: str) -> dict[str, Any] | None:
        if not is_valid_status(status):
            raise ValidationError("Unknown opportunity status.")
        return self._repo.set_status(user_id, opportunity_id, status)

    def delete(self, user_id: int, opportunity_id: int) -> bool:
        return self._repo.delete(user_id, opportunity_id)

    # -- context for Prepare / Practice ------------------------------------

    def context(self, user_id: int, opportunity_id: int) -> dict[str, Any] | None:
        """A bounded context projection that Prepare/Practice pre-populate from. Owner-scoped; a
        stale JD link is reported as unavailable so no inaccessible content is implied."""
        o = self._repo.get(user_id, opportunity_id)
        if o is None:
            return None
        jd_id = o["job_description_document_id"]
        jd_available = bool(jd_id) and self._repo.document_is_owned_jd(user_id, jd_id)
        return {
            "opportunity_id": o["id"],
            "title": o["title"],
            "target_role": o["target_role"],
            "company_name": o["company_name"],
            "company_location": o["company_location"],
            "company_country": o["company_country"],
            "company_domain": o["company_domain"],
            "job_description_document_id": jd_id if jd_available else None,
            "jd_available": jd_available,
        }

    def overview(self, user_id: int, opportunity_id: int) -> dict[str, Any] | None:
        """The Opportunity home projection: the record plus linked completed-interview ids and a
        bounded JD availability flag. Derived at read time (nothing extra persisted)."""
        o = self._repo.get(user_id, opportunity_id)
        if o is None:
            return None
        jd_id = o["job_description_document_id"]
        interview_ids = self._repo.linked_interview_ids(user_id, opportunity_id)
        return {
            **o,
            "jd_available": bool(jd_id) and self._repo.document_is_owned_jd(user_id, jd_id),
            "interview_ids": interview_ids,
            "interview_count": len(interview_ids),
        }

    # -- validation --------------------------------------------------------

    def _validate_jd(self, user_id: int, document_id: int | None) -> None:
        if document_id is None:
            return
        if not self._repo.document_is_owned_jd(user_id, document_id):
            # Foreign/missing/non-JD document: reject without disclosing anything.
            raise ValidationError("The selected job description is not available.")
