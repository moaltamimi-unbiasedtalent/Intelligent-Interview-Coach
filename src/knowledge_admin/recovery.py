"""Backup, verification and restore of governed knowledge (package 02A part 2, REQ-OWN-05 K5/K7).

WHAT IS BACKED UP (one self-describing directory): the governed registry rows (``knowledge_sources``, ``knowledge_source_versions``,
``knowledge_index_records``), every private source file (opaque storage key, bytes verbatim) and the persistent governed index (a file-level copy of the
Chroma directory plus a ``chunks.jsonl`` export used for integrity checking). The manifest records a SHA-256 for every file, row counts, the source
environment's safe ``RuntimeIdentity`` (02K) and one ``IndexManifestV2`` per collection (collection checksum over chunk ids, text and metadata).

SAFETY RULES (each one is covered by a test)
* DRY-RUN IS THE DEFAULT. Nothing is written unless ``execute=True``.
* NOTHING IS EVER DELETED OR OVERWRITTEN. A backup directory must be new or empty. A restore target must be EMPTY (no registry rows, no private files, no
  index files); a non-empty target is refused unless ``allow_non_empty`` is set, and even then existing rows, files and index data are kept, only missing
  registry rows and files are added, and the index is not touched (reported, with the instruction to run a reindex).
* Restores go into a SEPARATE environment (a different database, file directory and index directory); the source is only ever read.
* The backup is verified before a restore starts and the restored environment is verified afterwards (row counts, file checksums, chunk count, collection
  checksum). A mismatch is a failed result, never a silent success.
* Report text contains kinds, counts, short hashes and the fixed codes below. No URL, credential or absolute path ever appears in a report or a manifest.
* Actor references (``*_user_id``) are kept only when that user exists in the target; otherwise they are cleared and counted (the audit history lives in the
  source database and is not part of this backup).
"""

from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from sqlalchemy import DateTime, func, select
from sqlalchemy.orm import sessionmaker

from src.knowledge_admin import policy as P
from src.knowledge_admin.contracts import IndexManifestV2, RuntimeIdentity
from src.persistence import Job, KnowledgeIndexRecord, KnowledgeSource, KnowledgeSourceVersion as V, User

BACKUP_FORMAT = 1
MODELS = (KnowledgeSource, V, KnowledgeIndexRecord)            # parent first: restore order
TABLE_KEYS = {m.__tablename__: m for m in MODELS}
MANIFEST = "manifest.json"
REGISTRY = "registry.json"
CHUNKS = "chunks.jsonl"
FILES_DIR = "files"
INDEX_DIR = "index"
KNOWLEDGE_JOB_TYPES = (P.JOB_PARSE, P.JOB_INDEX, P.JOB_REINDEX, P.JOB_REMOVE)


class RecoveryError(Exception):
    """A refusal with a fixed, safe ``code`` (never a path or an exception text)."""

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(code + (": " + detail if detail else ""))
        self.code = code


def _sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _now(clock: Callable[[], datetime] | None = None) -> str:
    return (clock() if clock else datetime.now(timezone.utc)).isoformat()


# ===================================================================== registry (de)serialisation
def _row_dict(obj: Any) -> dict:
    out = {}
    for col in obj.__table__.columns:
        value = getattr(obj, col.key)
        out[col.key] = value.isoformat() if isinstance(value, datetime) else value
    return out


def dump_registry(session_factory: sessionmaker) -> dict[str, list[dict]]:
    with session_factory() as s:
        return {m.__tablename__: [_row_dict(r) for r in s.scalars(select(m).order_by(m.id if hasattr(m, "id") else m.version_id)).all()] for m in MODELS}


EVIDENCE_STATES = ("approved", "indexing", "indexed", "active")      # the database CHECK ck_ksv_approval_evidence requires an approver for these


def _from_dict(model: Any, row: dict, user_ids: set[int], counters: dict, fallback_user_id: int | None) -> Any:
    kwargs = {}
    for col in model.__table__.columns:
        value = row.get(col.key)
        if value is not None and isinstance(col.type, DateTime):
            value = datetime.fromisoformat(value)
        if value is not None and any(fk.column.table.name == "users" for fk in col.foreign_keys) and value not in user_ids:
            if model is V and col.key == "approved_by_user_id" and row["state"] in EVIDENCE_STATES and fallback_user_id is not None:
                counters["actor_references_remapped"] += 1          # approval evidence is mandatory: remapped to the EXPLICIT operator-chosen user
                value = fallback_user_id
            else:
                counters["actor_references_cleared"] += 1
                value = None
        kwargs[col.key] = value
    return model(**kwargs)


