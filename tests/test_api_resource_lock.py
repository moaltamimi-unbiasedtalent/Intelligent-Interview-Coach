"""Regression: the app-lifetime resource lock must be REENTRANT.

`_shared()` holds ``app.state.resources_lock`` while it calls a resource factory,
and some factories build another shared resource on the same thread (e.g.
``get_agent_service``'s factory calls ``get_app_config`` → ``_shared`` again). With a
plain ``threading.Lock`` this self-deadlocks: every first ``POST /agent/run`` on a
fresh process hangs forever. The lock is a ``threading.RLock`` so nested same-thread
resolution is allowed while cross-thread mutual exclusion is preserved.

These tests run each scenario in a worker thread with a timeout so a regression
FAILS the suite quickly instead of hanging it.
"""

from __future__ import annotations

import threading

from fastapi.testclient import TestClient

from src.api import dependencies as deps
from src.api.main import create_app


class _Req:
    """Minimal stand-in exposing the ``request.app.state`` that ``_shared`` reads."""

    def __init__(self, app):
        self.app = app


def _run_with_timeout(fn, timeout=5.0):
    box: dict = {}

    def worker():
        box["result"] = fn()

    t = threading.Thread(target=worker, daemon=True)
    t.start()
    t.join(timeout)
    assert not t.is_alive(), "resource lock deadlocked (is it a plain Lock, not RLock?)"
    return box["result"]


def test_nested_shared_does_not_deadlock():
    app = create_app()
    with TestClient(app):  # lifespan sets up resources + the reentrant lock
        req = _Req(app)

        def outer():
            # A factory that itself resolves ANOTHER shared resource — the exact
            # pattern get_agent_service uses (its factory calls get_app_config).
            def inner_factory():
                return deps._shared(req, "inner", lambda: "inner-value")

            return deps._shared(req, "outer", inner_factory)

        assert _run_with_timeout(outer) == "inner-value"
        assert app.state.resources["inner"] == "inner-value"
        assert app.state.resources["outer"] == "inner-value"


def test_resources_lock_is_reentrant():
    app = create_app()
    with TestClient(app):
        lock = app.state.resources_lock
        # An RLock can be acquired twice by the same thread; a plain Lock cannot.
        assert lock.acquire(blocking=False)
        try:
            assert lock.acquire(blocking=False), "resources_lock must be reentrant (RLock)"
            lock.release()
        finally:
            lock.release()
