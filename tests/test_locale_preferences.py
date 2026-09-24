"""Interface + conversation language preferences (Capstone P3.5).

Independent, bounded, server-persisted, user-scoped, default English, prod fail-closed.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests._auth_factories import build_auth_app, cookies_for, login_token, register

PW = "correcthorsebattery"


def test_defaults_are_english():
    app, _, _ = build_auth_app()
    with TestClient(app) as c:
        register(c, "a@example.com", PW)
        tok = login_token(c, "a@example.com", PW)
        me = c.get("/api/v1/auth/me", cookies=cookies_for(tok)).json()
        assert me["interface_locale"] == "en" and me["conversation_language"] == "en"


def test_interface_and_conversation_are_independent():
    app, _, _ = build_auth_app()
    with TestClient(app) as c:
        register(c, "a@example.com", PW)
        tok = login_token(c, "a@example.com", PW)
        # Set interface only.
        r = c.patch("/api/v1/auth/preferences", json={"interface_locale": "de"}, cookies=cookies_for(tok))
        assert r.status_code == 200 and r.json()["interface_locale"] == "de"
        assert r.json()["conversation_language"] == "en"  # unchanged
        # Set conversation only.
        r = c.patch("/api/v1/auth/preferences", json={"conversation_language": "fr"}, cookies=cookies_for(tok))
        j = r.json()
        assert j["interface_locale"] == "de" and j["conversation_language"] == "fr"
        assert j["response_detail"] == "brief"  # untouched


def test_persists_across_relogin():
    app, _, _ = build_auth_app()
    with TestClient(app) as c:
        register(c, "a@example.com", PW)
        tok = login_token(c, "a@example.com", PW)
        c.patch("/api/v1/auth/preferences", json={"interface_locale": "es", "conversation_language": "it"}, cookies=cookies_for(tok))
        tok2 = login_token(c, "a@example.com", PW)
        me = c.get("/api/v1/auth/me", cookies=cookies_for(tok2)).json()
        assert me["interface_locale"] == "es" and me["conversation_language"] == "it"


def test_cross_user_isolation():
    app, _, _ = build_auth_app()
    with TestClient(app) as c:
        register(c, "a@example.com", PW)
        register(c, "b@example.com", PW)
        a = login_token(c, "a@example.com", PW)
        b = login_token(c, "b@example.com", PW)
        c.patch("/api/v1/auth/preferences", json={"interface_locale": "nl"}, cookies=cookies_for(a))
        assert c.get("/api/v1/auth/me", cookies=cookies_for(b)).json()["interface_locale"] == "en"


def test_unsupported_locale_rejected():
    app, _, _ = build_auth_app()
    with TestClient(app) as c:
        register(c, "a@example.com", PW)
        tok = login_token(c, "a@example.com", PW)
        # Not in the seven-language allow-list → 422; nothing persisted.
        assert c.patch("/api/v1/auth/preferences", json={"interface_locale": "zz"}, cookies=cookies_for(tok)).status_code == 422
        assert c.patch("/api/v1/auth/preferences", json={"conversation_language": "xx"}, cookies=cookies_for(tok)).status_code == 422
        assert c.get("/api/v1/auth/me", cookies=cookies_for(tok)).json()["interface_locale"] == "en"


def test_production_requires_auth():
    app, _, _ = build_auth_app(env="production")
    with TestClient(app) as c:
        assert c.patch("/api/v1/auth/preferences", json={"interface_locale": "de"}).status_code == 401
