"""W12.4C OIDC correction: ID-token validation (OpenID Connect Core 3.1.3.7), UserInfo subject matching (5.3.2), PKCE S256 (RFC 7636 / RFC 9700
2.1.1), a trusted configured redirect URI, strict email_verified booleans, and the account pre-hijack regression. The REAL ``GoogleOidcProvider`` runs
against a mock Google (httpx MockTransport) that enforces the authorization-code and PKCE rules itself. No real Google call is possible: the socket
layer is blocked for anything that is not loopback."""

from __future__ import annotations

import base64
import hashlib
import json
import urllib.parse

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from src.api import dependencies as deps
from src.application.oidc import (
    GoogleOidcProvider, OidcError, new_pkce_verifier, pkce_challenge, validate_id_token,
)
from src.persistence import User
from tests._auth_factories import account_repo, build_auth_app, login_token, register

API = "/api/v1"
CID, CSEC = "client-id-123.apps.example", "client-secret-DO_NOT_LEAK_OIDC"
NOW = 1_800_000_000.0
CB = "https://api.example.test/api/v1/auth/oidc/google/callback"


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    import socket
    real = socket.socket.connect

    def guard(self, addr, *a, **k):
        host = addr[0] if isinstance(addr, tuple) else str(addr)
        if host not in ("127.0.0.1", "::1", "localhost") and not str(host).startswith("/"):
            raise AssertionError(f"outbound network attempt to {host}")
        return real(self, addr, *a, **k)
    monkeypatch.setattr(socket.socket, "connect", guard)
    monkeypatch.delenv("OIDC_REDIRECT_URI", raising=False)


def b64(obj) -> str:
    return base64.urlsafe_b64encode(json.dumps(obj).encode()).rstrip(b"=").decode()


def jwt(claims: dict | None = None, header: dict | None = None, **over) -> str:
    base = {"iss": "https://accounts.google.com", "aud": CID, "azp": CID, "sub": "g-sub-1", "email": "owner@example.test", "email_verified": True,
            "iat": NOW - 10, "exp": NOW + 3000}
    base.update(claims or {})
    base.update(over)
    for k in [k for k, v in base.items() if v is None]:
        del base[k]
    return f"{b64(header or {'alg': 'RS256', 'typ': 'JWT', 'kid': 'k1'})}.{b64(base)}.c2ln"


# ---------------- PKCE primitives ------------------------------------------------------------------------------------

def test_pkce_s256_matches_the_rfc_7636_test_vector_and_verifiers_are_fresh_and_in_range():
    assert pkce_challenge("dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk") == "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"
    vs = {new_pkce_verifier() for _ in range(50)}
    assert len(vs) == 50 and all(43 <= len(v) <= 128 and v.replace("-", "").replace("_", "").isalnum() for v in vs)


# ---------------- ID token validation (unit) ---------------------------------------------------------------------------

def v(token, **kw):
    return validate_id_token(token, client_id=CID, now=NOW, **kw)


def test_a_valid_id_token_returns_its_claims_and_both_documented_issuers_are_accepted():
    assert v(jwt())["sub"] == "g-sub-1"
    assert v(jwt(iss="accounts.google.com"))["sub"] == "g-sub-1"
    assert v(jwt(aud=[CID, "other"], azp=CID))["sub"] == "g-sub-1"
    assert v(jwt(exp=NOW - 30))["sub"] == "g-sub-1"                              # inside the 60 s clock skew


@pytest.mark.parametrize("token", [
    jwt(iss="https://evil.example"), jwt(iss="https://accounts.google.com.evil.test"), jwt(iss=None),
    jwt(aud="someone-else"), jwt(aud=None), jwt(aud=[CID, "other"], azp=None), jwt(azp="other-client"), jwt(aud=123),
    jwt(exp=NOW - 61), jwt(exp=None), jwt(exp="soon"), jwt(exp=True),
    jwt(iat=NOW + 120), jwt(iat=NOW - 86_401), jwt(iat=None),
    jwt(sub=None), jwt(sub=""), jwt(sub="x" * 256), jwt(sub=12345),
    jwt(email_verified="false"), jwt(email_verified="true"), jwt(email_verified=1), jwt(email=["a@b.co"]),
    jwt(header={"alg": "none"}), jwt(header={"alg": "HS256"}), jwt(header={"alg": "RS512"}), jwt(header={"typ": "JWT"}),
    None, 123, "", "abc", "a.b", "a.b.c.d", "!!!.???.***", f"{b64(['not', 'an', 'object'])}.{b64({})}.sig", f"{b64({'alg': 'RS256'})}.{b64([1])}.sig",
    f"{b64({'alg': 'RS256'})}.bm90LWpzb24.sig",
])
def test_invalid_id_tokens_are_refused(token):
    with pytest.raises(OidcError):
        v(token)


