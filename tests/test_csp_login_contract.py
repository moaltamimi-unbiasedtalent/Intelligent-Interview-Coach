"""Disposable authentication contract evidence for the CSP diagnostic."""

import pytest
from fastapi.testclient import TestClient

from tests._auth_factories import build_auth_app, register


@pytest.mark.parametrize("body", [{"email": "person@example.invalid"}, {"email": 42, "password": "synthetic-only"}])
def test_invalid_login_request_returns_schema_envelope(body):
    app, _, _ = build_auth_app()
    with TestClient(app) as client:
        response = client.post("/api/v1/auth/login", json=body)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_request"
    assert isinstance(response.json()["error"]["details"], list)


def test_login_application_email_validation_has_distinct_envelope():
    app, _, _ = build_auth_app()
    with TestClient(app) as client:
        response = client.post("/api/v1/auth/login", json={"email": "bad", "password": "synthetic-only"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert response.json()["error"]["message"] == "Enter a valid email address."


def test_valid_synthetic_login_still_succeeds():
    app, _, _ = build_auth_app()
    with TestClient(app) as client:
        assert register(client, "csp-contract@example.invalid", "synthetic-only-password").status_code == 201
        response = client.post("/api/v1/auth/login", json={"email": "csp-contract@example.invalid", "password": "synthetic-only-password"})
        assert response.status_code == 200
