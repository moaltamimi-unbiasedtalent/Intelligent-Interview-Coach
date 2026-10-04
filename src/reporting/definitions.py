"""Code-defined reporting vocabulary (P10B-W10.12): the privacy floor, the fixed periods and the metric definitions an Admin can read.

REPORTING_MIN_COHORT is an ENGINEERING PRIVACY CONTROL. It is not an anonymisation guarantee, not a GDPR certification and not a legal threshold.
"""

from __future__ import annotations

from dataclasses import dataclass

REPORTING_MIN_COHORT = 5
SUPPRESSED_LABEL = "Suppressed: small cohort"

# Fixed, code-defined periods. No client-supplied date or SQL expression is ever accepted. ``None`` days = all time.
PERIODS: dict[str, int | None] = {"7d": 7, "30d": 30, "90d": 90, "all_time": None}
DEFAULT_PERIOD = "30d"

# Access-plan direction is only unambiguous for the code-defined plan families (see src/entitlements.py PLAN_CODES).
PLAN_ORDER: dict[str, int] = {"basic": 0, "premium": 1}

# Metric states shown to the Admin (text first, never colour only).
STATE_AVAILABLE = "available"
STATE_PARTIAL = "partial"
STATE_SUPPRESSED = "suppressed"
STATE_UNAVAILABLE = "unavailable"
STATE_NOT_CAPTURED = "not_captured"


@dataclass(frozen=True)
class MetricDef:
    metric_id: str
    label: str
    source: str
    definition: str
    cohort_policy: str      # "cohort" (suppressed below the floor) | "operational" (platform telemetry, no candidate cohort)
    coverage: str


def _m(metric_id, label, source, definition, cohort_policy, coverage) -> MetricDef:
    return MetricDef(metric_id, label, source, definition, cohort_policy, coverage)


HIST = "Historical, from authoritative rows"
SINCE = "Captured since first event (W10.12 onward)"

METRICS: tuple[MetricDef, ...] = (
    _m("registrations", "Registrations", "users.created_at (candidate accounts)", "Candidate accounts created in the period.", "cohort", HIST),
    _m("onboarding_completed", "Onboarding completed", "users.onboarding_completed_at", "Candidate accounts whose onboarding completion timestamp falls in the period.", "cohort", HIST),
    _m("onboarding_rate", "Onboarding completion of period registrants", "users.onboarding_completed_at", "Share of the period's registrants whose onboarding is completed today (current state; accounts that predate onboarding were back-filled as completed).", "cohort", HIST),
    _m("opportunities_created", "Opportunities created", "opportunities.created_at", "Opportunity rows created in the period.", "cohort", HIST),
    _m("prepare_started", "Prepare runs started", "preparation_runs (source=created)", "Runs registered in the ownership index in the period (index exists from W10.10; back-filled rows are excluded).", "cohort", "From the W10.10 index"),
    _m("prepare_ready_rate", "Prepare runs reaching ready", "preparation_runs.state", "Share of started runs whose state is ready.", "cohort", "From the W10.10 index"),
    _m("practice_started", "Practice sessions started", "interview_sessions + interviews", "Distinct Practice sessions created in the period (live sessions plus completed history; abandoned sessions pruned by retention are not recoverable).", "cohort", "Lower bound"),
    _m("practice_completed", "Practice sessions completed", "interviews.status", "Completed interviews in the period.", "cohort", HIST),
    _m("activation", "Product activation", "first of opportunity / prepare run / practice session", "A candidate's FIRST substantive product action (Opportunity, Prepare run or Practice session). An analytics definition, not an access or billing state.", "cohort", "Lower bound for Prepare and abandoned Practice"),
    _m("returning", "Returning candidates", "same three domains", "Candidates with substantive activity on at least two distinct UTC dates inside the period.", "cohort", "Lower bound"),
    _m("feedback", "Candidate feedback", "user_feedback (rating, category)", "Helpful / not helpful counts and safe categories. Comment text is never read.", "cohort", HIST),
    _m("evaluation_score", "Average answer evaluation score", "answers.evaluation overall_score (numeric field only)", "Mean of the numeric overall score of evaluated answers; no answer, narrative or report text is read.", "cohort", HIST),
    _m("retrieval_outcomes", "Retrieval outcomes", "operational_metric_events (retrieval)", "Evidence found versus abstained, per captured retrieval. No query or evidence is stored.", "operational", SINCE),
    _m("request_outcomes", "Request outcomes and latency", "operational_metric_events (request)", "Success / error counts and p50 / p95 latency for code-defined operations.", "operational", SINCE),
    _m("provider_calls", "Provider call outcomes", "operational_metric_events (provider_call)", "Observed real provider calls (success / failure category / latency). Nothing is probed for reporting.", "operational", SINCE),
    _m("ai_usage", "AI usage", "ai_usage_facts", "Model calls and known tokens with token coverage.", "cohort", SINCE),
    _m("ai_known_cost", "Known AI cost (USD, partial coverage)", "ai_usage_facts.cost_usd_micros", "Sum of costs that are KNOWN (reported or calculated). Unknown cost is never zero.", "cohort", SINCE),
    _m("access_plans", "Active access-plan assignments", "subscriptions", "Product access assignments by plan. Access assignments are NOT payments.", "cohort", HIST),
    _m("mock_mrr", "Mock MRR", "billing_provider_subscriptions + commercial terms", "MOCK. Active mock provider subscriptions with configured terms, normalised to a monthly amount, per currency.", "cohort", "Mock billing state"),
    _m("mock_arr", "Mock ARR", "billing_provider_subscriptions + commercial terms", "MOCK. The same subscriptions normalised to an annual amount, per currency.", "cohort", "Mock billing state"),
    _m("mock_failed_payments", "Failed mock payments", "billing_payments", "MOCK. Failed mock payments in the period.", "operational", "Mock billing state"),
)
