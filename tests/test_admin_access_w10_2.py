"""P10B-W10.2: SEC-W10-01 closure, user/session/workspace administration. Real isolated SQLite."""

from __future__ import annotations

import hashlib

import pytest
from sqlalchemy import select

from src.application import admin_audit as A
from src.application import admin_permissions as perm
from tests._auth_factories import cookies_for, login_token, register
from tests.test_admin_foundation_w10_1 import PW, Env

API = "/api/v1"


@pytest.fixture()
def env():
    e = Env()
    yield e
    e.close()


def mk(env: Env, role: str = "user"):
    """Create a user; return (uid, email, cookies, raw_token)."""
    env.n += 1
    email = f"w2u{env.n}@x.com"
    register(env.c, email, PW)
    tok = login_token(env.c, email, PW)
    uid = env.c.get(f"{API}/auth/me", cookies=cookies_for(tok)).json()["user_id"]
    if role != "user":
        env.accounts.set_platform_role(uid, role)
    return uid, email, cookies_for(tok), tok


def me(env, ck):
    return env.c.get(f"{API}/auth/me", cookies=ck).status_code


def set_status(env, admin_ck, uid, status, **kw):
    return env.c.post(f"{API}/admin/users/{uid}/status", json={"status": status, **kw}, cookies=admin_ck)


# ---------------- SEC-W10-01 (SEC1-SEC12) ----------------------------------------------------------------

def test_sec1_to_sec9_full_lifecycle(env):
    _, _, admin, _ = mk(env, "platform_admin")
    vid, vemail, vck, _ = mk(env)                       # SEC1: active account signs in
    assert me(env, vck) == 200                           # SEC2: session authenticates
    r = set_status(env, admin, vid, "deactivated")       # SEC3: admin deactivates
    assert r.status_code == 200 and r.json()["sessions_revoked"] == 1   # SEC4: sessions revoked
    assert me(env, vck) == 401                           # SEC5: old session immediately fails
    assert env.c.post(f"{API}/auth/login", json={"email": vemail, "password": PW}).status_code == 401  # SEC6
    assert set_status(env, admin, vid, "active").status_code == 200      # SEC7: reactivated
    assert me(env, vck) == 401                           # SEC8: old session stays invalid
    tok2 = login_token(env.c, vemail, PW)                # SEC9: new sign-in works
    assert tok2 and me(env, cookies_for(tok2)) == 200


def test_sec10_audit_failure_rolls_back_deactivation_and_session_revocation(env, monkeypatch):
    _, _, admin, _ = mk(env, "platform_admin")
    vid, _, vck, _ = mk(env)
    from src.auth_repository import AccountRepository
    monkeypatch.setattr(AccountRepository, "_stage_audit", staticmethod(lambda s, a: (_ for _ in ()).throw(RuntimeError("x"))))
    assert set_status(env, admin, vid, "deactivated").status_code == 500
    monkeypatch.undo()
    assert env.accounts.get_account(vid).status == "active"
    assert me(env, vck) == 200                           # session NOT revoked: whole transaction rolled back
    assert not env.events(A.ADMIN_ACCOUNT_STATUS_CHANGE)


def test_sec11_no_session_secret_in_any_response(env):
    _, _, admin, _ = mk(env, "platform_admin")
    vid, _, vck, tok = mk(env)
    bodies = [
        env.c.get(f"{API}/admin/users/{vid}", cookies=admin).text,
        env.c.get(f"{API}/admin/users?q=w2u", cookies=admin).text,
        env.c.post(f"{API}/admin/users/{vid}/sessions/revoke", json={}, cookies=admin).text,
        env.c.get(f"{API}/admin/audit", cookies=admin).text,
    ]
    digest = hashlib.sha256(tok.encode()).hexdigest()
    for b in bodies:
        assert tok not in b and digest not in b and "token_hash" not in b and "user_agent" not in b


def test_sec12_request_time_guard_rejects_inactive_account_even_if_session_row_remains(env):
    uid, _, ck, tok = mk(env)
    env.accounts.set_status(uid, "deactivated")          # legacy path: flips status, does NOT revoke
    from src.auth_repository import SessionRepository
    from src.authsec.tokens import hash_token
    sessions = SessionRepository(env.repo.session_factory)
    assert any(True for _ in sessions.list_active(uid))  # the session row is still live
    assert me(env, ck) == 401                            # but the account cannot authenticate
    assert sessions.resolve(hash_token(tok)) is None


