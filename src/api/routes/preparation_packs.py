"""Opportunity Preparation Packs (W12.4D-P5-A): candidate API. Authenticated, owner-scoped, no raw model output, no credentials.

GENERATION is disabled by default (``PREPARATION_PACK_GENERATION_ENABLED``) and needs an active Premium entitlement; it is authorized and the opportunity
ownership verified BEFORE the AI admission dependency, so a denied request consumes no rate-limit slot, no quota and no provider call. READING, listing,
downloading and deleting stored Packs is never gated by plan or by the generation constant: a Pack is an independent candidate-owned artifact and stays
accessible after a downgrade. Foreign and missing ids are indistinguishable (404)."""

from __future__ import annotations

from typing import Any, Iterator

from fastapi import APIRouter, Depends, Header, HTTPException, Path, Query, Request, Response
from pydantic import BaseModel, Field

from src.ai_protection import ai_operation
from src.api.dependencies import (
    adzuna_credentials_configured,
    get_current_user_id,
    get_entitlement_service,
    get_pricing,
    get_repository,
    get_research_service,
    resolve_document_text,
)
from src.application import preparation_pack as PP
from src.application.preparation_pack import PackGenerationUnavailable
from src.application.preparation_pack_service import ModelGuidanceGenerator, PreparationPackService, collect_inputs
from src.opportunity_repository import OpportunityRepository
from src.preparation_pack_repository import PreparationPackRepository

router = APIRouter(prefix="/opportunities/{opportunity_id}/packs", tags=["preparation-packs"])
artifact_router = APIRouter(prefix="/preparation-packs", tags=["preparation-packs"])


class PackSummaryOut(BaseModel):
    id: int
    opportunity_id: int | None = None
    revision: int
    status: str
    schema_version: str
    failure_category: str | None = None
    created_at: str | None = None
    completed_at: str | None = None
    section_statuses: dict[str, str] = Field(default_factory=dict)


class PackDetailOut(PackSummaryOut):
    content: dict[str, Any] | None = None


class PackListOut(BaseModel):
    packs: list[PackSummaryOut]


class PackAvailabilityOut(BaseModel):
    """``generation``: feature_disabled | not_entitled | available. Display only: generation is re-authorized on the server."""

    generation: str


class PackGenerationOut(BaseModel):
    outcome: str                      # created | duplicate | in_progress
    pack: PackSummaryOut


def get_pack_policy(entitlements=Depends(get_entitlement_service)):
    return PP.PackAccessPolicy(entitlements)


def get_pack_repo(repo=Depends(get_repository)) -> PreparationPackRepository:
    return PreparationPackRepository(repo.session_factory)


def get_pack_generator(request: Request, pricing=Depends(get_pricing)) -> Iterator[Any]:
    """The model stage over the existing OpenRouter client (closed afterwards). Tests override this dependency, so no provider is ever reached offline."""
    from src.api.dependencies import get_app_config
    from src.openrouter_client import OpenRouterClient

    client = OpenRouterClient(get_app_config(request))
    try:
        yield ModelGuidanceGenerator(client, pricing)
    finally:
        client.close()


def _own_opportunity(repo, user_id: int, opportunity_id: int) -> dict:
    opp = OpportunityRepository(repo.session_factory).get(user_id, opportunity_id)
    if opp is None:
        raise HTTPException(status_code=404, detail="Opportunity not found.")
    return opp


def authorize_generation(opportunity_id: int = Path(..., ge=1), user_id: int = Depends(get_current_user_id), policy=Depends(get_pack_policy),
                         repo=Depends(get_repository)) -> dict:
    """Entitlement first (no probing while disabled or not entitled), then ownership. Runs BEFORE the AI admission dependency."""
    decision = policy.decide(user_id)
    if decision != "allowed":
        raise PackGenerationUnavailable(decision)
    return _own_opportunity(repo, user_id, opportunity_id)


@router.get("/availability", response_model=PackAvailabilityOut, summary="Whether Pack generation is currently available to the caller (display only)")
def availability(opportunity_id: int = Path(..., ge=1), user_id: int = Depends(get_current_user_id), policy=Depends(get_pack_policy),
                 repo=Depends(get_repository)) -> PackAvailabilityOut:
    _own_opportunity(repo, user_id, opportunity_id)
    d = policy.decide(user_id)
    return PackAvailabilityOut(generation="available" if d == "allowed" else d)


