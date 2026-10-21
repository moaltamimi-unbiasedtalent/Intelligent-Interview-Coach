"""Admin metric and report contract (package 03K). A TYPED, DECLARATIVE interface for the Admin dashboard (03D1) and the report builder (03E1).

This module adds NO metric, route, permission or behaviour. It defines the shapes those packages implement against, the registry validation they must pass and the
``MetricResult`` they must return. Invariants enforced here (and by ``tests/contracts/test_admin_metric_contract_03k.py``):

* The contract is data: a metric names a registered SOURCE (a named query or a fact table) and describes numerator/denominator as a closed aggregation plus a slug
  subject. No SQL text, column name, expression or free-text query is accepted anywhere (``reject_sql_like``; slugs cannot contain a dot).
* Missing data is ``unavailable`` or ``not_captured``, never zero. A ``MetricResult`` that is not ``ok`` carries ``value = None``, numerator and denominator ``None``.
* A cohort metric is suppressed below ``REPORTING_MIN_COHORT`` (a definition can raise the minimum, never lower it); a suppressed result never carries the count.
* Aggregates only: there is no per-user, raw-row or event-list shape in the contract.
"""

from __future__ import annotations

import re
from typing import Annotated, Any, Final, Literal, Sequence

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

from src.application import admin_permissions as perm
from src.reporting.definitions import (
    DEFAULT_PERIOD, METRICS, PERIODS, REPORTING_MIN_COHORT, STATE_AVAILABLE, STATE_NOT_CAPTURED, STATE_PARTIAL, STATE_SUPPRESSED, STATE_UNAVAILABLE, MetricDef,
)

# --------------------------------------------------------------------------------------------------------------------------- vocab
Unit = Literal["count", "percent", "ratio", "score", "seconds", "hours", "milliseconds", "tokens", "usd"]
PeriodKind = Literal["7d", "30d", "90d", "all_time"]
MissingBehaviour = Literal["unavailable", "not_captured"]
MetricState = Literal["ok", "suppressed", "unavailable", "not_captured"]
ChartKind = Literal["trend", "funnel", "share_of_whole", "distribution", "table"]
ComparisonMode = Literal["none", "previous_period"]
SourceKind = Literal["named_query", "fact_table"]
Aggregation = Literal["count", "count_distinct", "sum", "mean", "p50", "p95", "ratio"]
CoverageKind = Literal["historical", "since_first_event", "lower_bound", "from_index", "current_state", "mock_state"]
SuppressionKind = Literal["cohort", "operational"]
DimensionKind = Literal["time", "category"]

# Registered fact tables. A package adding a metric over a new fact adds its NAME here (a reviewed change); it never passes a table, column or query string.
SOURCE_CATALOG: Final[frozenset[str]] = frozenset({
    "users", "opportunities", "preparation_runs", "interview_sessions", "interviews", "user_feedback", "answers", "operational_metric_events", "ai_usage_facts",
    "subscriptions", "billing_provider_subscriptions", "billing_payments",
})
PERIOD_KINDS: Final[tuple[str, ...]] = tuple(PERIODS)

Slug = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]{0,63}$")]
Text = Annotated[str, StringConstraints(min_length=1, max_length=400)]

_SQL_LIKE = re.compile(
    r"(;\s*(\Z|select|insert|update|delete|drop|alter|truncate|create)|--|/\*|\*/|\\x|`"
    r"|\b(select|insert|update|delete|drop|alter|truncate|create|grant|union|exec|execute|pragma)\b\s+[\w*(]"
    r"|\bfrom\s+[\w\"]+(\.\w+)?\s+(where|join|group|order|limit)\b"
    r"|\b(where|having)\s+[\w.]+\s*(=|<|>|\bin\b|\blike\b)"
    r"|\b\w+\.\w+\s*(=|<|>|\bis\b|\bin\b|\blike\b)"
    r"|\b(or|and)\s+\d+\s*=\s*\d+)", re.IGNORECASE)