def test_at_hash_is_checked_when_present():
    access = "ya29.access-token-value"
    digest = hashlib.sha256(access.encode()).digest()
    good = base64.urlsafe_b64encode(digest[:16]).rstrip(b"=").decode()
    assert v(jwt(at_hash=good), access_token=access)["sub"] == "g-sub-1"
    with pytest.raises(OidcError):
        v(jwt(at_hash="wrong"), access_token=access)


# ---------------- the real provider against a mock Google --------------------------------------------------------------

class Google:
    """Enforces the authorization-code + PKCE rules a real Google enforces, and records every request."""

    def __init__(self, *, id_claims=None, id_token=None, userinfo=None, token_status=200, userinfo_status=200, id_header=None):
        self.requests: list[httpx.Request] = []
        self.codes: dict[str, str] = {}          # code -> the S256 challenge it was issued under
        self.id_claims, self.id_token, self.id_header = id_claims or {}, id_token, id_header
        self.userinfo = userinfo if userinfo is not None else {"sub": "g-sub-1", "email": "owner@example.test", "email_verified": True, "name": "Owner"}
        self.token_status, self.userinfo_status = token_status, userinfo_status
        self.transport = httpx.MockTransport(self._handle)

    def issue_code(self, authorization_url: str) -> str:
        q = urllib.parse.parse_qs(urllib.parse.urlparse(authorization_url).query)
        assert q["code_challenge_method"] == ["S256"] and q["client_id"] == [CID] and q["response_type"] == ["code"]
        code = f"code-{len(self.codes)}"
        self.codes[code] = q["code_challenge"][0]
        return code

    def _handle(self, req: httpx.Request) -> httpx.Response:
        self.requests.append(req)
        if req.url.host == "oauth2.googleapis.com":
            form = dict(urllib.parse.parse_qsl(req.content.decode()))
            challenge = self.codes.get(form.get("code", ""))
            if self.token_status != 200 or challenge is None or form.get("client_secret") != CSEC or form.get("client_id") != CID:
                return httpx.Response(400, json={"error": "invalid_grant"})
            if pkce_challenge(form.get("code_verifier", "x")) != challenge:        # PKCE enforced by the (mock) authorization server
                return httpx.Response(400, json={"error": "invalid_grant", "error_description": "PKCE verification failed"})
            self.codes.pop(form["code"])                                            # single use
            tok = self.id_token if self.id_token is not None else jwt(self.id_claims, self.id_header)
            return httpx.Response(200, json={"access_token": "ya29.access", "id_token": tok, "token_type": "Bearer", "expires_in": 3599})
        if req.url.host == "openidconnect.googleapis.com":
            return httpx.Response(self.userinfo_status, json=self.userinfo)
        return httpx.Response(500)


def provider(g: Google) -> GoogleOidcProvider:
    return GoogleOidcProvider(client_id=CID, client_secret=CSEC, transport=g.transport, clock=lambda: NOW)


def login(g: Google, p: GoogleOidcProvider, verifier=None):
    verifier = verifier or new_pkce_verifier()
    url = p.authorization_url(state="s", redirect_uri=CB, code_challenge=pkce_challenge(verifier))
    return p.exchange(code=g.issue_code(url), redirect_uri=CB, code_verifier=verifier)


