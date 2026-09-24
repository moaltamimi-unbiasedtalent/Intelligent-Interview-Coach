"""API-level authentication flows (Capstone P1/E1).

Register → verify → login → me → logout, plus password recovery/reset. Exercised
against a real SQLite DB with in-memory email capture (no provider calls).
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests._auth_factories import (
    SESSION_COOKIE,
    build_auth_app,
    cookies_for,
    login_token,
    register,
    reset_token,
    verification_token,
)

PW = "correcthorsebattery"


def test_register_is_uniform_and_does_not_autologin():
    app, _, mail = build_auth_app()
    with TestClient(app) as c:
        r = register(c, "alice@example.com", PW, "Alice")
        assert r.status_code == 201
        # No session cookie on register (verify then sign in).
        assert SESSION_COOKIE not in r.headers.get("set-cookie", "")
        assert verification_token(mail) is not None


def test_duplicate_registration_is_uniform_and_creates_no_duplicate():
    app, repo, mail = build_auth_app()
    with TestClient(app) as c:
        r1 = register(c, "alice@example.com", PW)
        r2 = register(c, "ALICE@example.com", "different-password-9")
        assert r1.status_code == r2.status_code == 201
        assert r1.json()["message"] == r2.json()["message"]  # uniform (no enumeration)
    # Only ONE user exists for that email.
    from sqlalchemy import func, select
    from src.persistence import User
    with repo.session_factory() as s:
        n = s.scalar(select(func.count()).select_from(User).where(User.email == "alice@example.com"))
        assert n == 1


def test_login_sets_session_and_me_returns_account():
    app, _, _ = build_auth_app()
    with TestClient(app) as c:
        register(c, "bob@example.com", PW)
        token = login_token(c, "bob@example.com", PW)
        assert token
        r = c.get("/api/v1/auth/me", cookies=cookies_for(token))
        assert r.status_code == 200
        body = r.json()
        assert body["email"] == "bob@example.com"
        assert body["tier"] == "basic"
        assert body["platform_role"] == "user"
        assert body["auth_method"] == "session"
        assert body["email_verified"] is False


def test_login_wrong_password_is_generic_401():
    app, _, _ = build_auth_app()
    with TestClient(app) as c:
        register(c, "bob@example.com", PW)
        r = c.post("/api/v1/auth/login", json={"email": "bob@example.com", "password": "nope-nope-nope"})
        assert r.status_code == 401
        assert r.json()["error"]["message"] == "Incorrect email or password."


def test_login_unknown_email_same_generic_401():
    app, _, _ = build_auth_app()
    with TestClient(app) as c:
        r = c.post("/api/v1/auth/login", json={"email": "ghost@example.com", "password": PW})
        assert r.status_code == 401
        assert r.json()["error"]["message"] == "Incorrect email or password."


def test_verify_email_single_use():
    app, _, mail = build_auth_app()
    with TestClient(app) as c:
        register(c, "carol@example.com", PW)
        tok = verification_token(mail)
        r = c.post("/api/v1/auth/verify-email", json={"token": tok})
        assert r.status_code == 200
        # replay → rejected
        r2 = c.post("/api/v1/auth/verify-email", json={"token": tok})
        assert r2.status_code == 400
        # and the account now reports verified
        session = login_token(c, "carol@example.com", PW)
        assert c.get("/api/v1/auth/me", cookies=cookies_for(session)).json()["email_verified"] is True


def test_verify_email_invalid_token_rejected():
    app, _, _ = build_auth_app()
    with TestClient(app) as c:
        r = c.post("/api/v1/auth/verify-email", json={"token": "not-a-real-token"})
        assert r.status_code == 400


def test_forgot_password_is_uniform_for_known_and_unknown():
    app, _, mail = build_auth_app()
    with TestClient(app) as c:
        register(c, "dave@example.com", PW)
        r_known = c.post("/api/v1/auth/forgot-password", json={"email": "dave@example.com"})
        r_unknown = c.post("/api/v1/auth/forgot-password", json={"email": "nobody@example.com"})
        assert r_known.status_code == r_unknown.status_code == 200
        assert r_known.json()["message"] == r_unknown.json()["message"]
        # A reset token was issued for the known account only.
        assert reset_token(mail) is not None


def test_reset_password_flow_and_session_revocation():
    app, _, mail = build_auth_app()
    with TestClient(app) as c:
        register(c, "erin@example.com", PW)
        old_token = login_token(c, "erin@example.com", PW)
        assert c.get("/api/v1/auth/me", cookies=cookies_for(old_token)).status_code == 200

        c.post("/api/v1/auth/forgot-password", json={"email": "erin@example.com"})
        rtok = reset_token(mail)
        r = c.post("/api/v1/auth/reset-password", json={"token": rtok, "password": "brand-new-pw-123"})
        assert r.status_code == 200

        # Old session is revoked (reset invalidates all sessions).
        assert c.get("/api/v1/auth/me", cookies=cookies_for(old_token)).status_code == 401
        # Old password no longer works; new one does.
        assert login_token(c, "erin@example.com", PW) is None
        assert login_token(c, "erin@example.com", "brand-new-pw-123") is not None


def test_reset_password_invalid_token_rejected():
    app, _, _ = build_auth_app()
    with TestClient(app) as c:
        r = c.post("/api/v1/auth/reset-password", json={"token": "bogus", "password": "brand-new-pw-123"})
        assert r.status_code == 400


def test_logout_invalidates_session():
    app, _, _ = build_auth_app()
    with TestClient(app) as c:
        register(c, "frank@example.com", PW)
        token = login_token(c, "frank@example.com", PW)
        assert c.get("/api/v1/auth/me", cookies=cookies_for(token)).status_code == 200
        c.post("/api/v1/auth/logout", cookies=cookies_for(token))
        # Re-presenting the now-revoked token fails.
        assert c.get("/api/v1/auth/me", cookies=cookies_for(token)).status_code == 401


def test_weak_password_rejected():
    app, _, _ = build_auth_app()
    with TestClient(app) as c:
        r = c.post("/api/v1/auth/register", json={"email": "gina@example.com", "password": "short"})
        assert r.status_code == 422


def test_invalid_email_rejected():
    app, _, _ = build_auth_app()
    with TestClient(app) as c:
        r = c.post("/api/v1/auth/register", json={"email": "not-an-email", "password": PW})
        assert r.status_code == 422
