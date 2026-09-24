"""Security matrix for the identity/platform foundation (Capstone P1/E1, §15).

Safety invariants that must hold: cross-user isolation = 0 leaks, unauthorized admin
and entitlement access rejected, production fails closed, the dev header is rejected
in production, sessions/tokens cannot be replayed, and the audit log never stores a
secret. Exercised against a real SQLite DB (no provider calls).
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests._auth_factories import (
    account_repo,
    build_auth_app,
    cookies_for,
    login_token,
    register,
)

PW = "correcthorsebattery"


def _account(app, repo, mail, email):
    """Register + login an account; return its session token."""
    with TestClient(app) as c:
        register(c, email, PW)
        return login_token(c, email, PW)


# --- cross-user isolation (0 leaks) ------------------------------------------


def test_cross_user_memory_isolation_via_sessions():
    app, repo, mail = build_auth_app()
    with TestClient(app) as c:
        register(c, "alice@example.com", PW)
        register(c, "bob@example.com", PW)
        alice = login_token(c, "alice@example.com", PW)
        bob = login_token(c, "bob@example.com", PW)

        # Alice saves a preparation memory.
        r = c.post(
            "/api/v1/memory",
            json={"category": "recurring_gap", "summary": "System design fundamentals"},
            cookies=cookies_for(alice),
        )
        assert r.status_code in (200, 201), r.text
        mem_id = r.json()["id"]

        # Bob cannot see Alice's memory in his own list.
        r = c.get("/api/v1/memory", cookies=cookies_for(bob))
        assert all(m["id"] != mem_id for m in r.json().get("items", r.json() if isinstance(r.json(), list) else []))

        # Bob cannot fetch or delete it by id (foreign id → not found).
        assert c.get(f"/api/v1/memory/{mem_id}", cookies=cookies_for(bob)).status_code == 404
        assert c.delete(f"/api/v1/memory/{mem_id}", cookies=cookies_for(bob)).status_code == 404

        # Alice still can.
        assert c.get(f"/api/v1/memory/{mem_id}", cookies=cookies_for(alice)).status_code == 200


def test_two_accounts_have_distinct_user_ids():
    app, repo, mail = build_auth_app()
    with TestClient(app) as c:
        register(c, "alice@example.com", PW)
        register(c, "bob@example.com", PW)
        a = c.get("/api/v1/auth/me", cookies=cookies_for(login_token(c, "alice@example.com", PW))).json()
        b = c.get("/api/v1/auth/me", cookies=cookies_for(login_token(c, "bob@example.com", PW))).json()
        assert a["user_id"] != b["user_id"]


# --- unauthenticated / fail-closed -------------------------------------------


def test_unauthenticated_scoped_route_in_production_is_401():
    app, _, _ = build_auth_app(env="production")
    with TestClient(app) as c:
        assert c.get("/api/v1/memory").status_code == 401
        assert c.get("/api/v1/auth/me").status_code == 401


def test_dev_header_rejected_in_production():
    app, _, _ = build_auth_app(env="production")
    with TestClient(app) as c:
        r = c.get("/api/v1/memory", headers={"X-User-Subject": "attacker"})
        assert r.status_code == 401
        r = c.get("/api/v1/auth/me", headers={"X-User-Subject": "attacker"})
        assert r.status_code == 401


def test_valid_session_cookie_cannot_be_overridden_by_dev_header():
    # In production a valid session wins; a spoofed dev header cannot change identity.
    app, _, _ = build_auth_app(env="production")
    with TestClient(app) as c:
        register(c, "carol@example.com", PW)
        token = login_token(c, "carol@example.com", PW)
        r = c.get(
            "/api/v1/auth/me",
            cookies=cookies_for(token),
            headers={"X-User-Subject": "attacker"},
        )
        assert r.status_code == 200 and r.json()["email"] == "carol@example.com"


# --- platform role enforcement -----------------------------------------------


def test_admin_route_rejects_normal_user():
    app, repo, _ = build_auth_app()
    with TestClient(app) as c:
        register(c, "user@example.com", PW)
        token = login_token(c, "user@example.com", PW)
        assert c.get("/api/v1/auth/admin/audit", cookies=cookies_for(token)).status_code == 403


def test_admin_route_allows_platform_admin():
    app, repo, _ = build_auth_app()
    with TestClient(app) as c:
        register(c, "admin@example.com", PW)
        token = login_token(c, "admin@example.com", PW)
        uid = c.get("/api/v1/auth/me", cookies=cookies_for(token)).json()["user_id"]
        # Bootstrap-equivalent promotion (no self-service endpoint exists).
        account_repo(repo).set_platform_role(uid, "platform_admin")
        r = c.get("/api/v1/auth/admin/audit", cookies=cookies_for(token))
        assert r.status_code == 200
        assert "events" in r.json()


def test_no_self_service_role_escalation_endpoint():
    # There must be no API that lets a user set their own platform role.
    app, _, _ = build_auth_app()
    with TestClient(app) as c:
        register(c, "user@example.com", PW)
        token = login_token(c, "user@example.com", PW)
        # Attempt common escalation shapes — all must fail (no such endpoint / ignored).
        for path, payload in [
            ("/api/v1/auth/me", {"platform_role": "platform_admin"}),
            ("/api/v1/auth/role", {"platform_role": "platform_admin"}),
        ]:
            r = c.post(path, json=payload, cookies=cookies_for(token))
            assert r.status_code in (404, 405, 422)
        # Role is unchanged.
        assert c.get("/api/v1/auth/me", cookies=cookies_for(token)).json()["platform_role"] == "user"


# --- entitlement enforcement -------------------------------------------------


def test_premium_endpoint_rejects_basic_tier():
    app, repo, _ = build_auth_app()
    with TestClient(app) as c:
        register(c, "basic@example.com", PW)
        token = login_token(c, "basic@example.com", PW)
        assert c.get("/api/v1/auth/premium/status", cookies=cookies_for(token)).status_code == 403


def test_premium_endpoint_allows_premium_tier():
    app, repo, _ = build_auth_app()
    with TestClient(app) as c:
        register(c, "premium@example.com", PW)
        token = login_token(c, "premium@example.com", PW)
        uid = c.get("/api/v1/auth/me", cookies=cookies_for(token)).json()["user_id"]
        account_repo(repo).set_tier(uid, "premium", source="test")
        r = c.get("/api/v1/auth/premium/status", cookies=cookies_for(token))
        assert r.status_code == 200 and r.json()["entitled"] is True


def test_entitlement_cannot_be_bypassed_via_request_body():
    # Passing a spoofed tier in the body must not grant premium (server resolves tier).
    app, repo, _ = build_auth_app()
    with TestClient(app) as c:
        register(c, "sneaky@example.com", PW)
        token = login_token(c, "sneaky@example.com", PW)
        r = c.get(
            "/api/v1/auth/premium/status",
            params={"tier": "premium"},
            cookies=cookies_for(token),
        )
        assert r.status_code == 403


# --- session / token replay ---------------------------------------------------


def test_session_replay_after_logout_denied():
    app, _, _ = build_auth_app()
    with TestClient(app) as c:
        register(c, "z@example.com", PW)
        token = login_token(c, "z@example.com", PW)
        c.post("/api/v1/auth/logout", cookies=cookies_for(token))
        assert c.get("/api/v1/auth/me", cookies=cookies_for(token)).status_code == 401


def test_forged_session_token_denied():
    app, _, _ = build_auth_app()
    with TestClient(app) as c:
        # A bogus cookie is present-but-invalid → 401 (never a silent grant/fallthrough).
        r = c.get("/api/v1/auth/me", cookies=cookies_for("totally-made-up-token"))
        assert r.status_code == 401


# --- audit safety -------------------------------------------------------------


def test_audit_log_contains_no_secrets():
    app, repo, mail = build_auth_app()
    with TestClient(app) as c:
        register(c, "audited@example.com", PW)
        login_token(c, "audited@example.com", PW)
        c.post("/api/v1/auth/login", json={"email": "audited@example.com", "password": "wrong-pw-value"})
        c.post("/api/v1/auth/forgot-password", json={"email": "audited@example.com"})

    from sqlalchemy import select
    from src.persistence import AuditEvent
    with repo.session_factory() as s:
        rows = s.scalars(select(AuditEvent)).all()
        assert rows, "audit events were recorded"
        for r in rows:
            blob = f"{r.event_type}{r.result}{r.target_type}{r.target_id}{r.context}".lower()
            assert PW not in blob
            assert "wrong-pw-value" not in blob
            assert "password_hash" not in blob
            assert "$2b$" not in blob  # no bcrypt hash
            assert "token=" not in blob  # no raw token / link
        # Events we expect to exist.
        kinds = {r.event_type for r in rows}
        assert "account.register" in kinds
        assert "account.login" in kinds


def test_audit_records_login_success_and_failure():
    app, repo, _ = build_auth_app()
    with TestClient(app) as c:
        register(c, "m@example.com", PW)
        login_token(c, "m@example.com", PW)
        c.post("/api/v1/auth/login", json={"email": "m@example.com", "password": "bad-password-1"})
    from sqlalchemy import select
    from src.persistence import AuditEvent
    with repo.session_factory() as s:
        results = {(r.event_type, r.result) for r in s.scalars(select(AuditEvent)).all()}
        assert ("account.login", "success") in results
        assert ("account.login", "failure") in results
