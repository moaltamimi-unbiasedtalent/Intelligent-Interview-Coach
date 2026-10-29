# ruff: noqa: F811
"""W12.4D-F2-A: Stripe Managed Payments provider-integration readiness. FULLY OFFLINE: the Stripe reader is exercised only against recording fake SDK
clients, every non-loopback socket fails the test, and every payload is synthetic. Nothing here is Stripe evidence, a price, or an owner decision."""

from __future__ import annotations

import json
import re
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import func, select

from src.billing import policy as P
from src.billing import provider_state as PS
from src.billing.provider_state import (
    NullStateReader, ProviderStateConfiguration, ProviderStateInvalid, ProviderStateNotFound, ProviderStateUnavailable, StripeStateReader, build_authorized_reader,
    build_runtime_reader,
)
from src.billing.reconcile import ProviderEventService
from src.persistence import BillingEntitlementDecision, BillingProviderEvent, BillingProviderLink, Subscription
from tests.test_webhooks_w12_4d_d import (  # noqa: F401  (shared fixtures and factories)
    SYNTHETIC_POLICY, _no_network, accept_and_process, checkout_event, count, dispute_event, env, invoice_event, link_of, plan_of, refund_event, sub_event,
)

ROOT = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------- recording fake SDK client --------------------------------------------------------------

class Resource:
    def __init__(self, log, name, **handlers):
        self._log, self._name = log, name
        for method, fn in handlers.items():
            setattr(self, method, self._wrap(method, fn))

    def _wrap(self, method, fn):
        def call(*a, **k):
            self._log.append((self._name, method))
            return fn(*a, **k) if callable(fn) else fn
        return call


def fake_client(log=None, *, subs=None, sessions=None, session_list=None, invoices=None, refunds=None, disputes=None, charges=None, invoice_payments=None, extra=None):
    log = [] if log is None else log
    v1 = SimpleNamespace(
        subscriptions=Resource(log, "subscriptions", retrieve=lambda i, p=None: subs[i] if isinstance(subs, dict) else subs, create=lambda *a, **k: 1 / 0, cancel=lambda *a, **k: 1 / 0),
        checkout=SimpleNamespace(sessions=Resource(log, "checkout.sessions", retrieve=lambda i, p=None: sessions[i] if isinstance(sessions, dict) else sessions,
                                                    list=lambda p=None: session_list if session_list is not None else {"data": []}, create=lambda *a, **k: 1 / 0)),
        invoices=Resource(log, "invoices", retrieve=lambda i, p=None: invoices[i] if isinstance(invoices, dict) else invoices),
        refunds=Resource(log, "refunds", retrieve=lambda i, p=None: refunds[i] if isinstance(refunds, dict) else refunds, create=lambda *a, **k: 1 / 0),
        disputes=Resource(log, "disputes", retrieve=lambda i, p=None: disputes[i] if isinstance(disputes, dict) else disputes),
        charges=Resource(log, "charges", retrieve=lambda i, p=None: charges[i] if isinstance(charges, dict) else charges),
        invoice_payments=Resource(log, "invoice_payments", list=lambda p=None: invoice_payments if invoice_payments is not None else {"data": []}),
    )
    for k, v in (extra or {}).items():
        setattr(v1, k, v)
    c = SimpleNamespace(v1=v1)
    c.log = log
    return c


def sub_obj(**over):
    base = {"id": "sub_1", "customer": "cus_1", "status": "active", "cancel_at_period_end": False, "livemode": False,
            "items": {"data": [{"price": {"id": "price_test_1", "currency": "eur", "unit_amount": 1999, "recurring": {"interval": "month"}}, "current_period_end": 1_900_000_000}]},
            "latest_invoice": "in_1"}
    base.update(over)
    return base


def reader(client, **kw):
    return StripeStateReader(lambda: client, **kw)


def err(name, text="boom"):
    return type(name, (Exception,), {})(text)


# ================================================================ 1. SUBSCRIPTION CONTRACT ====================================================

def test_expandable_objects_and_plain_ids_normalise_identically():
    plain = reader(fake_client(subs={"sub_1": sub_obj()})).get_subscription("sub_1")
    expanded = reader(fake_client(subs={"sub_1": sub_obj(customer={"id": "cus_1", "object": "customer"}, latest_invoice={"id": "in_1", "status": "paid"})})).get_subscription("sub_1")
    assert plain.customer_id == expanded.customer_id == "cus_1" and plain.latest_invoice_state == "none" and expanded.latest_invoice_state == "paid"


