"""Governed source registry (GKB-1). Reuses the existing manifest vocabulary; adds an explicit, audited approval lifecycle that is separate from "official" or "present locally".

Rules enforced here and again by database CHECK constraints: a synthetic fixture can never be approved; an approved source must have a VERIFIED licence; unknown facts stay
``unknown``/NULL; a re-import never changes the approval state or verified licence of a registered source; every approval transition is audited. Registry membership authorizes
nothing: ingestion and runtime use are separate approvals, and this module performs no download and no ingestion."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from src.knowledge_foundation import enums as E
from src.persistence import GlobalSource, GlobalSourceEvent

__all__ = ["SourceRegistry", "RegistryError", "TRANSITIONS", "UNAUTHORIZED_BY_DEFAULT"]

UNAUTHORIZED_BY_DEFAULT = ("discovered", "licensing_pending")

TRANSITIONS: dict[str, tuple[str, ...]] = {
    "discovered": ("licensing_pending", "restricted", "rejected"),
    "licensing_pending": ("licensing_verified", "restricted", "rejected"),
    "licensing_verified": ("approved_for_ingestion", "restricted", "rejected"),
    "approved_for_ingestion": ("approved_for_runtime_use", "restricted", "superseded", "rejected"),
    "approved_for_runtime_use": ("restricted", "superseded"),
    "restricted": ("licensing_pending", "rejected"),
    "rejected": (),
    "superseded": (),
}
_DESCRIPTIVE = ("publisher", "dataset_name", "dataset_version", "source_url", "geographies", "languages", "taxonomy", "evidence_category", "publication_date", "reference_period",
                "update_cadence", "precedence_category", "evidence_class", "operational_status", "validation_status", "retrieved_at", "checksum_sha256", "provenance")
_ENUM_FIELDS = {"licence_status": E.LICENCE_STATUSES, "attribution_required": E.TRI_STATES, "redistribution": E.TRI_STATES, "origin": E.ORIGINS, "precedence_category": E.PRECEDENCE,
                "validation_status": E.VALIDATION}


class RegistryError(ValueError):
    """A registry rule was violated. The message never carries source content."""


def _row(s: GlobalSource) -> dict[str, Any]:
    return {c.name: getattr(s, c.name) for c in s.__table__.columns}


class SourceRegistry:
    def __init__(self, session_factory) -> None:
        self._sf = session_factory

    # -------------------------------------------------------------------------------------------------- registration
    def register(self, source_id: str, **fields: Any) -> dict[str, Any]:
        """Register a source (idempotent). New sources start ``discovered`` with a licence status of at most ``stated_unverified``. For an existing source ONLY descriptive metadata
        is refreshed: approval status, licence verification, attribution and redistribution are never changed by a re-registration."""
        if not source_id or not isinstance(source_id, str) or len(source_id) > 64:
            raise RegistryError("invalid source id")
        for k, allowed in _ENUM_FIELDS.items():
            if k in fields and fields[k] is not None and fields[k] not in allowed:
                raise RegistryError(f"invalid value for {k}")
        if fields.get("evidence_class") not in (None, *E.EVIDENCE_CLASSES):
            raise RegistryError("invalid evidence class")
        if fields.get("licence_status") == "verified":
            raise RegistryError("a licence is verified only through set_licence")
        if fields.get("approval_status") not in (None, "discovered", "licensing_pending", "restricted"):
            raise RegistryError("a source cannot be registered as approved")
        with self._sf() as s:
            existing = s.scalar(select(GlobalSource).where(GlobalSource.source_id == source_id))
            if existing is not None:
                for k in _DESCRIPTIVE:
                    if k in fields:
                        setattr(existing, k, fields[k])
                if "licence_id" in fields and existing.licence_status != "verified":
                    existing.licence_id = fields["licence_id"]
                    existing.licence_status = fields.get("licence_status", existing.licence_status)
                s.commit()
                return _row(existing)
            row = GlobalSource(source_id=source_id, geographies=[], languages=[], provenance={})
            for k, v in fields.items():
                if hasattr(row, k) and k not in ("id", "source_id"):
                    setattr(row, k, v)
            if row.origin in E.FIXTURE_ORIGINS and row.approval_status not in ("restricted", "rejected"):
                row.approval_status = "restricted"                                 # a fixture is fixture-only from the start
            s.add(row)
            try:
                s.commit()
            except IntegrityError as exc:
                s.rollback()
                raise RegistryError("source violates a registry constraint") from exc
            s.add(GlobalSourceEvent(source_row_id=row.id, from_status=None, to_status=row.approval_status, reason="registered"))
            s.commit()
            return _row(row)

    def get(self, source_id: str) -> dict[str, Any] | None:
        with self._sf() as s:
            r = s.scalar(select(GlobalSource).where(GlobalSource.source_id == source_id))
            return _row(r) if r else None

    def list(self, *, approval_status: str | None = None) -> list[dict[str, Any]]:
        with self._sf() as s:
            stmt = select(GlobalSource).order_by(GlobalSource.source_id)
            if approval_status:
                stmt = stmt.where(GlobalSource.approval_status == approval_status)
            return [_row(r) for r in s.scalars(stmt)]

    # -------------------------------------------------------------------------------------------------- licence
    def set_licence(self, source_id: str, *, licence_id: str | None, licence_status: str, attribution_required: str = "unknown", redistribution: str = "unknown",
                    actor_user_id: int | None = None) -> dict[str, Any]:
        """Record licence facts. Moving a licence away from ``verified`` while the source is approved is refused: restrict the source first (an approval never survives a
        licence that is no longer verified)."""
        if licence_status not in E.LICENCE_STATUSES or attribution_required not in E.TRI_STATES or redistribution not in E.TRI_STATES:
            raise RegistryError("invalid licence value")
        with self._sf() as s:
            r = s.scalar(select(GlobalSource).where(GlobalSource.source_id == source_id))
            if r is None:
                raise RegistryError("unknown source")
            if r.approval_status in ("approved_for_ingestion", "approved_for_runtime_use") and licence_status != "verified":
                raise RegistryError("restrict the approved source before changing its licence away from verified")
            r.licence_id, r.licence_status, r.attribution_required, r.redistribution = licence_id, licence_status, attribution_required, redistribution
            s.commit()
            return _row(r)

    # -------------------------------------------------------------------------------------------------- lifecycle
    def transition(self, source_id: str, to_status: str, *, actor_user_id: int | None = None, reason: str | None = None) -> dict[str, Any]:
        """One audited approval transition. Allowed edges only; ``approved_*`` needs a verified licence and a non-fixture origin; ``approved_for_runtime_use`` also needs a
        known, non-synthetic origin and a recorded validation status."""
        if to_status not in E.APPROVAL_STATES:
            raise RegistryError("unknown approval status")
        with self._sf() as s:
            r = s.scalar(select(GlobalSource).where(GlobalSource.source_id == source_id))
            if r is None:
                raise RegistryError("unknown source")
            if to_status not in TRANSITIONS[r.approval_status]:
                raise RegistryError(f"transition {r.approval_status} -> {to_status} is not allowed")
            if to_status in ("approved_for_ingestion", "approved_for_runtime_use"):
                if r.origin in E.FIXTURE_ORIGINS:
                    raise RegistryError("a synthetic fixture can never be approved")
                if r.licence_status != "verified":
                    raise RegistryError("approval requires a verified licence")
            if to_status == "approved_for_runtime_use" and (r.origin not in E.EVIDENCE_ORIGINS or r.validation_status in ("unknown",)):
                raise RegistryError("runtime use requires a known non-fixture origin and a recorded validation status")
            from_status = r.approval_status
            r.approval_status = to_status
            s.add(GlobalSourceEvent(source_row_id=r.id, from_status=from_status, to_status=to_status, actor_user_id=actor_user_id, reason=(reason or None) and reason[:300]))
            s.commit()
            return _row(r)

    def supersede(self, source_id: str, *, by: str, actor_user_id: int | None = None) -> dict[str, Any]:
        if self.get(by) is None:
            raise RegistryError("unknown superseding source")
        self.transition(source_id, "superseded", actor_user_id=actor_user_id, reason=f"superseded by {by}"[:300])
        with self._sf() as s:
            r = s.scalar(select(GlobalSource).where(GlobalSource.source_id == source_id))
            r.superseded_by = by
            s.commit()
            return _row(r)

    def events(self, source_id: str) -> list[dict[str, Any]]:
        with self._sf() as s:
            r = s.scalar(select(GlobalSource).where(GlobalSource.source_id == source_id))
            if r is None:
                return []
            rows = s.scalars(select(GlobalSourceEvent).where(GlobalSourceEvent.source_row_id == r.id).order_by(GlobalSourceEvent.id)).all()
            return [{"from": e.from_status, "to": e.to_status, "actor_user_id": e.actor_user_id, "reason": e.reason} for e in rows]

    # -------------------------------------------------------------------------------------------------- decisions the rest of the system may ask
    def can_ingest(self, source_id: str) -> bool:
        r = self.get(source_id)
        return bool(r and r["approval_status"] in ("approved_for_ingestion", "approved_for_runtime_use") and r["licence_status"] == "verified" and r["origin"] not in E.FIXTURE_ORIGINS)

    def can_serve_as_evidence(self, source_id: str) -> bool:
        """True only for an approved-for-runtime-use, verified-licence source with a genuine (non-fixture, known) origin. Everything else, including every synthetic fixture
        and every official-but-unapproved source, is not evidence."""
        r = self.get(source_id)
        return bool(r and r["approval_status"] == "approved_for_runtime_use" and r["licence_status"] == "verified" and r["origin"] in E.EVIDENCE_ORIGINS)

    def freshness(self, source_id: str, *, now: datetime | None = None) -> dict[str, Any]:
        """Freshness metadata only (never a claim of currency): age in days since retrieval when recorded, else unknown."""
        r = self.get(source_id)
        if r is None:
            raise RegistryError("unknown source")
        at = r["retrieved_at"]
        if at is None:
            return {"retrieved_at": None, "age_days": None, "freshness": "unknown"}
        at = at if at.tzinfo else at.replace(tzinfo=timezone.utc)
        age = ((now or datetime.now(timezone.utc)) - at).days
        return {"retrieved_at": at.isoformat(), "age_days": age, "freshness": "recorded"}
