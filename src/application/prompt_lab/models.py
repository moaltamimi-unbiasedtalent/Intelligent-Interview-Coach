"""Prompt Lab data model (Capstone P6/E6).

A bounded, HUMAN-REVIEWED experiment framework isolated from production. It represents
experiments, variants, fixed evaluation sets, runs, metric results, human reviews and
promotion DECISIONS — but a promotion decision is only ever a RECOMMENDATION: nothing here
edits a production prompt, model policy, specialist routing, code or deployment. Applying
an approved change remains explicit, separate engineering work.

Every model is ``extra="forbid"`` so no unexpected/raw field can be smuggled in. No
secrets are stored; variant configs hold bounded PARAMETERS, never live production secrets.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

PROMPT_LAB_VERSION = "P6.E6.1"


class ExperimentStatus(str, Enum):
    DRAFT = "draft"
    RUNNING = "running"
    COMPLETED = "completed"
    REVIEWED = "reviewed"
    ARCHIVED = "archived"


class ReviewOutcome(str, Enum):
    APPROVE = "approve"      # approved as a RECOMMENDATION for engineering to consider
    REJECT = "reject"
    DEFER = "defer"


class PromotionOutcome(str, Enum):
    RECOMMEND_PROMOTE = "recommend_promote"
    RECOMMEND_HOLD = "recommend_hold"
    RECOMMEND_REJECT = "recommend_reject"


class Variant(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    variant_id: str = Field(min_length=1, max_length=64)
    label: str = Field(max_length=120)
    is_baseline: bool = False
    # Bounded PARAMETER config only (e.g. {"evidence_limit": 5, "model_operation": "..."}),
    # never production prompt text or secrets.
    config: dict[str, Any] = Field(default_factory=dict)
    notes: str | None = Field(default=None, max_length=1000)


class MetricResult(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    metric: str = Field(max_length=64)
    value: float
    passed: bool | None = None
    detail: str | None = Field(default=None, max_length=500)


class ExperimentRun(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    run_id: str
    variant_id: str
    evaluation_set_id: str
    evaluation_set_version: str
    started_at: datetime
    metrics: list[MetricResult] = Field(default_factory=list)
    # A safe snapshot of the production config versions AT RUN TIME (attribution, §16).
    production_versions: dict[str, str] = Field(default_factory=dict)
    error: str | None = None


class HumanReview(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    reviewer_id: str = Field(max_length=64)   # safe admin id only (never a candidate)
    outcome: ReviewOutcome
    reviewed_at: datetime
    reason: str | None = Field(default=None, max_length=1000)


class PromotionDecision(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    decided_by: str = Field(max_length=64)
    outcome: PromotionOutcome
    decided_at: datetime
    winning_variant_id: str | None = None
    rationale: str | None = Field(default=None, max_length=1000)
    # ALWAYS False — the Prompt Lab never applies a change to production (§15/§42).
    applied_to_production: bool = False


class EvaluationSet(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    evaluation_set_id: str = Field(min_length=1, max_length=64)
    version: str = Field(max_length=32)
    evaluator: str = Field(max_length=64)     # a registered DETERMINISTIC evaluator name
    description: str | None = Field(default=None, max_length=500)
    # Frozen, bounded, synthetic/approved cases only — never candidate-private content (§17).
    cases: list[dict[str, Any]] = Field(default_factory=list)


class Experiment(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    experiment_id: str = Field(min_length=1, max_length=64)
    title: str = Field(max_length=200)
    hypothesis: str = Field(max_length=2000)
    created_by: str = Field(max_length=64)    # safe admin id
    created_at: datetime
    status: ExperimentStatus = ExperimentStatus.DRAFT
    evaluation_set: EvaluationSet
    variants: list[Variant] = Field(default_factory=list)
    runs: list[ExperimentRun] = Field(default_factory=list)
    reviews: list[HumanReview] = Field(default_factory=list)
    promotion: PromotionDecision | None = None
    prompt_lab_version: str = PROMPT_LAB_VERSION