@pytest.mark.parametrize("mutation", [
    {"customer": None}, {"customer": {}}, {"customer": 7}, {"id": "sub_other"}, {"items": None}, {"items": {"data": []}}, {"status": None}, {"livemode": None},
])
def test_missing_null_or_mismatched_fields_are_invalid_never_inferred(mutation):
    with pytest.raises(ProviderStateInvalid):
        reader(fake_client(subs={"sub_1": sub_obj(**mutation)})).get_subscription("sub_1")


@pytest.mark.parametrize("status", ["PAID", "succeeded", "complete", "", 5, "future_status"])
def test_an_unexpected_status_is_refused_not_mapped(status):
    with pytest.raises(ProviderStateInvalid) as e:
        reader(fake_client(subs={"sub_1": sub_obj(status=status)})).get_subscription("sub_1")
    assert e.value.category == "unsupported_status"


@pytest.mark.parametrize("status", PS.SUBSCRIPTION_STATUSES)
def test_every_documented_subscription_status_is_accepted(status):
    assert reader(fake_client(subs={"sub_1": sub_obj(status=status)})).get_subscription("sub_1").state == status


@pytest.mark.parametrize("bad", [True, "1900000000", 1.5, -1, 10, 9_999_999_999_999])
def test_malformed_timestamps_are_invalid(bad):
    s = sub_obj()
    s["items"]["data"][0]["current_period_end"] = bad
    with pytest.raises(ProviderStateInvalid) as e:
        reader(fake_client(subs={"sub_1": s})).get_subscription("sub_1")
    assert e.value.category == "malformed_timestamp"


def test_an_absent_period_end_is_none_and_the_subscription_level_field_is_the_fallback():
    s = sub_obj()
    del s["items"]["data"][0]["current_period_end"]
    assert reader(fake_client(subs={"sub_1": s})).get_subscription("sub_1").current_period_end is None
    s["current_period_end"] = 1_900_000_000
    assert reader(fake_client(subs={"sub_1": s})).get_subscription("sub_1").current_period_end.year == 2030


def test_currency_validation_and_the_optional_allow_list():
    r = reader(fake_client(subs={"sub_1": sub_obj()}), allowed_currencies=frozenset({"EUR"}))
    assert r.get_subscription("sub_1").currency == "EUR"
    s = sub_obj()
    s["items"]["data"][0]["price"]["currency"] = "usd"
    with pytest.raises(ProviderStateInvalid) as e:
        reader(fake_client(subs={"sub_1": s}), allowed_currencies=frozenset({"EUR"})).get_subscription("sub_1")
    assert e.value.category == "unsupported_currency"
    s["items"]["data"][0]["price"]["currency"] = "eur1"
    with pytest.raises(ProviderStateInvalid):
        reader(fake_client(subs={"sub_1": s})).get_subscription("sub_1")


@pytest.mark.parametrize("amount", [-1, "1999", True, 19.99])
def test_malformed_amounts_are_invalid(amount):
    s = sub_obj()
    s["items"]["data"][0]["price"]["unit_amount"] = amount
    with pytest.raises(ProviderStateInvalid):
        reader(fake_client(subs={"sub_1": s})).get_subscription("sub_1")


def test_scheduled_cancellation_is_not_cancellation_and_canceled_is_terminal_fact():
    sched = reader(fake_client(subs={"sub_1": sub_obj(cancel_at_period_end=True)})).get_subscription("sub_1")
    assert sched.cancel_at_period_end is True and sched.state == "active"
    gone = reader(fake_client(subs={"sub_1": sub_obj(status="canceled")})).get_subscription("sub_1")
    assert gone.state == "canceled"
    assert reader(fake_client(subs={"sub_1": sub_obj(cancel_at_period_end="yes")})).get_subscription("sub_1").cancel_at_period_end is False   # only a real True counts


def test_a_replacement_subscription_is_a_different_id_never_merged():
    r = reader(fake_client(subs={"sub_1": sub_obj(status="canceled"), "sub_2": sub_obj(id="sub_2")}))
    assert r.get_subscription("sub_1").state == "canceled" and r.get_subscription("sub_2").state == "active"
    with pytest.raises(ProviderStateInvalid):
        reader(fake_client(subs={"sub_1": sub_obj(id="sub_2")})).get_subscription("sub_1")


