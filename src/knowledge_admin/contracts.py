"""Knowledge runtime, index manifest and scanner CONTRACT (package 02K; interface only, NO behaviour change).

Consumers: 02A (persistence/recovery), 02B (embedding integrity), 02C (malware scanning). The conformance suite is
``tests/contracts/test_knowledge_contract_02k.py``; consumers must keep it green. Requirement IDs: REQ-OWN-05 K3/K4,
REVIEW-04 R1/R4/R5 (contract part).

PUBLIC SURFACE (stable; additive changes only, bump ``SCHEMA_VERSION`` on a breaking change):
* ``SCHEMA_VERSION``
* Runtime identity: ``RuntimeIdentity``, ``DatabaseIdentity``, ``DataRootIdentity``, ``CollectionInfo``, ``EmbeddingState``,
  ``WorkerHeartbeatSummary``, ``build_runtime_identity``, ``database_fingerprint``, ``data_root_identity``,
  ``identities_compatible`` -> ``CompatibilityReport`` / ``Mismatch``.
* Index manifest: ``EmbedderIdentity``, ``IndexManifestV2``, ``compute_compatibility_hash``, ``embedder_matches`` ->
  ``EmbedderMatch``, ``parse_build_metadata``, ``parse_index_record``.
* Scanner: ``ScanVerdict``, ``ScanOutcome``, ``ScannerProtocol``, ``LegacyScannerAdapter``, ``scan_accepted`` (fail-closed rule).

INVARIANTS
1. Everything is frozen and JSON-serialisable (``to_dict`` / ``from_dict``, ``json.dumps(sort_keys=True)`` stable).
2. NO secret ever appears: no database URL, password, host credential, API key, absolute path or vector. The database is identified by
   its kind plus a SHA-256 fingerprint of ``kind://host:port/name`` (userinfo, query and driver removed); the data root by a fixed label
   plus a short hash.
3. Unknown stays unknown: a missing legacy field is ``None``; the compatibility hash is ``None`` unless all four inputs are known.
4. A mismatch is DATA (a typed report), never an exception. Unknown values are never treated as a match.
5. Nothing here writes, opens a network connection or calls a provider. Builders only read objects the caller already holds.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field, fields
from enum import Enum
from typing import Any, Mapping, Protocol, runtime_checkable
from urllib.parse import urlsplit

SCHEMA_VERSION = 1


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _pick(cls, d: Mapping[str, Any]) -> dict:
    names = {f.name for f in fields(cls)}
    return {k: v for k, v in d.items() if k in names}


# ===================================================================== runtime identity
@dataclass(frozen=True)
class DatabaseIdentity:
    kind: str | None              # "postgresql" | "sqlite" | ... (driver suffix removed)
    fingerprint: str | None       # sha256 hex of the credential-free URL; never reversible to the URL

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class DataRootIdentity:
    label: str                    # fixed, non-secret label
    short_hash: str | None        # first 12 hex of sha256(absolute path); the path itself is never stored

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class CollectionInfo:
    collection_id: str
    chunk_count: int | None = None    # None => store unreadable / unknown

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class EmbeddingState:
    provider: str | None = None
    model: str | None = None
    dimensions: int | None = None
    degraded: bool = False
    degradation_reason: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class WorkerHeartbeatSummary:
    status: str = "unknown"           # available | stale | none | unknown
    seen_recently: int = 0
    last_seen_at: str | None = None
    stale_after_seconds: int | None = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class RuntimeIdentity:
    database: DatabaseIdentity
    data_root: DataRootIdentity
    collections: tuple[CollectionInfo, ...] = ()
    embedding: EmbeddingState = field(default_factory=EmbeddingState)
    worker: WorkerHeartbeatSummary = field(default_factory=WorkerHeartbeatSummary)
    schema_version: int = SCHEMA_VERSION

    def to_dict(self) -> dict:
        return {"schema_version": self.schema_version, "database": self.database.to_dict(), "data_root": self.data_root.to_dict(),
                "collections": [c.to_dict() for c in self.collections], "embedding": self.embedding.to_dict(),
                "worker": self.worker.to_dict()}

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> "RuntimeIdentity":
        db, root = d.get("database") or {}, d.get("data_root") or {}
        return cls(
            database=DatabaseIdentity(db.get("kind"), db.get("fingerprint")),
            data_root=DataRootIdentity(root.get("label") or "knowledge-data-root", root.get("short_hash")),
            collections=tuple(CollectionInfo(c["collection_id"], c.get("chunk_count")) for c in d.get("collections") or ()),
            embedding=EmbeddingState(**_pick(EmbeddingState, d.get("embedding") or {})),
            worker=WorkerHeartbeatSummary(**_pick(WorkerHeartbeatSummary, d.get("worker") or {})),
            schema_version=int(d.get("schema_version", SCHEMA_VERSION)))


def database_fingerprint(database_url: str | None) -> DatabaseIdentity:
    """Kind plus fingerprint of ``kind://host:port/name``. Credentials, query string and driver suffix never influence the result."""
    if not database_url or not str(database_url).strip():
        return DatabaseIdentity(None, None)
    try:
        parts = urlsplit(str(database_url).strip())
        kind = (parts.scheme or "").split("+", 1)[0].lower() or None
        host = (parts.hostname or "").lower()           # hostname excludes userinfo
        try:
            port = parts.port
        except ValueError:
            port = None
        canonical = f"{kind}://{host}:{port or ''}{parts.path}"
    except Exception:  # noqa: BLE001 - an unparsable URL is unknown, and is never echoed
        return DatabaseIdentity(None, None)
    return DatabaseIdentity(kind, _sha(canonical))