class ContractError(ValueError):
    """Registry validation failed; ``problems`` lists every violation."""

    def __init__(self, problems: Sequence[str]) -> None:
        self.problems = list(problems)
        super().__init__("; ".join(self.problems))


def reject_sql_like(value: str) -> str:
    """The contract carries descriptions, never queries: SQL-like text is rejected in EVERY string field."""
    if _SQL_LIKE.search(value):
        raise ValueError("SQL-like text is not accepted in the metric contract")
    return value


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    @field_validator("*", mode="after")
    @classmethod
    def _no_sql(cls, v: Any) -> Any:
        if isinstance(v, str):
            reject_sql_like(v)
        elif isinstance(v, (list, tuple)):
            for item in v:
                if isinstance(item, str):
                    reject_sql_like(item)
        return v


# ----------------------------------------------------------------------------------------------------------------- definitions
class SourceRef(_Strict):
    kind: SourceKind
    name: Slug

    @model_validator(mode="after")
    def _registered(self) -> "SourceRef":
        if self.kind == "fact_table" and self.name not in SOURCE_CATALOG:
            raise ValueError(f"unknown fact table '{self.name}' (not in SOURCE_CATALOG)")
        return self


class Quantity(_Strict):
    """One side of a metric: a closed aggregation over a slug subject (e.g. count_distinct of ``candidate_accounts``). Never a column or expression."""
    aggregation: Aggregation
    subject: Slug


class CoverageRule(_Strict):
    kind: CoverageKind
    note: Text


class SuppressionPolicy(_Strict):
    kind: SuppressionKind
    min_cohort: int | None = None

    @model_validator(mode="after")
    def _floor(self) -> "SuppressionPolicy":
        if self.kind == "cohort":
            if self.min_cohort is None or self.min_cohort < REPORTING_MIN_COHORT:
                raise ValueError(f"a cohort metric must suppress below at least REPORTING_MIN_COHORT ({REPORTING_MIN_COHORT})")
        elif self.min_cohort is not None:
            raise ValueError("an operational metric has no candidate cohort, so no minimum cohort")
        return self


class DimensionDefinition(_Strict):
    dimension_id: Slug
    label: Text
    description: Text
    kind: DimensionKind
    max_buckets: int = Field(default=50, ge=1, le=500)


class MetricDefinition(_Strict):
    metric_id: Slug
    label: Text
    description: Text
    source: SourceRef
    numerator: Quantity
    denominator: Quantity | None = None
    unit: Unit
    period_kinds: list[PeriodKind] = Field(min_length=1)
    dimensions_allowed: list[Slug] = Field(default_factory=list)
    coverage: CoverageRule
    missing_behaviour: MissingBehaviour
    suppression: SuppressionPolicy
    permission_required: str

    @model_validator(mode="after")
    def _shape(self) -> "MetricDefinition":
        if len(set(self.period_kinds)) != len(self.period_kinds):
            raise ValueError("period_kinds must be unique")
        if len(set(self.dimensions_allowed)) != len(self.dimensions_allowed):
            raise ValueError("dimensions_allowed must be unique")
        if self.permission_required not in perm.PERMISSION_SET:
            raise ValueError(f"unknown permission '{self.permission_required}'")
        if self.unit in ("percent", "ratio") and self.denominator is None:
            raise ValueError("a percent or ratio metric must declare its denominator")
        return self


class DateRangeRule(_Strict):
    allowed_periods: list[PeriodKind] = Field(min_length=1)
    default_period: PeriodKind
    allow_custom_range: bool = False       # today no client-supplied date is accepted; enabling it requires a bound
    max_custom_days: int | None = Field(default=None, ge=1, le=3660)

    @model_validator(mode="after")
    def _rules(self) -> "DateRangeRule":
        if self.default_period not in self.allowed_periods:
            raise ValueError("default_period must be one of allowed_periods")
        if self.allow_custom_range != (self.max_custom_days is not None):
            raise ValueError("a custom range requires max_custom_days, and max_custom_days requires allow_custom_range")
        return self