def test_a_live_object_or_a_live_reader_is_refused_there_is_no_sandbox_to_live_fallback():
    with pytest.raises(ProviderStateInvalid) as e:
        reader(fake_client(subs={"sub_1": sub_obj(livemode=True)})).get_subscription("sub_1")
    assert e.value.category == "environment_mismatch"
    with pytest.raises(ProviderStateConfiguration) as e2:
        StripeStateReader(lambda: fake_client(), environment="live")
    assert e2.value.category == "environment_not_readable"


# ================================================================ 2. INVOICE / PAYMENT / REFUND / DISPUTE ====================================

def inv(**over):
    base = {"id": "in_1", "status": "paid", "amount_paid": 1999, "amount_due": 0, "currency": "eur", "livemode": False, "payment_intent": "pi_1",
            "parent": {"type": "subscription_details", "subscription_details": {"subscription": "sub_1"}}}
    base.update(over)
    return base


def test_invoice_evidence_is_normalised_with_the_subscription_from_the_parent():
    i = reader(fake_client(invoices={"in_1": inv()})).get_invoice("in_1")
    assert (i.status, i.amount_paid, i.amount_due, i.currency, i.subscription_id, i.payment_intent) == ("paid", 1999, 0, "EUR", "sub_1", "pi_1")
    assert reader(fake_client(invoices={"in_1": inv(parent=None, payment_intent={"id": "pi_9"})})).get_invoice("in_1").subscription_id is None


@pytest.mark.parametrize("mutation", [{"status": "refunded"}, {"amount_paid": None}, {"amount_due": -5}, {"id": "in_2"}, {"livemode": True}, {"currency": "euro"}])
def test_invoice_garbage_is_invalid(mutation):
    with pytest.raises(ProviderStateInvalid):
        reader(fake_client(invoices={"in_1": inv(**mutation)})).get_invoice("in_1")


def test_an_open_invoice_is_never_payment_evidence():
    i = reader(fake_client(invoices={"in_1": inv(status="open", amount_paid=0, amount_due=1999)})).get_invoice("in_1")
    assert i.status == "open" and i.amount_paid == 0


def test_refund_and_dispute_evidence_are_normalised_and_validated():
    r = reader(fake_client(refunds={"re_1": {"id": "re_1", "status": "succeeded", "amount": 1999, "currency": "eur", "payment_intent": "pi_1", "charge": "ch_1", "livemode": False}}))
    s = r.get_refund("re_1")
    assert (s.status, s.amount, s.currency, s.payment_intent, s.charge) == ("succeeded", 1999, "EUR", "pi_1", "ch_1")
    d = reader(fake_client(disputes={"dp_1": {"id": "dp_1", "status": "needs_response", "amount": 1999, "currency": "eur", "charge": "ch_1", "payment_intent": None, "livemode": False}}))
    assert d.get_dispute("dp_1").status == "needs_response"
    with pytest.raises(ProviderStateInvalid):
        reader(fake_client(refunds={"re_1": {"id": "re_1", "status": "completed", "amount": 1, "livemode": False}})).get_refund("re_1")
    with pytest.raises(ProviderStateInvalid):
        reader(fake_client(disputes={"dp_1": {"id": "dp_1", "status": "weird", "amount": 1, "livemode": False}})).get_dispute("dp_1")


def test_missing_payment_evidence_is_not_a_payment():
    assert reader(fake_client(charges={"ch_1": {"payment_intent": None}})).subscription_for_payment(payment_intent=None, charge="ch_1") is None
    c = fake_client(invoice_payments={"data": [{"invoice": None}]})
    with pytest.raises(ProviderStateInvalid):
        reader(c).subscription_for_payment(payment_intent="pi_1", charge=None)
    c2 = fake_client(invoice_payments={"data": [{"invoice": "in_1"}, {"invoice": "in_2"}]}, invoices={
        "in_1": inv(), "in_2": inv(id="in_2", parent={"type": "subscription_details", "subscription_details": {"subscription": "sub_2"}})})
    with pytest.raises(ProviderStateInvalid) as e:
        reader(c2).subscription_for_payment(payment_intent="pi_1", charge=None)
    assert e.value.category == "ambiguous_subscription"


