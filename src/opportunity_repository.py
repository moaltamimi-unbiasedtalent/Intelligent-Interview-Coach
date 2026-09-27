"""Owner-scoped Opportunity persistence (P10B Wave 6).

Every read and write is scoped to ``user_id``; a foreign/unknown id returns None/False and never
another user's data (the route turns None into a 404). Returns safe dict projections only (never
ORM objects). Mirrors the existing repository conventions (`InterviewRepository`/`MemoryRepository`).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from src.opportunity import ARCHIVED_STATUS, DEFAULT_STATUS
from src.persistence import CandidateDocument, Interview, Opportunity

__all__ = ["OpportunityRepository"]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class OpportunityRepository:
    def __init__(self, session_factory: sessionmaker) -> None:
        self._session_factory = session_factory

    # -- helpers -----------------------------------------------------------

    @staticmethod
    def _owned(session: Session, user_id: int, opportunity_id: int) -> Opportunity | None:
        row = session.get(Opportunity, opportunity_id)
        if row is None or row.user_id != user_id:
            return None
        return row

    @staticmethod
    def _to_dict(o: Opportunity) -> dict[str, Any]:
        return {
            "id": o.id,
            "title": o.title,
            "target_role": o.target_role,
            "company_name": o.company_name,
            "company_location": o.company_location,
            "company_country": o.company_country,
            "company_domain": o.company_domain,
            "job_description_document_id": o.job_description_document_id,
            "status": o.status,
            "notes": o.notes,
            "created_at": o.created_at.isoformat() if o.created_at else None,
            "updated_at": o.updated_at.isoformat() if o.updated_at else None,
            "archived_at": o.archived_at.isoformat() if o.archived_at else None,
        }

    def document_is_owned_jd(self, user_id: int, document_id: int) -> bool:
        """True only if the document exists, is owned by the user, and is a job_description."""
        with self._session_factory() as session:
            doc = session.get(CandidateDocument, document_id)
            return bool(doc and doc.user_id == user_id and doc.category == "job_description")

    # -- CRUD --------------------------------------------------------------

    def create(self, user_id: int, *, title: str, target_role: str,
               company_name: str | None = None, company_location: str | None = None,
               company_country: str | None = None, company_domain: str | None = None,
               job_description_document_id: int | None = None,
               notes: str | None = None) -> dict[str, Any]:
        with self._session_factory() as session:
            o = Opportunity(
                user_id=user_id, title=title, target_role=target_role,
                company_name=company_name, company_location=company_location,
                company_country=company_country, company_domain=company_domain,
                job_description_document_id=job_description_document_id,
                status=DEFAULT_STATUS, notes=notes,
            )
            session.add(o)
            session.commit()
            session.refresh(o)
            return self._to_dict(o)

    def list_for_user(self, user_id: int, *, include_archived: bool = False) -> list[dict[str, Any]]:
        with self._session_factory() as session:
            stmt = select(Opportunity).where(Opportunity.user_id == user_id)
            if not include_archived:
                stmt = stmt.where(Opportunity.status != ARCHIVED_STATUS)
            stmt = stmt.order_by(Opportunity.updated_at.desc(), Opportunity.id.desc())
            return [self._to_dict(o) for o in session.execute(stmt).scalars().all()]

    def get(self, user_id: int, opportunity_id: int) -> dict[str, Any] | None:
        with self._session_factory() as session:
            o = self._owned(session, user_id, opportunity_id)
            return self._to_dict(o) if o else None

    def update(self, user_id: int, opportunity_id: int, *, fields: dict[str, Any]) -> dict[str, Any] | None:
        """Partial update of owner-set fields. Unknown keys are ignored by the caller (the service
        validates and bounds before calling). Returns the updated dict, or None if not owned."""
        with self._session_factory() as session:
            o = self._owned(session, user_id, opportunity_id)
            if o is None:
                return None
            for key, value in fields.items():
                setattr(o, key, value)
            session.commit()
            session.refresh(o)
            return self._to_dict(o)

    def set_status(self, user_id: int, opportunity_id: int, status: str) -> dict[str, Any] | None:
        with self._session_factory() as session:
            o = self._owned(session, user_id, opportunity_id)
            if o is None:
                return None
            o.status = status
            o.archived_at = _utcnow() if status == ARCHIVED_STATUS else None
            session.commit()
            session.refresh(o)
            return self._to_dict(o)

    def delete(self, user_id: int, opportunity_id: int) -> bool:
        with self._session_factory() as session:
            o = self._owned(session, user_id, opportunity_id)
            if o is None:
                return False
            session.delete(o)
            session.commit()
            return True

    def clear_jd_links(self, document_id: int) -> None:
        """When a JD document is deleted, clear it from any Opportunity that referenced it so the
        Opportunity survives without pointing at inaccessible content. (On PostgreSQL the FK SET
        NULL also does this; this keeps SQLite - where the ALTER-added FK is absent - consistent.)"""
        with self._session_factory() as session:
            rows = session.execute(
                select(Opportunity).where(Opportunity.job_description_document_id == document_id)
            ).scalars().all()
            for o in rows:
                o.job_description_document_id = None
            if rows:
                session.commit()

    # -- associations (read-only projections) ------------------------------

    def linked_interview_ids(self, user_id: int, opportunity_id: int) -> list[int]:
        """Completed interviews linked to this Opportunity (owner-scoped). Empty if not owned."""
        with self._session_factory() as session:
            if self._owned(session, user_id, opportunity_id) is None:
                return []
            stmt = select(Interview.id).where(
                Interview.user_id == user_id, Interview.opportunity_id == opportunity_id
            ).order_by(Interview.id.desc())
            return [row for row in session.execute(stmt).scalars().all()]
