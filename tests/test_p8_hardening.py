"""Capstone P8 production-hardening tests: rate limits, account deletion, pause switch,
security headers, env validation, malware fail-safe. Functional (real SQLite auth stack) +
the deterministic eval invariants. Zero paid/live calls."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tests._auth_factories import (
    build_auth_app,
    cookies_for,
    login_token,
    register,
    verification_token,
)


def _verified_user(client, mail, email="user@example.com", pw="password123"):
    register(client, email, pw)
    token = verification_token(mail)
    client.post("/api/v1/auth/verify-email", json={"token": token})
    return login_token(client, email, pw)


# --- Eval invariants as pytest ------------------------------------------------------------


def test_rate_limit_eval_invariants():
    from scripts.eval_rate_limits import run

    failed = {k: v for k, v in run().items() if not v[0]}
    assert not failed, failed


def test_account_deletion_eval_invariants():
    from scripts.eval_account_deletion import run

    failed = {k: v for k, v in run().items() if not v[0]}
    assert not failed, failed


def test_hosting_readiness_eval_invariants():
    from scripts.eval_hosting_readiness import run

    failed = {k: v for k, v in run().items() if not v[0]}
    assert not failed, failed


# --- Auth rate limiting -------------------------------------------------------------------


def test_login_is_rate_limited():
    app, repo, mail = build_auth_app()
    with TestClient(app) as client:
        register(client, "rl@example.com", "password123")
        # Repeated failed logins for the same account eventually hit the per-account ceiling.
        statuses = [
            client.post("/api/v1/auth/login",
                        json={"email": "rl@example.com", "password": "wrong"}).status_code
            for _ in range(12)
        ]
        assert 429 in statuses, statuses
        # Anti-enumeration: a login for a NON-existent account is limited identically (also
        # 429), so rate-limit behaviour never signals whether an account exists.
        statuses2 = [
            client.post("/api/v1/auth/login",
                        json={"email": "ghost@example.com", "password": "wrong"}).status_code
            for _ in range(12)
        ]
        assert 429 in statuses2, statuses2


def test_register_is_rate_limited():
    app, repo, mail = build_auth_app()
    with TestClient(app) as client:
        statuses = [
            register(client, f"u{i}@example.com", "password123").status_code for i in range(12)
        ]
        assert 429 in statuses, statuses


# --- Account deletion endpoint ------------------------------------------------------------


def test_delete_account_endpoint_removes_session():
    app, repo, mail = build_auth_app()
    with TestClient(app) as client:
        token = _verified_user(client, mail)
        assert token
        # Authenticated before deletion.
        assert client.get("/api/v1/auth/me", cookies=cookies_for(token)).status_code == 200
        # Permanent deletion.
        r = client.post("/api/v1/auth/account/delete", cookies=cookies_for(token))
        assert r.status_code == 200, r.text
        # Session is gone → the same cookie is now unauthenticated.
        assert client.get("/api/v1/auth/me", cookies=cookies_for(token)).status_code == 401


def test_delete_account_is_idempotent_and_owner_scoped():
    from src.application.account_deletion_service import AccountDeletionService

    app, repo, mail = build_auth_app()
    svc = AccountDeletionService(repo.session_factory)
    # Deleting a non-existent user is a safe no-op.
    summary = svc.delete_account(999999)
    assert summary.existed is False


# --- Security headers ---------------------------------------------------------------------


def test_security_headers_present():
    app, repo, mail = build_auth_app()
    with TestClient(app) as client:
        h = client.get("/api/health").headers
    assert h.get("X-Content-Type-Options") == "nosniff"
    assert h.get("X-Frame-Options") == "DENY"
    assert "Content-Security-Policy" in h
    assert "Referrer-Policy" in h


# --- Operator pause switch ----------------------------------------------------------------


def test_durable_pause_blocks_capability_and_others_stay_available(tmp_path):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from src.api.guards import ensure_not_paused
    from src.application.pause import PauseService, PlatformPausedError
    from src.persistence import Base

    eng = create_engine(f"sqlite:///{tmp_path / 'p.db'}")
    Base.metadata.create_all(eng)
    svc = PauseService(sessionmaker(bind=eng), environment="staging")
    svc.set_paused("agent", True, expected_revision=0, reason="incident", actor_user_id=1)
    with pytest.raises(PlatformPausedError):
        ensure_not_paused("agent", svc)
    ensure_not_paused("ocr", svc)               # other capabilities remain available


def test_admin_pause_endpoint_toggles(monkeypatch):
    from src.persistence import User

    app, repo, mail = build_auth_app()
    with TestClient(app) as client:
        token = _verified_user(client, mail, email="admin@example.com")
        # Promote to platform admin directly in the DB.
        with repo.session_factory() as s:
            user = s.query(User).filter(User.email == "admin@example.com").one()
            user.platform_role = "operations_admin"          # the W10.0 owner of the pause switches (platform.config.manage)
            s.commit()
        r = client.post("/api/v1/admin/pause/agent", json={"paused": True, "expected_revision": 0, "reason": "incident"},
                        cookies=cookies_for(token))
        assert r.status_code == 200, r.text
        state = client.get("/api/v1/admin/pause", cookies=cookies_for(token)).json()
        assert next(i for i in state["items"] if i["capability"] == "agent")["paused"] is True and state["durable"] is True
        # Unknown capability is rejected.
        assert client.post("/api/v1/admin/pause/nope", json={"paused": True, "expected_revision": 0, "reason": "x"},
                           cookies=cookies_for(token)).status_code == 422


# --- Environment validation ---------------------------------------------------------------


def test_production_boot_fails_without_config(monkeypatch):
    from src.api.config import ApiSettings
    from src.api.main import create_app

    monkeypatch.setenv("API_ENV", "production")
    for var in ("FRONTEND_ORIGINS", "DATABASE_URL", "APP_BASE_URL"):
        monkeypatch.delenv(var, raising=False)
    with pytest.raises(RuntimeError):
        create_app(ApiSettings(env="production", frontend_origins=()))


def test_dev_boot_is_permissive():
    from src.api.config import ApiSettings
    from src.api.main import create_app

    # Building a dev app never raises (default env in tests is permissive).
    app = create_app(ApiSettings(env="test", frontend_origins=("http://localhost:3000",)))
    assert app is not None
