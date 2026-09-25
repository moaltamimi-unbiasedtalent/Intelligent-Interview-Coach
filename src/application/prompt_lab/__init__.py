"""Bounded, human-reviewed Prompt Lab (Capstone P6/E6).

Experiments over prompt/model-policy/specialist/retrieval CONFIG variants, run against
fixed deterministic evaluation sets, isolated from production, with NO auto-promotion —
a promotion decision is only ever a recommendation. See ``models`` and ``service``.
"""

from src.application.prompt_lab.models import (
    EvaluationSet,
    Experiment,
    ExperimentStatus,
    HumanReview,
    MetricResult,
    PromotionDecision,
    PromotionOutcome,
    ReviewOutcome,
    Variant,
)
from src.application.prompt_lab.service import EVALUATORS, PromptLabError, PromptLabService

__all__ = [
    "EvaluationSet", "Experiment", "ExperimentStatus", "HumanReview", "MetricResult",
    "PromotionDecision", "PromotionOutcome", "ReviewOutcome", "Variant",
    "EVALUATORS", "PromptLabError", "PromptLabService",
]
