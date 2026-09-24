"""Deterministic tests for bounded Google OIDC social login (Capstone P1/E1, §5).

Uses a FAKE provider injected via dependency override — no live Google call. Live
Google validation is classified UNVALIDATED. These tests cover the security-critical
logic: CSRF state validation, redirect allowlisting, account creation/linking and
safe failure.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.api import dependencies as deps
from src.application.oidc import OidcError, OidcIdentity, is_safe_redirect
from tests._auth_factories import SESSION_COOKIE, account_repo, build_auth_app, register


class _FakeGoogle:
    def __init__(self, identity=None, fail=False):
        self._identity = identity or OidcIdentity(
            provider="google", subject="g-sub-1", email="new@example.com",
            email_verified=True, display_name="New User",
        )
        self._fail = fail

    def authorization_url(self, *, state: str, redirect_uri: str) -> str:
        return f"https://accounts.google.com/o/oauth2/v2/auth?state={state}"

    def exchange(self, *, code: str, redirect_uri: str) -> OidcIdentity:
        if self._fail:
            raise OidcError("Google sign-in failed.")
        return self._identity


def _app_with_provider(provider):
    app, repo, mail = build_auth_app()
    app.dependency_overrides[deps.get_oidc_provider] = lambda: provider
    return app, repo, mail


# --- redirect allowlist (unit) -----------------------------------------------


@pytest.mark.parametrize("target,ok", [
    ("/prepare", True),
    ("/", True),
    ("//evil.com", False),
    ("http://evil.com", False),
    ("https://evil.com", False),
    ("/\\evil", False),
    ("javascript:alert(1)", False),
    ("", False),
    (None, False),
])
def test_is_safe_redirect(target, ok):
    assert is_safe_redirect(target) is ok


# --- start / callback flow ---------------------------------------------------


def test_start_returns_authorization_url_and_sets_state():
    app, _, _ = _app_with_provider(_FakeGoogle())
    with TestClient(app) as c:
        r = c.get("/api/v1/auth/oidc/google/start", params={"next": "/prepare"})
        assert r.status_code == 200
        assert "authorization_url" in r.json()
        assert "ask4mo_oidc_state" in r.headers.get("set-cookie", "")


def test_start_disabled_when_no_provider():
    app, _, _ = build_auth_app()  # no override → provider None (flag off)
    with TestClient(app) as c:
        assert c.get("/api/v1/auth/oidc/google/start").status_code == 404


def test_callback_creates_account_and_session():
    app, repo, _ = _app_with_provider(_FakeGoogle())
    with TestClient(app) as c:
        c.get("/api/v1/auth/oidc/google/start")  # sets state cookie
        state = c.cookies.get("ask4mo_oidc_state")
        r = c.get("/api/v1/auth/oidc/google/callback",
                  params={"code": "abc", "state": state}, follow_redirects=False)
        assert r.status_code == 303
        assert SESSION_COOKIE in r.headers.get("set-cookie", "")
    # The account now exists with a google identity.
    acct = account_repo(repo).find_by_email("new@example.com")
    assert acct is not None and "google" in acct.providers


def test_callback_rejects_state_mismatch_csrf():
    app, _, _ = _app_with_provider(_FakeGoogle())
    with TestClient(app) as c:
        c.get("/api/v1/auth/oidc/google/start")
        r = c.get("/api/v1/auth/oidc/google/callback",
                  params={"code": "abc", "state": "attacker-supplied"}, follow_redirects=False)
        assert r.status_code == 400


def test_callback_without_state_cookie_rejected():
    app, _, _ = _app_with_provider(_FakeGoogle())
    with TestClient(app) as c:
        # No /start first → no state cookie.
        r = c.get("/api/v1/auth/oidc/google/callback",
                  params={"code": "abc", "state": "x"}, follow_redirects=False)
        assert r.status_code == 400


def test_callback_provider_failure_is_safe():
    app, _, _ = _app_with_provider(_FakeGoogle(fail=True))
    with TestClient(app) as c:
        c.get("/api/v1/auth/oidc/google/start")
        state = c.cookies.get("ask4mo_oidc_state")
        r = c.get("/api/v1/auth/oidc/google/callback",
                  params={"code": "abc", "state": state}, follow_redirects=False)
        assert r.status_code == 400
        assert "failed" in r.json()["error"]["message"].lower()


def test_callback_links_to_existing_password_account_on_verified_email():
    identity = OidcIdentity(provider="google", subject="g-sub-2",
                            email="dual@example.com", email_verified=True, display_name=None)
    app, repo, _ = _app_with_provider(_FakeGoogle(identity=identity))
    with TestClient(app) as c:
        register(c, "dual@example.com", "correcthorsebattery")
        c.get("/api/v1/auth/oidc/google/start")
        state = c.cookies.get("ask4mo_oidc_state")
        c.get("/api/v1/auth/oidc/google/callback",
              params={"code": "abc", "state": state}, follow_redirects=False)
    acct = account_repo(repo).find_by_email("dual@example.com")
    assert "google" in acct.providers and "password" in acct.providers


def test_callback_sanitizes_unsafe_next_redirect():
    app, _, _ = _app_with_provider(_FakeGoogle())
    with TestClient(app) as c:
        c.get("/api/v1/auth/oidc/google/start", params={"next": "//evil.com"})
        state = c.cookies.get("ask4mo_oidc_state")
        r = c.get("/api/v1/auth/oidc/google/callback",
                  params={"code": "abc", "state": state}, follow_redirects=False)
        assert r.status_code == 303
        # Redirects to a safe local path, never the external host.
        assert r.headers["location"] == "/"