class ChartSpec(_Strict):
    chart_id: Slug
    kind: ChartKind
    metric_ids: list[Slug] = Field(min_length=1)
    dimension_id: Slug | None = None
    title: Text


class ReportDefinition(_Strict):
    report_id: Slug
    title: Text
    description: Text
    metric_ids: list[Slug] = Field(min_length=1)       # ordered
    allowed_filters: list[Slug] = Field(default_factory=list)
    date_range: DateRangeRule
    comparison_modes: list[ComparisonMode] = Field(default_factory=lambda: ["none"])
    charts: list[ChartSpec] = Field(default_factory=list)
    permission_required: str

    @model_validator(mode="after")
    def _shape(self) -> "ReportDefinition":
        if len(set(self.metric_ids)) != len(self.metric_ids):
            raise ValueError("metric_ids must be unique")
        if "none" not in self.comparison_modes or len(set(self.comparison_modes)) != len(self.comparison_modes):
            raise ValueError("comparison_modes must be unique and include 'none'")
        if len({c.chart_id for c in self.charts}) != len(self.charts):
            raise ValueError("chart ids must be unique within a report")
        if self.permission_required not in perm.PERMISSION_SET:
            raise ValueError(f"unknown permission '{self.permission_required}'")
        return self


# ----------------------------------------------------------------------------------------------------------------------- result
class MetricResult(_Strict):
    """What an implementation returns for one metric. Missing data is a STATE with ``value = None``, never a bare zero."""
    metric_id: Slug
    period: PeriodKind
    state: MetricState
    value: int | float | str | None = None
    numerator: int | float | None = None
    denominator: int | float | None = None
    coverage: str = ""
    partial: bool = False
    note: str = ""

    @model_validator(mode="after")
    def _missing_is_never_zero(self) -> "MetricResult":
        if self.state == "ok":
            if self.value is None:
                raise ValueError("an ok result needs a value (use state 'unavailable' or 'not_captured' for missing data)")
        else:
            if self.value is not None or self.numerator is not None or self.denominator is not None:
                raise ValueError(f"a '{self.state}' result carries no value, numerator or denominator (never a zero or a hidden count)")
            if self.partial:
                raise ValueError("only an ok result can be partial")
        return self


# -------------------------------------------------------------------------------------------------------------- compatibility
_AMOUNT_UNITS = {"count", "usd", "tokens"}


def chart_problems(chart: ChartSpec, metrics: dict[str, MetricDefinition], dimensions: dict[str, DimensionDefinition]) -> list[str]:
    """Chart kind must fit the MEANING of the metrics (trend over time, funnel of counts, share of a whole, distribution, table)."""
    out: list[str] = []
    ms = [metrics[i] for i in chart.metric_ids if i in metrics]
    dim = dimensions.get(chart.dimension_id) if chart.dimension_id else None
    tag = f"chart '{chart.chart_id}'"
    if chart.dimension_id and dim is None:
        out.append(f"{tag}: unknown dimension '{chart.dimension_id}'")
    for m in ms:
        if chart.dimension_id and chart.dimension_id not in m.dimensions_allowed:
            out.append(f"{tag}: metric '{m.metric_id}' does not allow dimension '{chart.dimension_id}'")
    if chart.kind == "trend":
        if dim is None or dim.kind != "time":
            out.append(f"{tag}: a trend needs a time dimension")
        if len({m.unit for m in ms}) > 1:
            out.append(f"{tag}: a trend must not mix units")
    elif chart.kind == "funnel":
        if len(ms) < 2 or any(m.unit != "count" for m in ms):
            out.append(f"{tag}: a funnel needs at least two count metrics")
        if chart.dimension_id:
            out.append(f"{tag}: a funnel has no dimension")
    elif chart.kind == "share_of_whole":
        if len(ms) != 1 or ms[0].unit not in _AMOUNT_UNITS:
            out.append(f"{tag}: a share-of-whole needs exactly one additive metric (count, usd or tokens), never a rate")
        if dim is None or dim.kind != "category":
            out.append(f"{tag}: a share-of-whole needs a category dimension")
    elif chart.kind == "distribution":
        if len(ms) != 1:
            out.append(f"{tag}: a distribution shows exactly one metric")
        if dim is None or dim.kind != "category":
            out.append(f"{tag}: a distribution needs a category dimension")
    return out


