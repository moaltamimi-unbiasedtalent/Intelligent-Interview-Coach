"""W12.4D-C: checkout and subscription lifecycle FOUNDATION. Providers here are fakes; no Stripe call is made and every non-loopback connection fails."""

from __future__ import annotations

import threading
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import func, select

from src.billing import lifecycle as L
from src.billing import policy as P
from src.billing.checkout import (
    CheckoutConflict, CheckoutNotFound, CheckoutProviderError, CheckoutService, CheckoutUnavailable, CheckoutValidationError,
)
from src.billing.provider import CheckoutResult, MockBillingAdapter, ProviderRejected, ProviderRetryable
from src.persistence import (
    BillingCheckoutSession, BillingCommercialTerms, BillingProviderPrice, PlanVersion, Subscription, User,
    init_db, make_engine, make_session_factory, utcnow,
)

ROOT = Path(__file__).resolve().parents[1]
ORIGIN = "https://app.example.test"


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


class FakeProvider:
    name = P.PROVIDER_STRIPE_MP
    live = False
    environment = "sandbox"

    def __init__(self, fail=None):
        self.calls, self.fail, self.lock = [], fail, threading.Lock()

    def capabilities(self):
        return {"checkout": True}

    def create_checkout_session(self, req):
        with self.lock:
            self.calls.append(req)
        if self.fail:
            raise self.fail
        return CheckoutResult(provider_session_id=f"cs_test_{req.client_reference_id}", url=f"https://checkout.stripe.test/{req.client_reference_id}")


MODE = SimpleNamespace(provider=P.PROVIDER_STRIPE_MP, environment="sandbox", enabled=False, live=False)


@pytest.fixture()
def env(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path / 'c.db'}")
    init_db(engine)
    sf = make_session_factory(engine)
    with sf() as s:
        pv = s.scalar(select(PlanVersion).where(PlanVersion.plan_code == "premium"))
        users = [User(subject=f"u{i}", provider="local", email=f"u{i}@x.test") for i in range(3)]
        s.add_all(users)
        s.flush()
        terms = BillingCommercialTerms(public_id="t" * 32, plan_version_id=pv.id, version=1, amount_minor=1999, currency="EUR", billing_interval="month",
                                       visibility="public", state="active")
        s.add(terms)
        s.flush()
        s.add(BillingProviderPrice(public_id="p" * 32, commercial_terms_id=terms.id, provider=P.PROVIDER_STRIPE_MP, environment="sandbox",
                                   provider_product_id="prod_test_1", provider_price_id="price_test_1", amount_minor=1999, currency="EUR",
                                   billing_interval="month", status="active"))
        s.commit()
        ids = [u.id for u in users]
    return SimpleNamespace(sf=sf, users=ids, engine=engine)


def svc(env, provider=None, **kw):
    kw.setdefault("readiness", lambda: "sandbox_access_unverified")
    return CheckoutService(env.sf, provider=provider or FakeProvider(), mode=kw.pop("mode", MODE), app_base_url=kw.pop("app_base_url", ORIGIN),
                           api_env=kw.pop("api_env", "production"), **kw)


def rows(env):
    with env.sf() as s:
        return s.scalars(select(BillingCheckoutSession)).all()


KEY = "key-aaaaaaaa-1"


def test_checkout_uses_server_side_terms_and_trusted_return_urls(env):
    prov = FakeProvider()
    out = svc(env, prov).create(env.users[0], "premium", KEY)
    assert out["status"] == "open" and out["redirect_url"].startswith("https://checkout.stripe.test/")
    req = prov.calls[0]
    assert req.provider_price_id == "price_test_1"
    assert req.success_url.startswith(ORIGIN + "/billing/return?") and req.cancel_url.startswith(ORIGIN + "/billing/return?")
    assert req.idempotency_key.startswith("ask4mo-checkout-") and req.client_reference_id


def test_same_key_returns_same_session_and_creates_one_provider_session(env):
    prov, s = FakeProvider(), None
    s = svc(env, prov)
    a, b = s.create(env.users[0], "premium", KEY), s.create(env.users[0], "premium", KEY)
    assert a["checkout_id"] == b["checkout_id"] and len(prov.calls) == 1 and len(rows(env)) == 1


def test_different_key_joins_the_open_attempt(env):
    prov = FakeProvider()
    s = svc(env, prov)
    a, b = s.create(env.users[0], "premium", KEY), s.create(env.users[0], "premium", "key-bbbbbbbb-2")
    assert a["checkout_id"] == b["checkout_id"] and len(prov.calls) == 1


