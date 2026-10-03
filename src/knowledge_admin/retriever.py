"""Candidate-side retrieval over GOVERNED knowledge (P10B-W10.8).

The control plane (SQL) is the ONLY authority on what is retrievable. A vector hit is returned only if its version is in the
current ACTIVE set read from the database on every call. So unapproved, unindexed, indexed-but-inactive, rejected and retired
content is never returned, even if its chunks physically exist in the vector collection (for example because a deletion
failed or has not run yet). There is deliberately no BM25 channel: it would index the whole collection and bypass this gate.
"""

from __future__ import annotations

from src.copilot.models import DocumentChunk, RetrievalResult
from src.knowledge_admin.service import KnowledgeAdminService

OVERFETCH = 4


class GovernedKnowledgeRetriever:
    def __init__(self, store, session_factory) -> None:
        self.store = store
        self._active = KnowledgeAdminService(session_factory, doc_store=None, jobs=None)

    def retrieve(self, query: str, top_k: int = 5, filters: dict | None = None) -> list[RetrievalResult]:
        query = (query or "").strip()
        if not query or top_k <= 0:
            return []
        active = self._active.active_version_ids()
        if not active or self.store.count() == 0:
            return []
        hits = self.store.query(query, top_k=top_k * OVERFETCH, filters=None)
        out: list[RetrievalResult] = []
        for hit in hits:
            meta = dict(hit.metadata)
            if meta.get("knowledge_version_id") not in active:
                continue
            chunk = DocumentChunk(chunk_id=hit.chunk_id, doc_id=hit.doc_id or hit.chunk_id, text=hit.text,
                                  position=int(meta.get("chunk_index", 0) or 0), metadata=meta)
            out.append(RetrievalResult(chunk=chunk, score=hit.score, retriever="governed"))
            if len(out) >= top_k:
                break
        return out