def validate_registry(metrics: Sequence[MetricDefinition], dimensions: Sequence[DimensionDefinition] = (), reports: Sequence[ReportDefinition] = ()) -> None:
    """Raises ``ContractError`` listing every violation. Pydantic already rejected malformed or SQL-like individual definitions."""
    problems: list[str] = []

    def dupes(label: str, ids: list[str]) -> None:
        for i in sorted({x for x in ids if ids.count(x) > 1}):
            problems.append(f"duplicate {label} id '{i}'")

    dupes("metric", [m.metric_id for m in metrics])
    dupes("dimension", [d.dimension_id for d in dimensions])
    dupes("report", [r.report_id for r in reports])
    mmap, dmap = {m.metric_id: m for m in metrics}, {d.dimension_id: d for d in dimensions}
    for m in metrics:
        for d in m.dimensions_allowed:
            if d not in dmap:
                problems.append(f"metric '{m.metric_id}': unknown dimension '{d}'")
    for r in reports:
        for mid in r.metric_ids:
            if mid not in mmap:
                problems.append(f"report '{r.report_id}': unknown metric '{mid}'")
            elif mmap[mid].permission_required != r.permission_required:
                problems.append(f"report '{r.report_id}': metric '{mid}' needs permission '{mmap[mid].permission_required}', not '{r.permission_required}'")
            elif not set(r.date_range.allowed_periods) <= set(mmap[mid].period_kinds):
                problems.append(f"report '{r.report_id}': metric '{mid}' does not support every allowed period")
        for f in r.allowed_filters:
            if f not in dmap:
                problems.append(f"report '{r.report_id}': unknown filter dimension '{f}'")
        for c in r.charts:
            for mid in c.metric_ids:
                if mid not in r.metric_ids:
                    problems.append(f"report '{r.report_id}' chart '{c.chart_id}': metric '{mid}' is not in the report")
            problems += chart_problems(c, mmap, dmap)
    if problems:
        raise ContractError(problems)


# ------------------------------------------------------------------------------------------------------------ result building
def check_result(result: MetricResult, definition: MetricDefinition) -> None:
    """A result must honour its definition: period supported, the missing state matches ``missing_behaviour``, operational metrics are never suppressed."""
    problems = []
    if result.metric_id != definition.metric_id:
        problems.append("metric id mismatch")
    if result.period not in definition.period_kinds:
        problems.append(f"period '{result.period}' is not supported by '{definition.metric_id}'")
    if result.state in ("unavailable", "not_captured") and result.state != definition.missing_behaviour:
        problems.append(f"missing data must be reported as '{definition.missing_behaviour}', not '{result.state}'")
    if result.state == "suppressed" and definition.suppression.kind == "operational":
        problems.append("an operational metric has no cohort to suppress")
    if problems:
        raise ContractError(problems)


def build_result(definition: MetricDefinition, period: str, value: Any, *, cohort: int | None = None, numerator: int | float | None = None,
                 denominator: int | float | None = None, partial: bool = False, note: str = "") -> MetricResult:
    """Shared semantics for 03D1/03E1: ``value is None`` means MISSING (state per ``missing_behaviour``); a cohort metric below its minimum is suppressed and
    carries no value, numerator or denominator; otherwise ok."""
    base = dict(metric_id=definition.metric_id, period=period, coverage=definition.coverage.note, note=note)
    if value is None:
        return MetricResult(state=definition.missing_behaviour, **base)
    if definition.suppression.kind == "cohort" and (cohort is None or cohort < (definition.suppression.min_cohort or REPORTING_MIN_COHORT)):
        return MetricResult(state="suppressed", **base)
    return MetricResult(state="ok", value=value, numerator=numerator, denominator=denominator, partial=partial, **base)