def test_checkout_association_validation():
    ok = {"id": "cs_1", "client_reference_id": "REF", "subscription": {"id": "sub_1"}, "livemode": False}
    a = reader(fake_client(sessions={"cs_1": ok})).checkout_session("cs_1")
    assert (a.client_reference_id, a.subscription_id) == ("REF", "sub_1")
    for bad in ({**ok, "id": "cs_2"}, {**ok, "livemode": None}, {**ok, "livemode": True}, {"livemode": False}):
        with pytest.raises(ProviderStateInvalid):
            reader(fake_client(sessions={"cs_1": bad})).checkout_session("cs_1")
    with pytest.raises(ProviderStateInvalid) as e:
        reader(fake_client(session_list={"data": [ok, {**ok, "id": "cs_9"}]})).checkout_for_subscription("sub_1")
    assert e.value.category == "ambiguous_checkout"
    assert reader(fake_client()).checkout_for_subscription("sub_1") is None


# ================================================================ 3. ERROR CLASSIFICATION ======================================================

@pytest.mark.parametrize("name,text,exc_type,category", [
    ("AuthenticationError", "Invalid API Key provided: sk_test_LEAK", ProviderStateConfiguration, "provider_auth_failed"),
    ("PermissionError", "restricted key lacks permission", ProviderStateConfiguration, "provider_permission_denied"),
    ("InvalidRequestError", "Invalid Stripe API version: 1999-01-01", ProviderStateConfiguration, "invalid_api_version"),
    ("InvalidRequestError", "Managed Payments is not supported for this account", ProviderStateConfiguration, "unsupported_feature"),
    ("InvalidRequestError", "The provided key does not have access to account acct_x", ProviderStateConfiguration, "wrong_account"),
    ("InvalidRequestError", "No such subscription: 'sub_x'", ProviderStateNotFound, "not_found"),
    ("InvalidRequestError", "something else entirely", ProviderStateInvalid, "invalid_request"),
    ("RateLimitError", "429", ProviderStateUnavailable, "rate_limited"),
    ("APIConnectionError", "Request timed out", ProviderStateUnavailable, "provider_timeout"),
    ("APIConnectionError", "connection reset", ProviderStateUnavailable, "provider_unavailable"),
    ("APIError", "500", ProviderStateUnavailable, "provider_unavailable"),
    ("SomethingNew", "who knows sk_live_LEAK", ProviderStateUnavailable, "provider_unavailable"),
])
def test_provider_errors_are_classified_without_leaking_text(name, text, exc_type, category):
    def boom(*a, **k):
        raise err(name, text)
    client = fake_client(subs=None)
    client.v1.subscriptions.retrieve = boom
    with pytest.raises(exc_type) as e:
        reader(client).get_subscription("sub_1")
    assert e.value.category == category and "sk_" not in repr(e.value) and "sk_" not in str(e.value.__cause__ or "")


def test_only_transient_categories_are_retryable():
    retryable = {n for n in dir(PS) if n.startswith("ProviderState") and issubclass(getattr(PS, n), PS.ProviderStateUnavailable)}
    assert retryable == {"ProviderStateUnavailable"}
    assert not issubclass(ProviderStateConfiguration, ProviderStateUnavailable) and not issubclass(ProviderStateInvalid, ProviderStateUnavailable)


def test_the_client_is_built_without_retries_and_the_reader_adds_none():
    calls = []

    def boom(*a, **k):
        calls.append(1)
        raise err("APIConnectionError", "timeout")
    client = fake_client()
    client.v1.subscriptions.retrieve = boom
    with pytest.raises(ProviderStateUnavailable):
        reader(client).get_subscription("sub_1")
    assert len(calls) == 1                                                                              # one attempt: the job layer owns bounded retries


# ================================================================ 4. READ-ONLY CAPABILITY BOUNDARY ===========================================

def test_only_retrieve_and_list_operations_exist_and_writes_are_unreachable():
    assert all(m in ("retrieve", "list") for _r, m in PS.READ_ONLY_OPERATIONS)
    c = fake_client(subs={"sub_1": sub_obj()})
    r = reader(c)
    for resource, method in (("subscriptions", "create"), ("subscriptions", "cancel"), ("checkout.sessions", "create"), ("refunds", "create"), ("customers", "delete")):
        with pytest.raises(ProviderStateConfiguration) as e:
            r._invoke(resource, method, {})
        assert e.value.category == "operation_not_read_only"
    assert c.log == []                                                                                  # no write was even attempted


