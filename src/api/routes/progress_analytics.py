"""Premium progress analytics (W12.4D-P4-B): READ-ONLY, caller-scoped, deterministic. Disabled by default (``PREMIUM_ANALYTICS_ENABLED``): while disabled every
route answers ``feature_disabled`` with no data. The interviews analysed are the caller's eligible completed history under the P2-B window; there is no
second selection rule, no LLM call and no stored result. Foreign or missing ids are 404; an owned interview outside the window is 403 ``history_not_available``."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from src.api.dependencies import get_current_user_id, get_entitlement_service, get_history_access_policy, get_repository
from src.api.schemas.progress_analytics import AnalyticsCompareResponse, AnalyticsOverviewResponse
from src.application import progress_analytics as PA
from src.repository import HistoryRestricted

router = APIRouter(prefix="/progress/analytics", tags=["progress-analytics"])


def get_analytics_policy(entitlements=Depends(get_entitlement_service)):
    """Built per request (nothing cached); disabled by default via a code constant."""
    return PA.PremiumAnalyticsPolicy(entitlements)


@router.get("", response_model=AnalyticsOverviewResponse, summary="Premium progress analytics over the caller's eligible completed history (disabled by default)")
def analytics_overview(
    opportunity_id: int | None = Query(None, ge=1),
    repo=Depends(get_repository),
    user_id: int = Depends(get_current_user_id),
    policy=Depends(get_analytics_policy),
    history=Depends(get_history_access_policy),
) -> AnalyticsOverviewResponse:
    state = policy.decide(user_id)
    if state != "allowed":
        return AnalyticsOverviewResponse(state=state)
    window = history.window_for(user_id)
    if opportunity_id is not None:
        from src.opportunity_repository import OpportunityRepository

        if OpportunityRepository(repo.session_factory).get(user_id, opportunity_id) is None:
            raise HTTPException(status_code=404, detail="Opportunity not found.")      # foreign and missing are indistinguishable
    rows, truncated = repo.analytics_rows(user_id, window, opportunity_id=opportunity_id, limit=PA.MAX_ANALYZED_INTERVIEWS)
    return AnalyticsOverviewResponse(**PA.overview(rows, truncated=truncated))


@router.get("/compare", response_model=AnalyticsCompareResponse, summary="Compare two of the caller's eligible completed interviews (disabled by default)")
def analytics_compare(
    base: int = Query(..., ge=1),
    target: int = Query(..., ge=1),
    repo=Depends(get_repository),
    user_id: int = Depends(get_current_user_id),
    policy=Depends(get_analytics_policy),
    history=Depends(get_history_access_policy),
) -> AnalyticsCompareResponse:
    state = policy.decide(user_id)
    if state != "allowed":
        return AnalyticsCompareResponse(state=state)
    if base == target:
        raise HTTPException(status_code=422, detail="Choose two different interviews.")
    window = history.window_for(user_id)
    rows, _ = repo.analytics_rows(user_id, window, limit=PA.MAX_ANALYZED_INTERVIEWS, only_ids=[base, target])
    found = {r["id"]: r for r in rows}
    for iid in (base, target):
        if iid not in found:
            if repo.is_restricted(user_id, iid, window):
                raise HistoryRestricted(iid)                                            # owned but outside the window: never compared
            raise HTTPException(status_code=404, detail="Interview not found.")
    return AnalyticsCompareResponse(**PA.compare(found[base], found[target]))
