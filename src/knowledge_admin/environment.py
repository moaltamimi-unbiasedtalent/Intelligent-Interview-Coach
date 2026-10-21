"""Environment identity, worker identity record, serving guard and safe diagnostics for the knowledge runtime (package 02A, K1 to K4).

Builds on the 02K contract (``RuntimeIdentity``, ``identities_compatible`` types, ``IndexManifestV2``) and adds NO schema: the worker's
identity is recorded through the EXISTING ``job_workers`` heartbeat (its ``worker_id`` carries three short, non-secret fingerprints, see
``worker_id_for``), because the database is the one channel an API and a worker are guaranteed to share. An API pointing at a different
data directory or embedding configuration than the worker that indexes for it is therefore detectable from the API side.

GUARD SEMANTICS (``KnowledgeServingGuard``)
* ``block`` findings: the API's identity differs from a live worker's, the registry records governed sources whose index collection is
  empty or missing, every registered private file is missing, the index is not persistent, or the private files / index sit in a
  temporary directory.
* HOSTED environments (staging, production, or an unrecognised ``API_ENV``) ENFORCE: candidate governed retrieval raises
  ``KnowledgeServingRefused`` (the career service records the channel as degraded instead of returning an empty list) and governed
  uploads are refused with a precise safe reason. Development keeps working and reports the same findings as clearly labelled warnings.
* Nothing returned here contains a URL, credential, absolute path, vector or exception text.
"""

from __future__ import annotations

import hashlib
import re
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable

from sqlalchemy import func, select

from src.knowledge_admin import policy as P
from src.knowledge_admin.config import KnowledgeRuntimeConfig
from src.knowledge_admin.contracts import (
    CompatibilityReport, IndexManifestV2, Mismatch, RuntimeIdentity, build_runtime_identity,
)
from src.persistence import Job, KnowledgeIndexRecord, KnowledgeSource
from src.persistence import KnowledgeSourceVersion as V

ZERO_ROOT, ZERO_DB, ZERO_EMB = "0" * 12, "0" * 8, "0" * 6
_WORKER_ID_RE = re.compile(r"^(?P<rand>[0-9a-f]{6})\.(?P<root>[0-9a-f]{12})\.(?P<db>[0-9a-f]{8})\.(?P<emb>[0-9a-f]{6})$")


# ===================================================================== worker identity record (job_workers heartbeat)
class _IdentityConfig:
    """The 02K builder reads ``database_url`` and the embedding fields from ONE object; this combines the runtime config's database URL
    with the copilot config's embedding fields without copying either."""

    def __init__(self, runtime: KnowledgeRuntimeConfig, copilot_config: Any) -> None:
        self.database_url = runtime.database_url
        self._copilot = copilot_config

    def __getattr__(self, name: str) -> Any:
        if name.startswith("embedding") or name in ("api_key",):
            return getattr(self._copilot, name)
        raise AttributeError(name)


def build_identity(runtime: KnowledgeRuntimeConfig, copilot_config: Any = None, *, stores: dict | None = None,
                   job_stats: Any = None) -> RuntimeIdentity:
    cfg: Any = _IdentityConfig(runtime, copilot_config) if copilot_config is not None else _DbOnly(runtime.database_url)
    return build_runtime_identity(cfg, stores=stores, job_stats=job_stats, data_root=runtime.data_root)


class _DbOnly:
    def __init__(self, url: str) -> None:
        self.database_url = url


def _emb_token(identity: RuntimeIdentity) -> str:
    e = identity.embedding
    if e.provider is None or e.model is None or e.dimensions is None:
        return ZERO_EMB                                   # unknown never matches (compared as unknown below)
    return hashlib.sha256(f"{e.provider}|{e.model}|{e.dimensions}".encode()).hexdigest()[:6]


def worker_id_for(identity: RuntimeIdentity, rand: str | None = None) -> str:
    """``<6 random>.<12 data-root hash>.<8 database fingerprint prefix>.<6 embedding hash>`` (30 chars, fits ``job_workers.worker_id``). Contains
    only the non-secret fingerprints defined by the 02K contract. The random part keeps concurrent workers distinct."""
    return ".".join((rand or uuid.uuid4().hex[:6], identity.data_root.short_hash or ZERO_ROOT,
                     (identity.database.fingerprint or ZERO_DB)[:8], _emb_token(identity)))


@dataclass(frozen=True)
class WorkerToken:
    root: str
    db: str
    emb: str


def parse_worker_id(worker_id: str | None) -> WorkerToken | None:
    m = _WORKER_ID_RE.match(worker_id or "")
    return WorkerToken(m["root"], m["db"], m["emb"]) if m else None


