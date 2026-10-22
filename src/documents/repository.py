"""Owner-scoped data access for documents, claims and stories (Capstone P4).

Every read/write is scoped by ``user_id``; a foreign id resolves to ``None`` / a no-op,
never another user's data (cross-user access is impossible). Returns plain dicts (safe
projections), never live ORM objects. File bytes live in the DocumentStore, not here.
"""

from __future__ import annotations

import re

from sqlalchemy import delete, select
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
    STORY_USER_CORRECTED,
    Answer,
    Interview,
    InterviewSession,
    PreparationPack,
    Question,
    StoryAnswerLink,
    StoryEvidence,
    StoryUse,
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
        failure_kind: str | None = None,
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
            # Cleared on success (failure_kind=None), set to a bounded tag on failure.
            v.failure_kind = failure_kind
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
                        "failure_kind": v.failure_kind,
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
            out: list[dict] = []
            for d in docs:
                # Current version carries the failure taxonomy + extraction origin the
                # inventory row needs, so the UI can render a localized state without a
                # second round-trip. Owner scoping is already guaranteed by the doc query.
                cur = s.scalar(
                    select(DocumentVersion).where(
                        DocumentVersion.document_id == d.id,
                        DocumentVersion.version == d.current_version,
                    )
                )
                out.append({
                    "id": d.id, "category": d.category, "title": d.title, "status": d.status,
                    "current_version": d.current_version,
                    "updated_at": d.updated_at.isoformat() if d.updated_at else None,
                    "failure_kind": cur.failure_kind if cur else None,
                    "extraction_origin": cur.extraction_origin if cur else None,
                })
            return out

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

    def clear_version_claims(self, *, user_id: int, document_id: int, version_id: int) -> int:
        """Delete the claims a specific version produced (owner-scoped), so a reprocess does
        not duplicate extraction. Only touches the caller's own document's claims."""
        with self._sf() as s:
            doc = s.get(CandidateDocument, document_id)
            if doc is None or doc.user_id != user_id:
                return 0
            rows = s.scalars(
                select(DocumentClaim).where(
                    DocumentClaim.user_id == user_id,
                    DocumentClaim.document_id == document_id,
                    DocumentClaim.version_id == version_id,
                )
            ).all()
            for c in rows:
                s.delete(c)
            s.commit()
            return len(rows)

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


# Story text copied into a session's ``candidate_background`` is wrapped in these markers so a deleted story's block can be found and removed again.
STORY_BLOCK_OPEN = "[[STORY {id} BEGIN]]"
STORY_BLOCK_CLOSE = "[[STORY {id} END]]"
VERIFICATION_LABELS = ("evidence_verified", "source_revoked", "answer_linked", "self_confirmed", "unverified")
_TEXT_FIELDS = ("situation", "task", "action", "result")


def strip_story_blocks(text: str, story_id: int) -> str:
    """Remove one story's marked block from a composed background (idempotent; unrelated text is untouched)."""
    pattern = re.escape(STORY_BLOCK_OPEN.format(id=story_id)) + r".*?" + re.escape(STORY_BLOCK_CLOSE.format(id=story_id))
    return re.sub(r"\n{3,}", "\n\n", re.sub(pattern, "", text or "", flags=re.S)).strip()


def quality_prompts(st: dict) -> list[str]:
    """Deterministic STAR quality prompts (codes only; the UI localises them). They ask the candidate to add what is MISSING from their own account and never
    suggest numbers or outcomes: nothing here invents content."""
    out: list[str] = []
    for f in _TEXT_FIELDS:
        if not (st.get(f) or "").strip():
            out.append(f"{f}_missing")
    action = (st.get("action") or "").strip()
    if action and len(action) < 40:
        out.append("action_thin")
    result = (st.get("result") or "").strip()
    if result and not re.search(r"\d", result):
        out.append("result_no_figure")
    if not st.get("competencies"):
        out.append("no_tags")
    return out


