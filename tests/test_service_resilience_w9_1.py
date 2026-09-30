"""P10B-W9.1 — Service resilience & truthful error handling (backend).

Regression tests that would have FAILED before this wave:

* An otherwise-unhandled 500 raised inside the real middleware stack must still carry
  ``Access-Control-Allow-Origin`` (for the allowed frontend origin) and ``X-Request-Id`` — so
  the browser receives the response and classifies it as a server error, not a misleading
  "couldn't connect" network failure (PF-01/PF-02).
* The safe 500 envelope must never leak exception text / SQL / filesystem paths.
* A disallowed origin is never reflected/authorised.
* Staging/production fail closed when the required CORS allow-list is missing.
* Expected HTTP errors (404/422) keep their status and the safe envelope — they never become
  a generic 500.

These tests are HERMETIC: they set the model-override env vars aside so they do not depend on a
developer's local ``.env`` (W9.1 §M), and they use a controlled in-test route rather than a
production debug route to trigger the unhandled exception (W9.1 §I).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.api.config import ApiSettings
from src.api.main import create_app

ALLOWED_ORIGIN = "http://localhost:3000"
# A deliberately "sensitive-looking" exception message; none of it may reach the client.
SECRET_MARKERS = ("boom-secret", "RuntimeError", "SELECT *", "/etc/passwd", "Traceback")


@pytest.fixture
def app_with_boom():
    """A real app (full middleware stack) plus one in-test route that raises. No production
    debug route is added; the throwaway route exists only on this per-test app instance."""
    app = create_app(ApiSettings(env="test", frontend_origins=(ALLOWED_ORIGIN,)))

    @app.get("/api/v1/_w9_1_boom")
    async def _boom():  # pragma: no cover - body is exercised via the client
        raise RuntimeError("boom-secret SELECT * FROM users; path=/etc/passwd")

    return app


def _client(app):
    # raise_server_exceptions=False so we observe the ACTUAL 500 response the browser would get.
    return TestClient(app, raise_server_exceptions=False)


def test_unhandled_500_carries_cors_and_request_id_for_allowed_origin(app_with_boom):
    with _client(app_with_boom) as c:
        r = c.get("/api/v1/_w9_1_boom", headers={"Origin": ALLOWED_ORIGIN})
    assert r.status_code == 500
    # The core PF-01 guarantee: the error response is delivered WITH CORS + correlation id.
    assert r.headers.get("access-control-allow-origin") == ALLOWED_ORIGIN
    assert r.headers.get("x-request-id")
    body = r.json()
    assert body["error"]["code"] == "internal_error"
    assert body["error"]["request_id"] == r.headers.get("x-request-id")
    # Safe: no exception detail / SQL / path / traceback leaks.
    for marker in SECRET_MARKERS:
        assert marker not in r.text


def test_unhandled_500_does_not_reflect_disallowed_origin(app_with_boom):
    with _client(app_with_boom) as c:
        r = c.get("/api/v1/_w9_1_boom", headers={"Origin": "http://evil.example"})
    assert r.status_code == 500
    assert r.headers.get("access-control-allow-origin") != "http://evil.example"
    # Still safe + correlated even when the origin is not allowed.
    assert r.headers.get("x-request-id")
    assert "boom-secret" not in r.text


def test_normal_response_has_request_id_and_cors(app_with_boom):
    with _client(app_with_boom) as c:
        r = c.get("/api/v1/health", headers={"Origin": ALLOWED_ORIGIN})
    assert r.status_code == 200
    assert r.headers.get("x-request-id")
    assert r.headers.get("access-control-allow-origin") == ALLOWED_ORIGIN


def test_expected_404_stays_404_with_envelope_and_headers(app_with_boom):
    with _client(app_with_boom) as c:
        r = c.get("/api/v1/this-route-does-not-exist", headers={"Origin": ALLOWED_ORIGIN})
    assert r.status_code == 404  # NOT converted to a 500
    assert r.headers.get("x-request-id")
    assert r.headers.get("access-control-allow-origin") == ALLOWED_ORIGIN
    assert r.json()["error"]["code"] == "not_found"


def test_validation_error_stays_422_not_500(app_with_boom):
    # A missing required field is rejected by request validation BEFORE any service runs.
    with _client(app_with_boom) as c:
        r = c.post("/api/v1/career/chat", json={}, headers={"Origin": ALLOWED_ORIGIN})
    assert r.status_code == 422  # NOT a generic 500
    assert r.headers.get("x-request-id")
    assert r.json()["error"]["code"] in ("invalid_request", "validation_error")


def test_staging_fails_closed_without_frontend_origins(monkeypatch):
    monkeypatch.setenv("API_ENV", "staging")
    for var in ("FRONTEND_ORIGINS", "DATABASE_URL", "APP_BASE_URL"):
        monkeypatch.delenv(var, raising=False)
    with pytest.raises(RuntimeError):
        create_app(ApiSettings(env="staging", frontend_origins=()))


def test_production_still_fails_closed_without_frontend_origins(monkeypatch):
    monkeypatch.setenv("API_ENV", "production")
    for var in ("FRONTEND_ORIGINS", "DATABASE_URL", "APP_BASE_URL"):
        monkeypatch.delenv(var, raising=False)
    with pytest.raises(RuntimeError):
        create_app(ApiSettings(env="production", frontend_origins=()))
