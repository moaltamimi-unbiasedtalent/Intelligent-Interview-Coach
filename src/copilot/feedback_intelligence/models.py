"""Typed contract for the OFFLINE Feedback Intelligence workflow (Phase 7G).

This is engineering/admin support — NOT candidate-facing, NOT a seventh Agent tool, and NOT part
of normal Ask4Mo execution. It converts SAFE, STRUCTURED signals into findings, human-reviewed
recommendations and experiment proposals. It never contains raw candidate content, and it never
modifies production: a human decides, an engineer implements separately.

Every model is ``extra="forbid"`` so a raw-text/candidate field can never be smuggled in.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

ANALYSIS_VERSION = "7G.1"


# --- controlled vocabularies ----------------------------------------------------------

class SignalType(str, Enum):
    USER_FEEDBACK = "user_feedback"
    AGENT_EVALUATION = "agent_evaluation"
    RETRIEVAL_EVALUATION = "retrieval_evaluation"
    RAGAS_EVALUATION = "ragas_evaluation"
    KNOWLEDGE_COVERAGE = "knowledge_coverage"
    EXTERNAL_RESEARCH_EVALUATION = "external_research_evaluation"
    INTERVIEW_PRACTICE_OPERATION = "interview_practice_operation"
    PROVIDER_OPERATION = "provider_operation"
    OBSERVABILITY_AGGREGATE = "observability_aggregate"
    ERROR_CATEGORY = "error_category"


class FindingCategory(str, Enum):
    QUALITY = "quality"
    RETRIEVAL = "retrieval"
    GROUNDING = "grounding"
    CITATION = "citation"
    GEOGRAPHY = "geography"
    KNOWLEDGE_GAP = "knowledge_gap"
    TOOL_SELECTION = "tool_selection"
    EXTERNAL_RESEARCH = "external_research"
    LATENCY = "latency"
    RELIABILITY = "reliability"
    PROVIDER_FAILURE = "provider_failure"
    INTERVIEW_PRACTICE = "interview_practice"
    UX_SIGNAL = "ux_signal"
    COST = "cost"
    SAFETY = "safety"


class Severity(str, Enum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Confidence(str, Enum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"


class FindingStatus(str, Enum):
    POSITIVE = "positive"                    # something is working well (§22)
    OBSERVATION_ONLY = "observation_only"    # below support threshold (§17)
    PATTERN = "pattern"
    RECOMMENDATION_ELIGIBLE = "recommendation_eligible"


class ChangeArea(str, Enum):
    KNOWLEDGE = "knowledge"
    RETRIEVAL = "retrieval"
    RESOLVER = "resolver"
    TOOL_POLICY = "tool_policy"
    PROMPT = "prompt"
    UX = "ux"
    OBSERVABILITY = "observability"
    EXTERNAL_RESEARCH = "external_research"
    INTERVIEW_PRACTICE = "interview_practice"
    PROVIDER = "provider"
    PERFORMANCE = "performance"
    EVALUATION = "evaluation"
    SECURITY = "security"


class ReviewOutcome(str, Enum):
    APPROVE = "approve"      # approved for an engineer to CONSIDER — never auto-executes (§36)
    REJECT = "reject"
    DEFER = "defer"


# --- signal ---------------------------------------------------------------------------

class FeedbackSignal(BaseModel):
    """One safe, structured signal. NO raw candidate content, NO free text (§8/§9)."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    signal_id: str = Field(min_length=1)
    signal_type: SignalType
    source: str = Field(min_length=1)
    observed_at: datetime | None = None
    run_id_hash: str | None = None           # pseudonymous / opaque only (§10)
    session_id_hash: str | None = None
    operation: str | None = None
    domain: str | None = None
    tool_name: str | None = None
    model_profile: str | None = None
    geography: str | None = None
    rating: str | None = None                # helpful | not_helpful | None (structured only)
    outcome: str | None = None               # success | insufficient_evidence | error | ...
    error_category: str | None = None        # sanitized category only (§58)
    latency_bucket: str | None = None        # fast | normal | slow (bucketed, §59)
    token_bucket: str | None = None
    retrieval_used: bool | None = None
    external_research_used: bool | None = None
    insufficient_evidence: bool | None = None
    citation_count: int | None = None
    source_count: int | None = None
    metric_name: str | None = None
    metric_value: float | None = None
    metric_dataset_hash: str | None = None   # provenance for metric comparison (§25)
    metric_version: str | None = None
    structured_feedback_category: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class FeedbackSnapshot(BaseModel):
    """Immutable analysis snapshot — makes recommendations reproducible (§13)."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    snapshot_id: str
    created_at: datetime
    window_start: datetime | None = None
    window_end: datetime | None = None
    signal_count: int = 0
    signal_sources: list[str] = Field(default_factory=list)
    source_versions: dict[str, str] = Field(default_factory=dict)
    git_sha: str | None = None
    git_dirty: bool | None = None
    input_hashes: dict[str, str] = Field(default_factory=dict)
    analysis_version: str = ANALYSIS_VERSION
    config: dict[str, Any] = Field(default_factory=dict)


class FeedbackFinding(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    finding_id: str
    title: str
    category: FindingCategory
    description: str
    signal_type: SignalType
    affected_operation: str | None = None
    affected_domain: str | None = None
    support_count: int = 0
    sample_size: int = 0
    rate: float | None = None
    baseline_rate: float | None = None
    change_vs_baseline: float | None = None
    confidence: Confidence = Confidence.LOW
    severity: Severity = Severity.INFO
    status: FindingStatus = FindingStatus.OBSERVATION_ONLY
    evidence_refs: list[str] = Field(default_factory=list)
    first_seen: datetime | None = None
    last_seen: datetime | None = None
    limitations: list[str] = Field(default_factory=list)
    positive: bool = False


class ImprovementRecommendation(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    recommendation_id: str
    finding_ids: list[str]
    title: str
    problem_statement: str
    change_area: ChangeArea
    recommendation: str
    expected_benefit: str
    risk: str
    priority: int = Field(ge=0, le=100)
    confidence: Confidence
    severity: Severity
    support_count: int = 0
    validation_plan: str
    rollback_plan: str
    requires_human_approval: bool = True
    complete: bool = True                    # §69: all quality fields present
    status: str = "awaiting_review"
    created_at: datetime | None = None


class ExperimentProposal(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    experiment_id: str
    recommendation_id: str
    hypothesis: str
    change_scope: str
    target_metric: str
    baseline: str | None = None
    success_criteria: str
    guardrail_metrics: list[str] = Field(default_factory=list)
    test_dataset: str | None = None
    estimated_risk: str = "unknown"
    rollback_condition: str
    estimated_effort: str = "unknown"
    status: str = "proposed"


class ReviewDecision(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    proposal_id: str                         # recommendation_id (or experiment_id)
    decision: ReviewOutcome
    reviewed_at: datetime
    reviewer_id: str | None = None           # safe admin identifier only (never a candidate)
    reason: str | None = Field(default=None, max_length=500)
    executed: bool = False                   # ALWAYS False — approval never executes (§36)
