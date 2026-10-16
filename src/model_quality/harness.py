"""Blinded Fast / Balanced / Advanced comparison harness (offline-validatable; no provider call, no secret, no real candidate data).

Evidence boundary (never blur): unit tests and mocked runners validate THIS CODE; they say nothing about model quality. ``evaluate_gate`` returns ``NOT_EVALUATED``
unless real ratings exist for the compared profiles AND thresholds with a rationale and an approver were supplied, and it never invents either. Latency, tokens, retries
and cost are reported as measured by the runner: unknown stays ``None`` (never 0) and cost is only ever a provider-reported figure.
"""

from __future__ import annotations

import json
import random
import statistics
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable

from src.llm.models import ModelProfile

ROOT = Path(__file__).resolve().parents[2]
SCENARIO_FILE = ROOT / "evaluations/model_quality/scenarios.json"
PROFILES = tuple(p.value for p in ModelProfile)                   # fast, balanced, advanced (no "medium")
TASKS = ("question_generation", "answer_feedback")
RATING_DIMENSIONS = ("question_relevance", "role_specificity", "competency_alignment", "difficulty_calibration", "followup_quality", "feedback_usefulness",
                     "rubric_consistency")
RATING_SCALE = (1, 5)


@dataclass(frozen=True)
class Scenario:
    id: str
    role: str
    industry: str
    career_level: str
    interview_type: str
    difficulty: str
    job_description: str
    candidate_background: str
    sample_answer: str


@dataclass
class RunResult:
    """One model operation as MEASURED by the runner. ``None`` means unknown (never 0)."""

    ok: bool
    output: dict | None = None
    latency_ms: int | None = None
    attempts: int | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost_usd: float | None = None          # only a provider-reported cost; never calculated from an assumed price
    error_category: str | None = None


Runner = Callable[[str, Scenario, str], RunResult]


@dataclass
class Cell:
    scenario_id: str
    task: str
    profile: str
    result: RunResult
    structural: dict = field(default_factory=dict)


@dataclass
class Thresholds:
    """Quality thresholds. NONE is defined by this code: an approver and a rationale are mandatory, so a threshold can never be chosen implicitly."""

    approved_by: str
    rationale: str
    min_mean_rating: dict          # dimension -> minimum mean (1..5) the candidate profile must reach
    max_failure_rate: float
    max_structural_invalid_rate: float


def load_scenarios(path: Path | None = None) -> list[Scenario]:
    data = json.loads((path or SCENARIO_FILE).read_text(encoding="utf-8"))
    if data.get("synthetic") is not True:
        raise ValueError("scenario file must be declared synthetic")
    return [Scenario(**{k: s[k] for k in Scenario.__dataclass_fields__}) for s in data["scenarios"]]


def validate_scenarios(scenarios: Iterable[Scenario]) -> list[str]:
    """Problems with the benchmark SET (empty when it is representative enough to use): diversity and the synthetic-only rule."""
    sc = list(scenarios)
    problems: list[str] = []
    if len({s.id for s in sc}) != len(sc):
        problems.append("duplicate scenario ids")
    for name, minimum in (("industry", 6), ("career_level", 5), ("interview_type", 5), ("difficulty", 3)):
        if len({getattr(s, name) for s in sc}) < minimum:
            problems.append(f"too few distinct {name} values (need {minimum})")
    for s in sc:
        blob = " ".join((s.job_description, s.candidate_background, s.sample_answer))
        if "@" in blob or "http" in blob.lower():
            problems.append(f"{s.id}: contains an address or link (synthetic scenarios must carry no contact data)")
    return problems


def structural_check(task: str, output: dict | None) -> dict:
    """Does the output satisfy the application's own typed contract? (Reliability only; says nothing about usefulness.)"""
    from pydantic import ValidationError

    from src.models import AnswerEvaluation, InterviewQuestion

    if output is None:
        return {"valid": False, "reason": "no_output"}
    model = InterviewQuestion if task == "question_generation" else AnswerEvaluation
    try:
        model.model_validate(output)
    except ValidationError:
        return {"valid": False, "reason": "schema"}
    return {"valid": True, "reason": None}


def run_benchmark(runner: Runner, scenarios: Iterable[Scenario], *, profiles: Iterable[str] = PROFILES, tasks: Iterable[str] = TASKS) -> list[Cell]:
    cells: list[Cell] = []
    for s in scenarios:
        for task in tasks:
            for profile in profiles:
                if profile not in PROFILES:
                    raise ValueError(f"unknown profile: {profile!r}")          # a raw provider model id can never be benchmarked or authorized by name
                res = runner(profile, s, task)
                cells.append(Cell(s.id, task, profile, res, structural_check(task, res.output) if res.ok else {"valid": False, "reason": "run_failed"}))
    return cells