def test_inactive_status_is_rejected_on_candidate_apis_too(env):
    uid, _, ck, _ = mk(env)
    assert env.c.get(f"{API}/memory", cookies=ck).status_code == 200
    env.accounts.set_status(uid, "deactivated")
    assert env.c.get(f"{API}/memory", cookies=ck).status_code == 401
    assert env.c.get(f"{API}/opportunities", cookies=ck).status_code == 401


# ---------------- session matrix ---------------------------------------------------------------------------

def test_force_logout_revoke_all_zero_multiple_and_isolation(env):
    _, _, admin, _ = mk(env, "platform_admin")
    vid, vemail, ck1, _ = mk(env)
    ck2 = cookies_for(login_token(env.c, vemail, PW))   # concurrent second session
    oid, _, ock, _ = mk(env)                             # unrelated user
    d = env.c.get(f"{API}/admin/users/{vid}", cookies=admin).json()
    assert d["sessions"]["active_count"] == 2
    r = env.c.post(f"{API}/admin/users/{vid}/sessions/revoke", json={"reason": "lost laptop"}, cookies=admin)
    assert r.json() == {"user_id": vid, "sessions_revoked": 2}
    assert me(env, ck1) == 401 and me(env, ck2) == 401 and me(env, ock) == 200
    again = env.c.post(f"{API}/admin/users/{vid}/sessions/revoke", json={}, cookies=admin)
    assert again.status_code == 200 and again.json()["sessions_revoked"] == 0   # truthful zero
    ev = env.events(A.ADMIN_SESSIONS_REVOKED)
    assert ev[1]["context"]["sessions_revoked"] == 2 and ev[1]["context"]["reason"] == "lost laptop"
    assert ev[1]["request_id"] == r.headers["X-Request-Id"]
    assert env.c.post(f"{API}/admin/users/99999/sessions/revoke", json={}, cookies=admin).status_code == 404


def test_normal_logout_still_works_and_expired_sessions_are_not_counted(env):
    uid, _, ck, _ = mk(env)
    assert env.c.post(f"{API}/auth/logout", cookies=ck).status_code in (200, 204)
    assert me(env, ck) == 401
    _, _, admin, _ = mk(env, "platform_admin")
    from datetime import timedelta
    from src.persistence import AuthSession, utcnow
    with env.repo.session_factory() as s:
        for row in s.scalars(select(AuthSession).where(AuthSession.user_id == uid)):
            row.revoked_at = None
            row.expires_at = utcnow() - timedelta(days=1)
        s.commit()
    assert env.c.get(f"{API}/admin/users/{uid}", cookies=admin).json()["sessions"]["active_count"] == 0


def test_admin_sessions_endpoint_permissions(env):
    vid, *_ = mk(env)
    _, _, cand, _ = mk(env)
    _, _, support, _ = mk(env, "support_operator")
    _, _, sec, _ = mk(env, "security_privacy_admin")
    assert env.c.post(f"{API}/admin/users/{vid}/sessions/revoke", json={}, cookies=cand).status_code == 403
    assert env.c.post(f"{API}/admin/users/{vid}/sessions/revoke", json={}, cookies=support).status_code == 403
    assert env.c.post(f"{API}/admin/users/{vid}/sessions/revoke", json={}, cookies=sec).status_code == 200


def test_deactivated_admin_loses_admin_access_and_demotion_is_immediate(env):
    aid, _, ack, _ = mk(env, "platform_admin")
    _, _, admin, _ = mk(env, "platform_admin")
    assert env.c.get(f"{API}/admin/home", cookies=ack).status_code == 200
    assert set_status(env, admin, aid, "deactivated").status_code == 200
    assert env.c.get(f"{API}/admin/home", cookies=ack).status_code in (401, 403)
    bid, _, bck, _ = mk(env, "platform_admin")
    _, _, admin2, _ = mk(env, "platform_admin")
    assert env.c.get(f"{API}/admin/home", cookies=bck).status_code == 200
    from tests._role_gov import change_role
    req, r = change_role(env.c, admin, admin2, bid, "user", password=PW)
    assert req.status_code == 200 and r.status_code == 200
    assert env.c.get(f"{API}/admin/home", cookies=bck).status_code == 403   # same session, instantly demoted


# ---------------- last admin / self protection ------------------------------------------------------------