def data_root_identity(absolute_path: str | None, label: str = "knowledge-data-root") -> DataRootIdentity:
    return DataRootIdentity(label, _sha(str(absolute_path))[:12] if absolute_path else None)


def _embedding_state(config: Any) -> EmbeddingState:
    from src.copilot import constants
    from src.copilot.embeddings import embedding_status
    st = embedding_status(config)
    resolved, configured = st.get("provider"), st.get("configured_provider")
    dims = constants.OPENAI_EMBEDDING_DIMENSIONS if resolved == "openai" else constants.LOCAL_EMBEDDING_DIMENSIONS
    degraded = resolved == "local" and configured != "local"
    return EmbeddingState(resolved, st.get("model"), dims, degraded, "fallback_to_local_embedder" if degraded else None)


def _worker_summary(job_stats: Any) -> WorkerHeartbeatSummary:
    try:
        stats = job_stats() if callable(job_stats) else job_stats
        w = (stats or {}).get("workers") or {}
        seen = int(w.get("seen_recently", 0))
        status = "available" if seen > 0 else ("stale" if w.get("items") else "none")
        return WorkerHeartbeatSummary(status, seen, w.get("last_seen_at"), w.get("stale_after_seconds"))
    except Exception:  # noqa: BLE001
        return WorkerHeartbeatSummary()


def _collections(stores: Mapping[str, Any] | None) -> tuple[CollectionInfo, ...]:
    out = []
    for cid, store in sorted((stores or {}).items()):
        try:
            n: int | None = int(store.count())
        except Exception:  # noqa: BLE001
            n = None
        out.append(CollectionInfo(str(cid), n))
    return tuple(out)


def build_runtime_identity(config: Any, session_factory: Any = None, *, stores: Mapping[str, Any] | None = None,
                           job_stats: Any = None, data_root: str | None = None) -> RuntimeIdentity:
    """Compose the identity from EXISTING sources only (read-only). ``config`` is the app config (``database_url``) and/or a
    CopilotConfig-like object (embedding fields); either may be partial. ``session_factory`` is accepted for signature stability
    (02A) and is deliberately not used to query anything here. ``stores`` maps collection id -> vector store (``count()``),
    ``job_stats`` is the ``JobService.stats()`` dict or a callable returning it."""
    from src.copilot import constants
    try:
        emb = _embedding_state(config) if hasattr(config, "embedding_provider") else EmbeddingState()
    except Exception:  # noqa: BLE001
        emb = EmbeddingState()
    return RuntimeIdentity(database=database_fingerprint(getattr(config, "database_url", None)),
                           data_root=data_root_identity(data_root or constants.data_path()),
                           collections=_collections(stores), embedding=emb, worker=_worker_summary(job_stats))


@dataclass(frozen=True)
class Mismatch:
    field: str
    api: Any
    worker: Any

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class CompatibilityReport:
    compatible: bool
    mismatches: tuple[Mismatch, ...] = ()
    schema_version: int = SCHEMA_VERSION

    def to_dict(self) -> dict:
        return {"schema_version": self.schema_version, "compatible": self.compatible, "mismatches": [m.to_dict() for m in self.mismatches]}


