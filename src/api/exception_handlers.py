"""Central exception handlers producing the safe error envelope.

Maps application errors to stable HTTP status codes and returns
``{"error": {code, message, request_id}}``. Application errors build on
``SafeError`` (their message is safe to show). Any *unknown* exception becomes a
generic 500 — its detail (repr/traceback/SQL/DB URL/provider key/raw response/
private content) is never returned; only a safe message and the request id.
"""

from __future__ import annotations

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
from src.interview.session_codec import SessionCodecError
from src.session_manager import DuplicateSubmissionError, SessionError

logger = logging.getLogger("api")


def _envelope(status: int, code: str, message: str, request_id: str) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"error": {"code": code, "message": message, "request_id": request_id}},
    )


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

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException):
        # Keep the stable envelope for explicit HTTP errors (e.g. 404 not found).
        code = {404: "not_found", 401: "unauthorized", 403: "forbidden"}.get(
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
                               "details": jsonable_encoder(exc.errors())}},
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
        return _envelope(
            500, "internal_error",
            "An unexpected error occurred. Please try again.", rid,
        )
