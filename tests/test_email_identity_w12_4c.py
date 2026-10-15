"""W12.4C: email and identity operations. No real provider is contacted: Brevo is exercised through an httpx MockTransport, the database is
a temporary SQLite file and every secret below is a test value that must appear only in this file."""

from __future__ import annotations

import json
import logging
import re
import threading
from datetime import timedelta

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text

from src import integrations as I
from src import secret_store as SS
from src.api import dependencies as deps
from src.application import admin_audit as A
from src.application import admin_permissions as perm
from src.auth_repository import TokenRepository
from src.authsec import tokens
from src.mail import BrevoEmailSender, MemoryEmailSender, NotConfiguredEmailSender, build_email_sender
from src.mail.sender import ConsoleEmailSender
from src.mail.service import RETENTION_DAYS, EmailAttemptRepository, EmailService
from src.mail.templates import BRAND_LINE, render
from src.locales import SUPPORTED_LOCALE_CODES
from src.persistence import ACCOUNT_STATUS_DEACTIVATED, AuditEvent, AuthToken, EmailAttempt, utcnow
from tests._auth_factories import account_repo, build_auth_app, cookies_for, login_token

API = "/api/v1"
PW = "correct-horse-battery-0001"
NEW_PW = "an-entirely-new-passphrase-0002"
KEY_A = "env-brevo-key-AAAA-DO_NOT_LEAK_W12_04C"
KEY_B = "managed-brevo-key-BBBB-DO_NOT_LEAK_W12_04C"
ORIGIN = "https://app.example.test"
SENDER = "no-reply@example.test"


class Hub:
    """A fake Brevo: records every request and answers according to ``behavior``."""

    def __init__(self, behavior=None):
        self.requests: list[httpx.Request] = []
        self.behavior = behavior or (lambda req: httpx.Response(201, json={"messageId": "<mid-0001@brevo.test>"}))
        self.transport = httpx.MockTransport(self._handle)

    def _handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        out = self.behavior(request)
        if isinstance(out, Exception):
            raise out
        return out

    def sent(self) -> list[dict]:
        return [json.loads(r.content) for r in self.requests if r.url.path == "/v3/smtp/email"]

    def last_token(self) -> str:
        body = self.sent()[-1]["textContent"]
        return re.search(r"token=([A-Za-z0-9_\-%]+)", body).group(1)


def brevo(hub: Hub, key: str = KEY_A) -> BrevoEmailSender:
    return BrevoEmailSender(api_key=key, sender_email=SENDER, transport=hub.transport)


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    """Qualification makes ZERO outbound connections: anything that is not loopback fails the test loudly."""
    import socket
    real = socket.socket.connect

    def guard(self, addr, *a, **k):
        host = addr[0] if isinstance(addr, tuple) else str(addr)
        if host not in ("127.0.0.1", "::1", "localhost") and not str(host).startswith("/"):
            raise AssertionError(f"outbound network attempt to {host}")
        return real(self, addr, *a, **k)
    monkeypatch.setattr(socket.socket, "connect", guard)


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    for n in ("EMAIL_PROVIDER", "EMAIL_SENDER", "BREVO_API_KEY", "APP_BASE_URL", "API_ENV", "SECRET_STORE_BACKEND", "SECRET_STORE_MASTER_KEY"):
        monkeypatch.delenv(n, raising=False)
    monkeypatch.setenv("APP_BASE_URL", ORIGIN)
    SS.reset_secret_store_for_tests()
    yield
    SS.reset_secret_store_for_tests()


class World:
    def __init__(self, sender):
        self.app, self.repo, self.mail = build_auth_app()
        self.sender = sender
        self.app.dependency_overrides[deps.get_email_sender] = lambda: self.sender
        self.c = TestClient(self.app)
        self.c.__enter__()
        self.accounts = account_repo(self.repo)
        self.n = 0

    def close(self):
        self.c.__exit__(None, None, None)

    def user(self, role="user", locale=None):
        self.n += 1
        email = f"w{self.n}@example.test"
        body = {"email": email, "password": PW}
        if locale:
            body["locale"] = locale
        assert self.c.post(f"{API}/auth/register", json=body).status_code == 201
        tok = login_token(self.c, email, PW)
        uid = self.c.get(f"{API}/auth/me", cookies=cookies_for(tok)).json()["user_id"]
        if role != "user":
            self.accounts.set_platform_role(uid, role)
        return uid, email, cookies_for(tok)

    def attempts(self):
        with self.repo.session_factory() as s:
            return s.scalars(select(EmailAttempt).order_by(EmailAttempt.id)).all()

    def events(self, kind=None):
        from src.auth_repository import AuditRepository
        return AuditRepository(self.repo.session_factory).recent(limit=300, event_type=kind)


