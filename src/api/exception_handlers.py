"""Central exception handlers producing the safe error envelope.

Maps application errors to stable HTTP status codes and returns
``{"error": {code, message, request_id}}``. Application errors build on
``SafeError`` (their message is safe to show). Any *unknown* exception becomes a
generic 500 — its detail (repr/traceback/SQL/DB URL/provider key/raw response/
private content) is never returned; only a safe message and the request id.
"""

from __future__ import annotations

import json

import logging

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from src.application.errors import (
    ConfigurationError,
    ConflictError,
    MissingHandoffConfigError,
    PersistenceError,
    UnavailableServiceError,
    ValidationError,
)
from src.ai_protection import AiUsageLimitError
from src.application.usage_quota import QuotaExhausted, QuotaNotConfigured, QuotaUnavailable
from src.application.preparation_pack import PackGenerationUnavailable
from src.application.history_access import HistoryNotAvailableError
from src.application.model_profile_access import ModelProfileInvalid, ModelProfileNotAuthorized, ModelProfileNotAvailable
from src.repository import HistoryRestricted
from src.application.pause import PauseStateUnavailable, PlatformPausedError
from src.interview.session_codec import SessionCodecError
from src.platform_config.flags import FeatureFlagStateUnavailable
from src.admin_security.errors import StepUpFailed, StepUpRequired, StepUpUnavailable
from src.session_manager import DuplicateSubmissionError, SessionError

logger = logging.getLogger("api")


def _envelope(status: int, code: str, message: str, request_id: str) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"error": {"code": code, "message": message, "request_id": request_id}},
    )


PLATFORM_PAUSED_MESSAGE = "Ask4Mo is temporarily unavailable for this activity. Your saved data remains available. Please try again later."
AI_USAGE_LIMIT_MESSAGE = ("You have reached a temporary safety limit on AI-generated work. Your saved work and history remain available. "
                          "Please try again in a little while.")
PACK_GENERATION_UNAVAILABLE_MESSAGE = ("Preparation Pack generation is not available for your account right now. Packs you already saved remain available to read and download.")
USAGE_QUOTA_MESSAGE = ("You have used the AI allowance included for this period. Your saved work and history remain available. "
                       "The allowance resets at the time shown.")
USAGE_QUOTA_UNAVAILABLE_MESSAGE = ("This AI feature is temporarily unavailable. Your saved work and history remain available. "
                                   "Please try again in a little while.")
HISTORY_NOT_AVAILABLE_MESSAGE = ("This interview is outside the history included in your current view. It has not been deleted and remains stored. "
                                 "You can still export or delete your data from your account.")
MODEL_PROFILE_MESSAGE = "That AI model profile is not available for your account. Please choose another profile."
PLATFORM_STATE_UNAVAILABLE_MESSAGE = "Ask4Mo cannot confirm that this activity is available right now. Please try again shortly."

# The single safe message for an otherwise-unhandled server error. Never carries exception
# detail, SQL, filesystem paths, secrets, provider payloads or private candidate data.
INTERNAL_ERROR_MESSAGE = "An unexpected error occurred. Please try again."


def safe_internal_error_response(request_id: str) -> JSONResponse:
    """The one canonical safe 500 envelope, shared by the catch-all middleware and the
    registered ``Exception`` handler so every catastrophic path returns an identical,
    leak-free contract (``{"error": {code, message, request_id}}``)."""
    return _envelope(500, "internal_error", INTERNAL_ERROR_MESSAGE, request_id)


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "")


