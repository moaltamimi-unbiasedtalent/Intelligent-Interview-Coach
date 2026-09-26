"""Realtime voice routes (Capstone P7.5, C1).

A thin, authenticated, bounded HTTP boundary that mints a short-lived realtime voice session
credential for the browser. The endpoint:

- requires an authenticated user (session cookie / dev header) — sessions are user-scoped;
- reports unavailable (503) when realtime is off/unconfigured, so the UI falls back to P7;
- rate-limits + concurrency-bounds session creation per user (abuse + cost, §25/§26);
- resolves provider/model/voice SERVER-SIDE (never a client slug — §27/§28);
- returns ONLY the provider's ephemeral client secret (never the long-lived key — §5);
- logs safe metadata only (no audio, no transcript, no secret — §29).

No audio or transcript ever passes through this route: the browser streams audio directly to
the provider over WebRTC. Durable Practice state stays with the interview application service.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException

from src.api.dependencies import get_current_principal
from src.api.guards import ensure_not_paused
from src.api.rate_limit import enforce, user_key
from src.api.schemas.voice import (
    RealtimeSessionCreateRequest,
    RealtimeSessionResponse,
    RealtimeStatusResponse,
)
from src.observability.sanitizer import error_category, safe_metadata
from src.voice.realtime import (
    SUPPORTED_REALTIME_LOCALES,
    RateLimitExceeded,
    RealtimeConfig,
    RealtimeProvider,
    RealtimeSessionLimiter,
    RealtimeSessionRequest,
    RealtimeUnavailableError,
    build_realtime_provider,
    resolve_realtime_config,
)

router = APIRouter(prefix="/voice", tags=["voice"])
_log = logging.getLogger("ask4mo.voice.realtime")

# Single-process, in-memory limiter (LOCAL-ONLY; production needs a shared store — §26).
_LIMITER = RealtimeSessionLimiter()


def get_realtime_config() -> RealtimeConfig:
    return resolve_realtime_config()


def get_realtime_provider(
    config: RealtimeConfig = Depends(get_realtime_config),
) -> RealtimeProvider | None:
    """The realtime provider, or None when realtime is off/unconfigured (→ fallback)."""
    return build_realtime_provider(config)


def get_realtime_limiter() -> RealtimeSessionLimiter:
    return _LIMITER


@router.get("/realtime/status", response_model=RealtimeStatusResponse,
            summary="Realtime voice availability (no secrets)")
def realtime_status(
    config: RealtimeConfig = Depends(get_realtime_config),
    principal=Depends(get_current_principal),
) -> RealtimeStatusResponse:
    """Authenticated availability check. Booleans/labels only; drives the Start-live-voice
    entry point. When ``available`` is false the UI stays on P7 turn-based voice."""
    return RealtimeStatusResponse(
        enabled=config.enabled,
        configured=config.configured,
        available=config.available,
        provider=config.provider,
        supported_locales=list(SUPPORTED_REALTIME_LOCALES),
        max_session_seconds=config.max_session_seconds,
        max_concurrent_per_user=config.max_concurrent_per_user,
        fallback="turn_based_voice",
    )


@router.post("/realtime/session", response_model=RealtimeSessionResponse,
             summary="Mint a short-lived realtime voice session (user-scoped)")
def create_realtime_session(
    body: RealtimeSessionCreateRequest,
    principal=Depends(get_current_principal),
    provider: RealtimeProvider | None = Depends(get_realtime_provider),
    limiter: RealtimeSessionLimiter = Depends(get_realtime_limiter),
    config: RealtimeConfig = Depends(get_realtime_config),
) -> RealtimeSessionResponse:
    user_id = principal.user_id

    # 0) Operator pause + per-user cost ceiling (§19/§21), on top of the concurrency limiter.
    ensure_not_paused("realtime_voice")
    enforce("cost_realtime_user", user_key(user_id))

    # 1) Availability → 503 so the client falls back to turn-based voice (never a dead-end).
    if provider is None or not config.available:
        _emit(user_id, body, outcome="unavailable")
        raise HTTPException(
            status_code=503,
            detail="Realtime voice is not available right now. Turn-based voice is ready.",
        )

    # 2) Rate + concurrency bound (abuse + cost).
    try:
        limiter.check_and_reserve(user_id)
    except RateLimitExceeded as exc:
        _emit(user_id, body, outcome="rate_limited")
        raise HTTPException(status_code=429, detail=str(exc)) from exc

    # 3) Mint the ephemeral session. Any provider failure → release the reservation, 503,
    #    fall back. The long-lived key never appears in the response or the log.
    try:
        req = RealtimeSessionRequest(
            user_id=user_id,
            locale=body.locale,
            surface=body.surface,
            interview_session_id=body.interview_session_id,
        )
        grant = provider.mint_session(req)
    except RealtimeUnavailableError as exc:
        limiter.release(user_id)
        _emit(user_id, body, outcome="unavailable", error=exc)
        raise HTTPException(
            status_code=503,
            detail="Realtime voice could not start. Turn-based voice is ready.",
        ) from exc
    except Exception as exc:  # noqa: BLE001 - never surface provider internals
        limiter.release(user_id)
        _emit(user_id, body, outcome="error", error=exc)
        raise HTTPException(
            status_code=503,
            detail="Realtime voice could not start. Turn-based voice is ready.",
        ) from exc

    _emit(user_id, body, outcome="created", grant_provider=grant.provider,
          grant_locale=grant.locale)
    return RealtimeSessionResponse(**grant.public_dict())


@router.post("/realtime/session/end", summary="Release a realtime session reservation")
def end_realtime_session(
    principal=Depends(get_current_principal),
    limiter: RealtimeSessionLimiter = Depends(get_realtime_limiter),
) -> dict:
    """Best-effort release of the caller's active-session reservation (idempotent). Ownership
    is implicit: a user can only release their OWN counter — never another account's."""
    limiter.release(principal.user_id)
    _log.info("realtime.session.end %s", safe_metadata({"user_scoped": True}))
    return {"status": "ended"}


def _emit(user_id: int, body: RealtimeSessionCreateRequest, *, outcome: str,
          error: BaseException | None = None, **extra) -> None:
    """Emit SAFE observability metadata only — no audio, no transcript, no secret, no key.

    We log an opaque user-scoped marker and the coarse locale/surface, never the raw user id
    as content, never the client secret, never any conversation text.
    """
    meta = {
        "outcome": outcome,
        "surface": body.surface,
        "locale": (body.locale or "en").split("-")[0][:2],
        "user_scoped": True,
        "error_category": error_category(error) if error is not None else None,
    }
    meta.update(extra)
    _log.info("realtime.session %s", safe_metadata(meta))