@pytest.fixture()
def hub():
    return Hub()


@pytest.fixture()
def w(hub):
    world = World(brevo(hub))
    yield world
    world.close()


# ---------------- the Brevo adapter: bounded categories, no retry, no raw text ---------------------------------------

@pytest.mark.parametrize("response,status,category", [
    (httpx.Response(201, json={"messageId": "<abc@brevo.test>"}), "provider_accepted", None),
    (httpx.Response(401, json={"message": "key not found"}), "failed", "provider_auth_failed"),
    (httpx.Response(403, json={}), "failed", "provider_auth_failed"),
    (httpx.Response(429, json={}), "failed", "rate_limited"),
    (httpx.Response(503, text="upstream exploded"), "failed", "provider_unavailable"),
    (httpx.Response(400, json={"message": "Sender is not valid"}), "failed", "invalid_sender"),
    (httpx.Response(400, json={"message": "recipient blocked"}), "failed", "message_rejected"),
    (httpx.ReadTimeout("sent, no reply"), "delivery_unknown", "delivery_unknown"),
    (httpx.ConnectTimeout("never connected"), "failed", "provider_timeout"),
    (httpx.ConnectError("refused"), "failed", "provider_unavailable"),
])
def test_brevo_outcomes_are_classified_without_retry_and_without_provider_text(response, status, category):
    hub = Hub(lambda req: response)
    result = brevo(hub).send_detailed(__import__("src.mail", fromlist=["EmailMessage"]).EmailMessage(
        to="a@example.test", subject="s", body="b", category="password_reset"))
    assert (result.status, result.failure_category) == (status, category)
    assert len(hub.requests) == 1                                    # never an automatic retry (a duplicate recovery email is worse than a failure)
    blob = repr(result)
    assert KEY_A not in blob and "exploded" not in blob and "not found" not in blob
    assert (result.provider_message_ref == "<abc@brevo.test>") is (status == "provider_accepted")
    assert result.accepted is (status == "provider_accepted")


def test_acceptance_is_not_delivery_the_states_have_no_delivered_or_bounced():
    from src.persistence import EMAIL_ATTEMPT_STATUSES
    assert "delivered" not in EMAIL_ATTEMPT_STATUSES and "bounced" not in EMAIL_ATTEMPT_STATUSES


def test_adapter_selection_never_prints_a_token_in_a_hosted_environment(monkeypatch):
    assert isinstance(build_email_sender(), ConsoleEmailSender)                 # development default (prints for a developer)
    monkeypatch.setenv("API_ENV", "production")
    assert isinstance(build_email_sender(), NotConfiguredEmailSender)           # hosted: nothing printed, reported honestly
    monkeypatch.setenv("EMAIL_PROVIDER", "brevo")
    assert isinstance(build_email_sender(), NotConfiguredEmailSender)           # provider chosen but no credential / sender
    monkeypatch.setenv("BREVO_API_KEY", KEY_A)
    monkeypatch.setenv("EMAIL_SENDER", "not an address")
    s = build_email_sender()
    assert isinstance(s, NotConfiguredEmailSender) and s.send_detailed(__import__("src.mail", fromlist=["EmailMessage"]).EmailMessage("a@b.co", "s", "b", "password_reset")).failure_category == "invalid_sender"
    monkeypatch.setenv("EMAIL_SENDER", SENDER)
    assert isinstance(build_email_sender(), BrevoEmailSender)
    for hostile in ("a@b.co\r\nBcc: x@y.z", "a@b.co, c@d.ef", "<a@b.co>"):
        monkeypatch.setenv("EMAIL_SENDER", hostile)
        assert isinstance(build_email_sender(), NotConfiguredEmailSender)


# ---------------- W12.4B credential resolution and the cached-client restart semantics -------------------------------

