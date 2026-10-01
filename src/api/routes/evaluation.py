"""Evaluation routes — read-only. Never triggers a paid RAGAS run.

All handlers are GET and only read stored artifacts / a safe configuration
snapshot. A user-triggered run endpoint is intentionally NOT added in Phase 2
(cost-gated execution stays explicit in the UI); it would require authorization
and cost confirmation and must never run on GET.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path

from src.api.dependencies import require_platform_admin
from src.api.schemas.evaluation import (
    EvaluationRunResponse,
    EvaluationRunsResponse,
    RagasConfigurationResponse,
)
from src.application import evaluation_service

# P10B-W9.3: these are INTERNAL engineering/reviewer diagnostics (offline evaluation metrics),
# never candidate-facing. Gate the whole router at platform-admin level so an ordinary candidate
# (or anonymous caller) can neither read them nor discover their contents by URL. Server-side
# authorization is the boundary; hiding the /review UI is only defense-in-depth.
router = APIRouter(
    prefix="/evaluation", tags=["evaluation"],
    dependencies=[Depends(require_platform_admin)],
)


@router.get("/latest", response_model=EvaluationRunResponse,
            summary="Latest usable RAGAS run")
def latest() -> EvaluationRunResponse:
    run = evaluation_service.latest_evaluation_run()
    if run is None:
        return EvaluationRunResponse(available=False)
    return EvaluationRunResponse(
        available=True, metrics=run.get("metrics"), run_config=run.get("run_config"))


@router.get("/runs", response_model=EvaluationRunsResponse,
            summary="Stored RAGAS run ids")
def runs() -> EvaluationRunsResponse:
    return EvaluationRunsResponse(runs=evaluation_service.list_evaluation_runs())


@router.get("/runs/{run_id}", response_model=EvaluationRunResponse,
            summary="One stored RAGAS run")
def run(run_id: str = Path(..., max_length=64)) -> EvaluationRunResponse:
    data = evaluation_service.get_evaluation_run(run_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Evaluation run not found.")
    return EvaluationRunResponse(
        available=True, metrics=data.get("metrics"), run_config=data.get("run_config"))


@router.get("/ragas/configuration", response_model=RagasConfigurationResponse,
            summary="Safe RAGAS readiness snapshot")
def ragas_configuration() -> RagasConfigurationResponse:
    status = evaluation_service.check_ragas_configuration()
    return RagasConfigurationResponse(
        ragas_ready=bool(status.get("ragas_ready")),
        evaluator_configured=bool(status.get("evaluator_configured")),
        career_configured=bool(status.get("career_configured")),
        can_run=bool(status.get("can_run")),
        missing=list(status.get("missing", [])),
    )
