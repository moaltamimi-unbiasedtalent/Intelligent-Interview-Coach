"""Shared pytest fixtures (Capstone P8).

Resets process-global runtime state between tests so hosted-operation controls added in P8
(the shared rate limiter and the operator pause registry) never leak counters/toggles across
tests. Kept deliberately small — no app wiring lives here (factories own that).
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _reset_runtime_state():
    # Fresh rate-limit counters per test (the in-memory limiter is a process singleton).
    from src.api.rate_limit import reset_rate_limiter

    reset_rate_limiter()
    # Fresh pause registry per test (no capability paused by default).
    try:
        from src.application.pause import reset_pause_registry

        reset_pause_registry()
    except Exception:  # noqa: BLE001 - pause module may not be imported in a given test set
        pass
    yield
