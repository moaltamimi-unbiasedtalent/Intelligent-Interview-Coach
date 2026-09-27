"""P10B Wave 2 — onboarding lifecycle + personalisation preferences (no live calls).

API-level (build_auth_app: real users/repo) for new-user semantics, persistence, bounded-enum
rejection, resume, owner scoping and language/geography independence; plus a migration-level test
proving existing accounts are backfilled to onboarding-completed (never blocked).
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests._auth_factories import build_auth_app, cookies_for, login_token, register

PW = "correcthorsebattery"


def _client():
    app, repo, _ = build_auth_app()
    c = TestClient(app)
    c.__enter__()
    return c, repo


def _me(c, tok):
    return c.get("/api/v1/auth/me", cookies=cookies_for(tok)).json()


# --- new-user semantics ------------------------------------------------------

def test_new_user_starts_with_onboarding_incomplete():
    c, _ = _client()
    try:
        register(c, "a@example.com", PW)
        a = login_token(c, "a@example.com", PW)
        me = _me(c, a)
        assert me["onboarding_completed"] is False
        assert me["onboarding_step"] == 0
        # Sensible defaults present.
        assert me["coaching_style"] == "balanced"
        assert me["career_geography"] == ""
    finally:
        c.__exit__(None, None, None)


# --- persistence + reflection ------------------------------------------------

def test_personalisation_preferences_persist():
    c, _ = _client()
    try:
        register(c, "a@example.com", PW)
        a = login_token(c, "a@example.com", PW)
        r = c.patch("/api/v1/auth/preferences", cookies=cookies_for(a), json={
            "coaching_style": "direct", "career_geography": "de",
            "target_role": "Staff Engineer", "display_name": "Jo",
        })
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["coaching_style"] == "direct"
        assert body["career_geography"] == "de"
        assert body["target_role"] == "Staff Engineer"
        assert body["display_name"] == "Jo"
        # Reflected on a fresh read.
        me = _me(c, a)
        assert me["coaching_style"] == "direct" and me["career_geography"] == "de"
    finally:
        c.__exit__(None, None, None)


def test_invalid_enums_rejected_422():
    c, _ = _client()
    try:
        register(c, "a@example.com", PW)
        a = login_token(c, "a@example.com", PW)
        assert c.patch("/api/v1/auth/preferences", cookies=cookies_for(a),
                       json={"coaching_style": "gimmick"}).status_code == 422
        assert c.patch("/api/v1/auth/preferences", cookies=cookies_for(a),
                       json={"career_geography": "atlantis"}).status_code == 422
    finally:
        c.__exit__(None, None, None)


# --- resume + complete -------------------------------------------------------

def test_onboarding_step_resumes_and_never_regresses():
    c, _ = _client()
    try:
        register(c, "a@example.com", PW)
        a = login_token(c, "a@example.com", PW)
        assert c.post("/api/v1/auth/onboarding", cookies=cookies_for(a), json={"step": 3}).json()["onboarding_step"] == 3
        # A lower step never regresses saved progress.
        assert c.post("/api/v1/auth/onboarding", cookies=cookies_for(a), json={"step": 1}).json()["onboarding_step"] == 3
    finally:
        c.__exit__(None, None, None)


def test_onboarding_complete_flag():
    c, _ = _client()
    try:
        register(c, "a@example.com", PW)
        a = login_token(c, "a@example.com", PW)
        assert _me(c, a)["onboarding_completed"] is False
        r = c.post("/api/v1/auth/onboarding", cookies=cookies_for(a), json={"complete": True})
        assert r.status_code == 200 and r.json()["onboarding_completed"] is True
        assert _me(c, a)["onboarding_completed"] is True
    finally:
        c.__exit__(None, None, None)


# --- separation + owner scoping ----------------------------------------------

def test_language_and_geography_are_independent():
    c, _ = _client()
    try:
        register(c, "a@example.com", PW)
        a = login_token(c, "a@example.com", PW)
        # Setting career geography must not touch conversation/interface language.
        c.patch("/api/v1/auth/preferences", cookies=cookies_for(a), json={"career_geography": "us"})
        me = _me(c, a)
        assert me["career_geography"] == "us"
        assert me["conversation_language"] == "en" and me["interface_locale"] == "en"
        # Setting interface language must not change career geography.
        c.patch("/api/v1/auth/preferences", cookies=cookies_for(a), json={"interface_locale": "de"})
        me = _me(c, a)
        assert me["interface_locale"] == "de" and me["career_geography"] == "us"
    finally:
        c.__exit__(None, None, None)


def test_preferences_are_owner_scoped():
    c, _ = _client()
    try:
        register(c, "a@example.com", PW)
        register(c, "b@example.com", PW)
        a = login_token(c, "a@example.com", PW)
        b = login_token(c, "b@example.com", PW)
        c.patch("/api/v1/auth/preferences", cookies=cookies_for(a), json={"coaching_style": "challenging"})
        # B's account is unaffected by A's change.
        assert _me(c, b)["coaching_style"] == "balanced"
    finally:
        c.__exit__(None, None, None)


# --- existing-user backfill (migration safety) -------------------------------

def test_existing_users_backfilled_to_completed(tmp_path, monkeypatch):
    """A user created BEFORE 0013 must be onboarding-completed after upgrade (never blocked)."""
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine, text

    url = f"sqlite:///{tmp_path/'bf.db'}"
    monkeypatch.setenv("DATABASE_URL", url)  # the migration env resolves the DB from here
    cfg = Config("alembic.ini")
    cfg.set_main_option("script_location", "migrations")
    cfg.set_main_option("sqlalchemy.url", url)

    command.upgrade(cfg, "0012_document_failure_kind")
    eng = create_engine(url)
    with eng.begin() as conn:
        conn.execute(text(
            "INSERT INTO users (subject, provider, platform_role, status, email_verified, created_at, updated_at) "
            "VALUES ('legacy', 'password', 'user', 'active', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
        ))
    command.upgrade(cfg, "0013_onboarding_personalisation")
    with eng.connect() as conn:
        row = conn.execute(text("SELECT onboarding_completed_at FROM users WHERE subject='legacy'")).scalar()
    assert row is not None  # backfilled → existing user is NOT blocked behind onboarding
