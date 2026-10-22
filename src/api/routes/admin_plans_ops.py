"""Plan administration operations (03B, REQ-OWN-02): matrix, comparison, rollback, assignment preview, single and bulk
assignment, assignment history and the effective-entitlement explanation. Every route declares an EXISTING permission
(``plans.read``, ``plans.manage``, ``subscriptions.manage``; the registry is unchanged).

Registered BEFORE ``admin_plans`` because its ``/{version_id}`` route would otherwise capture these fixed paths. Mutations
require an expected revision (409 when stale), write their audit row in the same transaction, and never touch billing:
an assignment is an access decision, not a payment.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from src.admin_repository import AdminNotFound
from src.api.dependencies import get_plan_repository, get_repository, get_request_id, require_permission
from src.api.schemas.admin_plans_ops import (
    AssignmentPreview,
    AssignResult,
    BulkAssignRequest,
    BulkAssignResult,
    EntitlementExplanation,
    PlanComparison,
    PlanMatrix,
    RestoreRequest,
    RestoreResult,
    SingleAssignRequest,
    SubjectPlanState,
    VersionAssignmentPage,
)
from src.application import admin_audit as A
from src.application import admin_permissions as perm
from src.entitlements import EntitlementError
from src.plans_admin import PlanAdminService

router = APIRouter(prefix="/admin/plans", tags=["admin-plans"])


def get_plan_admin(repo=Depends(get_repository)) -> PlanAdminService:
    return PlanAdminService(repo.session_factory)


def _run(fn):
    try:
        return fn()
    except AdminNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except EntitlementError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("/matrix", response_model=PlanMatrix, summary="Entitlement matrix: every registered key against every plan version")
def matrix(_p=Depends(require_permission(perm.PLANS_READ)), svc=Depends(get_plan_admin)) -> PlanMatrix:
    return PlanMatrix(**svc.matrix())


@router.get("/compare", response_model=PlanComparison, summary="Compare two plan versions entitlement by entitlement")
def compare(left: int = Query(ge=1), right: int = Query(ge=1), _p=Depends(require_permission(perm.PLANS_READ)),
            svc=Depends(get_plan_admin)) -> PlanComparison:
    return PlanComparison(**_run(lambda: svc.compare(left, right)))


@router.get("/explain", response_model=EntitlementExplanation,
            summary="Why an account or workspace is allowed or refused each entitlement (plan data only, no candidate content)")
def explain(user_id: int | None = Query(default=None, ge=1), workspace_id: int | None = Query(default=None, ge=1),
            _p=Depends(require_permission(perm.PLANS_READ)), svc=Depends(get_plan_admin)) -> EntitlementExplanation:
    return EntitlementExplanation(**_run(lambda: svc.explain(user_id=user_id, workspace_id=workspace_id)))


@router.get("/subjects/{subject_type}/{subject_id}", response_model=SubjectPlanState,
            summary="Current plan, assignment history and the revision a change must quote for one account or workspace")
def subject_state(subject_type: str, subject_id: int, _p=Depends(require_permission(perm.PLANS_READ)),
                  svc=Depends(get_plan_admin)) -> SubjectPlanState:
    return SubjectPlanState(**_run(lambda: svc.subject_state(subject_type, subject_id)))


@router.get("/versions/{version_id}/assignments", response_model=VersionAssignmentPage,
            summary="Assignment history of one plan version (subject type and id, state, source, dates)")
def version_assignments(version_id: int, page: int = Query(default=1, ge=1), page_size: int = Query(default=25, ge=1, le=100),
                        _p=Depends(require_permission(perm.PLANS_READ)), svc=Depends(get_plan_admin)) -> VersionAssignmentPage:
    return VersionAssignmentPage(**_run(lambda: svc.version_assignments(version_id, page=page, page_size=page_size)))


@router.post("/versions/{version_id}/restore-as-draft", response_model=RestoreResult,
             summary="Rollback: copy an earlier version into a NEW draft (history is never edited; nobody is moved)")
def restore_as_draft(version_id: int, body: RestoreRequest, request: Request,
                     principal=Depends(require_permission(perm.PLANS_MANAGE)), plans=Depends(get_plan_repository)) -> RestoreResult:
    audit = A.build_audit(event_type=A.ADMIN_PLAN_VERSION_CREATED, actor_user_id=principal.user_id,
                          request_id=get_request_id(request), target_type="plan_version", target_id=version_id)
    return RestoreResult(**_run(lambda: plans.restore_as_draft(version_id, expected_revision=body.expected_revision, audit=audit)))


@router.get("/assignments/preview", response_model=AssignmentPreview,
            summary="Preview an assignment as counts only: how many would change and which entitlements are gained or lost")
def preview(plan_code: str = Query(min_length=1, max_length=32), subject_type: str = Query(min_length=1, max_length=16),
            ids: str = Query(min_length=1, max_length=900, description="Comma-separated subject ids (at most 100)"),
            _p=Depends(require_permission(perm.SUBSCRIPTIONS_MANAGE)), svc=Depends(get_plan_admin)) -> AssignmentPreview:
    try:
        parsed = [int(x) for x in ids.split(",") if x.strip()]
    except ValueError:
        raise HTTPException(status_code=422, detail="Subject ids must be whole numbers.")
    return AssignmentPreview(**_run(lambda: svc.assignment_effect(plan_code, subject_type, parsed)))


@router.post("/assignments", response_model=AssignResult,
             summary="Assign ONE account or workspace to the active version of a plan (expected revision required; audited)")
def assign_one(body: SingleAssignRequest, request: Request, principal=Depends(require_permission(perm.SUBSCRIPTIONS_MANAGE)),
               plans=Depends(get_plan_repository), svc=Depends(get_plan_admin)) -> AssignResult:
    def go():
        state = svc.subject_state(body.subject_type, body.subject_id)
        audit = A.build_audit(event_type=A.ADMIN_SUBSCRIPTION_ASSIGNED, actor_user_id=principal.user_id,
                              request_id=get_request_id(request), target_type=body.subject_type, target_id=body.subject_id,
                              before=state["current"]["plan_code"] if state["current"] else None, after=body.plan_code)
        kw = {"workspace_id": body.subject_id} if body.subject_type == "workspace" else {"user_id": body.subject_id}
        return plans.assign(body.plan_code, source="admin", audit=audit, expected_revision=body.expected_revision, **kw)
    return AssignResult(**_run(go))


@router.post("/assignments/bulk", response_model=BulkAssignResult,
             summary="Assign up to 100 accounts or workspaces in ONE transaction (needs the preview revision; all or nothing)")
def assign_bulk(body: BulkAssignRequest, request: Request, principal=Depends(require_permission(perm.SUBSCRIPTIONS_MANAGE)),
                svc=Depends(get_plan_admin)) -> BulkAssignResult:
    rid = get_request_id(request)

    def audit_for(kind: str, subject_id: int, batch: int):
        return A.build_audit(event_type=A.ADMIN_SUBSCRIPTION_ASSIGNED, actor_user_id=principal.user_id, request_id=rid,
                             target_type=kind, target_id=subject_id, after=body.plan_code, bulk=True, batch_size=batch)
    return BulkAssignResult(**_run(lambda: svc.bulk_assign(body.plan_code, body.subject_type, body.subject_ids,
                                                           preview_revision=body.preview_revision, audit_for=audit_for)))