def identities_compatible(a: RuntimeIdentity, b: RuntimeIdentity) -> CompatibilityReport:
    """Compare API (``a``) with worker (``b``). Pure; never raises for a mismatch. Unknown on either side is a mismatch (not provable).
    Chunk counts and heartbeats are time-varying and deliberately NOT compared."""
    must_be_known = {"database.kind", "database.fingerprint", "data_root.short_hash", "embedding.provider", "embedding.model",
                     "embedding.dimensions"}
    pairs = [("schema_version", a.schema_version, b.schema_version),
             ("database.kind", a.database.kind, b.database.kind),
             ("database.fingerprint", a.database.fingerprint, b.database.fingerprint),
             ("data_root.short_hash", a.data_root.short_hash, b.data_root.short_hash),
             ("collections", sorted(c.collection_id for c in a.collections), sorted(c.collection_id for c in b.collections)),
             ("embedding.provider", a.embedding.provider, b.embedding.provider),
             ("embedding.model", a.embedding.model, b.embedding.model),
             ("embedding.dimensions", a.embedding.dimensions, b.embedding.dimensions)]
    bad = [Mismatch(n, x, y) for n, x, y in pairs if x != y or (x is None and n in must_be_known)]
    return CompatibilityReport(not bad, tuple(bad))


# ===================================================================== index manifest v2
def compute_compatibility_hash(provider: str | None, model: str | None, version: str | None, dimensions: int | None) -> str | None:
    """Deterministic hash of (provider, model, version, dimensions); ``None`` if any input is unknown (never invented)."""
    if provider is None or model is None or version is None or dimensions is None:
        return None
    return _sha(json.dumps([str(provider), str(model), str(version), int(dimensions)], separators=(",", ":")))


@dataclass(frozen=True)
class EmbedderIdentity:
    provider: str | None = None
    model: str | None = None
    version: str | None = None
    dimensions: int | None = None

    def compatibility_hash(self) -> str | None:
        return compute_compatibility_hash(self.provider, self.model, self.version, self.dimensions)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class IndexManifestV2:
    provider: str | None = None
    model: str | None = None
    version: str | None = None
    dimensions: int | None = None
    vector_metric: str | None = None           # cosine | l2 | ip
    collection_id: str | None = None
    checksum: str | None = None                # over the collection content (per collection)
    source_checksums: tuple[tuple[str, str], ...] = ()   # (source version id, checksum) pairs, sorted
    built_at: str | None = None
    source_version_ids: tuple[str, ...] = ()
    compatibility_hash: str | None = None
    degraded: bool = False
    degradation_reason: str | None = None
    embedder_label: str | None = None          # legacy free label (e.g. class name) kept when provider is unknown
    schema_version: int = SCHEMA_VERSION

    @classmethod
    def create(cls, **kw: Any) -> "IndexManifestV2":
        """Builds a manifest with the compatibility hash computed (callers cannot supply an inconsistent one)."""
        kw.pop("compatibility_hash", None)
        kw["source_checksums"] = tuple(sorted(tuple(x) for x in kw.get("source_checksums", ())))
        kw["source_version_ids"] = tuple(kw.get("source_version_ids", ()))
        return cls(compatibility_hash=compute_compatibility_hash(kw.get("provider"), kw.get("model"), kw.get("version"),
                                                                 kw.get("dimensions")), **kw)

    @property
    def embedder(self) -> EmbedderIdentity:
        return EmbedderIdentity(self.provider, self.model, self.version, self.dimensions)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["source_checksums"] = [list(x) for x in self.source_checksums]
        d["source_version_ids"] = list(self.source_version_ids)
        return d

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> "IndexManifestV2":
        kw = _pick(cls, d)
        kw["source_checksums"] = tuple(tuple(x) for x in kw.get("source_checksums") or ())
        kw["source_version_ids"] = tuple(kw.get("source_version_ids") or ())
        kw["schema_version"] = int(kw.get("schema_version", SCHEMA_VERSION))
        return cls.create(**kw)       # the hash is always recomputed, never trusted from storage


@dataclass(frozen=True)
class EmbedderMatch:
    compatible: bool
    mismatched_fields: tuple[str, ...] = ()
    unknown_fields: tuple[str, ...] = ()
    manifest_degraded: bool = False
    schema_version: int = SCHEMA_VERSION

    def to_dict(self) -> dict:
        return {"schema_version": self.schema_version, "compatible": self.compatible, "mismatched_fields": list(self.mismatched_fields),
                "unknown_fields": list(self.unknown_fields), "manifest_degraded": self.manifest_degraded}


def embedder_matches(manifest: IndexManifestV2, embedder: EmbedderIdentity) -> EmbedderMatch:
    """Does the live embedder produce vectors compatible with the manifest? Unknown on either side => not compatible (never assumed)."""
    mism: list[str] = []
    unk: list[str] = []
    for name in ("provider", "model", "version", "dimensions"):
        m, e = getattr(manifest, name), getattr(embedder, name)
        if m is None or e is None:
            unk.append(name)
        elif m != e:
            mism.append(name)
    return EmbedderMatch(not mism and not unk, tuple(mism), tuple(unk), manifest.degraded)


def _s(v: Any) -> str | None:
    return None if v is None or v == "" else str(v)


