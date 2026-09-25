"""Owner-scoped data access for documents, claims and stories (Capstone P4).

Every read/write is scoped by ``user_id``; a foreign id resolves to ``None`` / a no-op,
never another user's data (cross-user access is impossible). Returns plain dicts (safe
projections), never live ORM objects. File bytes live in the DocumentStore, not here.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from src.persistence import (
    CLAIM_ACCEPTED,
    CLAIM_EDITED,
    CLAIM_REJECTED,
    STORY_EVIDENCE_NONE,
    STORY_EVIDENCE_REVOKED,
    STORY_EVIDENCE_VERIFIED,
    STORY_MODEL_SUGGESTED,
    STORY_SOURCE_BACKED,
    CandidateDocument,
    CandidateStory,
    DocumentClaim,
    DocumentVersion,
    StoryEvidence,
    utcnow,
)

__all__ = ["DocumentRepository", "StoryRepository"]


def _claim_dict(c: DocumentClaim) -> dict:
    return {
        "id": c.id,
        "document_id": c.document_id,
        "version_id": c.version_id,
        "claim_type": c.claim_type,
        "text": c.text,
        "edited_text": c.edited_text,
        "display_text": c.edited_text if c.edited_text is not None else c.text,
        "source_page": c.source_page,
        "source_section": c.source_section,
        "review_state": c.review_state,
    }


class DocumentRepository:
    def __init__(self, session_factory: sessionmaker) -> None:
        self._sf = session_factory

    # -- documents / versions -------------------------------------------------

    def create_document(self, *, user_id: int, category: str, title: str) -> int:
        with self._sf() as s:
            doc = CandidateDocument(user_id=user_id, category=category, title=title, current_version=1)
            s.add(doc)
            s.commit()
            return doc.id

    def add_version(
        self, *, user_id: int, document_id: int, version: int, original_filename: str,
        storage_key: str, mime_type: str, size_bytes: int, language_hint: str | None,
    ) -> int | None:
        with self._sf() as s:
            doc = s.get(CandidateDocument, document_id)
            if doc is None or doc.user_id != user_id:
                return None
            v = DocumentVersion(
                document_id=document_id, version=version, original_filename=original_filename,
                storage_key=storage_key, mime_type=mime_type, size_bytes=size_bytes,
                language_hint=language_hint,
            )
            s.add(v)
            doc.current_version = version
            s.commit()
            return v.id

    def set_version_result(
        self, *, version_id: int, status: str, extraction_origin: str | None = None,
        page_count: int | None = None, failure_reason: str | None = None,
    ) -> None:
        with self._sf() as s:
            v = s.get(DocumentVersion, version_id)
            if v is None:
                return
            v.status = status
            if extraction_origin is not None:
                v.extraction_origin = extraction_origin
            if page_count is not None:
                v.page_count = page_count
            v.failure_reason = failure_reason
            s.commit()

    def set_document_status(self, *, user_id: int, document_id: int, status: str) -> bool:
        with self._sf() as s:
            doc = s.get(CandidateDocument, document_id)
            if doc is None or doc.user_id != user_id:
                return False
            doc.status = status
            s.commit()
            return True

    def current_version_id(self, *, user_id: int, document_id: int) -> int | None:
        with self._sf() as s:
            doc = s.get(CandidateDocument, document_id)
            if doc is None or doc.user_id != user_id:
                return None
            v = s.scalar(
                select(DocumentVersion).where(
                    DocumentVersion.document_id == document_id,
                    DocumentVersion.version == doc.current_version,
                )
            )
            return v.id if v else None

    def get_download(self, *, user_id: int, document_id: int, version: int | None = None) -> dict | None:
        """Return {storage_key, mime_type, filename} for an owned document version."""
        with self._sf() as s:
            doc = s.get(CandidateDocument, document_id)
            if doc is None or doc.user_id != user_id:
                return None
            ver = version if version is not None else doc.current_version
            v = s.scalar(
                select(DocumentVersion).where(
                    DocumentVersion.document_id == document_id, DocumentVersion.version == ver
                )
            )
            if v is None:
                return None
            return {"storage_key": v.storage_key, "mime_type": v.mime_type, "filename": v.original_filename}

    def get_document(self, *, user_id: int, document_id: int) -> dict | None:
        with self._sf() as s:
            doc = s.get(CandidateDocument, document_id)
            if doc is None or doc.user_id != user_id:
                return None
            versions = s.scalars(
                select(DocumentVersion).where(DocumentVersion.document_id == document_id)
                .order_by(DocumentVersion.version)
            ).all()
            claims = s.scalars(
                select(DocumentClaim).where(DocumentClaim.document_id == document_id)
                .order_by(DocumentClaim.id)
            ).all()
            return {
                "id": doc.id,
                "category": doc.category,
                "title": doc.title,
                "status": doc.status,
                "current_version": doc.current_version,
                "created_at": doc.created_at.isoformat() if doc.created_at else None,
                "versions": [
                    {
                        "version": v.version, "original_filename": v.original_filename,
                        "mime_type": v.mime_type, "size_bytes": v.size_bytes,
                        "page_count": v.page_count, "extraction_origin": v.extraction_origin,
                        "status": v.status, "failure_reason": v.failure_reason,
                        "language_hint": v.language_hint,
                    }
                    for v in versions
                ],
                "claims": [_claim_dict(c) for c in claims],
            }

    def list_documents(self, user_id: int) -> list[dict]:
        with self._sf() as s:
            docs = s.scalars(
                select(CandidateDocument).where(CandidateDocument.user_id == user_id)
                .order_by(CandidateDocument.updated_at.desc())
            ).all()
            return [
                {"id": d.id, "category": d.category, "title": d.title, "status": d.status,
                 "current_version": d.current_version,
                 "updated_at": d.updated_at.isoformat() if d.updated_at else None}
                for d in docs
            ]

    def approved_claims(self, user_id: int) -> list[dict]:
        """A user's APPROVED claims only (review_state accepted or edited), owner-scoped.

        Excludes pending (unreviewed) and rejected claims by design (Capstone P5 §8/§9):
        a specialist only ever sees candidate-approved evidence. Returns safe dict
        projections (``display_text`` + provenance), never raw ORM rows or file bytes.
        """
        with self._sf() as s:
            rows = s.scalars(
                select(DocumentClaim).where(
                    DocumentClaim.user_id == user_id,
                    DocumentClaim.review_state.in_((CLAIM_ACCEPTED, CLAIM_EDITED)),
                ).order_by(DocumentClaim.id)
            ).all()
            return [_claim_dict(c) for c in rows]

    def add_claims(self, *, user_id: int, document_id: int, version_id: int, claims: list) -> int:
        with self._sf() as s:
            doc = s.get(CandidateDocument, document_id)
            if doc is None or doc.user_id != user_id:
                return 0
            for c in claims:
                s.add(DocumentClaim(
                    user_id=user_id, document_id=document_id, version_id=version_id,
                    claim_type=c.claim_type, text=c.text, source_page=c.page, source_section=c.section,
                ))
            s.commit()
            return len(claims)

    def update_claim(self, *, user_id: int, claim_id: int, review_state: str, edited_text: str | None = None) -> dict | None:
        with self._sf() as s:
            c = s.get(DocumentClaim, claim_id)
            if c is None or c.user_id != user_id:
                return None
            c.review_state = review_state
            if review_state == CLAIM_EDITED and edited_text is not None:
                c.edited_text = edited_text
            if review_state in (CLAIM_ACCEPTED, CLAIM_REJECTED):
                # Accept/reject does not alter the corrected text (kept if previously edited).
                pass
            c.updated_at = utcnow()
            s.commit()
            return _claim_dict(c)

    def delete_document(self, *, user_id: int, document_id: int) -> list[str] | None:
        """Delete an owned document + all derived claims/versions (cascade). Returns the
        storage keys to purge from the file store, or None if not owned."""
        with self._sf() as s:
            doc = s.get(CandidateDocument, document_id)
            if doc is None or doc.user_id != user_id:
                return None
            keys = [
                v.storage_key for v in s.scalars(
                    select(DocumentVersion).where(DocumentVersion.document_id == document_id)
                ).all()
            ]
            s.delete(doc)  # cascades versions + claims (+ story_evidence via claim FK)
            s.commit()
            return keys


class StoryRepository:
    def __init__(self, session_factory: sessionmaker) -> None:
        self._sf = session_factory

    def create(self, *, user_id: int, title: str, status: str, fields: dict, claim_ids: list[int]) -> int:
        with self._sf() as s:
            story = CandidateStory(user_id=user_id, title=title, status=status, **fields)
            s.add(story)
            s.flush()
            # Only link claims the user owns (defence in depth).
            for cid in claim_ids:
                c = s.get(DocumentClaim, cid)
                if c is not None and c.user_id == user_id:
                    s.add(StoryEvidence(story_id=story.id, claim_id=cid))
            s.flush()
            story.evidence_state = self._derive_state(s, story.id, status)
            s.commit()
            return story.id

    def _derive_state(self, s, story_id: int, status: str) -> str:
        links = s.scalars(select(StoryEvidence).where(StoryEvidence.story_id == story_id)).all()
        if status != STORY_SOURCE_BACKED:
            return STORY_EVIDENCE_NONE
        # Source-backed: verified only while at least one live supporting claim remains.
        live = 0
        for link in links:
            claim = s.get(DocumentClaim, link.claim_id)
            if claim is not None:
                live += 1
        return STORY_EVIDENCE_VERIFIED if live else STORY_EVIDENCE_REVOKED

    def rederive_all_for_user(self, user_id: int) -> int:
        """Re-derive evidence_state for a user's source-backed stories (after a source
        deletion, a story with no live claims flips verified → source_revoked)."""
        changed = 0
        with self._sf() as s:
            stories = s.scalars(
                select(CandidateStory).where(
                    CandidateStory.user_id == user_id,
                    CandidateStory.status == STORY_SOURCE_BACKED,
                )
            ).all()
            for story in stories:
                new_state = self._derive_state(s, story.id, story.status)
                if new_state != story.evidence_state:
                    story.evidence_state = new_state
                    changed += 1
            s.commit()
            return changed

    def get(self, *, user_id: int, story_id: int) -> dict | None:
        with self._sf() as s:
            st = s.get(CandidateStory, story_id)
            if st is None or st.user_id != user_id:
                return None
            return self._dict(s, st)

    def list(self, user_id: int) -> list[dict]:
        with self._sf() as s:
            rows = s.scalars(
                select(CandidateStory).where(CandidateStory.user_id == user_id)
                .order_by(CandidateStory.updated_at.desc())
            ).all()
            return [self._dict(s, st) for st in rows]

    def evidence_stories(self, user_id: int) -> list[dict]:
        """A user's stories that are SAFE to use as evidence, owner-scoped (Capstone P5).

        Includes source-backed stories only while still verified, plus stories the
        candidate authored/corrected themselves. Excludes ``source_revoked`` stories
        (their supporting source was deleted) and ``model_suggested`` drafts (not yet
        candidate-approved). Safe dict projections only.
        """
        with self._sf() as s:
            rows = s.scalars(
                select(CandidateStory).where(CandidateStory.user_id == user_id)
                .order_by(CandidateStory.updated_at.desc())
            ).all()
            out: list[dict] = []
            for st in rows:
                if st.status == STORY_MODEL_SUGGESTED:
                    continue  # not candidate-approved
                if st.status == STORY_SOURCE_BACKED and st.evidence_state != STORY_EVIDENCE_VERIFIED:
                    continue  # source revoked → never presented as verified evidence
                out.append(self._dict(s, st))
            return out

    def update(self, *, user_id: int, story_id: int, fields: dict, mark_corrected: bool) -> dict | None:
        with self._sf() as s:
            st = s.get(CandidateStory, story_id)
            if st is None or st.user_id != user_id:
                return None
            for k, v in fields.items():
                setattr(st, k, v)
            if mark_corrected and st.status in (STORY_SOURCE_BACKED,):
                from src.persistence import STORY_USER_CORRECTED

                st.status = STORY_USER_CORRECTED
            st.updated_at = utcnow()
            s.commit()
            return self._dict(s, st)

    def delete(self, *, user_id: int, story_id: int) -> bool:
        with self._sf() as s:
            st = s.get(CandidateStory, story_id)
            if st is None or st.user_id != user_id:
                return False
            s.delete(st)
            s.commit()
            return True

    def _dict(self, s, st: CandidateStory) -> dict:
        links = s.scalars(select(StoryEvidence).where(StoryEvidence.story_id == st.id)).all()
        return {
            "id": st.id, "title": st.title, "situation": st.situation, "task": st.task,
            "action": st.action, "result": st.result, "competencies": st.competencies or [],
            "status": st.status, "evidence_state": st.evidence_state,
            "evidence_claim_ids": [link.claim_id for link in links],
            "updated_at": st.updated_at.isoformat() if st.updated_at else None,
        }
