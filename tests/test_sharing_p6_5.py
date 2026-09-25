"""Explicit sharing security matrix per OPERATIONAL resource type (Capstone P6.5 closure).

Proves, over the real app for BOTH operational share types (interview report + story), that:
owner can share; non-owner cannot; membership required; member can read after share; foreign
workspace/user cannot read; revocation and source deletion remove access immediately;
ownership stays with the candidate; platform admin gets no automatic access; a share id
cannot bypass owner/resource validation; and preparation_summary is NOT operationally
shareable.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests._auth_factories import account_repo, build_auth_app, cookies_for, login_token, register

PW = "correcthorsebattery"


def _uid(c, token):
    return c.get("/api/v1/auth/me", cookies=cookies_for(token)).json()["user_id"]


def _invite_token(mail):
    return mail.sent[-1].body.split("token=")[1].split()[0]


def _seed_report(repo, owner_id: int) -> str:
    from src.persistence import Interview, Report

    with repo.session_factory() as s:
        iv = Interview(user_id=owner_id, configuration={"target_role": "PM"}, status="completed")
        s.add(iv)
        s.flush()
        s.add(Report(interview_id=iv.id, report={"overall_score": 90, "summary": "Great"}))
        s.commit()
        return str(iv.id)


def _seed_story(c, token) -> str:
    r = c.post("/api/v1/stories", json={"title": "Win", "status": "user_created", "situation": "Led a team"},
               cookies=cookies_for(token))
    return str(r.json()["id"])


def _setup(mail_capable=True):
    """alice(owner) + bob(member of A's workspace) + mallory(outsider) + admin."""
    app, repo, mail = build_auth_app()
    c = TestClient(app)
    c.__enter__()
    for e in ("alice@x.com", "bob@x.com", "mallory@x.com", "admin@x.com"):
        register(c, e, PW)
    a = login_token(c, "alice@x.com", PW)
    b = login_token(c, "bob@x.com", PW)
    m = login_token(c, "mallory@x.com", PW)
    adm = login_token(c, "admin@x.com", PW)
    account_repo(repo).set_platform_role(_uid(c, adm), "platform_admin")
    wid = c.post("/api/v1/workspaces", json={"name": "Alpha"}, cookies=cookies_for(a)).json()["id"]
    c.post(f"/api/v1/workspaces/{wid}/invite", json={"email": "bob@x.com"}, cookies=cookies_for(a))
    c.post("/api/v1/workspaces/invitations/accept", json={"token": _invite_token(mail)}, cookies=cookies_for(b))
    return c, repo, a, b, m, adm, wid


def _resource(kind, c, repo, owner_token):
    if kind == "interview_report":
        return _seed_report(repo, _uid(c, owner_token))
    return _seed_story(c, owner_token)


def _run_matrix(kind: str):
    c, repo, a, b, m, adm, wid = _setup()
    try:
        rid = _resource(kind, c, repo, a)
        base = "/api/v1/shares"

        # non-owner cannot share the resource (bob doesn't own alice's resource).
        assert c.post(base, json={"workspace_id": wid, "resource_type": kind, "resource_id": rid},
                      cookies=cookies_for(b)).status_code == 403

        # owner shares into the workspace.
        r = c.post(base, json={"workspace_id": wid, "resource_type": kind, "resource_id": rid},
                   cookies=cookies_for(a))
        assert r.status_code == 200, r.text
        share_id = r.json()["share_id"]

        # member can read after share.
        assert c.get(f"{base}/resource/{kind}/{rid}", cookies=cookies_for(b)).status_code == 200
        # foreign (non-member) user cannot read.
        assert c.get(f"{base}/resource/{kind}/{rid}", cookies=cookies_for(m)).status_code == 404
        # platform admin receives NO automatic access.
        assert c.get(f"{base}/resource/{kind}/{rid}", cookies=cookies_for(adm)).status_code == 404

        # a non-owner cannot revoke the share (share id cannot bypass owner validation).
        assert c.delete(f"{base}/{share_id}", cookies=cookies_for(b)).status_code == 404

        # revocation removes access immediately.
        assert c.delete(f"{base}/{share_id}", cookies=cookies_for(a)).status_code == 200
        assert c.get(f"{base}/resource/{kind}/{rid}", cookies=cookies_for(b)).status_code == 404

        # ownership remains with alice: she can still read her own resource by re-sharing.
        c.post(base, json={"workspace_id": wid, "resource_type": kind, "resource_id": rid}, cookies=cookies_for(a))
        assert c.get(f"{base}/resource/{kind}/{rid}", cookies=cookies_for(b)).status_code == 200

        # source deletion removes access (no resurrection from a stale grant).
        if kind == "story":
            assert c.delete(f"/api/v1/stories/{rid}", cookies=cookies_for(a)).status_code == 200
        else:
            with repo.session_factory():
                repo.delete_interview(_uid(c, a), int(rid))
        assert c.get(f"{base}/resource/{kind}/{rid}", cookies=cookies_for(b)).status_code == 404
    finally:
        c.__exit__(None, None, None)


def test_report_sharing_security_matrix():
    _run_matrix("interview_report")


def test_story_sharing_security_matrix():
    _run_matrix("story")


def test_cross_workspace_share_cannot_be_read_from_another_workspace():
    c, repo, a, b, m, adm, wid = _setup()
    try:
        # mallory creates her OWN workspace; bob is only in alice's workspace.
        rid = _seed_report(repo, _uid(c, a))
        c.post("/api/v1/shares", json={"workspace_id": wid, "resource_type": "interview_report", "resource_id": rid},
               cookies=cookies_for(a))
        # mallory (member of a different, own workspace) still cannot read alice's shared report.
        c.post("/api/v1/workspaces", json={"name": "Mallory WS"}, cookies=cookies_for(m))
        assert c.get(f"/api/v1/shares/resource/interview_report/{rid}", cookies=cookies_for(m)).status_code == 404
    finally:
        c.__exit__(None, None, None)


def test_preparation_summary_is_not_operationally_shareable():
    c, repo, a, b, m, adm, wid = _setup()
    try:
        r = c.post("/api/v1/shares",
                   json={"workspace_id": wid, "resource_type": "preparation_summary", "resource_id": "1"},
                   cookies=cookies_for(a))
        assert r.status_code == 422  # not in the operational allowlist
    finally:
        c.__exit__(None, None, None)