def test_managed_brevo_credential_beats_the_environment_then_falls_back_and_a_cached_client_needs_a_restart(tmp_path, monkeypatch):
    from src.persistence import init_db, make_engine, make_session_factory

    monkeypatch.setenv("EMAIL_PROVIDER", "brevo")
    monkeypatch.setenv("EMAIL_SENDER", SENDER)
    monkeypatch.setenv("BREVO_API_KEY", KEY_A)
    eng = make_engine(f"sqlite:///{tmp_path / 's.db'}")
    init_db(eng)
    sf = make_session_factory(eng)
    monkeypatch.setenv(SS.BACKEND_ENV, SS.BACKEND_ENCRYPTED)
    import base64
    monkeypatch.setenv(SS.MASTER_KEY_ENV, base64.b64encode(bytes(range(32))).decode())
    SS.reset_secret_store_for_tests()
    store = SS.bind_secret_store(sf)
    cached = build_email_sender()                                    # what a running process holds
    assert isinstance(cached, BrevoEmailSender) and cached._api_key == KEY_A
    svc = I.IntegrationService(sf, store)
    assert svc.email_sender_is_current(cached) is True
    store.set("BREVO_API_KEY", KEY_B)
    assert build_email_sender()._api_key == KEY_B                    # a NEW client resolves the managed value (managed > environment)
    assert cached._api_key == KEY_A                                  # the cached client still uses the old credential
    assert svc.email_sender_is_current(cached) is False              # -> Admin must say "restart required", not "rotated"
    store.remove("BREVO_API_KEY")
    assert build_email_sender()._api_key == KEY_A                    # removal restores the environment fallback
    assert svc.email_sender_is_current(cached) is True


# ---------------- templates: eight locales, safe, localised, brand line invariant -----------------------------------

def test_every_locale_renders_all_messages_with_the_brand_line_expiry_and_exact_link():
    link = f"{ORIGIN}/reset-password?token=abc_DEF-123"
    seen = set()
    for loc in SUPPORTED_LOCALE_CODES:
        for kind, secs in (("email_verification", 86400), ("password_reset", 3600)):
            r = render(kind, locale=loc, link=link, expires_in_seconds=secs)
            assert link in r.body and r.body.endswith(BRAND_LINE) and "{" not in r.body and "<" not in r.body and r.locale == loc
            assert re.search(r"\b(24|1)\b", r.body), (loc, kind)       # the real expiry number, not hard-coded prose
            seen.add(r.subject)
        for kind in ("account_notice", "admin_test"):
            r = render(kind, locale=loc)
            assert r.body.endswith(BRAND_LINE) and "http" not in r.body       # no link or token in a notice or a test message
    assert len(seen) >= 14                                                  # translated, not English copies
    assert render("password_reset", locale="xx", link=link, expires_in_seconds=3600).locale == "en"   # unsupported -> English
    assert render("password_reset", locale="ru", link=link, expires_in_seconds=3600).subject != render("password_reset", locale="en", link=link, expires_in_seconds=3600).subject


# ---------------- registration -> verification, end to end through the real service boundaries ----------------------

def test_registration_verification_journey_with_trusted_origin_single_use_and_clean_evidence(w, hub, caplog):
    caplog.set_level(logging.DEBUG)
    r = w.c.post(f"{API}/auth/register", json={"email": "Ann@Example.Test", "password": PW, "locale": "de"}, headers={"Host": "evil.attacker.test"})
    assert r.status_code == 201 and "verification link" in r.json()["message"]
    mail = hub.sent()
    assert len(mail) == 1 and mail[0]["to"] == [{"email": "ann@example.test"}] and mail[0]["sender"]["email"] == SENDER
    body = mail[0]["textContent"]
    assert mail[0]["subject"].startswith("Bestätige") and body.endswith(BRAND_LINE)       # the recipient's chosen language
    link = re.search(r"https?://\S+", body).group(0)
    assert link.startswith(f"{ORIGIN}/verify-email?token=") and "evil.attacker" not in body    # trusted configured origin, never the Host header
    token = hub.last_token()
    tok = login_token(w.c, "ann@example.test", PW)
    assert w.c.get(f"{API}/auth/me", cookies=cookies_for(tok)).json()["email_verified"] is False   # accepted != verified
    assert w.c.post(f"{API}/auth/verify-email", json={"token": token}).status_code == 200
    assert w.c.get(f"{API}/auth/me", cookies=cookies_for(tok)).json()["email_verified"] is True
    again = w.c.post(f"{API}/auth/verify-email", json={"token": token})
    assert again.status_code == 400 and again.json()["error"]["code"] == "token_used"
    assert w.c.post(f"{API}/auth/verify-email", json={"token": "x" * 43}).json()["error"]["code"] == "token_invalid"
    # evidence: one accepted attempt, no recipient / token / link anywhere, and the token is hashed at rest
    rows = w.attempts()
    assert [(a.message_type, a.status, a.provider_message_ref, a.locale) for a in rows] == [("email_verification", "provider_accepted", "<mid-0001@brevo.test>", "de")]
    with w.repo.session_factory() as s:
        dump = json.dumps([(e.event_type, e.context, e.target_id) for e in s.scalars(select(AuditEvent)).all()], default=str)
        dump += json.dumps([(a.message_type, a.status, a.failure_category, a.provider_message_ref, a.locale, a.request_id) for a in s.scalars(select(EmailAttempt)).all()])
        stored = [t.token_hash for t in s.scalars(select(AuthToken)).all()]
    for secret in (token, "ann@example.test", KEY_A, link):
        assert secret not in dump and secret not in caplog.text, secret
    assert token not in stored and tokens.hash_token(token) in stored


