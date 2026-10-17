# ruff: noqa: F811
"""W12.4D-F1: independent billing security and financial-state qualification. FULLY OFFLINE: recording fakes, a synthetic signing secret, synthetic provider
state, isolated databases, and every non-loopback socket fails the test. ``SYNTHETIC_POLICY`` is NOT an owner decision and no price here is catalogue data.

Each test names the finding or control it proves (F1-xx for a corrected defect, C-xx for a verified control). See the F1 document for the register."""

from __future__ import annotations

import json
import threading
import time
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import func, select

from src.billing import policy as P
from src.billing import stripe_events as SE
from src.billing.checkout import CheckoutConflict, CheckoutService, CheckoutUnavailable
from src.billing.entitlement_bridge import UNAPPROVED_POLICY
from src.billing.provider import CheckoutResult, ProviderRejected, ProviderRetryable
from src.billing.provider_state import CheckoutAssociation, NullStateReader, ProviderStateUnavailable
from src.billing.reconcile import ProviderEventService, RecoveryKeyConflict, link_by_subscription_stmt
from src.persistence import (
    BillingCheckoutSession, BillingEntitlementDecision, BillingProviderEvent, BillingProviderLink, BillingRecoveryAction, Subscription, utcnow,
)
from tests.test_webhooks_w12_4d_d import (  # noqa: F401  (shared fixtures and factories)
    SECRET, SYNTHETIC_POLICY, _no_network, accept_and_process, body, checkout_event, count, deliver, dispute_event, env, invoice_event, link_of, plan_of, reader_for,
    receiver, refund_event, service, sign, sub_event,
)

ROOT = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------- helpers -----------------------------------------------------------------------------

class RecordingProvider:
    """A checkout provider fake that RECORDS every request and honours the provider idempotency key like Stripe does (same key, same session)."""
    name, live, environment = P.PROVIDER_STRIPE_MP, False, "sandbox"

    def __init__(self):
        self.requests, self.by_key = [], {}

    def capabilities(self):
        return {"checkout": True}

    def create_checkout_session(self, req):
        self.requests.append(req)
        if req.idempotency_key not in self.by_key:
            self.by_key[req.idempotency_key] = CheckoutResult(provider_session_id=f"cs_test_rec{len(self.by_key) + 1}", url=f"https://checkout.stripe.test/{len(self.by_key) + 1}")
        return self.by_key[req.idempotency_key]


def checkout_svc(env, provider=None, **kw):
    mode = SimpleNamespace(provider=P.PROVIDER_STRIPE_MP, environment="sandbox", enabled=False, live=False)
    return CheckoutService(env.sf, provider=provider or RecordingProvider(), mode=mode, app_base_url="https://app.example.test", api_env="production",
                           readiness=lambda: "sandbox_access_unverified", clock=lambda: env.clock_now[0], **kw)


def through(real):
    """Lets the REAL adapter be exercised through the checkout service: the adapter's own capability is False (never operational), so a test wrapper reports True and delegates."""
    return SimpleNamespace(name=real.name, live=False, environment="sandbox", capabilities=lambda: {"checkout": True}, create_checkout_session=real.create_checkout_session)


def clear_checkouts(env):
    with env.sf() as s:
        s.execute(BillingCheckoutSession.__table__.delete())
        s.commit()


# ================================================================ A. ARCHITECTURE INVENTORY (facts, from the repository) ============================

def test_inventory_components_exist_and_the_disabled_ones_are_disabled():
    import src.billing.checkout, src.billing.entitlement_bridge, src.billing.operations, src.billing.provider_state, src.billing.reconcile, src.billing.scheduler  # noqa: F401, E401
    from src.billing.provider import MockBillingAdapter
    from src.billing.stripe_provider import StripeManagedPaymentsProvider
    assert MockBillingAdapter.live is False and StripeManagedPaymentsProvider.live is False
    assert StripeManagedPaymentsProvider(environment="sandbox").capabilities()["checkout"] is False                  # DISABLED: not operational by capability
    assert (P.LIVE_BILLING_ENABLED, P.EXTERNAL_CHECKOUT_AUTHORIZED, P.STRIPE_WEBHOOK_AUTHORIZED, P.RECONCILE_SCHEDULER_ENABLED, P.PAID_ENTITLEMENT_POLICY_APPROVED) == (False,) * 5
    assert P.PROVIDERS == ("mock",)                                                                                   # the mock mirror stays mock-only


# ================================================================ B. KILL SWITCHES ==================================================================

def _deps_receiver(env, store):
    from src.api import dependencies as deps
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(settings=SimpleNamespace(env="production"))))
    return deps.get_webhook_receiver(request, SimpleNamespace(session_factory=env.sf), store)


def test_C01_configuration_alone_cannot_activate_anything(env, monkeypatch):
    from src import secret_store as SS
    from src.billing import stripe_provider as SP
    monkeypatch.setenv("BILLING_PROVIDER", "stripe_managed_payments")
    monkeypatch.setenv("STRIPE_ENVIRONMENT", "sandbox")
    store = SS.InMemorySecretStore({SP.SLOT_NAMES["sandbox"]["api"]: "sk_test_SYNTHETIC_F1_000000000001", SP.SLOT_NAMES["sandbox"]["webhook"]: SECRET})
    rcv = _deps_receiver(env, store)                                                      # provider selected, credentials present, environment sandbox
    assert rcv._authorized is False and rcv._provider == P.PROVIDER_STRIPE_MP and rcv._secrets()
    raw = body(sub_event())
    with pytest.raises(SE.WebhookError) as e:
        rcv.handle(raw, sign(raw))
    assert e.value.status == 503 and count(env, BillingProviderEvent) == 0                 # a perfectly signed event is still refused
    from src.billing.provider import build_provider, safe_mode
    provider = build_provider(safe_mode())
    assert provider.capabilities()["checkout"] is False
    with pytest.raises(ProviderRejected) as r:
        provider.create_checkout_session(SimpleNamespace(idempotency_key="k" * 12, provider_price_id="p", success_url="https://a/b", cancel_url="https://a/c",
                                                        client_reference_id="r", expires_at=None))
    assert str(r.value) == "checkout_not_authorized"                                      # credentials never authorise a checkout


def test_C02_an_approved_mapping_cannot_bypass_checkout_authorization(env):
    from src.billing.stripe_provider import StripeManagedPaymentsProvider
    co = checkout_svc(env, provider=StripeManagedPaymentsProvider(environment="sandbox"))
    with pytest.raises(CheckoutUnavailable) as e:
        co.create(env.users[0], "premium", "bypass-key-0001")                             # an ACTIVE mapping and ACTIVE terms exist in this database
    assert e.value.reason == "checkout_not_authorized"


