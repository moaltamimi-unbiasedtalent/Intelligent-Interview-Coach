"""Request-id middleware.

Every request gets a server-generated UUID (client-provided ids are ignored, so
the id can never carry attacker- or candidate-derived content). It is attached to
``request.state.request_id`` for handlers and safe logging, and returned in the
``X-Request-Id`` response header. This underpins production diagnostics and the
later Agent Inspector.
"""

from __future__ import annotations

import os
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

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
