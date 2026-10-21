"""API schemas for the Admin metric and report contract (03K). The models live in ``src.reporting.contract`` (strict, extra=forbid); this module is the
schema-layer export used by the 03D1/03E1 routes. It declares NO route."""

from __future__ import annotations

from src.reporting.contract import (  # noqa: F401
    ChartSpec, CoverageRule, DateRangeRule, DimensionDefinition, MetricDefinition, MetricResult, Quantity, ReportDefinition, SourceRef, SuppressionPolicy,
)

CONTRACT_MODELS = (MetricDefinition, DimensionDefinition, ReportDefinition, MetricResult)


def contract_json_schema() -> dict:
    """Deterministic JSON schema of the contract, committed at frontend/lib/admin/metricContract.schema.json and kept in sync by a test."""
    return {m.__name__: m.model_json_schema(mode="serialization") for m in CONTRACT_MODELS}