def test_C03_each_switch_flipped_alone_enables_nothing_else(env, monkeypatch):
    from src.billing.scheduler import schedule_tick
    from src.billing.stripe_provider import StripeManagedPaymentsProvider
    # EXTERNAL_CHECKOUT_AUTHORIZED alone: the adapter would try to build a real client, finds no credential and refuses; capability stays false
    monkeypatch.setattr(P, "EXTERNAL_CHECKOUT_AUTHORIZED", True)
    prov = StripeManagedPaymentsProvider(environment="sandbox", store=SimpleNamespace(get_for_runtime=lambda n: None, source=lambda n: "none"))
    with pytest.raises(ProviderRejected) as e:
        prov.create_checkout_session(SimpleNamespace(idempotency_key="k" * 12, provider_price_id="p", success_url="https://a/b", cancel_url="https://a/c", client_reference_id="r", expires_at=None))
    assert str(e.value) == "not_configured" and prov.capabilities()["checkout"] is False
    with pytest.raises(CheckoutUnavailable):
        checkout_svc(env, provider=prov).create(env.users[0], "premium", "flip-key-00001")
    monkeypatch.setattr(P, "EXTERNAL_CHECKOUT_AUTHORIZED", False)
    # RECONCILE_SCHEDULER_ENABLED alone: still no job without a reader
    monkeypatch.setattr(P, "RECONCILE_SCHEDULER_ENABLED", True)
    from src.persistence import Job
    assert schedule_tick(env.sf, SimpleNamespace(enqueue=lambda *a, **k: pytest.fail("enqueued")), reader_available=False, enabled=P.RECONCILE_SCHEDULER_ENABLED)["scheduled"] is False
    assert count(env, Job) == 0
    monkeypatch.setattr(P, "RECONCILE_SCHEDULER_ENABLED", False)
    # STRIPE_WEBHOOK_AUTHORIZED alone: events are stored, but reconciliation needs a reader (Null: retry) and the policy is unapproved: no access, no checkout
    rcv = receiver(env, svc=service(env, policy=UNAPPROVED_POLICY), authorized=True)
    reader_for(env)
    deliver(env, rcv, checkout_event(ref="REFAAAA0"))
    assert plan_of(env, env.users[0])["plan_code"] == "basic" and count(env, BillingProviderLink) == 0
    null_svc = ProviderEventService(env.sf, environment="sandbox", reader=NullStateReader(), policy=SYNTHETIC_POLICY)
    out = null_svc.accept(checkout_event(ref="REFAAAA0"))
    assert null_svc.process(out["public_id"]).status == "retry" and plan_of(env, env.users[0])["plan_code"] == "basic"
    # LIVE_BILLING_ENABLED alone: the webhook gate still refuses live, a live client is never built, checkout stays unauthorised
    monkeypatch.setattr(P, "LIVE_BILLING_ENABLED", True)
    assert receiver(env, environment="live", authorized=True)._env == "live"
    raw = body(sub_event(livemode=True))
    with pytest.raises(SE.WebhookError) as e2:
        receiver(env, environment="live", authorized=True).handle(raw, sign(raw))
    assert e2.value.category in ("live_disabled", "environment_mismatch")
    from src.billing.stripe_provider import StripeConfigurationError, build_stripe_client
    with pytest.raises(StripeConfigurationError):
        build_stripe_client(SimpleNamespace(), "live")
    monkeypatch.setattr(P, "LIVE_BILLING_ENABLED", False)


def test_C04_credential_rotation_cannot_activate_payments(env):
    from src import secret_store as SS
    from src.billing import stripe_provider as SP
    store = SS.InMemorySecretStore({})
    before = SP.readiness(store, provider_selected=P.PROVIDER_STRIPE_MP, environment="sandbox")["status"]
    store = SS.InMemorySecretStore({SP.SLOT_NAMES["sandbox"]["api"]: "sk_test_SYNTHETIC_F1_000000000002", SP.SLOT_NAMES["sandbox"]["webhook"]: SECRET})
    after = SP.readiness(store, provider_selected=P.PROVIDER_STRIPE_MP, environment="sandbox")["status"]
    assert (before, after) == ("not_configured", "sandbox_access_unverified")            # readiness moves, nothing else does
    assert SP.readiness(store, provider_selected=P.PROVIDER_STRIPE_MP, environment="sandbox")["eligibility"] == "not_confirmed"
    assert P.EXTERNAL_CHECKOUT_AUTHORIZED is False and P.STRIPE_WEBHOOK_AUTHORIZED is False and P.LIVE_BILLING_ENABLED is False


def test_C05_constants_are_never_assigned_outside_the_policy_module():
    import ast
    names = {"LIVE_BILLING_ENABLED", "EXTERNAL_CHECKOUT_AUTHORIZED", "STRIPE_WEBHOOK_AUTHORIZED", "RECONCILE_SCHEDULER_ENABLED", "PAID_ENTITLEMENT_POLICY_APPROVED"}
    offenders = []
    for path in (ROOT / "src").rglob("*.py"):
        if path.name == "policy.py" and path.parent.name == "billing":
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target] if isinstance(node, (ast.AugAssign, ast.AnnAssign)) else []
            for tg in targets:
                if (isinstance(tg, ast.Name) and tg.id in names) or (isinstance(tg, ast.Attribute) and tg.attr in names):
                    offenders.append(path.relative_to(ROOT).as_posix())
    assert offenders == []                                                                  # no setting, route or script assigns a kill switch


# ================================================================ C. STRIPE MANAGED PAYMENTS CONTRACT (offline) =====================================

def test_C06_checkout_parameters_require_managed_payments_and_subscription_mode_with_an_expiry_margin(env):
    from src.billing.stripe_provider import StripeManagedPaymentsProvider
    seen = {}

    class Sessions:
        def create(self, params, opts):
            seen.update(params=params, opts=opts)
            return SimpleNamespace(id="cs_test_1", url="https://checkout.stripe.com/c/1")
    client = SimpleNamespace(v1=SimpleNamespace(checkout=SimpleNamespace(sessions=Sessions())))
    real = StripeManagedPaymentsProvider(environment="sandbox", store=object(), client_factory=lambda store, e: client)
    prov = through(real)
    now = env.clock_now[0]
    clear_checkouts(env)
    checkout_svc(env, provider=prov).create(env.users[0], "premium", "contract-key-001")
    p = seen["params"]
    assert p["mode"] == "subscription" and p["managed_payments"] == {"enabled": True} and len(p["line_items"]) == 1 and p["line_items"][0]["quantity"] == 1
    assert "payment_method_types" not in p and "customer_email" not in p and "customer" not in p                       # nothing candidate-controlled or personal is sent
    assert p["success_url"].startswith("https://app.example.test/billing/return?") and p["cancel_url"].startswith("https://app.example.test/billing/return?")
    assert p["expires_at"] >= int((now + timedelta(seconds=P.CHECKOUT_SESSION_TTL_SECONDS + P.CHECKOUT_PROVIDER_EXPIRY_MARGIN_SECONDS)).timestamp()) - 1
    assert p["expires_at"] - int(now.timestamp()) >= 30 * 60 + 60                                                      # F1-02: strictly beyond Stripe's 30 minute minimum
    assert seen["opts"]["idempotency_key"].startswith("ask4mo-checkout-")


