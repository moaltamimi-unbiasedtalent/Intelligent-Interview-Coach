"""Reviewer/admin diagnostics authorization (Capstone P6, §30/§36).

The P6 reviewer surface is PLATFORM_ADMIN-gated: a normal candidate cannot read knowledge
governance, retention or Prompt Lab diagnostics; a platform admin can; and no secret or
candidate-private content is exposed.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests._auth_factories import (
    account_repo, build_auth_app, cookies_for, login_token, register,
)

PW = "correcthorsebattery"

_REVIEWER_ROUTES = [
    "/api/v1/reviewer/knowledge/readiness",
    "/api/v1/reviewer/knowledge/manifest",
    "/api/v1/reviewer/knowledge/coverage",
    "/api/v1/reviewer/knowledge/source-health",
    "/api/v1/reviewer/knowledge/language-boundary",
    "/api/v1/reviewer/config-versions",
    "/api/v1/reviewer/retention/inventory",
    "/api/v1/reviewer/prompt-lab/experiments",
]


def test_reviewer_routes_reject_normal_user():
    app, repo, _ = build_auth_app()
    with TestClient(app) as c:
        register(c, "user@example.com", PW)
        token = login_token(c, "user@example.com", PW)
        for path in _REVIEWER_ROUTES:
            assert c.get(path, cookies=cookies_for(token)).status_code == 403, path


def test_reviewer_routes_reject_unauthenticated():
    app, _, _ = build_auth_app(env="production")
    with TestClient(app) as c:
        for path in _REVIEWER_ROUTES:
            assert c.get(path).status_code in (401, 403), path


def test_reviewer_routes_allow_platform_admin_and_are_safe():
    app, repo, _ = build_auth_app()
    with TestClient(app) as c:
        register(c, "admin@example.com", PW)
        token = login_token(c, "admin@example.com", PW)
        uid = c.get("/api/v1/auth/me", cookies=cookies_for(token)).json()["user_id"]
        account_repo(repo).set_platform_role(uid, "platform_admin")
        for path in _REVIEWER_ROUTES:
            r = c.get(path, cookies=cookies_for(token))
            assert r.status_code == 200, f"{path} -> {r.status_code} {r.text}"
            blob = r.text.lower()
            # No secret VALUES / embeddings / prompts / CoT leak. (Descriptive vocabulary
            # like "password-reset tokens" or "audit_security" in the retention inventory is
            # metadata, not a secret — so we check for genuine leak markers only.)
            for bad in ("api_key", "sk-", "bearer ", "embedding vector", "system prompt:",
                        "chain of thought", "openrouter_"):
                assert bad not in blob, f"{path} leaked '{bad}'"


def test_readiness_and_inventory_shapes():
    app, repo, _ = build_auth_app()
    with TestClient(app) as c:
        register(c, "admin2@example.com", PW)
        token = login_token(c, "admin2@example.com", PW)
        uid = c.get("/api/v1/auth/me", cookies=cookies_for(token)).json()["user_id"]
        account_repo(repo).set_platform_role(uid, "platform_admin")
        readiness = c.get("/api/v1/reviewer/knowledge/readiness", cookies=cookies_for(token)).json()
        assert "overall" in readiness and readiness["total_components"] >= 10
        inv = c.get("/api/v1/reviewer/retention/inventory", cookies=cookies_for(token)).json()
        assert len(inv["inventory"]) >= 10
        versions = c.get("/api/v1/reviewer/config-versions", cookies=cookies_for(token)).json()
        assert versions["prompt_version"].startswith("prompt-")