@router.get("", response_model=PackListOut, summary="The caller's Packs for one opportunity (never plan-gated)")
def list_packs(opportunity_id: int = Path(..., ge=1), user_id: int = Depends(get_current_user_id), repo=Depends(get_repository),
               packs: PreparationPackRepository = Depends(get_pack_repo)) -> PackListOut:
    _own_opportunity(repo, user_id, opportunity_id)
    packs.reap_stale(older_than_seconds=PP.STALE_GENERATION_SECONDS, user_id=user_id, opportunity_id=opportunity_id)
    return PackListOut(packs=[PackSummaryOut(**p) for p in packs.list_for_opportunity(user_id, opportunity_id)])


@router.post("", response_model=PackGenerationOut, summary="Generate a Preparation Pack (disabled by default; Premium only)")
def generate_pack(
    request: Request,
    opportunity: dict = Depends(authorize_generation),
    _ai=Depends(ai_operation("career", "pack_generate")),
    user_id: int = Depends(get_current_user_id),
    repo=Depends(get_repository),
    packs: PreparationPackRepository = Depends(get_pack_repo),
    generator=Depends(get_pack_generator),
    research=Depends(get_research_service),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> PackGenerationOut:
    import uuid

    from src.application.company_intelligence_service import CompanyIntelligenceQuery, CompanyIntelligenceService

    def _company(opp: dict):
        svc = CompanyIntelligenceService(research, resolve_jd=lambda d: resolve_document_text(request, user_id=user_id, document_id=d),
                                         adzuna_configured=adzuna_credentials_configured())
        q = CompanyIntelligenceQuery(company_name=opp["company_name"], location=opp.get("company_location"), country=opp.get("company_country"),
                                     website=opp.get("company_domain"), target_role=opp.get("target_role"))
        return svc.research(q, user_id=user_id)

    op_key = f"pack:{user_id}:{opportunity['id']}:{(idempotency_key or uuid.uuid4().hex)[:60]}"
    service = PreparationPackService(packs, generator=generator)
    outcome, summary = service.generate(
        user_id=user_id, opportunity=opportunity, op_key=op_key,
        collect=lambda: collect_inputs(repo.session_factory, user_id=user_id, opportunity=opportunity,
                                       jd_resolver=lambda d: resolve_document_text(request, user_id=user_id, document_id=d, max_chars=PP.MAX_JD_CHARS),
                                       company_runner=_company))
    final = packs.get(user_id, summary["id"]) or summary
    return PackGenerationOut(outcome=outcome, pack=PackSummaryOut(**{k: final[k] for k in PackSummaryOut.model_fields if k in final}))


def _owned_pack(packs: PreparationPackRepository, user_id: int, pack_id: int) -> dict:
    p = packs.get(user_id, pack_id)
    if p is None:
        raise HTTPException(status_code=404, detail="Preparation Pack not found.")
    return p


@artifact_router.get("/{pack_id}", response_model=PackDetailOut, summary="One of the caller's Packs (never plan-gated)")
def get_pack(pack_id: int = Path(..., ge=1), user_id: int = Depends(get_current_user_id), packs: PreparationPackRepository = Depends(get_pack_repo)) -> PackDetailOut:
    p = _owned_pack(packs, user_id, pack_id)
    return PackDetailOut(**{k: p[k] for k in PackDetailOut.model_fields if k in p})


@artifact_router.get("/{pack_id}/download", summary="Download a completed Pack as JSON or Markdown (never plan-gated)")
def download_pack(pack_id: int = Path(..., ge=1), format: str = Query("json", pattern="^(json|md)$"), user_id: int = Depends(get_current_user_id),
                  packs: PreparationPackRepository = Depends(get_pack_repo)) -> Response:
    import json

    p = _owned_pack(packs, user_id, pack_id)
    if p["status"] not in ("completed", "insufficient_evidence") or not p["content"]:
        raise HTTPException(status_code=409, detail="This Pack has no content to download.")
    if format == "md":
        return Response(PP.render_markdown(p["content"]), media_type="text/markdown; charset=utf-8",
                        headers={"Content-Disposition": f'attachment; filename="preparation-pack-{pack_id}.md"', "X-Content-Type-Options": "nosniff"})
    return Response(json.dumps({"pack_id": p["id"], "revision": p["revision"], "status": p["status"], "schema_version": p["schema_version"], "content": p["content"]}, ensure_ascii=False, indent=2),
                    media_type="application/json", headers={"Content-Disposition": f'attachment; filename="preparation-pack-{pack_id}.json"', "X-Content-Type-Options": "nosniff"})


@artifact_router.delete("/{pack_id}", summary="Delete one of the caller's Packs")
def delete_pack(pack_id: int = Path(..., ge=1), user_id: int = Depends(get_current_user_id), packs: PreparationPackRepository = Depends(get_pack_repo)) -> dict:
    if not packs.delete(user_id, pack_id):
        raise HTTPException(status_code=404, detail="Preparation Pack not found.")
    return {"deleted": True}