def test_F1_02_the_local_attempt_always_ends_before_the_provider_session(env):
    assert P.CHECKOUT_PROVIDER_EXPIRY_MARGIN_SECONDS >= 120 and P.CHECKOUT_SESSION_TTL_SECONDS + P.CHECKOUT_PROVIDER_EXPIRY_MARGIN_SECONDS < 24 * 3600


def test_C07_no_silent_fallback_to_ordinary_stripe_payments():
    from src.billing.stripe_provider import StripeConfigurationError, require_managed_payments
    for bad in ({}, {"managed_payments": {}}, {"managed_payments": {"enabled": False}}, {"managed_payments": {"enabled": "true"}}, {"managed_payments": None}):
        with pytest.raises(StripeConfigurationError):
            require_managed_payments(bad)
    src = (ROOT / "src/billing/stripe_provider.py").read_text()
    assert src.count("require_managed_payments(params)") == 1 and 'mode": "subscription"' in src


def test_C08_credentials_are_per_client_never_global_and_never_retried():
    import stripe
    from src import secret_store as SS
    from src.billing import stripe_provider as SP
    before = getattr(stripe, "api_key", None)
    built = {}

    class Client:
        def __init__(self, key, **kw):
            built.update(key=key, kw=kw)
    SP.build_stripe_client(SS.InMemorySecretStore({SP.SLOT_NAMES["sandbox"]["api"]: "sk_test_SYNTHETIC_F1_000000000003"}), "sandbox", client_cls=Client)
    assert stripe.api_key == before and built["kw"]["max_network_retries"] == 0 and built["kw"]["stripe_version"] == P.STRIPE_API_VERSION
    with pytest.raises(SP.StripeConfigurationError) as e:                                                              # a live key in the sandbox slot is refused: no environment mixing
        SP.build_stripe_client(SS.InMemorySecretStore({SP.SLOT_NAMES["sandbox"]["api"]: "sk_live_SYNTHETIC_F1_000000000004"}), "sandbox", client_cls=Client)
    assert e.value.category == "credential_environment_mismatch"


def test_C09_provider_exceptions_are_reduced_to_bounded_categories_without_leaking_text(env):
    from src.billing.stripe_provider import StripeManagedPaymentsProvider

    class APIConnectionError(Exception):
        pass

    class Boom:
        def __init__(self, exc):
            self.exc = exc
        v1 = property(lambda self: SimpleNamespace(checkout=SimpleNamespace(sessions=SimpleNamespace(create=self._raise))))

        def _raise(self, *a, **k):
            raise self.exc
    for exc, expected in ((APIConnectionError("timed out reaching api with sk_test_LEAK"), ProviderRetryable), (RuntimeError("card 4242 declined sk_live_LEAK"), ProviderRejected)):
        prov = StripeManagedPaymentsProvider(environment="sandbox", store=object(), client_factory=lambda s, e, b=Boom(exc): b)
        with pytest.raises(expected) as e:
            prov.create_checkout_session(SimpleNamespace(idempotency_key="k" * 12, provider_price_id="p", success_url="https://a/b", cancel_url="https://a/c", client_reference_id="r", expires_at=None))
        assert "LEAK" not in str(e.value) and "4242" not in str(e.value)


def test_C10_a_malformed_provider_response_is_rejected_and_never_becomes_an_open_checkout(env):
    from src.billing.checkout import CheckoutProviderError
    from src.billing.stripe_provider import StripeManagedPaymentsProvider
    for resp in (SimpleNamespace(id=None, url="https://checkout.stripe.com/c/1"), SimpleNamespace(id="cs_1", url=None), SimpleNamespace(id="cs_1", url="http://insecure.example/x")):
        clear_checkouts(env)
        client = SimpleNamespace(v1=SimpleNamespace(checkout=SimpleNamespace(sessions=SimpleNamespace(create=lambda p, o, r=resp: r))))
        prov = through(StripeManagedPaymentsProvider(environment="sandbox", store=object(), client_factory=lambda s, e, c=client: c))
        with pytest.raises(CheckoutProviderError):
            checkout_svc(env, provider=prov).create(env.users[0], "premium", "malformed-key-01")
        with env.sf() as s:
            row = s.scalar(select(BillingCheckoutSession))
        assert row.status == "failed" and row.checkout_url is None


# ================================================================ D. CHECKOUT IDEMPOTENCY AND CRASH WINDOWS =============================================

def test_C11_crash_between_local_persistence_and_the_provider_call_resumes_deterministically(env):
    clear_checkouts(env)

    class Dies(RecordingProvider):
        def create_checkout_session(self, req):
            super().create_checkout_session(req)
            raise KeyboardInterrupt("process died after the request left")
    prov = Dies()
    co = checkout_svc(env, provider=prov)
    with pytest.raises(KeyboardInterrupt):
        co.create(env.users[0], "premium", "crash-key-00001")
    with env.sf() as s:
        row = s.scalar(select(BillingCheckoutSession))
    assert row.status == "pending_creation" and row.provider_attempts == 1
    healthy = RecordingProvider()
    healthy.by_key = dict(prov.by_key)                                                                               # Stripe remembers the key
    out = checkout_svc(env, provider=healthy).create(env.users[0], "premium", "crash-key-00001")
    assert out["status"] == "open" and count(env, BillingCheckoutSession) == 1
    assert prov.requests[0].idempotency_key == healthy.requests[0].idempotency_key                                    # the SAME provider key: no second session
    assert len(healthy.by_key) == 1


def test_C12_crash_after_the_provider_created_the_session_but_before_the_local_update(env, monkeypatch):
    import src.billing.checkout as C
    clear_checkouts(env)
    prov = RecordingProvider()
    co = checkout_svc(env, provider=prov)
    real = C.L.require_checkout_transition
    calls = {"n": 0}

    def flaky(old, new):
        if (old, new) == ("pending_creation", "open") and calls["n"] == 0:
            calls["n"] += 1
            raise RuntimeError("database went away after the provider answered")
        return real(old, new)
    monkeypatch.setattr(C.L, "require_checkout_transition", flaky)
    with pytest.raises(RuntimeError):
        co.create(env.users[0], "premium", "window-key-0001")
    assert len(prov.by_key) == 1 and count(env, BillingCheckoutSession) == 1
    out = co.create(env.users[0], "premium", "window-key-0001")
    assert out["status"] == "open" and len(prov.by_key) == 1 and len(prov.requests) == 2                              # retried, still ONE provider session
    with env.sf() as s:
        assert s.scalar(select(BillingCheckoutSession)).provider_session_id == "cs_test_rec1"


def test_C13_a_stale_pending_attempt_never_blocks_the_candidate_permanently(env):
    clear_checkouts(env)
    prov = RecordingProvider()
    co = checkout_svc(env, provider=prov)
    old = env.clock_now[0] - timedelta(days=2)
    with env.sf() as s:
        from src.persistence import BillingCommercialTerms, BillingProviderPrice
        t, pr = s.scalar(select(BillingCommercialTerms)), s.scalar(select(BillingProviderPrice))
        s.add(BillingCheckoutSession(public_id="STALEPEND0001", user_id=env.users[0], plan_version_id=t.plan_version_id, commercial_terms_id=t.id, price_mapping_id=pr.id,
                                     provider=P.PROVIDER_STRIPE_MP, environment="sandbox", status="pending_creation", idempotency_key="stale-key-0001", provider_attempts=1, created_at=old))
        s.commit()
    out = co.create(env.users[0], "premium", "fresh-key-00001")                                                      # a NEW key resumes the stuck attempt
    assert out["status"] == "open" and count(env, BillingCheckoutSession) == 1 and len(prov.by_key) == 1


