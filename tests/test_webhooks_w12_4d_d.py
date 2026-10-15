"""W12.4D-D: signed webhooks, durable processing, reconciliation and the entitlement bridge. FULLY OFFLINE: events are synthetic and signed with a synthetic
signing secret through the real Stripe SDK signature scheme, provider state comes from ``FakeStateReader``, and every non-loopback socket fails the test.
The ``SYNTHETIC_POLICY`` below is NOT an owner decision: it exists only so deterministic tests can exercise the bridge."""

from __future__ import annotations

import json
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import func, select

from src.billing import policy as P
from src.billing import stripe_events as SE
from src.billing.entitlement_bridge import UNAPPROVED_POLICY, EntitlementPolicy, decide, runtime_policy
from src.billing.provider_state import (
    CheckoutAssociation, FakeStateReader, NullStateReader, ProviderStateInvalid, ProviderStateUnavailable,
)
from src.billing.reconcile import ProviderEventService
from src.billing.webhook import WebhookReceiver
from src.entitlements import EntitlementService
from src.persistence import (
    BillingCheckoutSession, BillingCommercialTerms, BillingEntitlementDecision, BillingProviderEvent, BillingProviderLink, BillingProviderPrice,
    PlanVersion, Subscription, User, init_db, make_engine, make_session_factory, utcnow,
)

ROOT = Path(__file__).resolve().parents[1]
SECRET = "whsec_SYNTHETIC_W12_04DD_TEST_SECRET_000001"
OLD_SECRET = "whsec_SYNTHETIC_W12_04DD_TEST_SECRET_OLD_01"
API_VERSION = P.STRIPE_API_VERSION
SYNTHETIC_POLICY = EntitlementPolicy(policy_id="SYNTHETIC-TEST-POLICY", approved=True, trial_grants=True, past_due="keep", unpaid="revoke", canceled="revoke",
                                     paused="revoke", full_refund="revoke", dispute_open="keep", dispute_lost="revoke", synthetic=True)


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


# ---------------------------------------------------------------- event factories (synthetic Stripe-shaped payloads) ---------------------------------

def sign(body: bytes, secret: str = SECRET, ts: int | None = None, extra: str | None = None) -> str:
    import stripe
    header = stripe.WebhookSignature.generate_signature_header(body.decode(), secret, ts if ts is not None else int(time.time()))
    return header + (f",v1={extra}" if extra else "")


_n = [0]


def event(etype: str, obj: dict, *, eid: str | None = None, livemode: bool = False, created: int = 1_800_000_000, api_version: str = API_VERSION, **extra) -> dict:
    _n[0] += 1
    return {"id": eid or f"evt_synth_{_n[0]:06d}", "object": "event", "type": etype, "livemode": livemode, "created": created, "api_version": api_version,
            "data": {"object": obj}, **extra}


def body(ev: dict) -> bytes:
    return json.dumps(ev, separators=(",", ":")).encode()


def sub_event(etype="customer.subscription.updated", sub="sub_synth_1", **kw):
    return event(etype, {"id": sub, "object": "subscription", "customer": "cus_synth_1", "status": "active", "cancel_at_period_end": False}, **kw)


def invoice_event(etype="invoice.paid", sub="sub_synth_1", **kw):
    return event(etype, {"id": "in_synth_1", "object": "invoice", "customer": "cus_synth_1", "status": "paid", "amount_paid": 1999,
                         "parent": {"type": "subscription_details", "subscription_details": {"subscription": sub}}}, **kw)


def checkout_event(etype="checkout.session.completed", session="cs_test_c1", ref="REF", sub="sub_synth_1", **kw):
    return event(etype, {"id": session, "object": "checkout.session", "mode": "subscription", "payment_status": "paid", "client_reference_id": ref,
                         "customer": "cus_synth_1", "subscription": sub}, **kw)


def refund_event(pi="pi_synth_1", amount=1999, refunded=1999, **kw):
    return event("charge.refunded", {"id": "ch_synth_1", "object": "charge", "payment_intent": pi, "refunded": refunded >= amount, "amount": amount,
                                     "amount_refunded": refunded}, **kw)


def dispute_event(etype="charge.dispute.created", status="needs_response", pi="pi_synth_1", **kw):
    return event(etype, {"id": "dp_synth_1", "object": "dispute", "charge": "ch_synth_1", "payment_intent": pi, "status": status}, **kw)


# ---------------------------------------------------------------- environment --------------------------------------------------------------------------

class Env:
    pass


@pytest.fixture()
def env(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path / 'w.db'}")
    init_db(engine)
    sf = make_session_factory(engine)
    e = Env()
    e.sf, e.engine = sf, engine
    e.clock_now = [utcnow()]
    with sf() as s:
        pv = s.scalar(select(PlanVersion).where(PlanVersion.plan_code == "premium"))
        users = [User(subject=f"u{i}", provider="local", email=f"u{i}@x.test") for i in range(3)]
        s.add_all(users)
        s.flush()
        terms = BillingCommercialTerms(public_id="t" * 32, plan_version_id=pv.id, version=1, amount_minor=1999, currency="EUR", billing_interval="month",
                                       visibility="public", state="active")
        s.add(terms)
        s.flush()
        price = BillingProviderPrice(public_id="p" * 32, commercial_terms_id=terms.id, provider=P.PROVIDER_STRIPE_MP, environment="sandbox",
                                     provider_product_id="prod_test_1", provider_price_id="price_test_1", amount_minor=1999, currency="EUR",
                                     billing_interval="month", status="active")
        s.add(price)
        s.flush()
        from src.entitlements import ensure_default_subscription
        for u in users:
            ensure_default_subscription(s, u.id)                                         # every real account starts on the Basic system_default plan
        for i, u in enumerate(users):
            s.add(BillingCheckoutSession(public_id=f"REFAAAA{i}", user_id=u.id, plan_version_id=pv.id, commercial_terms_id=terms.id, price_mapping_id=price.id,
                                         provider=P.PROVIDER_STRIPE_MP, environment="sandbox", provider_session_id=f"cs_test_c{i + 1}", status="open",
                                         idempotency_key=f"idem-key-0000{i}", checkout_url="https://checkout.stripe.com/x", provider_attempts=1,
                                         created_at=utcnow(), expires_at=utcnow() + timedelta(minutes=30)))
        s.commit()
        e.users = [u.id for u in users]
        e.pv_premium = pv.id
    e.reader = FakeStateReader(clock=lambda: e.clock_now[0])
    return e


def reader_for(env, user_index=0, sub="sub_synth_1", customer="cus_synth_1", **state):
    """Provider-side truth: a subscription created by the checkout of ``users[user_index]``."""
    env.reader.set_subscription(sub, customer_id=customer, **state)
    env.reader.checkouts[f"cs_test_c{user_index + 1}"] = CheckoutAssociation(f"cs_test_c{user_index + 1}", f"REFAAAA{user_index}", sub, False)


def service(env, policy=SYNTHETIC_POLICY, environment="sandbox", audit=None):
    return ProviderEventService(env.sf, environment=environment, reader=env.reader, policy=policy, audit=audit, clock=lambda: env.clock_now[0])


def receiver(env, svc=None, jobs=None, secrets=(SECRET,), environment="sandbox", authorized=True, provider=P.PROVIDER_STRIPE_MP, audit=None):
    return WebhookReceiver(svc or service(env), jobs=jobs, secrets=lambda: list(secrets), environment=environment, provider_selected=provider, authorized=authorized,
                           audit=audit)


def deliver(env, rcv, ev, secret=SECRET, ts=None):
    raw = body(ev)
    return rcv.handle(raw, sign(raw, secret, ts))


def count(env, model):
    with env.sf() as s:
        return s.scalar(select(func.count()).select_from(model))


def plan_of(env, uid):
    return EntitlementService(env.sf).plan_summary(uid)


def link_of(env, uid=None):
    with env.sf() as s:
        q = select(BillingProviderLink)
        if uid:
            q = q.where(BillingProviderLink.user_id == uid)
        return s.scalar(q)


def accept_and_process(env, svc, ev):
    out = svc.accept(ev)
    return out, svc.process(out["public_id"])


# ================================================================ 1. WEBHOOK AUTHENTICATION ====================================================

def test_valid_signature_is_accepted_and_stored_without_changing_anything(env):
    ev = checkout_event()
    out = deliver(env, receiver(env), ev)
    assert out == {"status": "accepted"}
    assert count(env, BillingProviderEvent) == 1 and count(env, BillingProviderLink) == 0 and count(env, Subscription) == 3


def test_signature_failures_are_rejected_and_store_nothing(env):
    rcv, raw = receiver(env), body(checkout_event())
    cases = {
        "missing": None,
        "garbage": "not-a-signature",
        "malformed_ts": "t=abc,v1=deadbeef",
        "no_v1": f"t={int(time.time())},v0=abc",
        "wrong_secret": sign(raw, "whsec_SOMETHING_ELSE_ENTIRELY_0000000001"),
        "expired": sign(raw, SECRET, int(time.time()) - 10_000),
        "future": sign(raw, SECRET, int(time.time()) + 10_000),
    }
    for name, header in cases.items():
        with pytest.raises(SE.WebhookError) as e:
            rcv.handle(raw, header)
        assert e.value.status == 400, name
    with pytest.raises(SE.WebhookError):
        rcv.handle(raw + b" ", sign(raw))                       # tampered body
    assert count(env, BillingProviderEvent) == 0


