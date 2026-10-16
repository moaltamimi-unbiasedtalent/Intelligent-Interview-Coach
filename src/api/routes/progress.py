"""Progress routes — read-only, strictly user-scoped.

Surfaces the caller's own persisted practice metrics (from completed interviews).
Practice guidance only — never a score, ranking or hiring signal — and it fabricates
nothing: fields the persisted data cannot support are returned as null/empty.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from src.api.dependencies import get_current_user_id, get_history_access_policy, get_repository
from src.api.schemas.progress import ProgressResponse
from src.application import history_service

router = APIRouter(prefix="/progress", tags=["progress"])


@router.get("", response_model=ProgressResponse,
            summary="The caller's practice progress metrics")
def progress(
    repo=Depends(get_repository),
    user_id: int = Depends(get_current_user_id),
    policy=Depends(get_history_access_policy),
) -> ProgressResponse:
    # Same candidate and same window as the history list: one entitlement decision, one selection mechanism.
    window = policy.window_for(user_id)
    return ProgressResponse(**history_service.practice_progress(repo, user_id, window), access={"restricted": window is not None, "window": window})