def blind(cells: list[Cell], *, seed: int) -> tuple[list[dict], dict]:
    """Per (scenario, task) shuffle the profiles behind anonymous labels A, B, C. Returns (rating sheet WITHOUT profile names, separate key to unblind)."""
    rng = random.Random(seed)
    sheet: list[dict] = []
    key: dict = {}
    groups: dict[tuple[str, str], list[Cell]] = {}
    for c in cells:
        groups.setdefault((c.scenario_id, c.task), []).append(c)
    for (sid, task), group in sorted(groups.items()):
        order = list(group)
        rng.shuffle(order)
        for label, c in zip("ABCDEFGH", order):
            sheet.append({"scenario_id": sid, "task": task, "label": label, "output": c.result.output, "ok": c.result.ok})
            key[f"{sid}|{task}|{label}"] = c.profile
    return sheet, key


def _percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(round((pct / 100) * (len(ordered) - 1))))]


def aggregate(cells: list[Cell]) -> dict:
    out: dict[str, dict] = {}
    for profile in PROFILES:
        mine = [c for c in cells if c.profile == profile]
        if not mine:
            continue
        lat = [c.result.latency_ms for c in mine if c.result.latency_ms is not None]
        att = [c.result.attempts for c in mine if c.result.attempts is not None]
        known_tok = [c for c in mine if c.result.input_tokens is not None and c.result.output_tokens is not None]
        known_cost = [c.result.cost_usd for c in mine if c.result.cost_usd is not None]
        out[profile] = {
            "runs": len(mine),
            "failure_rate": sum(1 for c in mine if not c.result.ok) / len(mine),
            "structural_invalid_rate": sum(1 for c in mine if not c.structural.get("valid")) / len(mine),
            "latency_ms_p50": _percentile(lat, 50), "latency_ms_p95": _percentile(lat, 95), "latency_known_runs": len(lat),
            "attempts_mean": statistics.mean(att) if att else None, "retried_runs": sum(1 for a in att if a > 1),
            "tokens_known_runs": len(known_tok), "tokens_unknown_runs": len(mine) - len(known_tok),
            "input_tokens_known_total": sum(c.result.input_tokens for c in known_tok), "output_tokens_known_total": sum(c.result.output_tokens for c in known_tok),
            "cost_known_runs": len(known_cost), "cost_unknown_runs": len(mine) - len(known_cost),
            "cost_usd_known_total": sum(known_cost) if known_cost else None,       # unknown stays None; no price is ever assumed
        }
    return out


def apply_ratings(key: dict, ratings: list[dict]) -> dict:
    """Unblind REAL ratings (each: scenario_id, task, label, dimension, score 1..5) into per-profile, per-dimension means. Out-of-range or unknown entries are refused."""
    sums: dict[tuple[str, str], list[int]] = {}
    for r in ratings:
        if r["dimension"] not in RATING_DIMENSIONS or not (RATING_SCALE[0] <= r["score"] <= RATING_SCALE[1]):
            raise ValueError("invalid rating")
        profile = key[f"{r['scenario_id']}|{r['task']}|{r['label']}"]
        sums.setdefault((profile, r["dimension"]), []).append(r["score"])
    return {f"{p}|{d}": statistics.mean(v) for (p, d), v in sums.items()}


def evaluate_gate(aggregates: dict, rating_means: dict | None, thresholds: Thresholds | None, *, candidate: str = "fast") -> dict:
    """The ONLY place a verdict is produced. Without real ratings AND approved thresholds the verdict is NOT_EVALUATED; mocked or structural evidence never qualifies."""
    if not rating_means:
        return {"verdict": "NOT_EVALUATED", "reason": "no comparative ratings of real model outputs"}
    if thresholds is None or not thresholds.approved_by or not thresholds.rationale:
        return {"verdict": "NOT_EVALUATED", "reason": "no approved thresholds with a documented rationale"}
    agg = aggregates.get(candidate)
    if agg is None:
        return {"verdict": "NOT_EVALUATED", "reason": "candidate profile was not run"}
    failures = []
    for dim, minimum in thresholds.min_mean_rating.items():
        got = rating_means.get(f"{candidate}|{dim}")
        if got is None or got < minimum:
            failures.append(dim)
    if agg["failure_rate"] > thresholds.max_failure_rate:
        failures.append("failure_rate")
    if agg["structural_invalid_rate"] > thresholds.max_structural_invalid_rate:
        failures.append("structural_invalid_rate")
    return {"verdict": "PASS" if not failures else "FAIL", "failed": failures, "approved_by": thresholds.approved_by}
