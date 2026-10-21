"""Response schemas of the Command Center read model (package 03D1). ALLOWLIST: every model forbids extra fields, and no field can carry a candidate
identifier, content, e-mail, address, path, credential or free text. Every figure is a 03K ``MetricResult`` (a missing figure is a STATE with ``value`` null,
never zero) plus the evidence status, the dimension breakdowns and the unit/suppression labels the UI needs."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from src.reporting.contract import DimensionDefinition, MetricDefinition, MetricState, PeriodKind, Unit

# evidence status: WHY the figure is (or is not) trustworthy, in text first (never colour only).
EvidenceStatus = Literal["captured", "partial", "current_state", "not_captured", "unavailable", "suppressed"]
ComponentStatus = Literal["ok", "attention", "unavailable", "info"]


class _Out(BaseModel):
    model_config = ConfigDict(extra="forbid")


class BucketOut(_Out):
    key: str
    label: str
    state: Literal["ok", "suppressed", "unavailable"]
    value: int | float | None = None
    partial: bool = False


class BreakdownOut(_Out):
    dimension_id: str
    label: str
    buckets: list[BucketOut]


class MetricItemOut(_Out):
    metric_id: str
    label: str
    unit: Unit
    period: PeriodKind
    state: MetricState
    value: int | float | str | None = None
    numerator: int | float | None = None
    denominator: int | float | None = None
    coverage: str = ""
    partial: bool = False
    note: str = ""
    evidence: EvidenceStatus
    evidence_source: str
    suppression: Literal["cohort", "operational"]
    dimensions: list[str] = []
    cost_micro_usd: int | None = None          # exact integer micro-USD of a known-cost metric (null when unknown); ``value`` is the same cost in USD
    breakdowns: list[BreakdownOut] = []


class ComponentOut(_Out):
    component_id: str
    label: str
    status: ComponentStatus
    evidence: Literal["current_state", "unavailable"]
    note: str = ""


class CommandCenterResponse(_Out):
    section_id: str
    title: str
    period: PeriodKind
    window_start: str | None = None
    window_end: str
    generated_at: str
    utc: bool = True
    privacy: str
    captured_since: str | None = None
    metrics: list[MetricItemOut]
    components: list[ComponentOut] = []


class CommandCenterDefinitions(_Out):
    periods: list[PeriodKind]
    default_period: PeriodKind
    metrics: list[MetricDefinition]
    dimensions: list[DimensionDefinition]
