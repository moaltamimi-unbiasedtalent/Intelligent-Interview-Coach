"""Admin reporting (P10B-W10.12). EVERY route is GET and read-only, aggregate-only and permissioned.

* ``platform.reports.read``: product, quality, operations and AI economics.
* ``platform.reports.commercial.read``: the commercial report ONLY (a principal with just ``reports.read`` receives no commercial field: the route is 403).
There is no raw-fact, per-user or event-list route, and no request can choose a date expression: the period is one of a fixed set. Reports never write,
enqueue a job, change a flag/pause/plan/billing/AI setting or call a provider.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from src.api.dependencies import get_repository, require_permission
from src.api.schemas.admin import ReportDefinitions, ReportResponse
from src.application import admin_permissions as perm
from src.reporting.service import ReportingError, ReportingService

router = APIRouter(prefix="/admin/reports", tags=["admin-reports"])


def _svc(repo=Depends(get_repository)) -> ReportingService:
    return ReportingService(repo.session_factory)


def _run(fn):
    try:
        return fn()
    except ReportingError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("/definitions", response_model=ReportDefinitions, summary="What each metric means, its source, cohort policy and coverage")
def definitions(_p=Depends(require_permission(perm.REPORTS_READ)), svc=Depends(_svc)) -> ReportDefinitions:
    return ReportDefinitions(**svc.definitions())


@router.get("/product", response_model=ReportResponse, summary="Product usage (aggregates; small cohorts suppressed)")
def product(period: str = Query(default="30d", max_length=12), _p=Depends(require_permission(perm.REPORTS_READ)), svc=Depends(_svc)) -> ReportResponse:
    return ReportResponse(**_run(lambda: svc.product(period)))


@router.get("/quality", response_model=ReportResponse, summary="Quality (feedback, safe evaluation aggregates, retrieval and error outcomes)")
def quality(period: str = Query(default="30d", max_length=12), _p=Depends(require_permission(perm.REPORTS_READ)), svc=Depends(_svc)) -> ReportResponse:
    return ReportResponse(**_run(lambda: svc.quality(period)))


@router.get("/operations", response_model=ReportResponse, summary="Operations (jobs, integrations, knowledge, support, runtime, telemetry); reads current state only")
def operations(period: str = Query(default="30d", max_length=12), _p=Depends(require_permission(perm.REPORTS_READ)), repo=Depends(get_repository),
               svc=Depends(_svc)) -> ReportResponse:
    from src.application.pause import PauseService, PauseStateUnavailable
    from src.integrations import IntegrationService
    from src.jobs.service import JobService
    from src.knowledge_admin.service import KnowledgeAdminService
    from src.platform_config.flags import FeatureFlagService
    from src.secret_store import get_secret_store
    from src.support_repository import SupportRepository

    sf = repo.session_factory

    def safe(fn):
        try:
            return fn()
        except (PauseStateUnavailable, Exception):  # noqa: BLE001 - a section that cannot be read is reported unavailable, never as zero
            return None
    return ReportResponse(**_run(lambda: svc.operations(
        period, job_stats=safe(lambda: JobService(sf).stats()), integration_stats=safe(lambda: IntegrationService(sf, get_secret_store()).stats()),
        knowledge_stats=safe(lambda: KnowledgeAdminService(sf, doc_store=None, jobs=None).stats()), support_stats=safe(lambda: SupportRepository(sf).stats()),
        pause_stats=safe(lambda: PauseService(sf).stats()), flag_stats=safe(lambda: FeatureFlagService(sf).stats()))))


@router.get("/ai-economics", response_model=ReportResponse, summary="AI usage and known cost with explicit token and cost coverage (no live pricing)")
def ai_economics(period: str = Query(default="30d", max_length=12), _p=Depends(require_permission(perm.REPORTS_READ)), svc=Depends(_svc)) -> ReportResponse:
    return ReportResponse(**_run(lambda: svc.ai_economics(period)))


@router.get("/commercial", response_model=ReportResponse,
            summary="Commercial: access-plan assignments and MOCK billing (not live revenue). Separate permission")
def commercial(period: str = Query(default="30d", max_length=12), _p=Depends(require_permission(perm.REPORTS_COMMERCIAL)), svc=Depends(_svc)) -> ReportResponse:
    return ReportResponse(**_run(lambda: svc.commercial(period)))
