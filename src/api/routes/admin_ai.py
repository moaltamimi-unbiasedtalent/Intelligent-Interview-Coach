"""Admin AI and model administration (P10B-W10.7). Every route declares an explicit permission.

There is NO route that activates without an evaluation and a second approver: activation, approval and rollback are separate routes with
separate permissions, the approve route cannot be called by the requester or the author, and no request body can carry a provider model name
(the schema accepts catalogue ids only and the service validates them against the code-defined catalogue). Reads never return a prompt, a
candidate's content or a secret.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from src.ai_admin.service import AIConflict, AIForbidden, AINotFound, AIValidationError
from src.api.dependencies import get_ai_config_service, get_request_id, require_permission
from src.api.schemas.admin import (
    AIActivateBody, AIActivationPage, AIActivationView, AIApprovalPage, AIApprovalView, AICatalogueView, AICodeDefinedView, AIDraftCreate, AIDraftUpdate,
    AIEnvironmentsView, AIEvaluationView, AIOverview, AIReasonBody, AIRollbackBody, AIRuntimeView, AIVersionDetail, AIVersionPage, AIVersionSummary,
)
from src.application import admin_audit as A
from src.application import admin_permissions as perm

router = APIRouter(prefix="/admin/ai", tags=["admin-ai"])


def _guard(fn):
    try:
        return fn()
    except AINotFound:
        raise HTTPException(status_code=404, detail="Not found.")
    except AIValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except AIForbidden as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except AIConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc))


def _audit(request: Request, principal, event: str, target_type: str) -> dict:
    return A.build_audit(event_type=event, actor_user_id=principal.user_id, request_id=get_request_id(request), target_type=target_type)


def _config(body):
    return None if body is None else body.model_dump(exclude_none=True, exclude_unset=True)


@router.get("", response_model=AIOverview, summary="AI administration overview: counts and what this process resolves now")
def overview(_p=Depends(require_permission(perm.AI_READ)), svc=Depends(get_ai_config_service)) -> AIOverview:
    from src.ai_admin import catalogue as C
    from src.ai_admin.resolver import runtime_view

    return AIOverview(stats=svc.stats(), runtime=runtime_view(), catalogue_version=C.CATALOGUE_VERSION)


@router.get("/catalogue", response_model=AICatalogueView, summary="The approved model catalogue (code-defined)")
def catalogue(_p=Depends(require_permission(perm.AI_READ)), svc=Depends(get_ai_config_service)) -> AICatalogueView:
    return AICatalogueView(**svc.catalogue_view())


@router.get("/code-defined", response_model=AICodeDefinedView, summary="What a configuration cannot change (read-only)")
def code_defined(_p=Depends(require_permission(perm.AI_READ)), svc=Depends(get_ai_config_service)) -> AICodeDefinedView:
    return AICodeDefinedView(**svc.code_defined_view())


@router.get("/runtime", response_model=AIRuntimeView, summary="What this process resolves right now (diagnostic; no provider call)")
def runtime(_p=Depends(require_permission(perm.AI_READ))) -> AIRuntimeView:
    from src.ai_admin.resolver import runtime_view

    return AIRuntimeView(**runtime_view())


@router.get("/environments", response_model=AIEnvironmentsView, summary="Active configuration per environment")
def environments(_p=Depends(require_permission(perm.AI_READ)), svc=Depends(get_ai_config_service)) -> AIEnvironmentsView:
    return AIEnvironmentsView(**svc.environments())


@router.get("/history", response_model=AIActivationPage, summary="Append-only activation history")
def history(environment: str | None = None, page: int = Query(default=1, ge=1), page_size: int = Query(default=25, ge=1, le=100),
            _p=Depends(require_permission(perm.AI_READ)), svc=Depends(get_ai_config_service)) -> AIActivationPage:
    return AIActivationPage(**_guard(lambda: svc.history(environment=environment, page=page, page_size=page_size)))


@router.get("/approvals", response_model=AIApprovalPage, summary="Approval requests")
def approvals(status: str | None = None, page: int = Query(default=1, ge=1), page_size: int = Query(default=25, ge=1, le=100),
              _p=Depends(require_permission(perm.AI_READ)), svc=Depends(get_ai_config_service)) -> AIApprovalPage:
    return AIApprovalPage(**_guard(lambda: svc.list_approvals(status=status, page=page, page_size=page_size)))


@router.get("/configs", response_model=AIVersionPage, summary="Configuration versions")
def list_configs(state: str | None = None, page: int = Query(default=1, ge=1), page_size: int = Query(default=25, ge=1, le=100),
                 _p=Depends(require_permission(perm.AI_READ)), svc=Depends(get_ai_config_service)) -> AIVersionPage:
    return AIVersionPage(**_guard(lambda: svc.list_versions(state=state, page=page, page_size=page_size)))


@router.post("/configs", response_model=AIVersionDetail, status_code=201, summary="Create a draft configuration (catalogue ids and bounded tunables only)")
def create_config(body: AIDraftCreate, request: Request, principal=Depends(require_permission(perm.AI_MANAGE)),
                  svc=Depends(get_ai_config_service)) -> AIVersionDetail:
    return AIVersionDetail(**_guard(lambda: svc.create_draft(
        name=body.name, notes=body.notes, config=_config(body.settings), base_version_id=body.base_version_id, actor_user_id=principal.user_id,
        audit=_audit(request, principal, A.ADMIN_AI_CONFIG_CREATED, "ai_config"))))


@router.get("/configs/{public_id}", response_model=AIVersionDetail, summary="One configuration with checks, evaluations, approvals and activations")
def get_config(public_id: str, _p=Depends(require_permission(perm.AI_READ)), svc=Depends(get_ai_config_service)) -> AIVersionDetail:
    return AIVersionDetail(**_guard(lambda: svc.get_version(public_id[:40])))


@router.patch("/configs/{public_id}", response_model=AIVersionDetail, summary="Edit a DRAFT (any later state is frozen)")
def update_config(public_id: str, body: AIDraftUpdate, request: Request, principal=Depends(require_permission(perm.AI_MANAGE)),
                  svc=Depends(get_ai_config_service)) -> AIVersionDetail:
    return AIVersionDetail(**_guard(lambda: svc.update_draft(
        public_id[:40], name=body.name, notes=body.notes, config=_config(body.settings), actor_user_id=principal.user_id,
        audit=_audit(request, principal, A.ADMIN_AI_CONFIG_UPDATED, "ai_config"))))


@router.post("/configs/{public_id}/validate", response_model=AIVersionDetail, summary="Run deterministic validation; a passing draft is frozen")
def validate(public_id: str, request: Request, principal=Depends(require_permission(perm.AI_MANAGE)), svc=Depends(get_ai_config_service)) -> AIVersionDetail:
    return AIVersionDetail(**_guard(lambda: svc.validate(
        public_id[:40], actor_user_id=principal.user_id, audit=_audit(request, principal, A.ADMIN_AI_CONFIG_VALIDATED, "ai_config"))))


@router.post("/configs/{public_id}/evaluate", response_model=AIEvaluationView, status_code=202,
             summary="Queue a deterministic evaluation as a W10.9 job (no provider call)")
def evaluate(public_id: str, request: Request, principal=Depends(require_permission(perm.AI_MANAGE)), svc=Depends(get_ai_config_service)) -> AIEvaluationView:
    return AIEvaluationView(**_guard(lambda: svc.request_evaluation(
        public_id[:40], actor_user_id=principal.user_id, audit=_audit(request, principal, A.ADMIN_AI_EVALUATION_REQUESTED, "ai_config_evaluation"))))


@router.post("/configs/{public_id}/request-approval", response_model=AIApprovalView, status_code=201,
             summary="Submit an evaluated configuration for a DIFFERENT administrator to approve")
def request_approval(public_id: str, body: AIReasonBody, request: Request, principal=Depends(require_permission(perm.AI_MANAGE)),
                     svc=Depends(get_ai_config_service)) -> AIApprovalView:
    return AIApprovalView(**_guard(lambda: svc.request_approval(
        public_id[:40], reason=body.reason, actor_user_id=principal.user_id, audit=_audit(request, principal, A.ADMIN_AI_APPROVAL_REQUESTED, "ai_config_approval"))))


@router.post("/approvals/{approval_id}/approve", response_model=AIApprovalView,
             summary="A DIFFERENT administrator (not the requester, not the author) approves")
def approve(approval_id: str, body: AIReasonBody, request: Request, principal=Depends(require_permission(perm.AI_ACTIVATE)),
            svc=Depends(get_ai_config_service)) -> AIApprovalView:
    return AIApprovalView(**_guard(lambda: svc.decide_approval(
        approval_id[:40], approve=True, reason=body.reason, actor_user_id=principal.user_id,
        audit=_audit(request, principal, A.ADMIN_AI_APPROVED, "ai_config_approval"))))


@router.post("/approvals/{approval_id}/reject", response_model=AIApprovalView, summary="A different administrator rejects the request")
def reject(approval_id: str, body: AIReasonBody, request: Request, principal=Depends(require_permission(perm.AI_ACTIVATE)),
           svc=Depends(get_ai_config_service)) -> AIApprovalView:
    return AIApprovalView(**_guard(lambda: svc.decide_approval(
        approval_id[:40], approve=False, reason=body.reason, actor_user_id=principal.user_id,
        audit=_audit(request, principal, A.ADMIN_AI_REJECTED, "ai_config_approval"))))


@router.post("/configs/{public_id}/activate", response_model=AIActivationView, status_code=201,
             summary="Activate an approved configuration in THIS server's environment (production needs a prior staging activation of the same hash)")
def activate(public_id: str, body: AIActivateBody, request: Request, principal=Depends(require_permission(perm.AI_ACTIVATE)),
             svc=Depends(get_ai_config_service)) -> AIActivationView:
    return AIActivationView(**_guard(lambda: svc.activate(
        public_id[:40], reason=body.reason, actor_user_id=principal.user_id,
        audit=_audit(request, principal, A.ADMIN_AI_ACTIVATED, "ai_config_activation"))))


@router.post("/rollback", response_model=AIActivationView, status_code=201,
             summary="Return THIS server's environment to its previous activation, or to the code-defined defaults")
def rollback(body: AIRollbackBody, request: Request, principal=Depends(require_permission(perm.AI_ACTIVATE)),
             svc=Depends(get_ai_config_service)) -> AIActivationView:
    return AIActivationView(**_guard(lambda: svc.rollback(
        to_code=body.to_code, reason=body.reason, actor_user_id=principal.user_id,
        audit=_audit(request, principal, A.ADMIN_AI_ROLLED_BACK, "ai_config_activation"))))


@router.post("/configs/{public_id}/retire", response_model=AIVersionSummary, summary="Retire a version that is not active anywhere")
def retire(public_id: str, body: AIReasonBody, request: Request, principal=Depends(require_permission(perm.AI_MANAGE)),
           svc=Depends(get_ai_config_service)) -> AIVersionSummary:
    return AIVersionSummary(**_guard(lambda: svc.retire(
        public_id[:40], reason=body.reason, actor_user_id=principal.user_id, audit=_audit(request, principal, A.ADMIN_AI_RETIRED, "ai_config"))))