def test_expired_verification_link_and_resend_retires_the_earlier_link_with_a_cooldown(w, hub):
    _, email, ck = w.user()
    first = hub.last_token()
    with w.repo.session_factory() as s:
        s.execute(text("UPDATE auth_tokens SET expires_at = '2000-01-01 00:00:00'"))
        s.commit()
    assert w.c.post(f"{API}/auth/verify-email", json={"token": first}).json()["error"]["code"] == "token_expired"
    r = w.c.post(f"{API}/auth/verify-email/resend", cookies=ck)
    assert r.status_code == 200 and len(hub.sent()) == 2
    second = hub.last_token()
    assert second != first
    # the cooldown: a second resend inside a minute is refused, and no extra mail was submitted
    assert w.c.post(f"{API}/auth/verify-email/resend", cookies=ck).status_code == 429
    assert len(hub.sent()) == 2
    assert w.c.post(f"{API}/auth/verify-email", json={"token": second}).status_code == 200


def test_resend_with_a_provider_outage_is_honest_for_the_signed_in_owner(hub):
    hub.behavior = lambda req: httpx.Response(503)
    world = World(brevo(hub))
    try:
        assert world.c.post(f"{API}/auth/register", json={"email": "o@example.test", "password": PW}).status_code == 201   # public response stays uniform
        ck = cookies_for(login_token(world.c, "o@example.test", PW))
        r = world.c.post(f"{API}/auth/verify-email/resend", cookies=ck)
        assert r.status_code == 503 and r.json()["error"]["code"] == "email_unavailable"
        cats = [(a.status, a.failure_category) for a in world.attempts()]
        assert cats and all(c == ("failed", "provider_unavailable") for c in cats)
        with world.repo.session_factory() as s:
            fail = s.scalars(select(AuditEvent).where(AuditEvent.event_type == "account.email_failed")).all()
        assert fail and all(e.context.get("category") == "provider_unavailable" and "to" not in json.dumps(e.context) for e in fail)
    finally:
        world.close()


def test_a_provider_that_is_not_configured_is_never_reported_as_sent():
    world = World(NotConfiguredEmailSender())
    try:
        assert world.c.post(f"{API}/auth/register", json={"email": "n@example.test", "password": PW}).status_code == 201
        assert [(a.status, a.failure_category) for a in world.attempts()] == [("not_configured", "provider_not_configured")]
    finally:
        world.close()


# ---------------- password recovery ---------------------------------------------------------------------------------

def test_password_recovery_journey_sessions_old_credential_replay_and_localisation(w, hub):
    _, email, ck = w.user(locale="fr")
    n0 = len(hub.sent())
    uniform = w.c.post(f"{API}/auth/forgot-password", json={"email": email}).json()
    unknown = w.c.post(f"{API}/auth/forgot-password", json={"email": "nobody@example.test"}).json()
    assert uniform == unknown                                                              # no account-existence oracle
    sent = hub.sent()[n0:]
    assert len(sent) == 1 and sent[0]["to"] == [{"email": email}] and sent[0]["subject"].startswith("Réinitialisez")
    token = hub.last_token()
    assert w.c.get(f"{API}/auth/me", cookies=ck).status_code == 200
    r = w.c.post(f"{API}/auth/reset-password", json={"token": token, "password": NEW_PW})
    assert r.status_code == 200
    assert w.c.get(f"{API}/auth/me", cookies=ck).status_code == 401                         # every session of the account was revoked
    assert login_token(w.c, email, PW) is None and login_token(w.c, email, NEW_PW)          # old credential dead, new one works
    again = w.c.post(f"{API}/auth/reset-password", json={"token": token, "password": NEW_PW + "x"})
    assert again.status_code == 400 and again.json()["error"]["code"] == "token_used"
    assert login_token(w.c, email, NEW_PW + "x") is None                                    # the replay changed nothing
    events = [e["event_type"] + ":" + e["result"] for e in w.events()]
    assert "account.reset_request:success" in events and "account.reset_complete:success" in events and "account.reset_complete:failure" in events
    assert [a.message_type for a in w.attempts()].count("password_reset") == 1


