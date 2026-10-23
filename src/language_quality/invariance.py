"""Scoring invariance across conversation languages (06C, LG-05 engineering part, REQ-LANG-04).

Claim under test. Interview scoring and evaluation are LANGUAGE-INDEPENDENT: the rubric, the scoring rules and the score aggregation are the same in every conversation language;
the language directive changes only the language of the model's prose. In this product the scores are produced by the model (they are not recomputed by code), so there are two
distinct things that can be shown, and they must not be confused:

1. OFFLINE, deterministic (this module + ``tests/test_scoring_invariance_06c.py``): the CODE path is language-independent. For every language the system prompt equals the English
   prompt plus only the directive block, the user-message frame is identical, and for the same fake model output the parsed evaluation, the usage record and the aggregates are
   identical. Tolerance: EXACTLY ZERO (any difference is a defect in this code).
2. LIVE, needs the owner's budget marker and a model: whether the MODEL grades an answer and its translation the same. Not run here (NOT RUN / OPEN). ``LIVE_TOLERANCE_PROPOSED``
   is a PROPOSAL for the owner to approve (OD-GATE-THRESHOLDS); ``live_invariance_report`` refuses to issue a verdict without live scores and without approved thresholds.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping

ROOT = Path(__file__).resolve().parents[2]
PAIRS_FILE = ROOT / "evaluations" / "language_ai" / "answer_pairs.json"
RUBRIC_FIELDS = ("relevance", "structure", "evidence", "role_knowledge", "problem_solving", "communication", "credibility")
SCORE_FIELDS = ("overall_score", *RUBRIC_FIELDS)

# Offline pipeline tolerance: exact. Any non-zero difference between languages on the same (fake) model output is a code defect.
OFFLINE_TOLERANCE = {"overall_score": 0, "rubric": 0}

# PROPOSAL ONLY (not approved; OD-GATE-THRESHOLDS): the largest score difference between an answer and its translation graded by the same live model that would still count as
# "language-independent", per pair, and the share of pairs that must meet it. Rationale: repeated grading of the SAME text by an LLM already varies, so a zero tolerance would measure
# model noise, not language dependence; the proposal therefore sets the bar at the model's own same-language repeat noise (to be measured first with ``noise_floor``).
LIVE_TOLERANCE_PROPOSED = {"overall_score_abs": 10, "rubric_abs": 1, "min_share_of_pairs_within": 0.9, "status": "PROPOSED, NOT APPROVED (OD-GATE-THRESHOLDS)"}


@dataclass(frozen=True)
class AnswerPair:
    id: str
    level: str
    question: Mapping[str, str]
    answer: Mapping[str, str]
    reference_scores: Mapping[str, int]


def load_pairs(path: Path | None = None) -> tuple[list[AnswerPair], tuple[str, ...]]:
    data = json.loads((path or PAIRS_FILE).read_text(encoding="utf-8"))
    langs = tuple(data["languages"])
    pairs = [AnswerPair(p["id"], p["level"], p["question"], p["answer"], p["reference_scores"]) for p in data["pairs"]]
    for p in pairs:
        if set(p.question) != set(langs) or set(p.answer) != set(langs):
            raise ValueError(f"pair {p.id}: every language must be present in question and answer")
        if set(p.reference_scores) != set(SCORE_FIELDS):
            raise ValueError(f"pair {p.id}: reference scores must cover {SCORE_FIELDS}")
    return pairs, langs


def scores_of(evaluation: object) -> dict[str, int]:
    """The score fields of an evaluation object or mapping, as plain ints."""
    get = (lambda k: evaluation[k]) if isinstance(evaluation, Mapping) else (lambda k: getattr(evaluation, k))
    return {k: int(get(k)) for k in SCORE_FIELDS}


@dataclass
class InvarianceReport:
    mode: str                                       # "offline" | "live"
    status: str                                     # WITHIN_TOLERANCE | EXCEEDS_TOLERANCE | NOT_EVALUATED
    pairs: int = 0
    languages: tuple[str, ...] = ()
    max_overall_delta: int | None = None
    max_rubric_delta: int | None = None
    share_within: float | None = None
    per_language: dict[str, dict[str, int | float]] = field(default_factory=dict)
    worst: list[dict[str, object]] = field(default_factory=list)
    reason: str = ""
    tolerance: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {"mode": self.mode, "status": self.status, "pairs": self.pairs, "languages": list(self.languages), "max_overall_delta": self.max_overall_delta,
                "max_rubric_delta": self.max_rubric_delta, "share_within": self.share_within, "per_language": self.per_language, "worst": self.worst, "reason": self.reason,
                "tolerance": self.tolerance}


def _deltas(scores: Mapping[str, Mapping[str, Mapping[str, int]]], baseline: str) -> list[tuple[str, str, int, int]]:
    """(language, pair id, overall delta, max rubric delta) against the baseline language, for every pair present in both."""
    rows: list[tuple[str, str, int, int]] = []
    base = scores.get(baseline, {})
    for lang, by_pair in scores.items():
        if lang == baseline:
            continue
        for pid, sc in by_pair.items():
            if pid not in base:
                continue
            overall = abs(int(sc["overall_score"]) - int(base[pid]["overall_score"]))
            rubric = max(abs(int(sc[k]) - int(base[pid][k])) for k in RUBRIC_FIELDS)
            rows.append((lang, pid, overall, rubric))
    return rows


def offline_invariance_report(scores: Mapping[str, Mapping[str, Mapping[str, int]]], baseline: str = "en") -> InvarianceReport:
    """Compare per-language scores of the SAME fake model output through the real pipeline. Tolerance is exactly zero."""
    langs = tuple(sorted(scores))
    rows = _deltas(scores, baseline)
    if not rows:
        return InvarianceReport("offline", "NOT_EVALUATED", languages=langs, reason="no comparable (language, pair) rows", tolerance=dict(OFFLINE_TOLERANCE))
    mo, mr = max(r[2] for r in rows), max(r[3] for r in rows)
    ok = mo <= OFFLINE_TOLERANCE["overall_score"] and mr <= OFFLINE_TOLERANCE["rubric"]
    per: dict[str, dict[str, int | float]] = {}
    for lang in langs:
        mine = [r for r in rows if r[0] == lang]
        if mine:
            per[lang] = {"pairs": len(mine), "max_overall_delta": max(r[2] for r in mine), "max_rubric_delta": max(r[3] for r in mine)}
    worst = [{"language": r[0], "pair": r[1], "overall_delta": r[2], "rubric_delta": r[3]} for r in sorted(rows, key=lambda r: (-r[2], -r[3]))[:3]]
    return InvarianceReport("offline", "WITHIN_TOLERANCE" if ok else "EXCEEDS_TOLERANCE", pairs=len({r[1] for r in rows}), languages=langs, max_overall_delta=mo, max_rubric_delta=mr,
                            share_within=1.0 if ok else None, per_language=per, worst=worst, tolerance=dict(OFFLINE_TOLERANCE))


def live_invariance_report(scores: Mapping[str, Mapping[str, Mapping[str, int]]] | None, thresholds: Mapping[str, object] | None, baseline: str = "en") -> InvarianceReport:
    """Verdict on LIVE model scores. NOT_EVALUATED without live scores or without OWNER-APPROVED thresholds; it never invents either and never reads the PROPOSED numbers as approved."""
    if not scores:
        return InvarianceReport("live", "NOT_EVALUATED", reason="no live scores: live model measurement is NOT RUN (needs the owner's budget marker, OD-BUDGET)")
    approved = thresholds and thresholds.get("approved_by") and thresholds.get("approved_on") and all(k in thresholds for k in ("overall_score_abs", "rubric_abs", "min_share_of_pairs_within"))
    if not approved:
        return InvarianceReport("live", "NOT_EVALUATED", languages=tuple(sorted(scores)), reason="thresholds are not owner-approved (OD-GATE-THRESHOLDS); LIVE_TOLERANCE_PROPOSED is a proposal only")
    rows = _deltas(scores, baseline)
    if not rows:
        return InvarianceReport("live", "NOT_EVALUATED", languages=tuple(sorted(scores)), reason="no comparable (language, pair) rows")
    within = [r for r in rows if r[2] <= float(thresholds["overall_score_abs"]) and r[3] <= float(thresholds["rubric_abs"])]
    share = len(within) / len(rows)
    ok = share >= float(thresholds["min_share_of_pairs_within"])
    return InvarianceReport("live", "WITHIN_TOLERANCE" if ok else "EXCEEDS_TOLERANCE", pairs=len({r[1] for r in rows}), languages=tuple(sorted(scores)), max_overall_delta=max(r[2] for r in rows),
                            max_rubric_delta=max(r[3] for r in rows), share_within=round(share, 4), tolerance=dict(thresholds))


def noise_floor(repeat_scores: list[Mapping[str, int]]) -> dict[str, int]:
    """Largest spread of ``overall_score`` and of any rubric score across REPEATED gradings of the same text (to be measured live first; it sets the realistic tolerance)."""
    if len(repeat_scores) < 2:
        raise ValueError("at least two repeated gradings are needed")
    return {"overall_score": max(int(s["overall_score"]) for s in repeat_scores) - min(int(s["overall_score"]) for s in repeat_scores),
            "rubric": max(max(int(s[k]) for s in repeat_scores) - min(int(s[k]) for s in repeat_scores) for k in RUBRIC_FIELDS)}
