"""Worker-side knowledge pipeline: parse, index and removal (P10B-W10.8). Runs inside W10.9 jobs, never in an HTTP request.

Every step is REPLAY-SAFE (a job can run again after a lease expiry or a crash):
* parse: a guarded state check; the preview/extracted-size are overwritten with identical values (checksum-anchored).
* index: deterministic chunk ids (sha256 of version id + chunk text) and a store that skips ids already present, so a replay
  after a partial or complete write leaves exactly one copy of each chunk; the index record is an upsert.
* remove: deleting by version id is naturally idempotent.
Failures are classified (retryable vs permanent); on a job's LAST attempt the domain state is also set to ``failed`` so a
version can never sit in ``processing``/``indexing`` forever.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from typing import Any, Callable

from sqlalchemy import select, update

from src.copilot.ingestion.chunking import chunk_units
from src.copilot.ingestion.loaders import LoadedUnit
from src.documents.file_security import FileRejected, FileScanUnavailable, enforce_scan
from src.documents.parsing import ParseError, parse_document, parse_txt
from src.jobs.registry import PermanentJobError, RetryableJobError
from src.knowledge_admin import policy as P
from src.persistence import KnowledgeIndexRecord, KnowledgeSource, KnowledgeSourceVersion as V, utcnow

log = logging.getLogger("ask4mo.knowledge.runtime")


@dataclass
class KnowledgeRuntime:
    session_factory: Any
    doc_store: Any
    scanner: Any = None                      # a FileSecurityScanner (None => the configured default)
    vector_store_factory: Callable[[], Any] = None   # returns the GOVERNED collection store
    clock: Callable = utcnow


def _runtime(ctx) -> KnowledgeRuntime:
    rt = getattr(ctx.services, "knowledge", None) if ctx.services is not None else None
    if rt is None:
        raise PermanentJobError("configuration_error")
    return rt


def _fail_version(rt: KnowledgeRuntime, vpid: str, stage: str, category: str, expected: tuple[str, ...], **extra) -> None:
    with rt.session_factory() as s:
        s.execute(update(V).where(V.public_id == vpid, V.state.in_(expected)).values(
            state="failed", failed_stage=stage, failure_category=category, updated_at=rt.clock(), **extra))
        s.commit()


def _load(rt: KnowledgeRuntime, vpid: str) -> dict | None:
    with rt.session_factory() as s:
        v = s.scalar(select(V).where(V.public_id == vpid))
        if v is None:
            return None
        src = s.get(KnowledgeSource, v.source_id)
        return {"id": v.id, "state": v.state, "key": v.storage_key, "name": v.original_filename, "ext": v.original_filename.rsplit(".", 1)[-1].lower(),
                "checksum": v.checksum_sha256, "title": src.title, "source_id": src.public_id, "version": v.version,
                "language": v.language, "authority": v.authority_level, "publisher": v.publisher, "url": v.source_url}


def _read_verified(rt: KnowledgeRuntime, info: dict) -> bytes:
    try:
        data = rt.doc_store.read(info["key"])
    except FileNotFoundError:
        raise PermanentJobError("invalid_payload")
    except Exception:  # noqa: BLE001 - storage trouble is transient
        raise RetryableJobError("unavailable")
    if hashlib.sha256(data).hexdigest() != info["checksum"]:
        raise PermanentJobError("invalid_payload")      # integrity failure: never parse or index altered bytes
    return data


def _units(data: bytes, ext: str):
    parsed = parse_txt(data) if ext in ("txt", "md") else parse_document(data, ext)
    return [LoadedUnit(text=seg.text, metadata={k: v for k, v in (("page", seg.page), ("section", seg.section)) if v is not None})
            for seg in parsed.segments if seg.text.strip()], parsed.full_text


# ------------------------------------------------------------------ parse
def run_parse(vpid: str, ctx) -> None:
    rt = _runtime(ctx)
    info = _load(rt, vpid)
    if info is None or info["state"] not in ("queued", "processing"):
        return                                              # stale/replayed job: nothing to do
    last = ctx.attempt >= ctx.max_attempts
    with rt.session_factory() as s:
        s.execute(update(V).where(V.public_id == vpid, V.state == "queued").values(state="processing", updated_at=rt.clock()))
        s.commit()
    try:
        data = _read_verified(rt, info)
        scanner = rt.scanner
        try:
            result = enforce_scan(data, info["name"], scanner=scanner, required=True)
        except FileRejected:
            _fail_version(rt, vpid, "parse", "scan_failed", ("processing",), scan_status="scan_failed")
            raise PermanentJobError("unsupported")
        except FileScanUnavailable:
            _fail_version(rt, vpid, "parse", "scan_unavailable", ("processing",), scan_status="scan_unavailable")
            raise PermanentJobError("configuration_error")
        try:
            units, full = _units(data, info["ext"])
        except ParseError:
            _fail_version(rt, vpid, "parse", "parse_failed", ("processing",), scan_status="scan_passed", scanner_name=result.scanner)
            raise PermanentJobError("unsupported")
        if not full.strip():
            _fail_version(rt, vpid, "parse", "no_text", ("processing",), scan_status="scan_passed", scanner_name=result.scanner)
            raise PermanentJobError("unsupported")
        with rt.session_factory() as s:
            s.execute(update(V).where(V.public_id == vpid, V.state == "processing").values(
                state="review_required", scan_status="scan_passed", scanner_name=result.scanner,
                preview_text=full[:P.PREVIEW_CHARS], extracted_chars=len(full), failure_category=None, failed_stage=None,
                updated_at=rt.clock()))
            s.commit()
    except RetryableJobError:
        if last:
            _fail_version(rt, vpid, "parse", "unavailable", ("processing", "queued"))
        raise
    except PermanentJobError:
        raise
    except Exception:  # noqa: BLE001 - unexpected: record a safe category, never the text
        _fail_version(rt, vpid, "parse", "internal_error", ("processing", "queued"))
        raise PermanentJobError("internal_error")


# ------------------------------------------------------------------ index
def build_chunks(info: dict, data: bytes, version_public_id: str):
    units, _ = _units(data, info["ext"])
    chunks = chunk_units(units, source_id=version_public_id)       # ids = sha256(version id + chunk text): deterministic
    for c in chunks:
        c.metadata.update({
            "title": info["title"], "knowledge_source_id": info["source_id"], "knowledge_version_id": version_public_id,
            "authority_level": info["authority"], "publisher": info["publisher"], "language": info["language"],
            "source_version": str(info["version"]), "document_type": "governed_knowledge", "filename": info["name"],
        })
        if info["url"]:
            c.metadata["source_url"] = info["url"]
    return chunks


def run_index(vpid: str, ctx) -> None:
    rt = _runtime(ctx)
    info = _load(rt, vpid)
    if info is None or info["state"] != "indexing":
        return                                              # already indexed/active/retired/rejected: replay is a no-op
    last = ctx.attempt >= ctx.max_attempts
    try:
        data = _read_verified(rt, info)
        chunks = build_chunks(info, data, vpid)
        if not chunks:
            _fail_version(rt, vpid, "index", "no_chunks", ("indexing",))
            raise PermanentJobError("unsupported")
        store = rt.vector_store_factory()
        try:
            store.add_chunks(chunks)                        # idempotent: ids already present are skipped
        except Exception:  # noqa: BLE001 - vector store / embedding provider trouble: retry, text never recorded
            raise RetryableJobError("unavailable")
        now = rt.clock()
        with rt.session_factory() as s:
            rec = s.get(KnowledgeIndexRecord, info["id"])
            if rec is None:
                s.add(KnowledgeIndexRecord(version_id=info["id"], collection=P.COLLECTION, embedder=type(store.embedder).__name__[:64],
                                           chunk_count=len(chunks), state="built", built_at=now, updated_at=now))
            else:
                rec.chunk_count, rec.state, rec.built_at, rec.removed_at, rec.updated_at = len(chunks), "built", now, None, now
            s.flush()
            res = s.execute(update(V).where(V.public_id == vpid, V.state == "indexing").values(
                state="indexed", chunk_count=len(chunks), indexed_at=now, failure_category=None, failed_stage=None, updated_at=now))
            s.commit()
            if res.rowcount != 1:
                log.info("index finished for %s but the version is no longer indexing", vpid)
    except RetryableJobError:
        if last:
            _fail_version(rt, vpid, "index", "unavailable", ("indexing",))
        raise
    except PermanentJobError:
        raise
    except Exception:  # noqa: BLE001
        _fail_version(rt, vpid, "index", "internal_error", ("indexing",))
        raise PermanentJobError("internal_error")


# ------------------------------------------------------------------ removal
def run_remove(vpid: str, ctx) -> None:
    rt = _runtime(ctx)
    last = ctx.attempt >= ctx.max_attempts
    with rt.session_factory() as s:
        v = s.scalar(select(V).where(V.public_id == vpid))
        if v is None or v.state != "retired":
            return                                           # only a retired version is ever removed
        vid = v.id
    try:
        rt.vector_store_factory().delete_where({"knowledge_version_id": vpid})
    except Exception:  # noqa: BLE001
        if last:
            with rt.session_factory() as s:
                rec = s.get(KnowledgeIndexRecord, vid)
                if rec is not None:
                    rec.state, rec.updated_at = "removal_failed", rt.clock()
                    s.commit()
        raise RetryableJobError("unavailable")
    with rt.session_factory() as s:
        rec = s.get(KnowledgeIndexRecord, vid)
        if rec is not None:
            rec.state, rec.removed_at, rec.updated_at = "removed", rt.clock(), rt.clock()
            s.commit()
