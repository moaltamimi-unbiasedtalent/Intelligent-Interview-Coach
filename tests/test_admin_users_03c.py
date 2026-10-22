"""03C Admin Users (REQ-OWN-03): search/sort/filter, complete detail, strict actions, protection rules, privacy sentinels. Real isolated SQLite, offline."""

from __future__ import annotations

import inspect
import json

import pytest
from sqlalchemy import select

from src.api import dependencies as deps
from src.admin_users.revision import account_revision
from src.api.schemas import admin_users as S
from src.application import admin_audit as A
from src.application import admin_permissions as perm
from src.persistence import AuditEvent, AuthToken, PrivacyRequest, User
from src.support_repository import SupportRepository
from tests import _admin_matrix as M
from tests._auth_factories import cookies_for, login_token, register, verification_token
from tests.test_admin_foundation_w10_1 import PW, Env

API = "/api/v1"
ZERO = "0" * 16
BANNED = ("cv", "document", "answer", "conversation", "memory", "evidence", "transcript", "prompt", "password", "secret", "token", "hash", "subject")


@pytest.fixture()
def env():
    e = Env()
    e.mail = None
    yield e
    e.close()


class H:
    """Small harness around the Env: users, personas, requests, audit reads."""

    def __init__(self, env: Env):
        self.e, self.c, self.n = env, env.c, 0
        self.sf = env.repo.session_factory

    def mk(self, role: str = "user"):
        self.n += 1
        email = f"c03{self.n}@x.com"
        register(self.c, email, PW)
        tok = login_token(self.c, email, PW)
        ck = cookies_for(tok)
        uid = self.c.get(f"{API}/auth/me", cookies=ck).json()["user_id"]
        if role != "user":
            self.e.accounts.set_platform_role(uid, role)
        return uid, email, ck

    def rev(self, ck, uid) -> str:
        return self.c.get(f"{API}/admin/users/{uid}", cookies=ck).json()["revision"]

    def act(self, ck, uid, action, *, rev=None, reason="operator review", **extra):
        body = {"expected_revision": rev if rev is not None else self.rev(ck, uid), "reason": reason, **extra}
        return self.c.post(f"{API}/admin/users/{uid}/actions/{action}", json=body, cookies=ck)

    def audit(self, event_type, target_id=None):
        with self.sf() as s:
            q = select(AuditEvent).where(AuditEvent.event_type == event_type)
            if target_id is not None:
                q = q.where(AuditEvent.target_id == str(target_id))
            return s.scalars(q.order_by(AuditEvent.id)).all()


@pytest.fixture()
def h(env):
    return H(env)


# ------------------------------------------------------------------------------------------------- U1 list: search / sort / filter / pagination
def test_list_sort_filter_pagination_metadata_only(h):
    _, _, admin = h.mk("platform_admin")
    a, ea, _ = h.mk()
    b, eb, _ = h.mk()
    items = h.c.get(f"{API}/admin/users?sort=email&direction=asc&page_size=100", cookies=admin).json()["items"]
    emails = [i["email"] for i in items]
    assert emails == sorted(emails)
    desc = h.c.get(f"{API}/admin/users?sort=email&direction=desc&page_size=100", cookies=admin).json()["items"]
    assert [i["email"] for i in desc] == sorted(emails, reverse=True)
    page = h.c.get(f"{API}/admin/users?sort=email&direction=asc&page_size=2&page=2", cookies=admin).json()
    assert page["page"] == 2 and len(page["items"]) == 1 and page["total"] == 3 and page["items"][0]["email"] == emails[2]
    assert set(items[0]) == {"user_id", "email", "display_name", "status", "platform_role", "tier", "onboarding_completed", "interface_locale", "email_verified",
                            "created_at", "updated_at", "workspace_count", "active_session_count", "last_activity"}
    for bad in ("sort=password_hash", "direction=sideways", "last_active=yesterday", "open_case=cv", "auth_method=magic"):
        assert h.c.get(f"{API}/admin/users?{bad}", cookies=admin).status_code == 422, bad
    assert [i["user_id"] for i in h.c.get(f"{API}/admin/users?q={ea}", cookies=admin).json()["items"]] == [a]