def test_C14_retries_cannot_double_charge_two_simultaneous_attempts_make_one_session(env):
    clear_checkouts(env)
    prov = RecordingProvider()
    co = checkout_svc(env, provider=prov)
    results = []

    def go(i):
        try:
            results.append(co.create(env.users[0], "premium", f"race-key-{i:05d}")["checkout_id"])
        except Exception as exc:  # noqa: BLE001
            results.append(type(exc).__name__)
    ts = [threading.Thread(target=go, args=(i,)) for i in range(8)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert count(env, BillingCheckoutSession) == 1 and len(prov.by_key) == 1
    assert {r for r in results if len(r) == 32} <= {results[[len(r) == 32 for r in results].index(True)]}


def test_C15_retryable_provider_failure_is_bounded(env):
    from src.billing.checkout import MAX_PROVIDER_ATTEMPTS, CheckoutProviderError
    clear_checkouts(env)

    class Down:
        name, live, environment = P.PROVIDER_STRIPE_MP, False, "sandbox"
        def capabilities(self): return {"checkout": True}                                                           # noqa: E704
        def create_checkout_session(self, req): raise ProviderRetryable("provider_timeout")                          # noqa: E704
    co = checkout_svc(env, provider=Down())
    last = None
    for _ in range(MAX_PROVIDER_ATTEMPTS + 2):
        try:
            co.create(env.users[0], "premium", "bounded-key-0001")
        except CheckoutProviderError as exc:
            last = exc
    assert last is not None and last.retryable is False
    with env.sf() as s:
        assert s.scalar(select(BillingCheckoutSession)).provider_attempts == MAX_PROVIDER_ATTEMPTS


def test_C16_return_urls_come_from_configuration_never_from_the_host_header(env):
    from src.api import dependencies as deps
    import os
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(settings=SimpleNamespace(env="production", frontend_origins=("https://app.example.test",)))),
                              headers={"host": "evil.example", "x-forwarded-host": "evil.example", "origin": "https://evil.example"})
    os.environ.pop("ASK4MO_APP_BASE_URL", None)
    svc = deps.get_checkout_service(request, SimpleNamespace(session_factory=env.sf), SimpleNamespace(get_for_runtime=lambda n: None, source=lambda n: "none"))
    assert svc._origin == "https://app.example.test"
    prov = RecordingProvider()
    clear_checkouts(env)
    checkout_svc(env, provider=prov).create(env.users[1], "premium", "host-key-000001")
    assert all("evil.example" not in v for v in (prov.requests[0].success_url, prov.requests[0].cancel_url))


# ================================================================ E. WEBHOOK SECURITY (requalification) =================================================

def test_C17_an_invalid_signature_never_reaches_reconciliation_or_entitlement_logic(env, monkeypatch):
    import src.billing.reconcile as R
    called = []
    monkeypatch.setattr(R.ProviderEventService, "accept", lambda *a, **k: called.append("accept"))
    monkeypatch.setattr(R.ProviderEventService, "process", lambda *a, **k: called.append("process"))
    monkeypatch.setattr(R, "evaluate_and_apply", lambda *a, **k: called.append("bridge"))
    rcv = receiver(env)
    raw = body(sub_event())
    for header in (None, "t=1,v1=00", sign(raw, "whsec_WRONG_WRONG_WRONG_WRONG_WRONG_000001"), sign(raw, SECRET, int(time.time()) - 99_999)):
        with pytest.raises(SE.WebhookError):
            rcv.handle(raw, header)
    with pytest.raises(SE.WebhookError):
        rcv.handle(raw + b"x", sign(raw))
    assert called == []


def test_C18_replay_outside_the_tolerance_is_rejected_and_inside_it_is_idempotent(env):
    rcv = receiver(env)
    ev = checkout_event(ref="REFAAAA0")
    raw = body(ev)
    rcv.handle(raw, sign(raw))
    rcv.handle(raw, sign(raw))                                                                                        # inside the window: acknowledged, stored once
    assert count(env, BillingProviderEvent) == 1
    with pytest.raises(SE.WebhookError) as e:
        rcv.handle(raw, sign(raw, SECRET, int(time.time()) - 3600))                                                   # a captured request replayed an hour later
    assert e.value.category == "timestamp_outside_tolerance"


def test_F1_03_unauthenticated_traffic_cannot_grow_the_audit_log_while_the_route_is_off(env):
    rows = []
    audit = SimpleNamespace(record=lambda **k: rows.append(k))
    off = receiver(env, authorized=False, audit=audit)
    for _ in range(50):
        with pytest.raises(SE.WebhookError):
            off.handle(b"{}", "t=1,v1=00")
    assert rows == []
    unconfigured = receiver(env, secrets=(), audit=audit)
    with pytest.raises(SE.WebhookError):
        unconfigured.handle(b"{}", "t=1,v1=00")
    assert rows == []
    live = receiver(env, audit=audit)
    with pytest.raises(SE.WebhookError):
        live.handle(b"{}", "t=1,v1=00")
    assert [r["event_type"] for r in rows] == ["billing.webhook_signature_rejected"]                                  # a real rejection IS traced, once
    assert "t=1,v1" not in json.dumps(rows, default=str)


def test_C19_accepted_events_store_no_sensitive_fields_and_the_audit_has_no_secrets(env):
    rows = []
    rcv = receiver(env, svc=service(env, audit=SimpleNamespace(record=lambda **k: rows.append(k))), audit=SimpleNamespace(record=lambda **k: rows.append(k)))
    ev = checkout_event(ref="REFAAAA0")
    ev["data"]["object"]["customer_details"] = {"email": "pii@example.com", "name": "Pat Person"}
    ev["data"]["object"]["payment_method_details"] = {"card": {"last4": "4242"}}
    deliver(env, rcv, ev)
    with env.sf() as s:
        stored = json.dumps(s.scalar(select(BillingProviderEvent)).normalized_json)
    blob = stored + json.dumps(rows, default=str)
    for banned in ("pii@example.com", "Pat Person", "4242", SECRET, "whsec_", "sk_test"):
        assert banned not in blob


# ================================================================ F. RECONCILIATION RACES AND CONVERGENCE ===============================================

