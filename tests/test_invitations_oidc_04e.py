"""04E: the Google (OIDC) registration path needs an invitation too, but only when it would CREATE an account. Fake provider, no network."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from src.api import dependencies as deps
from src.application.oidc import OidcIdentity
from src.invitations import policy
from src.invitations import repository as R
from src.persistence import User
from tests._invitations_04e import Env, REFUSAL, full_database_text
from tests.test_auth_oidc import _FakeGoogle

START = "/api/v1/auth/oidc/google/start"
CALLBACK = "/api/v1/auth/oidc/google/callback"


def _identity(sub="g-new", email="new@example.com", verified=True):
    return OidcIdentity(provider="google", subject=sub, email=email, email_verified=verified, display_name="New")


@pytest.fixture()
def env(monkeypatch):
    # A local app with the requirement switched on: cookies work over http (Secure cookies are not stored by the test client).
    monkeypatch.setenv(policy.OVERRIDE_ENV_VAR, "true")
    e = Env("test")
    e.provider = _FakeGoogle(_identity())
    e.app.dependency_overrides[deps.get_oidc_provider] = lambda: e.provider
    yield e
    e.close()


def _flow(env: Env, *, code: str | None = None, identity: OidcIdentity | None = None):
    """start (optionally with the invitation header) then callback; returns the callback response."""
    if identity is not None:
        env.provider._identity = identity
    env.c.cookies.clear()
    headers = {"X-Invitation-Code": code} if code is not None else {}
    start = env.c.get(START, headers=headers)
    assert start.status_code == 200
    state = env.c.cookies.get("ask4mo_oidc_state")
    return env.c.get(CALLBACK, params={"code": "abc", "state": state}, follow_redirects=False)


def _users(env: Env, email: str) -> int:
    return env.set_user_count(email)


def test_new_google_account_without_an_invitation_is_refused_uniformly(env):
    r = _flow(env)
    assert r.status_code == 403
    err = r.json()["error"]
    assert {"code": err["code"], "message": err["message"]} == REFUSAL
    assert _users(env, "new@example.com") == 0
    assert "ask4mo_session" not in r.headers.get("set-cookie", "")
    # every transaction cookie is spent on the failure (state, next, pkce, invite)
    spent = r.headers.get("set-cookie", "")
    assert "ask4mo_oidc_state" in spent and "ask4mo_oidc_pkce" in spent


def test_new_google_account_with_a_valid_invitation_is_created_and_the_code_is_consumed(env):
    code, view = env.issue()
    r = _flow(env, code=code)
    assert r.status_code == 303 and "ask4mo_session" in r.headers.get("set-cookie", "")
    uid = env.accounts.find_by_email("new@example.com").user_id
    row = env.row(view.id)
    assert row.redeemed_by_user_id == uid and row.redeemed_at is not None
    types = [e.event_type for e in env.audit_rows()]
    assert "account.invitation_redeemed" in types and "account.oidc_login" in types
    assert code not in env.audit_blob() and code not in full_database_text(env)
    # replay: a different Google identity cannot reuse it
    r2 = _flow(env, code=code, identity=_identity(sub="g-other", email="other@example.com"))
    assert r2.status_code == 403 and _users(env, "other@example.com") == 0


@pytest.mark.parametrize("kind", ["unknown", "expired", "revoked"])
def test_unusable_codes_are_refused_with_the_same_response(env, kind):
    code = R.new_code()
    if kind != "unknown":
        code, view = env.issue()
        if kind == "expired":
            env.expire(view.id)
        else:
            env.invites.revoke(view.id, actor_user_id=None)
    r = _flow(env, code=code)
    assert r.status_code == 403 and r.json()["error"]["code"] == "invitation_required" and r.json()["error"]["message"] == REFUSAL["message"]
    assert _users(env, "new@example.com") == 0
    reasons = [e.context["reason"] for e in env.audit_rows() if e.event_type == "account.invitation_refused"]
    assert reasons == [{"unknown": "invalid"}.get(kind, kind)]
    assert [e.context["channel"] for e in env.audit_rows() if e.event_type == "account.invitation_refused"] == ["oidc"]


def test_existing_google_identity_signs_in_without_an_invitation(env):
    code, _ = env.issue()
    assert _flow(env, code=code).status_code == 303                          # registers
    r = _flow(env)                                                           # signs in again, no code
    assert r.status_code == 303 and "ask4mo_session" in r.headers.get("set-cookie", "")
    assert _users(env, "new@example.com") == 1


def test_linking_a_google_identity_to_an_existing_verified_account_needs_no_invitation(env):
    env.make_user(email="linked@example.com")                                # a verified password account that predates the beta gate
    r = _flow(env, identity=_identity(sub="g-link", email="linked@example.com"))
    assert r.status_code == 303                                              # not a registration, so no invitation is asked for
    assert _users(env, "linked@example.com") == 1


def test_email_bound_invitation_needs_the_provider_verified_matching_address(env):
    code, view = env.issue(email="bound@example.com")
    assert _flow(env, code=code, identity=_identity(sub="g-a", email="wrong@example.com")).status_code == 403
    assert _flow(env, code=code, identity=_identity(sub="g-b", email="bound@example.com", verified=False)).status_code == 403
    assert env.row(view.id).redeemed_at is None                              # neither attempt consumed it
    assert _flow(env, code=code, identity=_identity(sub="g-c", email="Bound@Example.com")).status_code == 303
    assert env.row(view.id).redeemed_at is not None


def test_the_code_travels_in_a_header_and_an_http_only_cookie_never_the_url(env):
    code, _ = env.issue()
    env.c.cookies.clear()
    start = env.c.get(START, headers={"X-Invitation-Code": code})
    assert code not in start.json()["authorization_url"]
    cookie = [h for h in start.headers.get_list("set-cookie") if "ask4mo_oidc_invite" in h][0]
    assert "HttpOnly" in cookie and "Max-Age=600" in cookie
    # no header: no cookie
    env.c.cookies.clear()
    assert not any("ask4mo_oidc_invite" in h for h in env.c.get(START).headers.get_list("set-cookie"))


def test_oidc_invitation_attempts_share_the_bounded_rate_limit(env):
    statuses = []
    for i in range(14):
        statuses.append(_flow(env, code=R.new_code(), identity=_identity(sub=f"g{i}", email=f"g{i}@example.com")).status_code)
    assert statuses[:10] == [403] * 10 and set(statuses[10:]) == {429}


def test_requirement_off_locally_leaves_google_registration_unchanged(monkeypatch):
    monkeypatch.delenv(policy.OVERRIDE_ENV_VAR, raising=False)
    e = Env("test")
    e.app.dependency_overrides[deps.get_oidc_provider] = lambda: _FakeGoogle(_identity(sub="g-dev", email="dev@example.com"))
    try:
        e.c.get(START)
        r = e.c.get(CALLBACK, params={"code": "abc", "state": e.c.cookies.get("ask4mo_oidc_state")}, follow_redirects=False)
        assert r.status_code == 303 and e.set_user_count("dev@example.com") == 1
    finally:
        e.close()


def test_a_refused_oidc_registration_leaves_no_user_row_behind(env):
    before = len(env.sf().scalars(select(User)).all())
    _flow(env, code=R.new_code())
    assert len(env.sf().scalars(select(User)).all()) == before