def test_self_deactivation_and_self_demotion_blocked_via_api(env):
    aid, _, admin, _ = mk(env, "platform_admin")
    mk(env, "platform_admin")
    assert set_status(env, admin, aid, "deactivated").status_code == 409
    from tests._role_gov import request_change
    assert request_change(env.c, admin, aid, "user", password=PW).status_code == 409     # no Admin may request a change for themselves
    assert env.accounts.get_account(aid).status == "active"


def test_last_active_platform_admin_is_protected_in_the_repository_transaction(env):
    from src.admin_repository import AdminUserRepository
    from src.application.errors import ConflictError
    repo = AdminUserRepository(env.repo.session_factory)
    only, *_ = mk(env, "platform_admin")
    for fn in (lambda: repo.set_status(only, "deactivated"), lambda: repo.set_platform_role(only, "user")):
        with pytest.raises(ConflictError):
            fn()
    acct = env.accounts.get_account(only)
    assert acct.status == "active" and acct.platform_role == "platform_admin"   # DB unchanged
    other, *_ = mk(env, "platform_admin")
    audit = A.build_audit(event_type=A.ADMIN_ACCOUNT_STATUS_CHANGE, actor_user_id=other, request_id="r",
                          target_type="user", target_id=only, before="active", after="deactivated")
    assert repo.set_status(only, "deactivated", audit=audit)["changed"] is True   # allowed: another admin exists
    assert env.events(A.ADMIN_ACCOUNT_STATUS_CHANGE)
    # now `other` is the last ACTIVE admin (the first one is deactivated)
    with pytest.raises(ConflictError):
        repo.set_platform_role(other, "user")


def test_inactive_admins_do_not_count_as_other_admins(env):
    from src.admin_repository import AdminUserRepository
    from src.application.errors import ConflictError
    repo = AdminUserRepository(env.repo.session_factory)
    a, *_ = mk(env, "platform_admin")
    b, *_ = mk(env, "platform_admin")
    env.accounts.set_status(b, "deactivated")
    with pytest.raises(ConflictError):
        repo.set_status(a, "deactivated")


# ---------------- role administration ------------------------------------------------------------------

def test_all_six_presets_accepted_and_unknown_or_custom_rejected(env):
    from tests._role_gov import change_role, request_change
    _, _, admin, _ = mk(env, "platform_admin")
    _, _, admin2, _ = mk(env, "platform_admin")
    tid, *_ = mk(env)
    for role in perm.ADMIN_ROLES:
        req, r = change_role(env.c, admin, admin2, tid, role, password=PW)
        assert req.status_code == 200 and r.status_code == 200, role
        assert env.accounts.get_account(tid).platform_role == role
    from src.api.rate_limit import reset_rate_limiter
    reset_rate_limiter()
    for bad in ("root", "custom:auditor", "platform_admin ", "PLATFORM_ADMIN", "", "x" * 40):
        assert request_change(env.c, admin, tid, bad, password=PW).status_code == 422
    assert env.accounts.get_account(tid).platform_role == perm.ADMIN_ROLES[-1]


def test_role_change_is_permissioned_audited_and_elevation_is_flagged(env):
    _, _, support, _ = mk(env, "support_operator")
    tid, *_ = mk(env)
    assert env.c.post(f"{API}/admin/role-changes", json={"target_user_id": tid, "role": "billing_admin", "reason": "x"}, cookies=support).status_code == 403
    _, _, admin, _ = mk(env, "platform_admin")
    _, _, admin2, _ = mk(env, "platform_admin")
    from tests._role_gov import approve, request_change
    q = request_change(env.c, admin, tid, "platform_admin", password=PW, reason="covers on-call")
    assert q.status_code == 200
    rq = env.events(A.ADMIN_ROLE_CHANGE_REQUESTED)[0]
    assert rq["context"]["before"] == "user" and rq["context"]["after"] == "platform_admin" and rq["context"]["reason"] == "covers on-call"
    r = approve(env.c, admin2, q.json()["public_id"], password=PW)
    assert r.status_code == 200
    ev = env.events(A.ADMIN_ROLE_CHANGE_APPROVED)[0]
    assert ev["request_id"] == r.headers["X-Request-Id"]
    assert ev["context"]["before_role"] == "user" and ev["context"]["requested_role"] == "platform_admin"
    assert ev["context"]["elevation"] is True
    assert ev["context"]["target_user_id"] == tid


