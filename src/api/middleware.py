"""Request-id middleware.

Every request gets a server-generated UUID (client-provided ids are ignored, so
the id can never carry attacker- or candidate-derived content). It is attached to
``request.state.request_id`` for handlers and safe logging, and returned in the
``X-Request-Id`` response header. This underpins production diagnostics and the
later Agent Inspector.
"""

from __future__ import annotations

import logging
import os
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

logger = logging.getLogger("api")

REQUEST_ID_HEADER = "X-Request-Id"


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = uuid.uuid4().hex
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers[REQUEST_ID_HEADER] = request_id
        return response


# Security headers for hosted operation (Capstone P8, §26). Evidence-based, not copied
# blindly: this is the JSON API, so its own responses need no script/style CSP — a strict
# `default-src 'none'` is safe for the API and never breaks the separately-served frontend,
# OAuth, WebRTC or the browser speech engines (those run in the frontend origin, which sets
# its own CSP). HSTS is emitted only in production (behind real TLS).
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, *, env: str = "development") -> None:
        super().__init__(app)
        self._is_prod = env == "production"

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        h = response.headers
        h.setdefault("X-Content-Type-Options", "nosniff")
        h.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        h.setdefault("X-Frame-Options", "DENY")
        h.setdefault("Permissions-Policy", "camera=(), geolocation=(), interest-cohort=()")
        # The API returns JSON only; lock its own document CSP down entirely and forbid framing.
        h.setdefault("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'")
        if self._is_prod:
            h.setdefault("Strict-Transport-Security", "max-age=63072000; includeSubDomains")
        return response


def security_headers_env() -> str:
    return (os.environ.get("API_ENV", "development") or "development").strip().lower()


_DEV_LIKE_ENVS = {"development", "dev", "local", "test", "testing"}


class CatchAllErrorMiddleware(BaseHTTPMiddleware):
    """Convert any otherwise-unhandled exception into the safe 500 envelope FROM INSIDE the
    CORS/RequestId layers (P10B-W9.1, PF-01/PF-02).

    Starlette's ``ServerErrorMiddleware`` — which turns an unhandled exception into a 500 —
    runs OUTSIDE all user middleware. A 500 produced there bypasses ``CORSMiddleware`` and
    ``RequestIdMiddleware``, so the browser receives a header-less cross-origin response and
    reports a misleading "network"/"couldn't connect" failure for what is actually a server
    bug. Installing this catch-all as the INNERMOST user middleware (so it is wrapped by CORS
    and RequestId) means the safe error response it returns still flows out through those
    layers and carries ``Access-Control-Allow-Origin`` and ``X-Request-Id``.

    The response body is the single safe contract; exception detail, tracebacks, SQL,
    filesystem paths, secrets and provider payloads are never returned (only a generic message
    and the request id). A traceback is logged only in non-production environments.
    """

    def __init__(self, app, *, env: str = "development") -> None:
        super().__init__(app)
        self._is_dev = str(env).strip().lower() in _DEV_LIKE_ENVS

    async def dispatch(self, request: Request, call_next):
        try:
            return await call_next(request)
        except Exception as exc:  # noqa: BLE001 - deliberate catch-all; detail is never leaked
            # Import here to avoid any import cycle at module load; exception_handlers does not
            # import this module.
            from src.api.exception_handlers import safe_internal_error_response

            request_id = getattr(request.state, "request_id", "")
            logger.error(
                "Unhandled API error",
                extra={"request_id": request_id, "error_category": type(exc).__name__},
                exc_info=self._is_dev,
            )
            response = safe_internal_error_response(request_id)
            # Stamp the correlation id on the response too, so it is present even if the
            # request-id middleware is not in the stack for some reason.
            response.headers[REQUEST_ID_HEADER] = request_id
            return response