def test_list_filters_activity_auth_method_cases_and_workspace(h):
    _, _, admin = h.mk("platform_admin")
    u, _, uck = h.mk()
    v, _, _ = h.mk()
    # last activity: every account just signed in => 24h bucket; an account with no session is 'never'
    got = {i["user_id"]: i["last_activity"] for i in h.c.get(f"{API}/admin/users?page_size=100", cookies=admin).json()["items"]}
    assert set(got.values()) == {"24h"}
    assert h.c.get(f"{API}/admin/users?last_active=never", cookies=admin).json()["total"] == 0
    assert h.c.get(f"{API}/admin/users?last_active=24h", cookies=admin).json()["total"] == 3
    assert h.c.get(f"{API}/admin/users?auth_method=password", cookies=admin).json()["total"] == 3
    assert h.c.get(f"{API}/admin/users?auth_method=other", cookies=admin).json()["total"] == 0
    SupportRepository(h.sf).create_ticket(owner_user_id=u, category="account_login", subject="SENTINEL-SUBJECT", message="SENTINEL-BODY", request_id=None,
                                          source_route=None, environment=None)
    r = h.c.get(f"{API}/admin/users?open_case=support", cookies=admin).json()
    assert [i["user_id"] for i in r["items"]] == [u]
    assert "SENTINEL" not in json.dumps(r)
    assert h.c.get(f"{API}/admin/users?open_case=privacy", cookies=admin).json()["total"] == 0
    assert h.c.get(f"{API}/admin/users?has_workspace=true", cookies=admin).json()["total"] == 0
    assert h.c.get(f"{API}/admin/users?has_workspace=false", cookies=admin).json()["total"] == 3
    h.c.post(f"{API}/workspaces", json={"name": "Team"}, cookies=uck)
    assert [i["user_id"] for i in h.c.get(f"{API}/admin/users?has_workspace=true", cookies=admin).json()["items"]] == [u]
    assert v not in [i["user_id"] for i in h.c.get(f"{API}/admin/users?has_workspace=true", cookies=admin).json()["items"]]


# ------------------------------------------------------------------------------------------------- complete detail + privacy sentinels
def test_detail_is_complete_and_leaks_nothing(h):
    _, _, admin = h.mk("platform_admin")
    u, email, _ = h.mk()
    SupportRepository(h.sf).create_ticket(owner_user_id=u, category="account_login", subject="SENTINEL-SUBJECT", message="SENTINEL-BODY", request_id=None,
                                          source_route=None, environment=None)
    from src.privacy.requests import PrivacyRequestService
    PrivacyRequestService(h.sf).create(u, "data_access", "SENTINEL-PRIVACY-NOTE")
    d = h.c.get(f"{API}/admin/users/{u}", cookies=admin).json()
    assert d["auth"]["methods"] == [{"method": "password", "email_verified": False, "linked_at": d["auth"]["methods"][0]["linked_at"]}]
    assert d["auth"]["local_sign_in"] is True and d["auth"]["pending_verification_links"] >= 1
    assert d["activity"] == {"last_active": "24h"}
    assert d["cases"]["support_open"] == 1 and d["cases"]["support_total"] == 1 and d["cases"]["privacy_open"] == 1 and d["cases"]["open_deletion_request_id"] is None
    assert d["membership"] == {"active": 0, "total": 0, "owner_of_active": 0}
    assert d["plan"]["current"]["plan_code"] == "basic" and len(d["revision"]) == 16
    text = json.dumps(d)
    for needle in ("SENTINEL", PW, "password_hash", "$2b$", "token_hash"):
        assert needle not in text
    assert text.count(email) == 1                      # the account email appears exactly once (the existing summary)
    with h.sf() as s:                                  # the revision is derived, not stored, and is deterministic
        user = s.get(User, u)
        assert account_revision(s, user) == account_revision(s, user) == d["revision"]