def compare_worker(api: RuntimeIdentity, worker_id: str | None) -> CompatibilityReport | None:
    """None when the worker did not record an identity (a legacy or non-knowledge worker id). Unknown on either side is a mismatch."""
    tok = parse_worker_id(worker_id)
    if tok is None:
        return None
    api_tok = (api.data_root.short_hash or ZERO_ROOT, (api.database.fingerprint or ZERO_DB)[:8], _emb_token(api))
    pairs = [("data_root.short_hash", api_tok[0], tok.root, ZERO_ROOT), ("database.fingerprint", api_tok[1], tok.db, ZERO_DB),
             ("embedding", api_tok[2], tok.emb, ZERO_EMB)]
    bad = [Mismatch(n, a, w) for n, a, w, zero in pairs if a != w or a == zero]
    return CompatibilityReport(not bad, tuple(bad))


# ===================================================================== guard
class KnowledgeServingRefused(Exception):
    """Candidate governed retrieval or a governed upload was refused by the environment guard. ``codes`` are safe finding codes."""

    def __init__(self, codes: list[str]) -> None:
        super().__init__("knowledge environment guard refused: " + ", ".join(codes))
        self.codes = list(codes)


MESSAGES = {
    "identity_mismatch": "The API and a live worker are configured with different knowledge environments (data root, database or embedding settings).",
    "governed_collection_empty": "The registry records governed sources with built indexes, but the governed collection is empty or missing in the store.",
    "governed_collection_short": "The governed collection holds fewer chunks than the registry records as built.",
    "private_files_missing": "The registry records private source files that are missing from the private file store.",
    "private_files_all_missing": "Every private source file recorded in the registry is missing from the private file store (volume not mounted or wrong directory).",
    "store_not_persistent": "The governed index is not persistent, so a separate worker's indexing is invisible to the API.",
    "store_unreadable": "The governed index could not be read.",
    "private_files_in_temp_directory": "Private source files are configured inside a temporary directory and will be lost.",
    "index_in_temp_directory": "The persistent index is inside a temporary directory and will be lost.",
    "data_root_in_temp_directory": "The data root is inside a temporary directory and will be lost.",
    "database_is_sqlite": "The registry database is SQLite (acceptable for development, not for a hosted deployment).",
    "worker_identity_unrecorded": "A worker is running but has not recorded a knowledge environment identity.",
    "worker_not_seen": "No worker has reported recently, so the worker's environment cannot be compared.",
    "registry_unreadable": "The governed registry could not be read.",
}
_BLOCKING = frozenset({"identity_mismatch", "governed_collection_empty", "private_files_all_missing", "store_not_persistent", "store_unreadable",
                       "private_files_in_temp_directory", "index_in_temp_directory", "data_root_in_temp_directory", "registry_unreadable"})


@dataclass(frozen=True)
class Finding:
    code: str
    severity: str                       # "block" (refuses when enforced) | "warn"
    message: str
    fields: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return {"code": self.code, "severity": self.severity, "message": self.message, "fields": list(self.fields)}


@dataclass(frozen=True)
class GuardReport:
    environment: str
    enforced: bool
    findings: tuple[Finding, ...] = ()
    checked_at: str = ""
    worker_identity: str = "unknown"             # match | mismatch | unrecorded | no_worker | unknown
    mismatched_fields: tuple[str, ...] = ()
    workers_checked: int = 0

    @property
    def blocking(self) -> tuple[Finding, ...]:
        return tuple(f for f in self.findings if f.severity == "block")

    @property
    def serving_allowed(self) -> bool:
        return (not self.enforced) or not self.blocking

    def to_dict(self) -> dict:
        return {"environment": self.environment, "enforced": self.enforced,
                "mode": "enforced" if self.enforced else "development_warning", "serving_allowed": self.serving_allowed,
                "checked_at": self.checked_at, "findings": [f.to_dict() for f in self.findings]}