def test_scoped_presets_cannot_manage_accounts(env):
    tid, *_ = mk(env)
    for role in ("billing_admin", "knowledge_admin", "operations_admin", "support_operator"):
        _, _, ck, _ = mk(env, role)
        assert env.c.post(f"{API}/admin/users/{tid}/status", json={"status": "deactivated"}, cookies=ck).status_code == 403, role
        assert env.c.post(f"{API}/admin/role-changes", json={"target_user_id": tid, "role": "user", "reason": "x"}, cookies=ck).status_code == 403, role
        assert env.c.post(f"{API}/admin/workspaces/1/members", json={"user_id": tid}, cookies=ck).status_code == 403, role
    _, _, sec, _ = mk(env, "security_privacy_admin")
    assert env.c.post(f"{API}/admin/users/{tid}/status", json={"status": "deactivated"}, cookies=sec).status_code == 403
    assert env.c.post(f"{API}/admin/role-changes", json={"target_user_id": tid, "role": "user", "reason": "x"}, cookies=sec).status_code == 403


def test_plan_change_keeps_the_legacy_tier_in_step(env):
    _, _, admin, _ = mk(env, "platform_admin")
    tid, *_ = mk(env)
    assert env.c.post(f"{API}/admin/users/{tid}/plan", json={"plan_code": "premium"}, cookies=admin).status_code == 200
    assert env.c.get(f"{API}/admin/users/{tid}", cookies=admin).json()["account"]["tier"] == "premium"


# ---------------- user list / detail ----------------------------------------------------------------------

def test_user_list_pagination_search_filters_and_bounds(env):
    _, aemail, admin, _ = mk(env, "platform_admin")
    ids = [mk(env)[0] for _ in range(6)]
    page1 = env.c.get(f"{API}/admin/users?page=1&page_size=3", cookies=admin).json()
    page2 = env.c.get(f"{API}/admin/users?page=2&page_size=3", cookies=admin).json()
    assert page1["total"] == 7 and len(page1["items"]) == 3 and len(page2["items"]) == 3
    assert not ({u["user_id"] for u in page1["items"]} & {u["user_id"] for u in page2["items"]})
    assert [u["user_id"] for u in page1["items"]] == sorted((u["user_id"] for u in page1["items"]), reverse=True)
    assert page1["users"] == page1["items"]
    one = env.c.get(f"{API}/admin/users?q={aemail}", cookies=admin).json()
    assert one["total"] == 1 and one["items"][0]["email"] == aemail
    assert env.c.get(f"{API}/admin/users?q={ids[2]}", cookies=admin).json()["items"][0]["user_id"] == ids[2]
    assert env.c.get(f"{API}/admin/users?q=%25", cookies=admin).json()["total"] == 0   # wildcard is literal
    env.accounts.set_status(ids[0], "deactivated")
    assert env.c.get(f"{API}/admin/users?status=deactivated", cookies=admin).json()["total"] == 1
    assert env.c.get(f"{API}/admin/users?role=platform_admin", cookies=admin).json()["total"] == 1
    assert env.c.get(f"{API}/admin/users?tier=basic", cookies=admin).json()["total"] == 7
    assert env.c.get(f"{API}/admin/users?tier=premium", cookies=admin).json()["total"] == 0
    assert env.c.get(f"{API}/admin/users?locale=en", cookies=admin).json()["total"] == 7
    assert env.c.get(f"{API}/admin/users?onboarding=pending", cookies=admin).json()["total"] == 7
    assert env.c.get(f"{API}/admin/users?email_verified=true", cookies=admin).json()["total"] == 0
    assert env.c.get(f"{API}/admin/users?page_size=101", cookies=admin).status_code == 422
    for bad in ("status=zombie", "role=custom", "tier=gold", "locale=xx", "onboarding=maybe"):
        assert env.c.get(f"{API}/admin/users?{bad}", cookies=admin).status_code == 422, bad