def test_valid_login_sends_pkce_secret_and_redirect_over_the_token_call_and_returns_the_validated_identity():
    g = Google()
    ident = login(g, provider(g))
    assert (ident.provider, ident.subject, ident.email, ident.email_verified, ident.display_name) == ("google", "g-sub-1", "owner@example.test", True, "Owner")
    token_req = next(r for r in g.requests if r.url.host == "oauth2.googleapis.com")
    form = dict(urllib.parse.parse_qsl(token_req.content.decode()))
    assert form["grant_type"] == "authorization_code" and form["redirect_uri"] == CB and "code_verifier" in form and form["client_secret"] == CSEC
    assert token_req.url.scheme == "https" and token_req.method == "POST"
    info_req = next(r for r in g.requests if r.url.host == "openidconnect.googleapis.com")
    assert info_req.headers["authorization"] == "Bearer ya29.access"


def test_authorization_url_carries_an_s256_challenge_and_never_the_verifier():
    g = Google()
    verifier = new_pkce_verifier()
    url = provider(g).authorization_url(state="s", redirect_uri=CB, code_challenge=pkce_challenge(verifier))
    q = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
    assert q["code_challenge"] == [pkce_challenge(verifier)] and q["code_challenge_method"] == ["S256"] and verifier not in url and CSEC not in url


@pytest.mark.parametrize("name,g", [
    ("wrong issuer", Google(id_claims={"iss": "https://evil.example"})),
    ("wrong audience", Google(id_claims={"aud": "another-client"})),
    ("expired", Google(id_claims={"exp": NOW - 3600})),
    ("not a jwt", Google(id_token="not-a-jwt")),
    ("alg none", Google(id_header={"alg": "none"})),
    ("missing id token", Google(id_token="")),
    ("userinfo subject mismatch", Google(userinfo={"sub": "someone-else", "email": "owner@example.test", "email_verified": True})),
    ("userinfo missing subject", Google(userinfo={"email": "owner@example.test", "email_verified": True})),
    ("userinfo email mismatch", Google(userinfo={"sub": "g-sub-1", "email": "attacker@example.test", "email_verified": True})),
    ("userinfo email_verified is a string", Google(userinfo={"sub": "g-sub-1", "email": "owner@example.test", "email_verified": "false"})),
    ("id token email_verified is a string", Google(id_claims={"email_verified": "false"})),
    ("userinfo not an object", Google(userinfo=["x"])),
    ("userinfo error", Google(userinfo_status=401)),
    ("token endpoint refuses", Google(token_status=400)),
])
def test_every_identity_problem_is_rejected_before_an_identity_exists(name, g):
    with pytest.raises(OidcError) as e:
        login(g, provider(g))
    assert CSEC not in str(e.value) and "ya29" not in str(e.value)


def test_conservative_email_verified_handling():
    g = Google(id_claims={"email_verified": False}, userinfo={"sub": "g-sub-1", "email": "owner@example.test", "email_verified": True})
    assert login(g, provider(g)).email_verified is False                      # the ID token says unverified
    g = Google(userinfo={"sub": "g-sub-1", "email": "owner@example.test", "email_verified": False})
    assert login(g, provider(g)).email_verified is False                      # UserInfo contradicts: the stricter value wins
    g = Google(id_claims={"email": None, "email_verified": None}, userinfo={"sub": "g-sub-1", "email": "owner@example.test", "email_verified": True})
    ident = login(g, provider(g))
    assert ident.email == "owner@example.test" and ident.email_verified is False   # no verified evidence in the ID token: never linked by email


def test_missing_or_wrong_pkce_verifier_never_yields_an_identity():
    g = Google()
    p = provider(g)
    url = p.authorization_url(state="s", redirect_uri=CB, code_challenge=pkce_challenge("the-real-verifier-" + "a" * 30))
    code = g.issue_code(url)
    with pytest.raises(OidcError):
        p.exchange(code=code, redirect_uri=CB, code_verifier=None)            # refused locally: no request is made
    assert not g.requests
    with pytest.raises(OidcError):
        p.exchange(code=code, redirect_uri=CB, code_verifier="a-different-verifier-" + "b" * 30)   # Google rejects the mismatch
    assert len(g.requests) == 1 and all(r.url.host != "openidconnect.googleapis.com" for r in g.requests)


# ---------------- through the HTTP routes ------------------------------------------------------------------------------

def world(g: Google, env="test"):
    app, repo, mail = build_auth_app(env=env)
    app.dependency_overrides[deps.get_oidc_provider] = lambda: provider(g)
    c = TestClient(app)
    c.__enter__()
    return app, repo, c


