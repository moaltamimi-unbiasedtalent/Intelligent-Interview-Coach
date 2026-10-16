"""Plan-aware AI model-profile metadata (W12.4D-P2-C): READ-ONLY, for a FUTURE candidate selector.

It reports which of Fast, Balanced and Advanced the caller's entitlement would authorize and the profile that would be used by default. It grants nothing, changes
nothing and never returns a provider model id, a price, a quality claim or an upgrade prompt. ``selector_active`` is False while the server-controlled rollout gate
is disabled, which is the state for every real candidate until a reviewed release enables it; the frontend does not use this endpoint yet (P3 owns the Premium UI).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from src.api.dependencies import get_current_user_id, get_model_profile_policy

router = APIRouter(prefix="/model-profiles", tags=["model-profiles"])


class ModelProfileOut(BaseModel):
    id: str
    authorized: bool
    description: str


class ModelProfilesResponse(BaseModel):
    selector_active: bool
    default: str
    profiles: list[ModelProfileOut]


@router.get("", response_model=ModelProfilesResponse, summary="Plan-aware model-profile metadata (read-only; no selector is active yet)")
def model_profiles(user_id: int = Depends(get_current_user_id), policy=Depends(get_model_profile_policy)) -> ModelProfilesResponse:
    return ModelProfilesResponse(**policy.catalogue(user_id))
