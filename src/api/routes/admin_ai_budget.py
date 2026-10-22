"""Read-only Admin status of the production AI budget governor (05C). One GET, gated by the EXISTING ``platform.ai.read`` permission (no new permission).

It reports state, counts and remaining headroom only. It never returns a provider key, the approval marker, a prompt, a model response or a user identifier, and there is no route here
that changes the budget, the kill switch or the configuration (those are owner-managed configuration and operator actions outside the web application).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict

from src.api.dependencies import get_repository, require_permission
from src.application import admin_permissions as perm
from src.llm.budget.status import budget_status

router = APIRouter(prefix="/admin/ai", tags=["admin-ai"])


class AiBudgetStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state: str
    reason: str | None = None
    enforcement: str
    budget_class: str | None = None
    config_loaded: bool
    approval_marker_configured: bool
    approval_marker_presented: bool
    env_kill_switch: bool
    limits: dict[str, int] | None = None
    priced_models: int | None = None
    ledger: dict[str, Any] | None = None
    note: str


@router.get("/budget", response_model=AiBudgetStatus, summary="AI budget governor status: state, counts and remaining headroom (read-only, no key or prompt)")
def ai_budget_status(_p=Depends(require_permission(perm.AI_READ)), repo=Depends(get_repository)) -> AiBudgetStatus:
    return AiBudgetStatus(**budget_status(repo.session_factory))