def test_new_schemas_carry_no_banned_field_names():
    for model in (S.AuthMethod, S.AdminUserAuth, S.AdminUserActivity, S.AdminUserCases, S.AdminUserMembership, S.ActionBody, S.AssignPlanBody, S.ActionResult):
        assert model.model_config.get("extra") == "forbid"
        for name in model.model_fields:
            assert not any(b in name.lower() for b in BANNED), (model.__name__, name)


# ------------------------------------------------------------------------------------------------- 7-persona matrix for every strict route
ACTIONS = ("deactivate", "reactivate", "force-signout", "assign-plan", "resend-verification", "expire-verification", "request-deletion")


def test_every_action_route_uses_an_existing_permission_and_the_registry_is_unchanged():
    assert len(perm.PERMISSIONS) == 44
    rs = {r.path: r for r in M.routes() if r.path.startswith("/admin/users/{user_id}/actions/")}
    assert {p.rsplit("/", 1)[1] for p in rs} == set(ACTIONS)
    for r in rs.values():
        assert r.permissions and r.permissions <= perm.PERMISSION_SET


def test_seven_persona_matrix_for_actions(h):
    uid, _, _ = h.mk()
    cookies = {}
    for persona in M.PERSONAS:
        cookies[persona] = h.mk(persona)[2] if persona != "user" else h.mk()[2]
    routes = {r.path.rsplit("/", 1)[1]: r for r in M.routes() if r.path.startswith("/admin/users/{user_id}/actions/")}
    for action, route in routes.items():
        for persona in M.PERSONAS:
            body = {"expected_revision": ZERO, "reason": "matrix probe"}
            if action == "assign-plan":
                body["plan_code"] = "basic"
            r = h.c.post(f"{API}/admin/users/{uid}/actions/{action}", json=body, cookies=cookies[persona])
            if M.expected_allowed(route.permissions, persona):
                assert r.status_code == 409, (action, persona, r.status_code, r.text)     # authorised, then stopped by the (deliberately stale) revision
            else:
                assert r.status_code == 403, (action, persona, r.status_code)
    assert h.c.post(f"{API}/admin/users/{uid}/actions/deactivate", json={"expected_revision": ZERO, "reason": "x1"}).status_code in (401, 403)


# ------------------------------------------------------------------------------------------------- strict body: revision + reason + allowlist
def test_body_validation_is_strict(h):
    _, _, admin = h.mk("platform_admin")
    u, _, _ = h.mk()
    url = f"{API}/admin/users/{u}/actions/deactivate"
    rev = h.rev(admin, u)
    assert h.c.post(url, json={"reason": "operator review"}, cookies=admin).status_code == 422                       # revision mandatory
    assert h.c.post(url, json={"expected_revision": rev}, cookies=admin).status_code == 422                          # reason mandatory
    assert h.c.post(url, json={"expected_revision": rev, "reason": "ab"}, cookies=admin).status_code == 422          # reason too short
    assert h.c.post(url, json={"expected_revision": rev, "reason": "x" * 201}, cookies=admin).status_code == 422
    assert h.c.post(url, json={"expected_revision": "not-hex!", "reason": "operator review"}, cookies=admin).status_code == 422
    assert h.c.post(url, json={"expected_revision": rev, "reason": "operator review", "platform_role": "platform_admin"}, cookies=admin).status_code == 422
    assert h.c.post(f"{API}/admin/users/{u}/actions/assign-plan", json={"expected_revision": rev, "reason": "operator review", "plan_code": "gold"},
                    cookies=admin).status_code == 422
    assert h.c.get(f"{API}/admin/users/{u}", cookies=admin).json()["account"]["status"] == "active"


