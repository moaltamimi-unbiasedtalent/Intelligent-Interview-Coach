"""Command Center read model API (package 03D1). EVERY route is GET, read-only, aggregate-only and permissioned with an EXISTING permission (the registry stays 44).

Permission per route, and why (the least privilege that already owns that data; nothing here is a new permission and nothing is a candidate-content grant):

* ``/definitions``        ``platform.overview.read``  the landing permission every Admin preset holds; the response is filtered to the metrics whose own permission the caller holds.
* ``/health``             ``platform.overview.read``  platform health is what the existing Command Center home already shows to every Admin preset.
* ``/ai-operations``      ``platform.ai.read``        AI usage, cost, outcomes and model state are the AI administration domain (``/admin/ai`` reads).
* ``/jobs``               ``platform.jobs.read``      the job queue domain (``/admin/jobs`` reads).
* ``/knowledge``          ``platform.knowledge.read`` governed knowledge state and its health alerts (``/admin/knowledge`` reads).
* ``/alerts``             ``platform.security.read``  alerts are read through the security domain today (``/admin/security/alerts``).
* ``/security-signals``   ``platform.security.read``  counts of the audit projection the security domain already exposes.
* ``/candidate-activity`` ``platform.reports.read``   the same aggregates, with the same cohort suppression, as ``/admin/reports/product``.

Reads are not audit-logged: the existing reporting reads (``/admin/reports/*``) and the other aggregate reads here are not, and an aggregate read exposes no
candidate or per-record data to account for. The period is one of a fixed set (an unknown period is 422); no client-supplied date or expression is accepted.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from src.api.dependencies import get_repository, require_permission
from src.api.schemas.command_center import CommandCenterDefinitions, CommandCenterResponse
from src.application import admin_permissions as perm
from src.reporting import command_center as CC
from src.reporting.contract import PERIOD_KINDS
from src.reporting.definitions import DEFAULT_PERIOD

router = APIRouter(prefix="/admin/command-center", tags=["admin-command-center"])


def _svc(repo=Depends(get_repository)) -> CC.CommandCenterService:
    return CC.CommandCenterService(repo.session_factory)


def _run(fn, period: str) -> CommandCenterResponse:
    try:
        return fn(period)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("/definitions", response_model=CommandCenterDefinitions, summary="The metric definitions (03K contract) the caller may read")
def definitions(principal=Depends(require_permission(perm.OVERVIEW_READ))) -> CommandCenterDefinitions:
    metrics, dims = CC.visible_definitions(perm.permissions_for_role(principal.platform_role))
    return CommandCenterDefinitions(periods=list(PERIOD_KINDS), default_period=DEFAULT_PERIOD, metrics=list(metrics), dimensions=list(dims))


@router.get("/health", response_model=CommandCenterResponse, summary="Platform health summary (aggregates; no provider is probed)")
def health(period: str = Query(default=DEFAULT_PERIOD, max_length=12), _p=Depends(require_permission(perm.OVERVIEW_READ)), svc=Depends(_svc)) -> CommandCenterResponse:
    return _run(svc.health, period)


@router.get("/ai-operations", response_model=CommandCenterResponse,
            summary="AI operations: usage, known tokens and cost (partial coverage), outcomes, retries, latency, model state, pause and limit state")
def ai_operations(period: str = Query(default=DEFAULT_PERIOD, max_length=12), _p=Depends(require_permission(perm.AI_READ)), svc=Depends(_svc)) -> CommandCenterResponse:
    return _run(svc.ai_operations, period)


@router.get("/jobs", response_model=CommandCenterResponse, summary="Job queue health (counts, ages, failure rate and duration; never a payload)")
def jobs(period: str = Query(default=DEFAULT_PERIOD, max_length=12), _p=Depends(require_permission(perm.JOBS_READ)), svc=Depends(_svc)) -> CommandCenterResponse:
    return _run(svc.jobs, period)


@router.get("/knowledge", response_model=CommandCenterResponse, summary="Knowledge readiness (governed versions, index records, knowledge health alerts)")
def knowledge(period: str = Query(default=DEFAULT_PERIOD, max_length=12), _p=Depends(require_permission(perm.KNOWLEDGE_READ)), svc=Depends(_svc)) -> CommandCenterResponse:
    return _run(svc.knowledge, period)


@router.get("/alerts", response_model=CommandCenterResponse, summary="Alert summary (counts by category and severity; no alert text)")
def alerts(period: str = Query(default=DEFAULT_PERIOD, max_length=12), _p=Depends(require_permission(perm.SECURITY_READ)), svc=Depends(_svc)) -> CommandCenterResponse:
    return _run(svc.alerts, period)


@router.get("/security-signals", response_model=CommandCenterResponse, summary="Auth and security signal counts (no actor, address or e-mail)")
def security_signals(period: str = Query(default=DEFAULT_PERIOD, max_length=12), _p=Depends(require_permission(perm.SECURITY_READ)),
                     svc=Depends(_svc)) -> CommandCenterResponse:
    return _run(svc.security, period)


@router.get("/candidate-activity", response_model=CommandCenterResponse, summary="Candidate activity aggregates (cohorts below the floor are suppressed)")
def candidate_activity(period: str = Query(default=DEFAULT_PERIOD, max_length=12), _p=Depends(require_permission(perm.REPORTS_READ)),
                       svc=Depends(_svc)) -> CommandCenterResponse:
    return _run(svc.candidate_activity, period)
