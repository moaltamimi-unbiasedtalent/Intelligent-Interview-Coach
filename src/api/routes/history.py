"""History routes — strictly user-scoped (read, plus owner delete as of P10B-W9.8).

Every operation resolves the caller's internal user id and passes it to the
repository, which filters by user. One user can never list or fetch another
user's reports (a foreign id returns 404, not another user's data).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path

from src.api.dependencies import (
    get_audit_repository, get_current_user_id, get_history_access_policy, get_repository, get_session_store, get_sharing_service,
)
from src.api.schemas.history import InterviewDetailResponse, InterviewListResponse
from src.application import history_service

router = APIRouter(prefix="/history", tags=["history"])


@router.get("/interviews", response_model=InterviewListResponse,
            summary="List the caller's interviews")
def list_interviews(
    repo=Depends(get_repository),
    user_id: int = Depends(get_current_user_id),
    policy=Depends(get_history_access_policy),
) -> InterviewListResponse:
    window = policy.window_for(user_id)
    rows = history_service.list_interview_reports(repo, user_id, window)
    access = {"restricted": False, "window": None, "hidden_count": 0}
    if window is not None:                                       # only a restricted caller costs the extra count query
        access = {"restricted": True, "window": window, "hidden_count": max(0, repo.count_completed(user_id) - len(rows))}
    return InterviewListResponse(interviews=rows, access=access)


@router.get("/interviews/{report_id}", response_model=InterviewDetailResponse,
            summary="Fetch one of the caller's interviews")
def get_interview(
    report_id: int = Path(..., ge=1),
    repo=Depends(get_repository),
    user_id: int = Depends(get_current_user_id),
    policy=Depends(get_history_access_policy),
) -> InterviewDetailResponse:
    # An owned interview outside the caller's window raises HistoryRestricted (403 history_not_available); a foreign or missing id is still a 404.
    detail = history_service.get_interview_report(repo, user_id, report_id, policy.window_for(user_id))
    if detail is None:
        raise HTTPException(status_code=404, detail="Interview not found.")
    return InterviewDetailResponse(interview=detail)


@router.delete("/interviews/{report_id}", summary="Delete one of the caller's completed interviews")
def delete_interview(
    report_id: int = Path(..., ge=1),
    repo=Depends(get_repository),
    store=Depends(get_session_store),
    sharing=Depends(get_sharing_service),
    audit=Depends(get_audit_repository),
    user_id: int = Depends(get_current_user_id),
) -> dict:
    """Hard-delete a completed interview (questions, answers, evaluations, report), the resumable session it
    was saved from, and any share grant of its report. Foreign/unknown ids return 404 (no disclosure);
    a repeat delete is 404, never a 5xx. Metadata-only audit (no answer text)."""
    deleted, source_session = repo.delete_interview_with_source(user_id, report_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Interview not found.")
    if source_session:
        store.discard(source_session, user_id)
    sharing.invalidate_on_delete(owner_user_id=user_id, resource_type="interview_report",
                                 resource_id=str(report_id))
    audit.record(event_type="interview.deleted", actor_user_id=user_id,
                 target_type="interview", target_id=str(report_id))
    return {"deleted": True}
