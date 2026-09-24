"""Private candidate documents, evidence, story bank & report export (Capstone P4).

Everything is owner-scoped (identity from the trusted session/dev boundary); a foreign
id is a 404 (never disclosing another user's data). Uploaded files are validated and
stored privately; document text is DATA and is never fed to an LLM. Report export reads
the stored report only (no LLM re-run) and omits all internal state.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, File, Form, HTTPException, Path, Query, UploadFile
from fastapi.responses import PlainTextResponse, Response

from src.api.dependencies import (
    get_current_user_id,
    get_documents_service,
    get_repository,
    get_stories_service,
)
from src.api.schemas.documents import (
    ClaimReviewRequest,
    DeleteResponse,
    DocumentDetail,
    DocumentListResponse,
    StoryCreateRequest,
    StoryDraftRequest,
    StoryListResponse,
    StoryOut,
    StoryUpdateRequest,
)
from src.application.report_export import build_json_export, build_markdown_export
from src.documents.validation import MAX_FILE_BYTES

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("", response_model=DocumentListResponse, summary="List the caller's private documents")
def list_documents(svc=Depends(get_documents_service), user_id: int = Depends(get_current_user_id)) -> DocumentListResponse:
    return DocumentListResponse(documents=svc.list(user_id))


@router.post("", response_model=DocumentDetail, status_code=201, summary="Upload a private document")
async def upload_document(
    file: UploadFile = File(...),
    category: str = Form("other"),
    language_hint: str | None = Form(None),
    svc=Depends(get_documents_service),
    user_id: int = Depends(get_current_user_id),
) -> DocumentDetail:
    data = await file.read()
    if len(data) > MAX_FILE_BYTES:
        raise HTTPException(status_code=413, detail="The file is too large (max 10 MB).")
    detail = svc.upload(
        user_id=user_id, filename=file.filename or "document",
        data=data, category=category, language_hint=language_hint,
    )
    return DocumentDetail(**detail)


@router.get("/{document_id}", response_model=DocumentDetail, summary="Get a document + its extracted claims")
def get_document(document_id: int = Path(...), svc=Depends(get_documents_service), user_id: int = Depends(get_current_user_id)) -> DocumentDetail:
    detail = svc.get(user_id=user_id, document_id=document_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    return DocumentDetail(**detail)


@router.post("/{document_id}/replace", response_model=DocumentDetail, summary="Replace a document with a new version")
async def replace_document(
    document_id: int = Path(...),
    file: UploadFile = File(...),
    language_hint: str | None = Form(None),
    svc=Depends(get_documents_service),
    user_id: int = Depends(get_current_user_id),
) -> DocumentDetail:
    data = await file.read()
    if len(data) > MAX_FILE_BYTES:
        raise HTTPException(status_code=413, detail="The file is too large (max 10 MB).")
    detail = svc.replace(user_id=user_id, document_id=document_id, filename=file.filename or "document", data=data, language_hint=language_hint)
    if detail is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    return DocumentDetail(**detail)


@router.get("/{document_id}/download", summary="Download the caller's own document file")
def download_document(
    document_id: int = Path(...),
    version: int | None = Query(default=None),
    svc=Depends(get_documents_service),
    user_id: int = Depends(get_current_user_id),
) -> Response:
    result = svc.download(user_id=user_id, document_id=document_id, version=version)
    if result is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    data, mime, filename = result
    # Sanitised filename; attachment (never inline/executed).
    safe = filename.replace('"', "")
    return Response(content=data, media_type=mime, headers={
        "Content-Disposition": f'attachment; filename="{safe}"',
    })


@router.post("/{document_id}/claims/{claim_id}/review", summary="Accept / edit / reject an extracted claim")
def review_claim(
    body: ClaimReviewRequest,
    document_id: int = Path(...),
    claim_id: int = Path(...),
    svc=Depends(get_documents_service),
    user_id: int = Depends(get_current_user_id),
) -> dict:
    updated = svc.review_claim(user_id=user_id, claim_id=claim_id, action=body.action, edited_text=body.edited_text)
    if updated is None:
        raise HTTPException(status_code=404, detail="Claim not found.")
    return updated


@router.delete("/{document_id}", response_model=DeleteResponse, summary="Delete a document and all derived evidence")
def delete_document(document_id: int = Path(...), svc=Depends(get_documents_service), user_id: int = Depends(get_current_user_id)) -> DeleteResponse:
    if not svc.delete(user_id=user_id, document_id=document_id):
        raise HTTPException(status_code=404, detail="Document not found.")
    return DeleteResponse(deleted=True)


# --- story / evidence bank ---------------------------------------------------

stories_router = APIRouter(prefix="/stories", tags=["documents"])


@stories_router.get("", response_model=StoryListResponse, summary="List the caller's stories")
def list_stories(svc=Depends(get_stories_service), user_id: int = Depends(get_current_user_id)) -> StoryListResponse:
    return StoryListResponse(stories=svc.list(user_id))


@stories_router.post("", response_model=StoryOut, status_code=201, summary="Create a story")
def create_story(body: StoryCreateRequest, svc=Depends(get_stories_service), user_id: int = Depends(get_current_user_id)) -> StoryOut:
    story = svc.create(
        user_id=user_id, title=body.title, status=body.status,
        fields={"situation": body.situation, "task": body.task, "action": body.action,
                "result": body.result, "competencies": body.competencies},
        claim_ids=body.claim_ids,
    )
    return StoryOut(**story)


@stories_router.post("/draft", response_model=StoryOut, status_code=201, summary="Draft a source-backed story from owned claims")
def draft_story(body: StoryDraftRequest, svc=Depends(get_stories_service), user_id: int = Depends(get_current_user_id)) -> StoryOut:
    story = svc.draft_from_claims(user_id=user_id, title=body.title, claim_ids=body.claim_ids)
    return StoryOut(**story)


@stories_router.get("/{story_id}", response_model=StoryOut, summary="Get one story")
def get_story(story_id: int = Path(...), svc=Depends(get_stories_service), user_id: int = Depends(get_current_user_id)) -> StoryOut:
    story = svc.get(user_id=user_id, story_id=story_id)
    if story is None:
        raise HTTPException(status_code=404, detail="Story not found.")
    return StoryOut(**story)


@stories_router.patch("/{story_id}", response_model=StoryOut, summary="Edit a story (marks source-backed as user-corrected)")
def update_story(body: StoryUpdateRequest, story_id: int = Path(...), svc=Depends(get_stories_service), user_id: int = Depends(get_current_user_id)) -> StoryOut:
    story = svc.update(user_id=user_id, story_id=story_id, fields=body.model_dump(exclude_none=True))
    if story is None:
        raise HTTPException(status_code=404, detail="Story not found.")
    return StoryOut(**story)


@stories_router.delete("/{story_id}", response_model=DeleteResponse, summary="Delete a story")
def delete_story(story_id: int = Path(...), svc=Depends(get_stories_service), user_id: int = Depends(get_current_user_id)) -> DeleteResponse:
    if not svc.delete(user_id=user_id, story_id=story_id):
        raise HTTPException(status_code=404, detail="Story not found.")
    return DeleteResponse(deleted=True)


# --- report export (bounded A9) ----------------------------------------------

export_router = APIRouter(prefix="/reports", tags=["documents"])


def _owned_report(repo, user_id: int, report_id: int) -> dict:
    detail = repo.get_interview(user_id, report_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Report not found.")
    return detail


@export_router.get("/{report_id}/export.json", summary="Export an owned report as JSON")
def export_report_json(report_id: int = Path(...), repo=Depends(get_repository), user_id: int = Depends(get_current_user_id)) -> Response:
    detail = _owned_report(repo, user_id, report_id)
    payload = build_json_export(detail)
    return Response(content=json.dumps(payload, ensure_ascii=False, indent=2), media_type="application/json", headers={
        "Content-Disposition": f'attachment; filename="ask4mo-report-{report_id}.json"',
    })


@export_router.get("/{report_id}/export.md", response_class=PlainTextResponse, summary="Export an owned report as Markdown")
def export_report_markdown(report_id: int = Path(...), repo=Depends(get_repository), user_id: int = Depends(get_current_user_id)) -> PlainTextResponse:
    detail = _owned_report(repo, user_id, report_id)
    return PlainTextResponse(content=build_markdown_export(detail), headers={
        "Content-Disposition": f'attachment; filename="ask4mo-report-{report_id}.md"',
    })