# ------------------------------------------------------------------------------------------------- lifecycle, revision, audit
def test_deactivate_reactivate_with_revision_and_atomic_audit(h):
    _, _, admin = h.mk("platform_admin")
    u, email, uck = h.mk()
    stale = h.rev(admin, u)
    r = h.act(admin, u, "deactivate", reason="abuse report")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["changed"] is True and body["sessions_revoked"] == 1 and body["revision"] != stale
    assert h.c.get(f"{API}/auth/me", cookies=uck).status_code == 401                          # session ended in the same transaction
    assert h.act(admin, u, "deactivate", rev=stale).status_code == 409                          # stale screen cannot replay or overwrite
    rows = h.audit(A.ADMIN_ACCOUNT_STATUS_CHANGE, u)
    assert len(rows) == 1 and rows[0].context["reason"] == "abuse report" and rows[0].context["after"] == "deactivated" and rows[0].context["sessions_revoked"] == 1
    assert email not in json.dumps(rows[0].context) and rows[0].actor_user_id is not None
    # idempotent by state: with a FRESH revision a repeat is a recorded no-op
    again = h.act(admin, u, "deactivate").json()
    assert again["changed"] is False and again["sessions_revoked"] == 0
    assert h.act(admin, u, "reactivate").json()["changed"] is True
    assert h.c.get(f"{API}/auth/me", cookies=uck).status_code == 401                          # old session is not revived


def test_force_signout_assign_plan_and_history(h):
    _, _, admin = h.mk("platform_admin")
    u, _, uck = h.mk()
    assert h.act(admin, u, "force-signout", reason="lost device").json()["sessions_revoked"] == 1
    assert h.c.get(f"{API}/auth/me", cookies=uck).status_code == 401
    r = h.act(admin, u, "assign-plan", reason="pilot upgrade", plan_code="premium")
    assert r.status_code == 200 and r.json()["plan_code"] == "premium" and r.json()["changed"] is True
    d = h.c.get(f"{API}/admin/users/{u}", cookies=admin).json()
    assert d["plan"]["current"]["plan_code"] == "premium" and len(d["plan"]["history"]) == 2 and d["account"]["tier"] == "premium"
    rows = h.audit(A.ADMIN_SUBSCRIPTION_ASSIGNED, u)
    assert len(rows) == 1 and rows[0].context["reason"] == "pilot upgrade" and rows[0].context["after_plan"] == "premium"
    stale = h.rev(admin, u)
    h.act(admin, u, "assign-plan", reason="pilot downgrade", plan_code="basic")
    assert h.act(admin, u, "assign-plan", rev=stale, plan_code="premium").status_code == 409


# ------------------------------------------------------------------------------------------------- protection rules
def test_self_actions_and_hierarchy_are_refused_server_side(h):
    me, _, admin = h.mk("platform_admin")
    other, _, other_ck = h.mk("platform_admin")
    for action, extra in (("deactivate", {}), ("force-signout", {}), ("assign-plan", {"plan_code": "premium"}), ("request-deletion", {}),
                          ("resend-verification", {}), ("expire-verification", {})):
        r = h.act(admin, me, action, **extra)
        assert r.status_code == 409, (action, r.status_code)
    assert h.c.get(f"{API}/admin/users/{me}", cookies=admin).json()["account"]["status"] == "active"
    # a security/privacy admin (sessions.revoke, privacy.execute) cannot act on a MORE privileged account, but can on a candidate
    _, _, sec = h.mk("security_privacy_admin")
    cand, _, _ = h.mk()
    assert h.act(sec, other, "force-signout").status_code == 403
    assert h.act(sec, other, "request-deletion").status_code == 403
    assert h.c.get(f"{API}/auth/me", cookies=other_ck).status_code == 200
    assert h.act(sec, cand, "force-signout").status_code == 200
    # a billing admin may assign plans to anyone but never to themselves
    bid, _, bill = h.mk("billing_admin")
    assert h.act(bill, bid, "assign-plan", plan_code="premium").status_code == 409
    assert h.act(bill, cand, "assign-plan", plan_code="premium").status_code == 200
    # legacy force-logout route is also hierarchy-protected
    assert h.c.post(f"{API}/admin/users/{other}/sessions/revoke", json={}, cookies=sec).status_code == 403
    assert h.c.get(f"{API}/auth/me", cookies=other_ck).status_code == 200