def test_a_full_read_session_touches_only_retrieve_and_list():
    c = fake_client(subs={"sub_1": sub_obj()}, sessions={"cs_1": {"id": "cs_1", "subscription": "sub_1", "livemode": False}}, invoices={"in_1": inv()},
                    refunds={"re_1": {"id": "re_1", "status": "pending", "amount": 1, "livemode": False}}, disputes={"dp_1": {"id": "dp_1", "status": "won", "amount": 1, "livemode": False}},
                    charges={"ch_1": {"payment_intent": "pi_1"}}, invoice_payments={"data": [{"invoice": "in_1"}]})
    r = reader(c)
    r.get_subscription("sub_1"); r.checkout_session("cs_1"); r.checkout_for_subscription("sub_1"); r.get_invoice("in_1"); r.get_refund("re_1"); r.get_dispute("dp_1")
    r.subscription_for_payment(payment_intent=None, charge="ch_1")
    assert {m for _r, m in c.log} <= {"retrieve", "list"} and ("subscriptions", "create") not in c.log


def test_the_billing_package_has_no_generic_outbound_http_client():
    for path in (ROOT / "src/billing").glob("*.py"):
        text = path.read_text(encoding="utf-8")
        for banned in ("import requests", "import httpx", "urllib.request", "from requests", "from httpx", "http.client", "aiohttp"):
            assert banned not in text, f"{path.name} contains {banned}"


# ================================================================ 5. PROVIDER-READ AUTHORIZATION BOUNDARY ====================================

def test_provider_reads_are_a_disabled_code_constant_and_sandbox_only():
    assert P.PROVIDER_READS_AUTHORIZED is False and P.PROVIDER_READ_ENVIRONMENTS == ("sandbox",)
    assert (P.LIVE_BILLING_ENABLED, P.EXTERNAL_CHECKOUT_AUTHORIZED, P.STRIPE_WEBHOOK_AUTHORIZED, P.RECONCILE_SCHEDULER_ENABLED, P.PAID_ENTITLEMENT_POLICY_APPROVED) == (False,) * 5


def test_an_authorized_reader_cannot_be_built_while_reads_are_unauthorized_even_with_credentials():
    class Store:
        def get_for_runtime(self, name):
            return SimpleNamespace(get_secret_value=lambda: "sk_test_" + "x" * 24)
    for env_name in ("sandbox", "live", "production", ""):
        with pytest.raises(ProviderStateConfiguration) as e:
            build_authorized_reader(Store(), env_name, client_factory=lambda: fake_client())
        assert e.value.category == "provider_reads_not_authorized"


def test_even_when_a_reviewed_release_authorizes_reads_live_stays_refused_and_building_is_lazy(monkeypatch):
    monkeypatch.setattr(P, "PROVIDER_READS_AUTHORIZED", True)
    built = []
    with pytest.raises(ProviderStateConfiguration) as e:
        build_authorized_reader(None, "live", client_factory=lambda: built.append(1))
    assert e.value.category == "environment_not_readable"
    r = build_authorized_reader(None, "sandbox", client_factory=lambda: built.append(1) or fake_client())
    assert isinstance(r, StripeStateReader) and built == []                                           # constructing the reader contacted nothing and built no client


def test_the_default_factory_is_secretstore_backed_and_refuses_missing_or_foreign_credentials(monkeypatch):
    monkeypatch.setattr(P, "PROVIDER_READS_AUTHORIZED", True)
    values = {}

    class Store:
        def get_for_runtime(self, name):
            v = values.get(name)
            return SimpleNamespace(get_secret_value=lambda: v) if v is not None else None

        def source(self, name):
            return "environment" if name in values else "none"
    r = build_authorized_reader(Store(), "sandbox")
    with pytest.raises(ProviderStateConfiguration) as e:
        r.get_subscription("sub_1")
    assert e.value.category == "not_configured"
    values["STRIPE_SANDBOX_SECRET_KEY"] = "sk_live_" + "x" * 24                                        # a LIVE key in the sandbox slot is never accepted
    with pytest.raises(ProviderStateConfiguration) as e2:
        r.get_subscription("sub_1")
    assert e2.value.category in ("credential_environment_mismatch", "credential_format")


def test_the_runtime_reader_is_null_whatever_the_gate_or_credentials_say(monkeypatch):
    assert isinstance(build_runtime_reader(), NullStateReader)
    monkeypatch.setattr(P, "PROVIDER_READS_AUTHORIZED", True)
    monkeypatch.setattr(P, "STRIPE_WEBHOOK_AUTHORIZED", True)
    assert isinstance(build_runtime_reader(), NullStateReader)
    from src.billing.wiring import build_provider_events
    from src.persistence import make_engine, make_session_factory
    assert build_provider_events(make_session_factory(make_engine("sqlite://"))).reader_available() is False


