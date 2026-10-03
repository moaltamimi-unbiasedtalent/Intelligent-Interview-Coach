"""Legal document registry and recorded acceptance (PRIV-W9-02, P10B-W10.10).

The text of Terms, Privacy and AI transparency stays in the product's own pages. This registers VERSIONS of them: a label, the
page reference, an effective date and (for new versions) a content hash. Published versions are immutable: new text is a new
version. Exactly one version per document is current (published). Acceptance is recorded per user and version with a timestamp and a
code-defined source; there is no IP, device or fingerprint. History is never fabricated: users who predate this have NO
recorded acceptance and are shown as such. Legal acceptance is a version acknowledgement, not consent to optional processing.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Callable

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from src.admin_repository import _stage
from src.auth_repository import AccountRepository
from src.persistence import ACCOUNT_STATUS_ACTIVE, LegalAcceptance, LegalDocument, LegalDocumentVersion as V, User, utcnow
from src.privacy import policy as P

_LABEL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,31}$")
_HASH = re.compile(r"^[0-9a-f]{64}$")


class LegalNotFound(Exception):
    pass


class LegalValidationError(Exception):
    pass


class LegalConflict(Exception):
    pass


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


class LegalService:
    def __init__(self, session_factory, clock: Callable[[], datetime] = utcnow) -> None:
        self._sf = session_factory
        self._clock = clock

    def ensure_baseline(self) -> None:
        """Idempotent. Migrated databases already carry the seed; create_all (dev/test) databases get it here."""
        with self._sf() as s:
            if s.scalar(select(func.count()).select_from(LegalDocument)):
                return
            now = self._clock()
            for code, (title, ref) in P.LEGAL_DOCUMENTS.items():
                doc = LegalDocument(code=code, title=title, created_at=now)
                s.add(doc)
                s.flush()
                s.add(V(document_id=doc.id, version=P.BASELINE_VERSION, state="published", is_baseline=True, content_ref=ref,
                        published_at=now, created_at=now, updated_at=now))
            s.commit()

    # ---------------------------------------------------------------- validation
    @staticmethod
    def validate_fields(*, version: str | None, content_ref: str, content_hash: str | None) -> None:
        if version is not None and not _LABEL.match(version or ""):
            raise LegalValidationError("The version label may use letters, digits, '.', '_' and '-' (up to 32 characters).")
        ref = (content_ref or "").strip()
        if not ref or len(ref) > 300 or not (ref.startswith("/") or ref.startswith("https://")) or re.search(r"[\s<>\"']", ref):
            raise LegalValidationError("The content reference must be a page path starting with '/' or an https address.")
        if content_hash is not None and not _HASH.match(content_hash):
            raise LegalValidationError("The content hash must be a lowercase SHA-256 hex digest (64 characters).")

    # ---------------------------------------------------------------- views
    @staticmethod
    def _v(v: V) -> dict:
        return {"id": v.id, "version": v.version, "state": v.state, "is_baseline": bool(v.is_baseline), "content_ref": v.content_ref,
                "content_hash": v.content_hash, "effective_at": _iso(v.effective_at), "published_at": _iso(v.published_at),
                "created_at": _iso(v.created_at)}

    def admin_overview(self) -> dict:
        self.ensure_baseline()
        with self._sf() as s:
            total_users = s.scalar(select(func.count()).select_from(User).where(User.status == ACCOUNT_STATUS_ACTIVE)) or 0
            out = []
            for doc in s.scalars(select(LegalDocument).order_by(LegalDocument.id)).all():
                versions = s.scalars(select(V).where(V.document_id == doc.id).order_by(V.id.desc())).all()
                current = next((v for v in versions if v.state == "published"), None)
                accepted = 0
                if current is not None:
                    accepted = s.scalar(select(func.count()).select_from(LegalAcceptance).where(LegalAcceptance.version_id == current.id)) or 0
                out.append({
                    "code": doc.code, "title": doc.title, "current": self._v(current) if current else None,
                    "versions": [{**self._v(v), "acceptances": s.scalar(select(func.count()).select_from(LegalAcceptance)
                                                                         .where(LegalAcceptance.version_id == v.id)) or 0} for v in versions],
                    "current_accepted": accepted, "current_not_recorded": max(0, total_users - accepted)})
            return {"documents": out, "active_accounts": total_users,
                    "note": "Counts reflect RECORDED acceptances only. Accounts that predate acceptance recording have none. This is not a compliance measure."}

    def for_user(self, user_id: int) -> dict:
        self.ensure_baseline()
        with self._sf() as s:
            items = []
            for doc in s.scalars(select(LegalDocument).order_by(LegalDocument.id)).all():
                cur = s.scalar(select(V).where(V.document_id == doc.id, V.state == "published"))
                acc = None
                latest = s.execute(select(LegalAcceptance, V.version).join(V, V.id == LegalAcceptance.version_id)
                                   .where(LegalAcceptance.user_id == user_id, V.document_id == doc.id)
                                   .order_by(LegalAcceptance.accepted_at.desc(), LegalAcceptance.id.desc())).first()
                if latest:
                    acc = {"version": latest[1], "accepted_at": _iso(latest[0].accepted_at), "source": latest[0].source,
                           "is_current": cur is not None and latest[0].version_id == cur.id}
                items.append({"code": doc.code, "title": doc.title, "path": P.LEGAL_DOCUMENTS[doc.code][1],
                              "current_version": cur.version if cur else None,
                              "effective_at": _iso(cur.effective_at) if cur else None,
                              "version_is_baseline": bool(cur.is_baseline) if cur else None,
                              "accepted_current": bool(acc and acc["is_current"]), "last_acceptance": acc})
            return {"documents": items}

    def export_for_user(self, user_id: int) -> list[dict]:
        with self._sf() as s:
            rows = s.execute(select(LegalAcceptance, V.version, LegalDocument.code).join(V, V.id == LegalAcceptance.version_id)
                             .join(LegalDocument, LegalDocument.id == V.document_id).where(LegalAcceptance.user_id == user_id)
                             .order_by(LegalAcceptance.id)).all()
            return [{"document": code, "version": ver, "accepted_at": _iso(a.accepted_at), "source": a.source} for a, ver, code in rows]

    # ---------------------------------------------------------------- admin mutations
    def _doc(self, s, code: str) -> LegalDocument:
        doc = s.scalar(select(LegalDocument).where(LegalDocument.code == code))
        if doc is None:
            raise LegalNotFound(code)
        return doc

    def create_draft(self, code: str, *, version: str, content_ref: str, content_hash: str | None, effective_at: datetime | None,
                     actor_user_id: int, audit: dict | None = None) -> dict:
        self.ensure_baseline()
        self.validate_fields(version=version, content_ref=content_ref, content_hash=content_hash)
        now = self._clock()
        with self._sf() as s:
            doc = self._doc(s, code)
            v = V(document_id=doc.id, version=version, state="draft", is_baseline=False, content_ref=content_ref.strip(),
                  content_hash=content_hash, effective_at=effective_at, created_by_user_id=actor_user_id, created_at=now, updated_at=now)
            s.add(v)
            try:
                s.flush()
            except IntegrityError:
                s.rollback()
                raise LegalConflict("That version label already exists for this document.")
            _stage(s, {**audit, "target_id": str(v.id)} if audit else None, document=code, version=version, new_state="draft")
            s.commit()
            return self._v(v)

    def update_draft(self, version_id: int, *, content_ref: str, content_hash: str | None, effective_at: datetime | None,
                     audit: dict | None = None) -> dict:
        self.validate_fields(version=None, content_ref=content_ref, content_hash=content_hash)
        with self._sf() as s:
            v = s.get(V, version_id)
            if v is None:
                raise LegalNotFound(str(version_id))
            if v.state != "draft":
                raise LegalConflict("A published or retired version is immutable; create a new version instead.")
            v.content_ref, v.content_hash, v.effective_at, v.updated_at = content_ref.strip(), content_hash, effective_at, self._clock()
            _stage(s, {**audit, "target_id": str(v.id)} if audit else None, version=v.version)
            s.commit()
            return self._v(v)

    def publish(self, version_id: int, *, actor_user_id: int, audit: dict | None = None) -> dict:
        now = self._clock()
        with self._sf() as s:
            v = s.get(V, version_id)
            if v is None:
                raise LegalNotFound(str(version_id))
            if v.state != "draft":
                raise LegalConflict("Only a draft can be published.")
            if not v.content_hash or not v.content_ref:
                raise LegalConflict("A content reference and a content hash are required to publish.")
            if v.effective_at is None:
                raise LegalConflict("An effective date is required to publish.")
            prior = s.scalar(select(V).where(V.document_id == v.document_id, V.state == "published"))
            if prior is not None:
                prior.state, prior.updated_at = "retired", now
                s.flush()                                  # retire first so the one-published index never conflicts
            v.state, v.published_at, v.published_by_user_id, v.updated_at = "published", now, actor_user_id, now
            _stage(s, {**audit, "target_id": str(v.id)} if audit else None, version=v.version, new_state="published",
                   replaced_version=prior.version if prior else None)
            try:
                s.commit()
            except IntegrityError:
                s.rollback()
                raise LegalConflict("Another version was published meanwhile; reload and retry.")
            return self._v(v)

    # ---------------------------------------------------------------- candidate acceptance
    def accept(self, user_id: int, code: str, *, source: str = "settings") -> dict:
        """Record acceptance of the CURRENT published version. Idempotent: a repeat returns the existing record."""
        if source not in P.ACCEPTANCE_SOURCES:
            raise LegalValidationError("Unknown acceptance source.")
        self.ensure_baseline()
        now = self._clock()
        with self._sf() as s:
            doc = self._doc(s, code)
            cur = s.scalar(select(V).where(V.document_id == doc.id, V.state == "published"))
            if cur is None:
                raise LegalNotFound(code)
            existing = s.scalar(select(LegalAcceptance).where(LegalAcceptance.user_id == user_id, LegalAcceptance.version_id == cur.id))
            if existing is None:
                s.add(LegalAcceptance(user_id=user_id, version_id=cur.id, accepted_at=now, source=source))
                AccountRepository._stage_audit(s, {"event_type": "legal.acceptance_recorded", "actor_user_id": user_id,
                                                   "target_type": "legal_document_version", "target_id": str(cur.id), "result": "success",
                                                   "request_id": None, "context": {"document": code, "version": cur.version, "source": source}})
                try:
                    s.commit()
                except IntegrityError:
                    s.rollback()          # a concurrent identical acceptance won the race: the result is the same
            return self.for_user(user_id)

    def delete_user_acceptances(self, s: Any, user_id: int) -> int:
        n = 0
        for a in s.scalars(select(LegalAcceptance).where(LegalAcceptance.user_id == user_id)).all():
            s.delete(a)
            n += 1
        return n
