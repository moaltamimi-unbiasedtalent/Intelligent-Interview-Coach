"""Offline retrieval and answer-quality metrics (package 02E). Pure functions: no network, no randomness, no I/O.

Every function takes plain ids / numbers so it can be driven by the frozen datasets today and by a live provider run later. Conventions:

* ``ranked`` is an ordered list of ids (best first); duplicates keep only their first occurrence.
* ``relevant`` is a set of ids (binary relevance) or, for nDCG, a mapping id -> non-negative gain.
* An undefined metric (no relevant item, no cases) returns ``None`` where the caller must NOT read it as 0.0 or 1.0; aggregates skip ``None``.
"""

from __future__ import annotations

import math
from typing import Iterable, Mapping, Sequence

__all__ = ["recall_at_k", "precision_at_k", "ndcg_at_k", "reciprocal_rank", "mean_reciprocal_rank", "cross_language_retrieval_rate",
           "citation_accuracy", "abstention_correctness", "mean_defined"]


def _dedupe(ranked: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for r in ranked:
        if r not in seen:
            seen.add(r)
            out.append(r)
    return out


def _check_k(k: int) -> None:
    if not isinstance(k, int) or isinstance(k, bool) or k <= 0:
        raise ValueError("k must be a positive integer")


def recall_at_k(ranked: Sequence[str], relevant: Iterable[str], k: int) -> float | None:
    """Fraction of the relevant set found in the top ``k``. ``None`` when nothing is relevant."""
    _check_k(k)
    rel = set(relevant)
    if not rel:
        return None
    return len(set(_dedupe(ranked)[:k]) & rel) / len(rel)


def precision_at_k(ranked: Sequence[str], relevant: Iterable[str], k: int) -> float | None:
    """Fraction of the top ``k`` returned items that are relevant (denominator = items actually returned, at most k). ``None`` when none returned."""
    _check_k(k)
    top = _dedupe(ranked)[:k]
    if not top:
        return None
    rel = set(relevant)
    return sum(1 for r in top if r in rel) / len(top)


def ndcg_at_k(ranked: Sequence[str], relevance: Mapping[str, float] | Iterable[str], k: int) -> float | None:
    """Normalised discounted cumulative gain at ``k`` (log2 discount). ``relevance`` is a gain mapping or a set of ids (gain 1). ``None`` when
    no item has a positive gain (the ideal DCG is zero, so the metric is undefined)."""
    _check_k(k)
    gains = dict(relevance) if isinstance(relevance, Mapping) else {r: 1.0 for r in relevance}
    if any(g < 0 for g in gains.values()):
        raise ValueError("gains must be non-negative")
    ideal = sorted((g for g in gains.values() if g > 0), reverse=True)[:k]
    idcg = sum(g / math.log2(i + 2) for i, g in enumerate(ideal))
    if idcg == 0:
        return None
    dcg = sum(gains.get(r, 0.0) / math.log2(i + 2) for i, r in enumerate(_dedupe(ranked)[:k]))
    return dcg / idcg


def reciprocal_rank(ranked: Sequence[str], relevant: Iterable[str]) -> float | None:
    rel = set(relevant)
    if not rel:
        return None
    for rank, r in enumerate(_dedupe(ranked), start=1):
        if r in rel:
            return 1.0 / rank
    return 0.0


def mean_defined(values: Iterable[float | None]) -> float | None:
    """Mean over the defined values; ``None`` when there are none."""
    vals = [v for v in values if v is not None]
    return sum(vals) / len(vals) if vals else None


def mean_reciprocal_rank(cases: Iterable[tuple[Sequence[str], Iterable[str]]]) -> float | None:
    """MRR over ``(ranked, relevant)`` pairs; cases with nothing relevant are skipped, not counted as zero."""
    return mean_defined(reciprocal_rank(r, rel) for r, rel in cases)


def cross_language_retrieval_rate(cases: Iterable[tuple[str, Sequence[str], Iterable[str]]], languages: Mapping[str, str], k: int = 5) -> float | None:
    """Share of queries whose top ``k`` contains at least one relevant item written in a language DIFFERENT from the query's.

    ``cases``: ``(query_language, ranked_ids, relevant_ids)``; ``languages``: item id -> language. Queries with no relevant item in another
    language are not applicable and are skipped (``None`` when none is applicable)."""
    _check_k(k)
    hits = applicable = 0
    for qlang, ranked, relevant in cases:
        cross = {r for r in relevant if languages.get(r) not in (None, qlang)}
        if not cross:
            continue
        applicable += 1
        if set(_dedupe(ranked)[:k]) & cross:
            hits += 1
    return hits / applicable if applicable else None


def citation_accuracy(cases: Iterable[tuple[Sequence[str], Iterable[str]]]) -> float | None:
    """Micro-averaged share of cited ids that are in the case's supporting set: ``(cited, supporting)`` per answer. An answer that cites
    nothing contributes no citations (so an uncited answer is neither accurate nor inaccurate here: measure abstention separately).
    ``None`` when nothing was cited at all."""
    right = total = 0
    for cited, supporting in cases:
        sup = set(supporting)
        ids = _dedupe(cited)
        total += len(ids)
        right += sum(1 for c in ids if c in sup)
    return right / total if total else None


def abstention_correctness(cases: Iterable[tuple[bool, bool]]) -> dict:
    """``(abstained, should_abstain)`` per case. Returns the accuracy plus the two error rates that matter separately:
    ``false_answer_rate`` (answered when it should have abstained: an unsupported citation risk) and ``false_abstention_rate`` (abstained when an
    answer was supported). Each rate is ``None`` when its denominator is empty."""
    tp = fp = tn = fn = 0   # positive = abstained
    for abstained, should in cases:
        if abstained and should:
            tp += 1
        elif abstained and not should:
            fp += 1
        elif not abstained and not should:
            tn += 1
        else:
            fn += 1
    n = tp + fp + tn + fn
    return {"n": n, "accuracy": (tp + tn) / n if n else None,
            "false_answer_rate": fn / (fn + tp) if (fn + tp) else None,
            "false_abstention_rate": fp / (fp + tn) if (fp + tn) else None,
            "counts": {"abstained_correctly": tp, "abstained_wrongly": fp, "answered_correctly": tn, "answered_wrongly": fn}}
