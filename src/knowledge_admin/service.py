"""Governed knowledge control plane (P10B-W10.8).

Invariant: UNAPPROVED KNOWLEDGE NEVER ENTERS CANDIDATE RETRIEVAL. Parsed != approved, approved != indexed, indexed != active.
Nothing is embedded or written to any vector collection before a human approval; a version becomes retrievable only by the
explicit ``activate`` action, and the retriever additionally checks THIS control plane (not the vector store) for the active
set. Every state change is a guarded UPDATE (``WHERE state = <expected>``) so replays and races are safe, and every Admin
action stages its audit event in the same transaction.

Cross-store consistency: SQL (control plane) and the vector store cannot share a transaction. Sequence: index first, then flip
state in SQL, and retrieval trusts SQL. A failed or delayed vector deletion therefore never exposes retired content.
"""

from __future__ import annotations

import hashlib
import re
import uuid
from datetime import datetime
from typing import Any, Callable
from urllib.parse import urlparse

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from src.admin_repository import _stage
from src.documents.storage import new_storage_key
from src.documents.validation import _sniff, sanitise_filename
from src.knowledge_admin import policy as P
from src.persistence import KnowledgeIndexRecord, KnowledgeSource, KnowledgeSourceVersion as V, utcnow


class KnowledgeValidationError(Exception):
    """A safe, user-facing validation failure (never echoes the submitted content)."""


class KnowledgeNotFound(Exception):
    pass


class KnowledgeConflict(Exception):
    pass


class KnowledgeBlocked(Exception):
    def __init__(self, blockers: list[str]) -> None:
        super().__init__("; ".join(blockers))
        self.blockers = blockers


class KnowledgeDuplicate(Exception):
    def __init__(self, existing_public_id: str) -> None:
        super().__init__("duplicate checksum")
        self.existing_public_id = existing_public_id


_URL_BAD = re.compile(r"[\s<>\"']")


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