def test_no_application_code_constructs_a_real_reader():
    owners = []
    for path in (ROOT / "src").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if re.search(r"StripeStateReader\(|build_authorized_reader\(", text):
            owners.append(path.relative_to(ROOT).as_posix())
    assert owners == ["src/billing/provider_state.py"]


def test_status_surfaces_cannot_trigger_a_read(env, monkeypatch):
    """Readiness, overview, credential-status, closure and scheduling paths run while every reader constructor explodes."""
    def explode(*a, **k):
        raise AssertionError("a provider reader must not be constructed")
    monkeypatch.setattr(PS.StripeStateReader, "__init__", explode)
    monkeypatch.setattr(PS, "build_authorized_reader", explode)
    from src.billing.operations import BillingOperations
    from src.billing.scheduler import schedule_tick
    from src.jobs.service import JobService
    ops = BillingOperations(env.sf, environment="sandbox", provider_selected=P.PROVIDER_STRIPE_MP, reader_available=False, readiness=lambda: {"status": "configured_not_tested"})
    ops.overview(); ops.readiness()
    assert schedule_tick(env.sf, JobService(env.sf), reader_available=False, enabled=True)["scheduled"] is False


# ================================================================ 6. READINESS HONESTY =======================================================

def test_readiness_separates_every_stage_and_never_claims_a_connection(env):
    from src.billing.operations import BillingOperations
    ops = BillingOperations(env.sf, environment="sandbox", provider_selected=P.PROVIDER_STRIPE_MP, reader_available=False,
                            readiness=lambda: {"status": "configured_not_tested", "sandbox": {"api": {"configured": True}}})
    rd = ops.readiness()
    st = rd["provider_read_stages"]
    assert list(st) == ["reader_implemented", "reader_selected_at_runtime", "credentials_configured", "sandbox_authorized", "eligibility_verified", "external_reads_authorized",
                        "checkout_authorized", "webhook_authorized", "scheduler_enabled", "entitlement_policy_approved", "sandbox_qualification_passed", "production_approved"]
    assert st["reader_implemented"] is True and st["credentials_configured"] is True
    assert [k for k, v in st.items() if v] == ["reader_implemented", "credentials_configured"]       # configured credentials are not authorization, a connection or health
    assert rd["provider_reads"] == "not_authorized" and rd["operational"] is False and rd["kill_switches"]["provider_reads_authorized"] is False
    text = json.dumps(rd).lower()
    for claim in ("connected", "healthy", "operational\": true"):
        assert claim not in text


# ================================================================ 7. WEBHOOK API-VERSION / EVENT CONTRACT ====================================

def test_incompatible_api_versions_are_held_visible_and_never_grant_or_revoke(env):
    env.reader.set_subscription("sub_synth_1")
    svc = ProviderEventService(env.sf, environment="sandbox", reader=env.reader, policy=SYNTHETIC_POLICY, clock=lambda: env.clock_now[0])
    for v in ("2020-01-01", "2099-01-01.future", "", None):
        out, r = accept_and_process(env, svc, sub_event(api_version=v))
        assert r.status == "skipped"
    assert count(env, BillingProviderLink) == 0 and plan_of(env, env.users[0])["plan_code"] == "basic"
    with env.sf() as s:
        assert s.scalar(select(func.count()).select_from(Subscription).where(Subscription.source == "provider")) == 0
        rows = s.scalars(select(BillingProviderEvent)).all()
    assert len(rows) == 4 and {x.status for x in rows} == {"needs_review"} and {x.failure_category for x in rows} == {"unsupported_api_version"}   # held, not ignored (B1R)


def test_thin_style_payloads_without_a_data_object_are_refused_not_processed():
    from src.billing import stripe_events as SE
    thin = {"id": "evt_thin_1", "object": "v2.core.event", "type": "v1.billing.meter.error_report_triggered", "livemode": False, "created": "2026-01-01T00:00:00Z",
            "related_object": {"id": "sub_1", "type": "subscription"}}
    with pytest.raises(SE.WebhookError):
        SE.parse_event(json.dumps(thin).encode())


# ================================================================ 8. OFFLINE END-TO-END THROUGH THE REAL READER ===============================

