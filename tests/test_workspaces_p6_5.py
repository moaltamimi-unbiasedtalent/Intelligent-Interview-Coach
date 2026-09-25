"""Workspaces + sharing (Capstone P6.5): membership, invitations, sharing, isolation.

HTTP-level tests over the real app (owner-scoped, private-by-default) + the deterministic
security eval gate.
"""

from __future__ import annotations

import subprocess
import sys

from fastapi.testclient import TestClient

from tests._auth_factories import build_auth_app, cookies_for, login_token, register

PW = "correcthorsebattery"


def _uid(c, token):
    return c.get("/api/v1/auth/me", cookies=cookies_for(token)).json()["user_id"]


def _invite_token(mail):
    return mail.sent[-1].body.split("token=")[1].split()[0]


def test_create_invite_accept_flow():
    app, repo, mail = build_auth_app()
    with TestClient(app) as c:
        register(c, "a@x.com", PW); register(c, "b@x.com", PW)
        a = login_token(c, "a@x.com", PW); b = login_token(c, "b@x.com", PW)
        wid = c.post("/api/v1/workspaces", json={"name": "Alpha"}, cookies=cookies_for(a)).json()["id"]
        assert c.post(f"/api/v1/workspaces/{wid}/invite", json={"email": "b@x.com"},
                      cookies=cookies_for(a)).status_code == 200
        tok = _invite_token(mail)
        r = c.post("/api/v1/workspaces/invitations/accept", json={"token": tok}, cookies=cookies_for(b))
        assert r.status_code == 200 and r.json()["member_count"] == 2
        # single-use replay fails
        assert c.post("/api/v1/workspaces/invitations/accept", json={"token": tok},
                      cookies=cookies_for(b)).status_code == 409


def test_private_by_default_and_nonmember_cannot_view():
    app, repo, mail = build_auth_app()
    with TestClient(app) as c:
        register(c, "a@x.com", PW); register(c, "m@x.com", PW)
        a = login_token(c, "a@x.com", PW); m = login_token(c, "m@x.com", PW)
        wid = c.post("/api/v1/workspaces", json={"name": "Alpha"}, cookies=cookies_for(a)).json()["id"]
        # non-member gets 404 (existence not probeable)
        assert c.get(f"/api/v1/workspaces/{wid}", cookies=cookies_for(m)).status_code == 404


def test_member_cannot_invite_or_remove():
    app, repo, mail = build_auth_app()
    with TestClient(app) as c:
        register(c, "a@x.com", PW); register(c, "b@x.com", PW)
        a = login_token(c, "a@x.com", PW); b = login_token(c, "b@x.com", PW)
        wid = c.post("/api/v1/workspaces", json={"name": "Alpha"}, cookies=cookies_for(a)).json()["id"]
        c.post(f"/api/v1/workspaces/{wid}/invite", json={"email": "b@x.com"}, cookies=cookies_for(a))
        c.post("/api/v1/workspaces/invitations/accept", json={"token": _invite_token(mail)}, cookies=cookies_for(b))
        a_uid = _uid(c, a)
        # bob (member) cannot invite or remove the owner
        assert c.post(f"/api/v1/workspaces/{wid}/invite", json={"email": "c@x.com"},
                      cookies=cookies_for(b)).status_code == 403
        assert c.post(f"/api/v1/workspaces/{wid}/members/{a_uid}/remove",
                      cookies=cookies_for(b)).status_code == 403


def test_foreign_invite_acceptance_rejected():
    app, repo, mail = build_auth_app()
    with TestClient(app) as c:
        register(c, "a@x.com", PW); register(c, "b@x.com", PW); register(c, "m@x.com", PW)
        a = login_token(c, "a@x.com", PW); m = login_token(c, "m@x.com", PW)
        wid = c.post("/api/v1/workspaces", json={"name": "Alpha"}, cookies=cookies_for(a)).json()["id"]
        c.post(f"/api/v1/workspaces/{wid}/invite", json={"email": "b@x.com"}, cookies=cookies_for(a))
        tok = _invite_token(mail)
        # mallory cannot accept bob's invite
        assert c.post("/api/v1/workspaces/invitations/accept", json={"token": tok},
                      cookies=cookies_for(m)).status_code == 403


def test_last_owner_cannot_leave():
    app, repo, mail = build_auth_app()
    with TestClient(app) as c:
        register(c, "a@x.com", PW)
        a = login_token(c, "a@x.com", PW)
        wid = c.post("/api/v1/workspaces", json={"name": "Alpha"}, cookies=cookies_for(a)).json()["id"]
        assert c.post(f"/api/v1/workspaces/{wid}/leave", cookies=cookies_for(a)).status_code == 409


def test_workspaces_require_auth_in_production():
    app, _, _ = build_auth_app(env="production")
    with TestClient(app) as c:
        assert c.get("/api/v1/workspaces").status_code == 401
        assert c.get("/api/v1/shares/mine").status_code == 401


def test_workspace_security_eval_gate_passes():
    r = subprocess.run([sys.executable, "scripts/eval_workspace_security.py"], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
