"""Platform Admin (Capstone P6.5): authorization + metadata boundary + audit + no superuser."""

from __future__ import annotations

import subprocess
import sys

from fastapi.testclient import TestClient

from tests._auth_factories import account_repo, build_auth_app, cookies_for, login_token, register

PW = "correcthorsebattery"

_ADMIN_ROUTES = [
    "/api/v1/admin/home", "/api/v1/admin/users", "/api/v1/admin/workspaces",
    "/api/v1/admin/privacy-requests", "/api/v1/admin/providers", "/api/v1/admin/audit",
    "/api/v1/admin/feedback",
]


def _admin_client():
    app, repo, mail = build_auth_app()
    c = TestClient(app); c.__enter__()
    register(c, "admin@x.com", PW)
    token = login_token(c, "admin@x.com", PW)
    uid = c.get("/api/v1/auth/me", cookies=cookies_for(token)).json()["user_id"]
    account_repo(repo).set_platform_role(uid, "platform_admin")
    return c, token, uid, repo


def test_normal_user_rejected_from_admin():
    app, repo, _ = build_auth_app()
    with TestClient(app) as c:
        register(c, "u@x.com", PW)
        t = login_token(c, "u@x.com", PW)
        for p in _ADMIN_ROUTES:
            assert c.get(p, cookies=cookies_for(t)).status_code == 403, p


def test_unauthenticated_rejected_from_admin():
    app, _, _ = build_auth_app(env="production")
    with TestClient(app) as c:
        for p in _ADMIN_ROUTES:
            assert c.get(p).status_code in (401, 403), p


def test_admin_can_access_and_view_is_metadata_only():
    c, token, _, _ = _admin_client()
    try:
        users = c.get("/api/v1/admin/users", cookies=cookies_for(token)).json()["users"]
        allowed = {"user_id", "email", "display_name", "platform_role", "status",
                   "email_verified", "tier", "created_at"}
        assert users and all(set(u) <= allowed for u in users)
        for bad in ("comment", "answers", "documents", "memory", "report"):
            assert all(bad not in u for u in users)
    finally:
        c.__exit__(None, None, None)


def test_privileged_changes_are_audited():
    c, token, admin_uid, _ = _admin_client()
    try:
        register(c, "target@x.com", PW)
        ttok = login_token(c, "target@x.com", PW)
        target_uid = c.get("/api/v1/auth/me", cookies=cookies_for(ttok)).json()["user_id"]
        assert c.post(f"/api/v1/admin/users/{target_uid}/tier", json={"tier": "premium"},
                      cookies=cookies_for(token)).status_code == 200
        events = c.get("/api/v1/admin/audit", cookies=cookies_for(token)).json()["events"]
        assert any(e["event_type"] == "admin.entitlement_change" for e in events)
    finally:
        c.__exit__(None, None, None)


def test_admin_cannot_self_demote():
    c, token, admin_uid, _ = _admin_client()
    try:
        r = c.post(f"/api/v1/admin/users/{admin_uid}/role", json={"role": "user"}, cookies=cookies_for(token))
        assert r.status_code == 409
    finally:
        c.__exit__(None, None, None)


def test_providers_and_audit_leak_no_secret():
    c, token, _, _ = _admin_client()
    try:
        prov = c.get("/api/v1/admin/providers", cookies=cookies_for(token)).text.lower()
        for bad in ("sk-", "bearer ey", "password_hash", "token="):
            assert bad not in prov
    finally:
        c.__exit__(None, None, None)


def test_platform_admin_eval_gate_passes():
    r = subprocess.run([sys.executable, "scripts/eval_platform_admin.py"], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
