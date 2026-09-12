"""Offline Feedback Intelligence (Phase 7G).

Engineering/admin support — NOT candidate-facing, NOT a seventh Agent tool, NOT part of normal
Ask4Mo execution. Aggregates SAFE structured signals into findings, human-reviewed recommendations
and experiment proposals. It NEVER modifies production: no code/prompt/KB/config/Git writes, no
shell, no arbitrary network, no external-research execution. A human decides; an engineer
implements separately.
"""

from __future__ import annotations

from src.copilot.feedback_intelligence.analysis import AnalysisConfig
from src.copilot.feedback_intelligence.models import (
    ExperimentProposal,
    FeedbackFinding,
    FeedbackSignal,
    FeedbackSnapshot,
    ImprovementRecommendation,
    ReviewDecision,
)
from src.copilot.feedback_intelligence.service import FeedbackRunResult, run

__all__ = [
    "AnalysisConfig",
    "FeedbackSignal",
    "FeedbackSnapshot",
    "FeedbackFinding",
    "ImprovementRecommendation",
    "ExperimentProposal",
    "ReviewDecision",
    "FeedbackRunResult",
    "run",
]
