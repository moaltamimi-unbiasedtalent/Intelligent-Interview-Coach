"""Candidate privacy requests and legal-version truth (P10B-W10.10). Owner-scoped; NOT admin routes.

A privacy request is a durable record for human follow-up; the immediate self-service export and deletion in Data & Privacy are
unchanged. A candidate can only create and read their OWN requests. Legal acceptance records the CURRENT published version of one
document for the caller (idempotent); it is a version acknowledgement, not consent to optional processing.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from src.api.dependencies import get_current_user_id, get_legal_service, get_privacy_request_service
from src.api.rate_limit import enforce, user_key
from src.api.schemas.privacy import LegalStatus, PrivacyRequestCreate, PrivacyRequestList, PrivacyRequestView
from src.privacy.legal import LegalNotFound, LegalValidationError
from src.privacy.requests import PrivacyConflict, PrivacyNotFound, PrivacyValidationError

router = APIRouter(prefix="/privacy", tags=["privacy"])


@router.post("/requests", response_model=PrivacyRequestView, status_code=201, summary="Submit a privacy request for human follow-up")
def create_request(body: PrivacyRequestCreate, user_id: int = Depends(get_current_user_id),
                   svc=Depends(get_privacy_request_service)) -> PrivacyRequestView:
    enforce("privacy_request_user", user_key(user_id))
    try:
        return PrivacyRequestView(**svc.create(user_id, body.request_type, body.note))
    except PrivacyValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except PrivacyConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except PrivacyNotFound:
        raise HTTPException(status_code=404, detail="Account not found.")


@router.get("/requests", response_model=PrivacyRequestList, summary="My privacy requests")
def my_requests(page: int = Query(default=1, ge=1, le=100000), page_size: int = Query(default=20, ge=1, le=50),
                user_id: int = Depends(get_current_user_id), svc=Depends(get_privacy_request_service)) -> PrivacyRequestList:
    return PrivacyRequestList(**svc.list_for_owner(user_id, page=page, page_size=page_size))


@router.get("/legal", response_model=LegalStatus, summary="Current legal document versions and my recorded acceptance")
def legal_status(user_id: int = Depends(get_current_user_id), legal=Depends(get_legal_service)) -> LegalStatus:
    return LegalStatus(**legal.for_user(user_id))


@router.post("/legal/{code}/accept", response_model=LegalStatus, summary="Record my acceptance of the CURRENT version of one document")
def accept(code: str, user_id: int = Depends(get_current_user_id), legal=Depends(get_legal_service)) -> LegalStatus:
    enforce("legal_accept_user", user_key(user_id))
    try:
        return LegalStatus(**legal.accept(user_id, code[:24], source="settings"))
    except (LegalNotFound, LegalValidationError):
        raise HTTPException(status_code=404, detail="Document not found.")