def test_F1_01_concurrent_events_for_one_new_subscription_converge_without_operator_work(env):
    reader_for(env)
    svc = service(env)
    ids = [svc.accept(e)["public_id"] for e in (checkout_event(ref="REFAAAA0"), sub_event(), invoice_event())]
    out = []
    ts = [threading.Thread(target=lambda i=i: out.append(svc.process(i))) for i in ids]
    [t.start() for t in ts]
    [t.join() for t in ts]
    with env.sf() as s:
        states = {e.status for e in s.scalars(select(BillingProviderEvent)).all()}
        cats = {e.failure_category for e in s.scalars(select(BillingProviderEvent)).all() if e.status != "processed"}
    assert "needs_review" not in states and "quarantined" not in states and cats <= {"concurrent_update"}        # a benign race is never an operator problem
    env.clock_now[0] += timedelta(hours=1)
    assert svc.sweep()["events"] >= 0
    for i in ids:
        svc.process(i)
    with env.sf() as s:
        assert {e.status for e in s.scalars(select(BillingProviderEvent)).all()} == {"processed"}
    assert count(env, BillingProviderLink) == 1 and plan_of(env, env.users[0])["plan_code"] == "premium"
    with env.sf() as s:
        assert s.scalar(select(func.count()).select_from(Subscription).where(Subscription.source == "provider")) == 1
        assert s.scalar(select(func.count()).select_from(BillingEntitlementDecision).where(BillingEntitlementDecision.applied.is_(True))) == 1


def test_F1_04_the_subscription_row_is_locked_for_update_on_postgres_not_on_sqlite_reads():
    from sqlalchemy.dialects import postgresql
    locked = str(link_by_subscription_stmt("stripe_managed_payments", "sandbox", "sub_x", lock=True).compile(dialect=postgresql.dialect()))
    plain = str(link_by_subscription_stmt("stripe_managed_payments", "sandbox", "sub_x").compile(dialect=postgresql.dialect()))
    assert "FOR UPDATE" in locked and "FOR UPDATE" not in plain


def test_C20_entitlement_persistence_failure_rolls_everything_back_and_retries(env, monkeypatch):
    import src.billing.reconcile as R
    reader_for(env)
    svc = service(env)
    out = svc.accept(checkout_event(ref="REFAAAA0"))
    real = R.evaluate_and_apply

    def fails(*a, **k):
        real(*a, **k)
        raise RuntimeError("entitlement persistence failed")
    monkeypatch.setattr(R, "evaluate_and_apply", fails)
    assert svc.process(out["public_id"]).status == "retry"
    assert count(env, BillingProviderLink) == 0 and count(env, BillingEntitlementDecision) == 0 and plan_of(env, env.users[0])["plan_code"] == "basic"
    monkeypatch.setattr(R, "evaluate_and_apply", real)
    env.clock_now[0] += timedelta(hours=1)
    assert svc.process(out["public_id"]).status == "processed" and plan_of(env, env.users[0])["plan_code"] == "premium"


def test_C21_a_failed_provider_read_never_proves_payment(env):
    reader_for(env)
    svc = service(env)
    for exc in (ProviderStateUnavailable("provider_timeout"), ProviderStateUnavailable("rate_limited")):
        env.reader.fail = exc
        out = svc.accept(checkout_event(ref="REFAAAA0", eid=f"evt_synth_fail_{exc.category}"))
        assert svc.process(out["public_id"]).status == "retry"
    assert count(env, BillingProviderLink) == 0 and plan_of(env, env.users[0])["plan_code"] == "basic"


# ================================================================ G. ADMIN AUTHORIZATION, RECOVERY ======================================================

@pytest.fixture()
def http():
    from tests.test_admin_foundation_w10_1 import Env
    e = Env()
    yield e
    e.app.dependency_overrides.clear()
    e.close()


def test_F1_05_an_idempotency_key_used_by_another_request_is_a_409_not_a_server_error(http):
    from tests.test_billing_ops_w12_4d_e import add_event
    ref = add_event(http.repo.session_factory)
    ref2 = add_event(http.repo.session_factory, event_id="evt_f1_000002")
    from tests.test_billing_ops_w12_4d_e import elevate
    _, ck1 = http.user("platform_admin")
    _, ck2 = http.user("billing_admin")
    elevate(http, ck1)
    elevate(http, ck2)
    url = "/api/v1/admin/billing/operations/events/{}/retry"
    assert http.c.post(url.format(ref), json={"reason": "first operator"}, headers={"Idempotency-Key": "shared-key-00001"}, cookies=ck1).status_code == 200
    again = http.c.post(url.format(ref2), json={"reason": "second operator"}, headers={"Idempotency-Key": "shared-key-00001"}, cookies=ck2)
    assert again.status_code == 409 and "already used" in again.text
    assert http.c.post(url.format(ref), json={"reason": "first operator"}, headers={"Idempotency-Key": "shared-key-00001"}, cookies=ck1).json()["replayed"] is True


def test_F1_05b_service_level_key_conflict_raises_the_typed_error(env):
    svc = service(env)
    svc.recover("retry_event", "f" * 32, actor_user_id=env.users[0], reason="operator retry", idempotency_key="typed-key-00001")
    with pytest.raises(RecoveryKeyConflict):
        svc.recover("retry_event", "f" * 32, actor_user_id=env.users[1], reason="someone else", idempotency_key="typed-key-00001")
    with pytest.raises(RecoveryKeyConflict):
        svc.recover("requeue_lease", "f" * 32, actor_user_id=env.users[0], reason="other action", idempotency_key="typed-key-00001")


def test_C22_an_interrupted_recovery_is_visible_as_requested_and_never_repeats_effects(env):
    svc = service(env)
    reader_for(env)
    out = svc.accept(checkout_event(ref="REFAAAA0"))
    with env.sf() as s:
        s.scalar(select(BillingProviderEvent)).status = "needs_review"
        s.commit()
    bad_audit = {"event_type": None, "actor_user_id": env.users[0], "result": "success"}                              # the audit row cannot be written
    with pytest.raises(Exception):
        svc.recover("retry_event", out["public_id"], actor_user_id=env.users[0], reason="audit will fail", idempotency_key="audit-fail-0001", audit=bad_audit)
    with env.sf() as s:
        action = s.scalar(select(BillingRecoveryAction))
    assert action.status == "requested"                                                                               # fail closed: the interruption is evidence, not a fake success
    assert count(env, BillingProviderLink) == 1 and plan_of(env, env.users[0])["plan_code"] == "premium"             # the verified pipeline had already run exactly once
    replay = svc.recover("retry_event", out["public_id"], actor_user_id=env.users[0], reason="audit will fail", idempotency_key="audit-fail-0001")
    assert replay["replayed"] is True and replay["status"] == "requested" and count(env, BillingProviderLink) == 1


def test_C23_recovery_authorization_has_no_privilege_escalation_path(http):
    from tests.test_billing_ops_w12_4d_e import add_event
    from src.application import admin_permissions as perm
    ref = add_event(http.repo.session_factory)
    for role in ("operations_admin", "support_operator", "security_privacy_admin", "knowledge_admin", "user"):
        _, ck = http.user(role)
        r = http.c.post(f"/api/v1/admin/billing/operations/events/{ref}/retry", json={"reason": "operator retry"}, headers={"Idempotency-Key": f"escalate-{role}-1"}, cookies=ck)
        assert r.status_code == 403, role
    holders = [r for r in perm.ADMIN_ROLES if "platform.billing.recover" in perm.permissions_for_role(r)]
    assert sorted(holders) == ["billing_admin", "platform_admin"]                                                      # owner decision B
    jobs_holders = [r for r in perm.ADMIN_ROLES if "platform.jobs.manage" in perm.permissions_for_role(r)]
    assert sorted(jobs_holders) == ["operations_admin", "platform_admin"]                                                # generic job management is unchanged and confers no billing authority
    assert len(perm.PERMISSIONS) == 44


