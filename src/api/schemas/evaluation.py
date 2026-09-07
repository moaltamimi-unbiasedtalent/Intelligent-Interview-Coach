"""Evaluation API schemas (read-only; never triggers a paid run)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class EvaluationRunResponse(BaseModel):
    """A stored RAGAS run (safe metrics + config metadata), or absent."""

    available: bool = False
    metrics: dict | None = None
    run_config: dict | None = None


class EvaluationRunsResponse(BaseModel):
    runs: list[str] = Field(default_factory=list)


class RagasConfigurationResponse(BaseModel):
    """Safe RAGAS readiness snapshot — never a secret value."""

    ragas_ready: bool = False
    evaluator_configured: bool = False
    career_configured: bool = False
    can_run: bool = False
    missing: list[str] = Field(default_factory=list)