def test_non_utf8_and_malformed_json_after_valid_signature(env):
    rcv = receiver(env)
    bad = b"\xff\xfe\x00"
    with pytest.raises(SE.WebhookError) as e:
        rcv.handle(bad, "t=1,v1=00")
    assert e.value.status == 400
    raw = b"{not json"
    with pytest.raises(SE.WebhookError) as e:
        rcv.handle(raw, sign(raw))
    assert e.value.category == "malformed_body"
    raw = json.dumps({"id": "evt_ok1", "type": "invoice.paid"}).encode()
    with pytest.raises(SE.WebhookError) as e:
        rcv.handle(raw, sign(raw))
    assert e.value.category == "malformed_event"
    assert count(env, BillingProviderEvent) == 0


@pytest.mark.parametrize("eid", ["evt_';drop table users;--", "evt_", "x" * 90, "cus_123", "evt_a b"])
def test_malformed_identifiers_never_reach_the_database(env, eid):
    raw = body(sub_event(eid=eid))
    with pytest.raises(SE.WebhookError) as e:
        receiver(env).handle(raw, sign(raw))
    assert e.value.category == "malformed_event" and count(env, BillingProviderEvent) == 0


def test_signature_rotation_old_and_new_signatures_in_one_header_verify_with_the_new_secret(env):
    import stripe
    raw = body(sub_event())
    ts = int(time.time())
    old_sig = stripe.WebhookSignature._compute_signature(f"{ts}.{raw.decode()}", OLD_SECRET)
    header = sign(raw, SECRET, ts, extra=old_sig)
    assert receiver(env, secrets=(SECRET,)).handle(raw, header) == {"status": "accepted"}
    header_old_only = f"t={ts},v1={old_sig}"
    with pytest.raises(SE.WebhookError):
        receiver(env, secrets=(SECRET,)).handle(body(sub_event()), header_old_only)      # an old-only signature is not accepted once the secret is replaced


def test_wrong_environment_is_rejected_even_with_a_valid_signature(env):
    live = sub_event(livemode=True)
    with pytest.raises(SE.WebhookError) as e:
        deliver(env, receiver(env), live)
    assert e.value.category == "environment_mismatch"
    with pytest.raises(SE.WebhookError) as e:
        deliver(env, receiver(env, environment="live"), sub_event())               # a live deployment refuses (live billing is disabled)
    assert e.value.status == 503
    with pytest.raises(SE.WebhookError):
        deliver(env, receiver(env, environment=None), sub_event())
    assert count(env, BillingProviderEvent) == 0


def test_not_operational_without_authorization_provider_or_secret(env):
    ev = sub_event()
    for kw in ({"authorized": False}, {"provider": "mock"}, {"provider": None}, {"secrets": ()}):
        with pytest.raises(SE.WebhookError) as e:
            deliver(env, receiver(env, **kw), ev)
        assert e.value.status == 503
    assert count(env, BillingProviderEvent) == 0


def test_oversized_payload_is_refused_before_verification(env):
    raw = b"{" + b" " * (P.WEBHOOK_MAX_BODY_BYTES + 10) + b"}"
    with pytest.raises(SE.WebhookError) as e:
        receiver(env).handle(raw, sign(raw))
    assert e.value.status == 413


def test_unknown_event_type_version_and_account_context_are_acknowledged_as_ignored(env):
    rcv = receiver(env)
    for ev in (event("some.unknown.event", {"id": "x_1"}), sub_event(api_version="2020-01-01"), sub_event(account="acct_other")):
        assert deliver(env, rcv, ev) == {"status": "accepted"}
    with env.sf() as s:
        rows = s.scalars(select(BillingProviderEvent)).all()
    assert {r.status for r in rows} == {"ignored"}
    assert {r.failure_category for r in rows} == {"unsupported_event_type", "unsupported_api_version", "unexpected_account_context"}
    assert count(env, BillingProviderLink) == 0


def test_persistence_failure_is_retryable_never_an_acknowledgement(env):
    class Broken:
        def accept(self, *a, **k):
            raise RuntimeError("disk full")
    with pytest.raises(SE.WebhookError) as e:
        deliver(env, receiver(env, svc=Broken()), sub_event())
    assert e.value.status == 503 and e.value.category == "persistence_failed"


def test_job_enqueue_failure_is_recovered_by_the_sweep(env):
    class Jobs:
        def enqueue(self, *a, **k):
            raise RuntimeError("queue down")
    reader_for(env)
    svc = service(env)
    assert deliver(env, receiver(env, svc=svc, jobs=Jobs()), checkout_event(ref="REFAAAA0")) == {"status": "accepted"}
    env.clock_now[0] += timedelta(minutes=5)
    counts = svc.sweep()
    assert counts["events"] == 1 and count(env, BillingProviderLink) == 1


def test_enqueue_uses_an_id_only_payload(env):
    calls = []
    jobs = SimpleNamespace(enqueue=lambda *a, **k: calls.append((a, k)))
    deliver(env, receiver(env, jobs=jobs), sub_event())
    (name, payload), kw = calls[0]
    assert name == P.JOB_PROCESS_PROVIDER_EVENT and set(payload) == {"event_id"} and len(payload["event_id"]) == 32


def test_the_signature_is_checked_with_the_sdk_boundary_and_a_future_timestamp_is_rejected_by_us():
    raw = b"{}"
    with pytest.raises(SE.WebhookError) as e:
        SE.verify_signature(raw, sign(raw, SECRET, int(time.time()) + 3600), [SECRET])
    assert e.value.category == "timestamp_outside_tolerance"
    SE.verify_signature(raw, sign(raw, SECRET, int(time.time()) - 60), [SECRET])


# ================================================================ 2. HTTP ROUTE ================================================================

@pytest.fixture()
def http():
    from tests.test_admin_foundation_w10_1 import Env as HttpEnv
    e = HttpEnv()
    yield e
    e.app.dependency_overrides.clear()
    e.close()


URL = "/api/v1/billing/webhooks/stripe"


def test_route_exists_post_only_and_needs_no_candidate_login(http):
    assert URL in http.app.openapi()["paths"] and set(http.app.openapi()["paths"][URL]) == {"post"}
    assert http.c.get(URL).status_code == 405
    r = http.c.post(URL, content=b"{}", headers={"Stripe-Signature": "t=1,v1=00"})
    assert r.status_code == 503                         # unauthenticated candidate, not a 401: the route is signature-authenticated and not operational by default
    assert "detail" in r.json() or "error" in r.json()
    assert "whsec" not in r.text and "secret" not in r.text.lower()


def test_route_end_to_end_with_authorization_injected(http, env):
    from src.api.dependencies import get_webhook_receiver
    rcv = receiver(env)
    http.app.dependency_overrides[get_webhook_receiver] = lambda: rcv
    ev = checkout_event()
    raw = body(ev)
    ok = http.c.post(URL, content=raw, headers={"Stripe-Signature": sign(raw)})
    assert ok.status_code == 200 and ok.json() == {"status": "accepted"}
    bad = http.c.post(URL, content=raw, headers={"Stripe-Signature": sign(raw, "whsec_NOPE_NOPE_NOPE_NOPE_NOPE_NOPE_0001")})
    assert bad.status_code == 400 and "signature" not in bad.text.lower()
    tampered = http.c.post(URL, content=raw + b" ", headers={"Stripe-Signature": sign(raw)})
    assert tampered.status_code == 400
    big = b"{" + b" " * (P.WEBHOOK_MAX_BODY_BYTES + 5) + b"}"
    assert http.c.post(URL, content=big, headers={"Stripe-Signature": sign(big)}).status_code == 413
    assert count(env, BillingProviderEvent) == 1 and count(env, Subscription) == 3


def _code(rel: str) -> str:
    import ast
    tree = ast.parse((ROOT / rel).read_text())
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and node.body and isinstance(node.body[0], ast.Expr) \
                and isinstance(getattr(node.body[0], "value", None), ast.Constant) and isinstance(node.body[0].value.value, str):
            node.body = node.body[1:] or [ast.Pass()]
    return ast.unparse(tree)


def test_route_has_no_candidate_auth_dependency_and_no_entitlement_mutation_in_source():
    route, recv = _code("src/api/routes/billing_webhooks.py"), _code("src/billing/webhook.py")
    assert "get_current_user_id" not in route and "Subscription" not in route and "entitlement" not in route.lower()
    assert "evaluate_and_apply" not in recv and "Subscription" not in recv and "entitlement" not in recv.lower()


def test_default_dependency_is_unauthorized_and_unconfigured(http):
    r = http.c.post(URL, content=body(sub_event()), headers={"Stripe-Signature": sign(body(sub_event()))})
    assert r.status_code == 503


# ================================================================ 3. DUPLICATES AND CONCURRENCY ================================================

def test_same_event_twice_is_stored_once(env):
    svc, ev = service(env), sub_event()
    a, b = svc.accept(ev), svc.accept(ev)
    assert (a["disposition"], b["disposition"]) == ("accepted", "duplicate") and a["public_id"] == b["public_id"]
    assert count(env, BillingProviderEvent) == 1


