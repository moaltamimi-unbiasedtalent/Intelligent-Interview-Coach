"""Caller-scoped usage-quota presentation (W12.4D-P4-A): READ-ONLY. Reports only the AUTHENTICATED caller's own server-computed state; grants and changes nothing.

While commercial quota enforcement is disabled (the state for every real candidate) it returns ``enforcement_active: false`` and no allowance, number or reset
time at all. With enforcement on, a feature without an owner-approved allowance is ``not_configured`` and carries no number. Never a price, upgrade prompt,
provider detail, other user's data or infrastructure detail.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from src.api.dependencies import get_current_user_id, get_repository
from src.api.dependencies import get_entitlement_service

router = APIRouter(prefix="/usage-quotas", tags=["usage-quotas"])


class QuotaFeatureOut(BaseModel):
    feature: str
    unit: str
    status: str                       # available | exhausted | not_configured | unavailable
    period: str | None = None
    allowance: int | None = None
    used: int | None = None
    remaining: int | None = None
    reset_at: str | None = None


class UsageQuotasResponse(BaseModel):
    enforcement_active: bool
    policy_version: str | None = None
    features: list[QuotaFeatureOut]


@router.get("", response_model=UsageQuotasResponse, summary="Caller's usage-quota state (read-only; empty while enforcement is disabled)")
def usage_quotas(user_id: int = Depends(get_current_user_id), repo=Depends(get_repository), entitlements=Depends(get_entitlement_service)) -> UsageQuotasResponse:
    from src.application.usage_quota import UsageQuotaService

    return UsageQuotasResponse(**UsageQuotaService(repo.session_factory, entitlements).snapshot(user_id))