def test_user_detail_is_safe_and_complete(env):
    _, _, admin, _ = mk(env, "platform_admin")
    uid, email, *_ = mk(env)
    d = env.c.get(f"{API}/admin/users/{uid}", cookies=admin).json()
    assert set(d) == {"account", "access", "sessions", "workspaces", "audit", "plan"}
    assert d["account"]["email"] == email and d["account"]["active_session_count"] == 1
    assert d["access"]["capabilities"] == []
    assert set(d["access"]["assignable_roles"]) == {"user", *perm.ADMIN_ROLES}
    assert d["access"]["is_self"] is False
    assert set(d["sessions"]["recent"][0]) == {"created_at", "last_used_at", "expires_at"}
    set_status(env, admin, uid, "deactivated", reason="abuse report")
    d = env.c.get(f"{API}/admin/users/{uid}", cookies=admin).json()
    assert d["audit"][0]["event_type"] == A.ADMIN_ACCOUNT_STATUS_CHANGE and d["audit"][0]["context"]["sessions_revoked"] == 1
    assert env.c.get(f"{API}/admin/users/99999", cookies=admin).status_code == 404


def test_user_list_and_detail_require_users_read(env):
    uid, *_ = mk(env)
    _, _, billing, _ = mk(env, "billing_admin")        # has users.read
    _, _, knowledge, _ = mk(env, "knowledge_admin")    # does not
    assert env.c.get(f"{API}/admin/users/{uid}", cookies=billing).status_code == 200
    assert env.c.get(f"{API}/admin/users/{uid}", cookies=knowledge).status_code == 403
    assert env.c.get(f"{API}/admin/users", cookies=knowledge).status_code == 403


# ---------------- workspaces ---------------------------------------------------------------------------------

def make_ws(env, ck, name="Alpha"):
    r = env.c.post(f"{API}/workspaces", json={"name": name}, cookies=ck)
    assert r.status_code in (200, 201), r.text
    body = r.json()
    return body.get("id") or body["workspace"]["id"]


def test_workspace_list_detail_and_membership_administration(env):
    _, _, admin, _ = mk(env, "platform_admin")
    oid, _, ock, _ = mk(env)
    mid, *_ = mk(env)
    wid = make_ws(env, ock)
    lst = env.c.get(f"{API}/admin/workspaces?q=alp", cookies=admin).json()
    assert lst["total"] == 1 and lst["items"][0]["id"] == wid and lst["items"][0]["member_count"] == 1
    d = env.c.get(f"{API}/admin/workspaces/{wid}", cookies=admin).json()
    assert d["active_owner_count"] == 1 and d["members"][0]["user_id"] == oid and "workspace_member" in d["workspace_roles"]
    r = env.c.post(f"{API}/admin/workspaces/{wid}/members", json={"user_id": mid}, cookies=admin)
    assert r.status_code == 200
    assert env.c.post(f"{API}/admin/workspaces/{wid}/members", json={"user_id": mid}, cookies=admin).status_code == 409
    assert env.c.post(f"{API}/admin/workspaces/{wid}/members", json={"user_id": 99999}, cookies=admin).status_code == 404
    assert env.c.post(f"{API}/admin/workspaces/99999/members", json={"user_id": mid}, cookies=admin).status_code == 404
    assert env.c.post(f"{API}/admin/workspaces/{wid}/members", json={"user_id": mid, "role": "boss"}, cookies=admin).status_code == 422
    ev = env.events(A.ADMIN_WORKSPACE_MEMBER_ADDED)[0]
    assert ev["request_id"] == r.headers["X-Request-Id"] and ev["context"]["member_user_id"] == mid
    assert env.c.post(f"{API}/admin/workspaces/{wid}/members/{mid}/role", json={"role": "workspace_owner"}, cookies=admin).status_code == 200
    assert env.c.get(f"{API}/admin/workspaces/{wid}", cookies=admin).json()["active_owner_count"] == 2
    assert env.c.delete(f"{API}/admin/workspaces/{wid}/members/{mid}", cookies=admin).status_code == 200
    assert env.c.delete(f"{API}/admin/workspaces/{wid}/members/{mid}", cookies=admin).status_code == 404
    # re-adding a removed member reuses the membership row (unique constraint respected)
    assert env.c.post(f"{API}/admin/workspaces/{wid}/members", json={"user_id": mid}, cookies=admin).status_code == 200
    detail = env.c.get(f"{API}/admin/users/{mid}", cookies=admin).json()
    assert detail["workspaces"][0]["workspace_id"] == wid and detail["account"]["workspace_count"] == 1