def test_same_event_delivered_concurrently_is_stored_once(env):
    svc, ev, results = service(env), sub_event(), []

    def go():
        try:
            results.append(svc.accept(ev)["disposition"])
        except Exception as exc:  # noqa: BLE001
            results.append(repr(exc))
    ts = [threading.Thread(target=go) for _ in range(8)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert count(env, BillingProviderEvent) == 1 and results.count("accepted") == 1 and all(r in ("accepted", "duplicate") for r in results)


def test_event_id_is_scoped_by_environment():
    assert BillingProviderEvent.__table__.constraints and any(
        {c.name for c in k.columns} == {"provider", "environment", "provider_event_id"} for k in BillingProviderEvent.__table__.constraints if hasattr(k, "columns"))


def test_redelivery_after_processing_is_a_no_op(env):
    reader_for(env)
    svc = service(env)
    ev = checkout_event(ref="REFAAAA0")
    out, r = accept_and_process(env, svc, ev)
    assert r.status == "processed"
    again = svc.accept(ev)
    assert again["disposition"] == "duplicate" and svc.process(out["public_id"]).status == "skipped"
    assert count(env, BillingProviderLink) == 1
    assert count(env, BillingEntitlementDecision) == 1


def test_two_different_events_for_the_same_business_change_grant_once(env):
    reader_for(env)
    svc = service(env)
    for ev in (checkout_event(ref="REFAAAA0"), sub_event(), invoice_event()):
        accept_and_process(env, svc, ev)
    assert count(env, BillingProviderLink) == 1
    with env.sf() as s:
        provider_rows = s.scalars(select(Subscription).where(Subscription.source == "provider")).all()
        applied = s.scalars(select(BillingEntitlementDecision).where(BillingEntitlementDecision.applied.is_(True))).all()
    assert len(provider_rows) == 1 and len(applied) == 1
    assert plan_of(env, env.users[0])["plan_code"] == "premium"


def test_concurrent_processing_of_one_event_runs_it_once(env):
    reader_for(env)
    svc = service(env)
    out = svc.accept(checkout_event(ref="REFAAAA0"))
    statuses = []
    ts = [threading.Thread(target=lambda: statuses.append(svc.process(out["public_id"]).status)) for _ in range(6)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert statuses.count("processed") == 1 and set(statuses) <= {"processed", "skipped"}
    assert count(env, BillingProviderLink) == 1 and count(env, BillingEntitlementDecision) == 1


def test_distinct_legitimate_updates_sharing_object_and_type_are_all_applied(env):
    reader_for(env)
    svc = service(env)
    accept_and_process(env, svc, checkout_event(ref="REFAAAA0"))
    seen = []
    for state, inv in (("past_due", "failed"), ("active", "paid"), ("past_due", "failed"), ("active", "paid")):
        env.clock_now[0] += timedelta(seconds=5)
        env.reader.set_subscription("sub_synth_1", state=state, latest_invoice_state=inv)
        accept_and_process(env, svc, sub_event())               # identical type AND object id, different business transition
        seen.append(link_of(env).provider_state)
    assert seen == ["past_due", "active", "past_due", "active"]


def test_two_valid_signatures_on_a_retried_event_store_one_row(env):
    rcv, ev = receiver(env), sub_event()
    raw = body(ev)
    rcv.handle(raw, sign(raw, SECRET, int(time.time())))
    rcv.handle(raw, sign(raw, SECRET, int(time.time()) - 30))
    assert count(env, BillingProviderEvent) == 1


# ================================================================ 4. CRASH RECOVERY AND RETRIES ================================================

def test_provider_timeout_then_retry_converges_without_duplicate_effects(env):
    reader_for(env)
    svc = service(env)
    env.reader.fail, env.reader.fail_times = ProviderStateUnavailable("provider_timeout"), 1
    out = svc.accept(checkout_event(ref="REFAAAA0"))
    first = svc.process(out["public_id"])
    assert first.status == "retry"
    with env.sf() as s:
        ev = s.scalar(select(BillingProviderEvent))
        assert ev.status == "failed" and ev.attempt_count == 1 and ev.next_attempt_at is not None and ev.failure_category == "provider_timeout"
    assert svc.process(out["public_id"]).status == "skipped"                         # too early: the event's own back-off holds
    env.clock_now[0] += timedelta(hours=1)
    assert svc.process(out["public_id"]).status == "processed"
    assert count(env, BillingProviderLink) == 1 and count(env, BillingEntitlementDecision) == 1


def test_abandoned_lease_is_reclaimed(env):
    reader_for(env)
    svc = service(env)
    out = svc.accept(checkout_event(ref="REFAAAA0"))
    with env.sf() as s:                                                              # simulate a worker that died mid-processing
        ev = s.scalar(select(BillingProviderEvent))
        ev.status, ev.lease_until, ev.attempt_count = "processing", env.clock_now[0] + timedelta(seconds=30), 1
        s.commit()
    assert svc.process(out["public_id"]).status == "skipped"                         # lease still valid: nobody steals it
    env.clock_now[0] += timedelta(minutes=10)
    assert svc.sweep()["events"] == 1 and count(env, BillingProviderLink) == 1


def test_a_crash_between_reconcile_and_commit_leaves_nothing_half_applied(env, monkeypatch):
    reader_for(env)
    svc = service(env)
    out = svc.accept(checkout_event(ref="REFAAAA0"))
    import src.billing.reconcile as R
    real = R.evaluate_and_apply

    def boom(*a, **k):
        real(*a, **k)
        raise RuntimeError("crash after the bridge ran, before commit")
    monkeypatch.setattr(R, "evaluate_and_apply", boom)
    assert svc.process(out["public_id"]).status == "retry"
    assert count(env, BillingProviderLink) == 0 and count(env, Subscription) == 3 and count(env, BillingEntitlementDecision) == 0      # all rolled back together
    monkeypatch.setattr(R, "evaluate_and_apply", real)
    env.clock_now[0] += timedelta(hours=1)
    assert svc.process(out["public_id"]).status == "processed"
    assert plan_of(env, env.users[0])["plan_code"] == "premium"


def test_retries_are_bounded_and_end_in_needs_review(env):
    reader_for(env)
    svc = service(env)
    env.reader.fail = ProviderStateUnavailable("provider_unavailable")
    out = svc.accept(checkout_event(ref="REFAAAA0"))
    last = None
    for _ in range(P.EVENT_PROCESS_MAX_ATTEMPTS + 2):
        env.clock_now[0] += timedelta(hours=2)
        last = svc.process(out["public_id"])
    with env.sf() as s:
        ev = s.scalar(select(BillingProviderEvent))
    assert ev.status == "needs_review" and ev.failure_category == "retries_exhausted" and ev.attempt_count == P.EVENT_PROCESS_MAX_ATTEMPTS
    assert last.status in ("needs_review", "skipped")
    assert count(env, BillingProviderLink) == 0


def test_invalid_provider_answer_is_never_treated_as_payment(env):
    svc = service(env)
    reader_for(env)
    env.reader.fail = ProviderStateInvalid("incomplete_response")
    out, r = accept_and_process(env, svc, checkout_event(ref="REFAAAA0"))
    assert r.status == "needs_review" and count(env, Subscription) == 3 and count(env, BillingProviderLink) == 0


# ================================================================ 5. EVENT ORDERING ============================================================

def test_invoice_paid_before_subscription_created_converges(env):
    reader_for(env)
    svc = service(env)
    accept_and_process(env, svc, invoice_event())                                     # no link and no checkout event yet: ownership comes from the checkout record
    accept_and_process(env, svc, sub_event("customer.subscription.created"))
    accept_and_process(env, svc, checkout_event(ref="REFAAAA0"))
    assert count(env, BillingProviderLink) == 1 and plan_of(env, env.users[0])["plan_code"] == "premium"


def test_subscription_updated_before_created_and_equal_timestamps(env):
    reader_for(env)
    svc = service(env)
    for ev in (sub_event("customer.subscription.updated", created=1_800_000_000), sub_event("customer.subscription.created", created=1_800_000_000)):
        accept_and_process(env, svc, ev)
    assert link_of(env).provider_state == "active" and count(env, BillingProviderLink) == 1


def test_stale_failure_event_cannot_undo_a_newer_recovery(env):
    reader_for(env)
    svc = service(env)
    accept_and_process(env, svc, checkout_event(ref="REFAAAA0"))
    env.clock_now[0] += timedelta(seconds=5)
    env.reader.set_subscription("sub_synth_1", state="past_due", latest_invoice_state="failed")
    accept_and_process(env, svc, invoice_event("invoice.payment_failed"))
    assert link_of(env).provider_state == "past_due"
    env.clock_now[0] += timedelta(seconds=5)
    env.reader.set_subscription("sub_synth_1", state="active", latest_invoice_state="paid")
    accept_and_process(env, svc, invoice_event("invoice.paid"))
    env.clock_now[0] += timedelta(seconds=5)
    accept_and_process(env, svc, invoice_event("invoice.payment_failed"))             # the OLD failure arrives last: the provider's current state still says active
    assert link_of(env).provider_state == "active" and plan_of(env, env.users[0])["plan_code"] == "premium"


def test_stale_deleted_event_does_not_cancel_an_active_subscription(env):
    reader_for(env)
    svc = service(env)
    accept_and_process(env, svc, checkout_event(ref="REFAAAA0"))
    env.clock_now[0] += timedelta(seconds=5)
    out, r = accept_and_process(env, svc, sub_event("customer.subscription.deleted"))
    with env.sf() as s:
        ev = s.scalar(select(BillingProviderEvent).where(BillingProviderEvent.public_id == out["public_id"]))
    assert link_of(env).provider_state == "active" and ev.reconciliation_json["conflict"] == "event_superseded_by_provider_state"
    assert plan_of(env, env.users[0])["plan_code"] == "premium"


def test_an_older_snapshot_never_overwrites_a_newer_one(env):
    reader_for(env)
    svc = service(env)
    accept_and_process(env, svc, checkout_event(ref="REFAAAA0"))
    env.clock_now[0] += timedelta(minutes=10)
    env.reader.set_subscription("sub_synth_1", state="past_due", latest_invoice_state="failed")
    accept_and_process(env, svc, sub_event())
    assert link_of(env).provider_state == "past_due"
    env.clock_now[0] -= timedelta(minutes=30)                                         # a lagging read that observed the provider EARLIER
    env.reader.set_subscription("sub_synth_1", state="active", latest_invoice_state="paid")
    out, _ = accept_and_process(env, svc, sub_event())
    with env.sf() as s:
        ev = s.scalar(select(BillingProviderEvent).where(BillingProviderEvent.public_id == out["public_id"]))
    assert link_of(env).provider_state == "past_due" and ev.reconciliation_json["disposition"] == "stale_snapshot_not_applied"


def test_a_canceled_subscription_is_never_reactivated_by_a_later_reading(env):
    reader_for(env)
    svc = service(env)
    accept_and_process(env, svc, checkout_event(ref="REFAAAA0"))
    env.clock_now[0] += timedelta(seconds=5)
    env.reader.set_subscription("sub_synth_1", state="canceled", latest_invoice_state="paid")
    accept_and_process(env, svc, sub_event("customer.subscription.deleted"))
    assert link_of(env).provider_state == "canceled" and plan_of(env, env.users[0])["plan_code"] == "basic"
    env.clock_now[0] += timedelta(seconds=5)
    env.reader.set_subscription("sub_synth_1", state="active")
    out, r = accept_and_process(env, svc, sub_event())
    assert r.status == "needs_review" and r.category == "terminal_reactivation_refused" and link_of(env).provider_state == "canceled"


def test_refund_before_the_invoice_update_converges(env):
    reader_for(env)
    env.reader.payments["pi_synth_1"] = "sub_synth_1"
    svc = service(env)
    accept_and_process(env, svc, refund_event())
    assert link_of(env).refund_state == "full"
    accept_and_process(env, svc, invoice_event())
    assert link_of(env).refund_state == "full"                                        # a later paid-invoice event never un-refunds
    assert plan_of(env, env.users[0])["plan_code"] == "basic"                          # full refund under the (synthetic) revoke rule


def test_missed_webhook_is_recovered_by_the_periodic_reconciliation(env):
    reader_for(env)
    with env.sf() as s:
        cs = s.scalar(select(BillingCheckoutSession).where(BillingCheckoutSession.user_id == env.users[0]))
        cs.browser_returned_at = env.clock_now[0]
        s.commit()
    svc = service(env)
    assert count(env, BillingProviderEvent) == 0
    counts = svc.sweep()
    assert counts["checkouts_checked"] == 1 and link_of(env).provider_state == "active" and plan_of(env, env.users[0])["plan_code"] == "premium"


def test_periodic_sweep_refreshes_stale_links_and_tolerates_provider_outage(env):
    reader_for(env)
    svc = service(env)
    accept_and_process(env, svc, checkout_event(ref="REFAAAA0"))
    env.clock_now[0] += timedelta(seconds=P.RECONCILE_STALE_AFTER_SECONDS + 10)
    env.reader.set_subscription("sub_synth_1", state="past_due", latest_invoice_state="failed")
    assert svc.sweep()["links_refreshed"] == 1 and link_of(env).provider_state == "past_due"
    env.clock_now[0] += timedelta(seconds=P.RECONCILE_STALE_AFTER_SECONDS + 10)
    env.reader.fail = ProviderStateUnavailable("provider_unavailable")
    assert svc.sweep()["unavailable"] >= 1 and link_of(env).provider_state == "past_due"


def test_unknown_provider_subscription_is_quarantined_without_access(env):
    svc = service(env)
    env.reader.set_subscription("sub_unknown", customer_id="cus_x")
    out, r = accept_and_process(env, svc, sub_event(sub="sub_unknown"))
    assert r.status == "quarantined" and r.category == "unknown_ownership"
    assert count(env, BillingProviderLink) == 0 and count(env, Subscription) == 3


def test_provider_resource_not_found_is_quarantined(env):
    svc = service(env)
    out, r = accept_and_process(env, svc, sub_event(sub="sub_gone"))
    assert r.status == "quarantined" and r.category == "provider_resource_not_found"


# ================================================================ 6. OWNERSHIP AND TENANT ISOLATION ============================================

def test_email_is_never_used_for_ownership(env):
    svc = service(env)
    env.reader.set_subscription("sub_synth_1")
    out, r = accept_and_process(env, svc, sub_event())
    assert r.category == "unknown_ownership"
    src = (ROOT / "src/billing/reconcile.py").read_text()
    assert "email" not in src.lower().replace("never matched by email", "")


def test_a_subscription_binds_only_to_the_checkout_owner(env):
    reader_for(env, user_index=1)
    svc = service(env)
    accept_and_process(env, svc, checkout_event(ref="REFAAAA1", session="cs_test_c2"))
    assert link_of(env, env.users[1]) is not None and link_of(env, env.users[0]) is None and link_of(env, env.users[2]) is None
    assert plan_of(env, env.users[1])["plan_code"] == "premium" and plan_of(env, env.users[0])["plan_code"] == "basic"


def test_event_metadata_cannot_override_ownership(env):
    reader_for(env, user_index=0)
    svc = service(env)
    forged = checkout_event(ref="REFAAAA2")                                            # an event claiming another candidate's checkout reference
    out, r = accept_and_process(env, svc, forged)
    assert r.status == "needs_review" and r.category == "ownership_ambiguous" and count(env, BillingProviderLink) == 0
    meta = sub_event()
    meta["data"]["object"]["metadata"] = {"user_id": str(env.users[2]), "client_reference_id": "REFAAAA2"}
    out, r = accept_and_process(env, svc, meta)
    assert link_of(env, env.users[2]) is None and link_of(env, env.users[0]).user_id == env.users[0]


def test_a_checkout_must_match_the_provider_session(env):
    svc = service(env)
    env.reader.set_subscription("sub_synth_1")
    env.reader.checkouts["cs_other"] = CheckoutAssociation("cs_other", "REFAAAA0", "sub_synth_1", False)
    out, r = accept_and_process(env, svc, sub_event())
    assert r.category == "checkout_mismatch"


def test_a_provider_customer_cannot_be_rebound_to_another_candidate(env):
    reader_for(env, user_index=0)
    svc = service(env)
    accept_and_process(env, svc, checkout_event(ref="REFAAAA0"))
    reader_for(env, user_index=1, sub="sub_synth_2", customer="cus_synth_1")          # same Stripe customer, different candidate's checkout
    out, r = accept_and_process(env, svc, sub_event(sub="sub_synth_2"))
    assert r.category == "customer_rebind" and link_of(env, env.users[1]) is None and plan_of(env, env.users[1])["plan_code"] == "basic"


def test_a_customer_swap_on_a_bound_subscription_is_refused(env):
    reader_for(env)
    svc = service(env)
    accept_and_process(env, svc, checkout_event(ref="REFAAAA0"))
    env.clock_now[0] += timedelta(seconds=5)
    env.reader.set_subscription("sub_synth_1", customer_id="cus_attacker")
    out, r = accept_and_process(env, svc, sub_event())
    assert r.category == "customer_mismatch" and link_of(env).provider_customer_id == "cus_synth_1"


def test_a_second_live_subscription_for_the_same_candidate_is_quarantined(env):
    reader_for(env)
    svc = service(env)
    accept_and_process(env, svc, checkout_event(ref="REFAAAA0"))
    env.reader.set_subscription("sub_synth_9", customer_id="cus_synth_9")
    env.reader.checkouts["cs_test_c1"] = CheckoutAssociation("cs_test_c1", "REFAAAA0", "sub_synth_9", False)
    out, r = accept_and_process(env, svc, sub_event(sub="sub_synth_9"))
    assert r.category == "duplicate_subscription" and count(env, BillingProviderLink) == 1


def test_a_sandbox_object_cannot_alter_state_in_another_environment(env):
    reader_for(env)
    env.reader.set_subscription("sub_synth_1", livemode=True)
    out, r = accept_and_process(env, service(env), checkout_event(ref="REFAAAA0"))
    assert r.category == "environment_mismatch" and count(env, BillingProviderLink) == 0


def test_price_and_terms_must_match_the_trusted_checkout(env):
    reader_for(env, price_id="price_other")
    assert accept_and_process(env, service(env), checkout_event(ref="REFAAAA0"))[1].category == "price_mismatch"
    reader_for(env, price_id="price_test_1", unit_amount=1)
    assert accept_and_process(env, service(env), checkout_event(ref="REFAAAA0"))[1].category == "price_mismatch"
    reader_for(env, unit_amount=1999, currency=None)
    assert accept_and_process(env, service(env), checkout_event(ref="REFAAAA0"))[1].category == "price_unverifiable"
    assert count(env, BillingProviderLink) == 0


def test_candidates_cannot_see_each_others_billing_state(http, env):
    # There is no candidate route that lists provider events or links; the status view is built from the caller's own rows only.
    paths = [p for p in http.app.openapi()["paths"] if p.startswith("/api/v1/billing")]
    assert not [p for p in paths if "event" in p or "link" in p or "subscription" in p]
    from src.billing.checkout import CheckoutService
    reader_for(env, user_index=0)
    accept_and_process(env, service(env), checkout_event(ref="REFAAAA0"))
    cs = CheckoutService(env.sf, app_base_url="https://app.example.test")
    mine, other = cs.status(env.users[0], "premium"), cs.status(env.users[1], "basic")
    assert mine["subscription"] == "active" and mine["entitlement"]["changed_by_billing"] is True
    assert other["subscription"] == "none" and other["entitlement"]["changed_by_billing"] is False


# ================================================================ 7. ENTITLEMENTS ==============================================================

def test_runtime_policy_is_unapproved_so_nothing_is_granted(env):
    reader_for(env)
    out, r = accept_and_process(env, service(env, policy=runtime_policy()), checkout_event(ref="REFAAAA0"))
    assert r.status == "processed" and r.decision == "policy_unapproved"
    assert plan_of(env, env.users[0])["plan_code"] == "basic" and count(env, BillingProviderLink) == 1
    with env.sf() as s:
        assert s.scalar(select(func.count()).select_from(Subscription).where(Subscription.source == "provider")) == 0
        d = s.scalar(select(BillingEntitlementDecision))
    assert d.decision == "policy_unapproved" and d.applied is False


def test_production_paid_activation_stays_disabled():
    assert P.LIVE_BILLING_ENABLED is False and P.EXTERNAL_CHECKOUT_AUTHORIZED is False
    assert P.STRIPE_WEBHOOK_AUTHORIZED is False and P.PAID_ENTITLEMENT_POLICY_APPROVED is False
    assert runtime_policy() is UNAPPROVED_POLICY and runtime_policy().approved is False
    from src.billing.wiring import build_provider_events
    svc = build_provider_events(make_session_factory(make_engine("sqlite://")))
    assert svc._policy.approved is False and isinstance(svc._reader, NullStateReader)
    assert P.PROVIDERS == ("mock",)


def test_verified_eligible_state_produces_the_entitlement_decision(env):
    reader_for(env)
    out, r = accept_and_process(env, service(env), checkout_event(ref="REFAAAA0"))
    assert r.decision == "grant" and plan_of(env, env.users[0])["plan_code"] == "premium"
    assert plan_of(env, env.users[0])["source"] == "subscription"


def test_active_without_a_paid_invoice_is_not_payment_evidence(env):
    reader_for(env, latest_invoice_state="open")
    out, r = accept_and_process(env, service(env), checkout_event(ref="REFAAAA0"))
    assert r.decision == "hold" and plan_of(env, env.users[0])["plan_code"] == "basic"


def test_checkout_completed_alone_is_not_proof_of_payment(env):
    reader_for(env, state="incomplete", latest_invoice_state="open")
    out, r = accept_and_process(env, service(env), checkout_event(ref="REFAAAA0"))
    assert r.decision == "none" and plan_of(env, env.users[0])["plan_code"] == "basic"


def test_checkout_redirect_cannot_grant_premium(env):
    from src.billing.checkout import CheckoutService
    cs = CheckoutService(env.sf, app_base_url="https://app.example.test")
    with env.sf() as s:
        public = s.scalar(select(BillingCheckoutSession.public_id).where(BillingCheckoutSession.user_id == env.users[0]))
    cs.record_return(env.users[0], public, "success")
    assert plan_of(env, env.users[0])["plan_code"] == "basic" and count(env, BillingProviderLink) == 0


@pytest.mark.parametrize("state,invoice,cancel_flag,expected", [
    ("active", "paid", False, "grant"), ("active", "paid", True, "grant"), ("trialing", "none", False, "grant"), ("past_due", "failed", False, "keep"),
    ("unpaid", "failed", False, "revoke"), ("canceled", "paid", False, "revoke"), ("incomplete", "open", False, "none"), ("paused", "none", False, "revoke"),
    ("incomplete_expired", "open", False, "revoke"),
])
def test_decision_table_under_the_synthetic_policy(state, invoice, cancel_flag, expected):
    link = SimpleNamespace(provider_state=state, latest_invoice_state=invoice, refund_state="none", dispute_state="none", cancel_at_period_end=cancel_flag)
    assert decide(link, SYNTHETIC_POLICY).action == expected


def test_undecided_owner_rules_hold_and_never_grant_or_revoke():
    undecided = EntitlementPolicy(policy_id="SYNTHETIC-UNDECIDED", approved=True, synthetic=True)
    for state in ("trialing", "past_due", "unpaid", "canceled", "paused"):
        link = SimpleNamespace(provider_state=state, latest_invoice_state="paid", refund_state="none", dispute_state="none")
        assert decide(link, undecided).action == "hold", state
    assert decide(SimpleNamespace(provider_state="active", latest_invoice_state="paid", refund_state="full", dispute_state="none"), undecided).action == "hold"
    assert decide(SimpleNamespace(provider_state="active", latest_invoice_state="paid", refund_state="none", dispute_state="open"), undecided).action == "hold"
    assert decide(SimpleNamespace(provider_state="active", latest_invoice_state="paid", refund_state="none", dispute_state="none"), undecided).action == "grant"
    with pytest.raises(ValueError):
        EntitlementPolicy(policy_id="x", approved=True, past_due="maybe")


def test_scheduled_cancellation_is_not_a_cancellation(env):
    reader_for(env, cancel_at_period_end=True)
    accept_and_process(env, service(env), checkout_event(ref="REFAAAA0"))
    assert link_of(env).cancel_at_period_end is True and plan_of(env, env.users[0])["plan_code"] == "premium"
    from src.billing.checkout import CheckoutService
    assert CheckoutService(env.sf, app_base_url="https://a.example").status(env.users[0], "premium")["subscription"] == "cancel_scheduled"


def test_cancellation_revokes_only_provider_owned_access_and_restores_basic(env):
    reader_for(env)
    svc = service(env)
    accept_and_process(env, svc, checkout_event(ref="REFAAAA0"))
    env.clock_now[0] += timedelta(seconds=5)
    env.reader.set_subscription("sub_synth_1", state="canceled")
    accept_and_process(env, svc, sub_event("customer.subscription.deleted"))
    p = plan_of(env, env.users[0])
    assert p["plan_code"] == "basic"
    with env.sf() as s:
        active = s.scalars(select(Subscription).where(Subscription.user_id == env.users[0], Subscription.status == "active")).all()
    assert len(active) == 1 and active[0].source == "system_default"


def test_manual_admin_assignments_are_never_overridden_or_revoked(env):
    with env.sf() as s:
        basic_active = s.scalar(select(Subscription).where(Subscription.user_id == env.users[0], Subscription.status == "active"))
        if basic_active is not None:
            basic_active.status = "ended"
            s.flush()
        s.add(Subscription(user_id=env.users[0], plan_version_id=env.pv_premium, status="active", source="admin"))
        s.commit()
    reader_for(env)
    svc = service(env)
    out, r = accept_and_process(env, svc, checkout_event(ref="REFAAAA0"))
    assert r.decision == "skipped_manual_assignment"
    env.clock_now[0] += timedelta(seconds=5)
    env.reader.set_subscription("sub_synth_1", state="canceled")
    accept_and_process(env, svc, sub_event("customer.subscription.deleted"))
    with env.sf() as s:
        row = s.scalar(select(Subscription).where(Subscription.user_id == env.users[0], Subscription.status == "active"))
    assert row.source == "admin" and plan_of(env, env.users[0])["plan_code"] == "premium"


def test_replayed_events_never_extend_or_duplicate_access(env):
    reader_for(env)
    svc = service(env)
    for _ in range(3):
        env.clock_now[0] += timedelta(seconds=5)
        accept_and_process(env, svc, sub_event())
    with env.sf() as s:
        rows = s.scalars(select(Subscription).where(Subscription.user_id == env.users[0], Subscription.source == "provider")).all()
    assert len(rows) == 1 and rows[0].ended_at is None


def test_full_refund_and_lost_dispute_follow_the_explicit_policy(env):
    reader_for(env)
    env.reader.payments["pi_synth_1"] = "sub_synth_1"
    svc = service(env)
    accept_and_process(env, svc, checkout_event(ref="REFAAAA0"))
    env.clock_now[0] += timedelta(seconds=5)
    accept_and_process(env, svc, refund_event(refunded=500))                           # partial: keeps access under this policy
    assert link_of(env).refund_state == "partial" and plan_of(env, env.users[0])["plan_code"] == "premium"
    env.clock_now[0] += timedelta(seconds=5)
    accept_and_process(env, svc, dispute_event())                                       # open dispute: keep (synthetic policy)
    assert link_of(env).dispute_state == "open" and plan_of(env, env.users[0])["plan_code"] == "premium"
    env.clock_now[0] += timedelta(seconds=5)
    accept_and_process(env, svc, dispute_event("charge.dispute.closed", "lost"))
    assert link_of(env).dispute_state == "lost" and plan_of(env, env.users[0])["plan_code"] == "basic"
    env.clock_now[0] += timedelta(seconds=5)
    accept_and_process(env, svc, dispute_event("charge.dispute.closed", "won"))        # a lost dispute never reverts
    assert link_of(env).dispute_state == "lost"


def test_a_refund_under_an_approved_keep_policy_keeps_access(env):
    keep = EntitlementPolicy(policy_id="SYNTHETIC-KEEP", approved=True, full_refund="keep", synthetic=True)
    reader_for(env)
    env.reader.payments["pi_synth_1"] = "sub_synth_1"
    svc = service(env, policy=keep)
    accept_and_process(env, svc, checkout_event(ref="REFAAAA0"))
    accept_and_process(env, svc, refund_event())
    assert link_of(env).refund_state == "full" and plan_of(env, env.users[0])["plan_code"] == "premium"


def test_recovery_after_payment_failure_restores_the_normal_state(env):
    reader_for(env)
    svc = service(env)
    accept_and_process(env, svc, checkout_event(ref="REFAAAA0"))
    env.clock_now[0] += timedelta(seconds=5)
    env.reader.set_subscription("sub_synth_1", state="past_due", latest_invoice_state="failed")
    accept_and_process(env, svc, invoice_event("invoice.payment_failed"))
    assert plan_of(env, env.users[0])["plan_code"] == "premium"                         # a failed attempt alone does not revoke (grace stays an owner decision)
    env.clock_now[0] += timedelta(seconds=5)
    env.reader.set_subscription("sub_synth_1", state="active", latest_invoice_state="paid")
    accept_and_process(env, svc, invoice_event("invoice.paid"))
    assert link_of(env).provider_state == "active" and plan_of(env, env.users[0])["plan_code"] == "premium"


def test_synthetic_policy_is_never_the_runtime_policy():
    assert SYNTHETIC_POLICY.synthetic is True and runtime_policy().synthetic is False
    assert UNAPPROVED_POLICY.approved is False


# ================================================================ 8. PROVIDER-INITIATED FACTS, AUDIT, SOURCE GUARDS ============================

def test_provider_initiated_refund_is_recorded_without_two_person_approval(env):
    reader_for(env)
    env.reader.payments["pi_synth_1"] = "sub_synth_1"
    from src.persistence import BillingApprovalRequest
    svc = service(env)
    accept_and_process(env, svc, checkout_event(ref="REFAAAA0"))
    accept_and_process(env, svc, refund_event())
    assert link_of(env).refund_state == "full" and count(env, BillingApprovalRequest) == 0       # an external fact needs no approval and creates none


def test_audit_records_ids_and_bounded_categories_only(env):
    seen = []
    audit = SimpleNamespace(record=lambda **k: seen.append(k))
    reader_for(env)
    svc = service(env, audit=audit)
    rcv = receiver(env, svc=svc, audit=audit)
    ev = checkout_event(ref="REFAAAA0")
    deliver(env, rcv, ev)
    with pytest.raises(SE.WebhookError):
        rcv.handle(body(ev), "t=1,v1=00")
    svc.process(svc.accept(ev)["public_id"])
    types = {a["event_type"] for a in seen}
    assert {"billing.webhook_received", "billing.webhook_event_accepted", "billing.webhook_signature_rejected", "billing.webhook_duplicate_ignored"} <= types
    blob = json.dumps(seen, default=str)
    assert SECRET not in blob and "whsec_" not in blob and "sk_" not in blob and "t=1,v1" not in blob and "u0@x.test" not in blob


def test_stored_event_holds_only_allow_listed_fields(env):
    ev = checkout_event(ref="REFAAAA0")
    ev["data"]["object"]["customer_details"] = {"email": "secret.person@example.com", "name": "Secret Person", "address": {"line1": "1 Road"}}
    ev["data"]["object"]["payment_method_details"] = {"card": {"last4": "4242"}}
    service(env).accept(ev)
    with env.sf() as s:
        row = s.scalar(select(BillingProviderEvent))
    blob = json.dumps(row.normalized_json) + json.dumps(row.reconciliation_json or {})
    assert "secret.person" not in blob and "4242" not in blob and "Road" not in blob and "Secret Person" not in blob
    assert set(row.normalized_json) <= {"kind", "subscription_id", "customer_id", "checkout_session_id", "client_reference_id", "payment_status", "mode"}


def test_live_and_checkout_gates_are_untouched_and_no_stripe_credentials_are_read_by_tests():
    assert P.LIVE_BILLING_ENABLED is False and P.EXTERNAL_CHECKOUT_AUTHORIZED is False


def test_allow_list_is_explicit_and_excludes_unverified_event_families():
    assert set(SE.ALLOWED_EVENT_TYPES) == {
        "checkout.session.completed", "checkout.session.async_payment_succeeded", "checkout.session.async_payment_failed", "customer.subscription.created",
        "customer.subscription.updated", "customer.subscription.deleted", "customer.subscription.paused", "customer.subscription.resumed", "invoice.paid",
        "invoice.payment_failed", "invoice.payment_action_required", "charge.refunded", "charge.dispute.created", "charge.dispute.closed"}
    assert not {"refund.created", "refund.updated"} & set(SE.ALLOWED_EVENT_TYPES)


def test_the_bridge_is_the_only_writer_of_provider_subscriptions():
    offenders = []
    for path in (ROOT / "src").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if 'source="provider"' in text or "source='provider'" in text:
            offenders.append(path.relative_to(ROOT).as_posix())
    assert offenders == ["src/billing/entitlement_bridge.py"]


def test_route_and_receiver_have_no_unrestricted_cors_or_generic_editor():
    src = (ROOT / "src/api/routes/billing_webhooks.py").read_text()
    assert "allow_origins" not in src and "CORSMiddleware" not in src and "setting" not in src.lower().replace("settings", "")


# ================================================================ 9. REAL STRIPE READER (FAKE CLIENT) ==========================================

def test_stripe_reader_normalises_a_subscription_from_a_fake_client():
    from src.billing.provider_state import StripeStateReader
    sub = {"id": "sub_1", "customer": "cus_1", "status": "active", "cancel_at_period_end": False, "livemode": False,
           "items": {"data": [{"price": {"id": "price_1", "currency": "eur", "unit_amount": 1999, "recurring": {"interval": "month"}}, "current_period_end": 1_900_000_000}]},
           "latest_invoice": {"id": "in_1", "status": "paid"}}
    client = SimpleNamespace(v1=SimpleNamespace(subscriptions=SimpleNamespace(retrieve=lambda i, p: sub)))
    snap = StripeStateReader(lambda: client).get_subscription("sub_1")
    assert (snap.state, snap.price_id, snap.currency, snap.interval, snap.unit_amount, snap.latest_invoice_state) == ("active", "price_1", "EUR", "month", 1999, "paid")
    assert snap.current_period_end == datetime.fromtimestamp(1_900_000_000, tz=timezone.utc)


def test_stripe_reader_rejects_incomplete_and_multi_item_answers_and_maps_outages():
    from src.billing.provider_state import StripeStateReader
    bad = {"id": "sub_1", "customer": "cus_1", "status": "active", "items": {"data": [{}, {}]}}
    client = SimpleNamespace(v1=SimpleNamespace(subscriptions=SimpleNamespace(retrieve=lambda i, p: bad)))
    with pytest.raises(ProviderStateInvalid):
        StripeStateReader(lambda: client).get_subscription("sub_1")

    class APIConnectionError(Exception):
        pass

    def down(i, p):
        raise APIConnectionError("timed out contacting api with sk_test_LEAK")
    client = SimpleNamespace(v1=SimpleNamespace(subscriptions=SimpleNamespace(retrieve=down)))
    with pytest.raises(ProviderStateUnavailable) as e:
        StripeStateReader(lambda: client).get_subscription("sub_1")
    assert "sk_test" not in str(e.value) and e.value.category == "provider_timeout"


def test_stripe_reader_maps_a_payment_to_its_subscription_through_the_invoice_parent():
    from src.billing.provider_state import StripeStateReader
    inv = {"id": "in_1", "parent": {"type": "subscription_details", "subscription_details": {"subscription": "sub_1"}}}
    client = SimpleNamespace(v1=SimpleNamespace(
        invoice_payments=SimpleNamespace(list=lambda p: {"data": [{"invoice": "in_1"}]}), invoices=SimpleNamespace(retrieve=lambda i: inv),
        charges=SimpleNamespace(retrieve=lambda c: {"payment_intent": "pi_1"})))
    r = StripeStateReader(lambda: client)
    assert r.subscription_for_payment(payment_intent="pi_1", charge=None) == "sub_1" and r.subscription_for_payment(payment_intent=None, charge="ch_1") == "sub_1"
    assert StripeStateReader(lambda: SimpleNamespace(v1=SimpleNamespace(charges=SimpleNamespace(retrieve=lambda c: {"payment_intent": None})))).subscription_for_payment(
        payment_intent=None, charge="ch_1") is None


def test_null_reader_refuses_every_read():
    for fn in (NullStateReader().get_subscription, NullStateReader().checkout_session, NullStateReader().checkout_for_subscription):
        with pytest.raises(ProviderStateUnavailable):
            fn("x")


# ================================================================ 10. MIGRATION ================================================================

def test_migration_0029_upgrade_downgrade_and_constraint_widening(tmp_path, monkeypatch):
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine, inspect, text

    url = f"sqlite:///{tmp_path / 'm.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    cfg = Config("alembic.ini")
    cfg.set_main_option("script_location", "migrations")
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "0028_checkout_sessions")
    eng = create_engine(url)
    assert "billing_provider_links" not in inspect(eng).get_table_names()
    command.upgrade(cfg, "head")
    insp = inspect(create_engine(url))
    assert {"billing_provider_events", "billing_provider_links", "billing_entitlement_decisions"} <= set(insp.get_table_names())
    uniques = {tuple(u["column_names"]) for u in insp.get_unique_constraints("billing_provider_events")}
    assert ("provider", "environment", "provider_event_id") in uniques
    with create_engine(url).begin() as c:                      # the widened constraint accepts 'provider' and still rejects anything else
        cols = "user_id, plan_version_id, status, source, started_at"
        c.execute(text("PRAGMA foreign_keys=OFF"))
        c.execute(text(f"INSERT INTO subscriptions ({cols}) VALUES (1, 1, 'ended', 'provider', '2026-01-01')"))
        with pytest.raises(Exception):
            c.execute(text(f"INSERT INTO subscriptions ({cols}) VALUES (1, 1, 'ended', 'bogus', '2026-01-01')"))
    with pytest.raises(Exception, match="Refusing to downgrade"):          # the provider row is real data: the downgrade refuses instead of deleting it
        command.downgrade(cfg, "0028_checkout_sessions")
    with create_engine(url).begin() as c:
        c.execute(text("DELETE FROM subscriptions WHERE source = 'provider'"))      # the operator's deliberate, backed-up clean-up (see the runbook)
    command.downgrade(cfg, "0028_checkout_sessions")
    assert "billing_provider_links" not in inspect(create_engine(url)).get_table_names()
    command.upgrade(cfg, "head")
    heads = __import__("alembic.script", fromlist=["ScriptDirectory"]).ScriptDirectory.from_config(cfg).get_heads()
    assert heads == ["0029_provider_webhooks"]
    text_ = (ROOT / "migrations/versions/0029_provider_webhooks.py").read_text()
    assert "create_all" not in text_ and "stamp" not in text_


# ================================================================ 11. BACKGROUND JOBS ==========================================================

def _worker(env, svc):
    from src.billing.runtime import BillingRuntime
    from src.jobs.service import JobService
    from src.jobs.worker import Worker
    jobs = JobService(env.sf)
    rt = BillingRuntime(session_factory=env.sf, provider_events=svc, jobs=jobs)
    return jobs, Worker(jobs, services=SimpleNamespace(billing=rt))


def test_job_types_are_registered_with_id_only_payloads_and_no_admin_enqueue():
    from src.jobs.registry import REGISTRY
    for code in (P.JOB_PROCESS_PROVIDER_EVENT, P.JOB_PROVIDER_RECONCILE):
        assert code in REGISTRY and REGISTRY[code].admin_enqueue is False
    assert set(REGISTRY[P.JOB_PROCESS_PROVIDER_EVENT].payload_model.model_fields) == {"event_id"}


def test_duplicate_background_jobs_for_one_event_collapse_and_process_once(env):
    reader_for(env)
    svc = service(env)
    jobs, worker = _worker(env, svc)
    out = svc.accept(checkout_event(ref="REFAAAA0"))
    a, created_a = jobs.enqueue(P.JOB_PROCESS_PROVIDER_EVENT, {"event_id": out["public_id"]}, idempotency_key=f"bpe:{out['public_id']}")
    b, created_b = jobs.enqueue(P.JOB_PROCESS_PROVIDER_EVENT, {"event_id": out["public_id"]}, idempotency_key=f"bpe:{out['public_id']}")
    assert created_a and not created_b and a["public_id"] == b["public_id"]
    assert worker.run_once() == "succeeded" and worker.run_once() == "idle"
    assert count(env, BillingProviderLink) == 1 and plan_of(env, env.users[0])["plan_code"] == "premium"


def test_worker_retries_a_provider_outage_then_succeeds(env):
    reader_for(env)
    svc = service(env)
    jobs, worker = _worker(env, svc)
    env.reader.fail, env.reader.fail_times = ProviderStateUnavailable("provider_unavailable"), 1
    out = svc.accept(checkout_event(ref="REFAAAA0"))
    jobs.enqueue(P.JOB_PROCESS_PROVIDER_EVENT, {"event_id": out["public_id"]}, idempotency_key=f"bpe:{out['public_id']}")
    assert worker.run_once() == "retry_scheduled"
    assert count(env, BillingProviderLink) == 0


def test_sweep_job_runs_the_bounded_reconciliation(env):
    reader_for(env)
    with env.sf() as s:
        cs = s.scalar(select(BillingCheckoutSession).where(BillingCheckoutSession.user_id == env.users[0]))
        cs.browser_returned_at = env.clock_now[0]
        s.commit()
    svc = service(env)
    jobs, worker = _worker(env, svc)
    jobs.enqueue(P.JOB_PROVIDER_RECONCILE, {"batch": 10})
    assert worker.run_once() == "succeeded" and link_of(env) is not None
    with pytest.raises(Exception):
        jobs.enqueue(P.JOB_PROVIDER_RECONCILE, {"batch": 10_000})
    with pytest.raises(Exception):
        jobs.enqueue(P.JOB_PROVIDER_RECONCILE, {"batch": 5, "secret": "x"})


def test_a_job_without_a_configured_runtime_fails_permanently_not_silently(env):
    from src.billing.runtime import BillingRuntime
    from src.jobs.service import JobService
    from src.jobs.worker import Worker
    jobs = JobService(env.sf)
    jobs.enqueue(P.JOB_PROCESS_PROVIDER_EVENT, {"event_id": "0" * 32})
    assert Worker(jobs, services=SimpleNamespace(billing=BillingRuntime(session_factory=env.sf))).run_once() == "failed"


# ================================================================ 12. PRE-MERGE QUALIFICATION (migration safety, cancellation scope, call paths) =====

def _alembic(tmp_path, monkeypatch):
    from alembic.config import Config
    url = f"sqlite:///{tmp_path / 'q.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    cfg = Config("alembic.ini")
    cfg.set_main_option("script_location", "migrations")
    cfg.set_main_option("sqlalchemy.url", url)
    return cfg, url


def _version(url):
    from sqlalchemy import create_engine, text
    with create_engine(url).connect() as c:
        return c.execute(text("SELECT version_num FROM alembic_version")).scalar()


def _tables(url):
    from sqlalchemy import create_engine, inspect
    return set(inspect(create_engine(url)).get_table_names())


def test_migration_fresh_upgrade_and_single_head(tmp_path, monkeypatch):
    from alembic import command
    from alembic.script import ScriptDirectory
    cfg, url = _alembic(tmp_path, monkeypatch)
    command.upgrade(cfg, "head")
    assert _version(url) == "0029_provider_webhooks" and ScriptDirectory.from_config(cfg).get_heads() == ["0029_provider_webhooks"]


def test_upgrade_from_0028_preserves_existing_subscriptions_and_partial_unique_indexes(tmp_path, monkeypatch):
    from alembic import command
    from sqlalchemy import create_engine, text
    cfg, url = _alembic(tmp_path, monkeypatch)
    command.upgrade(cfg, "0028_checkout_sessions")
    sf = make_session_factory(create_engine(url))
    with sf() as s:
        u = User(subject="u", provider="local", email="u@x.test")
        s.add(u)
        s.flush()
        pv = s.scalar(select(PlanVersion).where(PlanVersion.plan_code == "basic"))
        s.add_all([Subscription(user_id=u.id, plan_version_id=pv.id, status="ended", source="migration"),
                   Subscription(user_id=u.id, plan_version_id=pv.id, status="active", source="admin")])
        s.commit()
        uid = u.id
    command.upgrade(cfg, "head")
    with create_engine(url).connect() as c:
        rows = c.execute(text("SELECT status, source FROM subscriptions WHERE user_id = :u ORDER BY id"), {"u": uid}).all()
    assert rows == [("ended", "migration"), ("active", "admin")]                                  # nothing lost, nothing rewritten
    with pytest.raises(Exception):                                                                # the partial unique index survived the table rebuild
        with create_engine(url).begin() as c:
            c.execute(text(f"INSERT INTO subscriptions (user_id, plan_version_id, status, source, started_at) VALUES ({uid}, 1, 'active', 'provider', '2026-01-01')"))


def test_downgrade_on_an_empty_provider_surface_succeeds_and_reupgrades(tmp_path, monkeypatch):
    from alembic import command
    cfg, url = _alembic(tmp_path, monkeypatch)
    command.upgrade(cfg, "head")
    sf = make_session_factory(__import__("sqlalchemy").create_engine(url))
    with sf() as s:                                                                               # unrelated rows are untouched by a downgrade
        s.add(User(subject="keep", provider="local", email="k@x.test"))
        s.commit()
    command.downgrade(cfg, "0028_checkout_sessions")
    assert _version(url) == "0028_checkout_sessions" and "billing_provider_links" not in _tables(url)
    with sf() as s:
        assert s.scalar(select(func.count()).select_from(User)) == 1
    command.upgrade(cfg, "head")
    assert _version(url) == "0029_provider_webhooks" and "billing_provider_events" in _tables(url)


@pytest.mark.parametrize("seed", ["subscription", "event", "link", "decision"])
def test_downgrade_fails_closed_when_any_provider_record_exists_and_deletes_nothing(tmp_path, monkeypatch, seed):
    from alembic import command
    from sqlalchemy import create_engine, text
    cfg, url = _alembic(tmp_path, monkeypatch)
    command.upgrade(cfg, "head")
    now = utcnow()
    sf = make_session_factory(create_engine(url))
    with sf() as s:
        if seed == "subscription":
            s.add(Subscription(user_id=1, plan_version_id=1, status="active", source="provider"))
        elif seed == "event":
            s.add(BillingProviderEvent(public_id="e" * 32, provider=P.PROVIDER_STRIPE_MP, environment="sandbox", provider_event_id="evt_x", event_type="invoice.paid",
                                       received_at=now, normalized_json={}))
        elif seed == "link":
            s.add(BillingProviderLink(public_id="l" * 32, provider=P.PROVIDER_STRIPE_MP, environment="sandbox", provider_subscription_id="sub_x", provider_customer_id="cus_x",
                                      user_id=1, plan_version_id=1, commercial_terms_id=1, price_mapping_id=1, created_at=now, updated_at=now))
        else:
            s.add(BillingEntitlementDecision(link_id=1, decision="grant", reason="r", policy_id="p", provider_state="active", created_at=now))
        s.commit()
    with pytest.raises(Exception) as e:
        command.downgrade(cfg, "0028_checkout_sessions")
    assert "Refusing to downgrade" in str(e.value) and "backup" in str(e.value)
    assert _version(url) == "0029_provider_webhooks" and "billing_provider_links" in _tables(url)         # nothing was dropped
    with create_engine(url).connect() as c:
        total = sum(c.execute(text(f"SELECT COUNT(*) FROM {t}")).scalar() for t in ("billing_provider_events", "billing_provider_links", "billing_entitlement_decisions"))
        total += c.execute(text("SELECT COUNT(*) FROM subscriptions WHERE source = 'provider'")).scalar()
    assert total == 1                                                                                 # the seeded record is intact


def test_the_migration_source_never_deletes_provider_data():
    src = (ROOT / "migrations/versions/0029_provider_webhooks.py").read_text()
    assert "DELETE FROM" not in src and "FAIL CLOSED" in src and "RuntimeError" in src


# ---------------------------------------------------------------- cancellation is scoped to ONE provider subscription id ----------------------------

class _CheckoutProvider:
    name, live, environment = P.PROVIDER_STRIPE_MP, False, "sandbox"

    def __init__(self):
        self.n = 0

    def capabilities(self):
        return {"checkout": True}

    def create_checkout_session(self, req):
        from src.billing.provider import CheckoutResult
        self.n += 1
        return CheckoutResult(provider_session_id=f"cs_test_new{self.n}", url=f"https://checkout.stripe.test/{self.n}")


def _checkout_service(env):
    from src.billing.checkout import CheckoutService
    mode = SimpleNamespace(provider=P.PROVIDER_STRIPE_MP, environment="sandbox", enabled=False, live=False)
    return CheckoutService(env.sf, provider=_CheckoutProvider(), mode=mode, app_base_url="https://app.example.test", api_env="production",
                           readiness=lambda: "sandbox_access_unverified", clock=lambda: env.clock_now[0])


def _cancel_first_subscription(env, svc):
    reader_for(env)
    accept_and_process(env, svc, checkout_event(ref="REFAAAA0"))
    env.clock_now[0] += timedelta(seconds=5)
    env.reader.set_subscription("sub_synth_1", state="canceled")
    accept_and_process(env, svc, sub_event("customer.subscription.deleted"))
    assert link_of(env).provider_state == "canceled" and plan_of(env, env.users[0])["plan_code"] == "basic"


def test_a_live_subscription_blocks_a_second_purchase_but_a_canceled_one_does_not(env):
    from src.billing.checkout import CheckoutConflict
    svc, co = service(env), _checkout_service(env)
    reader_for(env)
    accept_and_process(env, svc, checkout_event(ref="REFAAAA0"))
    with pytest.raises(CheckoutConflict):
        co.create(env.users[0], "premium", "new-purchase-key-01")                                  # live subscription: no double charge
    env.clock_now[0] += timedelta(seconds=5)
    env.reader.set_subscription("sub_synth_1", state="canceled")
    accept_and_process(env, svc, sub_event("customer.subscription.deleted"))
    out = co.create(env.users[0], "premium", "new-purchase-key-02")                                # canceled is final for THAT subscription only
    assert out["status"] == "open" and out["redirect_url"]


def test_a_genuinely_new_subscription_after_cancellation_is_reconciled_and_granted(env):
    svc, co = service(env), _checkout_service(env)
    _cancel_first_subscription(env, svc)
    new = co.create(env.users[0], "premium", "new-purchase-key-03")
    with env.sf() as s:
        row = s.scalar(select(BillingCheckoutSession).where(BillingCheckoutSession.public_id == new["checkout_id"]))
        assert row.user_id == env.users[0] and row.provider_session_id == "cs_test_new1"
        old = s.scalar(select(BillingCheckoutSession).where(BillingCheckoutSession.user_id == env.users[0], BillingCheckoutSession.status == "expired"))
        assert old is not None and old.checkout_url is None                                        # the consumed checkout can never be reused
    env.clock_now[0] += timedelta(seconds=5)
    env.reader.set_subscription("sub_synth_2", customer_id="cus_synth_1")                         # the same candidate's provider customer, a NEW subscription id
    env.reader.checkouts["cs_test_new1"] = CheckoutAssociation("cs_test_new1", new["checkout_id"], "sub_synth_2", False)
    out, r = accept_and_process(env, svc, checkout_event(session="cs_test_new1", ref=new["checkout_id"], sub="sub_synth_2"))
    assert r.status == "processed" and r.decision == "grant"
    with env.sf() as s:
        links = s.scalars(select(BillingProviderLink).where(BillingProviderLink.user_id == env.users[0]).order_by(BillingProviderLink.id)).all()
    assert [(l.provider_subscription_id, l.provider_state) for l in links] == [("sub_synth_1", "canceled"), ("sub_synth_2", "active")]
    assert plan_of(env, env.users[0])["plan_code"] == "premium"


def test_stale_events_for_the_old_subscription_cannot_revoke_or_reactivate_around_the_new_one(env):
    svc, co = service(env), _checkout_service(env)
    _cancel_first_subscription(env, svc)
    new = co.create(env.users[0], "premium", "new-purchase-key-04")
    env.clock_now[0] += timedelta(seconds=5)
    env.reader.set_subscription("sub_synth_2", customer_id="cus_synth_1")
    env.reader.checkouts["cs_test_new1"] = CheckoutAssociation("cs_test_new1", new["checkout_id"], "sub_synth_2", False)
    accept_and_process(env, svc, checkout_event(session="cs_test_new1", ref=new["checkout_id"], sub="sub_synth_2"))
    env.clock_now[0] += timedelta(seconds=5)
    out, r = accept_and_process(env, svc, sub_event("customer.subscription.deleted", sub="sub_synth_1"))        # the OLD subscription's late cancellation again
    assert plan_of(env, env.users[0])["plan_code"] == "premium"                                    # a later event for the old link never revokes the newer grant
    env.reader.set_subscription("sub_synth_1", state="active")
    out, r = accept_and_process(env, svc, sub_event("customer.subscription.updated", sub="sub_synth_1"))
    assert r.category == "terminal_reactivation_refused"
    with env.sf() as s:
        old = s.scalar(select(BillingProviderLink).where(BillingProviderLink.provider_subscription_id == "sub_synth_1"))
    assert old.provider_state == "canceled"


def test_a_new_subscription_cannot_be_assigned_to_another_candidate(env):
    svc = service(env)
    _cancel_first_subscription(env, svc)
    env.reader.set_subscription("sub_synth_3", customer_id="cus_synth_1")                         # candidate 0's provider customer ...
    env.reader.checkouts["cs_test_c2"] = CheckoutAssociation("cs_test_c2", "REFAAAA1", "sub_synth_3", False)       # ... presented with candidate 1's checkout
    out, r = accept_and_process(env, svc, checkout_event(session="cs_test_c2", ref="REFAAAA1", sub="sub_synth_3"))
    assert r.category == "customer_rebind" and link_of(env, env.users[1]) is None and plan_of(env, env.users[1])["plan_code"] == "basic"


def test_a_second_live_subscription_is_still_quarantined_if_it_reaches_reconciliation(env):
    svc = service(env)
    reader_for(env)
    accept_and_process(env, svc, checkout_event(ref="REFAAAA0"))
    env.reader.set_subscription("sub_synth_dup", customer_id="cus_synth_1")
    env.reader.checkouts["cs_test_c1"] = CheckoutAssociation("cs_test_c1", "REFAAAA0", "sub_synth_dup", False)
    assert accept_and_process(env, svc, sub_event(sub="sub_synth_dup"))[1].category == "duplicate_subscription"


# ---------------------------------------------------------------- real call paths (not source text) ---------------------------------------------

def test_the_bridge_is_reached_only_from_reconciliation_not_from_the_webhook_or_checkout_paths(env, monkeypatch):
    import src.billing.entitlement_bridge as B
    import src.billing.reconcile as R
    from src.billing.checkout import CheckoutService
    calls = []
    real = B.evaluate_and_apply
    monkeypatch.setattr(R, "evaluate_and_apply", lambda *a, **k: calls.append("reconcile") or real(*a, **k))
    monkeypatch.setattr(B, "evaluate_and_apply", lambda *a, **k: calls.append("direct") or real(*a, **k))
    reader_for(env)
    svc = service(env)
    deliver(env, receiver(env, svc=svc), checkout_event(ref="REFAAAA0"))                          # authenticate + accept
    with env.sf() as s:
        public = s.scalar(select(BillingCheckoutSession.public_id).where(BillingCheckoutSession.user_id == env.users[0]))
    CheckoutService(env.sf, app_base_url="https://a.example").record_return(env.users[0], public, "success")      # browser return
    assert calls == [] and plan_of(env, env.users[0])["plan_code"] == "basic"
    svc.sweep()                                                                                   # only the reconciliation path reaches the bridge
    assert calls == ["reconcile"]


def test_only_reconciliation_calls_the_bridge_in_the_source_tree():
    callers = sorted(p.relative_to(ROOT).as_posix() for p in (ROOT / "src").rglob("*.py") if "evaluate_and_apply(" in p.read_text(encoding="utf-8"))
    assert callers == ["src/billing/entitlement_bridge.py", "src/billing/reconcile.py"]      # definition + the single call site


def test_the_deployed_dependency_graph_is_unauthorized_unapproved_and_unwired(env):
    from src.api import dependencies as deps
    store = SimpleNamespace(get_for_runtime=lambda name: SimpleNamespace(get_secret_value=lambda: SECRET))
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(settings=SimpleNamespace(env="production"))))
    repo = SimpleNamespace(session_factory=env.sf)
    rcv = deps.get_webhook_receiver(request, repo, store)
    assert rcv._authorized is False
    assert rcv._events._policy.approved is False and rcv._events._policy.synthetic is False
    assert isinstance(rcv._events._reader, NullStateReader)
    raw = body(checkout_event())
    with pytest.raises(SE.WebhookError) as e:
        rcv.handle(raw, sign(raw))                                                                # even a perfectly signed event is refused
    assert e.value.status == 503 and count(env, BillingProviderEvent) == 0
    from src.billing.wiring import build_billing_runtime
    rt = build_billing_runtime(env.sf)
    assert rt.provider_events._policy.approved is False and isinstance(rt.provider_events._reader, NullStateReader)


def test_a_synthetic_policy_cannot_be_used_in_a_hosted_environment(env, monkeypatch):
    monkeypatch.setenv("API_ENV", "production")
    with pytest.raises(ValueError):
        service(env)                                                                              # SYNTHETIC_POLICY
    monkeypatch.setenv("API_ENV", "staging")
    with pytest.raises(ValueError):
        service(env)
    service(env, policy=UNAPPROVED_POLICY)                                                        # the real runtime policy is always allowed
    monkeypatch.setenv("API_ENV", "test")
    service(env)


def test_two_person_financial_approvals_are_unchanged():
    from src.application import admin_permissions as perm
    from src.persistence import BillingApprovalRequest
    assert any("ck_bar_no_self_approval" in str(c.name) for c in BillingApprovalRequest.__table__.constraints)
    assert len(perm.PERMISSIONS) == 43
