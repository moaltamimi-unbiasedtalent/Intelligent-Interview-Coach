"""Owner-scoped list of a candidate's recent Mo preparation runs (04D, AC-18 / IR-AC18-RUNLIST).

``GET /api/v1/agent/runs`` returns ONLY the caller's own runs, newest first, bounded: run id, lifecycle state and timestamps. It never returns chat content, sources, prompts or
checkpoint data, and it reads the ownership index (``preparation_runs``) through one indexed query, never the checkpoint store. A run is opened with the existing owner-scoped
``GET /agent/runs/{run_id}``. It is registered BEFORE the agent router so the literal ``/runs`` path can never be read as a run id, and it does not build the agent graph, so it
keeps working on an environment where Mo cannot run (no AI configured).
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict

from src.api.dependencies import get_current_user_id, get_repository

router = APIRouter(prefix="/agent", tags=["agent"])


class RecentRun(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    state: Literal["started", "ready", "failed"]
    created_at: datetime | None = None
    updated_at: datetime | None = None


class RecentRunsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    runs: list[RecentRun]
    limit: int


@router.get("/runs", response_model=RecentRunsResponse, summary="List the caller's own recent preparation runs (owner-scoped, bounded, no content)")
def list_recent_runs(
    limit: int = Query(20, ge=1, le=50),
    user_id: int = Depends(get_current_user_id),
    repo=Depends(get_repository),
) -> RecentRunsResponse:
    from src.privacy.preparation import PreparationRunIndex

    rows = PreparationRunIndex(repo.session_factory).recent_for_owner(user_id, limit)
    return RecentRunsResponse(runs=[RecentRun(**r) for r in rows], limit=limit)
