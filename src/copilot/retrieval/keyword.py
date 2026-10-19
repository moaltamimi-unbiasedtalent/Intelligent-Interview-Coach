"""Lexical (BM25) retrieval over the career knowledge base.

BM25 excels at *exact* term matching — technologies, tools, certifications and
job titles (``Python``, ``SAP``, ``ISO 27001``, ``CIPD``, ``SHRM``, ``SQL``) —
where a semantic embedder can drift to merely related concepts. It indexes the
same chunks as the vector store and preserves their metadata, returning the same
:class:`RetrievalResult` type so it is interchangeable with vector retrieval.
"""

from __future__ import annotations

import re
import unicodedata

from src.copilot import constants
from src.copilot.models import DocumentChunk, RetrievalResult

__all__ = ["KeywordRetriever", "tokenize"]

# P10D: Unicode-aware tokens. The previous ``[a-z0-9]+`` split every word at an accented or non-Latin letter ("für" became "f", "r"; "développeur"
# became "d", "veloppeur"; Arabic and Cyrillic text produced no tokens at all), so the lexical channel could not match a word typed without its
# accents and matched on meaningless single letters. Tokens are now whole words, case-folded and accent-folded, so "Gespräch" and "Gesprach" agree.
# Pure-ASCII text tokenises exactly as before. (The offline ``LocalHashEmbedder`` keeps its ASCII tokeniser on purpose: changing it would change
# every stored embedding and require a re-index.)
_TOKEN_RE = re.compile(r"[^\W_]+")


def tokenize(text: str) -> list[str]:
    """Lower-case, accent-folded whole-word tokenisation shared by index and query.

    ``"ISO 27001"`` -> ``["iso", "27001"]``; ``"SQL"`` -> ``["sql"]``;
    ``"Vorstellungsgespräch für"`` -> ``["vorstellungsgesprach", "fur"]``. Using
    the same tokeniser for documents and queries is what makes exact-term
    matching reliable.
    """
    folded = unicodedata.normalize("NFKD", (text or "").casefold())
    folded = "".join(ch for ch in folded if not unicodedata.combining(ch))
    return _TOKEN_RE.findall(folded)


def _matches(metadata: dict, filters: dict | None) -> bool:
    if not filters:
        return True
    return all(metadata.get(key) == value for key, value in filters.items())


class KeywordRetriever:
    """BM25 retrieval over a fixed corpus of chunks."""

    def __init__(self, chunks: list[DocumentChunk]) -> None:
        self._chunks = list(chunks)
        self._bm25 = None
        if self._chunks:
            try:
                from rank_bm25 import BM25Okapi  # optional dependency ([rag] extra)
            except ImportError:
                # Degrade gracefully: no BM25 -> empty keyword results, so hybrid
                # falls back to vector-only rather than crashing.
                return
            corpus = [tokenize(chunk.text) for chunk in self._chunks]
            # Guard against a corpus of only empty token lists (BM25 divides by
            # the average document length).
            if any(corpus):
                self._bm25 = BM25Okapi(corpus)

    @classmethod
    def from_store(cls, store) -> "KeywordRetriever":
        """Build a BM25 index from the same chunks held by a vector store.

        P10D: the index is cached on the (process-shared) store, keyed by its size and its in-process mutation revision. The API built the career service, and with it this index
        over every stored chunk, for EVERY request (measured about 0.65 s for 14,087 chunks, several times the retrieval itself). A store that gained or lost chunks, in this
        process (revision) or another (size), rebuilds the index; nothing else changes, so results are identical."""
        try:
            key = (store.count(), getattr(store, "_revision", 0))
        except Exception:  # noqa: BLE001 - an uncountable store is simply not cached
            return cls(store.all_chunks())
        cached = getattr(store, "_keyword_index_cache", None)
        if cached is not None and cached[0] == key:
            return cached[1]
        retriever = cls(store.all_chunks())
        try:
            store._keyword_index_cache = (key, retriever)
        except Exception:  # noqa: BLE001 - e.g. a store with __slots__
            pass
        return retriever

    def count(self) -> int:
        return len(self._chunks)

    def retrieve(
        self,
        query: str,
        top_k: int = constants.DEFAULT_TOP_K,
        filters: dict | None = None,
    ) -> list[RetrievalResult]:
        """Return up to ``top_k`` chunks ranked by BM25 score (score > 0)."""
        query = (query or "").strip()
        if not query or self._bm25 is None or top_k <= 0:
            return []
        query_tokens = tokenize(query)
        if not query_tokens:
            return []

        scores = self._bm25.get_scores(query_tokens)
        scored: list[RetrievalResult] = []
        for chunk, score in zip(self._chunks, scores):
            score = float(score)
            if score <= 0.0:
                continue  # no lexical overlap
            if not _matches(chunk.metadata, filters):
                continue
            scored.append(
                RetrievalResult(chunk=chunk, score=score, retriever="keyword")
            )
        scored.sort(key=lambda result: result.score, reverse=True)
        return scored[:top_k]