def start(c: TestClient, **kw):
    r = c.get(f"{API}/auth/oidc/google/start", **kw)
    assert r.status_code == 200
    return r.json()["authorization_url"], c.cookies.get("ask4mo_oidc_state"), c.cookies.get("ask4mo_oidc_pkce")


def users(repo) -> int:
    with repo.session_factory() as s:
        return s.scalar(select(func.count()).select_from(User))


def test_full_flow_start_sets_state_and_a_bound_verifier_and_callback_spends_every_cookie():
    g = Google()
    app, repo, c = world(g)
    try:
        url, state, verifier = start(c)
        assert verifier and verifier not in url and pkce_challenge(verifier) in url
        r = c.get(f"{API}/auth/oidc/google/callback", params={"code": g.issue_code(url), "state": state}, follow_redirects=False)
        assert r.status_code == 303 and "ask4mo_session" in r.headers.get("set-cookie", "")
        assert not any(c.cookies.get(n) for n in ("ask4mo_oidc_state", "ask4mo_oidc_pkce", "ask4mo_oidc_next"))
        assert users(repo) == 1
        assert CSEC not in r.text and "ya29" not in r.text and verifier not in r.text
    finally:
        c.__exit__(None, None, None)


def test_state_mismatch_never_reaches_google_and_spends_the_transaction():
    g = Google()
    app, repo, c = world(g)
    try:
        url, state, _ = start(c)
        r = c.get(f"{API}/auth/oidc/google/callback", params={"code": g.issue_code(url), "state": "forged"}, follow_redirects=False)
        assert r.status_code == 400 and not g.requests and users(repo) == 0
        assert not c.cookies.get("ask4mo_oidc_state") and not c.cookies.get("ask4mo_oidc_pkce")
        assert c.get(f"{API}/auth/oidc/google/callback", params={"code": "x", "state": state}, follow_redirects=False).status_code == 400   # replay of the spent state
    finally:
        c.__exit__(None, None, None)


def test_a_callback_without_the_pkce_cookie_never_redeems_the_code():
    g = Google()
    app, repo, c = world(g)
    try:
        url, state, _ = start(c)
        c.cookies.delete("ask4mo_oidc_pkce")
        r = c.get(f"{API}/auth/oidc/google/callback", params={"code": g.issue_code(url), "state": state}, follow_redirects=False)
        assert r.status_code == 400 and not g.requests and users(repo) == 0
    finally:
        c.__exit__(None, None, None)


def test_code_injection_is_blocked_by_pkce_a_code_issued_for_another_browser_does_not_log_the_victim_in():
    g = Google()
    app, repo, attacker = world(g)
    try:
        attacker_url, _, _ = start(attacker)
        stolen_code = g.issue_code(attacker_url)                               # the attacker's own authorization, under the attacker's challenge
        victim = TestClient(app)
        victim.__enter__()
        _, victim_state, _ = start(victim)                                      # the victim's browser holds a DIFFERENT verifier
        r = victim.get(f"{API}/auth/oidc/google/callback", params={"code": stolen_code, "state": victim_state}, follow_redirects=False)
        assert r.status_code == 400 and "ask4mo_session" not in r.headers.get("set-cookie", "") and users(repo) == 0
        victim.__exit__(None, None, None)
    finally:
        attacker.__exit__(None, None, None)


@pytest.mark.parametrize("g", [Google(id_claims={"iss": "https://evil.example"}), Google(id_claims={"aud": "x"}), Google(id_claims={"exp": NOW - 3600}),
                               Google(userinfo={"sub": "other", "email": "owner@example.test", "email_verified": True}),
                               Google(userinfo={"sub": "g-sub-1", "email": "owner@example.test", "email_verified": "false"})])
def test_identity_problems_create_and_link_nothing_and_set_no_session(g):
    app, repo, c = world(g)
    try:
        register(c, "owner@example.test", "correcthorsebattery")
        before = users(repo)
        url, state, _ = start(c)
        r = c.get(f"{API}/auth/oidc/google/callback", params={"code": g.issue_code(url), "state": state}, follow_redirects=False)
        assert r.status_code == 400 and "ask4mo_session" not in r.headers.get("set-cookie", "") and users(repo) == before
        acct = account_repo(repo).find_by_email("owner@example.test")
        assert "google" not in acct.providers
    finally:
        c.__exit__(None, None, None)


