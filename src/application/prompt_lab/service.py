"""Prompt Lab service (Capstone P6/E6) — bounded, isolated, no auto-promotion.

Creates and runs HUMAN-REVIEWED experiments against FIXED evaluation sets using
DETERMINISTIC evaluators (no live model, no cost by default). Guarantees:
- **Production isolation**: a run never reads or writes a production prompt, the model
  policy, specialist routing, code or deployment. Evaluators only call PURE resolvers.
- **No auto-promotion**: results never change production; a promotion decision is a
  RECOMMENDATION with ``applied_to_production=False`` always.
- **Human decision required**: reviews/promotion are explicit, recorded actions.
- **Versioned + attributable**: every run snapshots the production config versions.

Storage is a simple JSON file store under a configurable base dir (default a git-ignored
``var/prompt_lab``); authorization (PLATFORM_ADMIN) is enforced at the API layer.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

from src.application.prompt_lab.models import (
    EvaluationSet,
    Experiment,
    ExperimentRun,
    ExperimentStatus,
    HumanReview,
    MetricResult,
    PromotionDecision,
    PromotionOutcome,
    ReviewOutcome,
    Variant,
)

__all__ = ["PromptLabError", "PromptLabService", "EVALUATORS"]

DEFAULT_BASE_DIR = Path("var/prompt_lab")


class PromptLabError(Exception):
    """A safe, bounded Prompt Lab error."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


# --- deterministic evaluators (no model, no cost, production-read-only) -------


def _eval_model_policy_floors(config: dict, cases: list[dict]) -> list[MetricResult]:
    """Evaluate an alternative model-policy CONFIG against safety floors — production
    policy is never mutated (pure resolver only). §31."""
    from src.llm.models import ModelProfile
    from src.llm.policy import OPERATION_POLICY, ModelOperation, resolve_policy

    operation = config.get("operation", "orchestration")
    try:
        op = ModelOperation(operation)
    except ValueError:
        return [MetricResult(metric="operation_valid", value=0.0, passed=False,
                             detail=f"unknown operation '{operation}'")]
    floor = OPERATION_POLICY[op].min_capability
    order = {ModelProfile.FAST: 0, ModelProfile.BALANCED: 1, ModelProfile.ADVANCED: 2}
    respected = bounded = 1
    checked = 0
    profiles = cases or [{"user_profile": p.value} for p in ModelProfile]
    for c in profiles:
        prof = c.get("user_profile")
        try:
            rp = resolve_policy(op, ModelProfile(prof) if prof else None)
        except Exception:  # noqa: BLE001
            respected = 0
            continue
        checked += 1
        if rp.uses_model and order[rp.profile] < order[floor]:
            respected = 0
        if any(order[f] >= order[rp.profile] for f in rp.fallback_profiles):
            bounded = 0
    return [
        MetricResult(metric="operation_valid", value=1.0, passed=True),
        MetricResult(metric="capability_floor_respected", value=float(respected),
                     passed=bool(respected), detail=f"checked={checked}"),
        MetricResult(metric="fallback_bounded", value=float(bounded), passed=bool(bounded)),
    ]


def _eval_specialist_evidence_limit(config: dict, cases: list[dict]) -> list[MetricResult]:
    """Evaluate a specialist evidence-limit CONFIG: bounds + bounded output. §32."""
    from src.agent.specialists import run_evidence_specialist
    from src.agent.specialists.schemas import EvidenceRequest

    limit = config.get("evidence_limit", 8)
    in_bounds = 1 if isinstance(limit, int) and 1 <= limit <= 20 else 0

    class _Fake:
        def approved_claims(self, uid):
            return [{"id": i, "claim_type": "skill", "display_text": f"skill {i} roadmapping",
                     "source_page": 1, "review_state": "accepted"} for i in range(1, 31)]

        def evidence_stories(self, uid):
            return []

    bounded_output = 1
    if in_bounds:
        sel = run_evidence_specialist(
            EvidenceRequest(need="roadmapping", limit=limit), user_id=1, evidence_service=_Fake())
        bounded_output = 1 if len(sel.items) <= limit else 0
    return [
        MetricResult(metric="evidence_limit_in_bounds", value=float(in_bounds), passed=bool(in_bounds)),
        MetricResult(metric="output_bounded", value=float(bounded_output), passed=bool(bounded_output)),
    ]


EVALUATORS = {
    "model_policy_floors": _eval_model_policy_floors,
    "specialist_evidence_limit": _eval_specialist_evidence_limit,
}