def test_last_active_platform_admin_stays_protected(h):
    from src.admin_repository import AdminUserRepository
    from src.application.errors import ConflictError

    _, _, _ = h.mk("platform_admin")
    only = h.mk("platform_admin")[0]
    with h.sf() as s:                                   # make `only` the single active admin
        for u in s.scalars(select(User).where(User.platform_role == "platform_admin", User.id != only)).all():
            u.status = "deactivated"
        s.commit()
    with pytest.raises(ConflictError):
        AdminUserRepository(h.sf).set_status(only, "deactivated")


def test_role_cannot_be_changed_by_any_users_route_and_role_request_is_revision_guarded(h):
    _, _, admin = h.mk("platform_admin")
    u, _, _ = h.mk()
    for r in M.routes():
        if r.path.startswith("/admin/users") and r.methods != ("GET",):
            src = r.route.endpoint.__module__ + r.route.endpoint.__qualname__
            assert "role" not in r.path.replace("role-changes", ""), r.path
            assert "set_platform_role" not in inspect.getsource(r.route.endpoint), src
    d = h.c.get(f"{API}/admin/users/{u}", cookies=admin).json()
    # the W10.13 flow needs a step-up; a stale revision is refused before anything is created
    pw = h.c.post(f"{API}/admin/step-up", json={"password": PW}, cookies=admin)
    assert pw.status_code == 200
    bad = h.c.post(f"{API}/admin/role-changes", json={"target_user_id": u, "role": "support_operator", "reason": "needs support access", "expected_revision": ZERO},
                   cookies=admin)
    assert bad.status_code == 409
    ok = h.c.post(f"{API}/admin/role-changes", json={"target_user_id": u, "role": "support_operator", "reason": "needs support access",
                                                     "expected_revision": d["revision"]}, cookies=admin)
    assert ok.status_code == 200 and ok.json()["status"] == "pending"
    assert h.c.get(f"{API}/admin/users/{u}", cookies=admin).json()["account"]["platform_role"] == "user"     # nothing applied without a second Admin
    assert h.c.get(f"{API}/admin/users/{u}", cookies=admin).json()["cases"]["pending_role_change"] is True


# ------------------------------------------------------------------------------------------------- verification flows
def test_resend_and_expire_verification(h):
    _, _, admin = h.mk("platform_admin")
    u, email, _ = h.mk()
    sender = h.e.app.dependency_overrides[deps.get_email_sender]()    # the capture sender wired by build_auth_app
    before = len(sender.sent)
    r = h.act(admin, u, "resend-verification", reason="user lost the email")
    assert r.status_code == 200 and r.json()["mail_accepted"] is True
    assert len(sender.sent) == before + 1 and verification_token(sender)
    rows = h.audit(A.ADMIN_USER_VERIFICATION_RESENT, u)
    assert len(rows) == 1 and rows[0].context["reason"] == "user lost the email" and email not in json.dumps(rows[0].context)
    sent_token = verification_token(sender)
    assert h.c.get(f"{API}/admin/users/{u}", cookies=admin).json()["auth"]["pending_verification_links"] == 1
    exp = h.act(admin, u, "expire-verification", reason="suspected misuse")
    assert exp.status_code == 200 and exp.json()["links_expired"] == 1 and exp.json()["changed"] is True
    assert h.c.post(f"{API}/auth/verify-email", json={"token": sent_token}).status_code in (400, 410, 422)           # the link no longer works
    assert h.audit(A.ADMIN_USER_VERIFICATION_EXPIRED, u)[0].context["links_expired"] == 1
    assert h.act(admin, u, "expire-verification").json()["changed"] is False                                          # nothing left: recorded no-op
    v, _, _ = h.mk()
    h.e.accounts.mark_email_verified(v)
    assert h.act(admin, v, "resend-verification", reason="verified already").status_code == 409                        # nothing to resend


