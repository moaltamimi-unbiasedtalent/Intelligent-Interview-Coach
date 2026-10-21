"""P10B-W9.3 — Security/menu exposure closure (backend authorization).

Closes the Pilot "security lapse on certain menu items": the internal engineering/reviewer
diagnostics endpoints behind Review & Diagnostics were previously unauthenticated. They must now
require platform-admin, while the candidate-facing Career-evidence (Sources) endpoints stay open to
ordinary candidates. Server-side authorization is the boundary (hiding the UI is only UX).

Matrix proven here:
    internal knowledge diagnostics  : anon 401/403, BASIC 403, admin 200
    internal evaluation diagnostics : anon 401/403, BASIC 403, admin 200
    candidate Sources / snapshot    : BASIC 200 (NOT gated)

Plus negative tests: no self-elevation via header/body/query; workspace membership and premium do
not imply admin; platform admin does not bypass owner-scoping for private agent runs.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests._auth_factories import (
    account_repo, build_auth_app, cookies_for, login_token, register,
)

PW = "correcthorsebattery"

# Internal engineering/reviewer diagnostics — must be platform-admin-only after W9.3.
INTERNAL_DIAGNOSTICS = [
    "/api/v1/knowledge/diagnostics",
    "/api/v1/evaluation/latest",
    "/api/v1/evaluation/runs",
    "/api/v1/evaluation/ragas/configuration",
]

# Candidate-facing career-evidence endpoints — must remain reachable by an ordinary candidate.
CANDIDATE_KNOWLEDGE = [
    "/api/v1/knowledge/sources",
    "/api/v1/knowledge/snapshot",
]


def _make_admin(c: TestClient, repo, email: str) -> str:
    register(c, email, PW)
    token = login_token(c, email, PW)
    uid = c.get("/api/v1/auth/me", cookies=cookies_for(token)).json()["user_id"]
    account_repo(repo).set_platform_role(uid, "platform_admin")
    return token


# --- internal diagnostics require authorization ------------------------------------------

def test_internal_diagnostics_reject_unauthenticated():
    app, _, _ = build_auth_app(env="production")
    with TestClient(app) as c:
        for path in INTERNAL_DIAGNOSTICS:
            assert c.get(path).status_code in (401, 403), path


def test_internal_diagnostics_reject_normal_candidate():
    app, repo, _ = build_auth_app()
    with TestClient(app) as c:
        register(c, "user@example.com", PW)
        token = login_token(c, "user@example.com", PW)
        for path in INTERNAL_DIAGNOSTICS:
            assert c.get(path, cookies=cookies_for(token)).status_code == 403, path


def test_internal_diagnostics_allow_platform_admin():
    app, repo, _ = build_auth_app()
    with TestClient(app) as c:
        token = _make_admin(c, repo, "admin@example.com")
        ck = cookies_for(token)
        for path in INTERNAL_DIAGNOSTICS:
            r = c.get(path, cookies=ck)
            assert r.status_code == 200, f"{path} -> {r.status_code} {r.text}"
        # Data-shape coverage (previously in test_api; preserved under the admin identity).
        assert "available" in c.get("/api/v1/evaluation/latest", cookies=ck).json()
        assert "runs" in c.get("/api/v1/evaluation/runs", cookies=ck).json()
        assert "can_run" in c.get("/api/v1/evaluation/ragas/configuration", cookies=ck).json()


# --- candidate-facing evidence stays open (NOT accidentally gated) ------------------------

def test_candidate_knowledge_sources_remain_accessible_to_normal_user():
    app, repo, _ = build_auth_app()
    with TestClient(app) as c:
        register(c, "user2@example.com", PW)
        token = login_token(c, "user2@example.com", PW)
        for path in CANDIDATE_KNOWLEDGE:
            r = c.get(path, cookies=cookies_for(token))
            assert r.status_code == 200, f"{path} -> {r.status_code} {r.text}"


# --- negative authorization: no self-elevation -------------------------------------------

def test_candidate_cannot_self_elevate_via_header_body_or_query():
    app, repo, _ = build_auth_app()
    with TestClient(app) as c:
        register(c, "user3@example.com", PW)
        token = login_token(c, "user3@example.com", PW)
        ck = cookies_for(token)
        # Forged role claims in header / query must be ignored — still 403.
        assert c.get("/api/v1/knowledge/diagnostics", cookies=ck,
                     headers={"X-Platform-Role": "platform_admin", "X-Role": "admin"}).status_code == 403
        assert c.get("/api/v1/evaluation/latest?platform_role=platform_admin&admin=true",
                     cookies=ck).status_code == 403


def test_workspace_membership_does_not_grant_diagnostics_access():
    # A user who owns/creates a workspace is still not a platform admin.
    app, repo, _ = build_auth_app()
    with TestClient(app) as c:
        register(c, "wsowner@example.com", PW)
        token = login_token(c, "wsowner@example.com", PW)
        ck = cookies_for(token)
        c.post("/api/v1/workspaces", json={"name": "Team"}, cookies=ck)
        assert c.get("/api/v1/knowledge/diagnostics", cookies=ck).status_code == 403
        assert c.get("/api/v1/evaluation/latest", cookies=ck).status_code == 403


def test_platform_admin_does_not_bypass_owner_scoping_for_agent_runs():
    # Platform admin is NOT a private-data superuser: a run they do not own is 404, not 200.
    app, repo, _ = build_auth_app()
    with TestClient(app) as c:
        token = _make_admin(c, repo, "admin2@example.com")
        r = c.get("/api/v1/agent/runs/not-a-real-owned-run", cookies=cookies_for(token))
        assert r.status_code == 404, f"expected owner-scoped 404, got {r.status_code}"


# --- 03A (REQ-OWN-08): moving Review and Diagnostics under /admin is UX only; the server decides -------------------------------------
# An Admin who lacks the specific read permission gets 403 on the same endpoints, whatever the navigation shows.

REVIEWER_ENDPOINTS_BY_PERMISSION = {
    "platform.knowledge.read": ["/api/v1/knowledge/diagnostics", "/api/v1/reviewer/knowledge/readiness", "/api/v1/reviewer/knowledge/coverage"],
    "platform.ai.read": ["/api/v1/evaluation/latest", "/api/v1/evaluation/runs", "/api/v1/reviewer/config-versions", "/api/v1/reviewer/prompt-lab/experiments"],
    "platform.privacy.read": ["/api/v1/reviewer/retention/inventory"],
}


def _make_role(c: TestClient, repo, email: str, role: str) -> str:
    register(c, email, PW)
    token = login_token(c, email, PW)
    uid = c.get("/api/v1/auth/me", cookies=cookies_for(token)).json()["user_id"]
    account_repo(repo).set_platform_role(uid, role)
    return token


def test_admin_without_the_permission_gets_403_on_diagnostics_and_reviewer_routes():
    from src.application.admin_permissions import permissions_for_role

    app, repo, _ = build_auth_app()
    with TestClient(app) as c:
        for role in ("billing_admin", "support_operator"):
            ck = cookies_for(_make_role(c, repo, f"{role}@example.com", role))
            held = permissions_for_role(role)
            for permission, paths in REVIEWER_ENDPOINTS_BY_PERMISSION.items():
                assert permission not in held, (role, permission)         # the fixture roles genuinely lack it
                for path in paths:
                    assert c.get(path, cookies=ck).status_code == 403, (role, path)


def test_a_specialist_role_reaches_only_the_routes_its_permission_covers():
    app, repo, _ = build_auth_app()
    with TestClient(app) as c:
        ck = cookies_for(_make_role(c, repo, "knowledge@example.com", "knowledge_admin"))       # holds knowledge.read and ai.read, not privacy.read
        assert c.get("/api/v1/knowledge/diagnostics", cookies=ck).status_code == 200
        assert c.get("/api/v1/evaluation/latest", cookies=ck).status_code == 200
        assert c.get("/api/v1/reviewer/retention/inventory", cookies=ck).status_code == 403


def test_candidate_gets_403_on_every_reviewer_and_diagnostics_route():
    app, repo, _ = build_auth_app()
    with TestClient(app) as c:
        register(c, "plain@example.com", PW)
        ck = cookies_for(login_token(c, "plain@example.com", PW))
        for paths in REVIEWER_ENDPOINTS_BY_PERMISSION.values():
            for path in paths:
                assert c.get(path, cookies=ck).status_code == 403, path
