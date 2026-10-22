"""Command Center read model (package 03D1): a metric-registry-backed, READ-ONLY, aggregate-only view of platform health, AI operations, job queue health,
knowledge readiness, alerts, security signals and candidate activity.

Every figure here is a 03K ``MetricResult`` built with ``contract.build_result`` and checked with ``contract.check_result`` against a ``MetricDefinition`` that
this module registers (``validate_registry`` runs at import time and in the tests). The W10.12 rules are inherited, not re-invented:

* aggregates only: no identifier, e-mail, address, path, credential, free text or candidate content reaches a response (the response schemas are allowlists);
* candidate-derived figures are COHORT metrics: below ``REPORTING_MIN_COHORT`` they are suppressed (``value`` null, never the count), rates also need a
  non-small numerator and complement, and partitions get secondary suppression (``suppression.partition``);
* missing data is ``unavailable`` or ``not_captured``, never zero; unknown token and cost are excluded and the metric is labelled partial; cost is exact integer
  micro-USD (``cost_micro_usd``) and currencies are never combined (there is a single currency, USD, here);
* nothing is double counted: AI token and cost figures come ONLY from ``ai_usage_facts`` (one canonical unit per Agent run or Practice operation), while
  operation outcomes, retries and latency come ONLY from ``ai_operation_events`` (one logical operation); the two are never summed together. Platform request and
  provider-call telemetry comes ONLY from ``operational_metric_events`` (no identity). Candidate activity delegates to the existing ``ReportingService.product``
  so it equals ``/admin/reports/product`` by construction.

Nothing here writes, enqueues a job, calls a provider or model, probes a connection, or reads candidate content.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any, Callable, Iterable, Sequence

from sqlalchemy import func, select

from src.api.schemas.command_center import BreakdownOut, BucketOut, CommandCenterResponse, ComponentOut, MetricItemOut
from src.application import admin_permissions as perm
from src.persistence import (
    AIOperationEvent, AIUsageFact, AdminNotification, AuditEvent, Job, KnowledgeIndexRecord, KnowledgeSourceVersion, OperationalMetricEvent, utcnow,
)
from src.reporting import contract as K
from src.reporting import suppression as S
from src.reporting.contract import (
    CoverageRule, DimensionDefinition, MetricDefinition, MetricResult, Quantity, SourceRef, SuppressionPolicy, build_result, check_result, validate_registry,
)
from src.reporting.definitions import PERIODS, REPORTING_MIN_COHORT
from src.reporting.service import ReportingService, _iso, _pct, _utc

PRIVACY = ("Aggregates only. Candidate cohorts below the engineering privacy floor are suppressed (this is not an anonymisation guarantee). "
           "No candidate content, identifier, e-mail, address or credential is returned.")
_ALL = list(PERIODS)

# ------------------------------------------------------------------------------------------------------------------------------ dimensions
_EXTRA_DIMENSIONS: tuple[DimensionDefinition, ...] = (
    DimensionDefinition(dimension_id="model_profile", label="Model profile", description="Fast, Balanced or Advanced; never a provider slug.", kind="category", max_buckets=10),
    DimensionDefinition(dimension_id="failure_category", label="Failure category", description="Bounded, code-defined failure categories; never an error text.",
                        kind="category", max_buckets=40),
    DimensionDefinition(dimension_id="provider", label="Provider", description="Code-defined provider labels.", kind="category", max_buckets=20),
    DimensionDefinition(dimension_id="outcome", label="Outcome", description="Code-defined outcome vocabulary.", kind="category", max_buckets=20),
    DimensionDefinition(dimension_id="job_type", label="Job type", description="Code-defined background job types.", kind="category", max_buckets=60),
    DimensionDefinition(dimension_id="job_state", label="Job state", description="Code-defined job lifecycle states.", kind="category", max_buckets=10),
    DimensionDefinition(dimension_id="knowledge_state", label="Knowledge version state", description="Code-defined governed knowledge states.", kind="category", max_buckets=12),
    DimensionDefinition(dimension_id="index_state", label="Index record state", description="Code-defined index record states.", kind="category", max_buckets=6),
    DimensionDefinition(dimension_id="alert_category", label="Alert category", description="Code-defined alert categories.", kind="category", max_buckets=20),
    DimensionDefinition(dimension_id="severity", label="Severity", description="Code-defined severities.", kind="category", max_buckets=6),
    DimensionDefinition(dimension_id="security_category", label="Security event category", description="Code-defined security event categories.", kind="category", max_buckets=20),
)
DIMENSIONS: tuple[DimensionDefinition, ...] = tuple(K.DIMENSIONS) + _EXTRA_DIMENSIONS
_DIM = {d.dimension_id: d for d in DIMENSIONS}

# ------------------------------------------------------------------------------------------------------------------------------ definitions
_SECTIONS = ("health", "ai_operations", "jobs", "knowledge", "alerts", "security", "candidate_activity")
SECTION_TITLES = {"health": "Platform health", "ai_operations": "AI operations", "jobs": "Job queue health", "knowledge": "Knowledge readiness",
                  "alerts": "Alerts", "security": "Auth and security signals", "candidate_activity": "Candidate activity"}
# One EXISTING permission per section (no permission is added; the registry stays 44). Justification, in the route module docstring.
SECTION_PERMISSION = {"health": perm.OVERVIEW_READ, "ai_operations": perm.AI_READ, "jobs": perm.JOBS_READ, "knowledge": perm.KNOWLEDGE_READ,
                      "alerts": perm.SECURITY_READ, "security": perm.SECURITY_READ, "candidate_activity": perm.REPORTS_READ}
_SECTION_OF: dict[str, str] = {}


def _d(section: str, mid: str, label: str, description: str, *, src: tuple[str, str], num: tuple[str, str], den: tuple[str, str] | None = None, unit: str = "count",
       dims: Sequence[str] = (), cov: tuple[str, str], missing: str = "unavailable", cohort: bool = False) -> MetricDefinition:
    _SECTION_OF[mid] = section
    return MetricDefinition(
        metric_id=mid, label=label, description=description, source=SourceRef(kind=src[0], name=src[1]), numerator=Quantity(aggregation=num[0], subject=num[1]),
        denominator=Quantity(aggregation=den[0], subject=den[1]) if den else None, unit=unit, period_kinds=list(_ALL), dimensions_allowed=list(dims),
        coverage=CoverageRule(kind=cov[0], note=cov[1]),
        missing_behaviour=missing,
        suppression=SuppressionPolicy(kind="cohort", min_cohort=REPORTING_MIN_COHORT) if cohort else SuppressionPolicy(kind="operational"),
        permission_required=SECTION_PERMISSION[section])


_CUR = ("current_state", "Current state at read time; not a historical figure.")
_SINCE_OPS = ("since_first_event", "Captured since the first operational event (W10.12 onward); nothing is back-filled.")
_SINCE_USAGE = ("since_first_event", "Captured since the first AI usage fact (W10.12 onward); nothing is back-filled.")
_SINCE_AIOP = ("since_first_event", "Captured since the first AI operation event (W12.4D-P2-A onward); nothing is back-filled.")
_HIST = ("historical", "Historical, from authoritative rows in the period.")
_F, _Q = "fact_table", "named_query"

_NEW: tuple[MetricDefinition, ...] = (
    # ---- platform health (operational, no candidate cohort)
    _d("health", "platform_workers_active", "Background workers seen recently", "Workers whose heartbeat is recent. Queue depth never implies a healthy worker.",
       src=(_Q, "job_worker_heartbeats"), num=("count_distinct", "workers"), cov=_CUR),
    _d("health", "platform_paused_capabilities", "Paused capabilities", "Capabilities an operator has paused (durable state).", src=(_Q, "platform_pause_state"),
       num=("count", "paused_capabilities"), cov=_CUR),
    _d("health", "platform_request_failure_rate", "Request failure rate", "Share of captured requests that ended in a server error or unavailable outcome.",
       src=(_F, "operational_metric_events"), num=("count", "failed_requests"), den=("count", "requests"), unit="percent", cov=_SINCE_OPS, missing="not_captured"),
    _d("health", "platform_request_latency_p95_ms", "Request latency p95", "95th percentile (nearest rank) of captured request durations.",
       src=(_F, "operational_metric_events"), num=("p95", "request_duration"), unit="milliseconds", cov=_SINCE_OPS, missing="not_captured"),
    # ---- AI operations: usage facts (cohort)
    _d("ai_operations", "ai_op_usage_units", "AI usage units", "Canonical usage units: one per Agent run or Practice operation.", src=(_F, "ai_usage_facts"),
       num=("count", "usage_units"), dims=("workflow", "model_profile", "operation", "model"), cov=_SINCE_USAGE, missing="not_captured", cohort=True),
    _d("ai_operations", "ai_op_model_calls", "Model calls", "Model invocations captured in usage units.", src=(_F, "ai_usage_facts"), num=("sum", "model_calls"),
       dims=("workflow", "model_profile", "operation", "model"), cov=_SINCE_USAGE, missing="not_captured", cohort=True),
    _d("ai_operations", "ai_op_known_tokens", "Known tokens (partial coverage)", "Sum of KNOWN total tokens; units without token data are excluded, never counted as zero.",
       src=(_F, "ai_usage_facts"), num=("sum", "known_tokens"), unit="tokens", dims=("workflow", "model_profile", "operation", "model"), cov=_SINCE_USAGE,
       missing="not_captured", cohort=True),
    _d("ai_operations", "ai_op_token_coverage", "Token coverage", "Share of usage units that carry token data.", src=(_F, "ai_usage_facts"),
       num=("count", "units_with_tokens"), den=("count", "usage_units"), unit="percent", cov=_SINCE_USAGE, missing="not_captured", cohort=True),
    _d("ai_operations", "ai_op_known_cost", "Known cost (USD, partial coverage)", "Sum of KNOWN cost (reported or calculated); unknown cost is excluded and never zero. "
       "Exact integer micro-USD is carried in cost_micro_usd.", src=(_F, "ai_usage_facts"), num=("sum", "known_cost_usd"), unit="usd",
       dims=("workflow", "model_profile", "operation", "model"), cov=_SINCE_USAGE, missing="not_captured", cohort=True),
    _d("ai_operations", "ai_op_cost_coverage", "Cost coverage", "Share of usage units with a known cost.", src=(_F, "ai_usage_facts"),
       num=("count", "units_with_cost"), den=("count", "usage_units"), unit="percent", cov=_SINCE_USAGE, missing="not_captured", cohort=True),
    # ---- AI operations: logical operations (cohort)
    _d("ai_operations", "ai_op_operations", "AI operations", "Logical candidate AI operations (one per operation, not per provider attempt).",
       src=(_Q, "ai_operation_events"), num=("count", "operations"), dims=("workflow", "operation"), cov=_SINCE_AIOP, missing="not_captured", cohort=True),
    _d("ai_operations", "ai_op_failed_operations", "Failed AI operations", "Operations that ended in failure (the degradation count).", src=(_Q, "ai_operation_events"),
       num=("count", "failed_operations"), dims=("workflow", "operation", "failure_category"), cov=_SINCE_AIOP, missing="not_captured", cohort=True),
    _d("ai_operations", "ai_op_failure_rate", "AI operation failure rate", "Share of logical AI operations that failed.", src=(_Q, "ai_operation_events"),
       num=("count", "failed_operations"), den=("count", "operations"), unit="percent", dims=("workflow", "operation"), cov=_SINCE_AIOP, missing="not_captured", cohort=True),
    _d("ai_operations", "ai_op_retry_attempts", "Provider retry attempts", "Provider attempts beyond completed calls, from operations with exact attempt evidence only.",
       src=(_Q, "ai_operation_events"), num=("sum", "retry_attempts"), dims=("workflow", "operation"), cov=_SINCE_AIOP, missing="not_captured", cohort=True),
    _d("ai_operations", "ai_op_latency_p50_ms", "AI operation latency p50", "Median (nearest rank) of operation call latency where it was captured.",
       src=(_Q, "ai_operation_events"), num=("p50", "operation_latency"), unit="milliseconds", dims=("workflow",), cov=_SINCE_AIOP, missing="not_captured", cohort=True),
    _d("ai_operations", "ai_op_latency_p95_ms", "AI operation latency p95", "95th percentile (nearest rank) of operation call latency where it was captured.",
       src=(_Q, "ai_operation_events"), num=("p95", "operation_latency"), unit="milliseconds", dims=("workflow",), cov=_SINCE_AIOP, missing="not_captured", cohort=True),
    _d("ai_operations", "ai_op_limit_observed", "Would-be limit refusals (observe mode)", "Operations that exceeded a request ceiling while limits are observed, not enforced.",
       src=(_Q, "ai_operation_events"), num=("count", "limit_observed_operations"), dims=("workflow",), cov=_SINCE_AIOP, missing="not_captured", cohort=True),
    _d("ai_operations", "ai_op_model_fallbacks", "Model fallbacks", "Fallbacks to a lower model tier. No event records one today, so this is never reported as zero.",
       src=(_Q, "model_fallback_events"), num=("count", "fallback_events"), cov=("since_first_event", "No fallback event is captured."), missing="not_captured"),
    # ---- AI operations: platform provider-call telemetry (operational, no identity)
    _d("ai_operations", "ai_op_provider_calls", "Provider calls", "Observed real provider calls (no identity).", src=(_F, "operational_metric_events"),
       num=("count", "provider_call_events"), dims=("operation", "provider", "outcome"), cov=_SINCE_OPS, missing="not_captured"),
    _d("ai_operations", "ai_op_provider_failure_rate", "Provider call failure rate", "Share of observed provider calls that were not a success.",
       src=(_F, "operational_metric_events"), num=("count", "failed_provider_calls"), den=("count", "provider_call_events"), unit="percent", dims=("operation", "provider"),
       cov=_SINCE_OPS, missing="not_captured"),
    _d("ai_operations", "ai_op_provider_latency_p95_ms", "Provider call latency p95", "95th percentile (nearest rank) of provider call durations.",
       src=(_F, "operational_metric_events"), num=("p95", "provider_call_duration"), unit="milliseconds", cov=_SINCE_OPS, missing="not_captured"),
    # ---- job queue health (operational)
    _d("jobs", "jobs_queued", "Queued jobs", "Jobs waiting to be claimed.", src=(_Q, "job_queue"), num=("count", "queued_jobs"), dims=("job_type",), cov=_CUR),
    _d("jobs", "jobs_running", "Running jobs", "Jobs currently leased by a worker.", src=(_Q, "job_queue"), num=("count", "running_jobs"), dims=("job_type",), cov=_CUR),
    _d("jobs", "jobs_retry_waiting", "Jobs waiting to retry", "Queued jobs that already failed an attempt and wait for the next one.", src=(_Q, "job_queue"),
       num=("count", "retry_waiting_jobs"), cov=_CUR),
    _d("jobs", "jobs_stale_leases", "Stale leases", "Running jobs whose lease expired.", src=(_Q, "job_queue"), num=("count", "stale_leases"), cov=_CUR),
    _d("jobs", "jobs_failed_current", "Failed jobs", "Jobs currently in the failed state.", src=(_Q, "job_queue"), num=("count", "failed_jobs"), dims=("job_type",), cov=_CUR),
    _d("jobs", "jobs_oldest_ready_age_s", "Oldest ready job age", "Age of the oldest queued job that is ready to run.", src=(_Q, "job_queue"),
       num=("p95", "ready_age"), unit="seconds", cov=_CUR),
    _d("jobs", "jobs_workers_active", "Workers seen recently", "Workers whose heartbeat is recent.", src=(_Q, "job_worker_heartbeats"), num=("count_distinct", "workers"), cov=_CUR),
    _d("jobs", "jobs_finished", "Jobs finished in the period", "Jobs that succeeded or failed with a finish time in the period.", src=(_Q, "job_queue"),
       num=("count", "finished_jobs"), dims=("job_type", "job_state"), cov=_HIST),
    _d("jobs", "jobs_failure_rate", "Job failure rate", "Share of jobs finished in the period that failed.", src=(_Q, "job_queue"), num=("count", "failed_finished_jobs"),
       den=("count", "finished_jobs"), unit="percent", dims=("job_type",), cov=_HIST),
    _d("jobs", "jobs_duration_p95_s", "Job duration p95", "95th percentile (nearest rank) of run time of jobs finished in the period.", src=(_Q, "job_queue"),
       num=("p95", "job_duration"), unit="seconds", cov=_HIST),
    # ---- knowledge readiness (operational: registry state, no candidate cohort)
    _d("knowledge", "knowledge_versions", "Governed knowledge versions", "Versions in the governed registry by lifecycle state.", src=(_Q, "knowledge_registry"),
       num=("count", "knowledge_versions"), dims=("knowledge_state",), cov=_CUR),
    _d("knowledge", "knowledge_active_versions", "Active knowledge versions", "Versions currently serving governed retrieval.", src=(_Q, "knowledge_registry"),
       num=("count", "active_versions"), cov=_CUR),
    _d("knowledge", "knowledge_awaiting_review", "Versions awaiting review", "Versions parsed and waiting for a human decision.", src=(_Q, "knowledge_registry"),
       num=("count", "review_required_versions"), cov=_CUR),
    _d("knowledge", "knowledge_failed_versions", "Failed versions", "Versions whose parsing or indexing failed.", src=(_Q, "knowledge_registry"),
       num=("count", "failed_versions"), cov=_CUR),
    _d("knowledge", "knowledge_index_records", "Index records", "Index records by state (built, removed, removal failed).", src=(_Q, "knowledge_index"),
       num=("count", "index_records"), dims=("index_state",), cov=_CUR),
    _d("knowledge", "knowledge_open_alerts", "Open knowledge alerts", "Knowledge health alerts that are not resolved.", src=(_Q, "admin_alerts"),
       num=("count", "open_knowledge_alerts"), dims=("alert_category", "severity"), cov=_CUR),
    _d("knowledge", "knowledge_retrieval_outcomes", "Retrieval outcomes", "Captured retrievals by outcome (evidence found, abstained, error). No query or evidence is stored.",
       src=(_F, "operational_metric_events"), num=("count", "retrieval_events"), dims=("operation", "outcome"), cov=_SINCE_OPS, missing="not_captured"),
    _d("knowledge", "knowledge_retrieval_error_rate", "Retrieval error rate", "Share of captured retrievals that ended in an error.", src=(_F, "operational_metric_events"),
       num=("count", "retrieval_errors"), den=("count", "retrieval_events"), unit="percent", cov=_SINCE_OPS, missing="not_captured"),
    # ---- alerts
    _d("alerts", "alerts_unresolved", "Unresolved alerts", "Active and acknowledged alerts.", src=(_Q, "admin_alerts"), num=("count", "unresolved_alerts"),
       dims=("alert_category", "severity"), cov=_CUR),
    _d("alerts", "alerts_active_high", "Active high or critical alerts", "Active alerts of severity high or critical.", src=(_Q, "admin_alerts"),
       num=("count", "active_high_alerts"), cov=_CUR),
    _d("alerts", "alerts_opened", "Alerts first seen in the period", "Alerts whose first occurrence falls in the period.", src=(_Q, "admin_alerts"),
       num=("count", "opened_alerts"), dims=("alert_category", "severity"), cov=_HIST),
    _d("alerts", "alerts_resolved", "Alerts resolved in the period", "Alerts resolved in the period.", src=(_Q, "admin_alerts"), num=("count", "resolved_alerts"), cov=_HIST),
    # ---- auth and security signals (counts of audit rows; no actor, address or email)
    _d("security", "security_events", "Security events", "Security-relevant audit events in the period (successful sign-ins are not security events).",
       src=(_Q, "security_event_projection"), num=("count", "security_events"), dims=("security_category", "severity"), cov=_HIST),
    _d("security", "security_failed_logins", "Failed sign-ins", "Failed sign-in attempts recorded for a known account.", src=(_Q, "security_event_projection"),
       num=("count", "failed_logins"), cov=_HIST),
    _d("security", "security_access_denied", "Denied Admin access", "Admin requests refused for a missing permission.", src=(_Q, "security_event_projection"),
       num=("count", "access_denied"), cov=_HIST),
    _d("security", "security_step_up_failures", "Failed step-up attempts", "Failed step-up re-authentication attempts.", src=(_Q, "security_event_projection"),
       num=("count", "step_up_failures"), cov=_HIST),
    _d("security", "security_role_change_events", "Role-change events", "Role-change requests, approvals, rejections and cancellations.", src=(_Q, "security_event_projection"),
       num=("count", "role_change_events"), cov=_HIST),
    _d("security", "security_open_incidents", "Open incidents", "Incidents that are open, investigating or monitoring.", src=(_Q, "incident_register"),
       num=("count", "open_incidents"), cov=_CUR),
    _d("security", "security_anomaly_rules_firing", "Anomaly rules firing now", "Deterministic burst rules currently exceeding their threshold for a known account.",
       src=(_Q, "security_event_projection"), num=("count", "firing_rules"), cov=_CUR),
)

# Candidate activity delegates to the existing report service: contract id -> legacy report metric id.
_ACTIVITY: dict[str, str] = {
    "registrations": "registrations", "onboarding_completed": "onboarding_completed", "onboarding_rate": "onboarding_rate", "opportunities_created": "opportunities_created",
    "prepare_started": "prepare_started", "prepare_ready_rate": "prepare_ready_rate", "practice_started": "practice_started", "practice_completed": "practice_completed",
    "activation": "activated_candidates", "returning": "returning_candidates",
}
_ACTIVITY_DEFS = tuple(m for m in K.contract_metrics() if m.metric_id in _ACTIVITY)
for _m in _ACTIVITY_DEFS:
    _SECTION_OF[_m.metric_id] = "candidate_activity"

METRICS: tuple[MetricDefinition, ...] = _NEW + _ACTIVITY_DEFS
_DEF: dict[str, MetricDefinition] = {m.metric_id: m for m in METRICS}
validate_registry(METRICS, DIMENSIONS)                       # a duplicate, unknown dimension or unknown permission fails at import
assert set(_ACTIVITY) <= set(_DEF) and all(_SECTION_OF[m.metric_id] in _SECTIONS for m in METRICS)
assert all(m.permission_required == SECTION_PERMISSION[_SECTION_OF[m.metric_id]] for m in METRICS)


def metrics_for_section(section: str) -> tuple[MetricDefinition, ...]:
    return tuple(m for m in METRICS if _SECTION_OF[m.metric_id] == section)


def visible_definitions(permissions: frozenset[str]) -> tuple[tuple[MetricDefinition, ...], tuple[DimensionDefinition, ...]]:
    """The definitions a caller may see: only metrics whose own permission the caller holds, and only the dimensions those metrics use."""
    ms = tuple(m for m in METRICS if m.permission_required in permissions)
    used = {d for m in ms for d in m.dimensions_allowed}
    return ms, tuple(d for d in DIMENSIONS if d.dimension_id in used)


# ------------------------------------------------------------------------------------------------------------------------------ the service
def _evidence(result: MetricResult, defn: MetricDefinition) -> str:
    if result.state == "ok":
        if result.partial:
            return "partial"
        return "current_state" if defn.coverage.kind == "current_state" else "captured"
    return result.state


class CommandCenterService:
    """READ-ONLY. ``session_factory`` is the repository's; ``clock`` is injectable for deterministic tests."""

    def __init__(self, session_factory, *, clock: Callable[[], datetime] = utcnow, pause=None) -> None:
        self._sf = session_factory
        self._clock = clock
        self._pause = pause
        self._reports = ReportingService(session_factory, clock=clock)

    # ------------------------------------------------------------------ plumbing
    def window(self, period: str | None):
        from src.reporting.service import ReportingError

        try:
            return self._reports.window(period)
        except ReportingError as exc:
            raise ValueError(str(exc)) from exc

    def _mk(self, mid: str, period: str, value: Any, *, cohort: int | None = None, numerator: Any = None, denominator: Any = None, partial: bool = False,
            note: str = "", coverage: str | None = None, suppress: bool = False, breakdowns: Sequence[BreakdownOut] = (), cost_micros: int | None = None) -> MetricItemOut:
        defn = _DEF[mid]
        if suppress:
            result = MetricResult(metric_id=mid, period=period, state="suppressed", coverage=defn.coverage.note, note=note)
        else:
            result = build_result(defn, period, value, cohort=cohort, numerator=numerator, denominator=denominator, partial=partial, note=note)
        check_result(result, defn)
        if coverage and result.state == "ok":
            result = result.model_copy(update={"coverage": coverage})
        show = result.state == "ok"
        return MetricItemOut(
            **result.model_dump(), label=defn.label, unit=defn.unit, evidence=_evidence(result, defn), evidence_source=f"{defn.source.kind}:{defn.source.name}",
            suppression=defn.suppression.kind, dimensions=list(defn.dimensions_allowed), cost_micro_usd=cost_micros if show else None,
            breakdowns=list(breakdowns) if show else [])

    def _missing(self, mid: str, period: str, note: str) -> MetricItemOut:
        return self._mk(mid, period, None, note=note)

    def _envelope(self, section: str, period: str, since, now, metrics: list[MetricItemOut], components: list[ComponentOut] | None = None,
                  captured_since: str | None = None) -> CommandCenterResponse:
        return CommandCenterResponse(section_id=section, title=SECTION_TITLES[section], period=period, window_start=_iso(since), window_end=_iso(now), generated_at=_iso(now),
                                     privacy=PRIVACY, captured_since=captured_since, metrics=metrics, components=components or [])

    @staticmethod
    def _in(col, since, now):
        return ReportingService._in(col, since, now)

    @staticmethod
    def _breakdown(dim_id: str, groups: dict[str, list], value_fn: Callable[[list], Any], *, cohort_fn: Callable[[list], int] | None = None,
                   partial_fn: Callable[[list], bool] | None = None, operational: bool = False) -> BreakdownOut:
        """One dimension breakdown with primary + secondary suppression. A bucket whose value is unknown is ``unavailable`` (never zero)."""
        dim = _DIM[dim_id]
        keys = sorted(groups)[: dim.max_buckets]
        buckets = [{"label": k, "values": [value_fn(groups[k])], "cohort": (cohort_fn(groups[k]) if cohort_fn else 0)} for k in keys]
        rows = S.partition(buckets, operational=operational)
        out = []
        for k, row in zip(keys, rows):
            cell = row["cells"][0]
            if cell["suppressed"]:
                out.append(BucketOut(key=k, label=k, state="suppressed"))
            elif cell["figure"] is None:
                out.append(BucketOut(key=k, label=k, state="unavailable"))
            else:
                out.append(BucketOut(key=k, label=k, state="ok", value=cell["figure"], partial=bool(partial_fn(groups[k])) if partial_fn else False))
        return BreakdownOut(dimension_id=dim_id, label=dim.label, buckets=out)

    @staticmethod
    def _group(rows: Iterable, key_fn: Callable[[Any], str]) -> dict[str, list]:
        g: dict[str, list] = defaultdict(list)
        for r in rows:
            g[key_fn(r)].append(r)
        return g

    # ------------------------------------------------------------------ health
    def health(self, period: str | None = None) -> CommandCenterResponse:
        from src.application.admin_command_center import health_summary, migration_status, pause_state, rate_limit_mode
        from src.application.pause import PauseService, PauseStateUnavailable
        from src.jobs.service import JobService

        period, since, now = self.window(period)
        sec = "health"
        pause = self._pause or PauseService(self._sf)
        m: list[MetricItemOut] = []
        try:
            workers = JobService(self._sf).stats()["workers"]["seen_recently"]
            m.append(self._mk("platform_workers_active", period, int(workers)))
        except Exception:  # noqa: BLE001 - an unreadable source is unavailable, never zero
            m.append(self._missing("platform_workers_active", period, "Worker heartbeats cannot be read right now."))
        try:
            paused = pause.stats()["paused_count"]
            m.append(self._mk("platform_paused_capabilities", period, int(paused)))
        except PauseStateUnavailable:
            m.append(self._missing("platform_paused_capabilities", period, "The authoritative pause state cannot be read right now."))
        with self._sf() as s:
            base = self._in(OperationalMetricEvent.occurred_at, since, now)
            first = s.scalar(select(func.min(OperationalMetricEvent.occurred_at)))
            rows = s.execute(select(OperationalMetricEvent.outcome, OperationalMetricEvent.duration_ms).where(OperationalMetricEvent.event_type == "request", *base)).all()
        total = len(rows)
        failed = sum(1 for o, _dur in rows if o in ("server_error", "unavailable"))
        if total:
            m.append(self._mk("platform_request_failure_rate", period, round(100.0 * failed / total, 1), numerator=failed, denominator=total))
            ds = sorted(int(d) for _o, d in rows if d is not None)
            m.append(self._mk("platform_request_latency_p95_ms", period, _pct(ds, 0.95)) if ds else
                     self._missing("platform_request_latency_p95_ms", period, "No request duration was captured in the period."))
        else:
            why = "No request has been captured in this period." if first else "No request has been captured yet."
            m.append(self._missing("platform_request_failure_rate", period, why))
            m.append(self._missing("platform_request_latency_p95_ms", period, why))
        comps: list[ComponentOut] = []
        hs = health_summary(self._sf)
        comps.append(ComponentOut(component_id="database", label="Database", status="ok" if hs["database"] == "reachable" else "attention", evidence="current_state",
                                  note="Reachable (a cheap internal check)." if hs["database"] == "reachable" else "The database did not answer an internal check."))
        ms = migration_status(self._sf)
        comps.append(ComponentOut(component_id="migrations", label="Database migrations", status={"match": "ok", "mismatch": "attention"}.get(ms["state"], "unavailable"),
                                  evidence="current_state" if ms["state"] != "unknown" else "unavailable",
                                  note={"match": "The database revision matches the repository head.", "mismatch": "The database revision differs from the repository head.",
                                        }.get(ms["state"], "Migration state could not be determined.")))
        ps = pause_state(pause)
        comps.append(ComponentOut(component_id="pause", label="Operator pause", status={"running": "ok", "paused": "attention"}.get(ps["status"], "unavailable"),
                                  evidence="current_state" if ps["status"] in ("running", "paused") else "unavailable",
                                  note={"running": "Nothing is paused.", "paused": "At least one capability is paused."}.get(ps["status"], "The pause state cannot be read.")))
        rl = rate_limit_mode()
        comps.append(ComponentOut(component_id="rate_limit", label="Rate limiting", status="ok" if rl["distributed"] else "info", evidence="current_state",
                                  note="A shared store is active." if rl["distributed"] else "Limits are enforced per process, not shared across replicas."))
        comps.append(ComponentOut(component_id="providers", label="Provider health", status="info", evidence="current_state",
                                  note="Providers are not probed here; provider-call outcomes are shown only from observed real calls."))
        return self._envelope(sec, period, since, now, m, comps, captured_since=_iso(first))

    # ------------------------------------------------------------------ AI operations
    def ai_operations(self, period: str | None = None) -> CommandCenterResponse:
        from src.ai_protection import AI_COST_LIMITS_ENFORCED
        from src.application.pause import PauseService, PauseStateUnavailable
        from src.application.usage_quota import DEFAULT_POLICY, USAGE_QUOTAS_ENFORCED

        period, since, now = self.window(period)
        sec = "ai_operations"
        with self._sf() as s:
            facts = s.execute(select(AIUsageFact.user_id, AIUsageFact.workflow, AIUsageFact.operation, AIUsageFact.model_profile, AIUsageFact.model_id,
                                     AIUsageFact.model_calls, AIUsageFact.total_tokens, AIUsageFact.cost_usd_micros).where(
                *self._in(AIUsageFact.occurred_at, since, now))).all()
            first_fact = s.scalar(select(func.min(AIUsageFact.occurred_at)))
            ops = s.execute(select(AIOperationEvent.user_id, AIOperationEvent.workflow, AIOperationEvent.operation, AIOperationEvent.status, AIOperationEvent.failure_category,
                                   AIOperationEvent.provider_attempts, AIOperationEvent.attempt_coverage, AIOperationEvent.calls_ok, AIOperationEvent.calls_failed,
                                   AIOperationEvent.latency_ms, AIOperationEvent.limit_observed).where(*self._in(AIOperationEvent.started_at, since, now))).all()
            first_op = s.scalar(select(func.min(AIOperationEvent.started_at)))
            ev = s.execute(select(OperationalMetricEvent.operation, OperationalMetricEvent.provider, OperationalMetricEvent.outcome, OperationalMetricEvent.duration_ms).where(
                OperationalMetricEvent.event_type == "provider_call", *self._in(OperationalMetricEvent.occurred_at, since, now))).all()
            first_ev = s.scalar(select(func.min(OperationalMetricEvent.occurred_at)))
        m: list[MetricItemOut] = []
        users = lambda rs: len({r[0] for r in rs if r[0] is not None})   # noqa: E731

        # -- usage facts: tokens and cost come ONLY from here
        fact_ids = ("ai_op_usage_units", "ai_op_model_calls", "ai_op_known_tokens", "ai_op_token_coverage", "ai_op_known_cost", "ai_op_cost_coverage")
        if not facts:
            why = "No AI usage has been captured in this period." if first_fact else "No AI usage has been captured yet."
            m += [self._missing(i, period, why) for i in fact_ids]
        else:
            n, cohort = len(facts), users(facts)
            by = {"workflow": lambda r: r[1], "model_profile": lambda r: r[3] or "unknown", "operation": lambda r: r[2], "model": lambda r: r[4] or "unknown"}
            groups = {d: self._group(facts, fn) for d, fn in by.items()}
            tok = [r for r in facts if r[6] is not None]
            cost = [r for r in facts if r[7] is not None]

            def bds(value_fn, partial_fn=None, dims=("workflow", "model_profile", "operation", "model")):
                return [self._breakdown(d, groups[d], value_fn, cohort_fn=users, partial_fn=partial_fn) for d in dims]
            m.append(self._mk("ai_op_usage_units", period, n, cohort=cohort, breakdowns=bds(len)))
            m.append(self._mk("ai_op_model_calls", period, sum(r[5] for r in facts), cohort=cohort, breakdowns=bds(lambda g: sum(r[5] for r in g))))
            known_tokens = sum(r[6] for r in tok)
            tok_cov = round(100.0 * len(tok) / n, 1)
            m.append(self._mk("ai_op_known_tokens", period, known_tokens if tok else None, cohort=cohort, partial=len(tok) < n, coverage=f"Token coverage {tok_cov}% of usage units",
                              note="Units without token data are excluded, not counted as zero." if tok else "No usage unit in the period carries token data.",
                              breakdowns=bds(lambda g: sum(r[6] for r in g if r[6] is not None) if any(r[6] is not None for r in g) else None,
                                             lambda g: any(r[6] is None for r in g))))
            m.append(self._rate("ai_op_token_coverage", period, len(tok), n, cohort, note="Share of usage units that carry token data."))
            micros = sum(r[7] for r in cost)
            cost_cov = round(100.0 * len(cost) / n, 1)
            m.append(self._mk("ai_op_known_cost", period, round(micros / 1_000_000, 6) if cost else None, cohort=cohort, partial=len(cost) < n, cost_micros=micros if cost else None,
                              coverage=f"Cost coverage {cost_cov}% of usage units",
                              note="Known cost only (reported or calculated); unknown cost is excluded and never zero." if cost else "No usage unit in the period carries a known cost.",
                              breakdowns=bds(lambda g: round(sum(r[7] for r in g if r[7] is not None) / 1_000_000, 6) if any(r[7] is not None for r in g) else None,
                                             lambda g: any(r[7] is None for r in g))))
            m.append(self._rate("ai_op_cost_coverage", period, len(cost), n, cohort, note="Share of usage units with a known cost."))

        # -- logical operations: outcomes, retries and latency come ONLY from here
        op_ids = ("ai_op_operations", "ai_op_failed_operations", "ai_op_failure_rate", "ai_op_retry_attempts", "ai_op_latency_p50_ms", "ai_op_latency_p95_ms", "ai_op_limit_observed")
        if not ops:
            why = "No AI operation has been captured in this period." if first_op else "No AI operation has been captured yet."
            m += [self._missing(i, period, why) for i in op_ids]
        else:
            n, cohort = len(ops), users(ops)
            wf, opn = self._group(ops, lambda r: r[1]), self._group(ops, lambda r: r[2])
            failed = [r for r in ops if r[3] == "failed"]
            m.append(self._mk("ai_op_operations", period, n, cohort=cohort, breakdowns=[self._breakdown("workflow", wf, len, cohort_fn=users),
                                                                                       self._breakdown("operation", opn, len, cohort_fn=users)]))
            m.append(self._mk("ai_op_failed_operations", period, len(failed), cohort=cohort, breakdowns=[
                self._breakdown("workflow", self._group(failed, lambda r: r[1]), len, cohort_fn=users),
                self._breakdown("operation", self._group(failed, lambda r: r[2]), len, cohort_fn=users),
                self._breakdown("failure_category", self._group(failed, lambda r: r[4] or "unspecified"), len, cohort_fn=users)]))
            m.append(self._rate("ai_op_failure_rate", period, len(failed), n, cohort, note="Share of logical AI operations that failed.",
                                breakdowns=[self._breakdown("workflow", wf, lambda g: S.rate(sum(1 for r in g if r[3] == "failed"), len(g), cohort=users(g)),
                                                            cohort_fn=lambda g: users(g) if S.rate(sum(1 for r in g if r[3] == "failed"), len(g), cohort=users(g)) is not None else 0)]))
            exact = [r for r in ops if r[6] == "exact" and r[5] is not None]
            retries = sum(max(0, r[5] - (r[7] + r[8])) for r in exact)
            m.append(self._mk("ai_op_retry_attempts", period, retries if exact else None, cohort=cohort, partial=len(exact) < n,
                              coverage=f"Exact attempt evidence for {round(100.0 * len(exact) / n, 1)}% of operations",
                              note="Counted from operations with exact attempt evidence only." if exact else "No operation in the period has exact attempt evidence.",
                              breakdowns=[self._breakdown("workflow", self._group(exact, lambda r: r[1]), lambda g: sum(max(0, r[5] - (r[7] + r[8])) for r in g), cohort_fn=users)]))
            lat = sorted(int(r[9]) for r in ops if r[9] is not None)
            for mid, q in (("ai_op_latency_p50_ms", 0.5), ("ai_op_latency_p95_ms", 0.95)):
                m.append(self._mk(mid, period, _pct(lat, q) if lat else None, cohort=users([r for r in ops if r[9] is not None]), partial=len(lat) < n,
                                  note="" if lat else "No operation latency was captured in the period."))
            lim = [r for r in ops if r[10]]
            m.append(self._mk("ai_op_limit_observed", period, len(lim), cohort=cohort, note="Limits are observed, not enforced: nothing was refused.",
                              breakdowns=[self._breakdown("workflow", self._group(lim, lambda r: r[1]), len, cohort_fn=users)]))
        m.append(self._missing("ai_op_model_fallbacks", period, "No event records a fallback to a lower model tier, so none is reported (this is not zero)."))

        # -- platform provider-call telemetry (no identity, operational)
        if not ev:
            why = "No provider call has been captured in this period." if first_ev else "No provider call has been captured yet."
            m += [self._missing(i, period, why) for i in ("ai_op_provider_calls", "ai_op_provider_failure_rate", "ai_op_provider_latency_p95_ms")]
        else:
            n = len(ev)
            fail = sum(1 for r in ev if r[2] != "success")
            m.append(self._mk("ai_op_provider_calls", period, n, breakdowns=[
                self._breakdown("operation", self._group(ev, lambda r: r[0]), len, operational=True),
                self._breakdown("provider", self._group(ev, lambda r: r[1] or "unknown"), len, operational=True),
                self._breakdown("outcome", self._group(ev, lambda r: r[2]), len, operational=True)]))
            m.append(self._mk("ai_op_provider_failure_rate", period, round(100.0 * fail / n, 1), numerator=fail, denominator=n, breakdowns=[
                self._breakdown("operation", self._group(ev, lambda r: r[0]), lambda g: round(100.0 * sum(1 for r in g if r[2] != "success") / len(g), 1), operational=True),
                self._breakdown("provider", self._group(ev, lambda r: r[1] or "unknown"), lambda g: round(100.0 * sum(1 for r in g if r[2] != "success") / len(g), 1),
                                operational=True)]))
            ds = sorted(int(r[3]) for r in ev if r[3] is not None)
            m.append(self._mk("ai_op_provider_latency_p95_ms", period, _pct(ds, 0.95) if ds else None, partial=len(ds) < n,
                              note="" if ds else "No provider call duration was captured in the period."))

        comps = self._ai_components(AI_COST_LIMITS_ENFORCED, USAGE_QUOTAS_ENFORCED, DEFAULT_POLICY, PauseService, PauseStateUnavailable)
        firsts = [t for t in (first_fact, first_op, first_ev) if t is not None]
        return self._envelope(sec, period, since, now, m, comps, captured_since=_iso(min(firsts, key=_utc)) if firsts else None)

    def _rate(self, mid: str, period: str, num: int, den: int, cohort: int, *, note: str = "", breakdowns: Sequence[BreakdownOut] = ()) -> MetricItemOut:
        """A percentage honouring the W10.12 disclosure rule: a small denominator, numerator or complement suppresses it (state suppressed, never a count)."""
        rate = S.rate(num, den, cohort=cohort)
        if rate is None:
            return self._mk(mid, period, 0, suppress=True, note=note)
        return self._mk(mid, period, rate, cohort=cohort, numerator=num, denominator=den, note=note, breakdowns=breakdowns)

    def _ai_components(self, limits_enforced, quotas_enforced, quota_policy, pause_cls, unavailable_exc) -> list[ComponentOut]:
        comps: list[ComponentOut] = []
        try:
            from src.ai_admin.resolver import runtime_view

            rv = runtime_view()
            degraded = bool(rv.get("fallback_reason"))
            comps.append(ComponentOut(
                component_id="model_configuration", label="Model configuration", status="attention" if degraded else "ok", evidence="current_state",
                note=("A governed configuration could not be used, so the code defaults are in force." if degraded else
                      "A governed configuration is active." if rv.get("mode") == "governed" else "No governed configuration is active; the code defaults are in force.")))
        except Exception:  # noqa: BLE001
            comps.append(ComponentOut(component_id="model_configuration", label="Model configuration", status="unavailable", evidence="unavailable",
                                      note="The configuration state cannot be read right now."))
        comps.append(ComponentOut(component_id="ai_request_ceilings", label="AI request ceilings", status="info", evidence="current_state",
                                  note="Enforced: requests over a ceiling are refused." if limits_enforced else "Observe mode: ceilings are recorded, nothing is refused."))
        configured = bool(getattr(quota_policy, "allowances", None))
        comps.append(ComponentOut(component_id="usage_quotas", label="Usage quotas", status="info", evidence="current_state",
                                  note=("Enforced." if quotas_enforced else "Not enforced.") + (" An allowance policy is configured." if configured else " No allowance policy is configured.")))
        try:
            snap = pause_cls(self._sf).snapshot()
            for cap, st in sorted(snap.items()):
                comps.append(ComponentOut(component_id=f"pause_{cap}", label=f"Pause: {cap.replace('_', ' ')}", status="attention" if st["paused"] else "ok", evidence="current_state",
                                          note="Paused by an operator." if st["paused"] else "Running."))
        except unavailable_exc:
            comps.append(ComponentOut(component_id="pause", label="Operator pause", status="unavailable", evidence="unavailable", note="The pause state cannot be read right now."))
        return comps

    # ------------------------------------------------------------------ jobs
    def jobs(self, period: str | None = None) -> CommandCenterResponse:
        from src.jobs.service import JobService

        period, since, now = self.window(period)
        m: list[MetricItemOut] = []
        try:
            st = JobService(self._sf, clock=self._clock).stats(now=now)
        except Exception:  # noqa: BLE001
            st = None
        cur = ("jobs_queued", "jobs_running", "jobs_retry_waiting", "jobs_stale_leases", "jobs_failed_current", "jobs_oldest_ready_age_s", "jobs_workers_active")
        if st is None:
            m += [self._missing(i, period, "The job queue cannot be read right now.") for i in cur]
        else:
            q, by_type = st["queue"], st["by_type"]

            def per_type(state: str) -> list[BreakdownOut]:
                groups = {t["job_type"]: [t[state]] for t in by_type if t.get(state)}
                return [self._breakdown("job_type", groups, lambda g: g[0], operational=True)]
            m.append(self._mk("jobs_queued", period, q["queued"], breakdowns=per_type("queued")))
            m.append(self._mk("jobs_running", period, q["running"], breakdowns=per_type("running")))
            m.append(self._mk("jobs_retry_waiting", period, q["retry_waiting"]))
            m.append(self._mk("jobs_stale_leases", period, q["stale_leases"]))
            m.append(self._mk("jobs_failed_current", period, q["failed"], breakdowns=per_type("failed")))
            m.append(self._mk("jobs_oldest_ready_age_s", period, q["oldest_ready_age_seconds"]) if q["oldest_ready_age_seconds"] is not None else
                     self._missing("jobs_oldest_ready_age_s", period, "No queued job is ready to run, so there is no age to report."))
            m.append(self._mk("jobs_workers_active", period, st["workers"]["seen_recently"]))
        with self._sf() as s:
            rows = s.execute(select(Job.job_type, Job.state, Job.started_at, Job.finished_at).where(
                Job.state.in_(("succeeded", "failed")), Job.finished_at.is_not(None), *self._in(Job.finished_at, since, now))).all()
        if not rows:
            why = "No job finished in this period."
            m += [self._missing(i, period, why) for i in ("jobs_finished", "jobs_failure_rate", "jobs_duration_p95_s")]
        else:
            n, failed = len(rows), sum(1 for r in rows if r[1] == "failed")
            m.append(self._mk("jobs_finished", period, n, breakdowns=[self._breakdown("job_type", self._group(rows, lambda r: r[0]), len, operational=True),
                                                                      self._breakdown("job_state", self._group(rows, lambda r: r[1]), len, operational=True)]))
            m.append(self._mk("jobs_failure_rate", period, round(100.0 * failed / n, 1), numerator=failed, denominator=n, breakdowns=[
                self._breakdown("job_type", self._group(rows, lambda r: r[0]), lambda g: round(100.0 * sum(1 for r in g if r[1] == "failed") / len(g), 1), operational=True)]))
            durs = sorted(max(0.0, (_utc(r[3]) - _utc(r[2])).total_seconds()) for r in rows if r[2] is not None and r[3] is not None)
            m.append(self._mk("jobs_duration_p95_s", period, round(_pct(durs, 0.95), 3) if durs else None, partial=len(durs) < n,
                              note="" if durs else "No finished job has a start time."))
        return self._envelope("jobs", period, since, now, m)

    # ------------------------------------------------------------------ knowledge readiness
    def knowledge(self, period: str | None = None) -> CommandCenterResponse:
        period, since, now = self.window(period)
        V = KnowledgeSourceVersion
        with self._sf() as s:
            states = dict(s.execute(select(V.state, func.count()).group_by(V.state)).all())
            idx = dict(s.execute(select(KnowledgeIndexRecord.state, func.count()).group_by(KnowledgeIndexRecord.state)).all())
            alerts = s.execute(select(AdminNotification.category, AdminNotification.severity).where(
                AdminNotification.source_type == "knowledge", AdminNotification.state != "resolved")).all()
            ret = s.execute(select(OperationalMetricEvent.operation, OperationalMetricEvent.outcome).where(
                OperationalMetricEvent.event_type == "retrieval", *self._in(OperationalMetricEvent.occurred_at, since, now))).all()
            first_ret = s.scalar(select(func.min(OperationalMetricEvent.occurred_at)))
        m = [
            self._mk("knowledge_versions", period, sum(states.values()), breakdowns=[self._breakdown("knowledge_state", {k: [v] for k, v in states.items()}, lambda g: g[0], operational=True)]),
            self._mk("knowledge_active_versions", period, states.get("active", 0)),
            self._mk("knowledge_awaiting_review", period, states.get("review_required", 0)),
            self._mk("knowledge_failed_versions", period, states.get("failed", 0)),
            self._mk("knowledge_index_records", period, sum(idx.values()), breakdowns=[self._breakdown("index_state", {k: [v] for k, v in idx.items()}, lambda g: g[0], operational=True)]),
            self._mk("knowledge_open_alerts", period, len(alerts), breakdowns=[self._breakdown("alert_category", self._group(alerts, lambda r: r[0]), len, operational=True),
                                                                              self._breakdown("severity", self._group(alerts, lambda r: r[1]), len, operational=True)]),
        ]
        if ret:
            err = sum(1 for r in ret if r[1] == "error")
            m.append(self._mk("knowledge_retrieval_outcomes", period, len(ret), breakdowns=[self._breakdown("operation", self._group(ret, lambda r: r[0]), len, operational=True),
                                                                                          self._breakdown("outcome", self._group(ret, lambda r: r[1]), len, operational=True)]))
            m.append(self._mk("knowledge_retrieval_error_rate", period, round(100.0 * err / len(ret), 1), numerator=err, denominator=len(ret)))
        else:
            why = "No retrieval has been captured in this period." if first_ret else "No retrieval has been captured yet."
            m += [self._missing("knowledge_retrieval_outcomes", period, why), self._missing("knowledge_retrieval_error_rate", period, why)]
        active = states.get("active", 0)
        comps = [
            ComponentOut(component_id="governed_set", label="Governed knowledge set", status="ok" if active else "attention", evidence="current_state",
                         note="At least one governed version is active." if active else "No governed version is active, so governed retrieval contributes nothing."),
            ComponentOut(component_id="knowledge_alerts", label="Knowledge health alerts", status="attention" if alerts else "ok", evidence="current_state",
                         note="At least one knowledge health alert is unresolved." if alerts else "No knowledge health alert is unresolved."),
        ]
        return self._envelope("knowledge", period, since, now, m, comps)

    # ------------------------------------------------------------------ alerts
    def alerts(self, period: str | None = None) -> CommandCenterResponse:
        period, since, now = self.window(period)
        A = AdminNotification
        with self._sf() as s:
            unresolved = s.execute(select(A.category, A.severity, A.state).where(A.state != "resolved")).all()
            opened = s.execute(select(A.category, A.severity).where(*self._in(A.first_seen_at, since, now))).all()
            resolved = s.scalar(select(func.count()).select_from(A).where(A.state == "resolved", *self._in(A.resolved_at, since, now))) or 0
        high = sum(1 for _c, sv, st in unresolved if st == "active" and sv in ("high", "critical"))
        by = lambda rows, i: self._group(rows, lambda r: r[i])   # noqa: E731
        m = [
            self._mk("alerts_unresolved", period, len(unresolved), breakdowns=[self._breakdown("alert_category", by(unresolved, 0), len, operational=True),
                                                                              self._breakdown("severity", by(unresolved, 1), len, operational=True)]),
            self._mk("alerts_active_high", period, high),
            self._mk("alerts_opened", period, len(opened), breakdowns=[self._breakdown("alert_category", by(opened, 0), len, operational=True),
                                                                      self._breakdown("severity", by(opened, 1), len, operational=True)]),
            self._mk("alerts_resolved", period, int(resolved)),
        ]
        return self._envelope("alerts", period, since, now, m)

    # ------------------------------------------------------------------ security signals
    def security(self, period: str | None = None) -> CommandCenterResponse:
        from src.admin_security import definitions as D
        from src.admin_security.events import SecurityEventService
        from src.application import admin_audit as AU

        period, since, now = self.window(period)
        types = list(D.SECURITY_EVENT_TYPES)
        with self._sf() as s:
            rows = s.execute(select(AuditEvent.event_type, AuditEvent.result).where(AuditEvent.event_type.in_(types), *self._in(AuditEvent.created_at, since, now))).all()
        # a successful sign-in is an authentication event but not a security event (same rule as the Security events list)
        rows = [r for r in rows if not (r[0] == "account.login" and r[1] == "success")]
        cat = lambda r: D.SECURITY_EVENT_TYPES[r[0]][0]   # noqa: E731
        sev = lambda r: D.SECURITY_EVENT_TYPES[r[0]][1]   # noqa: E731
        count = lambda t: sum(1 for r in rows if r[0] == t)   # noqa: E731
        m = [
            self._mk("security_events", period, len(rows), breakdowns=[self._breakdown("security_category", self._group(rows, cat), len, operational=True),
                                                                       self._breakdown("severity", self._group(rows, sev), len, operational=True)]),
            self._mk("security_failed_logins", period, count("account.login")),
            self._mk("security_access_denied", period, count(AU.ADMIN_ACCESS_DENIED)),
            self._mk("security_step_up_failures", period, count(AU.ADMIN_STEP_UP_FAILED)),
            self._mk("security_role_change_events", period, sum(1 for r in rows if cat(r) == "role_change")),
        ]
        try:
            from src.admin_security.incidents import IncidentService

            m.append(self._mk("security_open_incidents", period, IncidentService(self._sf).open_count()))
        except Exception:  # noqa: BLE001
            m.append(self._missing("security_open_incidents", period, "The incident register cannot be read right now."))
        try:
            m.append(self._mk("security_anomaly_rules_firing", period, len({a.get("rule") for a in SecurityEventService(self._sf).anomalies()})))
        except Exception:  # noqa: BLE001
            m.append(self._missing("security_anomaly_rules_firing", period, "The anomaly rules cannot be evaluated right now."))
        return self._envelope("security", period, since, now, m)

    # ------------------------------------------------------------------ candidate activity
    def candidate_activity(self, period: str | None = None) -> CommandCenterResponse:
        period, since, now = self.window(period)
        report = self._reports.product(period)
        legacy = {x["metric_id"]: x for x in report["sections"][0]["metrics"]}
        m: list[MetricItemOut] = []
        for cid, lid in _ACTIVITY.items():
            defn = _DEF[cid]
            result = K.result_from_legacy(legacy[lid], period)
            result = result.model_copy(update={"metric_id": cid})
            check_result(result, defn)
            m.append(MetricItemOut(**result.model_dump(), label=defn.label, unit=defn.unit, evidence=_evidence(result, defn), evidence_source=f"{defn.source.kind}:{defn.source.name}",
                                   suppression=defn.suppression.kind, dimensions=[]))
        return self._envelope("candidate_activity", period, since, now, m)


SECTION_METHODS = {"health": "health", "ai_operations": "ai_operations", "jobs": "jobs", "knowledge": "knowledge", "alerts": "alerts", "security": "security",
                   "candidate_activity": "candidate_activity"}