def test_recovery_tokens_are_account_bound_purpose_bound_expiring_and_newest_wins(w, hub):
    _, e1, _ = w.user()
    _, e2, _ = w.user()
    verify_token = hub.sent() and re.search(r"token=([\w\-%]+)", hub.sent()[-1]["textContent"]).group(1)
    assert w.c.post(f"{API}/auth/reset-password", json={"token": verify_token, "password": NEW_PW}).json()["error"]["code"] == "token_invalid"   # wrong purpose
    w.c.post(f"{API}/auth/forgot-password", json={"email": e1})
    t1 = hub.last_token()
    w.c.post(f"{API}/auth/forgot-password", json={"email": e1})
    t2 = hub.last_token()
    assert w.c.post(f"{API}/auth/reset-password", json={"token": t1, "password": NEW_PW}).json()["error"]["code"] == "token_used"   # superseded by the newest
    w.c.post(f"{API}/auth/forgot-password", json={"email": e2})
    t_other = hub.last_token()
    assert w.c.post(f"{API}/auth/reset-password", json={"token": t2, "password": NEW_PW}).status_code == 200
    assert login_token(w.c, e1, NEW_PW) and login_token(w.c, e2, PW)                       # e2 untouched by e1's reset
    with w.repo.session_factory() as s:
        s.execute(text("UPDATE auth_tokens SET expires_at = '2000-01-01 00:00:00'"))
        s.commit()
    assert w.c.post(f"{API}/auth/reset-password", json={"token": t_other, "password": NEW_PW}).json()["error"]["code"] == "token_expired"
    assert w.c.post(f"{API}/auth/reset-password", json={"token": t_other, "password": "short"}).status_code in (400, 422)   # weak password rejected before use


