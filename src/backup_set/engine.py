"""One consistent backup SET of database + private documents + governed knowledge (package 05B, PG-09; builds on 02A ``knowledge_admin.recovery``).

WHAT A SET IS: one directory created in one run, described by ONE ``manifest.json`` written LAST (a directory without a manifest is not a set and is refused by
``verify``/``restore``). It holds
* ``database/``   a consistent snapshot: SQLite through the online backup API (a consistent copy while the file is in use), PostgreSQL through ``pg_dump`` (custom
                  format, credentials passed through the child's environment, never on the command line);
* ``documents/``  every private candidate document file (opaque storage keys, bytes verbatim);
* ``knowledge/``  the 02A governed-knowledge backup (registry rows, private source files, ``chunks.jsonl``, a file-level copy of the persistent index) with its own
                  02A manifest; the index checksum, the embedder identity and a deterministic retrieval probe are recorded in the set manifest.
The manifest records a SHA-256 for every file (plaintext and as stored), row counts for EVERY table, the Alembic revision, the encryption posture and the
consistency evidence. Optional AES-256-GCM sealing (``crypto``) and an HMAC manifest signature make tampering detectable.

SAFETY RULES (each is covered by a test)
* DRY-RUN IS THE DEFAULT. Nothing is written without ``execute=True``.
* NOTHING IS EVER OVERWRITTEN OR DELETED. A backup target must be new or empty; a restore target must not exist or be empty; the set is only ever read by a
  restore. Files are created exclusively. Symlinks in a source tree are skipped (never followed), a symlink in a set is refused.
* ACTIVE JOBS ARE REFUSED (a queued or running job means the snapshot could be taken mid-write); the check is repeated after the copy, and any change to the
  source files during the copy discards the set (no manifest is written, so it can never be restored).
* ENCRYPTION AT REST IS REQUIRED in every hosted environment (staging, production and any unknown ``API_ENV``): execute is refused unless the set is sealed or the
  operator attests that the destination is encrypted storage (recorded as an attestation, NOT verified). Development and test may write an unencrypted set, and say so.
* A restore verifies the whole set first (every file, the manifest signature when present or required) and the restored environment afterwards (schema
  revision, every table's row count, every file checksum, the index checksum). A mismatch is a failed result, never a silent success.
* Reports and the manifest hold codes, counts and short hashes. No URL, credential, key, absolute path or file content appears in either.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import shutil
import sqlite3
import subprocess
import tempfile
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from sqlalchemy import inspect, text
from sqlalchemy.engine import make_url

from src.backup_set import crypto
from src.knowledge_admin import policy as KP
from src.knowledge_admin.recovery import Report, collection_checksum, create_backup as create_knowledge_backup, restore_backup as restore_knowledge_backup

SET_FORMAT = 1
TOOL = "ask4mo-backup-set/1"
MANIFEST = "manifest.json"
DB_DIR, DOCS_DIR, KNOWLEDGE_DIR = "database", "documents", "knowledge"
SQLITE_FILE, PG_FILE = f"{DB_DIR}/app.sqlite", f"{DB_DIR}/app.pgdump"
DEV_ENVIRONMENTS = ("development", "dev", "local", "test", "testing")
RESTORE_DB_NAME_MARKERS = ("restore", "staging", "drill")
PROBE_QUERIES, PROBE_TOP_K = 5, 3
_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,62}$")


class SetError(Exception):
    """A refusal with a fixed, safe ``code`` (never a path, a URL, a key or an exception text)."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def encryption_required(api_env: str | None) -> bool:
    """Hosted environments (staging, production and ANY unknown value) always require encryption at rest; only the named local environments do not."""
    return (api_env or "development").strip().lower() not in DEV_ENVIRONMENTS


def _now(clock: Callable[[], datetime] | None = None) -> datetime:
    return clock() if clock else datetime.now(timezone.utc)


def sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def safe_rel(name: str) -> bool:
    """A manifest path must be a plain relative path: no absolute path, no parent step, no backslash, no NUL, no empty part."""
    if not name or "\x00" in name or "\\" in name or name.startswith("/"):
        return False
    parts = name.split("/")
    return all(p not in ("", ".", "..") for p in parts)