def register_exception_handlers(app: FastAPI) -> None:
    # A practice-handoff context missing industry/career level is a SPECIFIC 422 with
    # a stable code, so the Coach UI asks for exactly those two fields — never inferred
    # from status alone. Registered as its own handler; Starlette matches the most
    # specific class in the exception's MRO, so this wins over the generic below.
    @app.exception_handler(MissingHandoffConfigError)
    async def _missing_handoff_config(request: Request, exc: MissingHandoffConfigError):
        return _envelope(
            422, "missing_interview_handoff_config", str(exc), _request_id(request))

    @app.exception_handler(ValidationError)
    async def _validation(request: Request, exc: ValidationError):
        return _envelope(422, "validation_error", str(exc), _request_id(request))

    @app.exception_handler(ConfigurationError)
    async def _configuration(request: Request, exc: ConfigurationError):
        return _envelope(503, "not_configured", str(exc), _request_id(request))

    @app.exception_handler(UnavailableServiceError)
    async def _unavailable(request: Request, exc: UnavailableServiceError):
        return _envelope(503, "service_unavailable", str(exc), _request_id(request))

    @app.exception_handler(PersistenceError)
    async def _persistence(request: Request, exc: PersistenceError):
        return _envelope(503, "persistence_error", str(exc), _request_id(request))

    @app.exception_handler(ConflictError)
    async def _conflict(request: Request, exc: ConflictError):
        return _envelope(409, "conflict", str(exc), _request_id(request))

    # Interview state-machine errors (safe messages). A duplicate submission is a
    # conflict (409, recoverable by re-reading state); other invalid transitions are
    # a 422. Registered from most specific to least — DuplicateSubmissionError first.
    @app.exception_handler(DuplicateSubmissionError)
    async def _duplicate(request: Request, exc: DuplicateSubmissionError):
        return _envelope(409, "duplicate_submission", str(exc), _request_id(request))

    @app.exception_handler(SessionError)
    async def _session_error(request: Request, exc: SessionError):
        return _envelope(422, "invalid_transition", str(exc), _request_id(request))

    @app.exception_handler(SessionCodecError)
    async def _session_codec(request: Request, exc: SessionCodecError):
        # Stored interview state could not be decoded (corrupt/unsupported). Fail
        # safely with a generic message — never expose the payload or the raw cause.
        return _envelope(
            503, "session_unreadable",
            "This interview session could not be read. Please start a new interview.",
            _request_id(request))

    # Durable operator pause (P10B-W10.11). Stable machine-readable codes with FIXED safe copy: no reason, actor, capability detail or internal state.
    @app.exception_handler(PlatformPausedError)
    async def _platform_paused(request: Request, exc: PlatformPausedError):
        return _envelope(503, "platform_paused", PLATFORM_PAUSED_MESSAGE, _request_id(request))

    # W12.4D-P2-A: a per-user safety ceiling on AI-generated work (enforcement mode only). Fixed safe copy plus bounded machine-readable facts: the affected
    # capability, that the limit is temporary and when to retry. No plan, price or upgrade wording: no paid tier is commercially active.
    @app.exception_handler(AiUsageLimitError)
    async def _ai_usage_limit(request: Request, exc: AiUsageLimitError):
        response = _envelope(429, "ai_usage_limit", AI_USAGE_LIMIT_MESSAGE, _request_id(request))
        body = json.loads(response.body)
        body["error"].update({"capability": exc.workflow, "temporary": True, "retry_after_seconds": exc.retry_after})
        return JSONResponse(status_code=429, content=body, headers={"Retry-After": str(exc.retry_after)})

    # W12.4D-P5-A: Pack GENERATION is unavailable (rollout gate off or not entitled). Fixed safe copy; the bounded reason is machine-readable; no plan, price or
    # upgrade wording. Saved Packs are never affected.
    @app.exception_handler(PackGenerationUnavailable)
    async def _pack_generation_unavailable(request: Request, exc: PackGenerationUnavailable):
        response = _envelope(403, "preparation_pack_generation_unavailable", PACK_GENERATION_UNAVAILABLE_MESSAGE, _request_id(request))
        body = json.loads(response.body)
        body["error"]["reason"] = exc.reason
        return JSONResponse(status_code=403, content=body)

    # W12.4D-P4-A: product usage quota (enforcement mode only). Fixed safe copy plus bounded facts; no plan, price or upgrade wording. A missing policy or an
    # unreadable store fails closed for the quota-gated operation only (503), never as unlimited use.
    @app.exception_handler(QuotaExhausted)
    async def _usage_quota_exhausted(request: Request, exc: QuotaExhausted):
        response = _envelope(429, "usage_quota_exhausted", USAGE_QUOTA_MESSAGE, _request_id(request))
        body = json.loads(response.body)
        body["error"].update({"feature": exc.feature, "period": exc.period, "reset_at": exc.reset_at.isoformat(), "retry_after_seconds": exc.retry_after})
        return JSONResponse(status_code=429, content=body, headers={"Retry-After": str(exc.retry_after)})

    @app.exception_handler(QuotaNotConfigured)
    @app.exception_handler(QuotaUnavailable)
    async def _usage_quota_unavailable(request: Request, exc: Exception):
        return _envelope(503, "usage_quota_unavailable", USAGE_QUOTA_UNAVAILABLE_MESSAGE, _request_id(request))

    # W12.4D-P2-B: the caller OWNS the interview but it lies outside the history window of their entitlement. Fixed safe copy; nothing about the interview.
    @app.exception_handler(HistoryRestricted)
    @app.exception_handler(HistoryNotAvailableError)
    async def _history_not_available(request: Request, exc: Exception):
        return _envelope(403, "history_not_available", HISTORY_NOT_AVAILABLE_MESSAGE, _request_id(request))

    # W12.4D-P2-C: model-profile authorization. Fixed safe copy: no plan, price or upgrade wording, and the refused profile is not echoed.
    @app.exception_handler(ModelProfileNotAuthorized)
    async def _model_profile_not_authorized(request: Request, exc: ModelProfileNotAuthorized):
        return _envelope(403, "model_profile_not_authorized", MODEL_PROFILE_MESSAGE, _request_id(request))

    @app.exception_handler(ModelProfileNotAvailable)
    async def _model_profile_not_available(request: Request, exc: ModelProfileNotAvailable):
        return _envelope(422, "model_profile_not_available", MODEL_PROFILE_MESSAGE, _request_id(request))

    @app.exception_handler(ModelProfileInvalid)
    async def _model_profile_invalid(request: Request, exc: ModelProfileInvalid):
        return _envelope(422, "invalid_model_profile", "Unknown model profile.", _request_id(request))

    @app.exception_handler(FeatureFlagStateUnavailable)
    async def _flag_state_unavailable(request: Request, exc: FeatureFlagStateUnavailable):
        return _envelope(503, "platform_state_unavailable", PLATFORM_STATE_UNAVAILABLE_MESSAGE, _request_id(request))

    @app.exception_handler(PauseStateUnavailable)
    async def _platform_state_unavailable(request: Request, exc: PauseStateUnavailable):
        return _envelope(503, "platform_state_unavailable", PLATFORM_STATE_UNAVAILABLE_MESSAGE, _request_id(request))

    # Step-up (P10B-W10.13): fixed codes and safe copy. Never reveals whether an account has a password credential beyond "unavailable".
    @app.exception_handler(StepUpRequired)
    async def _step_up_required(request: Request, exc: StepUpRequired):
        return _envelope(403, "step_up_required", str(exc), _request_id(request))

    @app.exception_handler(StepUpUnavailable)
    async def _step_up_unavailable(request: Request, exc: StepUpUnavailable):
        return _envelope(403, "step_up_unavailable", str(exc), _request_id(request))

    @app.exception_handler(StepUpFailed)
    async def _step_up_failed(request: Request, exc: StepUpFailed):
        return _envelope(403, "step_up_failed", str(exc), _request_id(request))

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException):
        # Keep the stable envelope for explicit HTTP errors (e.g. 404 not found).
        code = getattr(exc, "error_code", None) or {404: "not_found", 401: "unauthorized", 403: "forbidden"}.get(
            exc.status_code, "http_error")
        message = exc.detail if isinstance(exc.detail, str) else "Request failed."
        return _envelope(exc.status_code, code, message, _request_id(request))

    @app.exception_handler(RequestValidationError)
    async def _request_validation(request: Request, exc: RequestValidationError):
        # FastAPI body/schema validation — return the safe, structured detail.
        rid = _request_id(request)
        return JSONResponse(
            status_code=422,
            content={"error": {"code": "invalid_request",
                               "message": "Request validation failed.",
                               "request_id": rid,
                               "details": [{k: v for k, v in e.items() if k not in ("input", "ctx", "url")}
                                           for e in jsonable_encoder(exc.errors())]}},
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception):
        rid = _request_id(request)
        # SAFE BY DEFAULT: log only the request id + exception CLASS NAME. A raw
        # traceback (exc_info) can capture private request data held in stack frames
        # (JD/background/answers, DB params, credentials), so it is emitted ONLY in an
        # explicitly non-production environment for local debugging. The client always
        # receives a generic message.
        env = getattr(getattr(request.app.state, "settings", None), "env", "production")
        dev = str(env).lower() in ("development", "dev", "test")
        logger.error(
            "Unhandled API error",
            extra={"request_id": rid, "error_category": type(exc).__name__},
            exc_info=dev,
        )
        # NOTE (P10B-W9.1): in normal operation CatchAllErrorMiddleware (installed INSIDE the
        # CORS layer) converts unhandled exceptions to this same envelope so the response
        # still carries CORS + X-Request-Id. This handler remains as the last-resort safety
        # net (Starlette's ServerErrorMiddleware) and returns the identical safe contract.
        return safe_internal_error_response(rid)