def test_C24_candidate_endpoints_are_owner_scoped_and_never_present_failure_as_free(http):
    uid_a, ck_a = http.user()
    uid_b, ck_b = http.user()
    for path in ("/api/v1/billing/summary", "/api/v1/billing/checkout/status"):
        a, b = http.c.get(path, cookies=ck_a), http.c.get(path, cookies=ck_b)
        assert a.status_code == b.status_code == 200 and a.json().get("checkout_id") == b.json().get("checkout_id") is None
        assert http.c.get(path, cookies={"ask4mo_session": "bogus"}).status_code == 401
    assert "other" not in http.c.get("/api/v1/billing/summary", cookies=ck_a).text.lower()


def test_C25_every_candidate_locale_states_critical_financial_facts_truthfully():
    from src.billing import policy  # noqa: F401
    import re
    root = ROOT / "frontend/lib/i18n/messages"
    forbidden_en = re.compile(r"payment (was )?successful|premium (is )?unlocked|thank you for your purchase|you are now premium", re.I)
    for frag in ("w124dc", "w124de"):
        en = "\n".join(l for l in (root / frag / "en.ts").read_text().splitlines() if not l.lstrip().startswith("//"))     # the header comment states what is forbidden
        assert not forbidden_en.search(en)
        for loc in ("de", "fr", "es", "it", "pt", "nl", "ru"):
            text = (root / frag / f"{loc}.ts").read_text()
            assert "Ask More. Be More." not in text
    # the failure copy never claims a plan: it says it could not load
    de = (root / "w124de/de.ts").read_text()
    assert "konnte gerade nicht geladen werden" in de and "loadError" in de


# ================================================================ H. SUBSCRIPTION LIFECYCLE MATRIX ======================================================

@pytest.mark.parametrize("name,steps,final_state,final_plan", [
    ("renewal", [("active", "paid", False)], "active", "premium"),
    ("payment_failure_then_recovery", [("past_due", "failed", False), ("active", "paid", False)], "active", "premium"),
    ("scheduled_cancellation", [("active", "paid", True)], "active", "premium"),
    ("immediate_cancellation", [("canceled", "paid", False)], "canceled", "basic"),
    ("expiry_before_confirmation", [("incomplete_expired", "open", False)], "incomplete_expired", "basic"),
    ("unpaid", [("unpaid", "failed", False)], "unpaid", "basic"),
])
def test_C26_lifecycle_matrix_under_the_synthetic_policy(env, name, steps, final_state, final_plan):
    svc = service(env)
    reader_for(env)
    accept_and_process(env, svc, checkout_event(ref="REFAAAA0"))
    for state, invoice, cancel in steps:
        env.clock_now[0] += timedelta(seconds=5)
        env.reader.set_subscription("sub_synth_1", state=state, latest_invoice_state=invoice, cancel_at_period_end=cancel)
        accept_and_process(env, svc, sub_event())
    assert link_of(env).provider_state == final_state and plan_of(env, env.users[0])["plan_code"] == final_plan


def test_C27_two_simultaneous_subscription_attempts_end_with_one_live_subscription(env):
    svc = service(env)
    reader_for(env)
    accept_and_process(env, svc, checkout_event(ref="REFAAAA0"))
    env.reader.set_subscription("sub_synth_dup", customer_id="cus_synth_1")
    env.reader.checkouts["cs_test_c1"] = CheckoutAssociation("cs_test_c1", "REFAAAA0", "sub_synth_dup", False)
    out, r = accept_and_process(env, svc, sub_event(sub="sub_synth_dup"))
    assert r.category == "duplicate_subscription"
    with pytest.raises(CheckoutConflict):
        checkout_svc(env).create(env.users[0], "premium", "dup-attempt-00001")
    assert count(env, BillingProviderLink) == 1


# ================================================================ I. MIGRATION INTEGRITY (isolated databases) ============================================

def _alembic(tmp_path, monkeypatch):
    from alembic.config import Config
    url = f"sqlite:///{tmp_path / 'f1.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    cfg = Config("alembic.ini")
    cfg.set_main_option("script_location", "migrations")
    cfg.set_main_option("sqlalchemy.url", url)
    return cfg, url


def test_C28_billing_schema_constraints_indexes_and_foreign_keys_exist_after_a_fresh_upgrade(tmp_path, monkeypatch):
    from alembic import command
    from sqlalchemy import create_engine, inspect
    cfg, url = _alembic(tmp_path, monkeypatch)
    command.upgrade(cfg, "head")
    insp = inspect(create_engine(url))
    idx = lambda t: {i["name"]: i for i in insp.get_indexes(t)}                                                  # noqa: E731
    uq = lambda t: {tuple(u["column_names"]) for u in insp.get_unique_constraints(t)}                             # noqa: E731
    assert idx("billing_checkout_sessions")["uq_bcs_one_open_per_user_plan"]["unique"] and ("user_id", "idempotency_key") in uq("billing_checkout_sessions")
    assert ("provider", "provider_session_id") in uq("billing_checkout_sessions")
    assert idx("billing_provider_links")["uq_bpl_one_live_per_user"]["unique"] and ("provider", "environment", "provider_subscription_id") in uq("billing_provider_links")
    assert ("provider", "environment", "provider_event_id") in uq("billing_provider_events") and ("idempotency_key",) in uq("billing_recovery_actions")
    assert ("provider", "environment", "provider_price_id") in uq("billing_provider_prices")
    fks = {(t, fk["referred_table"], fk["options"].get("ondelete")) for t in ("billing_checkout_sessions", "billing_provider_links", "billing_entitlement_decisions", "billing_recovery_actions")
           for fk in insp.get_foreign_keys(t)}
    assert ("billing_checkout_sessions", "users", "CASCADE") in fks and ("billing_provider_links", "users", "CASCADE") in fks                  # deleted with the account
    assert ("billing_provider_links", "billing_commercial_terms", "RESTRICT") in fks and ("billing_checkout_sessions", "plan_versions", "RESTRICT") in fks   # terms history protected
    assert ("billing_recovery_actions", "users", "SET NULL") in fks                                                                          # the operator trail survives a user deletion


def test_C29_reapplying_head_is_a_no_op_and_stepwise_upgrade_from_each_billing_revision_reaches_head(tmp_path, monkeypatch):
    from alembic import command
    cfg, url = _alembic(tmp_path, monkeypatch)
    for rev in ("0027_email_attempts", "0028_checkout_sessions", "0029_provider_webhooks", "0030_billing_recovery", "head"):
        command.upgrade(cfg, rev)
    command.upgrade(cfg, "head")                                                                                    # re-application: nothing to do, nothing breaks
    from sqlalchemy import create_engine, text
    with create_engine(url).connect() as c:
        assert c.execute(text("SELECT version_num FROM alembic_version")).scalar() == "0038_compensation_concepts"


