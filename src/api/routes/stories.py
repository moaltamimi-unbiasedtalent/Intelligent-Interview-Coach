"""Story Bank API (Capstone P4; completed by package 04A, REQ-OWN-06).

Every route is owner-scoped through ``get_current_user_id``: another account's story, claim, answer or share is a 404 that is indistinguishable from a missing one
(never a 403, never a hint that it exists). Search, suggestion and filter words travel in a POST body, so story content never lands in a URL or an access log.
Responses and errors carry no story text beyond the owner's own projection; nothing here writes story content to a log or an audit record.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel, Field

from src.api.dependencies import get_current_user_id, get_sharing_service, get_stories_service
from src.api.schemas.documents import (
    DeleteResponse,
    StoryCreateRequest,
    StoryDraftRequest,
    StoryEvidenceRequest,
    StoryListResponse,
    StoryOut,
    StorySuggestRequest,
    StorySuggestResponse,
    StoryTagsResponse,
    StoryUpdateRequest,
)

router = APIRouter(prefix="/stories", tags=["documents"])

_NOT_FOUND = "Story not found."


class StorySearchRequest(BaseModel):
    model_config = {"extra": "forbid"}
    q: str | None = Field(default=None, max_length=200)
    tag: str | None = Field(default=None, max_length=60)
    status: Literal["source_backed", "user_created", "user_corrected", "model_suggested"] | None = None
    verification: Literal["evidence_verified", "source_revoked", "answer_linked", "self_confirmed", "unverified"] | None = None
    opportunity_id: int | None = Field(default=None, ge=1)
    archived: Literal["active", "archived", "all"] = "active"


def _found(story: dict | None) -> StoryOut:
    if story is None:
        raise HTTPException(status_code=404, detail=_NOT_FOUND)
    return StoryOut(**story)


@router.get("", response_model=StoryListResponse, summary="List the caller's active stories")
def list_stories(svc=Depends(get_stories_service), user_id: int = Depends(get_current_user_id)) -> StoryListResponse:
    return StoryListResponse(stories=svc.list(user_id))


@router.post("/search", response_model=StoryListResponse, summary="Search and filter the caller's own stories")
def search_stories(body: StorySearchRequest, svc=Depends(get_stories_service), user_id: int = Depends(get_current_user_id)) -> StoryListResponse:
    return StoryListResponse(stories=svc.list(
        user_id, q=body.q, tag=body.tag, status=body.status, verification=body.verification,
        opportunity_id=body.opportunity_id, archived=body.archived))


@router.get("/tags", response_model=StoryTagsResponse, summary="Distinct competency tags across the caller's active stories")
def story_tags(svc=Depends(get_stories_service), user_id: int = Depends(get_current_user_id)) -> StoryTagsResponse:
    return StoryTagsResponse(tags=svc.tags(user_id))


@router.post("/suggest", response_model=StorySuggestResponse, summary="Suggest the caller's own stories for an interview (proposals only; the candidate approves)")
def suggest_stories(body: StorySuggestRequest, svc=Depends(get_stories_service), user_id: int = Depends(get_current_user_id)) -> StorySuggestResponse:
    return StorySuggestResponse(suggestions=svc.suggest(user_id=user_id, terms=body.terms, opportunity_id=body.opportunity_id, limit=body.limit))


@router.post("", response_model=StoryOut, status_code=201, summary="Create a story")
def create_story(body: StoryCreateRequest, svc=Depends(get_stories_service), user_id: int = Depends(get_current_user_id)) -> StoryOut:
    story = svc.create(
        user_id=user_id, title=body.title, status=body.status,
        fields=body.model_dump(include={"situation", "task", "action", "result", "competencies"}),
        claim_ids=body.claim_ids, opportunity_id=body.opportunity_id,
    )
    return StoryOut(**story)


@router.post("/draft", response_model=StoryOut, status_code=201, summary="Draft a source-backed story from owned claims")
def draft_story(body: StoryDraftRequest, svc=Depends(get_stories_service), user_id: int = Depends(get_current_user_id)) -> StoryOut:
    story = svc.draft_from_claims(user_id=user_id, title=body.title, claim_ids=body.claim_ids, opportunity_id=body.opportunity_id)
    return StoryOut(**story)


@router.get("/{story_id}", response_model=StoryOut, summary="Get one story")
def get_story(story_id: int = Path(...), svc=Depends(get_stories_service), user_id: int = Depends(get_current_user_id)) -> StoryOut:
    return _found(svc.get(user_id=user_id, story_id=story_id))


@router.patch("/{story_id}", response_model=StoryOut, summary="Edit a story (marks source-backed as user-corrected)")
def update_story(body: StoryUpdateRequest, story_id: int = Path(...), svc=Depends(get_stories_service), user_id: int = Depends(get_current_user_id)) -> StoryOut:
    return _found(svc.update(
        user_id=user_id, story_id=story_id, fields=body.model_dump(exclude_none=True, exclude={"opportunity_id"}),
        opportunity_id=body.opportunity_id, set_opportunity="opportunity_id" in body.model_fields_set))


@router.post("/{story_id}/archive", response_model=StoryOut, summary="Archive a story (reversible; revokes its share grants)")
def archive_story(story_id: int = Path(...), svc=Depends(get_stories_service), sharing=Depends(get_sharing_service),
                  user_id: int = Depends(get_current_user_id)) -> StoryOut:
    story = _found(svc.archive(user_id=user_id, story_id=story_id))
    # Consent: an archived story is out of every shared view at once, and restoring it never re-shares it (the candidate must share again, explicitly).
    sharing.invalidate_on_delete(owner_user_id=user_id, resource_type="story", resource_id=str(story_id))
    return story


@router.post("/{story_id}/restore", response_model=StoryOut, summary="Restore an archived story (shares stay revoked)")
def restore_story(story_id: int = Path(...), svc=Depends(get_stories_service), user_id: int = Depends(get_current_user_id)) -> StoryOut:
    return _found(svc.restore(user_id=user_id, story_id=story_id))


@router.post("/{story_id}/confirm", response_model=StoryOut, summary="The candidate confirms the account is accurate (a self-attestation, not evidence)")
def confirm_story(story_id: int = Path(...), svc=Depends(get_stories_service), user_id: int = Depends(get_current_user_id)) -> StoryOut:
    return _found(svc.confirm(user_id=user_id, story_id=story_id, confirmed=True))


@router.delete("/{story_id}/confirm", response_model=StoryOut, summary="Withdraw the self-confirmation")
def unconfirm_story(story_id: int = Path(...), svc=Depends(get_stories_service), user_id: int = Depends(get_current_user_id)) -> StoryOut:
    return _found(svc.confirm(user_id=user_id, story_id=story_id, confirmed=False))


@router.post("/{story_id}/evidence", response_model=StoryOut, summary="Link one of the caller's own claims or practice answers as evidence")
def attach_evidence(body: StoryEvidenceRequest, story_id: int = Path(...), svc=Depends(get_stories_service), user_id: int = Depends(get_current_user_id)) -> StoryOut:
    return _found(svc.attach_evidence(user_id=user_id, story_id=story_id, kind=body.kind, ref_id=body.ref_id))


@router.delete("/{story_id}/evidence/{kind}/{ref_id}", response_model=StoryOut, summary="Remove an evidence link")
def detach_evidence(story_id: int = Path(...), kind: Literal["claim", "answer"] = Path(...), ref_id: int = Path(..., ge=1),
                    svc=Depends(get_stories_service), user_id: int = Depends(get_current_user_id)) -> StoryOut:
    return _found(svc.detach_evidence(user_id=user_id, story_id=story_id, kind=kind, ref_id=ref_id))


@router.delete("/{story_id}", response_model=DeleteResponse, summary="Delete a story and everything derived from it")
def delete_story(story_id: int = Path(...), svc=Depends(get_stories_service),
                 sharing=Depends(get_sharing_service), user_id: int = Depends(get_current_user_id)) -> DeleteResponse:
    if not svc.delete(user_id=user_id, story_id=story_id):
        raise HTTPException(status_code=404, detail=_NOT_FOUND)
    # A deleted source must not leave an active-looking grant (ids can be reused on SQLite).
    sharing.invalidate_on_delete(owner_user_id=user_id, resource_type="story", resource_id=str(story_id))
    return DeleteResponse(deleted=True)