def test_concurrent_redemption_of_one_link_succeeds_exactly_once(w, hub):
    _, email, _ = w.user()
    token = hub.last_token()
    repo = TokenRepository(w.repo.session_factory)
    barrier, results = threading.Barrier(12), []

    def redeem():
        barrier.wait()
        try:
            results.append(repo.consume_detailed(token_hash=tokens.hash_token(token), purpose="email_verification")[0])
        except Exception:  # noqa: BLE001 - a locked database counts as a loser
            results.append(None)
    threads = [threading.Thread(target=redeem) for _ in range(12)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert sum(1 for r in results if r is not None) == 1


def test_recovery_is_neutral_and_silent_for_oidc_only_suspended_and_malformed_requests(w, hub):
    acc = w.accounts
    oidc_id = acc.link_or_create_oidc(provider="google", provider_subject="g-1", email="oidc@example.test", email_verified=True, display_name=None)
    _, sus_email, _ = w.user()
    sus = acc.find_by_email(sus_email).user_id
    acc.set_status(sus, ACCOUNT_STATUS_DEACTIVATED)
    before = len(hub.sent())
    msgs = {json.dumps(w.c.post(f"{API}/auth/forgot-password", json={"email": e}).json()) for e in ("oidc@example.test", sus_email, "nobody@example.test", "not-an-email")}
    assert len(msgs) == 1 and len(hub.sent()) == before                   # identical answers; nothing mailed to an OIDC-only or suspended account
    with w.repo.session_factory() as s:
        reasons = {e.context.get("reason") for e in s.scalars(select(AuditEvent).where(AuditEvent.event_type == "account.reset_request")).all() if e.result == "not_eligible"}
    assert reasons == {"no_password_credential", "inactive_account"} and oidc_id


def test_a_provider_outage_during_recovery_is_uniform_publicly_and_recorded_internally(hub):
    hub.behavior = lambda req: httpx.Response(503)
    world = World(brevo(hub))
    try:
        world.c.post(f"{API}/auth/register", json={"email": "r@example.test", "password": PW})
        r = world.c.post(f"{API}/auth/forgot-password", json={"email": "r@example.test"})
        assert r.status_code == 200 and "If an account exists" in r.json()["message"]
        assert len([a for a in world.attempts() if a.message_type == "password_reset" and a.status == "failed"]) == 1
        assert len(hub.sent()) == 2                                       # exactly one try each; no retry loop, no regeneration storm
    finally:
        world.close()


# ---------------- identity linking -----------------------------------------------------------------------------------

def test_pre_hijack_an_unverified_password_account_loses_its_credential_when_the_real_owner_signs_in_with_google(w):
    acc = w.accounts
    assert w.c.post(f"{API}/auth/register", json={"email": "victim@example.test", "password": "attacker-chosen-pass-01"}).status_code == 201
    attacker_ck = cookies_for(login_token(w.c, "victim@example.test", "attacker-chosen-pass-01"))
    uid = acc.link_or_create_oidc(provider="google", provider_subject="g-victim", email="victim@example.test", email_verified=True, display_name="V")
    assert w.c.get(f"{API}/auth/me", cookies=attacker_ck).status_code == 401           # the attacker's session is revoked
    assert login_token(w.c, "victim@example.test", "attacker-chosen-pass-01") is None   # and so is the attacker's password
    me = acc.get_account(uid)
    assert me.email_verified is True and me.has_password is False and "google" in me.providers


def test_a_verified_password_account_keeps_its_password_and_an_unverified_google_email_never_links(w, hub):
    acc = w.accounts
    uid, email, _ = w.user()
    w.c.post(f"{API}/auth/verify-email", json={"token": hub.last_token()})
    assert acc.link_or_create_oidc(provider="google", provider_subject="g-2", email=email, email_verified=True, display_name=None) == uid
    assert acc.get_account(uid).has_password is True                                       # a verified owner's password is not touched
    other = acc.link_or_create_oidc(provider="google", provider_subject="g-3", email=email, email_verified=False, display_name=None)
    assert other != uid                                                                    # an UNVERIFIED claim never links to an existing account


# ---------------- Admin: authorization, diagnostics, test email, probe ------------------------------------------------

def test_the_connection_probe_checks_credential_and_sender_and_never_sends_an_email(monkeypatch):
    monkeypatch.setenv("EMAIL_SENDER", SENDER)

    def answer(senders):
        def f(req):
            if req.url.path == "/v3/account":
                return httpx.Response(200, json={})
            return httpx.Response(200, json={"senders": senders})
        return f
    store = SS.InMemorySecretStore({"BREVO_API_KEY": KEY_A})
    ok = Hub(answer([{"email": SENDER, "active": True}]))
    assert I.probe_brevo(store, transport=ok.transport) == I.ProbeResult("success", "ok", I.probe_brevo(store, transport=ok.transport).latency_ms)
    assert [r.url.path for r in ok.requests[:2]] == ["/v3/account", "/v3/senders"] and all(r.method == "GET" for r in ok.requests)
    assert not any(r.url.path == "/v3/smtp/email" for r in ok.requests)
    assert I.probe_brevo(store, transport=Hub(answer([{"email": "other@example.test", "active": True}])).transport).category == "configuration_error"
    assert I.probe_brevo(store, transport=Hub(answer([{"email": SENDER, "active": False}])).transport).category == "configuration_error"
    assert I.probe_brevo(store, transport=Hub(lambda r: httpx.Response(401)).transport).category == "unauthorized"
    assert I.probe_brevo(SS.InMemorySecretStore(), transport=ok.transport).category == "configuration_error"
    monkeypatch.delenv("EMAIL_SENDER")
    assert I.probe_brevo(store, transport=ok.transport).category == "configuration_error"
    assert I.run_probe("email_brevo", store, {"email_brevo": lambda s: (_ for _ in ()).throw(RuntimeError(KEY_A))}).category == "unknown"


def _admin_world(hub):
    world = World(brevo(hub))
    return world


def test_admin_delivery_status_is_truthful_bounded_and_permissioned(monkeypatch, hub):
    monkeypatch.setenv("EMAIL_PROVIDER", "brevo")
    monkeypatch.setenv("EMAIL_SENDER", SENDER)
    monkeypatch.setenv("BREVO_API_KEY", KEY_A)
    world = World(brevo(hub))
    try:
        for role, code in (("platform_admin", 200), ("operations_admin", 200), ("security_privacy_admin", 403), ("knowledge_admin", 403),
                           ("billing_admin", 403), ("support_operator", 403), ("user", 403)):
            _, _, ck = world.user(role)
            assert world.c.get(f"{API}/admin/integrations/email_brevo/delivery", cookies=ck).status_code == code, role
        assert [r for r, p in perm.ROLE_PRESETS.items() if perm.INTEGRATIONS_READ in p and r != "platform_admin"] == ["operations_admin"] and len(perm.PERMISSIONS) == 44 and len(set(perm.PERMISSIONS) - {"platform.billing.recover"}) == 43
        _, _, adm = world.user("platform_admin")
        d = world.c.get(f"{API}/admin/integrations/email_brevo/delivery", cookies=adm).json()
        assert d["status"] == "provider_accepted"                 # the registration mails above were accepted by the fake provider
        assert d["delivery_confirmation"] == "not_collected" and d["live_delivery"] == "unverified"
        assert d["adapter_in_process"] == "brevo" and d["restart_required"] is False and d["sender_verification"] == "unknown"
        assert d["identity_pipeline"] == {"verification": "ready", "recovery": "ready"} and d["link_origin"] == {"configured": True, "https": True}
        blob = json.dumps(d)
        for secret in (KEY_A, "example.test/verify-email", "token=", "w1@example.test", SENDER):
            assert secret not in blob, secret
        assert world.c.get(f"{API}/admin/integrations/openrouter/delivery", cookies=adm).status_code == 404
        # a rotation after the client was built is reported as restart-required, never as active
        store = SS.EnvironmentSecretStore()
        monkeypatch.setenv("BREVO_API_KEY", KEY_B)
        world.app.dependency_overrides[deps.get_secret_store] = lambda: store
        d2 = world.c.get(f"{API}/admin/integrations/email_brevo/delivery", cookies=adm).json()
        assert d2["restart_required"] is True and "restart" in d2["restart_reason"]
        # a failed submission becomes the headline and a bounded category
        hub.behavior = lambda req: httpx.Response(401)
        world.c.post(f"{API}/auth/forgot-password", json={"email": "w1@example.test"})
        d3 = world.c.get(f"{API}/admin/integrations/email_brevo/delivery", cookies=adm).json()
        assert d3["status"] == "delivery_failed" and d3["last_failure_category"] == "provider_auth_failed"
    finally:
        world.close()


def test_the_manual_test_email_goes_only_to_the_acting_admin_is_explicit_audited_and_rate_limited(monkeypatch, hub):
    monkeypatch.setenv("EMAIL_PROVIDER", "brevo")
    monkeypatch.setenv("EMAIL_SENDER", SENDER)
    monkeypatch.setenv("BREVO_API_KEY", KEY_A)
    world = World(brevo(hub))
    try:
        url = f"{API}/admin/integrations/email_brevo/test-email"
        _, _, ops = world.user("operations_admin")
        uid, email, adm = world.user("platform_admin", locale="nl")
        for role in ("security_privacy_admin", "billing_admin", "support_operator", "knowledge_admin", "user"):
            _, _, ck = world.user(role)
            assert world.c.post(url, json={"confirm": True}, cookies=ck).status_code == 403, role
        assert world.c.post(url, json={}, cookies=adm).status_code == 422                          # explicit confirmation
        assert world.c.post(url, json={"confirm": True, "to": "victim@example.test"}, cookies=adm).status_code == 422   # no recipient field exists
        n0 = len(hub.sent())
        r = world.c.post(url, json={"confirm": True}, cookies=adm)
        assert r.status_code == 200 and r.json()["status"] == "provider_accepted" and "not a delivery confirmation" in r.json()["note"]
        sent = hub.sent()[n0:]
        assert len(sent) == 1 and sent[0]["to"] == [{"email": email}] and "token" not in sent[0]["textContent"] and "http" not in sent[0]["textContent"]
        assert sent[0]["subject"].startswith("Ask4Mo-test")                                       # the admin's own language
        assert world.c.post(url, json={"confirm": True}, cookies=ops).status_code == 200            # ops_admin holds integrations.manage
        assert world.c.post(url, json={"confirm": True}, cookies=adm).status_code == 200
        assert world.c.post(url, json={"confirm": True}, cookies=adm).status_code == 200
        assert world.c.post(url, json={"confirm": True}, cookies=adm).status_code == 429            # 3 per hour per administrator; never bulk
        kinds = [e["event_type"] for e in world.events()]
        assert kinds.count(A.ADMIN_EMAIL_TEST_REQUESTED) == 4 and kinds.count(A.ADMIN_EMAIL_TEST_SENT) == 4   # 3 by the owner + 1 by operations
        with world.repo.session_factory() as s:
            blob = json.dumps([(e.context, e.target_id) for e in s.scalars(select(AuditEvent).where(AuditEvent.event_type.like("admin.email_test%"))).all()], default=str)
        assert email not in blob and KEY_A not in blob
        assert [a.message_type for a in world.attempts()].count("admin_test") == 4
    finally:
        world.close()


def test_a_development_adapter_is_reported_as_captured_not_sent(w):
    world = World(MemoryEmailSender())
    try:
        _, _, adm = world.user("platform_admin")
        r = world.c.post(f"{API}/admin/integrations/email_brevo/test-email", json={"confirm": True}, cookies=adm).json()
        assert r["status"] == "captured" and r["adapter"] == "memory" and "nothing was sent to a provider" in r["note"]
    finally:
        world.close()


# ---------------- config, retention, migration, hygiene ----------------------------------------------------------------

def test_production_requires_an_https_link_origin(monkeypatch):
    from src.api.env_validation import validate_runtime_config
    monkeypatch.setenv("APP_BASE_URL", "http://app.example.test")
    assert any("https" in c for c in validate_runtime_config("production").critical)
    monkeypatch.setenv("APP_BASE_URL", ORIGIN)
    assert not any("APP_BASE_URL must be an https" in c for c in validate_runtime_config("production").critical)


def test_attempt_rows_are_purged_by_age_and_hold_no_recipient_after_account_deletion(w):
    uid, email, _ = w.user()
    repo = EmailAttemptRepository(w.repo.session_factory)
    with w.repo.session_factory() as s:
        s.add(EmailAttempt(message_type="password_reset", provider="brevo", status="failed", failure_category="rate_limited",
                           created_at=utcnow() - timedelta(days=RETENTION_DAYS + 1)))
        s.commit()
    EmailService(MemoryEmailSender(), repo).deliver(__import__("src.mail", fromlist=["EmailMessage"]).EmailMessage("a@b.co", "s", "b", "admin_test"))
    assert all(a.created_at.replace(tzinfo=None) > (utcnow() - timedelta(days=RETENTION_DAYS)).replace(tzinfo=None) for a in w.attempts())
    cols = {c.name for c in EmailAttempt.__table__.columns}
    assert cols == {"id", "message_type", "provider", "status", "failure_category", "provider_message_ref", "locale", "request_id", "user_id", "created_at"}
    summary = repo.summary()
    assert "user_id" not in json.dumps(summary) and email not in json.dumps(summary)


def test_migration_0027_single_head_fresh_and_round_trip(tmp_path, monkeypatch):
    from alembic import command
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    from sqlalchemy import create_engine, inspect

    def cfg(url):
        c = Config("alembic.ini")
        c.set_main_option("script_location", "migrations")
        c.set_main_option("sqlalchemy.url", url)
        return c

    url = f"sqlite:///{tmp_path / 'm.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    assert ScriptDirectory.from_config(cfg(url)).get_heads() == ["0031_account_closure"]
    command.upgrade(cfg(url), "0026_managed_secrets")
    assert "email_attempts" not in inspect(create_engine(url)).get_table_names()
    command.upgrade(cfg(url), "head")
    assert {c["name"] for c in inspect(create_engine(url)).get_columns("email_attempts")} == {"id", "message_type", "provider", "status", "failure_category",
        "provider_message_ref", "locale", "request_id", "user_id", "created_at"}
    command.downgrade(cfg(url), "0026_managed_secrets")
    assert "email_attempts" not in inspect(create_engine(url)).get_table_names()
    command.upgrade(cfg(url), "head")


def test_test_values_exist_only_in_test_sources():
    import subprocess
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    out = subprocess.run(["git", "grep", "-l", "DO_NOT_LEAK_W12_04C", "--", "."], cwd=root, capture_output=True, text=True).stdout.split()
    assert set(out) <= {"tests/test_email_identity_w12_4c.py"}, out