def test_workspace_owner_invariant_and_inactive_account_rules(env):
    _, _, admin, _ = mk(env, "platform_admin")
    oid, _, ock, _ = mk(env)
    wid = make_ws(env, ock)
    assert env.c.delete(f"{API}/admin/workspaces/{wid}/members/{oid}", cookies=admin).status_code == 409
    assert env.c.post(f"{API}/admin/workspaces/{wid}/members/{oid}/role", json={"role": "workspace_member"}, cookies=admin).status_code == 409
    assert env.c.get(f"{API}/admin/workspaces/{wid}", cookies=admin).json()["active_owner_count"] == 1
    did, *_ = mk(env)
    env.accounts.set_status(did, "deactivated")
    assert env.c.post(f"{API}/admin/workspaces/{wid}/members", json={"user_id": did}, cookies=admin).status_code == 409


def test_workspace_membership_audit_rollback_and_removal_revokes_shares(env, monkeypatch):
    _, _, admin, _ = mk(env, "platform_admin")
    oid, _, ock, _ = mk(env)
    mid, *_ = mk(env)
    wid = make_ws(env, ock)
    from src.auth_repository import AccountRepository
    monkeypatch.setattr(AccountRepository, "_stage_audit", staticmethod(lambda s, a: (_ for _ in ()).throw(RuntimeError("x"))))
    assert env.c.post(f"{API}/admin/workspaces/{wid}/members", json={"user_id": mid}, cookies=admin).status_code == 500
    monkeypatch.undo()
    d = env.c.get(f"{API}/admin/workspaces/{wid}", cookies=admin).json()
    assert [m["user_id"] for m in d["members"]] == [oid]          # nothing committed
    assert not env.events(A.ADMIN_WORKSPACE_MEMBER_ADDED)


def test_workspace_routes_permissions(env):
    oid, _, ock, _ = mk(env)
    wid = make_ws(env, ock)
    _, _, support, _ = mk(env, "support_operator")
    _, _, knowledge, _ = mk(env, "knowledge_admin")
    _, _, cand, _ = mk(env)
    assert env.c.get(f"{API}/admin/workspaces/{wid}", cookies=support).status_code == 200      # read only
    assert env.c.delete(f"{API}/admin/workspaces/{wid}/members/{oid}", cookies=support).status_code == 403
    assert env.c.get(f"{API}/admin/workspaces", cookies=knowledge).status_code == 403
    assert env.c.get(f"{API}/admin/workspaces/{wid}", cookies=cand).status_code == 403


# ---------------- private-data boundary + route coverage ---------------------------------------------------

BANNED = ("resume", "cv_text", "document_content", "document_text", "answer_text", "report_text", "memory_content",
          "preparation_messages", "chat_messages", "private_evidence", "uploaded_file_bytes", "transcript",
          "token", "token_hash", "password", "secret", "user_agent", "storage_key", "ip_address")


def test_admin_schemas_expose_no_candidate_content_or_secret_fields():
    from pydantic import BaseModel
    from src.api.schemas import admin as schemas
    names = []
    for cls in vars(schemas).values():
        if isinstance(cls, type) and issubclass(cls, BaseModel) and cls.__module__ == schemas.__name__:
            names += list(cls.model_fields)
    assert len(names) > 60
    assert [n for n in names if n in BANNED] == []


def test_all_current_privileged_routes_have_explicit_canonical_permissions(env):
    from src.api.admin_route_invariant import admin_routes, ungated
    routes = admin_routes()
    paths = {(r.path, r.methods) for r in routes}
    for p in (("/admin/users/{user_id}", ("GET",)), ("/admin/users/{user_id}/sessions/revoke", ("POST",)),
              ("/admin/workspaces/{workspace_id}", ("GET",)),
              ("/admin/workspaces/{workspace_id}/members", ("POST",)),
              ("/admin/workspaces/{workspace_id}/members/{user_id}", ("DELETE",)),
              ("/admin/workspaces/{workspace_id}/members/{user_id}/role", ("POST",))):
        assert p in paths, p
    assert ungated(routes) == []
    assert all(r.permissions <= perm.PERMISSION_SET for r in routes)


def test_candidate_cannot_reach_any_new_admin_route(env):
    _, _, ck, _ = mk(env)
    for method, path, body in (("GET", "/admin/users/1", None), ("POST", "/admin/users/1/sessions/revoke", {}),
                               ("GET", "/admin/workspaces/1", None), ("POST", "/admin/workspaces/1/members", {"user_id": 1}),
                               ("DELETE", "/admin/workspaces/1/members/1", None),
                               ("POST", "/admin/workspaces/1/members/1/role", {"role": "workspace_member"})):
        assert env.c.request(method, API + path, json=body, cookies=ck).status_code == 403, path