def test_pre_hijack_regression_through_the_full_flow():
    g = Google()
    app, repo, c = world(g)
    try:
        assert c.post(f"{API}/auth/register", json={"email": "owner@example.test", "password": "attacker-chosen-pass-01"}).status_code == 201
        attacker_session = login_token(c, "owner@example.test", "attacker-chosen-pass-01")
        url, state, _ = start(c)
        assert c.get(f"{API}/auth/oidc/google/callback", params={"code": g.issue_code(url), "state": state}, follow_redirects=False).status_code == 303
        assert login_token(c, "owner@example.test", "attacker-chosen-pass-01") is None
        assert c.get(f"{API}/auth/me", cookies={"ask4mo_session": attacker_session}).status_code == 401
        acct = account_repo(repo).find_by_email("owner@example.test")
        assert acct.email_verified is True and acct.has_password is False and "google" in acct.providers
    finally:
        c.__exit__(None, None, None)


# ---------------- redirect URI: a configured trusted origin, never the request Host ------------------------------------

def test_a_configured_redirect_uri_is_used_and_a_hostile_host_header_changes_nothing(monkeypatch):
    monkeypatch.setenv("OIDC_REDIRECT_URI", CB)
    g = Google()
    app, repo, c = world(g)
    try:
        url, state, _ = start(c, headers={"Host": "evil.attacker.test", "X-Forwarded-Host": "evil.attacker.test"})
        assert urllib.parse.parse_qs(urllib.parse.urlparse(url).query)["redirect_uri"] == [CB]
        c.get(f"{API}/auth/oidc/google/callback", params={"code": g.issue_code(url), "state": state}, headers={"Host": "evil.attacker.test"}, follow_redirects=False)
        token_req = next(r for r in g.requests if r.url.host == "oauth2.googleapis.com")
        assert dict(urllib.parse.parse_qsl(token_req.content.decode()))["redirect_uri"] == CB
    finally:
        c.__exit__(None, None, None)


@pytest.mark.parametrize("bad", ["http://api.example.test/api/v1/auth/oidc/google/callback", "https://api.example.test/other", "https://api.example.test/api/v1/auth/oidc/google/callback?x=1",
                                 "javascript:alert(1)"])
def test_an_invalid_configured_redirect_uri_refuses_to_start(monkeypatch, bad):
    monkeypatch.setenv("OIDC_REDIRECT_URI", bad)
    app, repo, c = world(Google())
    try:
        assert c.get(f"{API}/auth/oidc/google/start").status_code == 503
    finally:
        c.__exit__(None, None, None)


def test_a_hosted_environment_without_a_configured_redirect_uri_never_falls_back_to_the_host_header():
    app, repo, c = world(Google(), env="production")
    try:
        assert c.get(f"{API}/auth/oidc/google/start", headers={"Host": "evil.attacker.test"}).status_code == 503
    finally:
        c.__exit__(None, None, None)


def test_production_validation_requires_the_trusted_redirect_uri_when_google_login_is_on(monkeypatch):
    from src.api.env_validation import validate_runtime_config
    monkeypatch.setenv("FEATURE_GOOGLE_LOGIN", "true")
    assert any("OIDC_REDIRECT_URI" in c for c in validate_runtime_config("production").critical)
    monkeypatch.setenv("OIDC_REDIRECT_URI", CB)
    assert not any("OIDC_REDIRECT_URI" in c for c in validate_runtime_config("production").critical)


# ---------------- strict booleans at the linking layer -------------------------------------------------------------------

@pytest.mark.parametrize("truthy", ["false", "true", 1, "yes"])
def test_only_a_real_boolean_true_can_link_by_email(truthy):
    app, repo, mail = build_auth_app()
    acc = account_repo(repo)
    with TestClient(app) as c:
        register(c, "owner@example.test", "correcthorsebattery")
        existing = acc.find_by_email("owner@example.test").user_id
        got = acc.link_or_create_oidc(provider="google", provider_subject="g-x", email="owner@example.test", email_verified=truthy, display_name=None)
        assert got != existing and "google" not in acc.find_by_email("owner@example.test").providers