def _finding(code: str, fields: tuple[str, ...] = ()) -> Finding:
    return Finding(code, "block" if code in _BLOCKING else "warn", MESSAGES[code], fields)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class KnowledgeServingGuard:
    """Evaluates the environment against the registry. Read-only, bounded, cached for ``ttl`` seconds (0 disables the cache)."""

    def __init__(self, session_factory: Any, runtime: KnowledgeRuntimeConfig, *, store_provider: Callable[[], Any],
                 doc_store: Any = None, job_service: Any = None, copilot_config: Any = None, ttl_seconds: float = 15.0,
                 clock: Callable[[], float] = time.monotonic, on_report: Callable[[GuardReport], None] | None = None) -> None:
        self._sf, self._rt, self._store, self._docs = session_factory, runtime, store_provider, doc_store
        self._jobs, self._cc, self._ttl, self._clock = job_service, copilot_config, ttl_seconds, clock
        self._on_report = on_report
        self._cached: tuple[float, GuardReport] | None = None
        self._lock = threading.Lock()

    @property
    def runtime(self) -> KnowledgeRuntimeConfig:
        return self._rt

    # ------------------------------------------------------------ pieces
    def _store_or_none(self) -> Any:
        try:
            return self._store()
        except Exception:  # noqa: BLE001
            return None

    def _workers(self) -> list[dict]:
        try:
            return list(self._jobs.stats()["workers"]["items"]) if self._jobs is not None else []
        except Exception:  # noqa: BLE001
            return []

    def api_identity(self, store: Any = None) -> RuntimeIdentity:
        stores = {self._rt.governed_collection: store} if store is not None else {}
        try:
            stats = self._jobs.stats if self._jobs is not None else None
        except Exception:  # noqa: BLE001
            stats = None
        return build_identity(self._rt, self._cc, stores=stores, job_stats=stats)

    def _registry_facts(self) -> dict | None:
        try:
            with self._sf() as s:
                rows = s.execute(select(V.public_id, V.storage_key, KnowledgeIndexRecord.chunk_count)
                                 .join(KnowledgeIndexRecord, KnowledgeIndexRecord.version_id == V.id)
                                 .where(V.state.in_(("active", "indexed")), KnowledgeIndexRecord.state == "built")).all()
                files = s.execute(select(V.storage_key).where(V.state.in_(("active", "indexed", "approved", "review_required")))).scalars().all()
            return {"built_versions": len(rows), "built_chunks": sum(int(r[2] or 0) for r in rows), "keys": [k for k in files if k]}
        except Exception:  # noqa: BLE001
            return None

    # ------------------------------------------------------------ evaluation
    def evaluate(self) -> GuardReport:
        findings: list[Finding] = []
        enforced = self._rt.hosted
        for code in self._rt.placement_problems():
            if code == "database_is_sqlite" and not enforced:
                continue                                      # SQLite is the normal development database: only a hosted deployment is told
            findings.append(_finding(code))

        store = self._store_or_none()
        facts = self._registry_facts()
        count: int | None = None
        if store is not None:
            try:
                count = int(store.count())
            except Exception:  # noqa: BLE001
                count = None
            if not hasattr(store, "persist_dir"):
                findings.append(_finding("store_not_persistent"))
        if facts is None:
            findings.append(_finding("registry_unreadable"))
        elif facts["built_versions"] > 0:
            if store is None or count is None:
                findings.append(_finding("store_unreadable"))
            elif count == 0:
                findings.append(_finding("governed_collection_empty"))
            elif count < facts["built_chunks"]:
                findings.append(_finding("governed_collection_short"))
        if facts is not None and self._docs is not None and facts["keys"]:
            missing = sum(1 for k in facts["keys"] if not self._safe_exists(k))
            if missing == len(facts["keys"]):
                findings.append(_finding("private_files_all_missing"))
            elif missing:
                findings.append(_finding("private_files_missing"))

        # ---- worker identity (job_workers heartbeat)
        api_id = self.api_identity(store)
        active = [w for w in self._workers() if w.get("active")]
        state, fields_bad = "no_worker" if not active else "unknown", []
        if not active:
            findings.append(_finding("worker_not_seen"))
        else:
            reports = [compare_worker(api_id, w.get("worker_id")) for w in active]
            recorded = [r for r in reports if r is not None]
            if not recorded:
                state = "unrecorded"
                findings.append(_finding("worker_identity_unrecorded"))
            else:
                bad = [r for r in recorded if not r.compatible]
                if bad:
                    state = "mismatch"
                    fields_bad = sorted({m.field for r in bad for m in r.mismatches})
                    findings.append(_finding("identity_mismatch", tuple(fields_bad)))
                else:
                    state = "match"
        report = GuardReport(self._rt.environment, enforced, tuple(findings), _now(), state, tuple(fields_bad), len(active))
        if self._on_report is not None:
            try:
                self._on_report(report)
            except Exception:  # noqa: BLE001 - observation must never change the outcome
                pass
        return report

    def _safe_exists(self, key: str) -> bool:
        try:
            return bool(self._docs.exists(key))
        except Exception:  # noqa: BLE001
            return False

    def check(self, *, fresh: bool = False) -> GuardReport:
        with self._lock:
            now = self._clock()
            if not fresh and self._cached is not None and self._ttl > 0 and now - self._cached[0] < self._ttl:
                return self._cached[1]
        report = self.evaluate()
        with self._lock:
            self._cached = (self._clock(), report)
        return report

    def require_serving(self) -> GuardReport:
        report = self.check()
        if not report.serving_allowed:
            raise KnowledgeServingRefused([f.code for f in report.blocking])
        return report