class KnowledgeAdminService:
    def __init__(self, session_factory: sessionmaker, *, doc_store: Any, jobs: Any,
                 clock: Callable[[], datetime] = utcnow) -> None:
        self._sf = session_factory
        self._store = doc_store
        self._jobs = jobs
        self._clock = clock

    # ------------------------------------------------------------------ validation
    @staticmethod
    def validate_metadata(*, title: str | None = None, language: str, authority_level: int, publisher: str,
                          source_url: str | None, provenance_note: str, licence_class: str) -> dict:
        def bounded(value: str, limit: int, field: str) -> str:
            value = (value or "").strip()
            if len(value) > limit or "\x00" in value:
                raise KnowledgeValidationError(f"{field} is too long or invalid.")
            return value

        out = {"publisher": bounded(publisher, P.MAX_PUBLISHER, "Publisher"),
               "provenance_note": bounded(provenance_note, P.MAX_PROVENANCE, "Provenance note")}
        if title is not None:
            out["title"] = bounded(title, P.MAX_TITLE, "Title")
            if not out["title"]:
                raise KnowledgeValidationError("A title is required.")
        if language not in P.KB_LANGUAGES:
            raise KnowledgeValidationError("Unsupported knowledge language.")   # Russian is NOT a KB language
        if authority_level not in P.AUTHORITY_LEVELS or isinstance(authority_level, bool):
            raise KnowledgeValidationError("Authority level must be 1, 2 or 3.")
        if licence_class not in P.LICENCE_CLASSES:
            raise KnowledgeValidationError("Unknown licence classification.")
        url = (source_url or "").strip() or None
        if url is not None:
            parsed = urlparse(url)
            if len(url) > P.MAX_URL or _URL_BAD.search(url) or parsed.scheme != "https" or not parsed.hostname \
                    or parsed.username or parsed.password:
                raise KnowledgeValidationError("The source URL must be a plain https address (it is a reference only and is never fetched).")
        out.update(language=language, authority_level=int(authority_level), licence_class=licence_class, source_url=url)
        return out

    @staticmethod
    def validate_upload(filename: str, data: bytes) -> tuple[str, str, str]:
        if not data:
            raise KnowledgeValidationError("The file is empty.")
        if len(data) > P.MAX_UPLOAD_BYTES:
            raise KnowledgeValidationError("The file is too large (max 5 MB).")
        name = sanitise_filename(filename)                 # display name only; never a path
        ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
        if ext not in P.ALLOWED_EXTENSIONS:
            raise KnowledgeValidationError("Unsupported file type. Use PDF, TXT or Markdown.")
        if not _sniff(data, "pdf" if ext == "pdf" else "txt"):
            raise KnowledgeValidationError("The file content does not match its type.")
        if ext != "pdf":
            try:
                data.decode("utf-8")
            except UnicodeDecodeError:
                raise KnowledgeValidationError("Text and Markdown files must be UTF-8.")
        return ext, P.ALLOWED_EXTENSIONS[ext], name

    # ------------------------------------------------------------------ creation
    def create_source(self, *, title: str, filename: str, data: bytes, actor_user_id: int | None,
                      audit: dict | None = None, **meta) -> dict:
        m = self.validate_metadata(title=title, **meta)
        return self._add_version(None, m, filename, data, actor_user_id, audit)

    def add_version(self, source_public_id: str, *, filename: str, data: bytes, actor_user_id: int | None,
                    audit: dict | None = None, **meta) -> dict:
        m = self.validate_metadata(**meta)
        return self._add_version(source_public_id, m, filename, data, actor_user_id, audit)

    def _add_version(self, source_public_id: str | None, m: dict, filename: str, data: bytes,
                     actor: int | None, audit: dict | None) -> dict:
        ext, media, safe_name = self.validate_upload(filename, data)
        checksum = hashlib.sha256(data).hexdigest()
        key, now, vpid = new_storage_key(), self._clock(), uuid.uuid4().hex
        with self._sf() as s:
            if source_public_id is None:
                src = KnowledgeSource(public_id=uuid.uuid4().hex, title=m["title"], created_by_user_id=actor,
                                      created_at=now, updated_at=now)
                s.add(src)
                s.flush()
                number = 1
            else:
                src = s.scalar(select(KnowledgeSource).where(KnowledgeSource.public_id == source_public_id))
                if src is None:
                    raise KnowledgeNotFound(source_public_id)
                dup = s.scalar(select(V.public_id).where(V.source_id == src.id, V.checksum_sha256 == checksum))
                if dup:
                    raise KnowledgeDuplicate(dup)     # same bytes, same source: never silently a new version
                number = (s.scalar(select(func.max(V.version)).where(V.source_id == src.id)) or 0) + 1
            self._store.save(key, data)
            ver = V(public_id=vpid, source_id=src.id, version=number, state="queued", language=m["language"],
                    authority_level=m["authority_level"], publisher=m["publisher"], source_url=m["source_url"],
                    provenance_note=m["provenance_note"], licence_class=m["licence_class"], original_filename=safe_name,
                    storage_key=key, media_type=media, byte_size=len(data), checksum_sha256=checksum,
                    scan_status="not_scanned", created_by_user_id=actor, created_at=now, updated_at=now)
            s.add(ver)
            try:
                s.flush()
            except IntegrityError:
                s.rollback()
                self._store.delete(key)
                raise KnowledgeConflict("This file has already been uploaded for this source.")
            _stage(s, {**audit, "target_id": vpid} if audit else None, source_public_id=src.public_id,
                   version_public_id=vpid, version=number, new_state="queued", authority_level=m["authority_level"],
                   language=m["language"], licence_class=m["licence_class"])
            try:
                s.commit()
            except Exception:
                self._store.delete(key)
                raise
            src_public = src.public_id
        self._enqueue_parse(vpid, actor)
        return {"source_public_id": src_public, "version_public_id": vpid, "version": number}

    def _enqueue_parse(self, vpid: str, actor: int | None) -> None:
        view, _ = self._jobs.enqueue(P.JOB_PARSE, {"version_id": vpid}, idempotency_key=f"parse:{vpid}:{self._clock().timestamp()}",
                                     actor_user_id=actor)
        with self._sf() as s:
            s.execute(update(V).where(V.public_id == vpid).values(parse_job_public_id=view["public_id"]))
            s.commit()

    # ------------------------------------------------------------------ guarded transitions
    def _version(self, s, public_id: str) -> V:
        v = s.scalar(select(V).where(V.public_id == public_id))
        if v is None:
            raise KnowledgeNotFound(public_id)
        return v

    def _move(self, s, v: V, expected: tuple[str, ...], new: str, **values) -> None:
        if new not in P.TRANSITIONS.get(v.state, set()) or v.state not in expected:
            raise KnowledgeConflict(f"A {v.state.replace('_', ' ')} version cannot move to {new.replace('_', ' ')}.")
        res = s.execute(update(V).where(V.id == v.id, V.state == v.state).values(state=new, updated_at=self._clock(), **values))
        if res.rowcount != 1:
            s.rollback()
            raise KnowledgeConflict("The version changed while this action ran; reload and retry.")

    @staticmethod
    def blockers(v: V) -> list[str]:
        """Everything that prevents approval or activation. Fail-closed: unknown provenance blocks."""
        out = []
        if v.scan_status != "scan_passed":
            out.append("The file has not passed a malware scan (" + v.scan_status.replace("_", " ") + ").")
        if not (v.publisher or "").strip():
            out.append("The publisher is not recorded.")
        if not (v.provenance_note or "").strip():
            out.append("The provenance note is not recorded.")
        if v.licence_class not in P.ACTIVATABLE_LICENCES:
            out.append("The licence classification does not permit use (" + P.LICENCE_LABEL.get(v.licence_class, v.licence_class) + ").")
        if v.language not in P.KB_LANGUAGES:
            out.append("The language is not a supported knowledge language.")
        if v.authority_level not in P.AUTHORITY_LEVELS:
            out.append("The authority level is invalid.")
        if not (v.extracted_chars or 0) > 0:
            out.append("No text was extracted.")
        return out

    def update_metadata(self, public_id: str, *, audit: dict | None = None, **meta) -> dict:
        m = self.validate_metadata(**meta)
        with self._sf() as s:
            v = self._version(s, public_id)
            if v.state not in ("queued", "review_required", "failed"):
                raise KnowledgeConflict("Metadata is frozen once a version is approved; upload a new version to change it.")
            v.language, v.authority_level, v.publisher = m["language"], m["authority_level"], m["publisher"]
            v.source_url, v.provenance_note, v.licence_class = m["source_url"], m["provenance_note"], m["licence_class"]
            v.updated_at = self._clock()
            _stage(s, {**audit, "target_id": public_id} if audit else None, version_public_id=public_id,
                   authority_level=m["authority_level"], language=m["language"], licence_class=m["licence_class"])
            s.commit()
        return self.version_detail(public_id)

    def approve(self, public_id: str, *, actor_user_id: int, audit: dict | None = None) -> dict:
        now = self._clock()
        with self._sf() as s:
            v = self._version(s, public_id)
            if v.state != "review_required":
                raise KnowledgeConflict("Only a version awaiting review can be approved.")
            blockers = self.blockers(v)
            if blockers:
                raise KnowledgeBlocked(blockers)
            self._move(s, v, ("review_required",), "approved", approved_by_user_id=actor_user_id, approved_at=now)
            _stage(s, {**audit, "target_id": public_id} if audit else None, version_public_id=public_id,
                   old_state="review_required", new_state="approved")
            s.commit()
        return self.version_detail(public_id)

    def reject(self, public_id: str, *, reason: str, actor_user_id: int, audit: dict | None = None) -> dict:
        if reason not in P.REJECTION_REASONS:
            raise KnowledgeValidationError("Choose a rejection reason.")
        now = self._clock()
        with self._sf() as s:
            v = self._version(s, public_id)
            old = v.state
            if old not in ("review_required", "approved"):
                raise KnowledgeConflict("Only a version awaiting review or approved (not yet indexed) can be rejected.")
            self._move(s, v, ("review_required", "approved"), "rejected", rejected_by_user_id=actor_user_id,
                       rejected_at=now, rejection_reason=reason)
            _stage(s, {**audit, "target_id": public_id} if audit else None, version_public_id=public_id,
                   old_state=old, new_state="rejected", reason_category=reason)
            s.commit()
        return self.version_detail(public_id)

    def request_index(self, public_id: str, *, actor_user_id: int, audit: dict | None = None) -> dict:
        with self._sf() as s:
            v = self._version(s, public_id)
            if v.state not in ("approved", "failed") or (v.state == "failed" and v.failed_stage != "index"):
                raise KnowledgeConflict("Only an approved version can be indexed.")
            if v.approved_at is None:
                raise KnowledgeConflict("Only an approved version can be indexed.")
            old = v.state
            self._move(s, v, ("approved", "failed"), "indexing", failure_category=None, failed_stage=None)
            _stage(s, {**audit, "target_id": public_id} if audit else None, version_public_id=public_id,
                   old_state=old, new_state="indexing")
            s.commit()
        try:
            view, _ = self._jobs.enqueue(P.JOB_INDEX, {"version_id": public_id}, actor_user_id=actor_user_id,
                                         idempotency_key=f"index:{public_id}")
        except Exception:
            with self._sf() as s:   # compensate: the version must not sit in 'indexing' without a job
                s.execute(update(V).where(V.public_id == public_id, V.state == "indexing").values(state="approved"))
                s.commit()
            raise
        with self._sf() as s:
            s.execute(update(V).where(V.public_id == public_id).values(index_job_public_id=view["public_id"]))
            s.commit()
        return self.version_detail(public_id)

    def activate(self, public_id: str, *, actor_user_id: int, audit: dict | None = None) -> dict:
        """Verify indexed + approved + permissible, then atomically switch the source's single active version."""
        now, retired_pid = self._clock(), None
        with self._sf() as s:
            v = self._version(s, public_id)
            if v.state != "indexed" or v.approved_at is None:
                raise KnowledgeConflict("Only an approved, fully indexed version can be activated.")
            blockers = [b for b in self.blockers(v) if "No text" not in b]
            rec = s.get(KnowledgeIndexRecord, v.id)
            if rec is None or rec.state != "built" or (rec.chunk_count or 0) <= 0:
                blockers.append("The index for this version is not complete.")
            if blockers:
                raise KnowledgeBlocked(blockers)
            prior = s.scalar(select(V).where(V.source_id == v.source_id, V.state == "active", V.id != v.id))
            if prior is not None:
                retired_pid = prior.public_id
                s.execute(update(V).where(V.id == prior.id, V.state == "active").values(
                    state="retired", retired_at=now, retired_by_user_id=actor_user_id, updated_at=now))
            self._move(s, v, ("indexed",), "active", activated_at=now, activated_by_user_id=actor_user_id)
            _stage(s, {**audit, "target_id": public_id} if audit else None, version_public_id=public_id,
                   version=v.version, old_state="indexed", new_state="active", replaced_version_public_id=retired_pid)
            try:
                s.commit()
            except IntegrityError:
                s.rollback()
                raise KnowledgeConflict("Another version of this source is active; reload and retry.")
        if retired_pid:
            self._enqueue_remove(retired_pid, actor_user_id)
        return self.version_detail(public_id)

    def retire(self, public_id: str, *, actor_user_id: int, audit: dict | None = None) -> dict:
        """Retire from candidate retrieval IMMEDIATELY (control-plane state); physical vector removal follows by job."""
        now = self._clock()
        with self._sf() as s:
            v = self._version(s, public_id)
            old = v.state
            if old not in ("active", "indexed"):
                raise KnowledgeConflict("Only an active or indexed version can be retired.")
            self._move(s, v, ("active", "indexed"), "retired", retired_at=now, retired_by_user_id=actor_user_id)
            _stage(s, {**audit, "target_id": public_id} if audit else None, version_public_id=public_id,
                   old_state=old, new_state="retired")
            s.commit()
        self._enqueue_remove(public_id, actor_user_id)
        return self.version_detail(public_id)

    def _enqueue_remove(self, vpid: str, actor: int | None) -> None:
        try:
            self._jobs.enqueue(P.JOB_REMOVE, {"version_id": vpid}, actor_user_id=actor, idempotency_key=f"remove:{vpid}")
        except Exception:   # noqa: BLE001 - retrieval is already excluded by control-plane state
            pass

    def reprocess(self, public_id: str, *, actor_user_id: int, audit: dict | None = None) -> dict:
        with self._sf() as s:
            v = self._version(s, public_id)
            if v.state != "failed":
                raise KnowledgeConflict("Only a failed version can be reprocessed.")
            stage = v.failed_stage
            if stage == "index":
                s.rollback()
                return self.request_index(public_id, actor_user_id=actor_user_id, audit=audit)
            self._move(s, v, ("failed",), "queued", failure_category=None, failed_stage=None, scan_status="not_scanned")
            _stage(s, {**audit, "target_id": public_id} if audit else None, version_public_id=public_id,
                   old_state="failed", new_state="queued")
            s.commit()
        self._enqueue_parse(public_id, actor_user_id)
        return self.version_detail(public_id)

    def delete_version(self, public_id: str, *, audit: dict | None = None) -> dict:
        """Hard delete ONLY a never-approved version (queued/review/failed/rejected, nothing indexed). Approved or
        once-active history is retired, never deleted."""
        with self._sf() as s:
            v = self._version(s, public_id)
            built = s.get(KnowledgeIndexRecord, v.id)
            if v.state not in ("queued", "review_required", "failed", "rejected") or v.approved_at is not None or built is not None:
                raise KnowledgeConflict("Approved or indexed versions are retired, not deleted.")
            key, src_id = v.storage_key, v.source_id
            _stage(s, {**audit, "target_id": public_id} if audit else None, version_public_id=public_id, old_state=v.state)
            s.delete(v)
            s.flush()
            if (s.scalar(select(func.count()).select_from(V).where(V.source_id == src_id)) or 0) == 0:
                s.delete(s.get(KnowledgeSource, src_id))
            s.commit()
        if key:
            self._store.delete(key)
        return {"deleted": public_id}

    # ------------------------------------------------------------------ read models
    def _row(self, v: V, src: KnowledgeSource) -> dict:
        return {
            "source_public_id": src.public_id, "title": src.title, "version_public_id": v.public_id, "version": v.version,
            "state": v.state, "active": v.state == "active", "language": v.language, "authority_level": v.authority_level,
            "authority_meaning": P.AUTHORITY_MEANING[v.authority_level], "publisher": v.publisher,
            "licence_class": v.licence_class, "licence_label": P.LICENCE_LABEL[v.licence_class],
            "scan_status": v.scan_status, "chunk_count": v.chunk_count, "failure_category": v.failure_category,
            "created_at": _iso(v.created_at), "updated_at": _iso(v.updated_at),
        }

    def list_sources(self, *, state: str | None = None, language: str | None = None, authority: int | None = None,
                     licence: str | None = None, active: bool | None = None, q: str | None = None,
                     page: int = 1, page_size: int = 25) -> dict:
        page, page_size = max(1, int(page)), max(1, min(int(page_size), 100))
        rank = func.row_number().over(
            partition_by=V.source_id, order_by=((V.state == "active").desc(), V.version.desc())).label("rk")
        with self._sf() as s:
            ranked = select(V.id.label("vid"), rank).subquery()
            conds = [ranked.c.rk == 1]
            if state:
                if state not in P.STATES:
                    raise KnowledgeValidationError("Unknown state.")
                conds.append(V.state == state)
            if language:
                conds.append(V.language == language)
            if authority:
                conds.append(V.authority_level == int(authority))
            if licence:
                conds.append(V.licence_class == licence)
            if active is True:
                conds.append(V.state == "active")
            elif active is False:
                conds.append(V.state != "active")
            if q:
                like = f"%{q.strip()[:80]}%"
                conds.append((KnowledgeSource.title.ilike(like)) | (KnowledgeSource.public_id == q.strip().lower())
                             | (V.publisher.ilike(like)))
            base = select(V, KnowledgeSource).join(ranked, ranked.c.vid == V.id).join(KnowledgeSource, KnowledgeSource.id == V.source_id).where(*conds)
            total = s.scalar(select(func.count()).select_from(base.subquery())) or 0
            rows = s.execute(base.order_by(V.updated_at.desc(), V.id.desc()).limit(page_size).offset((page - 1) * page_size)).all()
            return {"items": [self._row(v, src) for v, src in rows], "total": total, "page": page, "page_size": page_size}

    def source_detail(self, source_public_id: str) -> dict:
        with self._sf() as s:
            src = s.scalar(select(KnowledgeSource).where(KnowledgeSource.public_id == source_public_id))
            if src is None:
                raise KnowledgeNotFound(source_public_id)
            versions = s.scalars(select(V).where(V.source_id == src.id).order_by(V.version.desc())).all()
            return {"source_public_id": src.public_id, "title": src.title, "created_at": _iso(src.created_at),
                    "versions": [self._row(v, src) for v in versions]}

    def version_detail(self, public_id: str) -> dict:
        with self._sf() as s:
            v = self._version(s, public_id)
            src = s.get(KnowledgeSource, v.source_id)
            rec = s.get(KnowledgeIndexRecord, v.id)
            blockers = self.blockers(v) if v.state in ("review_required", "approved", "indexed") else []
            frozen = v.state not in ("queued", "review_required", "failed")
            return {
                **self._row(v, src),
                "source_reference": v.source_url, "provenance_note": v.provenance_note, "original_filename": v.original_filename,
                "media_type": v.media_type, "byte_size": v.byte_size, "checksum_sha256": v.checksum_sha256,
                "scanner": v.scanner_name, "extracted_chars": v.extracted_chars,
                "preview": v.preview_text, "preview_is_truncated": bool((v.extracted_chars or 0) > len(v.preview_text or "")),
                "failed_stage": v.failed_stage, "rejection_reason": v.rejection_reason,
                "approved_at": _iso(v.approved_at), "approved_by_user_id": v.approved_by_user_id,
                "indexed_at": _iso(v.indexed_at), "activated_at": _iso(v.activated_at), "retired_at": _iso(v.retired_at),
                "parse_job_id": v.parse_job_public_id, "index_job_id": v.index_job_public_id,
                "index": ({"state": rec.state, "chunk_count": rec.chunk_count, "embedder": rec.embedder, "collection": rec.collection,
                           "built_at": _iso(rec.built_at)} if rec else None),
                "blockers": blockers, "metadata_frozen": frozen,
                "can": {"edit": not frozen, "approve": v.state == "review_required" and not blockers,
                        "reject": v.state in ("review_required", "approved"),
                        "index": v.state == "approved" or (v.state == "failed" and v.failed_stage == "index"),
                        "activate": v.state == "indexed" and not [b for b in blockers if "No text" not in b],
                        "retire": v.state in ("active", "indexed"),
                        "reprocess": v.state == "failed",
                        "delete": v.state in ("queued", "review_required", "failed", "rejected") and v.approved_at is None and rec is None},
            }

    def stats(self) -> dict:
        with self._sf() as s:
            counts = dict(s.execute(select(V.state, func.count()).group_by(V.state)).all())
            sources = s.scalar(select(func.count()).select_from(KnowledgeSource)) or 0
        return {"sources": sources, "awaiting_review": counts.get("review_required", 0), "indexing": counts.get("indexing", 0),
                "failed": counts.get("failed", 0), "indexed_not_active": counts.get("indexed", 0), "active": counts.get("active", 0)}

    def active_version_ids(self) -> set[str]:
        with self._sf() as s:
            return set(s.scalars(select(V.public_id).where(V.state == "active", V.language.in_(P.KB_LANGUAGES))).all())
