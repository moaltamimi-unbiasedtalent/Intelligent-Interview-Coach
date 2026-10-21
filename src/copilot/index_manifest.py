"""Persisted index manifests and the query-time compatibility rule (package 02B, REVIEW-04 R4/R5; REQ-OWN-05 K4 remainder).

Every vector collection records WHICH embedder built it (provider, model, recorded version, dimensions, compatibility hash, collection checksum,
build time, degradation label) in an ``IndexManifestV2`` (the frozen 02K contract) stored beside the index. A store refuses to QUERY an index
whose manifest is provably incompatible with the live embedder, and refuses to WRITE vectors of a different embedder into it, so vectors from
two embedders can never be mixed and a query can never be scored against an index it was not embedded for.

RULES (``evaluate_index``)
* empty collection: nothing to mismatch (the manifest is created by the first write).
* a KNOWN field that differs (provider, model, version, dimensions): ``mismatch``. Refused in EVERY environment: the vectors are not comparable.
* a field unknown on either side, a missing manifest on a non-empty collection, an unreadable manifest, or an index labelled degraded
  (built by the lexical hash embedder): refused when HOSTED (unknown is never assumed compatible), a labelled warning in development
  (legacy development indexes predate manifests).
* the live embedder is the lexical hash embedder in a hosted environment: refused (``hash_embedder_not_allowed``), whatever the index says.

Refusal is a typed :class:`IndexIncompatibleError` carrying ONLY field names and fixed codes: never a value, path, key or URL. Callers (the
career service, the governed retriever) record the retrieval channel as DEGRADED instead of returning an empty result.

STORAGE: a small JSON sidecar ``<persist_dir>/knowledge-manifests/<collection>.json`` written atomically, so it travels with the index in a
backup or restore (``knowledge_admin.recovery`` copies the whole directory). The in-memory store keeps it on the object. No schema change.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from src.knowledge_admin.contracts import EmbedderIdentity, EmbedderMatch, IndexManifestV2, embedder_matches

MANIFEST_DIR = "knowledge-manifests"
LEXICAL_DEGRADATION = "lexical_hash_embedder"
OK, EMPTY, NO_MANIFEST, MISMATCH, UNKNOWN_FIELDS, UNREADABLE, DEGRADED_INDEX, HASH_HOSTED = (
    "ok", "empty", "no_manifest", "mismatch", "unknown_fields", "manifest_unreadable", "degraded_index", "hash_embedder_not_allowed")

MESSAGES = {
    OK: "The index manifest matches the live embedder.",
    EMPTY: "The collection is empty; its manifest is created by the first build.",
    NO_MANIFEST: "The collection holds vectors but records no index manifest, so the embedder that built it is unknown.",
    MISMATCH: "The index was built by an embedder that differs from the live embedder; its vectors are not comparable.",
    UNKNOWN_FIELDS: "The index manifest or the live embedder does not record every embedding field, so compatibility cannot be proven.",
    UNREADABLE: "The index manifest could not be read.",
    DEGRADED_INDEX: "The index was built by the lexical hash embedder (not semantic) and is not acceptable in a hosted environment.",
    HASH_HOSTED: "The live embedder is the lexical hash embedder, which a hosted environment never accepts.",
}


class IndexIncompatibleError(Exception):
    """The vector index cannot be queried or extended with the live embedder. ``codes`` and ``fields`` are fixed, value-free identifiers."""

    def __init__(self, codes: Iterable[str], fields: Iterable[str] = (), collection: str | None = None) -> None:
        self.codes = list(codes)
        self.fields = tuple(fields)
        self.collection = collection
        super().__init__("vector index incompatible: " + ", ".join(self.codes) + (f" ({', '.join(self.fields)})" if self.fields else ""))


@dataclass(frozen=True)
class IndexStatus:
    collection_id: str | None
    state: str
    refuse: bool
    fields: tuple[str, ...] = ()
    hosted: bool = False
    chunk_count: int | None = None
    manifest: IndexManifestV2 | None = None
    match: EmbedderMatch | None = None
    live: EmbedderIdentity | None = None

    @property
    def compatible(self) -> bool:
        return self.state in (OK, EMPTY)

    @property
    def message(self) -> str:
        return MESSAGES.get(self.state, "")

    def to_safe_dict(self) -> dict:
        """Provider/model/version/dimensions are non-secret identifiers by the 02K contract; no path, URL, key or vector is ever included."""
        m = self.manifest
        return {"collection_id": self.collection_id, "state": self.state, "compatible": self.compatible, "refused": self.refuse,
                "differing_fields": list(self.fields), "chunk_count": self.chunk_count, "message": self.message,
                "manifest": None if m is None else {"provider": m.provider, "model": m.model, "version": m.version, "dimensions": m.dimensions,
                                                      "metric": m.vector_metric, "compatibility_hash": m.compatibility_hash,
                                                      "checksum": m.checksum, "built_at": m.built_at, "degraded": m.degraded,
                                                      "degradation_reason": m.degradation_reason},
                "live_embedder": None if self.live is None else self.live.to_dict()}


def evaluate_index(manifest: IndexManifestV2 | None, live: EmbedderIdentity, *, count: int | None, hosted: bool, collection_id: str | None = None,
                   unreadable: bool = False) -> IndexStatus:
    """Pure decision for one collection. See the module rules."""
    def status(state: str, refuse: bool, fields: tuple[str, ...] = (), match: EmbedderMatch | None = None) -> IndexStatus:
        return IndexStatus(collection_id, state, refuse, fields, hosted, count, manifest, match, live)

    if hosted and live.provider == "local":
        return status(HASH_HOSTED, True, ("provider",))
    if count == 0:
        return status(EMPTY, False)
    if unreadable:
        return status(UNREADABLE, hosted, ("manifest",))
    if manifest is None:
        return status(NO_MANIFEST, hosted, ("manifest",))
    match = embedder_matches(manifest, live)
    if match.mismatched_fields:
        return status(MISMATCH, True, tuple(match.mismatched_fields), match)
    if match.unknown_fields:
        return status(UNKNOWN_FIELDS, hosted, tuple(match.unknown_fields), match)
    if hosted and (manifest.degraded or manifest.provider == "local"):
        return status(DEGRADED_INDEX, True, ("degraded",), match)
    return status(OK, False, (), match)


def raise_if_refused(status: IndexStatus) -> None:
    if status.refuse:
        raise IndexIncompatibleError([status.state], status.fields, status.collection_id)


# ---------------------------------------------------------------- persistence
def manifest_file(persist_dir: str | os.PathLike, collection: str) -> Path:
    safe = "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in collection)[:96] or "collection"
    return Path(persist_dir) / MANIFEST_DIR / f"{safe}.json"


class ManifestUnreadable(Exception):
    pass


def read_manifest(path: Path) -> IndexManifestV2 | None:
    """``None`` when no manifest exists; :class:`ManifestUnreadable` for a corrupt or unreadable file (never an invented manifest)."""
    if not path.exists():
        return None
    try:
        return IndexManifestV2.from_dict(json.loads(path.read_text(encoding="utf-8")))
    except Exception:  # noqa: BLE001 - corrupt JSON, wrong shape, permission: all unprovable
        raise ManifestUnreadable() from None


def write_manifest(path: Path, manifest: IndexManifestV2) -> None:
    """Atomic write (temp file in the same directory, then rename) so a crash never leaves a half-written manifest."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".manifest-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(manifest.to_dict(), sort_keys=True, indent=1))
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def remove_manifest(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        pass


def ids_checksum(chunk_ids: Iterable[str]) -> str:
    """Checksum over the collection content identity (sorted deterministic chunk ids)."""
    h = hashlib.sha256()
    for cid in sorted(chunk_ids):
        h.update(cid.encode("utf-8"))
        h.update(b"\n")
    return h.hexdigest()


def build_manifest(live: EmbedderIdentity, *, collection_id: str | None, chunk_ids: Iterable[str], embedder_label: str | None,
                   existing: IndexManifestV2 | None = None, clock: Any = None) -> IndexManifestV2:
    """A manifest for a collection built by ``live``. An existing manifest keeps its ORIGINAL embedder identity (the writer was verified compatible
    before the write); only the checksum and build time move."""
    now = (clock() if clock else datetime.now(timezone.utc)).isoformat()
    base = existing.embedder if existing is not None else live
    degraded = base.provider == "local"
    return IndexManifestV2.create(
        provider=base.provider, model=base.model, version=base.version, dimensions=base.dimensions, vector_metric="cosine",
        collection_id=collection_id, checksum=ids_checksum(chunk_ids), built_at=now,
        source_version_ids=existing.source_version_ids if existing else (), source_checksums=existing.source_checksums if existing else (),
        degraded=degraded, degradation_reason=LEXICAL_DEGRADATION if degraded else None, embedder_label=embedder_label)
