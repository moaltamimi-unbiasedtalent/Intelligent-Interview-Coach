"""Calibrated relevance floor (package 02E, L-REL-1).

A RELEVANCE FLOOR is the minimum retrieval score below which a chunk is not evidence and must not be cited. This module provides

1. the mechanism: :class:`RelevanceFloor`, :func:`apply_floor` (a result survives only when ``score > floor``) and :func:`abstains`
   (an irrelevant-only result set leaves nothing, so the caller abstains instead of citing an unrelated source);
2. the configuration: :func:`resolve_floor` with the precedence ``environment override`` > ``approved calibrated entry for this embedder
   identity`` > ``safe default``. The default is :data:`DEFAULT_FLOOR` = 0.0, EXCLUSIVE: a chunk with no similarity at all is never returned
   (this is the P10D behaviour and is the strictest value that is correct for every embedder without measured scores);
3. the calibration: :func:`calibrate` takes scored retrieval results with ground-truth relevance (per language) and computes the precision /
   recall trade-off at every candidate floor and the abstention behaviour on queries that have NO relevant source, then PROPOSES a floor with its
   evidence. A proposal is advice: nothing here applies it. A calibrated entry takes effect only when it is written into the floor table with
   ``approved: true`` (a human decision) AND its embedder identity matches the live embedder exactly.

Scores are embedder-specific (cosine of one model is not comparable with another's), so a floor is always bound to an embedder identity
(provider, model, version, dimensions). No score distribution from any real embedder is assumed anywhere in this module.
"""

from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

__all__ = ["DEFAULT_FLOOR", "FLOOR_ENV", "FLOOR_TABLE_PATH", "RelevanceFloor", "apply_floor", "abstains", "resolve_floor", "ScoredQuery", "calibrate",
           "identity_key", "FloorConfigurationError"]

DEFAULT_FLOOR = 0.0
FLOOR_ENV = "COPILOT_RELEVANCE_FLOOR"
FLOOR_TABLE_PATH = Path(__file__).resolve().parents[3] / "evaluations" / "retrieval_quality" / "relevance_floors.json"
MIN_QUERIES_PER_LANGUAGE = 30      # below this a per-language proposal is labelled insufficient_sample (a planning bound, not a statistical test)


class FloorConfigurationError(ValueError):
    """The floor override or table is invalid. Raised instead of silently using a looser value."""


@dataclass(frozen=True)
class RelevanceFloor:
    value: float
    source: str                       # "default" | "environment" | "calibrated"
    detail: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.value, (int, float)) or isinstance(self.value, bool) or not math.isfinite(self.value) or not 0.0 <= self.value < 1.0:
            raise FloorConfigurationError("a relevance floor must be a finite number in [0, 1)")


def apply_floor(results: Sequence[Any], floor: RelevanceFloor | float, *, score_of=lambda r: r.score) -> list[Any]:
    """Keep results whose score is strictly above the floor, preserving order. A NaN or non-numeric score never survives."""
    f = floor.value if isinstance(floor, RelevanceFloor) else float(floor)
    out = []
    for r in results:
        try:
            s = float(score_of(r))
        except (TypeError, ValueError):
            continue
        if math.isfinite(s) and s > f:
            out.append(r)
    return out


def abstains(results: Sequence[Any], floor: RelevanceFloor | float, *, score_of=lambda r: r.score) -> bool:
    """True when nothing survives the floor: the caller must abstain (no citation) rather than cite a below-floor chunk."""
    return not apply_floor(results, floor, score_of=score_of)


def identity_key(provider: str | None, model: str | None, version: str | None, dimensions: int | None) -> str:
    """Stable text key of an embedder identity. An unknown field makes the key unmatched on purpose (``?``): an unknown identity never inherits a calibration."""
    return "|".join("?" if v in (None, "") else str(v) for v in (provider, model, version, dimensions))