def canonical(manifest: dict) -> bytes:
    return json.dumps({k: v for k, v in manifest.items() if k != "signature"}, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sign(manifest: dict, key: bytes) -> dict:
    return {"alg": "hmac-sha256", "key_fingerprint": crypto.fingerprint(key), "value": hmac.new(key, canonical(manifest), hashlib.sha256).hexdigest()}


def manifest_digest(set_dir: Path) -> str:
    return sha_file(Path(set_dir) / MANIFEST)


# ===================================================================== source description
@dataclass
class Source:
    """Where a set is taken from. Every location is the operator's own configuration (the same variables the API and the worker read)."""

    database_url: str
    documents_dir: Path
    knowledge_files_dir: Path | None = None       # the governed knowledge private-file directory (under the data root)
    knowledge_index_dir: Path | None = None       # the persistent governed Chroma directory
    identity: Any = None                          # an optional 02K ``RuntimeIdentity`` (safe: no URL, path or secret)

    def dialect(self) -> str:
        return make_url(self.database_url).get_backend_name()


class _NoFiles:
    def exists(self, key: str) -> bool:
        return False

    def read(self, key: str) -> bytes:   # pragma: no cover - never reached
        raise FileNotFoundError(key)


def _engine(url: str):
    from src.persistence import make_engine

    return make_engine(url)


def _sqlite_path(url: str) -> Path:
    u = make_url(url)
    if u.get_backend_name() != "sqlite" or not u.database or u.database == ":memory:":
        raise SetError("sqlite_file_required")
    return Path(u.database)


def _check_ident(name: str) -> str:
    if not _IDENT.match(name):
        raise SetError("unsafe_table_name")
    return name


def table_counts_sqlite(path: Path) -> dict[str, int]:
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        names = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
        return {n: int(con.execute(f'SELECT COUNT(*) FROM "{_check_ident(n)}"').fetchone()[0]) for n in names}
    finally:
        con.close()


def table_counts_sa(engine) -> dict[str, int]:
    with engine.connect() as c:
        names = sorted(inspect(c).get_table_names())
        return {n: int(c.execute(text(f'SELECT COUNT(*) FROM "{_check_ident(n)}"')).scalar() or 0) for n in names}


def table_counts(url: str) -> dict[str, int]:
    if make_url(url).get_backend_name() == "sqlite":
        return table_counts_sqlite(_sqlite_path(url))
    eng = _engine(url)
    try:
        return table_counts_sa(eng)
    finally:
        eng.dispose()


def schema_revision(counts_url: str) -> str | None:
    eng = _engine(counts_url)
    try:
        with eng.connect() as c:
            if "alembic_version" not in inspect(c).get_table_names():
                return None
            return c.execute(text("SELECT version_num FROM alembic_version")).scalar()
    finally:
        eng.dispose()


def active_jobs(url: str) -> int:
    """Queued or running jobs of ANY type (the snapshot must not be taken while work is in flight). Raises ``SetError('jobs_table_missing')`` on a database without the queue."""
    eng = _engine(url)
    try:
        with eng.connect() as c:
            if "jobs" not in inspect(c).get_table_names():
                raise SetError("jobs_table_missing")
            return int(c.execute(text("SELECT COUNT(*) FROM jobs WHERE state IN ('queued','running')")).scalar() or 0)
    finally:
        eng.dispose()


def _tree_fingerprint(root: Path | None, *, mtimes: bool = True) -> tuple:
    """(name, size[, mtime]) of every regular file. The persistent index directory is fingerprinted WITHOUT mtimes: merely opening a Chroma collection rewrites its HNSW
    segment files with identical content and size, so an mtime there would report a change that is not one (found by the scratch-restore rewrite). Added, removed or
    resized index files are still detected; the active-jobs check covers index writes."""
    if root is None or not root.is_dir():
        return ()
    out = []
    for p in sorted(root.rglob("*")):
        if p.is_file() and not p.is_symlink():
            st = p.stat()
            out.append((str(p.relative_to(root)), st.st_size) + ((st.st_mtime_ns,) if mtimes else ()))
    return tuple(out)


def _is_inside(child: Path, parent: Path | None) -> bool:
    if parent is None:
        return False
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def _dir_nonempty(path: Path) -> bool:
    return path.exists() and (not path.is_dir() or any(path.iterdir()))


# ===================================================================== writing files into a set
@dataclass
class _Writer:
    out: Path
    set_id: str
    key: bytes | None
    files: dict = field(default_factory=dict)

    def put(self, logical: str, src: Path) -> None:
        if not safe_rel(logical) or logical in self.files:
            raise SetError("unsafe_path")
        stored = logical + (".sealed" if self.key else "")
        dst = self.out / stored
        dst.parent.mkdir(parents=True, exist_ok=True)
        if self.key:
            plain, size = crypto.seal_file(src, dst, self.key, set_id=self.set_id, logical=logical)
        else:
            with open(src, "rb") as fin, open(dst, "xb") as fout:                 # exclusive create: never overwrites
                shutil.copyfileobj(fin, fout, 1 << 20)
            plain, size = sha_file(dst), dst.stat().st_size
        self.files[logical] = {"sha256": plain, "size": size, "stored": stored, "stored_sha256": sha_file(dst), "sealed": bool(self.key)}


def _pg_env_and_args(url: str) -> tuple[dict, list[str]]:
    u = make_url(url)
    if u.get_backend_name() not in ("postgresql", "postgres"):
        raise SetError("postgresql_required")
    env = dict(os.environ)
    if u.password:
        env["PGPASSWORD"] = u.password                          # never on the command line (a process list shows arguments)
    for query, variable in {"sslmode": "PGSSLMODE", "sslrootcert": "PGSSLROOTCERT", "sslcert": "PGSSLCERT", "sslkey": "PGSSLKEY", "sslcrl": "PGSSLCRL", "connect_timeout": "PGCONNECT_TIMEOUT"}.items():
        if query in u.query:
            env[variable] = u.query[query]
    args = []
    if u.host:
        args += ["--host", u.host]
    if u.port:
        args += ["--port", str(u.port)]
    if u.username:
        args += ["--username", u.username]
    if not u.database:
        raise SetError("database_name_missing")
    return env, args + ["--dbname", u.database]


def _run_pg(binary: str, argv: list[str], env: dict, code: str) -> None:
    try:
        done = subprocess.run([binary, *argv], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3600, check=False)
    except FileNotFoundError:
        raise SetError(code + "_tool_missing") from None
    except subprocess.TimeoutExpired:
        raise SetError(code + "_timeout") from None
    if done.returncode != 0:
        raise SetError(code)                                    # stderr is discarded on purpose: it can carry a host, a user or a table value


def _knowledge_handles(src: Source):
    from src.copilot.embeddings import LocalHashEmbedder
    from src.copilot.vectorstore import ChromaStore
    from src.documents.storage import LocalDocumentStore
    from src.persistence import make_session_factory

    eng = _engine(src.database_url)
    sf = make_session_factory(eng)
    files = src.knowledge_files_dir
    chroma = src.knowledge_index_dir
    docs = LocalDocumentStore(str(files)) if files is not None and Path(files).is_dir() else _NoFiles()
    store = ChromaStore(LocalHashEmbedder(), persist_dir=str(chroma), collection_name=KP.COLLECTION) if chroma is not None and Path(chroma).is_dir() else None
    return sf, docs, store, eng


def retrieval_probe(store: Any) -> dict:
    """A deterministic retrieval-evidence probe: queries are the first words of evenly spaced governed chunks (no model, no network, the local hashing embedder);
    the evidence is the ordered chunk ids and rounded scores. The drill re-runs the same queries against the restored index and compares."""
    chunks = sorted(store.all_chunks(), key=lambda c: c.chunk_id)
    if not chunks:
        return {"run": False, "reason": "no_chunks"}
    n = min(PROBE_QUERIES, len(chunks))
    picks = [chunks[(i * len(chunks)) // n] for i in range(n)]
    probes = []
    for c in picks:
        q = " ".join(c.text.split()[:12])
        hits = store.query(q, top_k=PROBE_TOP_K)
        probes.append({"query": q, "hit_ids": [h.chunk_id for h in hits], "scores": [round(float(h.score), 6) for h in hits]})
    return {"run": True, "top_k": PROBE_TOP_K, "embedder": "local_hash", "queries": probes}


# ===================================================================== create
def create_set(source: Source, *, out_dir: str | Path, execute: bool = False, encryption_key: bytes | None = None, signing_key: bytes | None = None,
               storage_encrypted_attested: bool = False, api_env: str | None = None, allow_active_jobs: bool = False,
               pg_dump_bin: str = "pg_dump", extra_manifest: dict | None = None, pg_snapshot: str | None = None,
               private_probe: bool = False, before_publish: Callable | None = None, clock: Callable[[], datetime] | None = None) -> Report:
    out = Path(out_dir)
    rep = Report("backup_set", execute)
    dialect = source.dialect()
    if dialect not in ("sqlite", "postgresql"):
        rep.ok, rep.codes = False, ["unsupported_database"]
        return rep
    required = encryption_required(api_env)
    if required and encryption_key is None and not storage_encrypted_attested:
        rep.ok = False
        rep.codes.append("encryption_required")                  # hosted: seal the set or attest encrypted storage
    if encryption_key is None and storage_encrypted_attested:
        rep.codes.append("encryption_attested_not_verified")
    if encryption_key is None and not storage_encrypted_attested and not required:
        rep.codes.append("unencrypted_set")                      # allowed locally, stated in the manifest
    if _dir_nonempty(out):
        rep.ok = False
        rep.codes.append("backup_target_not_empty")
    docs_dir = Path(source.documents_dir)
    for src_dir in (docs_dir, source.knowledge_files_dir, source.knowledge_index_dir):
        if _is_inside(out, Path(src_dir) if src_dir else None):
            rep.ok = False
            rep.codes.append("backup_target_inside_source")
            break
    if dialect == "sqlite":
        try:
            _sqlite_path(source.database_url)
        except SetError as e:
            rep.ok, rep.codes = False, rep.codes + [e.code]
    try:
        pending = active_jobs(source.database_url)
    except SetError as e:
        rep.ok, rep.codes = False, rep.codes + [e.code]
        return rep
    except Exception:  # noqa: BLE001 - never the driver text (it can hold a host or a user name)
        rep.ok, rep.codes = False, rep.codes + ["source_database_unreachable"]
        return rep
    if pending and not allow_active_jobs:
        rep.ok = False
        rep.codes.append("jobs_active")
    elif pending:
        rep.codes.append("jobs_active_allowed_inconsistent")
    doc_files = [p for p in sorted(docs_dir.rglob("*")) if p.is_file() and not p.is_symlink()] if docs_dir.is_dir() else []
    skipped_links = sum(1 for p in docs_dir.rglob("*") if p.is_symlink()) if docs_dir.is_dir() else 0
    try:
        counts = table_counts(source.database_url)
    except Exception:  # noqa: BLE001
        rep.ok, rep.codes = False, rep.codes + ["source_database_unreachable"]
        return rep
    rep.counts = {"tables": len(counts), "rows": sum(counts.values()), "document_files": len(doc_files), "symlinks_skipped": skipped_links}
    if not execute or not rep.ok:
        return rep

    set_id = uuid.uuid4().hex
    created = _now(clock)
    writer = _Writer(out, set_id, encryption_key)
    before = (_tree_fingerprint(docs_dir), _tree_fingerprint(source.knowledge_files_dir), _tree_fingerprint(source.knowledge_index_dir, mtimes=False))
    out.mkdir(parents=True, exist_ok=True)
    engines: list = []
    with tempfile.TemporaryDirectory(prefix="a4mb-") as work_s:
        work = Path(work_s)
        try:
            # 1) database snapshot
            if dialect == "sqlite":
                snap = work / "app.sqlite"
                src_con = sqlite3.connect(f"file:{_sqlite_path(source.database_url)}?mode=ro", uri=True)
                dst_con = sqlite3.connect(snap)
                try:
                    src_con.backup(dst_con)
                finally:
                    dst_con.close()
                    src_con.close()
                db_counts = table_counts_sqlite(snap)
                writer.put(SQLITE_FILE, snap)
                db_file = SQLITE_FILE
            else:
                snap = work / "app.pgdump"
                env, conn = _pg_env_and_args(source.database_url)
                _run_pg(pg_dump_bin, ["--format=custom", "--no-owner", "--no-privileges", *(["--snapshot", pg_snapshot] if pg_snapshot else []), "--file", str(snap), *conn], env, "pg_dump_failed")
                db_counts = counts
                writer.put(PG_FILE, snap)
                db_file = PG_FILE
            revision = schema_revision(source.database_url)
            # 2) private documents
            for p in doc_files:
                writer.put(f"{DOCS_DIR}/{p.relative_to(docs_dir).as_posix()}", p)
            # 3) governed knowledge (02A set) staged in a work directory, then written like every other component
            sf, kdocs, store, kengine = _knowledge_handles(source)
            engines.append(kengine)
            kdir = work / "k"
            krep = create_knowledge_backup(sf, kdocs, store, out_dir=kdir, chroma_dir=source.knowledge_index_dir if source.knowledge_index_dir and Path(source.knowledge_index_dir).is_dir() else None,
                                           identity=source.identity, execute=True, allow_active_jobs=allow_active_jobs, clock=clock)
            if not krep.ok:
                rep.ok, rep.codes = False, rep.codes + ["knowledge_backup_failed"] + krep.codes
                return rep
            rep.codes += [c for c in krep.codes if c not in rep.codes]
            for p in sorted(kdir.rglob("*")):
                if p.is_file():
                    writer.put(f"{KNOWLEDGE_DIR}/{p.relative_to(kdir).as_posix()}", p)
            kman = json.loads((kdir / "manifest.json").read_text(encoding="utf-8"))
            probe = {"run": False, "reason": "no_index"}
            if store is not None:
                try:
                    probe = retrieval_probe(store)
                except Exception:  # noqa: BLE001 - an incompatible or non-local index: recorded as NOT RUN, never faked
                    probe = {"run": False, "reason": "probe_failed"}
            if private_probe:
                probe_file = work / "retrieval-probe.json"
                probe_file.write_text(json.dumps(probe))
                writer.put("evidence/retrieval-probe.json", probe_file)
                probe = {"run": probe.get("run", False), "protected_file": "evidence/retrieval-probe.json"}
            after_jobs = active_jobs(source.database_url)
        except SetError as e:
            rep.ok, rep.codes = False, rep.codes + [e.code]
            return rep
        except crypto.CryptoError as e:
            rep.ok, rep.codes = False, rep.codes + [e.code]
            return rep
        finally:
            for e in engines:
                e.dispose()
    after = (_tree_fingerprint(docs_dir), _tree_fingerprint(source.knowledge_files_dir), _tree_fingerprint(source.knowledge_index_dir, mtimes=False))
    if after != before:
        rep.ok, rep.codes = False, rep.codes + ["source_changed_during_backup"]
        return rep                                              # no manifest: this directory can never be restored
    if after_jobs and not allow_active_jobs:
        rep.ok, rep.codes = False, rep.codes + ["jobs_started_during_backup"]
        return rep
    mode = "aes-256-gcm-chunked" if encryption_key else ("storage_attested" if storage_encrypted_attested else "none")
    manifest = {
        "format": SET_FORMAT, "tool": TOOL, "set_id": set_id, "created_at": created.isoformat(),
        "encryption": {"mode": mode, "key_fingerprint": crypto.fingerprint(encryption_key) if encryption_key else None,
                       "note": "attested, NOT verified by this tool" if mode == "storage_attested" else None},
        "consistency": {"jobs_active_at_start": pending, "jobs_active_at_end": after_jobs, "source_unchanged_during_copy": True, "consistent": not pending and not after_jobs,
                        "method": "sqlite online backup + file fingerprint before and after" if dialect == "sqlite" else "pg_dump snapshot + file fingerprint before and after"},
        "database": {"dialect": dialect, "file": db_file, "schema_revision": revision, "tables": len(db_counts), "row_counts": db_counts},
        "documents": {"count": len(doc_files), "bytes": sum(v["size"] for k, v in writer.files.items() if k.startswith(DOCS_DIR + "/")), "symlinks_skipped": skipped_links},
        "knowledge": {"counts": kman["counts"], "chunks": kman["counts"].get("chunks", 0), "index_checksum": (kman.get("index_manifest") or {}).get("checksum"),
                      "embedder": ((kman.get("source_identity") or {}).get("embedding")), "manifest_sha256": writer.files[f"{KNOWLEDGE_DIR}/manifest.json"]["sha256"],
                      "consistent": kman.get("consistent", False)},
        "retrieval_probe": probe,
        "files": writer.files,
    }
    if extra_manifest:
        manifest.update({k: v for k, v in extra_manifest.items() if k not in manifest})
    if before_publish is not None:
        before_publish(manifest)
    key = signing_key or (crypto.derive_signing_key(encryption_key) if encryption_key else None)
    if key is not None:
        manifest["signature"] = sign(manifest, key)
    (out / MANIFEST).write_text(json.dumps(manifest, sort_keys=True, indent=1), encoding="utf-8")
    rep.counts |= {"files": len(writer.files), "chunks": manifest["knowledge"]["chunks"]}
    rep.details = {"set_id": set_id, "encryption": mode, "signed": key is not None, "consistent": manifest["consistency"]["consistent"],
                   "schema_revision": revision, "index_checksum": (manifest["knowledge"]["index_checksum"] or "")[:16] or None,
                   "manifest_sha256": manifest_digest(out)}
    return rep


# ===================================================================== verify
def load_manifest(set_dir: str | Path) -> dict:
    p = Path(set_dir) / MANIFEST
    if p.is_symlink() or not p.is_file():
        raise SetError("set_manifest_missing")
    try:
        m = json.loads(p.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        raise SetError("set_manifest_invalid") from None
    if not isinstance(m, dict) or m.get("format") != SET_FORMAT or not isinstance(m.get("files"), dict) or not isinstance(m.get("set_id"), str):
        raise SetError("set_format_unsupported")
    return m


def verify_set(set_dir: str | Path, *, encryption_key: bytes | None = None, signing_key: bytes | None = None, require_signature: bool = False,
               require_encryption: bool = False) -> Report:
    """Read-only. Checks the manifest, its signature, every file (stored checksum always; plaintext checksum when the key is available), unlisted files,
    symlinks and manifest paths. Never writes."""
    base = Path(set_dir)
    rep = Report("verify_set", False)
    try:
        m = load_manifest(base)
    except SetError as e:
        rep.ok, rep.codes = False, [e.code]
        return rep
    problems: list[str] = []
    mode = (m.get("encryption") or {}).get("mode")
    sig = m.get("signature")
    key = signing_key or (crypto.derive_signing_key(encryption_key) if encryption_key else None)
    if sig:
        if key is None:
            rep.codes.append("signature_not_checked_no_key")
            if require_signature:
                problems.append("signature_not_checked_no_key")
        elif sig.get("key_fingerprint") != crypto.fingerprint(key):
            problems.append("manifest_signature_key_mismatch")
        elif not hmac.compare_digest(str(sig.get("value")), sign(m, key)["value"]):
            problems.append("manifest_tampered")
    elif require_signature:
        problems.append("manifest_unsigned")
    if require_encryption and mode not in ("aes-256-gcm-chunked", "storage_attested"):
        problems.append("set_not_encrypted")
    if mode == "aes-256-gcm-chunked" and encryption_key is not None and (m["encryption"].get("key_fingerprint") != crypto.fingerprint(encryption_key)):
        problems.append("encryption_key_mismatch")
    elif mode == "aes-256-gcm-chunked" and encryption_key is None:
        rep.codes.append("plaintext_not_verified_no_key")
    listed = set()
    bad = unsafe = missing = plain_bad = 0
    for logical, e in sorted(m["files"].items()):
        stored = e.get("stored") if isinstance(e, dict) else None
        if not safe_rel(logical) or not isinstance(stored, str) or not safe_rel(stored):
            unsafe += 1
            continue
        listed.add(stored)
        p = base / stored
        if p.is_symlink():
            problems.append("symlink_in_set")
            continue
        if not p.is_file():
            missing += 1
            continue
        if sha_file(p) != e.get("stored_sha256"):
            bad += 1
            continue
        if e.get("sealed") and encryption_key is not None and "encryption_key_mismatch" not in problems:
            try:
                if crypto.sealed_sha256(p, encryption_key, set_id=m["set_id"], logical=logical) != e.get("sha256"):
                    plain_bad += 1
            except crypto.CryptoError:
                plain_bad += 1
        elif not e.get("sealed") and sha_file(p) != e.get("sha256"):
            bad += 1
    unlisted = 0
    for p in sorted(base.rglob("*")):
        if p.is_symlink():
            problems.append("symlink_in_set")
        elif p.is_file() and p.relative_to(base).as_posix() not in listed and p.name != MANIFEST:
            unlisted += 1
    if unsafe:
        problems.append("unsafe_path_in_manifest")
    if missing:
        problems.append("file_missing")
    if bad:
        problems.append("file_checksum_mismatch")
    if plain_bad:
        problems.append("sealed_file_invalid")
    if unlisted:
        problems.append("unlisted_file")
    rep.counts = {"files_checked": len(m["files"]), "files_missing": missing, "files_modified": bad + plain_bad, "files_unlisted": unlisted, "paths_unsafe": unsafe}
    rep.details = {"set_id": m["set_id"], "created_at": m.get("created_at"), "encryption": mode, "signed": bool(sig), "consistent": (m.get("consistency") or {}).get("consistent"),
                   "manifest_sha256": manifest_digest(base)}
    if problems:
        rep.ok = False
        rep.codes = sorted(set(problems)) + rep.codes
    return rep


# ===================================================================== restore
def _materialise(base: Path, manifest: dict, logical: str, dst: Path, key: bytes | None) -> None:
    e = manifest["files"][logical]
    src = base / e["stored"]
    if e.get("sealed"):
        if key is None:
            raise SetError("encryption_key_missing")
        plain, _ = crypto.unseal_to(src, dst, key, set_id=manifest["set_id"], logical=logical)
    else:
        dst.parent.mkdir(parents=True, exist_ok=True)
        with open(src, "rb") as fin, open(dst, "xb") as fout:
            shutil.copyfileobj(fin, fout, 1 << 20)
        plain = sha_file(dst)
    if plain != e["sha256"]:
        raise SetError("restored_file_checksum_mismatch")


def restore_layout(target_root: Path) -> dict[str, Path]:
    return {"database": target_root / DB_DIR / "restored.db", "documents": target_root / DOCS_DIR, "knowledge_files": target_root / KNOWLEDGE_DIR / "private",
            "knowledge_index": target_root / KNOWLEDGE_DIR / "chroma"}


def _pg_target_problems(url: str) -> list[str]:
    u = make_url(url)
    if u.get_backend_name() not in ("postgresql", "postgres"):
        return ["postgresql_required"]
    name = (u.database or "").lower()
    if not any(m in name for m in RESTORE_DB_NAME_MARKERS):
        return ["target_database_name_refused"]                  # the name must say restore, staging or drill: a guard against clobbering production
    eng = _engine(url)
    try:
        with eng.connect() as c:
            if inspect(c).get_table_names() or c.execute(text("SELECT count(*) FROM pg_class r JOIN pg_namespace n ON n.oid=r.relnamespace WHERE n.nspname NOT LIKE 'pg_%' AND n.nspname != 'information_schema'")).scalar() or c.execute(text("SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname NOT LIKE 'pg_%' AND n.nspname != 'information_schema'")).scalar():
                return ["target_database_not_empty"]
    except Exception:  # noqa: BLE001
        return ["target_database_unreachable"]
    finally:
        eng.dispose()
    return []


def restore_set(set_dir: str | Path, *, target_root: str | Path, execute: bool = False, encryption_key: bytes | None = None, signing_key: bytes | None = None,
                require_signature: bool = False, recovery_token: str | None = None, target_database_url: str | None = None, pg_restore_bin: str = "pg_restore", fallback_user_id: int | None = None) -> Report:
    """Restore into a SEPARATE environment under ``target_root`` (a new or empty directory; nothing is overwritten): ``database/restored.db`` (or the named
    PostgreSQL database), ``documents/``, ``knowledge/private`` and ``knowledge/chroma``. Dry-run by default: verifies the set and plans, writes nothing."""
    base, root = Path(set_dir), Path(target_root)
    rep = Report("restore_set", execute)
    v = verify_set(base, encryption_key=encryption_key, signing_key=signing_key, require_signature=require_signature)
    if not v.ok:
        rep.ok, rep.codes = False, ["backup_integrity_failed"] + v.codes
        return rep
    m = load_manifest(base)
    rep.counts = {"files": len(m["files"]), "tables": m["database"]["tables"], "document_files": m["documents"]["count"], "chunks": m["knowledge"]["chunks"]}
    sealed = (m.get("encryption") or {}).get("mode") == "aes-256-gcm-chunked"
    if sealed and encryption_key is None:
        rep.ok, rep.codes = False, ["encryption_key_missing"]
        return rep
    leased = recovery_token and root.is_dir() and {p.name for p in root.iterdir()} == {"RECOVERY_PENDING.json"} and json.loads((root / "RECOVERY_PENDING.json").read_text()).get("token") == recovery_token
    if _dir_nonempty(root) and not leased:
        rep.ok, rep.codes = False, ["target_not_empty"]
        return rep
    dialect = m["database"]["dialect"]
    if dialect == "postgresql":
        if not target_database_url:
            rep.ok, rep.codes = False, ["target_database_url_required"]
            return rep
        problems = _pg_target_problems(target_database_url)
        if problems:
            rep.ok, rep.codes = False, problems
            return rep
    elif target_database_url:
        rep.ok, rep.codes = False, ["target_database_url_not_applicable"]
        return rep
    if not execute:
        return rep

    lay = restore_layout(root)
    try:
        with tempfile.TemporaryDirectory(prefix="a4mr-") as work_s:
            work = Path(work_s)
            root.mkdir(parents=True, exist_ok=True)
            # database
            if dialect == "sqlite":
                _materialise(base, m, m["database"]["file"], lay["database"], encryption_key)
                db_url = f"sqlite:///{lay['database']}"
            else:
                dump = work / "app.pgdump"
                _materialise(base, m, m["database"]["file"], dump, encryption_key)
                env, conn = _pg_env_and_args(target_database_url)
                _run_pg(pg_restore_bin, ["--no-owner", "--no-privileges", "--exit-on-error", "--single-transaction", *conn, str(dump)], env, "pg_restore_failed")
                db_url = target_database_url
            # documents
            lay["documents"].mkdir(parents=True, exist_ok=True)
            for logical in sorted(k for k in m["files"] if k.startswith(DOCS_DIR + "/")):
                _materialise(base, m, logical, root / logical, encryption_key)
            # knowledge: decrypt the 02A set into the work directory, then let the 02A restore place registry rows (already in the database), files and the index
            kdir = work / "k"
            for logical in sorted(k for k in m["files"] if k.startswith(KNOWLEDGE_DIR + "/")):
                _materialise(base, m, logical, kdir / logical[len(KNOWLEDGE_DIR) + 1:], encryption_key)
            eng = _engine(db_url)
            try:
                from src.copilot.embeddings import LocalHashEmbedder
                from src.copilot.vectorstore import ChromaStore
                from src.persistence import make_session_factory

                sf = make_session_factory(eng)
                krep = restore_knowledge_backup(kdir, session_factory=sf, files_dir=lay["knowledge_files"], index_dir=lay["knowledge_index"], execute=True, allow_non_empty=True,
                                                fallback_user_id=fallback_user_id,
                                                open_store=lambda: ChromaStore(LocalHashEmbedder(), persist_dir=str(lay["knowledge_index"]), collection_name=KP.COLLECTION))
                rep.codes += [c for c in krep.codes if c not in ("non_empty_target_allowed",) and c not in rep.codes]
                if not krep.ok:
                    rep.ok = False
                    rep.codes.insert(0, "knowledge_restore_failed")
                rep.details = {"knowledge": krep.details}
            finally:
                eng.dispose()
    except SetError as e:
        rep.ok, rep.codes = False, rep.codes + [e.code]
        return rep
    except crypto.CryptoError as e:
        rep.ok, rep.codes = False, rep.codes + [e.code]
        return rep
    # post-restore verification of the TARGET
    problems = verify_restored_environment(m, db_url, root)
    if problems:
        rep.ok = False
        rep.codes = sorted(set(problems)) + [c for c in rep.codes if c not in problems]
    rep.details |= {"restored_tables": m["database"]["tables"], "schema_revision": m["database"]["schema_revision"]}
    return rep


def verify_restored_environment(manifest: dict, db_url: str, root: Path) -> list[str]:
    """Row count of EVERY table, the schema revision, every document file checksum. (The knowledge files and the index checksum are verified by the 02A restore.)"""
    problems: list[str] = []
    try:
        counts = table_counts(db_url)
    except Exception:  # noqa: BLE001
        return ["restored_database_unreadable"]
    want = manifest["database"]["row_counts"]
    for t, n in want.items():
        if counts.get(t) != n:
            problems.append("row_count_mismatch")
            break
    if schema_revision(db_url) != manifest["database"]["schema_revision"]:
        problems.append("schema_revision_mismatch")
    for logical, e in manifest["files"].items():
        if logical.startswith(DOCS_DIR + "/"):
            p = root / logical
            if not p.is_file() or sha_file(p) != e["sha256"]:
                problems.append("document_checksum_mismatch")
                break
    return problems


def row_count_diff(manifest: dict, db_url: str) -> dict[str, tuple[int, int | None]]:
    counts = table_counts(db_url)
    return {t: (n, counts.get(t)) for t, n in manifest["database"]["row_counts"].items() if counts.get(t) != n}


__all__ = ["Source", "SetError", "create_set", "verify_set", "restore_set", "load_manifest", "encryption_required", "retrieval_probe", "restore_layout",
           "verify_restored_environment", "table_counts", "collection_checksum", "sha_file", "manifest_digest", "safe_rel"]
