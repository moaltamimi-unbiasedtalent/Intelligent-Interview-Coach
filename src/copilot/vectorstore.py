"""Vector store for Career Intelligence Copilot.

Two interchangeable backends implement the same :class:`BaseVectorStore`
interface so retrieval never depends on a specific store:

* :class:`ChromaStore` — a *persistent* Chroma collection (the real store).
* :class:`InMemoryVectorStore` — a pure-Python cosine store with no
  dependencies, used as a fallback when Chroma is not installed and as the
  backend in tests.

Both store the embedding, chunk text, sanitised metadata and the stable chunk id,
and both skip re-indexing chunks whose ids are already present, so re-running the
indexer over unchanged content is cheap.
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass

from src.copilot import constants
from src.copilot.config import CopilotConfig
from src.copilot import index_manifest as _im
from src.copilot.embeddings import BaseEmbedder, build_embedder, current_environment
from src.copilot.models import DocumentChunk
from src.knowledge_admin.contracts import EmbedderIdentity, IndexManifestV2

__all__ = [
    "VectorHit",
    "IndexResult",
    "BaseVectorStore",
    "ChromaStore",
    "InMemoryVectorStore",
    "build_vector_store",
    "sanitize_metadata",
]


@dataclass
class VectorHit:
    """One raw hit from the vector store (before mapping to a RetrievalResult)."""

    chunk_id: str
    doc_id: str
    text: str
    metadata: dict
    score: float  # cosine similarity, higher is better


@dataclass
class IndexResult:
    """Outcome of an indexing call."""

    added: int = 0
    skipped_existing: int = 0
    total: int = 0

    def as_dict(self) -> dict:
        return {"added": self.added, "skipped_existing": self.skipped_existing, "total": self.total}


def sanitize_metadata(metadata: dict, *, doc_id: str) -> dict:
    """Keep only known scalar metadata (Chroma rejects nested values)."""
    clean: dict = {"doc_id": doc_id}
    for key in constants.VECTOR_METADATA_KEYS:
        value = metadata.get(key)
        if isinstance(value, (str, int, float, bool)):
            clean[key] = value
    return clean


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


def _matches(metadata: dict, filters: dict | None) -> bool:
    if not filters:
        return True
    return all(metadata.get(key) == value for key, value in filters.items())


class BaseVectorStore(ABC):
    """Shared store interface. Holds the embedder used for index + query."""

    embedder: BaseEmbedder
    collection_name: str | None = None

    # ---- 02B: index manifest + compatibility guard ------------------------------------------------------------------------------------
    # Subclasses supply ``_load_manifest`` / ``_save_manifest`` / ``_drop_manifest`` / ``_all_ids``. The guard runs BEFORE any embedding call
    # (so a refused query or write never spends a paid embedding request) and never returns an empty result for an incompatible index.
    def _live_identity(self) -> EmbedderIdentity:
        ident = getattr(self.embedder, "identity", None)
        if callable(ident):
            return ident()
        return EmbedderIdentity(getattr(self.embedder, "provider", None), getattr(self.embedder, "model", None),
                                getattr(self.embedder, "version", None), getattr(self.embedder, "dimensions", None))

    def _load_manifest(self) -> IndexManifestV2 | None:  # pragma: no cover - overridden
        return None

    def _save_manifest(self, manifest: IndexManifestV2) -> None:  # pragma: no cover - overridden
        return None

    def _drop_manifest(self) -> None:  # pragma: no cover - overridden
        return None

    def _all_ids(self) -> list[str]:  # pragma: no cover - overridden
        return []

    def index_manifest(self) -> IndexManifestV2 | None:
        """The persisted manifest of this collection, ``None`` if none exists (unreadable raises nothing here: see ``index_status``)."""
        try:
            return self._load_manifest()
        except _im.ManifestUnreadable:
            return None

    def index_status(self, *, environment: str | None = None) -> "_im.IndexStatus":
        """Compatibility of this collection with the live embedder in ``environment`` (default ``API_ENV``). Read-only; never raises for a mismatch."""
        env = current_environment(environment)
        unreadable = False
        manifest = None
        try:
            manifest = self._load_manifest()
        except _im.ManifestUnreadable:
            unreadable = True
        try:
            count: int | None = int(self.count())
        except Exception:  # noqa: BLE001
            count = None
        return _im.evaluate_index(manifest, self._live_identity(), count=count, hosted=env != "development",
                                  collection_id=self.collection_name, unreadable=unreadable)

    def assert_servable(self) -> "_im.IndexStatus":
        """Raise :class:`IndexIncompatibleError` when the index must not be queried or extended with the live embedder."""
        status = self.index_status()
        _im.raise_if_refused(status)
        return status

    def _record_build(self, *, had_vectors: bool) -> None:
        """After a successful write: create the manifest for a new collection, or move checksum/build time of an existing one. A legacy
        non-empty collection WITHOUT a manifest stays without one (its embedder is unknown and is never invented)."""
        try:
            existing = self._load_manifest()
        except _im.ManifestUnreadable:
            return
        if existing is None and had_vectors:
            return
        self._save_manifest(_im.build_manifest(self._live_identity(), collection_id=self.collection_name, chunk_ids=self._all_ids(),
                                               embedder_label=type(self.embedder).__name__[:64], existing=existing))

    def _refresh_after_delete(self) -> None:
        """Keep the manifest checksum truthful after a deletion; an emptied collection loses its manifest (the next build records a new one)."""
        try:
            existing = self._load_manifest()
        except _im.ManifestUnreadable:
            return
        if existing is None:
            return
        ids = self._all_ids()
        if not ids:
            self._drop_manifest()
            return
        self._save_manifest(_im.build_manifest(existing.embedder, collection_id=self.collection_name, chunk_ids=ids,
                                               embedder_label=existing.embedder_label, existing=existing))

    def _touch(self) -> None:
        """Record an in-process mutation (P10D). ``KeywordRetriever.from_store`` keys its cached BM25 index on (count, revision), so a store that changed without a change of
        size (delete then add the same number, or a reset) never serves a stale lexical index."""
        self._revision = getattr(self, "_revision", 0) + 1

    @abstractmethod
    def add_chunks(self, chunks: Sequence[DocumentChunk]) -> IndexResult:
        ...

    @abstractmethod
    def query(
        self, text: str, *, top_k: int, filters: dict | None = None
    ) -> list[VectorHit]:
        ...

    @abstractmethod
    def count(self) -> int:
        ...

    @abstractmethod
    def reset(self) -> None:
        ...

    @abstractmethod
    def all_chunks(self) -> list[DocumentChunk]:
        """Return every stored chunk (so BM25 can index the same corpus)."""
        ...

    def delete_where(self, filters: dict) -> int:
        """Physically delete chunks whose metadata equals ``filters`` (P10B-W10.8). Returns the number removed.

        Used only to clean up governed knowledge. Access control NEVER depends on it: retrieval is gated by the
        control-plane (SQL) active set, so a failed or delayed deletion cannot expose retired content.
        """
        raise NotImplementedError("This vector store does not support deletion.")


class InMemoryVectorStore(BaseVectorStore):
    """A dependency-free cosine store (fallback + tests)."""

    def __init__(self, embedder: BaseEmbedder, *, collection_name: str | None = None) -> None:
        self.embedder = embedder
        self.collection_name = collection_name
        self._items: dict[str, dict] = {}
        self._manifest: IndexManifestV2 | None = None

    def _load_manifest(self) -> IndexManifestV2 | None:
        return self._manifest

    def _save_manifest(self, manifest: IndexManifestV2) -> None:
        self._manifest = manifest

    def _drop_manifest(self) -> None:
        self._manifest = None

    def _all_ids(self) -> list[str]:
        return list(self._items)

    def add_chunks(self, chunks: Sequence[DocumentChunk]) -> IndexResult:
        self.assert_servable()
        had_vectors = bool(self._items)
        new = [c for c in chunks if c.chunk_id not in self._items]
        skipped = len(chunks) - len(new)
        if new:
            self._touch()
            vectors = self.embedder.embed_documents([c.text for c in new])
            for chunk, vector in zip(new, vectors):
                self._items[chunk.chunk_id] = {
                    "doc_id": chunk.doc_id,
                    "text": chunk.text,
                    "metadata": sanitize_metadata(chunk.metadata, doc_id=chunk.doc_id),
                    "vector": vector,
                }
            self._record_build(had_vectors=had_vectors)
        return IndexResult(added=len(new), skipped_existing=skipped, total=len(self._items))

    def query(
        self, text: str, *, top_k: int, filters: dict | None = None
    ) -> list[VectorHit]:
        self.assert_servable()          # 02B: an incompatible index is refused (typed), never answered with an empty or mis-scored result
        if not self._items or top_k <= 0:
            return []
        qvec = self.embedder.embed_query(text)
        scored: list[VectorHit] = []
        for chunk_id, item in self._items.items():
            if not _matches(item["metadata"], filters):
                continue
            scored.append(
                VectorHit(
                    chunk_id=chunk_id,
                    doc_id=item["doc_id"],
                    text=item["text"],
                    metadata=dict(item["metadata"]),
                    score=_cosine(qvec, item["vector"]),
                )
            )
        scored.sort(key=lambda hit: hit.score, reverse=True)
        return scored[:top_k]

    def count(self) -> int:
        return len(self._items)

    def delete_where(self, filters: dict) -> int:
        doomed = [cid for cid, item in self._items.items() if filters and _matches(item["metadata"], filters)]
        for cid in doomed:
            del self._items[cid]
        self._touch()
        self._refresh_after_delete()
        return len(doomed)

    def reset(self) -> None:
        self._touch()
        self._items.clear()
        self._drop_manifest()

    def all_chunks(self) -> list[DocumentChunk]:
        return [
            DocumentChunk(
                chunk_id=chunk_id,
                doc_id=item["doc_id"],
                text=item["text"],
                position=int(item["metadata"].get("chunk_index", 0) or 0),
                metadata=dict(item["metadata"]),
            )
            for chunk_id, item in self._items.items()
        ]


class ChromaStore(BaseVectorStore):
    """A persistent Chroma-backed vector store (cosine space)."""

    def __init__(
        self,
        embedder: BaseEmbedder,
        *,
        persist_dir: str = constants.CHROMA_PERSIST_DIR,
        collection_name: str = constants.CHROMA_COLLECTION_NAME,
    ) -> None:
        import logging

        import chromadb  # local import: optional dependency
        from chromadb.config import Settings

        # Chroma's telemetry client logs noisy ERRORs on some posthog versions
        # even when disabled; silence it (nothing leaves the machine either way).
        logging.getLogger("chromadb.telemetry").setLevel(logging.CRITICAL)

        self.embedder = embedder
        self.persist_dir = persist_dir
        self.collection_name = collection_name
        self._manifest_path = _im.manifest_file(persist_dir, collection_name)
        # Local-only telemetry is disabled: nothing about queries leaves the machine.
        self._client = chromadb.PersistentClient(
            path=persist_dir,
            settings=Settings(anonymized_telemetry=False),
        )
        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def _load_manifest(self) -> IndexManifestV2 | None:
        return _im.read_manifest(self._manifest_path)

    def _save_manifest(self, manifest: IndexManifestV2) -> None:
        _im.write_manifest(self._manifest_path, manifest)

    def _drop_manifest(self) -> None:
        _im.remove_manifest(self._manifest_path)

    def _all_ids(self) -> list[str]:
        return list(self._collection.get(include=[]).get("ids", []))

    def _existing_ids(self, ids: list[str]) -> set[str]:
        if not ids:
            return set()
        got = self._collection.get(ids=ids, include=[])
        return set(got.get("ids", []))

    def add_chunks(self, chunks: Sequence[DocumentChunk]) -> IndexResult:
        chunks = list(chunks)
        if not chunks:
            return IndexResult(total=self.count())
        self.assert_servable()
        had_vectors = self.count() > 0
        existing = self._existing_ids([c.chunk_id for c in chunks])
        new = [c for c in chunks if c.chunk_id not in existing]
        skipped = len(chunks) - len(new)
        added = 0
        if new:
            self._touch()
        # Embed + add in batches to bound memory and request size.
        batch = constants.EMBED_BATCH_SIZE
        for start in range(0, len(new), batch):
            group = new[start : start + batch]
            vectors = self.embedder.embed_documents([c.text for c in group])
            self._collection.add(
                ids=[c.chunk_id for c in group],
                documents=[c.text for c in group],
                metadatas=[
                    sanitize_metadata(c.metadata, doc_id=c.doc_id) for c in group
                ],
                embeddings=vectors,
            )
            added += len(group)
        if added:
            self._record_build(had_vectors=had_vectors)
        return IndexResult(added=added, skipped_existing=skipped, total=self.count())

    @staticmethod
    def _where(filters: dict | None) -> dict | None:
        if not filters:
            return None
        conditions = [{key: value} for key, value in filters.items()]
        if len(conditions) == 1:
            return conditions[0]
        return {"$and": conditions}

    def query(
        self, text: str, *, top_k: int, filters: dict | None = None
    ) -> list[VectorHit]:
        self.assert_servable()          # 02B: refuse an incompatible index (typed) before spending an embedding call
        if top_k <= 0 or self.count() == 0:
            return []
        qvec = self.embedder.embed_query(text)
        result = self._collection.query(
            query_embeddings=[qvec],
            n_results=min(top_k, self.count()),
            where=self._where(filters),
            include=["documents", "metadatas", "distances"],
        )
        ids = (result.get("ids") or [[]])[0]
        documents = (result.get("documents") or [[]])[0]
        metadatas = (result.get("metadatas") or [[]])[0]
        distances = (result.get("distances") or [[]])[0]
        hits: list[VectorHit] = []
        for chunk_id, text_, metadata, distance in zip(
            ids, documents, metadatas, distances
        ):
            metadata = dict(metadata or {})
            hits.append(
                VectorHit(
                    chunk_id=chunk_id,
                    doc_id=metadata.get("doc_id", ""),
                    text=text_,
                    metadata=metadata,
                    score=1.0 - float(distance),  # cosine distance -> similarity
                )
            )
        return hits

    def count(self) -> int:
        return self._collection.count()

    def delete_where(self, filters: dict) -> int:
        if not filters:
            return 0
        got = self._collection.get(where=self._where(filters), include=[])
        ids = got.get("ids", [])
        if ids:
            self._collection.delete(ids=ids)
        self._touch()
        self._refresh_after_delete()
        return len(ids)

    def reset(self) -> None:
        self._touch()
        self._drop_manifest()
        self._client.delete_collection(self.collection_name)
        self._collection = self._client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def all_chunks(self) -> list[DocumentChunk]:
        got = self._collection.get(include=["documents", "metadatas"])
        ids = got.get("ids", [])
        documents = got.get("documents", []) or []
        metadatas = got.get("metadatas", []) or []
        chunks: list[DocumentChunk] = []
        for chunk_id, text, metadata in zip(ids, documents, metadatas):
            if not text:
                continue  # DocumentChunk requires non-empty text
            metadata = dict(metadata or {})
            chunks.append(
                DocumentChunk(
                    chunk_id=chunk_id,
                    doc_id=metadata.get("doc_id", chunk_id),
                    text=text or "",
                    position=int(metadata.get("chunk_index", 0) or 0),
                    metadata=metadata,
                )
            )
        return chunks


def _chroma_available() -> bool:
    try:
        import chromadb  # noqa: F401

        return True
    except ImportError:
        return False


def build_vector_store(
    config: CopilotConfig,
    *,
    embedder: BaseEmbedder | None = None,
    in_memory: bool = False,
) -> BaseVectorStore:
    """Build a vector store; Chroma when available unless ``in_memory`` is set."""
    embedder = embedder or build_embedder(config)
    if in_memory or not _chroma_available():
        return InMemoryVectorStore(embedder, collection_name=constants.CHROMA_COLLECTION_NAME)
    return ChromaStore(embedder, persist_dir=config.chroma_persist_dir)