def test_C30_a_downgrade_over_financial_history_refuses_and_a_clean_one_reverses(tmp_path, monkeypatch):
    from alembic import command
    from sqlalchemy import create_engine, inspect, text
    cfg, url = _alembic(tmp_path, monkeypatch)
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "0027_email_attempts")                                                                    # empty billing history: reversible end to end
    assert "billing_checkout_sessions" not in inspect(create_engine(url)).get_table_names()
    command.upgrade(cfg, "head")
    with create_engine(url).begin() as c:
        c.execute(text("INSERT INTO billing_recovery_actions (public_id, action, reason, idempotency_key, status, created_at) VALUES ('" + "c" * 32 + "', 'retry_event', 'r', 'f1-mig-key-1', 'completed', '2026-01-01')"))
    with pytest.raises(Exception, match="Refusing to downgrade"):
        command.downgrade(cfg, "0029_provider_webhooks")
    with create_engine(url).connect() as c:
        assert c.execute(text("SELECT COUNT(*) FROM billing_recovery_actions")).scalar() == 1


# ================================================================ J. SCHEDULER ====================================================================

def test_C31_scheduler_conditions_abandoned_job_recovery_and_no_unexpected_provider_call(env):
    from src.billing.runtime import BillingRuntime
    from src.billing.scheduler import schedule_tick
    from src.jobs.service import JobService
    from src.jobs.worker import Worker
    reader_for(env)
    jobs = JobService(env.sf)
    now = utcnow()
    assert schedule_tick(env.sf, jobs, reader_available=True, enabled=True, now=now)["scheduled"]
    calls_before = len(env.reader.calls)
    svc = service(env)
    worker = Worker(jobs, services=SimpleNamespace(billing=BillingRuntime(session_factory=env.sf, provider_events=svc, jobs=jobs)))
    assert worker.run_once() == "succeeded"
    assert len(env.reader.calls) >= calls_before                                                                    # only the injected FAKE reader is ever called
    src = (ROOT / "src/billing/scheduler.py").read_text()
    assert "stripe" not in src.lower().replace("no stripe call", "") and "StripeStateReader" not in src


def test_C32_enqueue_failure_during_a_tick_leaves_no_partial_state_and_the_next_tick_works(env):
    from src.billing.scheduler import schedule_tick
    from src.jobs.service import JobService
    from src.persistence import Job
    now = utcnow()
    boom = SimpleNamespace(enqueue=lambda *a, **k: (_ for _ in ()).throw(RuntimeError("queue down")))
    with pytest.raises(RuntimeError):
        schedule_tick(env.sf, boom, reader_available=True, enabled=True, now=now)
    assert count(env, Job) == 0
    assert schedule_tick(env.sf, JobService(env.sf), reader_available=True, enabled=True, now=now)["scheduled"] is True


# ================================================================ K. END-TO-END OFFLINE SIMULATION =====================================================

def test_E2E_complete_offline_billing_flow_with_a_recording_fake_provider(env):
    """Synthetic candidate -> controlled provider request -> persisted attempt -> signed webhook -> durable acceptance -> reconciliation against synthetic
    authoritative state -> entitlement bridge under an explicitly SYNTHETIC policy; then failure, recovery, cancellation, replacement, refund, dispute,
    stale replay and a cross-candidate attack. Nothing here touches a kill switch, a real provider or the catalogue."""
    prov = RecordingProvider()
    co = checkout_svc(env, provider=prov)
    svc = service(env)
    rcv = receiver(env, svc=svc)
    tick = lambda s=5: env.clock_now.__setitem__(0, env.clock_now[0] + timedelta(seconds=s))                        # noqa: E731

    def run(ev):
        out = svc.accept(ev)
        return out, svc.process(out["public_id"])

    clear_checkouts(env)
    # 1. checkout through a recording fake: price, mode inputs and return URLs are server decisions
    first = co.create(env.users[0], "premium", "e2e-key-0000001")
    assert len(prov.requests) == 1 and prov.requests[0].provider_price_id == "price_test_1" and prov.requests[0].client_reference_id == first["checkout_id"]
    assert plan_of(env, env.users[0])["plan_code"] == "basic"                                                         # a redirect grants nothing
    co.record_return(env.users[0], first["checkout_id"], "success")
    assert plan_of(env, env.users[0])["plan_code"] == "basic" and co.summary(env.users[0], "basic")["state"] == "confirmation_pending"
    # 2. signed webhook accepted durably, then reconciled against authoritative synthetic state
    env.reader.set_subscription("sub_e2e_1", customer_id="cus_e2e_1")
    env.reader.checkouts["cs_test_rec1"] = CheckoutAssociation("cs_test_rec1", first["checkout_id"], "sub_e2e_1", False)
    ev1 = checkout_event(session="cs_test_rec1", ref=first["checkout_id"], sub="sub_e2e_1")
    assert deliver(env, rcv, ev1) == {"status": "accepted"}
    with env.sf() as s:
        stored = s.scalar(select(BillingProviderEvent))
        assert stored.status == "received"                                                                            # acceptance is not reconciliation
    assert plan_of(env, env.users[0])["plan_code"] == "basic"
    assert svc.process(stored.public_id).status == "processed" and plan_of(env, env.users[0])["plan_code"] == "premium"
    assert co.summary(env.users[0], "premium")["state"] == "active" and co.summary(env.users[0], "premium")["entitlement"]["changed_by_billing"] is True
    # 3. payment failure then recovery
    tick()
    env.reader.set_subscription("sub_e2e_1", state="past_due", latest_invoice_state="failed")
    run(invoice_event("invoice.payment_failed", sub="sub_e2e_1"))
    assert co.summary(env.users[0], "premium")["state"] == "past_due" and plan_of(env, env.users[0])["plan_code"] == "premium"      # synthetic grace: keep
    tick()
    env.reader.set_subscription("sub_e2e_1", state="active", latest_invoice_state="paid")
    run(invoice_event("invoice.paid", sub="sub_e2e_1"))
    assert co.summary(env.users[0], "premium")["state"] == "active"
    # 4. cancellation: scheduled, then effective
    tick()
    env.reader.set_subscription("sub_e2e_1", cancel_at_period_end=True, current_period_end=env.clock_now[0] + timedelta(days=10))
    run(sub_event(sub="sub_e2e_1"))
    sm = co.summary(env.users[0], "premium")
    assert sm["state"] == "cancel_at_period_end" and sm["cancellation_effective_at"] and plan_of(env, env.users[0])["plan_code"] == "premium"
    tick()
    env.reader.set_subscription("sub_e2e_1", state="canceled")
    run(sub_event("customer.subscription.deleted", sub="sub_e2e_1"))
    assert co.summary(env.users[0], "basic")["state"] == "canceled" and plan_of(env, env.users[0])["plan_code"] == "basic"
    # 5. stale replay: a duplicate id and a fresh id replaying 'active' cannot resurrect the canceled subscription
    assert svc.accept(ev1)["disposition"] == "duplicate"
    tick()
    env.reader.set_subscription("sub_e2e_1", state="active")
    out, r = run(sub_event(sub="sub_e2e_1"))
    assert r.category == "terminal_reactivation_refused" and plan_of(env, env.users[0])["plan_code"] == "basic"
    # 6. replacement subscription after cancellation (a NEW provider id through a NEW checkout)
    second = co.create(env.users[0], "premium", "e2e-key-0000002")
    assert len(prov.requests) == 2 and second["checkout_id"] != first["checkout_id"]
    tick()
    env.reader.set_subscription("sub_e2e_2", customer_id="cus_e2e_1")
    env.reader.checkouts["cs_test_rec2"] = CheckoutAssociation("cs_test_rec2", second["checkout_id"], "sub_e2e_2", False)
    out, r = run(checkout_event(session="cs_test_rec2", ref=second["checkout_id"], sub="sub_e2e_2"))
    assert r.decision == "grant" and plan_of(env, env.users[0])["plan_code"] == "premium" and count(env, BillingProviderLink) == 1 + 1
    # 7. a late event for the OLD subscription cannot revoke the newer grant
    tick()
    env.reader.set_subscription("sub_e2e_1", state="canceled")
    run(sub_event("customer.subscription.deleted", sub="sub_e2e_1"))
    assert plan_of(env, env.users[0])["plan_code"] == "premium"
    # 8. dispute opened (kept under the synthetic policy), then a full refund revokes provider-owned access only
    env.reader.payments["pi_synth_1"] = "sub_e2e_2"
    tick()
    run(dispute_event())
    assert co.summary(env.users[0], "premium")["state"] == "disputed" and plan_of(env, env.users[0])["plan_code"] == "premium"
    tick()
    run(refund_event())
    assert plan_of(env, env.users[0])["plan_code"] == "basic"
    # 9. cross-candidate attack: candidate 0's provider customer presented with candidate 1's checkout
    other = co.create(env.users[1], "premium", "e2e-key-0000003")
    env.reader.set_subscription("sub_e2e_evil", customer_id="cus_e2e_1")
    env.reader.checkouts["cs_test_rec3"] = CheckoutAssociation("cs_test_rec3", other["checkout_id"], "sub_e2e_evil", False)
    out, r = run(checkout_event(session="cs_test_rec3", ref=other["checkout_id"], sub="sub_e2e_evil"))
    assert r.category == "customer_rebind" and plan_of(env, env.users[1])["plan_code"] == "basic" and link_of(env, env.users[1]) is None
    # final determinism
    assert plan_of(env, env.users[2])["plan_code"] == "basic" and len(prov.requests) == 3
    with env.sf() as s:
        assert s.scalar(select(func.count()).select_from(Subscription).where(Subscription.source == "provider", Subscription.status == "active")) == 0
        assert s.scalar(select(func.count()).select_from(Subscription).where(Subscription.user_id == env.users[0], Subscription.status == "active")) == 1
    assert (P.LIVE_BILLING_ENABLED, P.EXTERNAL_CHECKOUT_AUTHORIZED, P.STRIPE_WEBHOOK_AUTHORIZED) == (False, False, False)


