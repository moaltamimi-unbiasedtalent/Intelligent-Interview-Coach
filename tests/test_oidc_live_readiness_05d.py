"""05D: Google sign-in fails closed by default and refuses every bad callback with the fake provider. No network. Live Google validation is NOT RUN."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from src.api import dependencies as deps
from src.application.oidc import GoogleOidcProvider, OidcError, OidcIdentity, google_enabled, oidc_status
from src.persistence import AuthSession, User
from tests._auth_factories import build_auth_app
from tests.test_auth_oidc import _FakeGoogle

START, CALLBACK = "/api/v1/auth/oidc/google/start", "/api/v1/auth/oidc/google/callback"


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for k in ("FEATURE_GOOGLE_LOGIN", "GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "OIDC_REDIRECT_URI"):
        monkeypatch.delenv(k, raising=False)


# ---- the disable path is the default ---------------------------------------------------------------------------------------
def test_nothing_configured_is_disabled_with_a_reason_and_never_live_validated():
    st = oidc_status()
    assert st == {"enabled": False, "reason": "flag_off", "client_id_set": False, "client_secret_set": False, "live_validated": False}
    assert google_enabled() is False


def test_credentials_without_the_flag_stay_disabled_the_explicit_disable_path(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "id.apps.example")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "secret-value")
    assert oidc_status()["reason"] == "flag_off" and google_enabled() is False
    monkeypatch.setenv("FEATURE_GOOGLE_LOGIN", "false")
    assert google_enabled() is False


@pytest.mark.parametrize("cid,sec,reason", [("", "s", "client_id_missing"), ("i", "", "client_secret_missing"), ("", "", "client_id_missing"), (" ", "s", "client_id_missing")])
def test_flag_on_with_incomplete_client_settings_is_disabled(monkeypatch, cid, sec, reason):
    monkeypatch.setenv("FEATURE_GOOGLE_LOGIN", "true")
    monkeypatch.setenv("GOOGLE_CLIENT_ID", cid)
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", sec)
    assert oidc_status()["reason"] == reason and google_enabled() is False


def test_flag_and_both_settings_enable_it_and_status_never_contains_a_value(monkeypatch):
    monkeypatch.setenv("FEATURE_GOOGLE_LOGIN", "true")
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "id.apps.example")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "secret-value-XYZ")
    st = oidc_status()
    assert st["enabled"] is True and st["reason"] == "enabled" and st["live_validated"] is False
    assert "secret-value-XYZ" not in str(st) and "id.apps.example" not in str(st)


def test_the_real_dependency_builds_no_provider_when_disabled_and_routes_answer_404_without_cookies():
    app, repo, _ = build_auth_app()
    c = TestClient(app)
    c.__enter__()
    assert deps.get_oidc_provider(None) is None
    r = c.get(START)
    assert r.status_code == 404 and "set-cookie" not in r.headers
    assert c.get(CALLBACK, params={"code": "x", "state": "y"}).status_code == 404
    with repo.session_factory() as s:
        assert s.scalar(select(func.count()).select_from(User)) == 0


def test_the_provider_cannot_be_constructed_without_credentials():
    for cid, sec in (("", "s"), ("i", ""), ("", "")):
        with pytest.raises(OidcError):
            GoogleOidcProvider(client_id=cid, client_secret=sec)


# ---- hosted redirect trust -------------------------------------------------------------------------------------------------
def _hosted_app(provider, monkeypatch, redirect):
    app, repo, _ = build_auth_app(env="staging")
    app.dependency_overrides[deps.get_oidc_provider] = lambda: provider
    if redirect is not None:
        monkeypatch.setenv("OIDC_REDIRECT_URI", redirect)
    client = TestClient(app)
    client.__enter__()
    return client, repo


@pytest.mark.parametrize("redirect", [None, "", "http://api.example.test/api/v1/auth/oidc/google/callback", "https://api.example.test/other",
                                      "https://api.example.test/api/v1/auth/oidc/google/callback?x=1", "https://api.example.test/api/v1/auth/oidc/google/callback#f"])
def test_hosted_start_refuses_without_a_trusted_configured_redirect_and_sets_no_cookie(monkeypatch, redirect):
    c, _ = _hosted_app(_FakeGoogle(), monkeypatch, redirect)
    r = c.get(START, headers={"host": "evil.example"})
    assert r.status_code == 503 and "set-cookie" not in r.headers


def test_hosted_start_with_the_trusted_redirect_ignores_a_spoofed_host(monkeypatch):
    seen = {}

    class Spy(_FakeGoogle):
        def authorization_url(self, *, state, redirect_uri, code_challenge=None):
            seen.update(redirect_uri=redirect_uri, challenge=code_challenge)
            return super().authorization_url(state=state, redirect_uri=redirect_uri, code_challenge=code_challenge)

    c, _ = _hosted_app(Spy(), monkeypatch, "https://api.example.test/api/v1/auth/oidc/google/callback")
    assert c.get(START, headers={"host": "evil.example"}).status_code == 200
    assert seen["redirect_uri"] == "https://api.example.test/api/v1/auth/oidc/google/callback" and seen["challenge"]


# ---- every callback refusal, with the existing fake provider ------------------------------------------------------------------
class _Env:
    def __init__(self, provider=None, env="test"):
        self.app, self.repo, _ = build_auth_app(env=env)
        self.provider = provider or _FakeGoogle(OidcIdentity("google", "g-1", "refuse@example.com", True, "R"))
        self.app.dependency_overrides[deps.get_oidc_provider] = lambda: self.provider
        self.c = TestClient(self.app)
        self.c.__enter__()

    def start(self):
        self.c.cookies.clear()
        assert self.c.get(START).status_code == 200
        jar = {k: v for k, v in self.c.cookies.items()}
        self.c.cookies.clear()                  # the test supplies cookies explicitly, so a removed one is really absent
        return jar

    def counts(self):
        with self.repo.session_factory() as s:
            return s.scalar(select(func.count()).select_from(User)), s.scalar(select(func.count()).select_from(AuthSession))


def _assert_refused(r, env, status=400):
    assert r.status_code == status, r.text
    set_cookie = r.headers.get("set-cookie", "")
    assert "ask4mo_session" not in set_cookie or "ask4mo_session=;" in set_cookie
    for name in ("ask4mo_oidc_state", "ask4mo_oidc_pkce"):
        assert name in set_cookie                                           # the transaction is spent on EVERY failure
    assert env.counts() == (0, 0)


def test_state_mismatch_is_refused():
    e = _Env()
    jar = e.start()
    _assert_refused(e.c.get(CALLBACK, params={"code": "c", "state": "forged"}, cookies=jar), e)


def test_missing_state_parameter_is_refused():
    e = _Env()
    jar = e.start()
    _assert_refused(e.c.get(CALLBACK, params={"code": "c"}, cookies=jar), e)


def test_missing_state_cookie_is_refused_cross_site_forgery():
    e = _Env()
    jar = e.start()
    jar.pop("ask4mo_oidc_state")
    _assert_refused(e.c.get(CALLBACK, params={"code": "c", "state": "anything"}, cookies=jar), e)


def test_missing_pkce_verifier_cookie_never_redeems_the_code():
    redeemed = []

    class Spy(_FakeGoogle):
        def exchange(self, **kw):
            redeemed.append(kw)
            return super().exchange(**kw)

    e = _Env(Spy())
    jar = e.start()
    state = jar["ask4mo_oidc_state"]
    jar.pop("ask4mo_oidc_pkce")
    _assert_refused(e.c.get(CALLBACK, params={"code": "c", "state": state}, cookies=jar), e)
    assert redeemed == []


def test_provider_error_with_no_code_is_refused_without_redeeming():
    e = _Env()
    jar = e.start()
    _assert_refused(e.c.get(CALLBACK, params={"state": jar["ask4mo_oidc_state"], "error": "access_denied"}, cookies=jar), e)


def test_exchange_failure_covering_pkce_id_token_and_userinfo_problems_is_a_generic_refusal():
    e = _Env(_FakeGoogle(fail=True))
    jar = e.start()
    r = e.c.get(CALLBACK, params={"code": "c", "state": jar["ask4mo_oidc_state"]}, cookies=jar)
    _assert_refused(r, e)
    assert "Google sign-in failed" in r.text and "ya29" not in r.text


def test_the_pkce_verifier_reaches_the_provider_and_the_challenge_is_what_start_sent():
    from src.application.oidc import pkce_challenge

    seen = {}

    class Spy(_FakeGoogle):
        def authorization_url(self, *, state, redirect_uri, code_challenge=None):
            seen["challenge"] = code_challenge
            return super().authorization_url(state=state, redirect_uri=redirect_uri, code_challenge=code_challenge)

        def exchange(self, *, code, redirect_uri, code_verifier=None):
            seen["verifier"] = code_verifier
            return super().exchange(code=code, redirect_uri=redirect_uri, code_verifier=code_verifier)

    e = _Env(Spy())
    jar = e.start()
    assert e.c.get(CALLBACK, params={"code": "c", "state": jar["ask4mo_oidc_state"]}, cookies=jar, follow_redirects=False).status_code == 303
    assert seen["verifier"] and pkce_challenge(seen["verifier"]) == seen["challenge"]


def test_a_spent_transaction_cannot_be_replayed():
    e = _Env()
    jar = e.start()
    first = e.c.get(CALLBACK, params={"code": "c", "state": jar["ask4mo_oidc_state"]}, cookies=jar, follow_redirects=False)
    assert first.status_code == 303
    replay = e.c.get(CALLBACK, params={"code": "c", "state": jar["ask4mo_oidc_state"]}, follow_redirects=False)          # cookies were deleted by the response
    assert replay.status_code == 400


def test_unverified_google_email_never_links_to_an_existing_account():
    from src.auth_repository import AccountRepository
    from src.authsec import passwords

    e = _Env(_FakeGoogle(OidcIdentity("google", "g-evil", "victim@example.com", False, "X")))
    accounts = AccountRepository(e.repo.session_factory)
    victim = accounts.create_password_account(email="victim@example.com", password_hash=passwords.hash_password("correcthorsebattery"), display_name=None)
    accounts.mark_email_verified(victim)
    jar = e.start()
    r = e.c.get(CALLBACK, params={"code": "c", "state": jar["ask4mo_oidc_state"]}, cookies=jar, follow_redirects=False)
    with e.repo.session_factory() as s:
        users = s.scalars(select(User).where(User.email == "victim@example.com")).all()
        owner_ids = {u.id for u in users}
    assert victim in owner_ids
    from src.persistence import AccountIdentity
    with e.repo.session_factory() as s:
        linked = s.scalars(select(AccountIdentity).where(AccountIdentity.provider_subject == "g-evil")).all()
    assert all(i.user_id != victim for i in linked) and r.status_code in (303, 400, 403, 409)
