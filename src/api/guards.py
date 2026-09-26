"""Route guards for hosted operation (Capstone P8): per-user cost limits + operator pause.

Dependency factories that costly provider-backed routes attach to enforce, server-side:
- a per-user rate ceiling on the operation plus a global ceiling (§19), and
- the operator pause switch (§21) — a paused capability returns a truthful 503 rather than
  silently doing nothing or pretending to run.

These are additive to any operation-specific control already present (e.g. the realtime
session concurrency limiter, the interview operation lease). Frontend disabling is never the
only control (§19).
"""

from __future__ import annotations

from typing import Any, Callable

from fastapi import Depends, HTTPException

from src.api.dependencies import get_current_user_id
from src.api.rate_limit import enforce, user_key
from src.application.pause import get_pause_registry

__all__ = ["cost_limit", "require_not_paused", "ensure_not_paused"]


def cost_limit(bucket: str) -> Callable[..., Any]:
    """Build a dependency that applies a per-user cost bucket + the global cost ceiling.

    Keys off the authenticated user id only (not the full Principal), so it adds no account-
    repository dependency to a route."""

    def _dep(user_id: int = Depends(get_current_user_id)):
        enforce(bucket, user_key(user_id))
        enforce("cost_global", "all")
        return user_id

    return _dep


def ensure_not_paused(capability: str) -> None:
    """Raise 503 if an operator has paused this capability (truthful, not silent)."""
    if get_pause_registry().is_paused(capability):
        raise HTTPException(
            status_code=503,
            detail="This feature is temporarily paused by the operator. Please try again later.",
        )


def require_not_paused(capability: str) -> Callable[..., Any]:
    """Build a dependency that rejects requests while ``capability`` is paused."""

    def _dep():
        ensure_not_paused(capability)

    return _dep