def test_concurrent_requests_create_one_attempt(env):
    prov = FakeProvider()
    s = svc(env, prov)
    outs, errs = [], []

    def go(k):
        try:
            outs.append(s.create(env.users[0], "premium", k))
        except Exception as e:  # noqa: BLE001
            errs.append(e)
    ts = [threading.Thread(target=go, args=(f"race-key-{i:04d}",)) for i in range(6)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert len(rows(env)) == 1
    assert all(isinstance(e, (CheckoutConflict, CheckoutProviderError)) for e in errs)


def test_idempotency_key_is_owner_scoped(env):
    s = svc(env)
    a, b = s.create(env.users[0], "premium", KEY), s.create(env.users[1], "premium", KEY)
    assert a["checkout_id"] != b["checkout_id"]


@pytest.mark.parametrize("bad", ["", "short", "has space 12345", "x" * 65, "semi;colon12"])
def test_bad_idempotency_keys_are_refused(env, bad):
    with pytest.raises(CheckoutValidationError):
        svc(env).create(env.users[0], "premium", bad)


@pytest.mark.parametrize("plan", ["free", "enterprise", "../premium", ""])
def test_only_purchasable_plans(env, plan):
    with pytest.raises(CheckoutUnavailable):
        svc(env).create(env.users[0], plan, KEY)


def test_fail_closed_without_active_terms_or_mapping(env):
    with env.sf() as s:
        s.execute(BillingProviderPrice.__table__.update().values(status="retired"))
        s.commit()
    with pytest.raises(CheckoutUnavailable) as e:
        svc(env).create(env.users[0], "premium", KEY)
    assert e.value.reason == "no_price_mapping"
    with env.sf() as s:
        s.execute(BillingCommercialTerms.__table__.update().values(state="retired"))
        s.commit()
    assert svc(env).availability("premium")["reason"] == "no_active_terms"


def test_mismatched_mapping_snapshot_is_never_the_price(env):
    with env.sf() as s:
        s.execute(BillingProviderPrice.__table__.update().values(amount_minor=1))
        s.commit()
    assert svc(env).availability("premium")["reason"] == "no_price_mapping"


def test_provider_and_mode_gates(env):
    assert svc(env, mode=SimpleNamespace(provider="mock", environment=None, enabled=True, live=False)).availability("premium")["reason"] == "provider_not_selected"
    assert svc(env, mode=SimpleNamespace(provider=P.PROVIDER_STRIPE_MP, environment="live", enabled=False, live=False)).availability("premium")["reason"] == "live_disabled"
    assert svc(env, readiness=lambda: "not_configured").availability("premium")["reason"] == "provider_not_ready"
    p = FakeProvider()
    p.capabilities = lambda: {"checkout": False}
    assert svc(env, p).availability("premium")["reason"] == "checkout_not_authorized"
    assert svc(env, MockBillingAdapter()).availability("premium")["reason"] == "provider_not_selected"


def test_public_availability_reveals_no_internal_reason(env):
    out = svc(env, readiness=lambda: "not_configured").public_availability("premium")
    assert out == {"plan": "premium", "available": False, "reason": "not_enabled"}


@pytest.mark.parametrize("origin", ["", "http://app.example.test", "https://app.example.test/path", "javascript:alert(1)", "https://"])
def test_untrusted_origin_refused(env, origin):
    with pytest.raises(CheckoutUnavailable):
        svc(env, app_base_url=origin).create(env.users[0], "premium", KEY)


def test_localhost_http_only_in_development(env):
    assert svc(env, app_base_url="http://localhost:3015", api_env="development").availability("premium")["available"]
    assert not svc(env, app_base_url="http://localhost:3015", api_env="production").availability("premium")["available"]


def test_retryable_failure_can_be_retried_with_same_key_and_never_double_creates(env):
    prov = FakeProvider(fail=ProviderRetryable("provider_timeout"))
    s = svc(env, prov)
    with pytest.raises(CheckoutProviderError) as e:
        s.create(env.users[0], "premium", KEY)
    assert e.value.retryable
    prov.fail = None
    out = s.create(env.users[0], "premium", KEY)
    assert out["status"] == "open" and len(rows(env)) == 1
    assert prov.calls[0].idempotency_key == prov.calls[1].idempotency_key


def test_rejection_is_terminal_for_that_key_and_stores_no_url(env):
    s = svc(env, FakeProvider(fail=ProviderRejected("managed_payments_not_enabled")))
    with pytest.raises(CheckoutProviderError) as e:
        s.create(env.users[0], "premium", KEY)
    assert not e.value.retryable
    r = rows(env)[0]
    assert r.status == "failed" and r.checkout_url is None and r.failure_category == "managed_payments_not_enabled"


def test_browser_return_is_a_fact_not_a_payment(env):
    s = svc(env)
    cid = s.create(env.users[0], "premium", KEY)["checkout_id"]
    out = s.record_return(env.users[0], cid, "success")
    assert out["browser_returned"] and out["status"] == "open"
    st = s.status(env.users[0], "free")
    assert st["subscription"] == "confirmation_pending" and st["confirmation"] == "pending"
    assert st["entitlement"] == {"plan_code": "free", "source": "entitlement_service", "changed_by_billing": False}
    with env.sf() as sess:
        assert sess.scalar(select(func.count()).select_from(Subscription).where(Subscription.plan_version_id.in_(
            select(PlanVersion.id).where(PlanVersion.plan_code == "premium")))) == 0


def test_cancel_return_ends_attempt_and_clears_url_and_allows_a_new_one(env):
    s = svc(env)
    cid = s.create(env.users[0], "premium", KEY)["checkout_id"]
    assert s.record_return(env.users[0], cid, "cancel")["status"] == "canceled"
    assert rows(env)[0].checkout_url is None
    assert s.create(env.users[0], "premium", "key-cccccccc-3")["checkout_id"] != cid
    with pytest.raises(CheckoutConflict):
        s.create(env.users[0], "premium", KEY)


def test_return_for_another_users_checkout_is_not_found(env):
    s = svc(env)
    cid = s.create(env.users[0], "premium", KEY)["checkout_id"]
    with pytest.raises(CheckoutNotFound):
        s.record_return(env.users[1], cid, "success")
    with pytest.raises(CheckoutNotFound):
        s.record_return(env.users[0], "nope", "success")
    with pytest.raises(CheckoutValidationError):
        s.record_return(env.users[0], cid, "paid")


def test_expiry_is_lazy_and_makes_room_for_a_new_attempt(env):
    now = [utcnow()]
    s = svc(env, clock=lambda: now[0])
    cid = s.create(env.users[0], "premium", KEY)["checkout_id"]
    now[0] += timedelta(seconds=P.CHECKOUT_SESSION_TTL_SECONDS + 5)
    assert s.status(env.users[0], "free")["checkout"] == "expired"
    out = s.create(env.users[0], "premium", "key-dddddddd-4")
    assert out["checkout_id"] != cid and out["status"] == "open"


def test_status_with_no_attempt_is_none_and_never_paid(env):
    st = svc(env).status(env.users[0], "free")
    assert (st["checkout"], st["subscription"], st["payment"]) == ("none", "none", "none")


def test_deleting_the_user_deletes_their_attempts(env):
    svc(env).create(env.users[0], "premium", KEY)
    with env.sf() as s:
        s.execute(BillingCheckoutSession.__table__.delete().where(BillingCheckoutSession.user_id == env.users[0]))
        s.commit()
    assert rows(env) == []


# ---------------- lifecycle model -------------------------------------------------------------------------------------

def test_checkout_state_machine():
    assert L.checkout_transition_allowed("pending_creation", "open") and L.checkout_transition_allowed("open", "expired")
    for terminal in ("canceled", "expired"):
        assert not any(L.checkout_transition_allowed(terminal, n) for n in ("open", "pending_creation", "failed"))
    assert not L.checkout_transition_allowed("open", "failed")
    with pytest.raises(L.LifecycleError):
        L.require_checkout_transition("canceled", "open")


@pytest.mark.parametrize("state", sorted(L.EVIDENCE_REQUIRED_SUBSCRIPTION))
def test_provider_owned_subscription_states_need_verified_evidence(state):
    with pytest.raises(L.LifecycleError):
        L.require_evidence("subscription", state, evidence_verified=False)
    L.require_evidence("subscription", state, evidence_verified=True)


@pytest.mark.parametrize("state", sorted(L.EVIDENCE_REQUIRED_PAYMENT))
def test_provider_owned_payment_states_need_verified_evidence(state):
    with pytest.raises(L.LifecycleError):
        L.require_evidence("payment", state, evidence_verified=False)


def test_no_paid_checkout_status_exists():
    from src.persistence import CHECKOUT_STATUSES
    assert not {"paid", "complete", "completed", "succeeded", "active"} & set(CHECKOUT_STATUSES)


def test_candidate_view_never_reports_active_without_evidence():
    v = L.candidate_view(checkout_status="open", browser_returned=True, plan_code="free")
    assert v["subscription"] == "confirmation_pending" and v["entitlement"]["changed_by_billing"] is False


# ---------------- safety constants and boundaries ---------------------------------------------------------------------

def test_live_and_external_checkout_stay_off_and_events_stay_refused():
    assert P.LIVE_BILLING_ENABLED is False and P.EXTERNAL_CHECKOUT_AUTHORIZED is False and P.PROVIDERS == ("mock",)


def test_mock_never_runs_a_checkout():
    with pytest.raises(ProviderRejected):
        MockBillingAdapter().create_checkout_session(object())


def test_real_stripe_adapter_refuses_checkout_by_configuration():
    from src.billing.provider import CheckoutRequest
    from src.billing.stripe_provider import StripeManagedPaymentsProvider
    req = CheckoutRequest("k" * 12, "price_x", "https://a/b", "https://a/c", "ref")
    with pytest.raises(ProviderRejected) as e:
        StripeManagedPaymentsProvider(environment="sandbox").create_checkout_session(req)
    assert str(e.value) == "checkout_not_authorized"


def test_stripe_adapter_builds_managed_payments_subscription_params_with_injected_client():
    from src.billing.provider import CheckoutRequest
    from src.billing.stripe_provider import StripeManagedPaymentsProvider
    seen = {}

    class Sessions:
        def create(self, params, opts):
            seen.update(params=params, opts=opts)
            return SimpleNamespace(id="cs_test_1", url="https://checkout.stripe.test/c/1")
    client = SimpleNamespace(v1=SimpleNamespace(checkout=SimpleNamespace(sessions=Sessions())))
    prov = StripeManagedPaymentsProvider(environment="sandbox", store=object(), client_factory=lambda store, env: client)
    out = prov.create_checkout_session(CheckoutRequest("idem-key-123456", "price_x", "https://a/b", "https://a/c", "ref1"))
    assert out.provider_session_id == "cs_test_1"
    assert seen["params"]["mode"] == "subscription" and seen["params"]["managed_payments"] == {"enabled": True}
    assert seen["opts"] == {"idempotency_key": "idem-key-123456"}


def test_migration_0028_is_single_head_and_in_the_model():
    versions = sorted((ROOT / "migrations" / "versions").glob("*.py"))
    text = (ROOT / "migrations" / "versions" / "0028_checkout_sessions.py").read_text()
    assert 'down_revision = "0027_email_attempts"' in text
    downs = [p.read_text() for p in versions]
    assert sum('down_revision = "0028_checkout_sessions"' in d for d in downs) == 0
    assert "create_all" not in text and "stamp" not in text


# ---------------- HTTP surface ----------------------------------------------------------------------------------------

@pytest.fixture()
def http():
    from tests.test_admin_foundation_w10_1 import Env
    e = Env()
    yield e
    e.close()


API = "/api/v1/billing"


def test_checkout_routes_require_authentication(http):
    bad = {"ask4mo_session": "not-a-session"}      # development falls back to a dev identity with NO cookie; an invalid one is always a 401
    assert http.c.post(f"{API}/checkout-sessions", json={"plan": "premium"}, cookies=bad).status_code == 401
    assert http.c.post(f"{API}/checkout-returns", json={"checkout_id": "x" * 12, "outcome": "success"}, cookies=bad).status_code == 401
    assert http.c.get(f"{API}/checkout/status", cookies=bad).status_code == 401


def test_client_cannot_control_price_currency_redirect_or_entitlement(http):
    _, ck = http.user()
    for extra in ({"amount": 1}, {"currency": "USD"}, {"success_url": "https://evil.test"}, {"price_id": "price_x"}, {"entitlement": "premium"}, {"provider": "x"}):
        r = http.c.post(f"{API}/checkout-sessions", json={"plan": "premium", **extra}, cookies=ck, headers={"Idempotency-Key": "http-key-0001"})
        assert r.status_code == 422, extra
    assert http.c.post(f"{API}/checkout-sessions", json={"plan": "free"}, cookies=ck, headers={"Idempotency-Key": "http-key-0001"}).status_code == 422


def test_checkout_is_disabled_by_default_and_reveals_no_internal_reason(http):
    _, ck = http.user()
    r = http.c.post(f"{API}/checkout-sessions", json={"plan": "premium"}, cookies=ck, headers={"Idempotency-Key": "http-key-0002"})
    assert r.status_code == 503 and "not enabled" in r.json()["error"]["message"].lower()
    a = http.c.get(f"{API}/checkout/availability", params={"plan": "premium"})
    assert a.status_code == 200 and a.json() == {"plan": "premium", "available": False, "reason": "not_enabled"}


def test_status_is_owner_scoped_and_never_paid(http):
    _, ck = http.user()
    s = http.c.get(f"{API}/checkout/status", cookies=ck).json()
    assert (s["checkout"], s["subscription"], s["payment"]) == ("none", "none", "none")
    assert s["entitlement"]["changed_by_billing"] is False


def test_there_is_no_payment_success_endpoint(http):
    billing = {p for p in http.app.openapi()["paths"] if p.startswith("/api/v1/billing")}
    assert billing == {f"{API}/checkout/availability", f"{API}/checkout-sessions", f"{API}/checkout-returns", f"{API}/checkout/status"}
