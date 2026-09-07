"""Health, readiness and capabilities routes (no provider calls, no secrets)."""

from __future__ import annotations

import os

from fastapi import APIRouter, Request

from src.api.schemas.common import CapabilitiesResponse, HealthResponse

router = APIRouter(tags=["health"])


def _live_enabled() -> bool:
    return os.environ.get("INTERVIEW_LIVE_ENABLED", "").strip().lower() in {
        "1", "true", "yes", "on"}


@router.get("/health", response_model=HealthResponse, summary="Liveness")
def health(request: Request) -> HealthResponse:
    return HealthResponse(
        status="ok",
        service="intelligent-interview-coach",
        version=request.app.state.settings.version,
    )


@router.get("/ready", response_model=HealthResponse, summary="Readiness")
def ready(request: Request) -> HealthResponse:
    # Liveness == readiness for now: the app has no blocking startup dependency and
    # expensive resources build lazily on first use. No provider call here.
    return health(request)


@router.get("/capabilities", response_model=CapabilitiesResponse,
            summary="Safe feature availability")
def capabilities() -> CapabilitiesResponse:
    # Deterministic RAG today; agent features are planned (advertised as False).
    return CapabilitiesResponse(live_interview_enabled=_live_enabled())
