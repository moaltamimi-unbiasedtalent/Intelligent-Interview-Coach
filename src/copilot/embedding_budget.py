"""Paid-embedding approval guard and run estimates (package 02B; OD-BUDGET).

NO code path in this repository may call a paid embedding provider unless BOTH of the following are present in the process environment:

* ``ASK4MO_ALLOW_PAID_EMBEDDINGS=1``  (an explicit, per-process opt-in), and
* ``ASK4MO_EMBEDDING_BUDGET_MARKER=OD-BUDGET:<reference>``  (the owner's approved-budget reference for decision OD-BUDGET),
  together with ``ASK4MO_EMBEDDING_MAX_CALLS=<n>`` (the approved ceiling on provider calls for the run).

Neither variable is ever set by the repository, a test, CI or an agent; only the owner sets them for a specific run. A free embedder (the local
hash embedder) never needs approval. :func:`guard_embedder` returns the embedder untouched when it is free, and wraps a paid one in
:class:`BudgetedEmbedder`, which counts calls and refuses past the approved ceiling, so even an approved run is bounded.

Refusals are typed (:class:`PaidEmbeddingRefused`) and carry only fixed codes (never the marker value or any key).
"""

from __future__ import annotations

import math
import os
import re
from dataclasses import dataclass
from typing import Any, Mapping

from src.copilot import constants
from src.copilot.embeddings import BaseEmbedder

PAID_FLAG_ENV = "ASK4MO_ALLOW_PAID_EMBEDDINGS"
BUDGET_MARKER_ENV = "ASK4MO_EMBEDDING_BUDGET_MARKER"
MAX_CALLS_ENV = "ASK4MO_EMBEDDING_MAX_CALLS"
_MARKER_RE = re.compile(r"^OD-BUDGET:[A-Za-z0-9._-]{4,64}$")


class PaidEmbeddingRefused(Exception):
    """A paid embedding call was refused. ``codes`` are fixed identifiers; no value from the environment is ever included."""

    def __init__(self, codes: list[str]) -> None:
        super().__init__("paid embedding refused: " + ", ".join(codes))
        self.codes = list(codes)


@dataclass(frozen=True)
class ApprovedBudget:
    max_calls: int


def require_paid_embedding_approval(env: Mapping[str, str] | None = None) -> ApprovedBudget:
    """Raise :class:`PaidEmbeddingRefused` unless the explicit flag AND an approved-budget marker AND a call ceiling are all present and valid."""
    e = os.environ if env is None else env
    codes: list[str] = []
    if (e.get(PAID_FLAG_ENV) or "").strip().lower() not in ("1", "true", "yes"):
        codes.append("paid_flag_missing")
    marker = (e.get(BUDGET_MARKER_ENV) or "").strip()
    if not marker:
        codes.append("budget_marker_missing")
    elif not _MARKER_RE.match(marker):
        codes.append("budget_marker_invalid")
    max_calls = 0
    raw = (e.get(MAX_CALLS_ENV) or "").strip()
    if not raw:
        codes.append("max_calls_missing")
    else:
        try:
            max_calls = int(raw)
        except ValueError:
            max_calls = 0
        if max_calls <= 0:
            codes.append("max_calls_invalid")
    if codes:
        raise PaidEmbeddingRefused(codes)
    return ApprovedBudget(max_calls=max_calls)


class BudgetedEmbedder(BaseEmbedder):
    """Wraps a paid embedder; counts provider calls and refuses past the approved ceiling (before the call is made)."""

    def __init__(self, inner: BaseEmbedder, budget: ApprovedBudget) -> None:
        self._inner, self._budget = inner, budget
        self.provider, self.model = inner.provider, inner.model
        self.dimensions, self.version = inner.dimensions, getattr(inner, "version", None)
        self.calls = 0

    def _spend(self) -> None:
        if self.calls >= self._budget.max_calls:
            raise PaidEmbeddingRefused(["budget_exhausted"])
        self.calls += 1

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self._spend()
        return self._inner.embed_documents(texts)

    def embed_query(self, text: str) -> list[float]:
        self._spend()
        return self._inner.embed_query(text)


def is_free(embedder: BaseEmbedder) -> bool:
    return getattr(embedder, "provider", None) == "local"


def guard_embedder(embedder: BaseEmbedder, env: Mapping[str, str] | None = None) -> BaseEmbedder:
    """The embedder unchanged when it is free; otherwise it is returned only after approval, wrapped in a call-ceiling guard."""
    if is_free(embedder):
        return embedder
    return BudgetedEmbedder(embedder, require_paid_embedding_approval(env))


# ------------------------------------------------------------------ estimates (no provider call; arithmetic only)
# Indicative cost classes by total embedded tokens for a small OpenAI-compatible embedding model. The rate is a planning assumption, not a quote:
# verify the provider's current price before approving a run. Classes, not amounts, are what a budget decision needs.
_COST_CLASSES = ((1_000_000, "negligible (well under USD 1)"), (50_000_000, "low (a few USD at most)"), (500_000_000, "moderate (tens of USD)"))


def cost_class(tokens: int) -> str:
    for ceiling, label in _COST_CLASSES:
        if tokens < ceiling:
            return label
    return "high (hundreds of USD or more; needs explicit sizing)"


def estimate_embedding_run(*, document_texts: list[str], query_texts: list[str], batch_size: int = constants.EMBED_BATCH_SIZE) -> dict:
    """Embedding calls and approximate tokens for indexing ``document_texts`` (batched) and embedding each query one by one."""
    docs, queries = len(document_texts), len(query_texts)
    doc_calls = math.ceil(docs / batch_size) if docs else 0
    tokens = sum(max(1, len(t) // 4) for t in document_texts) + sum(max(1, len(t) // 4) for t in query_texts)    # ~4 characters per token
    return {"document_texts": docs, "query_texts": queries, "document_calls": doc_calls, "query_calls": queries,
            "embedding_calls": doc_calls + queries, "approx_tokens": tokens, "cost_class": cost_class(tokens),
            "assumptions": "about 4 characters per token; documents batched at EMBED_BATCH_SIZE; one call per query; indicative only"}


def estimate_rebuild(*, chunk_count: int, avg_chunk_chars: int = 1500, batch_size: int = constants.EMBED_BATCH_SIZE) -> dict:
    """Embedding calls and cost class for rebuilding an index of ``chunk_count`` chunks."""
    calls = math.ceil(chunk_count / batch_size) if chunk_count else 0
    tokens = chunk_count * max(1, avg_chunk_chars // 4)
    return {"chunks": chunk_count, "embedding_calls": calls, "approx_tokens": tokens, "cost_class": cost_class(tokens),
            "assumptions": f"{avg_chunk_chars} characters per chunk (about 4 characters per token); batches of {batch_size}; indicative only"}


def describe_requirements() -> dict[str, Any]:
    """What an owner must set to allow one paid run (names only; values are the owner's)."""
    return {"required_environment": [PAID_FLAG_ENV, BUDGET_MARKER_ENV, MAX_CALLS_ENV], "marker_format": "OD-BUDGET:<reference>"}
