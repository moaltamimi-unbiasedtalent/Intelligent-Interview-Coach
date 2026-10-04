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


@router.get("/ready", summary="Readiness (DB + config; no provider calls)")
def ready(request: Request) -> dict:
    """Real readiness probe (§32): checks DB connectivity and critical config WITHOUT any
    expensive provider call. Returns 503 when not ready so a load balancer holds traffic."""
    from fastapi import HTTPException
    from sqlalchemy import text

    checks: dict[str, bool] = {}

    # 1) Database connectivity (cheap SELECT 1).
    try:
        from src.api.dependencies import get_repository

        repo = get_repository(request)
        with repo.session_factory() as s:
            s.execute(text("SELECT 1"))
        checks["database"] = True
    except Exception:  # noqa: BLE001 - readiness never leaks the error detail
        checks["database"] = False

    # 2) Critical config (production fails fast at boot, but report here too).
    try:
        report = getattr(request.app.state, "env_report", None)
        checks["config"] = bool(report.ok) if report is not None else True
    except Exception:  # noqa: BLE001
        checks["config"] = True

    ready_ok = all(checks.values())
    body = {
        "status": "ready" if ready_ok else "not_ready",
        "service": "intelligent-interview-coach",
        "version": request.app.state.settings.version,
        "checks": checks,
    }
    if not ready_ok:
        raise HTTPException(status_code=503, detail=body)
    return body


def _repo_or_none(request: Request):
    """The repository through the app's dependency graph (so test/app overrides apply). None when it cannot be built (reported as unavailable)."""
    from src.api.dependencies import get_repository

    try:
        override = request.app.dependency_overrides.get(get_repository)
        return override() if override is not None else get_repository(request)
    except Exception:  # noqa: BLE001
        return None


def _paused_or_unreadable(capability: str, repo) -> bool:
    """Durable pause check for availability projections. An unreadable authoritative store counts as NOT available (fail closed)."""
    from src.application.pause import PauseService

    try:
        return PauseService(repo.session_factory).is_paused(capability)   # repo None -> AttributeError -> fail closed
    except Exception:  # noqa: BLE001
        return True


def _realtime_voice_available(repo) -> bool:
    """Realtime voice (P7.5) is available only when the deployment flag is on AND a realtime
    provider key is configured AND an operator has not paused it — otherwise the UI falls back
    to P7 turn-based voice. Reads booleans only; never touches or returns the key value."""
    from src.voice.realtime import resolve_realtime_config

    return resolve_realtime_config().available and not _paused_or_unreadable("realtime_voice", repo)


def _company_research_available(repo) -> bool:
    """Company Intelligence (P10B Wave 5) is available when external research is enabled (the durable W10.11 flag over the existing
    environment baseline, default on) and not operator-paused. Reads booleans only; never implies a provider key is present."""
    from src.platform_config.flags import FeatureFlagService

    try:   # request-scoped durable read (shared by every process). Control-plane state that cannot be read is UNKNOWN: report the capability unavailable.
        flag_on = FeatureFlagService(repo.session_factory).effective("external_research")
    except Exception:  # noqa: BLE001 - includes repo None (AttributeError) and FeatureFlagStateUnavailable
        return False
    return flag_on and not _paused_or_unreadable("current_market", repo)


@router.get("/capabilities", response_model=CapabilitiesResponse,
            summary="Safe feature availability")
def capabilities(request: Request) -> CapabilitiesResponse:
    repo = _repo_or_none(request)
    # Agentic RAG (Phase 6), long-term memory (Phase 7) and HITL (Phase 8) are all
    # available. The candidate Agent Coach cutover is a deployment flag (Phase 9).
    return CapabilitiesResponse(
        live_interview_enabled=_live_enabled(),
        agentic_rag=True,
        agent_memory=True,
        human_in_the_loop=True,
        agent_coach_enabled=_flag_enabled("AGENT_COACH_ENABLED"),
        realtime_voice_enabled=_realtime_voice_available(repo),
        company_research_enabled=_company_research_available(repo),
    )