def collection_checksum(chunks: list[Any]) -> str:
    """Order-independent digest over (chunk id, text hash, sorted metadata). Never includes a vector."""
    parts = sorted(f"{c.chunk_id}:{_sha_bytes(c.text.encode('utf-8'))}:{json.dumps(c.metadata, sort_keys=True, default=str)}" for c in chunks)
    return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()


def _chunk_line(c: Any) -> str:
    return json.dumps({"chunk_id": c.chunk_id, "text": c.text, "metadata": c.metadata}, sort_keys=True, default=str)


# ===================================================================== reports
@dataclass
class Report:
    action: str
    executed: bool
    ok: bool = True
    codes: list[str] = field(default_factory=list)            # fixed refusal / warning codes
    counts: dict = field(default_factory=dict)
    details: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"action": self.action, "mode": "executed" if self.executed else "dry_run", "ok": self.ok, "codes": list(self.codes),
                "counts": dict(self.counts), "details": dict(self.details)}


# ===================================================================== backup
def _quiescence_problem(session_factory: sessionmaker) -> int:
    with session_factory() as s:
        return int(s.scalar(select(func.count()).select_from(Job).where(Job.job_type.in_(KNOWLEDGE_JOB_TYPES), Job.state.in_(("queued", "running")))) or 0)


def _dir_nonempty(path: Path) -> bool:
    return path.exists() and (not path.is_dir() or any(path.iterdir()))


def create_backup(session_factory: sessionmaker, doc_store: Any, governed_store: Any, *, out_dir: str | Path, chroma_dir: str | Path | None,
                  identity: RuntimeIdentity | None = None, execute: bool = False, allow_active_jobs: bool = False,
                  clock: Callable[[], datetime] | None = None) -> Report:
    out = Path(out_dir)
    rep = Report("backup", execute)
    registry = dump_registry(session_factory)
    versions = registry[V.__tablename__]
    keys = [v["storage_key"] for v in versions if v.get("storage_key")]
    present = [k for k in keys if doc_store.exists(k)]
    missing = [k for k in keys if k not in set(present)]
    pending = _quiescence_problem(session_factory)
    chunks = governed_store.all_chunks() if governed_store is not None else []
    chroma = Path(chroma_dir) if chroma_dir else None
    rep.counts = {t: len(r) for t, r in registry.items()} | {"private_files": len(present), "private_files_missing": len(missing), "chunks": len(chunks)}
    if missing:
        rep.codes.append("private_files_missing")             # recorded in the manifest; a backup of a damaged environment is still a backup
    if pending and not allow_active_jobs:
        rep.ok = False
        rep.codes.append("knowledge_jobs_active")              # an index copy taken mid-write could be inconsistent
    if _dir_nonempty(out):
        rep.ok = False
        rep.codes.append("backup_target_not_empty")
    if not execute or not rep.ok:
        return rep

    (out / FILES_DIR).mkdir(parents=True, exist_ok=True)
    files = {}
    for k in present:
        data = doc_store.read(k)
        (out / FILES_DIR / k).write_bytes(data)
        files[k] = _sha_bytes(data)
    (out / REGISTRY).write_text(json.dumps(registry, sort_keys=True, indent=1), encoding="utf-8")
    (out / CHUNKS).write_text("\n".join(_chunk_line(c) for c in sorted(chunks, key=lambda c: c.chunk_id)), encoding="utf-8")
    index_files = {}
    if chroma is not None and chroma.is_dir():
        for src in sorted(p for p in chroma.rglob("*") if p.is_file()):
            rel = src.relative_to(chroma)
            dst = out / INDEX_DIR / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            index_files[str(rel).replace("\\", "/")] = _sha_file(dst)
    built = [r for r in registry[KnowledgeIndexRecord.__tablename__] if r["state"] == "built"]
    by_version = {v["id"]: v for v in versions}
    source_checksums = tuple((by_version[r["version_id"]]["public_id"], by_version[r["version_id"]]["checksum_sha256"]) for r in built if r["version_id"] in by_version)
    emb = identity.embedding if identity else None
    manifest_v2 = IndexManifestV2.create(collection_id=P.COLLECTION, checksum=collection_checksum(chunks), source_checksums=source_checksums,
                                         built_at=_now(clock), source_version_ids=tuple(sorted(s for s, _ in source_checksums)),
                                         provider=emb.provider if emb else None, model=emb.model if emb else None,
                                         dimensions=emb.dimensions if emb else None, degraded=bool(emb.degraded) if emb else False,
                                         degradation_reason=emb.degradation_reason if emb else None)
    manifest = {"format": BACKUP_FORMAT, "created_at": _now(clock), "source_identity": identity.to_dict() if identity else None,
                "counts": rep.counts, "registry_sha256": _sha_file(out / REGISTRY), "chunks_sha256": _sha_file(out / CHUNKS),
                "files": files, "missing_files": missing, "index_files": index_files, "index_manifest": manifest_v2.to_dict(),
                "consistent": not pending}
    (out / MANIFEST).write_text(json.dumps(manifest, sort_keys=True, indent=1), encoding="utf-8")
    rep.details = {"files_copied": len(files), "index_files_copied": len(index_files), "index_checksum": manifest_v2.checksum[:16] if manifest_v2.checksum else None,
                   "consistent": not pending}
    return rep


