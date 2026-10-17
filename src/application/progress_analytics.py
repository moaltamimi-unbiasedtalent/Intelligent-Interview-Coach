"""Premium progress analytics and interview comparison (W12.4D-P4-B). DETERMINISTIC, descriptive and computed on request from the retained interview records:
no LLM call, no provider dependency, no stored snapshot, no cache (so a plan change or a deletion applies on the very next request).

* **Default disabled.** ``PREMIUM_ANALYTICS_ENABLED = False`` is a code constant (like the billing and other rollout gates). While False every analytics
  route answers ``feature_disabled`` with no data, so no new paid capability exists for anyone. Existing Basic progress is a different, untouched route.
* **One entitlement authority.** With the gate on, access needs an ACTIVE Premium-plan subscription read through ``plan_state.resolve_plan_state`` over the
  existing ``EntitlementService``. ``premium_preview``, client labels, expired or unknown or unreadable state are ``not_entitled``.
* **One history rule.** The interviews analysed are exactly the caller's eligible COMPLETED history under ``HistoryAccessPolicy.window_for`` (the P2-B
  mechanism, ``InterviewRepository._eligible_ids``). An analytics entitlement can never widen history access, and an aggregate never reveals an interview
  outside the window.
* **Honest measurement.** Recorded values are the persisted per-answer rubric (seven 1-10 dimensions) and 0-100 overall score, plus the report's overall
  readiness score. Everything else is a CALCULATED aggregate (plain mean) and says so. Missing values are never zero, out-of-range or non-numeric values are
  ignored as corrupt, and nothing is imputed. There is no readiness probability, no prediction and no STAR score (STAR is not a scored dimension).
* **No causal claim.** A difference between attempts is a difference in recorded practice scores. The scoring version is NOT recorded with an interview, so
  it is always reported as a limitation, and a difference in role, level, opportunity or question mix is reported as limited comparability.
"""

from __future__ import annotations

import math
import os
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Callable

# A code constant: nothing but a reviewed, owner-approved release can enable Premium analytics. Tests flip it on an isolated module attribute.
PREMIUM_ANALYTICS_ENABLED = False
MAX_ANALYZED_INTERVIEWS = 500            # the newest eligible interviews analysed in one request; ``truncated`` says when more exist
MIN_SCORED_INTERVIEWS_FOR_TREND = 2      # a change needs two measured points
LOW_SAMPLE_ANSWERS = 3                   # below this many scored answers an interview score is flagged ``low_sample`` (never hidden, never weighted)
RUBRIC = ("relevance", "structure", "evidence", "role_knowledge", "problem_solving", "communication", "credibility")
BANDS = (("0-39", 0, 39.999), ("40-59", 40, 59.999), ("60-79", 60, 79.999), ("80-100", 80, 100.0))
_TEST_ENVS = ("development", "dev", "local", "test", "testing")
TOP_IMPROVEMENT_AREAS = 5
METHODOLOGY = ("score_is_mean_of_answer_overall_scores", "rubric_dimensions_are_1_to_10_means", "missing_values_excluded_never_zero",
               "chronological_created_at_then_id", "no_weighting", "no_significance_claim", "no_causal_claim")

__all__ = ["PREMIUM_ANALYTICS_ENABLED", "PremiumAnalyticsPolicy", "overview", "compare", "RUBRIC", "MAX_ANALYZED_INTERVIEWS"]


class PremiumAnalyticsPolicy:
    """Stateless per request. ``decide`` -> ``feature_disabled`` | ``not_entitled`` | ``allowed``."""

    def __init__(self, entitlements, *, override: Callable[[int], str] | None = None) -> None:
        if override is not None and (os.environ.get("API_ENV") or "development").strip().lower() not in _TEST_ENVS:
            raise ValueError("A synthetic analytics decision cannot be used outside development and test.")
        self._entitlements, self._override = entitlements, override

    def decide(self, user_id: int) -> str:
        if not PREMIUM_ANALYTICS_ENABLED:
            return "feature_disabled"
        if self._override is not None:
            return "allowed" if self._override(int(user_id)) == "premium" else "not_entitled"
        from src.application.plan_state import PREMIUM, resolve_plan_state

        return "allowed" if resolve_plan_state(self._entitlements, user_id) == PREMIUM else "not_entitled"


# ------------------------------------------------------------------------------------------------------------------------------ measurement hygiene
def _num(v, lo: float, hi: float) -> float | None:
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v < lo or v > hi:
        return None
    return float(v)


