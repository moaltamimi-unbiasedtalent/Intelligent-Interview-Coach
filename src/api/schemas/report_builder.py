"""Allowlist response and request schemas for the Admin report builder (package 03E1). Every model forbids extra fields; there is no open dict or Any anywhere, so a
new internal field can never leak. Responses carry no owner id, no candidate identifier and no row-level data."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, model_validator

from src.reporting.report_builder import BuilderDefinition

MetricState = Literal["ok", "suppressed", "unavailable", "not_captured"]


class _Out(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RegistryMetric(_Out):
    metric_id: str
    label: str
    description: str
    unit: str
    coverage: str
    suppression: Literal["cohort", "operational"]
    dimensions: list[str]
    must_group_by: str | None
    comparable: bool


class RegistryReportType(_Out):
    report_id: str
    title: str
    description: str
    permission_required: str
    windows: list[str]
    metrics: list[RegistryMetric]


class RegistryDimension(_Out):
    dimension_id: str
    label: str
    description: str
    kind: Literal["time", "category"]
    max_buckets: int


class RegistryLimits(_Out):
    max_metrics: int
    max_filters: int
    max_filter_values: int
    max_export_rows: int
    max_definition_bytes: int


class RegistryResponse(_Out):
    report_types: list[RegistryReportType]
    dimensions: list[RegistryDimension]
    windows: list[str]
    chart_kinds: list[str]
    comparisons: list[str]
    limits: RegistryLimits
    min_cohort: int
    rules: list[str]


class ProblemOut(_Out):
    code: str
    field: str
    message: str


class ValidateResponse(_Out):
    valid: bool
    problems: list[ProblemOut]


class BucketOut(_Out):
    label: str
    state: Literal["ok", "suppressed", "unavailable"]
    value: int | float | str | None


class FilterOut(_Out):
    dimension_id: str
    values: list[str]


class PreviousOut(_Out):
    state: MetricState
    value: int | float | str | None
    partial: bool
    note: str
    buckets: list[BucketOut] | None


class PreviewMetricOut(_Out):
    metric_id: str
    label: str
    unit: str
    period: str
    coverage: str
    suppression: Literal["cohort", "operational"]
    state: MetricState
    value: int | float | str | None
    partial: bool
    note: str
    group_dimension: str | None
    buckets: list[BucketOut] | None
    previous: PreviousOut | None = None


class PreviewResponse(_Out):
    report_id: str
    title: str
    window: str
    window_start: str | None
    window_end: str
    generated_at: str
    utc: bool
    group_by: str | None
    filters: list[FilterOut]
    chart: str | None
    comparison: Literal["none", "previous_period"]
    previous_window_start: str | None
    previous_window_end: str | None
    metrics: list[PreviewMetricOut]
    privacy: str


class SavedWrite(BaseModel):
    """Create or replace a saved report definition. ``expected_revision`` is required on update and ignored on create."""
    model_config = ConfigDict(extra="forbid", strict=True)
    name: str = Field(min_length=3, max_length=60)
    definition: BuilderDefinition
    shared: StrictBool = False
    expected_revision: StrictInt | None = Field(default=None, ge=1)


class SavedOut(_Out):
    id: int
    name: str
    report_id: str
    definition: BuilderDefinition | None
    valid: bool
    shared: bool
    revision: int
    editable: bool
    created_at: str | None
    updated_at: str | None


class SavedList(_Out):
    items: list[SavedOut]
    max_saved: int


class ExportRequest(BaseModel):
    """Export an ALREADY-SUPPRESSED aggregate result of exactly one definition: inline or a saved one the caller may see."""
    model_config = ConfigDict(extra="forbid", strict=True)
    format: Literal["csv", "json"]
    definition: BuilderDefinition | None = None
    saved_id: StrictInt | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def _one(self) -> "ExportRequest":
        if (self.definition is None) == (self.saved_id is None):
            raise ValueError("give exactly one of definition or saved_id")
        return self
