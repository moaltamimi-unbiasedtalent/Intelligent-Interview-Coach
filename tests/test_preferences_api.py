"""Response-detail preference API (Capstone P2/E2).

Server-side, user-scoped, default brief, editable, persists, not entitlement-gated,
production fail-closed. Also present in the agent response as the presentation contract.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests._auth_factories import build_auth_app, cookies_for, login_token, register

PW = "correcthorsebattery"


def test_default_is_brief():
    app, _, _ = build_auth_app()
    with TestClient(app) as c:
        register(c, "a@example.com", PW)
        tok = login_token(c, "a@example.com", PW)
        assert c.get("/api/v1/auth/me", cookies=cookies_for(tok)).json()["response_detail"] == "brief"


def test_update_and_persist():
    app, _, _ = build_auth_app()
    with TestClient(app) as c:
        register(c, "a@example.com", PW)
        tok = login_token(c, "a@example.com", PW)
        r = c.patch("/api/v1/auth/preferences", json={"response_detail": "detailed"}, cookies=cookies_for(tok))
        assert r.status_code == 200 and r.json()["response_detail"] == "detailed"
        # Persists on a fresh /me (survives a re-fetch / re-login).
        assert c.get("/api/v1/auth/me", cookies=cookies_for(tok)).json()["response_detail"] == "detailed"
        tok2 = login_token(c, "a@example.com", PW)
        assert c.get("/api/v1/auth/me", cookies=cookies_for(tok2)).json()["response_detail"] == "detailed"


def test_preference_is_user_scoped():
    app, _, _ = build_auth_app()
    with TestClient(app) as c:
        register(c, "a@example.com", PW)
        register(c, "b@example.com", PW)
        a = login_token(c, "a@example.com", PW)
        b = login_token(c, "b@example.com", PW)
        c.patch("/api/v1/auth/preferences", json={"response_detail": "detailed"}, cookies=cookies_for(a))
        assert c.get("/api/v1/auth/me", cookies=cookies_for(b)).json()["response_detail"] == "brief"


def test_invalid_value_rejected():
    app, _, _ = build_auth_app()
    with TestClient(app) as c:
        register(c, "a@example.com", PW)
        tok = login_token(c, "a@example.com", PW)
        assert c.patch("/api/v1/auth/preferences", json={"response_detail": "verbose"}, cookies=cookies_for(tok)).status_code == 422


def test_production_requires_auth():
    app, _, _ = build_auth_app(env="production")
    with TestClient(app) as c:
        assert c.patch("/api/v1/auth/preferences", json={"response_detail": "detailed"}).status_code == 401


def test_preference_change_is_audited_without_secrets():
    app, repo, _ = build_auth_app()
    with TestClient(app) as c:
        register(c, "a@example.com", PW)
        tok = login_token(c, "a@example.com", PW)
        c.patch("/api/v1/auth/preferences", json={"response_detail": "detailed"}, cookies=cookies_for(tok))
    from sqlalchemy import select
    from src.persistence import AuditEvent
    with repo.session_factory() as s:
        rows = [r for r in s.scalars(select(AuditEvent)).all() if r.event_type == "account.preferences_change"]
        assert rows and rows[0].result == "success"
        blob = f"{rows[0].context}".lower()
        assert PW not in blob and "$2b$" not in blob