class PromptLabService:
    def __init__(self, base_dir: Path | str = DEFAULT_BASE_DIR) -> None:
        self._dir = Path(base_dir) / "experiments"
        self._dir.mkdir(parents=True, exist_ok=True)

    # -- persistence ----------------------------------------------------------

    def _path(self, experiment_id: str) -> Path:
        safe = "".join(ch for ch in experiment_id if ch.isalnum() or ch in ("-", "_"))
        if not safe or safe != experiment_id:
            raise PromptLabError("Invalid experiment id.")
        return self._dir / f"{safe}.json"

    def _save(self, exp: Experiment) -> None:
        self._path(exp.experiment_id).write_text(
            exp.model_dump_json(indent=2), encoding="utf-8")

    def get(self, experiment_id: str) -> Experiment | None:
        path = self._path(experiment_id)
        if not path.is_file():
            return None
        return Experiment.model_validate_json(path.read_text(encoding="utf-8"))

    def list(self) -> list[dict]:
        out = []
        for p in sorted(self._dir.glob("*.json")):
            try:
                exp = Experiment.model_validate_json(p.read_text(encoding="utf-8"))
            except Exception:  # noqa: BLE001
                continue
            out.append({"experiment_id": exp.experiment_id, "title": exp.title,
                        "status": exp.status.value, "created_at": exp.created_at.isoformat(),
                        "variant_count": len(exp.variants), "run_count": len(exp.runs)})
        return out

    # -- lifecycle ------------------------------------------------------------

    def create_experiment(
        self, *, title: str, hypothesis: str, created_by: str,
        evaluation_set: EvaluationSet, variants: list[Variant],
    ) -> Experiment:
        if evaluation_set.evaluator not in EVALUATORS:
            raise PromptLabError(f"Unknown evaluator '{evaluation_set.evaluator}'.")
        if not variants:
            raise PromptLabError("An experiment needs at least one variant.")
        if sum(1 for v in variants if v.is_baseline) != 1:
            raise PromptLabError("Exactly one baseline variant is required.")
        exp = Experiment(
            experiment_id=uuid.uuid4().hex[:16], title=title, hypothesis=hypothesis,
            created_by=created_by, created_at=_now(),
            evaluation_set=evaluation_set, variants=variants,
        )
        self._save(exp)
        return exp

    def run_experiment(self, experiment_id: str) -> Experiment:
        """Run the fixed evaluation set against every variant with a DETERMINISTIC
        evaluator. Never mutates production configuration."""
        from src.config_versions import production_versions

        exp = self.get(experiment_id)
        if exp is None:
            raise PromptLabError("Experiment not found.")
        evaluator = EVALUATORS.get(exp.evaluation_set.evaluator)
        if evaluator is None:
            raise PromptLabError("Unknown evaluator.")
        versions = production_versions()
        exp.status = ExperimentStatus.RUNNING
        for variant in exp.variants:
            run = ExperimentRun(
                run_id=uuid.uuid4().hex[:16], variant_id=variant.variant_id,
                evaluation_set_id=exp.evaluation_set.evaluation_set_id,
                evaluation_set_version=exp.evaluation_set.version,
                started_at=_now(), production_versions=versions,
            )
            try:
                run.metrics = list(evaluator(variant.config, exp.evaluation_set.cases))
            except Exception as exc:  # noqa: BLE001 - a bad variant fails safely, not the run
                run.error = f"evaluator_error:{type(exc).__name__}"
            exp.runs.append(run)
        exp.status = ExperimentStatus.COMPLETED
        self._save(exp)
        return exp

    def add_review(self, experiment_id: str, *, reviewer_id: str, outcome: str,
                   reason: str | None = None) -> Experiment:
        exp = self.get(experiment_id)
        if exp is None:
            raise PromptLabError("Experiment not found.")
        exp.reviews.append(HumanReview(
            reviewer_id=reviewer_id, outcome=ReviewOutcome(outcome),
            reviewed_at=_now(), reason=reason))
        exp.status = ExperimentStatus.REVIEWED
        self._save(exp)
        return exp

    def record_promotion_decision(
        self, experiment_id: str, *, decided_by: str, outcome: str,
        winning_variant_id: str | None = None, rationale: str | None = None,
    ) -> Experiment:
        """Record a promotion RECOMMENDATION. It NEVER applies to production
        (``applied_to_production`` stays False); applying is separate engineering work."""
        exp = self.get(experiment_id)
        if exp is None:
            raise PromptLabError("Experiment not found.")
        if not exp.reviews:
            raise PromptLabError("A human review is required before a promotion decision.")
        exp.promotion = PromotionDecision(
            decided_by=decided_by, outcome=PromotionOutcome(outcome), decided_at=_now(),
            winning_variant_id=winning_variant_id, rationale=rationale,
            applied_to_production=False,
        )
        self._save(exp)
        return exp