def _load_table(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        entries = data["entries"]
        if not isinstance(entries, list):
            raise TypeError
    except Exception:  # noqa: BLE001
        raise FloorConfigurationError("the relevance floor table is unreadable") from None
    return entries


def resolve_floor(identity: tuple[str | None, str | None, str | None, int | None] | None = None, *, language: str | None = None,
                  env: Mapping[str, str] | None = None, table_path: Path | None = None) -> RelevanceFloor:
    """Environment override, else the approved calibrated entry for exactly this embedder identity (and language, else its ``*`` entry), else the default.

    An invalid override raises :class:`FloorConfigurationError`; it is never ignored in favour of a looser value. Entries that are not
    ``approved`` or whose identity key differs are ignored."""
    e = os.environ if env is None else env
    raw = (e.get(FLOOR_ENV) or "").strip()
    if raw:
        try:
            return RelevanceFloor(float(raw), "environment", FLOOR_ENV)
        except ValueError:
            raise FloorConfigurationError(f"{FLOOR_ENV} is not a number in [0, 1)") from None
    if identity is not None and identity_key(*identity).count("?") == 0:
        key = identity_key(*identity)
        wanted = [language, "*"] if language else ["*"]
        entries = [x for x in _load_table(table_path or FLOOR_TABLE_PATH) if x.get("approved") is True and x.get("identity") == key]
        for lang in wanted:
            for x in entries:
                if x.get("language") == lang:
                    return RelevanceFloor(float(x["floor"]), "calibrated", f"{key} [{lang}]")
    return RelevanceFloor(DEFAULT_FLOOR, "default", "uncalibrated embedder: strict no-similarity floor")


# ------------------------------------------------------------------ calibration
@dataclass(frozen=True)
class ScoredQuery:
    """One query's retrieved candidates: ``scored`` = ``(score, is_relevant)`` for every candidate the retriever returned (its whole top-k).
    ``language`` is the question language. A query with no relevant candidate in the corpus (``answerable=False``) must end in abstention."""

    query_id: str
    language: str
    scored: tuple[tuple[float, bool], ...]
    answerable: bool = True


@dataclass
class _Point:
    floor: float
    kept: int = 0
    kept_relevant: int = 0
    total_relevant: int = 0
    answerable_queries: int = 0
    answerable_abstained: int = 0          # false abstentions
    unanswerable_queries: int = 0
    unanswerable_answered: int = 0         # irrelevant citations: the failure the floor exists to prevent

    def to_dict(self) -> dict:
        prec = self.kept_relevant / self.kept if self.kept else None
        rec = self.kept_relevant / self.total_relevant if self.total_relevant else None
        return {"floor": round(self.floor, 6), "precision": None if prec is None else round(prec, 4), "recall": None if rec is None else round(rec, 4),
                "kept": self.kept, "false_abstention_rate": round(self.answerable_abstained / self.answerable_queries, 4) if self.answerable_queries else None,
                "irrelevant_citation_rate": round(self.unanswerable_answered / self.unanswerable_queries, 4) if self.unanswerable_queries else None}


def _curve(queries: Sequence[ScoredQuery], candidates: Sequence[float]) -> list[_Point]:
    pts = []
    for f in candidates:
        p = _Point(f)
        for q in queries:
            kept = [(s, rel) for s, rel in q.scored if math.isfinite(s) and s > f]
            relevant_total = sum(1 for _, rel in q.scored if rel)
            p.kept += len(kept)
            p.kept_relevant += sum(1 for _, rel in kept if rel)
            p.total_relevant += relevant_total
            if q.answerable:
                p.answerable_queries += 1
                p.answerable_abstained += 0 if kept else 1
            else:
                p.unanswerable_queries += 1
                p.unanswerable_answered += 1 if kept else 0
        pts.append(p)
    return pts


def _candidates(queries: Iterable[ScoredQuery]) -> list[float]:
    scores = sorted({round(s, 6) for q in queries for s, _ in q.scored if math.isfinite(s) and 0.0 <= s < 1.0})
    # a floor is "strictly above": placing it AT an observed score drops that score, so observed scores are the exact break points
    return sorted({DEFAULT_FLOOR, *scores})


def calibrate(queries: Sequence[ScoredQuery], *, min_precision: float = 0.9, max_irrelevant_citation_rate: float = 0.0,
              min_queries_per_language: int = MIN_QUERIES_PER_LANGUAGE) -> dict:
    """Per-language and overall precision / recall trade-off and a PROPOSED floor with its evidence.

    The proposal for a slice is the floor with the HIGHEST recall among those that satisfy BOTH constraints: item precision >= ``min_precision`` and the
    irrelevant-citation rate on unanswerable queries <= ``max_irrelevant_citation_rate`` (default: none). Ties go to the LOWER floor (fewer false
    abstentions). If no floor satisfies both, ``proposed_floor`` is ``None``: the evidence does not support a floor and the safe default stays.
    ``confidence`` is ``insufficient_sample`` for a slice with fewer than ``min_queries_per_language`` queries or with no unanswerable query (the
    irrelevant-citation constraint is then unmeasured). A proposal is never applied by this function."""
    if not 0.0 <= min_precision <= 1.0 or not 0.0 <= max_irrelevant_citation_rate <= 1.0:
        raise ValueError("constraints must be within [0, 1]")
    queries = list(queries)
    cands = _candidates(queries)

    def slice_result(qs: list[ScoredQuery]) -> dict:
        pts = _curve(qs, cands)
        ok = []
        for p in pts:
            d = p.to_dict()
            prec_ok = d["precision"] is not None and d["precision"] >= min_precision
            irr_ok = d["irrelevant_citation_rate"] is None or d["irrelevant_citation_rate"] <= max_irrelevant_citation_rate
            if prec_ok and irr_ok:
                ok.append(d)
        best = None
        for d in ok:                       # candidates ascend, so strict > keeps the lowest floor on ties
            if best is None or (d["recall"] or 0.0) > (best["recall"] or 0.0):
                best = d
        unanswerable = sum(1 for q in qs if not q.answerable)
        insufficient = len(qs) < min_queries_per_language or unanswerable == 0
        return {"queries": len(qs), "answerable": len(qs) - unanswerable, "unanswerable": unanswerable,
                "proposed_floor": None if best is None else best["floor"], "at_proposal": best,
                "confidence": "insufficient_sample" if insufficient else "adequate_sample",
                "curve": [p.to_dict() for p in pts]}

    languages = sorted({q.language for q in queries})
    return {"schema_version": 1, "constraints": {"min_precision": min_precision, "max_irrelevant_citation_rate": max_irrelevant_citation_rate,
                                                 "min_queries_per_language": min_queries_per_language},
            "applied": False,
            "note": "A proposal is evidence for a human decision. It is applied only through an approved entry in the relevance floor table for an exact embedder identity.",
            "overall": slice_result(queries),
            "by_language": {lang: slice_result([q for q in queries if q.language == lang]) for lang in languages}}
