"""Latency, throughput, token and cost accounting from a provider-call record (package 02E).

The benchmark runner records ONE :class:`ProviderCallRecord` per embedding call; :func:`summarise` turns the records into the figures the owner
asked for. Nothing here makes a call. A fake provider fills the records in tests; a later governed live run fills them with real timings and
usage. Cost is ``None`` (unknown), never 0, unless a price is configured for the model.
"""

from __future__ import annotations

import math
import time
from dataclasses import asdict, dataclass
from typing import Any, Callable, Iterable

from src.copilot.embeddings import BaseEmbedder

__all__ = ["ProviderCallRecord", "RecordingEmbedder", "summarise", "estimate_tokens"]


def estimate_tokens(text: str) -> int:
    """About four characters per token (the same planning assumption as ``embedding_budget``); a provider-reported count replaces it when known."""
    return max(1, len(text or "") // 4)


@dataclass(frozen=True)
class ProviderCallRecord:
    model: str
    kind: str                       # "documents" | "query"
    texts: int
    tokens: int
    latency_ms: float
    ok: bool = True
    error_code: str | None = None
    cost_usd: float | None = None   # None = unknown

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _pct(sorted_vals: list[float], p: float) -> float | None:
    if not sorted_vals:
        return None
    idx = max(0, min(len(sorted_vals) - 1, math.ceil(p / 100 * len(sorted_vals)) - 1))
    return round(sorted_vals[idx], 3)


def summarise(records: Iterable[ProviderCallRecord], *, price_per_million_tokens_usd: float | None = None) -> dict:
    """Calls, errors, tokens, latency p50/p95/mean, throughput (tokens and texts per second of provider time) and cost.

    Cost: the sum of record costs when every record has one; else tokens x ``price_per_million_tokens_usd`` when a price is given; else ``None``."""
    recs = list(records)
    lat = sorted(r.latency_ms for r in recs)
    tokens, texts = sum(r.tokens for r in recs), sum(r.texts for r in recs)
    seconds = sum(r.latency_ms for r in recs) / 1000.0
    if recs and all(r.cost_usd is not None for r in recs):
        cost, basis = round(sum(r.cost_usd for r in recs), 6), "recorded"        # type: ignore[misc]
    elif price_per_million_tokens_usd is not None:
        cost, basis = round(tokens * price_per_million_tokens_usd / 1_000_000, 6), "configured_price"
    else:
        cost, basis = None, "unknown"
    return {"calls": len(recs), "failed_calls": sum(1 for r in recs if not r.ok), "texts": texts, "tokens": tokens,
            "latency_ms": {"p50": _pct(lat, 50), "p95": _pct(lat, 95), "mean": round(sum(lat) / len(lat), 3) if lat else None},
            "throughput": {"tokens_per_second": round(tokens / seconds, 3) if seconds > 0 else None,
                           "texts_per_second": round(texts / seconds, 3) if seconds > 0 else None},
            "cost_usd": cost, "cost_basis": basis}


class RecordingEmbedder(BaseEmbedder):
    """Wraps any embedder and appends a :class:`ProviderCallRecord` per call. Provider failures are recorded (code only) and re-raised."""

    def __init__(self, inner: BaseEmbedder, *, clock: Callable[[], float] = time.perf_counter, price_per_million_tokens_usd: float | None = None) -> None:
        self._inner, self._clock, self._price = inner, clock, price_per_million_tokens_usd
        self.provider, self.model = inner.provider, inner.model
        self.dimensions, self.version = inner.dimensions, getattr(inner, "version", None)
        self.records: list[ProviderCallRecord] = []

    def _call(self, kind: str, texts: list[str], fn):
        tokens = sum(estimate_tokens(t) for t in texts)
        cost = None if self._price is None else tokens * self._price / 1_000_000
        start = self._clock()
        try:
            out = fn()
        except Exception as exc:  # noqa: BLE001 - only a fixed code is kept
            ms = (self._clock() - start) * 1000.0
            self.records.append(ProviderCallRecord(self.model, kind, len(texts), tokens, ms, False, getattr(exc, "code", "provider_error"), cost))
            raise
        ms = (self._clock() - start) * 1000.0
        self.records.append(ProviderCallRecord(self.model, kind, len(texts), tokens, ms, True, None, cost))
        return out

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        texts = list(texts)
        return self._call("documents", texts, lambda: self._inner.embed_documents(texts))

    def embed_query(self, text: str) -> list[float]:
        return self._call("query", [text], lambda: self._inner.embed_query(text))