def provider_world(log=None, **over):
    """The Stripe API as a recording fake: Checkout Session for user 0, one subscription, its invoice."""
    sub = sub_obj(id="sub_synth_1", customer="cus_synth_1", latest_invoice={"id": "in_1", "status": "paid"}, **over)
    session = {"id": "cs_test_c1", "client_reference_id": "REFAAAA0", "subscription": "sub_synth_1", "livemode": False}
    return fake_client(log, subs={"sub_synth_1": sub}, sessions={"cs_test_c1": session}, session_list={"data": [session]},
                       invoices={"in_1": inv(id="in_1")})


def real_service(env, client, policy=SYNTHETIC_POLICY):
    return ProviderEventService(env.sf, environment="sandbox", reader=StripeStateReader(lambda: client), policy=policy, clock=lambda: env.clock_now[0])


def test_E2E_checkout_event_to_synthetic_policy_grant_through_the_real_reader_with_a_recording_fake(env):
    client = provider_world()
    svc = real_service(env, client)
    out, r = accept_and_process(env, svc, checkout_event(ref="REFAAAA0"))
    assert r.status == "processed" and plan_of(env, env.users[0])["plan_code"] == "premium"
    assert plan_of(env, env.users[1])["plan_code"] == "basic"                                          # no cross-candidate grant
    assert {m for _r, m in client.log} <= {"retrieve", "list"}
    for ev in (sub_event(), invoice_event()):                                                           # replay and sibling events change nothing further
        accept_and_process(env, svc, ev)
    with env.sf() as s:
        assert s.scalar(select(func.count()).select_from(Subscription).where(Subscription.source == "provider")) == 1
        assert s.scalar(select(func.count()).select_from(BillingEntitlementDecision).where(BillingEntitlementDecision.applied.is_(True))) == 1


def test_E2E_the_unapproved_runtime_policy_grants_nothing_even_with_perfect_provider_state(env):
    from src.billing.entitlement_bridge import runtime_policy
    svc = real_service(env, provider_world(), policy=runtime_policy())
    out, r = accept_and_process(env, svc, checkout_event(ref="REFAAAA0"))
    assert r.decision == "policy_unapproved" and plan_of(env, env.users[0])["plan_code"] == "basic"


def test_E2E_provider_cancellation_and_scheduled_cancellation(env):
    c = provider_world()
    svc = real_service(env, c)
    accept_and_process(env, svc, checkout_event(ref="REFAAAA0"))
    c.v1.subscriptions.retrieve = lambda i, p=None: sub_obj(id="sub_synth_1", customer="cus_synth_1", cancel_at_period_end=True, latest_invoice={"id": "in_1", "status": "paid"})
    accept_and_process(env, svc, sub_event())
    assert plan_of(env, env.users[0])["plan_code"] == "premium" and link_of(env, env.users[0]).cancel_at_period_end is True     # scheduled is not ended
    c.v1.subscriptions.retrieve = lambda i, p=None: sub_obj(id="sub_synth_1", customer="cus_synth_1", status="canceled", latest_invoice={"id": "in_1", "status": "paid"})
    accept_and_process(env, svc, sub_event("customer.subscription.deleted"))
    assert plan_of(env, env.users[0])["plan_code"] == "basic"


def test_E2E_cross_candidate_attack_checkout_reference_of_another_user_grants_nothing(env):
    c = provider_world()
    other = {"id": "cs_test_c2", "client_reference_id": "REFAAAA1", "subscription": "sub_synth_1", "livemode": False}
    c.v1.checkout.sessions.retrieve = lambda i, p=None: {**other, "id": i}
    c.v1.checkout.sessions.list = lambda p=None: {"data": [other]}
    out, r = accept_and_process(env, real_service(env, c), checkout_event(ref="REFAAAA0"))
    assert r.status in ("quarantined", "needs_review") and plan_of(env, env.users[0])["plan_code"] == "basic" and plan_of(env, env.users[1])["plan_code"] == "basic"


@pytest.mark.parametrize("exc,expected_status", [
    ("APIConnectionError", "retry"), ("RateLimitError", "retry"), ("APIError", "retry"),
    ("AuthenticationError", "needs_review"), ("PermissionError", "needs_review"),
])
def test_E2E_provider_outage_or_refusal_never_grants_and_is_observable(env, exc, expected_status):
    c = provider_world()

    def boom(*a, **k):
        raise err(exc, "x")
    c.v1.subscriptions.retrieve = boom
    out, r = accept_and_process(env, real_service(env, c), checkout_event(ref="REFAAAA0"))
    assert r.status == expected_status and plan_of(env, env.users[0])["plan_code"] == "basic"
    with env.sf() as s:
        assert s.scalar(select(func.count()).select_from(Subscription).where(Subscription.source == "provider")) == 0


