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
    get_history_access_policy,
    get_pause_service,
    get_repository,
)
from src.api.schemas.documents import (
    ClaimReviewRequest,
    DeleteResponse,
    DocumentDetail,
    DocumentListResponse,
)
from src.application.report_export import build_json_export, build_markdown_export
from src.documents.validation import MAX_FILE_BYTES

router = APIRouter(prefix="/documents", tags=["documents"])


def _scan_or_reject(data: bytes, filename: str) -> None:
    """Malware-scan policy (§16/§17): fail closed when scanning is required but unavailable;
    reject flagged files; never claim a file is clean unless a real scanner passed it."""
    from src.documents.file_security import (
        FileRejected, FileScanUnavailable, enforce_scan)

    try:
        enforce_scan(data, filename)
    except FileScanUnavailable as exc:
        raise HTTPException(
            status_code=503,
            detail="File uploads are temporarily unavailable (security scanning offline).",
        ) from exc
    except FileRejected as exc:
        raise HTTPException(
            status_code=422,
            detail="This file was rejected by a security scan and was not stored.",
        ) from exc


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
    pause=Depends(get_pause_service),
) -> DocumentDetail:
    # Per-user upload ceiling + OCR pause (§19/§21). OCR runs during upload, so a paused OCR
    # capability blocks new uploads truthfully rather than silently skipping extraction.
    from src.api.guards import ensure_not_paused
    from src.api.rate_limit import enforce, user_key

    ensure_not_paused("ocr", pause)
    enforce("cost_upload_user", user_key(user_id))
    data = await file.read()
    if len(data) > MAX_FILE_BYTES:
        raise HTTPException(status_code=413, detail="The file is too large (max 10 MB).")
    _scan_or_reject(data, file.filename or "document")
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
    pause=Depends(get_pause_service),
) -> DocumentDetail:
    from src.api.guards import ensure_not_paused
    from src.api.rate_limit import enforce, user_key

    ensure_not_paused("ocr", pause)
    enforce("cost_upload_user", user_key(user_id))
    data = await file.read()
    if len(data) > MAX_FILE_BYTES:
        raise HTTPException(status_code=413, detail="The file is too large (max 10 MB).")
    _scan_or_reject(data, file.filename or "document")
    detail = svc.replace(user_id=user_id, document_id=document_id, filename=file.filename or "document", data=data, language_hint=language_hint)
    if detail is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    return DocumentDetail(**detail)


@router.post("/{document_id}/reprocess", response_model=DocumentDetail, summary="Retry extraction on an already-stored document")
def reprocess_document(
    document_id: int = Path(...),
    svc=Depends(get_documents_service),
    user_id: int = Depends(get_current_user_id),
    pause=Depends(get_pause_service),
) -> DocumentDetail:
    # Owner-scoped retry of the same governed pipeline on the file we already hold (no new
    # upload). Blocked while OCR is paused (extraction may run) and rate-limited like uploads.
    from src.api.guards import ensure_not_paused
    from src.api.rate_limit import enforce, user_key

    ensure_not_paused("ocr", pause)
    enforce("cost_upload_user", user_key(user_id))
    detail = svc.reprocess(user_id=user_id, document_id=document_id)
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
def delete_document(document_id: int = Path(...), svc=Depends(get_documents_service), repo=Depends(get_repository), user_id: int = Depends(get_current_user_id)) -> DeleteResponse:
    if not svc.delete(user_id=user_id, document_id=document_id):
        raise HTTPException(status_code=404, detail="Document not found.")
    # P10B Wave 6: clear any Opportunity's JD link to this now-deleted document so the Opportunity
    # survives without pointing at inaccessible content (Postgres also SET NULLs via the FK).
    from src.opportunity_repository import OpportunityRepository
    OpportunityRepository(repo.session_factory).clear_jd_links(document_id)
    return DeleteResponse(deleted=True)


# --- report export (bounded A9) ----------------------------------------------

export_router = APIRouter(prefix="/reports", tags=["documents"])


def _owned_report(repo, user_id: int, report_id: int, window: int | None = None) -> dict:
    detail = repo.get_interview(user_id, report_id, window) if window is not None else repo.get_interview(user_id, report_id)   # raises HistoryRestricted outside the window
    if detail is None:
        raise HTTPException(status_code=404, detail="Report not found.")
    return detail


@export_router.get("/{report_id}/export.json", summary="Export an owned report as JSON")
def export_report_json(report_id: int = Path(...), repo=Depends(get_repository), user_id: int = Depends(get_current_user_id),
                       policy=Depends(get_history_access_policy)) -> Response:
    detail = _owned_report(repo, user_id, report_id, policy.window_for(user_id))
    payload = build_json_export(detail)
    return Response(content=json.dumps(payload, ensure_ascii=False, indent=2), media_type="application/json", headers={
        "Content-Disposition": f'attachment; filename="ask4mo-report-{report_id}.json"',
    })


@export_router.get("/{report_id}/export.md", response_class=PlainTextResponse, summary="Export an owned report as Markdown")
def export_report_markdown(report_id: int = Path(...), repo=Depends(get_repository), user_id: int = Depends(get_current_user_id),
                           policy=Depends(get_history_access_policy)) -> PlainTextResponse:
    detail = _owned_report(repo, user_id, report_id, policy.window_for(user_id))
    return PlainTextResponse(content=build_markdown_export(detail), headers={
        "Content-Disposition": f'attachment; filename="ask4mo-report-{report_id}.md"',
    })
