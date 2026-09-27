"""Candidate Opportunity routes (P10B Wave 6).

A candidate's private preparation context for one job. Every operation is owner-scoped by the
trusted authenticated user id (never client-supplied); a foreign/unknown id returns 404 and never
another user's data. Create/archive/delete emit metadata-only audit events. Opportunity is BASIC
(no capability gate) - it is the same class of owned candidate data as history/documents/memory.

It orchestrates existing services: it does not persist company research, evidence or reports - it
only groups them. Company Intelligence, Prepare and Practice are reached with Opportunity CONTEXT
(the client passes the opportunity's fields / id to the existing endpoints).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path, Query

from src.api.dependencies import get_audit_repository, get_current_user_id, get_opportunity_service
from src.api.schemas.opportunity import (
    OpportunityContextOut,
    OpportunityCreateRequest,
    OpportunityListResponse,
    OpportunityOut,
    OpportunityOverviewOut,
    OpportunityUpdateRequest,
)

router = APIRouter(prefix="/opportunities", tags=["opportunities"])


@router.post("", response_model=OpportunityOut, status_code=201,
             summary="Create a candidate opportunity")
def create_opportunity(
    body: OpportunityCreateRequest,
    user_id: int = Depends(get_current_user_id),
    service=Depends(get_opportunity_service),
    audit=Depends(get_audit_repository),
) -> OpportunityOut:
    created = service.create(
        user_id, target_role=body.target_role, title=body.title,
        company_name=body.company_name, company_location=body.company_location,
        company_country=body.company_country, company_domain=body.company_domain,
        job_description_document_id=body.job_description_document_id, notes=body.notes)
    audit.record(event_type="opportunity.created", actor_user_id=user_id,
                 target_type="opportunity", target_id=str(created["id"]))
    return OpportunityOut(**created)


@router.get("", response_model=OpportunityListResponse, summary="List your opportunities")
def list_opportunities(
    include_archived: bool = Query(default=False),
    user_id: int = Depends(get_current_user_id),
    service=Depends(get_opportunity_service),
) -> OpportunityListResponse:
    rows = service.list(user_id, include_archived=include_archived)
    return OpportunityListResponse(opportunities=[OpportunityOut(**r) for r in rows])


@router.get("/{opportunity_id}", response_model=OpportunityOverviewOut,
            summary="Opportunity overview (home)")
def get_opportunity(
    opportunity_id: int = Path(ge=1),
    user_id: int = Depends(get_current_user_id),
    service=Depends(get_opportunity_service),
) -> OpportunityOverviewOut:
    overview = service.overview(user_id, opportunity_id)
    if overview is None:
        raise HTTPException(status_code=404, detail="Opportunity not found.")
    return OpportunityOverviewOut(**overview)


@router.get("/{opportunity_id}/context", response_model=OpportunityContextOut,
            summary="Bounded context for Prepare/Practice")
def opportunity_context(
    opportunity_id: int = Path(ge=1),
    user_id: int = Depends(get_current_user_id),
    service=Depends(get_opportunity_service),
) -> OpportunityContextOut:
    ctx = service.context(user_id, opportunity_id)
    if ctx is None:
        raise HTTPException(status_code=404, detail="Opportunity not found.")
    return OpportunityContextOut(**ctx)


@router.patch("/{opportunity_id}", response_model=OpportunityOut,
              summary="Update an opportunity")
def update_opportunity(
    body: OpportunityUpdateRequest,
    opportunity_id: int = Path(ge=1),
    user_id: int = Depends(get_current_user_id),
    service=Depends(get_opportunity_service),
    audit=Depends(get_audit_repository),
) -> OpportunityOut:
    patch = body.model_dump(exclude_unset=True)
    updated = service.update(user_id, opportunity_id, patch=patch)
    if updated is None:
        raise HTTPException(status_code=404, detail="Opportunity not found.")
    if patch.get("status") == "archived":
        audit.record(event_type="opportunity.archived", actor_user_id=user_id,
                     target_type="opportunity", target_id=str(opportunity_id))
    return OpportunityOut(**updated)


@router.post("/{opportunity_id}/archive", response_model=OpportunityOut,
             summary="Archive an opportunity")
def archive_opportunity(
    opportunity_id: int = Path(ge=1),
    user_id: int = Depends(get_current_user_id),
    service=Depends(get_opportunity_service),
    audit=Depends(get_audit_repository),
) -> OpportunityOut:
    archived = service.archive(user_id, opportunity_id)
    if archived is None:
        raise HTTPException(status_code=404, detail="Opportunity not found.")
    audit.record(event_type="opportunity.archived", actor_user_id=user_id,
                 target_type="opportunity", target_id=str(opportunity_id))
    return OpportunityOut(**archived)


@router.delete("/{opportunity_id}", summary="Delete an opportunity")
def delete_opportunity(
    opportunity_id: int = Path(ge=1),
    user_id: int = Depends(get_current_user_id),
    service=Depends(get_opportunity_service),
    audit=Depends(get_audit_repository),
) -> dict:
    # Deleting an Opportunity NEVER deletes its linked interviews/documents/evidence - the links
    # are set to NULL so history and the global evidence bank survive.
    deleted = service.delete(user_id, opportunity_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Opportunity not found.")
    audit.record(event_type="opportunity.deleted", actor_user_id=user_id,
                 target_type="opportunity", target_id=str(opportunity_id))
    return {"deleted": True}
