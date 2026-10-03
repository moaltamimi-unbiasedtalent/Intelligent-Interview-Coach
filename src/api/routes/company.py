"""Candidate-facing Company Intelligence (P10B Wave 5).

A directable, owner-scoped endpoint over the governed external research engine (Phase 7F) - the
capability the founder could not find. It reuses every existing safety control:

* plan entitlement ``current_market_research`` (in the Basic plan - all users);
* the operator pause switch ``current_market`` (truthful 503 when paused);
* the per-user cost ceiling ``cost_research_user`` and the global ceiling;
* the SSRF/robots/injection/size guards inside the research engine (untouched).

Identity is disambiguated deterministically (a company is only researched against an explicit
website); the optional JD is resolved owner-scoped server-side (a foreign/missing id yields no
text and is never disclosed). The response separates FACT / REVIEW / MODEL_INFERENCE and carries
honest provider status - it never fabricates a successful research state.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from src.api.dependencies import (
    adzuna_credentials_configured,
    get_current_user_id,
    get_research_service,
    require_entitlement,
    resolve_document_text,
)
from src.api.guards import cost_limit, require_not_paused
from src.application.authorization import Capability
from src.application.company_intelligence_service import (
    CompanyIntelligenceQuery,
    CompanyIntelligenceReport,
    CompanyIntelligenceService,
)

router = APIRouter(prefix="/research", tags=["company-intelligence"])


@router.post("/company", response_model=CompanyIntelligenceReport,
             summary="Directable company intelligence for interview preparation")
def company_intelligence(
    body: CompanyIntelligenceQuery,
    request: Request,
    user_id: int = Depends(get_current_user_id),
    _principal=Depends(require_entitlement(Capability.CURRENT_MARKET_RESEARCH)),
    _pause=Depends(require_not_paused("current_market")),
    _cost=Depends(cost_limit("cost_research_user")),
    research_service=Depends(get_research_service),
) -> CompanyIntelligenceReport:
    """Research one company for interview preparation. Never raises for a provider failure -
    an unavailable/partial provider is reported honestly in the response."""

    def _resolve_jd(document_id: int) -> str | None:
        # Owner-scoped; a foreign/missing/deleted document returns None (never another user's data).
        return resolve_document_text(request, user_id=user_id, document_id=document_id)

    service = CompanyIntelligenceService(
        research_service,
        resolve_jd=_resolve_jd,
        adzuna_configured=adzuna_credentials_configured(),
    )
    return service.research(body, user_id=user_id)