def _clean_answer(a: dict) -> dict:
    ev = a.get("evaluation") if isinstance(a.get("evaluation"), dict) else {}
    areas = ev.get("improvement_areas")
    return {"type": a.get("question_type") if isinstance(a.get("question_type"), str) else None, "overall": _num(ev.get("overall_score"), 0, 100),
            "rubric": {d: _num(ev.get(d), 1, 10) for d in RUBRIC},
            "areas": [x.strip()[:120] for x in areas if isinstance(x, str) and x.strip()] if isinstance(areas, list) else []}


def _r1(x: float | None) -> float | None:
    return None if x is None else round(x + 0.0, 1)


def _mean(xs: list[float]) -> float | None:
    return sum(xs) / len(xs) if xs else None


def _iso(dt) -> str | None:
    return dt.isoformat() if isinstance(dt, datetime) else None


def _norm(s) -> str | None:
    return s.strip().lower() if isinstance(s, str) and s.strip() else None


def _point(row: dict) -> dict:
    ans = [_clean_answer(a) for a in row.get("answers", [])]
    scores = [a["overall"] for a in ans if a["overall"] is not None]
    rubric = {}
    for d in RUBRIC:
        vals = [a["rubric"][d] for a in ans if a["rubric"][d] is not None]
        rubric[d] = {"average": _r1(_mean(vals)), "answers_measured": len(vals)}
    return {"interview_id": row["id"], "date": _iso(row.get("created_at")), "practice_score": _r1(_mean(scores)), "answers_scored": len(scores),
            "low_sample": 0 < len(scores) < LOW_SAMPLE_ANSWERS, "report_score": _r1(_num(row.get("report_score"), 0, 100)),
            "target_role": row.get("target_role") if isinstance(row.get("target_role"), str) else None,
            "career_level": row.get("career_level") if isinstance(row.get("career_level"), str) else None,
            "opportunity_id": row.get("opportunity_id"), "question_count": int(row.get("questions") or 0), "rubric": rubric, "_ans": ans}


def _public(p: dict) -> dict:
    return {k: v for k, v in p.items() if not k.startswith("_")}


def _direction(change: float | None) -> str | None:
    if change is None:
        return None
    return "improved" if change > 0 else "declined" if change < 0 else "unchanged"