def _i(v: Any) -> int | None:
    try:
        return None if v is None or isinstance(v, bool) else int(v)
    except (TypeError, ValueError):
        return None


def parse_build_metadata(meta: Mapping[str, Any] | None) -> IndexManifestV2:
    """Reads the EXISTING ``data/knowledge/build_metadata.json`` shape (``runtime_pipeline_version``, ``built_at``, ``source_versions``,
    optional ``embedding`` block) without writing anything. Absent fields stay ``None``; nothing is inferred."""
    meta = meta if isinstance(meta, Mapping) else {}
    emb = meta.get("embedding") if isinstance(meta.get("embedding"), Mapping) else {}
    sv = meta.get("source_versions")
    if isinstance(sv, Mapping):
        ids = tuple(sorted(str(k) for k in sv))
    elif isinstance(sv, (list, tuple)):
        ids = tuple(sorted(str(x) for x in sv))
    else:
        ids = ()
    return IndexManifestV2.create(
        provider=_s(emb.get("provider") or meta.get("embedding_provider")), model=_s(emb.get("model") or meta.get("embedding_model")),
        version=_s(emb.get("version") or meta.get("embedding_version")), dimensions=_i(emb.get("dimensions") or meta.get("embedding_dimensions")),
        vector_metric=_s(emb.get("metric") or meta.get("vector_metric")), collection_id=_s(meta.get("collection")),
        checksum=_s(meta.get("checksum")), built_at=_s(meta.get("built_at")), source_version_ids=ids,
        degraded=bool(meta.get("degraded", False)), degradation_reason=_s(meta.get("degradation_reason")))


def parse_index_record(record: Any, version_public_id: str | None = None) -> IndexManifestV2:
    """Reads a governed ``KnowledgeIndexRecord`` (or a dict with the same keys): ``collection``, ``embedder`` (a class-name label),
    ``built_at``. The label is kept as ``embedder_label``; provider/model/dimensions stay unknown (the record never stored them)."""
    g = (lambda k: record.get(k)) if isinstance(record, Mapping) else (lambda k: getattr(record, k, None))
    built = g("built_at")
    return IndexManifestV2.create(
        collection_id=_s(g("collection")), embedder_label=_s(g("embedder")),
        built_at=built.isoformat() if hasattr(built, "isoformat") else _s(built),
        source_version_ids=(version_public_id,) if version_public_id else ())


# ===================================================================== scanner contract
class ScanVerdict(str, Enum):
    CLEAN = "clean"
    INFECTED = "infected"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class ScanOutcome:
    verdict: ScanVerdict
    scanner: str
    real_scan: bool = False       # True only when a REAL scanner ran; a no-op scanner can never claim a clean scan
    detail: str = ""
    schema_version: int = SCHEMA_VERSION

    def to_dict(self) -> dict:
        return {"schema_version": self.schema_version, "verdict": self.verdict.value, "scanner": self.scanner,
                "real_scan": self.real_scan, "detail": self.detail}


@runtime_checkable
class ScannerProtocol(Protocol):
    name: str

    def available(self) -> bool: ...

    def scan(self, data: bytes, filename: str) -> ScanOutcome: ...


class LegacyScannerAdapter:
    """Adapts a ``src.documents.file_security.FileSecurityScanner`` to ``ScannerProtocol``. Does not change the legacy scanner."""

    def __init__(self, legacy: Any) -> None:
        self._legacy = legacy
        self.name = getattr(legacy, "name", "unknown")

    def available(self) -> bool:
        try:
            return bool(self._legacy.available())
        except Exception:  # noqa: BLE001
            return False

    def scan(self, data: bytes, filename: str) -> ScanOutcome:
        from src.documents.file_security import FileScanUnavailable
        if not self.available():
            return ScanOutcome(ScanVerdict.UNAVAILABLE, self.name, False, "scanner_unavailable")
        try:
            r = self._legacy.scan(data, filename)
        except FileScanUnavailable:
            return ScanOutcome(ScanVerdict.UNAVAILABLE, self.name, False, "scanner_unavailable")
        return ScanOutcome(ScanVerdict.CLEAN if r.clean else ScanVerdict.INFECTED, self.name, self.name != "null", str(r.detail or ""))


def scan_accepted(outcome: ScanOutcome, *, required: bool) -> bool:
    """The FAIL-CLOSED rule (mirrors ``enforce_scan``): infected never passes; when scanning is required only a clean verdict from a REAL
    scanner passes; when not required, a non-infected outcome passes only as 'not scanned' (callers never display it as virus-free)."""
    if outcome.verdict is ScanVerdict.INFECTED:
        return False
    if required:
        return outcome.verdict is ScanVerdict.CLEAN and outcome.real_scan
    return True
