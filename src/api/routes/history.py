"""History routes — read-only and strictly user-scoped.

Every operation resolves the caller's internal user id and passes it to the
repository, which filters by user. One user can never list or fetch another
user's reports (a foreign id returns 404, not another user's data).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path

from src.api.dependencies import get_current_user_id, get_repository
from src.api.schemas.history import InterviewDetailResponse, InterviewListResponse
from src.application import history_service

router = APIRouter(prefix="/history", tags=["history"])


@router.get("/interviews", response_model=InterviewListResponse,
            summary="List the caller's interviews")
def list_interviews(
    repo=Depends(get_repository),
    user_id: int = Depends(get_current_user_id),
) -> InterviewListResponse:
    return InterviewListResponse(
        interviews=history_service.list_interview_reports(repo, user_id))


@router.get("/interviews/{report_id}", response_model=InterviewDetailResponse,
            summary="Fetch one of the caller's interviews")
def get_interview(
    report_id: int = Path(..., ge=1),
    repo=Depends(get_repository),
    user_id: int = Depends(get_current_user_id),
) -> InterviewDetailResponse:
    detail = history_service.get_interview_report(repo, user_id, report_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Interview not found.")
    return InterviewDetailResponse(interview=detail)