# ===================================================================== verify
def load_manifest(backup_dir: str | Path) -> dict:
    p = Path(backup_dir) / MANIFEST
    if not p.is_file():
        raise RecoveryError("backup_manifest_missing")
    m = json.loads(p.read_text(encoding="utf-8"))
    if m.get("format") != BACKUP_FORMAT:
        raise RecoveryError("backup_format_unsupported")
    return m


def verify_backup(backup_dir: str | Path) -> Report:
    base = Path(backup_dir)
    rep = Report("verify", False)
    try:
        m = load_manifest(base)
    except RecoveryError as e:
        rep.ok, rep.codes = False, [e.code]
        return rep
    problems = []
    for name, expected in (("registry_sha256", REGISTRY), ("chunks_sha256", CHUNKS)):
        p = base / expected
        if not p.is_file() or _sha_file(p) != m[name]:
            problems.append(f"{expected}_integrity")
    bad_files = [k for k, h in m["files"].items() if not (base / FILES_DIR / k).is_file() or _sha_file(base / FILES_DIR / k) != h]
    bad_index = [k for k, h in m["index_files"].items() if not (base / INDEX_DIR / k).is_file() or _sha_file(base / INDEX_DIR / k) != h]
    if bad_files:
        problems.append("private_file_integrity")
    if bad_index:
        problems.append("index_file_integrity")
    rep.counts = {"files_checked": len(m["files"]), "files_bad": len(bad_files), "index_files_checked": len(m["index_files"]), "index_files_bad": len(bad_index)}
    if problems:
        rep.ok, rep.codes = False, problems
    rep.details = {"consistent": m.get("consistent", False), "created_at": m["created_at"], "missing_files_at_backup": len(m.get("missing_files", []))}
    return rep


# ===================================================================== restore
def _target_nonempty(session_factory: sessionmaker, files_dir: Path, index_dir: Path) -> list[str]:
    out = []
    with session_factory() as s:
        for m in MODELS:
            if (s.scalar(select(func.count()).select_from(m)) or 0) > 0:
                out.append("registry_not_empty")
                break
    if _dir_nonempty(files_dir):
        out.append("files_not_empty")
    if _dir_nonempty(index_dir):
        out.append("index_not_empty")
    return out


def load_chunks(backup_dir: str | Path) -> list:
    from src.copilot.models import DocumentChunk

    out = []
    text = (Path(backup_dir) / CHUNKS).read_text(encoding="utf-8")
    for line in text.splitlines():
        if not line.strip():
            continue
        d = json.loads(line)
        meta = dict(d["metadata"])
        out.append(DocumentChunk(chunk_id=d["chunk_id"], doc_id=meta.get("doc_id", d["chunk_id"]), text=d["text"],
                                 position=int(meta.get("chunk_index", 0) or 0), metadata=meta))
    return out