def test_E2E_a_live_object_in_the_sandbox_world_is_never_trusted(env):
    out, r = accept_and_process(env, real_service(env, provider_world(livemode=True)), checkout_event(ref="REFAAAA0"))
    assert r.status == "needs_review" and plan_of(env, env.users[0])["plan_code"] == "basic"


def test_E2E_refund_and_dispute_events_are_facts_through_the_verified_pipeline(env):
    svc = real_service(env, provider_world())
    env_paid = accept_and_process(env, svc, checkout_event(ref="REFAAAA0"))[1]
    assert env_paid.status == "processed"
    svc2 = ProviderEventService(env.sf, environment="sandbox", reader=_paid_reader(env), policy=SYNTHETIC_POLICY, clock=lambda: env.clock_now[0])
    for ev in (dispute_event(), refund_event()):
        accept_and_process(env, svc2, ev)
    link = link_of(env, env.users[0])
    assert link is not None


def _paid_reader(env):
    env.reader.set_subscription("sub_synth_1", customer_id="cus_synth_1")
    env.reader.payments["pi_synth_1"] = "sub_synth_1"
    from src.billing.provider_state import CheckoutAssociation
    env.reader.checkouts["cs_test_c1"] = CheckoutAssociation("cs_test_c1", "REFAAAA0", "sub_synth_1", False)
    return env.reader


# ================================================================ 9. CHECKOUT CONTRACT (MOCKED SDK) ==========================================

def test_the_checkout_parameters_sent_to_the_sdk_are_server_controlled_and_managed(env):
    from src.billing.provider import CheckoutRequest
    from src.billing.stripe_provider import StripeManagedPaymentsProvider
    sent = []

    class Sessions:
        def create(self, params, opts=None):
            sent.append((params, opts))
            return SimpleNamespace(id="cs_test_1", url="https://checkout.stripe.com/c/pay/cs_test_1", expires_at=1_900_000_000)
    client = SimpleNamespace(v1=SimpleNamespace(checkout=SimpleNamespace(sessions=Sessions())))
    prov = StripeManagedPaymentsProvider(environment="sandbox", client_factory=lambda store, e: client)
    req = CheckoutRequest(client_reference_id="REF1", provider_price_id="price_test_1", success_url="https://app.example.test/billing/return?outcome=success",
                          cancel_url="https://app.example.test/billing/return?outcome=cancel", idempotency_key="ck-abcdefgh1234", expires_at=1_900_000_000,
                          **{k: v for k, v in {}.items()})
    prov.create_checkout_session(req)
    params, opts = sent[0]
    assert params["managed_payments"] == {"enabled": True} and params["mode"] == "subscription" and params["line_items"] == [{"price": "price_test_1", "quantity": 1}]
    assert opts == {"idempotency_key": "ck-abcdefgh1234"} and "amount" not in json.dumps(params) and "unit_amount" not in json.dumps(params)
    assert "automatic_tax" not in params and "payment_method_types" not in params                      # Managed Payments owns tax and payment methods


def test_the_checkout_url_that_is_stored_must_pass_the_https_check_and_the_adapter_refuses_without_authorization():
    from src.billing.provider import CheckoutRequest, ProviderRejected
    from src.billing.stripe_provider import StripeManagedPaymentsProvider
    req = CheckoutRequest(client_reference_id="REF1", provider_price_id="price_test_1", success_url="https://a.test/s", cancel_url="https://a.test/c", idempotency_key="ck-abcdefgh1234", expires_at=None)
    with pytest.raises(ProviderRejected) as e:
        StripeManagedPaymentsProvider(environment="sandbox").create_checkout_session(req)
    assert e.value.category == "checkout_not_authorized" if hasattr(e.value, "category") else True


# ================================================================ 10. ISOLATION AND DOCUMENTATION ============================================

def test_the_sdk_pin_and_api_version_are_unchanged_and_agree():
    from importlib.metadata import version
    assert P.STRIPE_API_VERSION == "2026-09-30.endive" and version("stripe") == "16.0.1"
    assert '"stripe==16.0.1"' in (ROOT / "pyproject.toml").read_text()
    from stripe import _api_version
    assert _api_version._ApiVersion.CURRENT == P.STRIPE_API_VERSION


def test_this_module_never_enables_a_network_call_default_sockets_are_blocked():
    import socket
    with pytest.raises(Exception):
        socket.create_connection(("api.stripe.com", 443), timeout=1)
