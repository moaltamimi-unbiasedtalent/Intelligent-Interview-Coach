"""Candidate-feedback routes — user-scoped, ownership-verified (P5).

A rating attaches to one logical output (Agent answer / interview evaluation / final
report) the caller owns. The server sets ``user_id``; a foreign/unknown target is a
404 (never disclosing whether it exists for someone else). Feedback never modifies Agent
behaviour — it is a human-reviewed improvement signal only.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.api.dependencies import get_current_user_id, get_feedback_service
from src.api.schemas.feedback import (
    FeedbackCreateRequest,
    FeedbackDeleteResponse,
    FeedbackResponse,
)
from src.feedback import FeedbackSurface

router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.post("", response_model=FeedbackResponse, status_code=status.HTTP_201_CREATED,
             summary="Submit or update feedback on one output (owner-scoped)")
def submit_feedback(
    body: FeedbackCreateRequest,
    service=Depends(get_feedback_service),
    user_id: int = Depends(get_current_user_id),
) -> FeedbackResponse:
    item = service.submit(
        user_id, surface=body.surface.value, target_id=body.target_id,
        rating=body.rating.value, comment=body.comment,
    )
    if item is None:  # not owned / unknown target → not-found (no disclosure)
        raise HTTPException(status_code=404, detail="Feedback target not found.")
    return FeedbackResponse(**item.to_public())


@router.get("", response_model=FeedbackResponse | None,
            summary="Fetch the caller's feedback for one output (for refresh restore)")
def get_feedback(
    surface: FeedbackSurface = Query(...),
    target_id: str = Query(..., min_length=1, max_length=128),
    service=Depends(get_feedback_service),
    user_id: int = Depends(get_current_user_id),
) -> FeedbackResponse | None:
    item = service.get(user_id, surface.value, target_id)
    return FeedbackResponse(**item.to_public()) if item is not None else None


@router.delete("", response_model=FeedbackDeleteResponse,
               summary="Reset the caller's feedback for one output")
def delete_feedback(
    surface: FeedbackSurface = Query(...),
    target_id: str = Query(..., min_length=1, max_length=128),
    service=Depends(get_feedback_service),
    user_id: int = Depends(get_current_user_id),
) -> FeedbackDeleteResponse:
    deleted = service.delete(user_id, surface.value, target_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Feedback not found.")
    return FeedbackDeleteResponse(deleted=True)