def test_resend_refused_for_deactivated_account(h):
    _, _, admin = h.mk("platform_admin")
    u, _, _ = h.mk()
    h.act(admin, u, "deactivate")
    assert h.act(admin, u, "resend-verification").status_code == 409


# ------------------------------------------------------------------------------------------------- deletion only through the privacy pipeline
def test_request_deletion_uses_the_existing_privacy_pipeline_and_deletes_nothing(h):
    _, _, admin = h.mk("platform_admin")
    u, _, _ = h.mk()
    r = h.act(admin, u, "request-deletion", reason="user asked by letter")
    assert r.status_code == 200, r.text
    rid = r.json()["request_id"]
    assert r.json()["changed"] is True and rid
    with h.sf() as s:
        pr = s.scalar(select(PrivacyRequest).where(PrivacyRequest.public_id == rid))
        assert pr.request_type == "deletion" and pr.source == "admin_recorded" and pr.user_id == u and pr.created_by_user_id is not None
        assert s.get(User, u) is not None and s.get(User, u).status == "active"        # NOTHING was deleted or deactivated by this action
    again = h.act(admin, u, "request-deletion").json()
    assert again["request_id"] == rid and again["changed"] is False                      # idempotent: never a second open request
    d = h.c.get(f"{API}/admin/users/{u}", cookies=admin).json()
    assert d["cases"]["open_deletion_request_id"] == rid
    assert len(h.audit(A.ADMIN_USER_DELETION_REQUESTED, rid)) == 1
    listed = h.c.get(f"{API}/admin/privacy/requests", cookies=admin).json()
    assert rid in json.dumps(listed)
    # execution stays in the existing, separately gated pipeline: refused until the request is acknowledged, then it queues the SAME job candidates use
    assert h.c.post(f"{API}/admin/privacy/requests/{rid}/execute-deletion", cookies=admin).status_code == 409
    assert h.c.post(f"{API}/admin/privacy/requests/{rid}/status", json={"status": "acknowledged"}, cookies=admin).status_code == 200
    assert h.c.post(f"{API}/admin/privacy/requests/{rid}/execute-deletion", cookies=admin).status_code == 200


# ------------------------------------------------------------------------------------------------- atomicity: an audit failure rolls the change back
def test_audit_failure_rolls_back_the_mutation(h, monkeypatch):
    _, _, admin = h.mk("platform_admin")
    u, _, _ = h.mk()
    h.act(admin, u, "resend-verification")
    rev = h.rev(admin, u)

    def boom(*a, **k):
        raise RuntimeError("audit store down")

    monkeypatch.setattr("src.admin_users.actions._stage", boom)
    assert h.act(admin, u, "expire-verification", rev=rev).status_code == 500
    with h.sf() as s:
        assert s.scalar(select(AuthToken).where(AuthToken.user_id == u, AuthToken.consumed_at.is_(None))) is not None     # token untouched


# ------------------------------------------------------------------------------------------------- legacy routes: optional revision is enforced when supplied
def test_legacy_routes_enforce_a_supplied_revision(h):
    _, _, admin = h.mk("platform_admin")
    u, _, _ = h.mk()
    assert h.c.post(f"{API}/admin/users/{u}/status", json={"status": "deactivated", "expected_revision": ZERO}, cookies=admin).status_code == 409
    assert h.c.post(f"{API}/admin/users/{u}/plan", json={"plan_code": "premium", "expected_revision": ZERO}, cookies=admin).status_code == 409
    assert h.c.post(f"{API}/admin/users/{u}/sessions/revoke", json={"expected_revision": ZERO}, cookies=admin).status_code == 409
    rev = h.rev(admin, u)
    assert h.c.post(f"{API}/admin/users/{u}/status", json={"status": "deactivated", "expected_revision": rev}, cookies=admin).status_code == 200


def test_actions_on_unknown_account_are_404(h):
    _, _, admin = h.mk("platform_admin")
    for action in ACTIONS:
        extra = {"plan_code": "basic"} if action == "assign-plan" else {}
        assert h.act(admin, 99999, action, rev=ZERO, **extra).status_code == 404, action