# ===================================================================== safe diagnostics
def _iso(dt) -> str | None:
    return dt.isoformat() if dt else None


def registry_manifest(session_factory: Any, collection_id: str = P.COLLECTION) -> IndexManifestV2:
    """The governed collection's manifest as DERIVED from the registry (no stored state): per-source checksums are the file checksums of
    every version whose index is built; the collection checksum covers (version id, file checksum, chunk count). Provider, model, version
    and dimensions stay unknown here (02B owns them): a manifest never invents what was not recorded."""
    with session_factory() as s:
        rows = s.execute(select(V.public_id, V.checksum_sha256, KnowledgeIndexRecord.chunk_count, KnowledgeIndexRecord.built_at,
                                KnowledgeIndexRecord.embedder)
                         .join(KnowledgeIndexRecord, KnowledgeIndexRecord.version_id == V.id)
                         .where(KnowledgeIndexRecord.state == "built").order_by(V.public_id)).all()
    if not rows:
        return IndexManifestV2.create(collection_id=collection_id)
    digest = hashlib.sha256("|".join(f"{r[0]}:{r[1]}:{int(r[2] or 0)}" for r in rows).encode()).hexdigest()
    latest = max((r[3] for r in rows if r[3] is not None), default=None)
    labels = {r[4] for r in rows if r[4]}
    return IndexManifestV2.create(collection_id=collection_id, checksum=digest, source_checksums=tuple((r[0], r[1]) for r in rows),
                                  built_at=_iso(latest), source_version_ids=tuple(r[0] for r in rows),
                                  embedder_label=(sorted(labels)[0] if len(labels) == 1 else ("mixed" if labels else None)))


def last_indexing(session_factory: Any) -> dict:
    with session_factory() as s:
        row = s.execute(select(Job.state, Job.finished_at, Job.last_error_category).where(Job.job_type.in_((P.JOB_INDEX, P.JOB_REINDEX)),
                                                                                          Job.state.in_(("succeeded", "failed")))
                        .order_by(Job.finished_at.desc()).limit(1)).first()
        last_ok = s.scalar(select(func.max(V.indexed_at)))
    if row is None:
        return {"result": "none", "at": _iso(last_ok), "failure_category": None}
    return {"result": row[0], "at": _iso(row[1]) or _iso(last_ok), "failure_category": row[2] if row[0] == "failed" else None}


def environment_diagnostics(session_factory: Any, guard: KnowledgeServingGuard, *, governed_store: Any, curated_store: Any,
                            job_service: Any = None) -> dict:
    """The safe ``environment`` block of the Admin readiness response: identity, collections, manifest summary, worker match, last indexing."""
    rt = guard.runtime
    report = guard.check()
    ident = guard.api_identity(governed_store)
    cols = []
    for cid, role, store in ((rt.curated_collection, "curated", curated_store), (rt.governed_collection, "governed", governed_store)):
        count = None
        if store is not None:
            try:
                count = int(store.count())
            except Exception:  # noqa: BLE001
                count = None
        cols.append({"collection_id": cid, "role": role, "chunk_count": count, "persistent": bool(store is not None and hasattr(store, "persist_dir"))})
    manifest = registry_manifest(session_factory, rt.governed_collection)
    m = manifest.to_dict()
    return {
        "environment": rt.environment, "hosted": rt.hosted,
        "database": ident.database.to_dict(), "data_root": ident.data_root.to_dict(),
        "private_files": rt.to_safe_dict()["private_files"],
        "collections": cols,
        "manifest": {"collection_id": m["collection_id"], "checksum": m["checksum"], "source_version_count": len(m["source_version_ids"]),
                     "built_at": m["built_at"], "embedder_label": m["embedder_label"], "compatibility_hash": m["compatibility_hash"],
                     "embedding_fields_known": manifest.compatibility_hash is not None},
        "embedder_identity": ident.embedding.to_dict(),
        "worker_identity": {"status": report.worker_identity, "mismatched_fields": list(report.mismatched_fields),
                            "workers_checked": report.workers_checked},
        "guard": report.to_dict(),
        "last_indexing": last_indexing(session_factory),
    }


def count_registry(session_factory: Any) -> int:
    with session_factory() as s:
        return int(s.scalar(select(func.count()).select_from(KnowledgeSource)) or 0)