# ------------------------------------------------------------------------------------------------------------------------------ overview
def overview(rows: list[dict], *, truncated: bool, now: datetime | None = None) -> dict:
    """Trends, distribution, rubric breakdown, question-type view, practice frequency and recurring improvement areas over ``rows`` (already the caller's
    eligible completed interviews, oldest first). Returns a ``state`` of ``no_data`` | ``insufficient_data`` | ``ready``."""
    now = now or datetime.now(timezone.utc)
    pts = [_point(r) for r in rows]
    scored = [p for p in pts if p["practice_score"] is not None]
    state = "no_data" if not pts else ("ready" if len(scored) >= MIN_SCORED_INTERVIEWS_FOR_TREND else "insufficient_data")
    summary = {"first_score": None, "latest_score": None, "change": None, "direction": None, "comparable_context": None, "average_score": None, "best_score": None}
    if scored:
        scores = [p["practice_score"] for p in scored]
        summary.update(first_score=scores[0], latest_score=scores[-1], average_score=_r1(_mean(scores)), best_score=max(scores))
        if len(scored) >= MIN_SCORED_INTERVIEWS_FOR_TREND:
            change = _r1(scores[-1] - scores[0])
            summary.update(change=change, direction=_direction(change),
                           comparable_context=_norm(scored[0]["target_role"]) == _norm(scored[-1]["target_role"]) and _norm(scored[0]["career_level"]) == _norm(scored[-1]["career_level"]))
    distribution = {name: sum(1 for p in scored if lo <= p["practice_score"] <= hi) for name, lo, hi in BANDS}
    by_type: dict[str, list[float]] = defaultdict(list)
    dims: dict[str, list[float]] = {d: [] for d in RUBRIC}
    areas: Counter = Counter()
    for p in pts:
        for a in p["_ans"]:
            if a["overall"] is not None and a["type"]:
                by_type[a["type"]].append(a["overall"])
            for d in RUBRIC:
                if a["rubric"][d] is not None:
                    dims[d].append(a["rubric"][d])
            areas.update(a["areas"])
    measured = [(d, _mean(v), len(v)) for d, v in dims.items() if v]
    strongest = weakest = None
    if len(measured) >= 2 and max(n for _, _, n in measured) >= LOW_SAMPLE_ANSWERS:
        ordered = sorted(measured, key=lambda t: (-t[1], RUBRIC.index(t[0])))          # ties broken by the fixed rubric order: deterministic
        strongest, weakest = ordered[0][0], ordered[-1][0]
        if round(ordered[0][1], 1) == round(ordered[-1][1], 1):
            strongest = weakest = None                                              # no measurable difference between dimensions
    dated = [datetime.fromisoformat(p["date"]) for p in pts if p["date"]]
    dated = [d if d.tzinfo else d.replace(tzinfo=timezone.utc) for d in dated]
    by_month = Counter(d.strftime("%Y-%m") for d in dated)
    return {
        "state": state, "truncated": bool(truncated), "analyzed_limit": MAX_ANALYZED_INTERVIEWS,
        "counts": {"completed_interviews": len(pts), "scored_interviews": len(scored), "unscored_interviews": len(pts) - len(scored)},
        "points": [_public(p) | {"rubric": p["rubric"]} for p in pts], "summary": summary, "distribution": distribution,
        "rubric": {"dimensions": [{"id": d, "average": _r1(_mean(v)), "answers_measured": len(v)} for d, v in dims.items()], "strongest": strongest, "weakest": weakest},
        "by_question_type": [{"type": t, "average_score": _r1(_mean(v)), "answers_scored": len(v)} for t, v in sorted(by_type.items())],
        "frequency": {"last_30_days": sum(1 for d in dated if d >= now - timedelta(days=30)), "last_90_days": sum(1 for d in dated if d >= now - timedelta(days=90)),
                      "by_month": [{"month": m, "count": c} for m, c in sorted(by_month.items())]},
        "improvement_areas": [{"area": a, "count": c, "origin": "model_generated"} for a, c in sorted(areas.items(), key=lambda t: (-t[1], t[0]))[:TOP_IMPROVEMENT_AREAS]],
        "filters": {"roles": sorted({r for r in (p["target_role"] for p in pts) if r}), "opportunity_ids": sorted({p["opportunity_id"] for p in pts if p["opportunity_id"]})},
        "methodology": list(METHODOLOGY), "limitations": ["scoring_version_not_recorded", "model_feedback_not_objective"],
    }


# ------------------------------------------------------------------------------------------------------------------------------ comparison
def compare(base_row: dict, target_row: dict) -> dict:
    """Two eligible attempts side by side. ``base`` is the earlier reference, ``target`` the one being compared. A difference is computed only from values
    measured on BOTH sides; ``comparability`` is ``comparable`` or ``limited`` with the reason codes."""
    a, b = _point(base_row), _point(target_row)
    reasons = []
    if _norm(a["target_role"]) != _norm(b["target_role"]):
        reasons.append("different_role")
    if _norm(a["career_level"]) != _norm(b["career_level"]):
        reasons.append("different_level")
    if a["opportunity_id"] != b["opportunity_id"]:
        reasons.append("different_opportunity")
    types_a = Counter(x["type"] for x in a["_ans"] if x["type"])
    types_b = Counter(x["type"] for x in b["_ans"] if x["type"])
    if set(types_a) != set(types_b):
        reasons.append("different_question_mix")
    if a["question_count"] != b["question_count"]:
        reasons.append("different_question_count")
    if a["low_sample"] or b["low_sample"]:
        reasons.append("low_sample")
    both = a["practice_score"] is not None and b["practice_score"] is not None
    diff = _r1(b["practice_score"] - a["practice_score"]) if both else None
    dims = []
    for d in RUBRIC:
        x, y = a["rubric"][d]["average"], b["rubric"][d]["average"]
        dims.append({"id": d, "base": x, "target": y, "difference": _r1(y - x) if x is not None and y is not None else None})
    return {
        "state": "ready" if both else "insufficient_data",
        "base": _public(a) | {"rubric": a["rubric"]}, "target": _public(b) | {"rubric": b["rubric"]},
        "score_difference": diff, "direction": _direction(diff), "rubric_differences": dims,
        "comparability": "comparable" if not [r for r in reasons if r != "low_sample"] and "low_sample" not in reasons else "limited", "comparability_reasons": reasons,
        "limitations": ["scoring_version_not_recorded", "model_feedback_not_objective", "difference_is_not_proof_of_skill_change"],
        "methodology": list(METHODOLOGY),
    }