def result_from_legacy(legacy: dict, period: str) -> MetricResult:
    """Adapts one legacy report metric dict (``suppression.metric`` shape) to ``MetricResult`` without changing its figure."""
    state = legacy["state"]
    if state in (STATE_AVAILABLE, STATE_PARTIAL):
        return MetricResult(metric_id=legacy["metric_id"], period=period, state="ok", value=legacy["figure"], coverage=legacy.get("coverage", ""),
                            partial=state == STATE_PARTIAL, note=legacy.get("note", ""))
    mapped = {STATE_SUPPRESSED: "suppressed", STATE_UNAVAILABLE: "unavailable", STATE_NOT_CAPTURED: "not_captured"}[state]
    return MetricResult(metric_id=legacy["metric_id"], period=period, state=mapped, coverage=legacy.get("coverage", ""), note=legacy.get("note", ""))


# --------------------------------------------------------------------------------------- adapter over the EXISTING definitions
_ALL: tuple[str, ...] = tuple(PERIODS)
_C = perm.REPORTS_READ
_COMMERCIAL = perm.REPORTS_COMMERCIAL
# metric_id -> (source kind, source name, numerator (aggregation, subject), denominator|None, unit, dimensions, coverage kind)
_ADAPT: dict[str, tuple] = {
    "registrations": ("fact_table", "users", ("count_distinct", "candidate_accounts"), None, "count", (), "historical"),
    "onboarding_completed": ("fact_table", "users", ("count_distinct", "onboarded_accounts"), None, "count", (), "historical"),
    "onboarding_rate": ("fact_table", "users", ("count_distinct", "onboarded_accounts"), ("count_distinct", "candidate_accounts"), "percent", (), "historical"),
    "opportunities_created": ("fact_table", "opportunities", ("count", "opportunities"), None, "count", (), "historical"),
    "prepare_started": ("fact_table", "preparation_runs", ("count", "preparation_runs"), None, "count", (), "from_index"),
    "prepare_ready_rate": ("fact_table", "preparation_runs", ("count", "ready_runs"), ("count", "preparation_runs"), "percent", (), "from_index"),
    "practice_started": ("fact_table", "interview_sessions", ("count_distinct", "practice_sessions"), None, "count", (), "lower_bound"),
    "practice_completed": ("fact_table", "interviews", ("count", "completed_interviews"), None, "count", (), "historical"),
    "activation": ("named_query", "first_substantive_action", ("count_distinct", "activated_candidates"), None, "count", (), "lower_bound"),
    "returning": ("named_query", "returning_candidates", ("count_distinct", "returning_candidates"), None, "count", (), "lower_bound"),
    "feedback": ("fact_table", "user_feedback", ("count", "feedback_items"), None, "count", ("feedback_category",), "historical"),
    "evaluation_score": ("fact_table", "answers", ("mean", "overall_score"), None, "score", (), "historical"),
    "retrieval_outcomes": ("fact_table", "operational_metric_events", ("count", "retrieval_events"), None, "count", (), "since_first_event"),
    "request_outcomes": ("fact_table", "operational_metric_events", ("count", "request_events"), None, "count", ("operation",), "since_first_event"),
    "provider_calls": ("fact_table", "operational_metric_events", ("count", "provider_call_events"), None, "count", (), "since_first_event"),
    "ai_usage": ("fact_table", "ai_usage_facts", ("sum", "known_tokens"), None, "tokens", ("model", "workflow"), "since_first_event"),
    "ai_known_cost": ("fact_table", "ai_usage_facts", ("sum", "known_cost_usd"), None, "usd", ("model", "workflow"), "since_first_event"),
    "access_plans": ("fact_table", "subscriptions", ("count_distinct", "assigned_subjects"), None, "count", ("plan",), "historical"),
    "mock_mrr": ("fact_table", "billing_provider_subscriptions", ("sum", "monthly_amount"), None, "usd", ("currency",), "mock_state"),
    "mock_arr": ("fact_table", "billing_provider_subscriptions", ("sum", "annual_amount"), None, "usd", ("currency",), "mock_state"),
    "mock_failed_payments": ("fact_table", "billing_payments", ("count", "failed_payments"), None, "count", (), "mock_state"),
}
_COMMERCIAL_IDS = {"access_plans", "mock_mrr", "mock_arr", "mock_failed_payments"}