class StoryRepository:
    def __init__(self, session_factory: sessionmaker) -> None:
        self._sf = session_factory

    # -- writes ---------------------------------------------------------------

    def create(self, *, user_id: int, title: str, status: str, fields: dict, claim_ids: list[int], opportunity_id: int | None = None) -> int:
        with self._sf() as s:
            story = CandidateStory(user_id=user_id, title=title, status=status, opportunity_id=opportunity_id, **fields)
            s.add(story)
            s.flush()
            # Only link claims the user owns (defence in depth).
            for cid in claim_ids:
                c = s.get(DocumentClaim, cid)
                if c is not None and c.user_id == user_id:
                    s.add(StoryEvidence(story_id=story.id, claim_id=cid))
            s.flush()
            story.evidence_state = self._evidence_state(s, story)
            s.commit()
            return story.id

    def update(self, *, user_id: int, story_id: int, fields: dict, mark_corrected: bool) -> dict | None:
        with self._sf() as s:
            st = s.get(CandidateStory, story_id)
            if st is None or st.user_id != user_id:
                return None
            text_changed = any(k in fields and fields[k] != getattr(st, k) for k in _TEXT_FIELDS)
            for k, v in fields.items():
                setattr(st, k, v)
            if mark_corrected and st.status in (STORY_SOURCE_BACKED, STORY_MODEL_SUGGESTED) and text_changed:
                # Editing source text or a model draft makes it the candidate's OWN corrected account (never "verbatim source").
                st.status = STORY_USER_CORRECTED
            if text_changed:
                st.confirmed_at = None            # a confirmation applies to the text that was confirmed
            st.evidence_state = self._evidence_state(s, st)
            st.updated_at = utcnow()
            s.commit()
            return self._dict(s, st)

    def set_archived(self, *, user_id: int, story_id: int, archived: bool) -> dict | None:
        with self._sf() as s:
            st = s.get(CandidateStory, story_id)
            if st is None or st.user_id != user_id:
                return None
            st.archived_at = utcnow() if archived else None
            st.updated_at = utcnow()
            s.commit()
            return self._dict(s, st)

    def set_confirmed(self, *, user_id: int, story_id: int, confirmed: bool) -> dict | None:
        with self._sf() as s:
            st = s.get(CandidateStory, story_id)
            if st is None or st.user_id != user_id:
                return None
            st.confirmed_at = utcnow() if confirmed else None
            st.updated_at = utcnow()
            s.commit()
            return self._dict(s, st)

    def attach_claim(self, *, user_id: int, story_id: int, claim_id: int) -> dict | None:
        """Link an OWN, not-rejected claim. None = story or claim not owned/missing (indistinguishable)."""
        with self._sf() as s:
            st = s.get(CandidateStory, story_id)
            c = s.get(DocumentClaim, claim_id)
            if st is None or st.user_id != user_id or c is None or c.user_id != user_id or c.review_state == CLAIM_REJECTED:
                return None
            if s.scalar(select(StoryEvidence).where(StoryEvidence.story_id == story_id, StoryEvidence.claim_id == claim_id)) is None:
                s.add(StoryEvidence(story_id=story_id, claim_id=claim_id))
                s.flush()
            st.evidence_state = self._evidence_state(s, st)
            st.updated_at = utcnow()
            s.commit()
            return self._dict(s, st)

    def detach_claim(self, *, user_id: int, story_id: int, claim_id: int) -> dict | None:
        with self._sf() as s:
            st = s.get(CandidateStory, story_id)
            if st is None or st.user_id != user_id:
                return None
            s.execute(delete(StoryEvidence).where(StoryEvidence.story_id == story_id, StoryEvidence.claim_id == claim_id))
            s.flush()
            st.evidence_state = self._evidence_state(s, st)
            st.updated_at = utcnow()
            s.commit()
            return self._dict(s, st)

    def _owned_answer(self, s, user_id: int, answer_id: int) -> Answer | None:
        a = s.get(Answer, answer_id)
        if a is None:
            return None
        q = s.get(Question, a.question_id)
        iv = s.get(Interview, q.interview_id) if q is not None else None
        return a if iv is not None and iv.user_id == user_id else None

    def attach_answer(self, *, user_id: int, story_id: int, answer_id: int) -> dict | None:
        """Link one of the caller's OWN practice answers (a reference only). None = not owned/missing."""
        with self._sf() as s:
            st = s.get(CandidateStory, story_id)
            if st is None or st.user_id != user_id or self._owned_answer(s, user_id, answer_id) is None:
                return None
            if s.scalar(select(StoryAnswerLink).where(StoryAnswerLink.story_id == story_id, StoryAnswerLink.answer_id == answer_id)) is None:
                s.add(StoryAnswerLink(story_id=story_id, answer_id=answer_id))
            st.updated_at = utcnow()
            s.commit()
            return self._dict(s, st)

    def detach_answer(self, *, user_id: int, story_id: int, answer_id: int) -> dict | None:
        with self._sf() as s:
            st = s.get(CandidateStory, story_id)
            if st is None or st.user_id != user_id:
                return None
            s.execute(delete(StoryAnswerLink).where(StoryAnswerLink.story_id == story_id, StoryAnswerLink.answer_id == answer_id))
            st.updated_at = utcnow()
            s.commit()
            return self._dict(s, st)

    def record_uses(self, *, user_id: int, story_ids: list[int], session_id: str | None) -> None:
        """Record that these stories were used in a session. Only the caller's OWN stories are recorded (a forged id is ignored) and a repeat is a no-op."""
        with self._sf() as s:
            for sid in story_ids:
                st = s.get(CandidateStory, sid)
                if st is None or st.user_id != user_id:
                    continue
                if s.scalar(select(StoryUse).where(StoryUse.story_id == sid, StoryUse.session_id == session_id, StoryUse.user_id == user_id)) is None:
                    s.add(StoryUse(user_id=user_id, story_id=sid, session_id=session_id))
            s.commit()

    def unlink_opportunity(self, *, user_id: int, opportunity_id: int) -> int:
        """Clear the Opportunity link of the owner's stories (SQLite has no SET NULL on the ALTER-added column)."""
        with self._sf() as s:
            rows = s.scalars(select(CandidateStory).where(CandidateStory.user_id == user_id, CandidateStory.opportunity_id == opportunity_id)).all()
            for st in rows:
                st.opportunity_id = None
            s.commit()
            return len(rows)

    def delete(self, *, user_id: int, story_id: int) -> bool:
        """Delete one owned story AND everything derived from it that Ask4Mo copied: evidence and answer links, use records, the story's text inside
        session configuration (marked blocks) and Preparation Pack items that cite it. Share grants are revoked by the caller (route) in the same request."""
        with self._sf() as s:
            st = s.get(CandidateStory, story_id)
            if st is None or st.user_id != user_id:
                return False
            session_ids = [r for r in s.scalars(select(StoryUse.session_id).where(StoryUse.story_id == story_id, StoryUse.user_id == user_id)).all() if r]
            self._strip_from_sessions(s, user_id, story_id, session_ids)
            self._strip_from_packs(s, user_id, story_id)
            s.execute(delete(StoryUse).where(StoryUse.story_id == story_id))
            s.execute(delete(StoryAnswerLink).where(StoryAnswerLink.story_id == story_id))
            s.execute(delete(StoryEvidence).where(StoryEvidence.story_id == story_id))
            s.delete(st)
            s.commit()
            return True

    @staticmethod
    def _strip_from_sessions(s, user_id: int, story_id: int, session_ids: list[str]) -> None:
        for sid in set(session_ids):
            sess = s.get(InterviewSession, sid)
            if sess is not None and sess.user_id == user_id and isinstance(sess.state_payload, dict):
                payload = dict(sess.state_payload)
                cfg = payload.get("config")
                if isinstance(cfg, dict) and cfg.get("candidate_background"):
                    payload["config"] = {**cfg, "candidate_background": strip_story_blocks(cfg["candidate_background"], story_id)}
                    sess.state_payload = payload
            for iv in s.scalars(select(Interview).where(Interview.user_id == user_id, Interview.source_session_id == sid)).all():
                conf = iv.configuration
                if isinstance(conf, dict) and conf.get("candidate_background"):
                    iv.configuration = {**conf, "candidate_background": strip_story_blocks(conf["candidate_background"], story_id)}

    @staticmethod
    def _strip_from_packs(s, user_id: int, story_id: int) -> None:
        ref = f"S{story_id}"

        def clean(node):
            if isinstance(node, list):
                kept = []
                for it in node:
                    if isinstance(it, dict) and ref in (it.get("ref_ids") or []):
                        continue                     # an item that cites the deleted story (its text may carry the story) is removed whole
                    kept.append(clean(it))
                return kept
            if isinstance(node, dict):
                return {k: clean(v) for k, v in node.items()}
            return node

        for pack in s.scalars(select(PreparationPack).where(PreparationPack.user_id == user_id)).all():
            if pack.content and f"'{ref}'" in repr(pack.content):
                pack.content = clean(pack.content)

    # -- derivation -------------------------------------------------------------

    def _live_claim_links(self, s, st: CandidateStory) -> tuple[list[StoryEvidence], int]:
        links = s.scalars(select(StoryEvidence).where(StoryEvidence.story_id == st.id)).all()
        live = 0
        for link in links:
            claim = s.get(DocumentClaim, link.claim_id)
            if claim is not None and claim.user_id == st.user_id and claim.review_state != CLAIM_REJECTED:
                live += 1
        return list(links), live

    def _evidence_state(self, s, st: CandidateStory) -> str:
        """DOCUMENT evidence only. verified = at least one linked claim still exists, is the owner's and is not rejected; a story that
        had document sources (source-backed or corrected from one, or with links whose claims are gone) and has none left is source_revoked."""
        links, live = self._live_claim_links(s, st)
        if live:
            return STORY_EVIDENCE_VERIFIED
        if links or st.status in (STORY_SOURCE_BACKED, STORY_USER_CORRECTED):
            return STORY_EVIDENCE_REVOKED
        return STORY_EVIDENCE_NONE

    def _live_answer_ids(self, s, st: CandidateStory) -> list[int]:
        out: list[int] = []
        for link in s.scalars(select(StoryAnswerLink).where(StoryAnswerLink.story_id == st.id)).all():
            if self._owned_answer(s, st.user_id, link.answer_id) is not None:
                out.append(link.answer_id)
        return out

    def rederive_all_for_user(self, user_id: int) -> int:
        """Re-store the derived evidence_state of every story of a user (reads are derived anyway; this keeps the stored column truthful)."""
        changed = 0
        with self._sf() as s:
            for story in s.scalars(select(CandidateStory).where(CandidateStory.user_id == user_id)).all():
                new_state = self._evidence_state(s, story)
                if new_state != story.evidence_state:
                    story.evidence_state = new_state
                    changed += 1
            s.commit()
            return changed

    # -- reads ------------------------------------------------------------------

    def get(self, *, user_id: int, story_id: int) -> dict | None:
        with self._sf() as s:
            st = s.get(CandidateStory, story_id)
            if st is None or st.user_id != user_id:
                return None
            return self._dict(s, st)

    def list(self, user_id: int, *, archived: str = "active") -> list[dict]:
        """``archived``: "active" (default; archived stories never appear in Pack/agent/Practice reads), "archived" or "all"."""
        with self._sf() as s:
            q = select(CandidateStory).where(CandidateStory.user_id == user_id)
            if archived == "active":
                q = q.where(CandidateStory.archived_at.is_(None))
            elif archived == "archived":
                q = q.where(CandidateStory.archived_at.is_not(None))
            rows = s.scalars(q.order_by(CandidateStory.updated_at.desc(), CandidateStory.id.desc())).all()
            return [self._dict(s, st) for st in rows]

    def evidence_stories(self, user_id: int) -> list[dict]:
        """A user's stories that are SAFE to use as evidence, owner-scoped (Capstone P5; 04A narrows it).

        Excludes archived stories, source-backed stories whose source is gone, and model suggestions the candidate has not confirmed
        or edited (a confirmation or an edit is their approval). Safe dict projections only."""
        return [d for d in self.list(user_id) if self.is_usable(d)]

    @staticmethod
    def is_usable(d: dict) -> bool:
        if d.get("archived_at"):
            return False
        if d["status"] == STORY_MODEL_SUGGESTED and not d.get("confirmed_at"):
            return False
        if d["status"] == STORY_SOURCE_BACKED and d["evidence_state"] != STORY_EVIDENCE_VERIFIED:
            return False
        return True

    def usable_by_ids(self, user_id: int, story_ids: list[int]) -> list[dict] | None:
        """The owner's usable stories for exactly these ids, in the given order; None if ANY id is foreign, missing, archived or unusable
        (one indistinguishable answer, so the caller cannot probe other accounts)."""
        by_id = {d["id"]: d for d in self.evidence_stories(user_id)}
        if any(sid not in by_id for sid in story_ids):
            return None
        return [by_id[sid] for sid in story_ids]

    def _dict(self, s, st: CandidateStory) -> dict:
        links = s.scalars(select(StoryEvidence).where(StoryEvidence.story_id == st.id)).all()
        evidence_state = self._evidence_state(s, st)
        answers = self._live_answer_ids(s, st)
        if evidence_state == STORY_EVIDENCE_VERIFIED:
            verification = "evidence_verified"
        elif evidence_state == STORY_EVIDENCE_REVOKED:
            verification = "source_revoked"
        elif answers:
            verification = "answer_linked"
        elif st.confirmed_at:
            verification = "self_confirmed"
        else:
            verification = "unverified"
        uses = s.scalars(select(StoryUse.created_at).where(StoryUse.story_id == st.id, StoryUse.user_id == st.user_id)).all()
        d = {
            "id": st.id, "title": st.title, "situation": st.situation, "task": st.task,
            "action": st.action, "result": st.result, "competencies": st.competencies or [],
            "status": st.status, "evidence_state": evidence_state, "verification": verification,
            "evidence_claim_ids": [link.claim_id for link in links],
            "evidence_answer_ids": answers,
            "opportunity_id": st.opportunity_id,
            "archived_at": st.archived_at.isoformat() if st.archived_at else None,
            "confirmed_at": st.confirmed_at.isoformat() if st.confirmed_at else None,
            "use_count": len(uses),
            "last_used_at": max(uses).isoformat() if uses else None,
            "updated_at": st.updated_at.isoformat() if st.updated_at else None,
        }
        d["quality_prompts"] = quality_prompts(d)
        return d