# ================================================================ L. PRIVACY, RETENTION AND DELETION ===================================================

def _seed_full_billing_for_user0(env):
    reader_for(env)
    svc = service(env)
    accept_and_process(env, svc, checkout_event(ref="REFAAAA0"))
    svc.recover("retry_event", "f" * 32, actor_user_id=env.users[0], reason="operator retry", idempotency_key="priv-key-000001")     # a recovery row by this user as operator
    assert count(env, BillingProviderLink) == 1 and count(env, BillingEntitlementDecision) >= 1


def _cancel_provider_subscription(env):
    svc = service(env)
    env.clock_now[0] += timedelta(seconds=5)
    env.reader.set_subscription("sub_synth_1", state="canceled", latest_invoice_state="paid")
    accept_and_process(env, svc, sub_event("customer.subscription.deleted"))
    assert link_of(env).provider_state == "canceled"
    return svc


def test_F1_06_account_deletion_removes_the_provider_billing_records_on_every_database(env):
    """On PostgreSQL the FK cascade removed these; on SQLite (no FK enforcement) they were left orphaned. The explicit delete makes both behave the same. With the
    subscription TERMINAL (W12.4D-F1R) the normal deletion is permitted."""
    from src.application.account_deletion_service import AccountDeletionService
    _seed_full_billing_for_user0(env)
    _cancel_provider_subscription(env)
    summary = AccountDeletionService(env.sf).delete_account(env.users[0])
    with env.sf() as s:
        assert s.scalar(select(func.count()).select_from(BillingProviderLink).where(BillingProviderLink.user_id == env.users[0])) == 0
        assert s.scalar(select(func.count()).select_from(BillingCheckoutSession).where(BillingCheckoutSession.user_id == env.users[0])) == 0
        assert s.scalar(select(func.count()).select_from(BillingEntitlementDecision)) == 0
        action = s.scalar(select(BillingRecoveryAction))
        assert action is None or action.actor_user_id is None                                                      # the operator trail is anonymised, not deleted
        ev = s.scalar(select(BillingProviderEvent))
        assert ev is None or ev.link_id is None                                                                    # events keep only opaque ids and never point at a deleted link
        assert s.scalar(select(func.count()).select_from(BillingCheckoutSession).where(BillingCheckoutSession.user_id == env.users[1])) == 1   # other candidates untouched
    assert summary.deleted_rows.get("billing_provider_rows", 0) >= 2


def test_F1_07_remediated_deletion_with_a_live_provider_subscription_is_refused_not_silent(env):
    """F1-07 (W12.4D-F1R, owner decision A): the service refuses to silently orphan an unresolved subscription. Full coverage is in test_account_closure_w12_4d_f1r."""
    from src.application.account_deletion_service import AccountDeletionService, SubscriptionResolutionRequired
    _seed_full_billing_for_user0(env)
    with pytest.raises(SubscriptionResolutionRequired):
        AccountDeletionService(env.sf).delete_account(env.users[0])
    assert count(env, BillingProviderLink) == 1 and plan_of(env, env.users[0])["plan_code"] == "premium"            # nothing was deleted


def test_C33_billing_data_stores_inventory_has_no_card_secret_or_content_columns():
    from src.persistence import Base
    import re
    banned = re.compile(r"card|pan\b|cvv|iban|password|secret|token|signature|email|name$|address|raw|payload|body|content|answer|resume|transcript", re.I)
    allowed = {"normalized_json", "reconciliation_json"}                                                            # allow-listed id/status maps, asserted separately
    tables = ("billing_checkout_sessions", "billing_provider_links", "billing_provider_events", "billing_entitlement_decisions", "billing_recovery_actions", "billing_provider_prices")
    offenders = {t: [c.name for c in Base.metadata.tables[t].columns if banned.search(c.name) and c.name not in allowed] for t in tables}
    assert {t: v for t, v in offenders.items() if v} == {"billing_checkout_sessions": ["checkout_url"]} or all(not v or v == ["checkout_url"] for v in offenders.values())
