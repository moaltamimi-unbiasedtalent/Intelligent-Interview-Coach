"""Request-id middleware.

Every request gets a server-generated UUID (client-provided ids are ignored, so
the id can never carry attacker- or candidate-derived content). It is attached to
``request.state.request_id`` for handlers and safe logging, and returned in the
``X-Request-Id`` response header. This underpins production diagnostics and the
later Agent Inspector.
"""

from __future__ import annotations

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
