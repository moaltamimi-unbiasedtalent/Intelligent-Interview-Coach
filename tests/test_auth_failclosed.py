"""Sprint 4 Phase 11 — production fail-closed identity boundary.

The transitional X-User-Subject boundary must NOT silently share one anonymous
identity across callers in production. Development keeps the convenience fallback.
This is not an auth provider — production still requires a real gateway/OIDC.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from src.api import dependencies as deps
from src.api.config import ApiSettings
from src.api.main import create_app


def _client(env: str) -> TestClient:
    app = create_app(ApiSettings(env=env, frontend_origins=("http://localhost:3000",)))
    # A capabilities/health call needs no external services; identity is resolved for
    # scoped routes. Use an interview route which requires get_current_user_id.
    return TestClient(app)


def test_production_rejects_missing_identity():
    with _client("production") as c:
        # No X-User-Subject → fail closed (401), never anonymous data sharing.
        r = c.get("/api/v1/interviews", headers={})
        assert r.status_code == 401
        assert r.json()["error"]["code"] == "unauthorized"


def test_production_rejects_dev_header():
    # Capstone P1/E1: the transitional X-User-Subject header is DEV-ONLY. In production
    # it must NOT be honoured as identity — only a trusted session cookie is accepted.
    from tests._interview_factories import make_durable_store
    with _client("production") as c:
        c.app.dependency_overrides[deps.get_session_store] = lambda: make_durable_store()
        from tests.test_api import _FakeRepo
        c.app.dependency_overrides[deps.get_repository] = lambda: _FakeRepo()
        r = c.get("/api/v1/interviews", headers={"X-User-Subject": "attacker"})
        assert r.status_code == 401
        assert r.json()["error"]["code"] == "unauthorized"


def test_development_allows_anonymous_fallback():
    from tests._interview_factories import make_durable_store
    with _client("development") as c:
        c.app.dependency_overrides[deps.get_session_store] = lambda: make_durable_store()
        from tests.test_api import _FakeRepo
        c.app.dependency_overrides[deps.get_repository] = lambda: _FakeRepo()
        r = c.get("/api/v1/interviews", headers={})  # anonymous dev identity
        assert r.status_code == 200
