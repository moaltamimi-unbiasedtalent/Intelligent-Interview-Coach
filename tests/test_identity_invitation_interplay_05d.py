"""05D: the identity flows (verification, recovery, password registration, Google new account) under the merged 04E invitation-only rule, path by path.

Hosted environment (``staging``): an invitation is ALWAYS required to CREATE an account, never to sign in, verify, recover or link. A refused registration sends NO
mail and creates NO row; recovery and verification never create an account, never reveal whether one exists, and never need a code. Fake mail and fake Google only."""

from __future__ import annotations

import pytest
from sqlalchemy import func, select

from src.api import dependencies as deps
from src.application.oidc import OidcIdentity
from src.persistence import AuthToken, User
from tests._auth_factories import verification_token, reset_token
from tests._invitations_04e import API, PW, REFUSAL, Env, refusal_body
from tests.test_auth_oidc import _FakeGoogle

START, CALLBACK = f"{API}/auth/oidc/google/start", f"{API}/auth/oidc/google/callback"


@pytest.fixture()
def env():
    e = Env("staging")
    yield e
    e.close()


def _users(e: Env) -> int:
    with e.sf() as s:
        return s.scalar(select(func.count()).select_from(User)) or 0


def _tokens(e: Env) -> int:
    with e.sf() as s:
        return s.scalar(select(func.count()).select_from(AuthToken)) or 0


# ---- registration -> verification ------------------------------------------------------------------------------------------
def test_uninvited_registration_sends_no_verification_mail_and_creates_no_token_or_user(env):
    r = env.register("nobody@example.com")
    assert r.status_code == 403 and refusal_body(r) == REFUSAL
    assert env.mail.sent == [] and _users(env) == 0 and _tokens(env) == 0


@pytest.mark.parametrize("kind", ["unknown", "expired", "revoked", "wrong_email"])
def test_unusable_invitation_registration_sends_no_mail_and_creates_nothing(env, kind):
    from src.invitations import repository as R

    code = R.new_code()
    if kind != "unknown":
        code, view = env.issue(email="bound@example.com" if kind == "wrong_email" else None)
        if kind == "expired":
            env.expire(view.id)
        if kind == "revoked":
            env.invites.revoke(view.id, actor_user_id=None)
    r = env.register("nobody@example.com", code)
    assert r.status_code == 403 and refusal_body(r) == REFUSAL
    assert env.mail.sent == [] and _users(env) == 0 and _tokens(env) == 0


def test_invited_registration_sends_exactly_one_verification_mail_without_the_code_and_the_link_verifies(env):
    code, _ = env.issue()
    assert env.register("invited@example.com", code).status_code == 201
    assert [m.category for m in env.mail.sent] == ["email_verification"]
    msg = env.mail.sent[0]
    assert code not in msg.body and code not in msg.subject and msg.to == "invited@example.com"
    token = verification_token(env.mail)
    assert token and env.c.post(f"{API}/auth/verify-email", json={"token": token}).status_code == 200
    assert env.c.post(f"{API}/auth/verify-email", json={"token": token}).status_code == 400            # single use
    assert env.accounts.find_by_email("invited@example.com").email_verified is True


def test_verification_resend_for_an_existing_account_needs_no_invitation(env):
    from src.authsec import passwords

    uid = env.accounts.create_password_account(email="old@example.com", password_hash=passwords.hash_password(PW), display_name=None)
    from tests._auth_factories import cookies_for, login_token

    tok = login_token(env.c, "old@example.com", PW)
    assert tok
    r = env.c.post(f"{API}/auth/verify-email/resend", cookies=cookies_for(tok))
    assert r.status_code == 200 and any(m.category == "email_verification" for m in env.mail.sent) and uid


def test_verification_tokens_cannot_be_used_to_create_an_account_and_unknown_tokens_create_nothing(env):
    assert env.c.post(f"{API}/auth/verify-email", json={"token": "not-a-real-token"}).status_code == 400
    assert _users(env) == 0 and _tokens(env) == 0


def test_a_valid_code_with_an_existing_email_sends_only_the_account_notice_to_the_owner(env):
    env.make_user(email="taken@example.com")
    before = len(env.mail.sent)
    code, _ = env.issue()
    assert env.register("taken@example.com", code).status_code == 201                  # uniform success shape
    new = env.mail.sent[before:]
    assert [(m.category, m.to) for m in new] == [("account_notice", "taken@example.com")] and env.set_user_count("taken@example.com") == 1


# ---- recovery -------------------------------------------------------------------------------------------------------------
def test_forgot_password_for_an_unknown_address_creates_no_account_sends_no_mail_and_is_uniform(env):
    env.make_user(email="known@example.com")
    before = len(env.mail.sent)
    unknown = env.c.post(f"{API}/auth/forgot-password", json={"email": "ghost@example.com"})
    known = env.c.post(f"{API}/auth/forgot-password", json={"email": "known@example.com"})
    assert unknown.status_code == known.status_code == 200 and unknown.json() == known.json()
    assert env.set_user_count("ghost@example.com") == 0
    assert [m.to for m in env.mail.sent[before:]] == ["known@example.com"]            # mail only to the real account, nothing to the stranger