def restore_backup(backup_dir: str | Path, *, session_factory: sessionmaker, files_dir: str | Path, index_dir: str | Path, open_store: Callable[[], Any],
                   execute: bool = False, allow_non_empty: bool = False, rebuild_index: bool = False, fallback_user_id: int | None = None) -> Report:
    """Restore into a SEPARATE environment. ``open_store`` opens the governed store on ``index_dir`` AFTER the index files were copied (it is also used
    for the post-restore verification). Existing data is never deleted or overwritten. ``rebuild_index`` skips the file-level index copy and instead
    re-adds the backed-up chunks through the target store (its embedder runs: only use it with a local or approved embedder)."""
    base, files_dir, index_dir = Path(backup_dir), Path(files_dir), Path(index_dir)
    rep = Report("restore", execute)
    v = verify_backup(base)
    if not v.ok:
        rep.ok, rep.codes = False, ["backup_integrity_failed"] + v.codes
        return rep
    manifest = load_manifest(base)
    registry = json.loads((base / REGISTRY).read_text(encoding="utf-8"))
    rep.counts = dict(manifest["counts"])
    if rebuild_index and ((manifest.get("source_identity") or {}).get("embedding") or {}).get("provider") != "local":
        rep.ok, rep.codes = False, ["rebuild_requires_local_embedder"]      # never re-embed with a provider that was not the source's (cost, drift)
        return rep
    nonempty = _target_nonempty(session_factory, files_dir, index_dir)
    if nonempty and not allow_non_empty:
        rep.ok, rep.codes = False, ["target_not_empty"] + nonempty
        return rep
    if nonempty:
        rep.codes.append("non_empty_target_allowed")
    with session_factory() as s:
        target_users = set(s.scalars(select(User.id)).all())
    needs_actor = [r for r in registry[V.__tablename__] if r["state"] in EVIDENCE_STATES and r.get("approved_by_user_id") not in target_users]
    if needs_actor and (fallback_user_id is None or fallback_user_id not in target_users):
        # Approval evidence cannot be dropped and must not be invented: the operator names an EXISTING user of the target as the restorer of record.
        rep.ok = False
        rep.codes.append("approval_actor_missing_in_target")
        rep.details = {"versions_needing_an_actor": len(needs_actor)}
        return rep
    if not execute:
        return rep

    counters = {"actor_references_cleared": 0, "actor_references_remapped": 0}
    copy_index = "index_not_empty" not in nonempty
    with session_factory() as s:
        user_ids = set(s.scalars(select(User.id)).all())
        existing = {m.__tablename__: {getattr(r, "public_id", None) or r.version_id for r in s.scalars(select(m)).all()} for m in MODELS}
        existing_ids = {m.__tablename__: {getattr(r, "id", None) or r.version_id for r in s.scalars(select(m)).all()} for m in MODELS}
        added = {}
        for m in MODELS:
            n = 0
            for row in registry[m.__tablename__]:
                ident = row.get("public_id") or row["version_id"]
                if ident in existing[m.__tablename__]:
                    continue
                pk = row.get("id") or row["version_id"]
                if pk in existing_ids[m.__tablename__]:
                    s.rollback()
                    rep.ok, rep.codes = False, rep.codes + ["registry_id_conflict"]
                    return rep
                s.add(_from_dict(m, row, user_ids, counters, fallback_user_id))
                n += 1
            s.flush()
            added[m.__tablename__] = n
        s.commit()
    copied_files = 0
    files_dir.mkdir(parents=True, exist_ok=True)
    for k in manifest["files"]:
        dst = files_dir / k
        if dst.exists():
            if _sha_file(dst) != manifest["files"][k]:
                rep.ok, rep.codes = False, rep.codes + ["private_file_conflict"]
                return rep
            continue
        shutil.copy2(base / FILES_DIR / k, dst)
        copied_files += 1
    index_copied = 0
    if copy_index and rebuild_index:
        index_dir.mkdir(parents=True, exist_ok=True)
        store = open_store()
        store.add_chunks(load_chunks(base))                  # deterministic chunk ids: a replay adds nothing twice
        index_copied = -1
        rep.codes.append("index_rebuilt_from_chunks")
    elif copy_index:
        index_dir.mkdir(parents=True, exist_ok=True)
        for rel in manifest["index_files"]:
            dst = index_dir / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(base / INDEX_DIR / rel, dst)
            index_copied += 1
    else:
        rep.codes.append("index_not_restored_run_reindex")
    rep.details = {"rows_added": added, "files_copied": copied_files, "index_files_copied": index_copied} | counters
    verify_restored(rep, manifest, session_factory, files_dir, open_store if copy_index else None)
    return rep


def verify_restored(rep: Report, manifest: dict, session_factory: sessionmaker, files_dir: Path, open_store: Callable[[], Any] | None) -> None:
    """Post-restore verification of the TARGET: row counts, every file's checksum, chunk count and collection checksum."""
    problems = []
    with session_factory() as s:
        for m in MODELS:
            if (s.scalar(select(func.count()).select_from(m)) or 0) < manifest["counts"][m.__tablename__]:
                problems.append(f"{m.__tablename__}_row_count")
    for k, h in manifest["files"].items():
        p = files_dir / k
        if not p.is_file() or _sha_file(p) != h:
            problems.append("private_file_checksum")
            break
    if open_store is not None:
        store = open_store()
        chunks = store.all_chunks()
        if len(chunks) != manifest["counts"]["chunks"]:
            problems.append("index_chunk_count")
        if collection_checksum(chunks) != manifest["index_manifest"]["checksum"]:
            problems.append("index_collection_checksum")
        rep.counts["restored_chunks"] = len(chunks)
    if problems:
        rep.ok = False
        rep.codes.extend(sorted(set(problems)))
