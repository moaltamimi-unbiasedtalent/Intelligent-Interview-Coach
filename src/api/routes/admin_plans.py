"""Admin plan catalogue and version lifecycle (P10B-W10.4). Every route declares an explicit permission.

Plans are versioned: a DRAFT is the only editable state, ACTIVE and RETIRED versions are immutable, activating
a version never moves existing subscribers (they stay pinned), and nothing here touches billing, prices or
payment. Entitlement keys come from the code registry; Admin input cannot invent one.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt

from src.admin_repository import AdminNotFound
from src.api.dependencies import get_plan_repository, get_request_id, require_permission
from src.api.schemas.admin import AssignablePlan, PlanDetail, PlanList
from src.application import admin_audit as A
from src.application import admin_permissions as perm
from src.entitlements import EntitlementError

router = APIRouter(prefix="/admin/plans", tags=["admin-plans"])


class EntitlementValue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: StrictBool          # no coercion: "yes" or 1 are rejected
    limit: StrictInt | None = None


class DraftUpdate(BaseModel):
    entitlements: dict[str, EntitlementValue] = Field(min_length=1, max_length=50)


def _audit(event: str, request: Request, principal, version_id):
    return A.build_audit(event_type=event, actor_user_id=principal.user_id, request_id=get_request_id(request),
                         target_type="plan_version", target_id=version_id)


def _run(fn):
    try:
        return fn()
    except AdminNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except EntitlementError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("", response_model=PlanList, summary="Plan catalogue: every version with its lifecycle and subscriber counts")
def catalogue(_p=Depends(require_permission(perm.PLANS_READ)), plans=Depends(get_plan_repository)) -> PlanList:
    return PlanList(items=plans.list_versions())


@router.get("/assignable", response_model=list[AssignablePlan], summary="Active plan versions an operator may assign")
def assignable(_p=Depends(require_permission(perm.SUBSCRIPTIONS_MANAGE)), plans=Depends(get_plan_repository)):
    return [AssignablePlan(**p) for p in plans.assignable_plans()]


@router.get("/{version_id}", response_model=PlanDetail, summary="One plan version with its typed entitlement values")
def detail(version_id: int, _p=Depends(require_permission(perm.PLANS_READ)), plans=Depends(get_plan_repository)) -> PlanDetail:
    d = plans.get_version(version_id)
    if d is None:
        raise HTTPException(status_code=404, detail="Plan version not found.")
    return PlanDetail(**d)


@router.post("/{plan_code}/versions", summary="Create the next DRAFT version of an existing plan (copies the latest)")
def create_draft(plan_code: str, request: Request, principal=Depends(require_permission(perm.PLANS_MANAGE)),
                 plans=Depends(get_plan_repository)) -> dict:
    audit = _audit(A.ADMIN_PLAN_VERSION_CREATED, request, principal, plan_code)
    return _run(lambda: plans.create_draft(plan_code, audit=audit))


@router.patch("/versions/{version_id}/entitlements", summary="Edit a DRAFT version's entitlement values (registry keys only)")
def update_draft(version_id: int, body: DraftUpdate, request: Request,
                 principal=Depends(require_permission(perm.PLANS_MANAGE)), plans=Depends(get_plan_repository)) -> dict:
    audit = _audit(A.ADMIN_PLAN_VERSION_UPDATED, request, principal, version_id)
    values = {k: v.model_dump() for k, v in body.entitlements.items()}
    return _run(lambda: plans.update_draft(version_id, values, audit=audit))


@router.post("/versions/{version_id}/activate",
             summary="Activate a draft: it becomes assignable and immutable; the previous active version is retired; nobody is moved")
def activate(version_id: int, request: Request, principal=Depends(require_permission(perm.PLANS_MANAGE)),
             plans=Depends(get_plan_repository)) -> dict:
    audit = _audit(A.ADMIN_PLAN_VERSION_ACTIVATED, request, principal, version_id)
    return _run(lambda: plans.activate(version_id, audit=audit))


@router.post("/versions/{version_id}/retire", summary="Retire an active version (no new assignments; subscribers stay pinned)")
def retire(version_id: int, request: Request, principal=Depends(require_permission(perm.PLANS_MANAGE)),
           plans=Depends(get_plan_repository)) -> dict:
    audit = _audit(A.ADMIN_PLAN_VERSION_RETIRED, request, principal, version_id)
    return _run(lambda: plans.retire(version_id, audit=audit))