def test_a_recovery_link_resets_the_password_without_any_invitation_and_revokes_sessions(env):
    from tests._auth_factories import cookies_for, login_token

    env.make_user(email="rec@example.com")
    old = login_token(env.c, "rec@example.com", PW)
    env.c.post(f"{API}/auth/forgot-password", json={"email": "rec@example.com"})
    token = reset_token(env.mail)
    assert token
    assert env.c.post(f"{API}/auth/reset-password", json={"token": token, "password": "another-long-password-1"}).status_code == 200
    assert env.c.get(f"{API}/auth/me", cookies=cookies_for(old)).status_code == 401
    assert login_token(env.c, "rec@example.com", "another-long-password-1")


def test_a_reset_token_never_creates_an_account_and_a_forged_one_changes_nothing(env):
    assert env.c.post(f"{API}/auth/reset-password", json={"token": "forged", "password": "another-long-password-1"}).status_code == 400
    assert _users(env) == 0


def test_recovery_does_not_consume_or_require_an_invitation(env):
    code, view = env.issue()
    env.make_user(email="x@example.com")
    env.c.post(f"{API}/auth/forgot-password", json={"email": "x@example.com"})
    assert env.row(view.id).redeemed_at is None


# ---- Google (OIDC) ----------------------------------------------------------------------------------------------------------
def _identity(sub="g-new", email="new@example.com", verified=True):
    return OidcIdentity(provider="google", subject=sub, email=email, email_verified=verified, display_name="N")


@pytest.fixture()
def goog(env):
    env.provider = _FakeGoogle(_identity())
    env.app.dependency_overrides[deps.get_oidc_provider] = lambda: env.provider
    import os
    os.environ["OIDC_REDIRECT_URI"] = "https://api.example.test/api/v1/auth/oidc/google/callback"
    yield env
    os.environ.pop("OIDC_REDIRECT_URI", None)


def _flow(e: Env, *, code=None, identity=None):
    if identity is not None:
        e.provider._identity = identity
    e.c.cookies.clear()
    r = e.c.get(START, headers={"X-Invitation-Code": code} if code else {})
    assert r.status_code == 200, r.text
    # staging sets Secure cookies the test client will not return over http: replay them explicitly
    jar = {c.name: c.value for c in e.c.cookies.jar}
    if "ask4mo_oidc_state" not in jar:
        for h in r.headers.get_list("set-cookie"):
            n, _, rest = h.partition("=")
            jar[n] = rest.split(";")[0]
    return e.c.get(CALLBACK, params={"code": "abc", "state": jar["ask4mo_oidc_state"]}, cookies=jar, follow_redirects=False)


def test_google_new_account_without_an_invitation_is_refused_in_a_hosted_environment_and_creates_nothing(goog):
    r = _flow(goog)
    assert r.status_code == 403 and refusal_body(r) == REFUSAL
    assert goog.set_user_count("new@example.com") == 0 and goog.mail.sent == []
    assert "ask4mo_session" not in r.headers.get("set-cookie", "") or "ask4mo_session=;" in r.headers.get("set-cookie", "")


@pytest.mark.parametrize("kind", ["unknown", "expired", "revoked"])
def test_google_new_account_with_an_unusable_code_is_refused_uniformly(goog, kind):
    from src.invitations import repository as R

    code = R.new_code()
    if kind != "unknown":
        code, view = goog.issue()
        if kind == "expired":
            goog.expire(view.id)
        else:
            goog.invites.revoke(view.id, actor_user_id=None)
    r = _flow(goog, code=code)
    assert r.status_code == 403 and refusal_body(r) == REFUSAL and goog.set_user_count("new@example.com") == 0


def test_google_new_account_with_a_valid_code_is_created_once_and_no_mail_is_sent(goog):
    code, view = goog.issue()
    r = _flow(goog, code=code)
    assert r.status_code == 303 and goog.set_user_count("new@example.com") == 1
    assert goog.row(view.id).redeemed_at is not None and goog.mail.sent == []                # Google proves the mailbox: no verification mail
    again = _flow(goog, code=code, identity=_identity(sub="g-other", email="other@example.com"))
    assert again.status_code == 403 and goog.set_user_count("other@example.com") == 0


def test_google_unverified_email_never_satisfies_an_email_bound_invitation(goog):
    code, view = goog.issue(email="new@example.com")
    r = _flow(goog, code=code, identity=_identity(verified=False))
    assert r.status_code == 403 and goog.set_user_count("new@example.com") == 0 and goog.row(view.id).redeemed_at is None


def test_google_sign_in_for_an_existing_identity_or_verified_account_needs_no_code(goog):
    goog.make_user(email="linked@example.com")
    r = _flow(goog, identity=_identity(sub="g-link", email="linked@example.com"))
    assert r.status_code == 303                                                                # links to the existing verified account
    r2 = _flow(goog, identity=_identity(sub="g-link", email="linked@example.com"))
    assert r2.status_code == 303                                                               # and signs in again as that identity
    assert goog.set_user_count("linked@example.com") == 1


def test_google_does_not_reach_the_account_creation_path_when_disabled(env):
    r = env.c.get(START)
    assert r.status_code == 404
    assert env.c.get(CALLBACK, params={"code": "abc", "state": "x"}).status_code == 404
    assert _users(env) == 0


def test_hosted_environment_requires_an_invitation_whatever_the_local_override_says(env, monkeypatch):
    from src.invitations.policy import invitation_required

    monkeypatch.setenv("REGISTRATION_INVITATION_REQUIRED", "false")
    assert invitation_required("staging") is True and invitation_required("production") is True and invitation_required("anything-else") is True
    assert env.register("nobody@example.com").status_code == 403
