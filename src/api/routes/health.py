"""Health, readiness and capabilities routes (no provider calls, no secrets)."""

from __future__ import annotations

import os

from fastapi import APIRouter, Request

from src.api.schemas.common import CapabilitiesResponse, HealthResponse

router = APIRouter(tags=["health"])


def _flag_enabled(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _live_enabled() -> bool:
    return _flag_enabled("INTERVIEW_LIVE_ENABLED")


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


def _realtime_voice_available() -> bool:
    """Realtime voice (P7.5) is available only when the deployment flag is on AND a realtime
    provider key is configured — otherwise the UI falls back to P7 turn-based voice. Reads
    booleans only; never touches or returns the key value."""
    from src.voice.realtime import resolve_realtime_config

    return resolve_realtime_config().available


@router.get("/capabilities", response_model=CapabilitiesResponse,
            summary="Safe feature availability")
def capabilities() -> CapabilitiesResponse:
    # Agentic RAG (Phase 6), long-term memory (Phase 7) and HITL (Phase 8) are all
    # available. The candidate Agent Coach cutover is a deployment flag (Phase 9).
    return CapabilitiesResponse(
        live_interview_enabled=_live_enabled(),
        agentic_rag=True,
        agent_memory=True,
        human_in_the_loop=True,
        agent_coach_enabled=_flag_enabled("AGENT_COACH_ENABLED"),
        realtime_voice_enabled=_realtime_voice_available(),
    )