DIMENSIONS: tuple[DimensionDefinition, ...] = (
    DimensionDefinition(dimension_id="time", label="Time", description="Fixed UTC periods only; no client-supplied date.", kind="time"),
    DimensionDefinition(dimension_id="plan", label="Access plan", description="Code-defined access-plan families.", kind="category", max_buckets=10),
    DimensionDefinition(dimension_id="model", label="Approved model", description="Approved AI model identifiers.", kind="category"),
    DimensionDefinition(dimension_id="workflow", label="Workflow", description="Code-defined AI workflows.", kind="category", max_buckets=20),
    DimensionDefinition(dimension_id="feedback_category", label="Feedback category", description="Safe feedback categories; comment text is never read.",
                        kind="category", max_buckets=20),
    DimensionDefinition(dimension_id="operation", label="Operation", description="Code-defined operations.", kind="category", max_buckets=50),
    DimensionDefinition(dimension_id="currency", label="Currency", description="Currencies are never combined.", kind="category", max_buckets=20),
)


def _adapt(m: MetricDef) -> MetricDefinition:
    kind, name, num, den, unit, dims, cov = _ADAPT[m.metric_id]
    operational = m.cohort_policy == "operational"
    return MetricDefinition(
        metric_id=m.metric_id, label=m.label, description=m.definition, source=SourceRef(kind=kind, name=name),
        numerator=Quantity(aggregation=num[0], subject=num[1]), denominator=Quantity(aggregation=den[0], subject=den[1]) if den else None, unit=unit,
        period_kinds=list(_ALL), dimensions_allowed=list(dims), coverage=CoverageRule(kind=cov, note=m.coverage), missing_behaviour="unavailable",
        suppression=SuppressionPolicy(kind="operational") if operational else SuppressionPolicy(kind="cohort", min_cohort=REPORTING_MIN_COHORT),
        permission_required=_COMMERCIAL if m.metric_id in _COMMERCIAL_IDS else _C)


def contract_metrics() -> tuple[MetricDefinition, ...]:
    """The existing ``METRICS`` as contract definitions. Read-only view: ``definitions.METRICS`` and ``/admin/reports/definitions`` are untouched."""
    return tuple(_adapt(m) for m in METRICS)


def contract_reports() -> tuple[ReportDefinition, ...]:
    """The existing report endpoints described in the contract (metric ids only from ``METRICS``; no new metric, no chart)."""
    rng = DateRangeRule(allowed_periods=list(_ALL), default_period=DEFAULT_PERIOD)
    spec = {
        "product": ("Product usage", ("registrations", "onboarding_completed", "onboarding_rate", "opportunities_created", "prepare_started", "prepare_ready_rate",
                                      "practice_started", "practice_completed", "activation", "returning"), _C),
        "quality": ("Quality", ("feedback", "evaluation_score", "retrieval_outcomes", "request_outcomes", "provider_calls"), _C),
        "ai_economics": ("AI economics", ("ai_usage", "ai_known_cost"), _C),
        "commercial": ("Commercial (mock billing, not live revenue)", ("access_plans", "mock_mrr", "mock_arr", "mock_failed_payments"), _COMMERCIAL),
    }
    return tuple(ReportDefinition(report_id=k, title=t, description=f"Existing {k.replace('_', ' ')} report, aggregates only.", metric_ids=list(ids), date_range=rng,
                                  permission_required=p) for k, (t, ids, p) in spec.items())


def default_registry() -> tuple[tuple[MetricDefinition, ...], tuple[DimensionDefinition, ...], tuple[ReportDefinition, ...]]:
    metrics, reports = contract_metrics(), contract_reports()
    validate_registry(metrics, DIMENSIONS, reports)
    return metrics, DIMENSIONS, reports
