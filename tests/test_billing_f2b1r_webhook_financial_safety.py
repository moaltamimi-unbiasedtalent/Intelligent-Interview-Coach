# ruff: noqa: F811
"""W12.4D-F2-B1R: validly signed FINANCIAL webhooks under an unsupported API version are durable, visible, recoverable only through an authorized operator
path, reconciled only from authoritative provider state, and fail closed. FULLY OFFLINE (fake reader, synthetic secret, blocked sockets, isolated database).
``SYNTHETIC_POLICY`` is not an owner decision."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import func, select

from src.billing import policy as P
from src.billing.entitlement_bridge import runtime_policy
from src.billing.operations import BillingOperations
from src.billing.provider_state import (
    DisputeSnapshot, InvoiceSnapshot, NullStateReader, ProviderStateUnavailable,
)
from src.billing.reconcile import ProviderEventService
from src.persistence import BillingProviderEvent, BillingProviderLink, Subscription
from tests.test_webhooks_w12_4d_d import (  # noqa: F401  (shared fixtures and factories)
    SECRET, SYNTHETIC_POLICY, _no_network, accept_and_process, body, checkout_event, count, deliver, dispute_event, env, event, invoice_event, link_of, plan_of,
    reader_for, receiver, refund_event, service, sign, sub_event,
)

OLD = "2020-01-01"


def events_of(env):
    with env.sf() as s:
        return s.scalars(select(BillingProviderEvent).order_by(BillingProviderEvent.id)).all()


def provider_rows(env):
    with env.sf() as s:
        return s.scalar(select(func.count()).select_from(Subscription).where(Subscription.source == "provider"))


def grant_first(env):
    """A compatible checkout grants Premium under the synthetic policy, so a later incompatible event has something to (wrongly) change."""
    reader_for(env)
    svc = service(env)
    accept_and_process(env, svc, checkout_event(ref="REFAAAA0"))
    assert plan_of(env, env.users[0])["plan_code"] == "premium"
    return svc


def ops(env, reader=True):
    return BillingOperations(env.sf, environment="sandbox", provider_selected=P.PROVIDER_STRIPE_MP, reader_available=reader, readiness=lambda: {"status": "configured_not_tested"})


# ---------------------------------------------------------------- classification at the door ----------------------------------------------------------------

def test_supported_compatible_financial_event_is_accepted_and_processed_as_before(env):
    reader_for(env)
    out, r = accept_and_process(env, service(env), checkout_event(ref="REFAAAA0"))
    assert out["disposition"] == "accepted" and r.status == "processed" and plan_of(env, env.users[0])["plan_code"] == "premium"


def test_invalid_signature_stores_nothing_whatever_the_version(env):
    rcv = receiver(env)
    raw = body(sub_event(api_version=OLD))
    from src.billing import stripe_events as SE
    with pytest.raises(SE.WebhookError):
        rcv.handle(raw, sign(raw, "whsec_attacker_secret_value_0000000000"))
    assert events_of(env) == []


@pytest.mark.parametrize("etype", ["customer.updated", "payment_intent.succeeded", "refund.created", "some.unknown.event"])
@pytest.mark.parametrize("version", [OLD, "2099-01-01.future", None])
def test_irrelevant_event_types_stay_ignored_whatever_their_version(env, etype, version):
    out = service(env).accept(event(etype, {"id": "x_1"}, api_version=version))
    assert out["disposition"] == "ignored"
    (row,) = events_of(env)
    assert (row.status, row.failure_category) == ("ignored", "unsupported_event_type")


@pytest.mark.parametrize("make", [sub_event, invoice_event, checkout_event, refund_event, dispute_event])
def test_every_incompatible_financial_kind_is_held_with_reference_only_and_acknowledged(env, make):
    rcv = receiver(env)
    ev = make(api_version=OLD)
    assert deliver(env, rcv, ev) == {"status": "accepted"}                                   # acknowledged: it is durably stored, so Stripe must not retry forever
    (row,) = events_of(env)
    assert (row.status, row.failure_category, row.processed_at) == ("needs_review", "unsupported_api_version", None)
    assert set(row.normalized_json) <= {"kind", "api_incompatible", "object_id"}             # no customer, status, amount, refund or dispute field was read
    assert row.normalized_json["api_incompatible"] is True
    assert count(env, BillingProviderLink) == 0 and plan_of(env, env.users[0])["plan_code"] == "basic"


def test_a_reference_whose_prefix_does_not_match_the_event_kind_is_not_kept(env):
    svc = service(env)
    svc.accept(event("customer.subscription.deleted", {"id": "cus_synth_9"}, api_version=OLD))
    assert events_of(env)[0].normalized_json["object_id"] is None


def test_a_malformed_supported_version_subscription_event_is_quarantined_for_review_not_ignored(env):
    svc = service(env)
    out, r = accept_and_process(env, svc, event("customer.subscription.updated", {"id": "!!bad", "status": "canceled"}))
    assert r.status == "needs_review" and r.category == "malformed_financial_event"
    assert plan_of(env, env.users[0])["plan_code"] == "basic"


def test_duplicate_incompatible_event_is_one_row_and_one_attention_item(env):
    svc = service(env)
    ev = sub_event(api_version=OLD, eid="evt_synth_dup_001")
    assert svc.accept(ev)["disposition"] == "held"
    assert svc.accept(ev)["disposition"] == "duplicate"
    assert len(events_of(env)) == 1 and ops(env).overview()["events"]["held_unsupported_api_version"] == 1


def test_environment_isolation_still_applies_to_incompatible_events(env):
    from src.billing import stripe_events as SE
    with pytest.raises(SE.WebhookError):
        service(env).accept(sub_event(api_version=OLD, livemode=True))
    assert events_of(env) == []


# ---------------------------------------------------------------- admin visibility ----------------------------------------------------------------------------

def test_held_events_are_visible_in_attention_counts_diagnostics_and_classification(env):
    svc = service(env)
    svc.accept(sub_event(api_version=OLD))
    ov = ops(env).overview()["events"]
    assert (ov["needs_review"], ov["awaiting_operator"], ov["held_unsupported_api_version"], ov["ignored"]) == (1, 1, 1, 0)
    rec = ops(env).reconciliation()
    assert any("unsupported_api_version" in str(v) for v in rec.values())
    listing = ops(env).events(status="needs_review", event_type=None, environment=None, page=1, page_size=10)
    (item,) = listing["items"]
    assert item["failure_category"] == "unsupported_api_version"
    detail = ops(env).event_detail(item["reference"])
    assert "Held" in detail["classification"] and "API version" in detail["classification"] and detail["recoverable"] is True
    assert "cus_" not in str(detail) and "normalized" not in str(detail)                       # no payload content in the diagnostic


# ---------------------------------------------------------------- fail closed ---------------------------------------------------------------------------------

def test_a_held_incompatible_cancellation_neither_revokes_nor_is_applied_until_recovered(env):
    svc = grant_first(env)
    before = link_of(env, env.users[0]).provider_state
    svc.accept(sub_event("customer.subscription.deleted", api_version=OLD))
    assert plan_of(env, env.users[0])["plan_code"] == "premium" and link_of(env, env.users[0]).provider_state == before == "active"
    (held,) = [e for e in events_of(env) if e.status == "needs_review"]
    assert svc.process(held.public_id).status == "skipped"                                   # a held event is never claimed by the worker or the sweep
    assert svc.sweep()["events"] == 0 and plan_of(env, env.users[0])["plan_code"] == "premium"


def test_authorized_recovery_reconciles_a_held_cancellation_from_authoritative_state_not_the_payload(env):
    svc = grant_first(env)
    # The incompatible payload CLAIMS the subscription is active for another customer; the provider's authoritative state says canceled: the provider wins.
    svc.accept(event("customer.subscription.deleted", {"id": "sub_synth_1", "status": "active", "customer": "cus_attacker"}, api_version=OLD))
    env.reader.set_subscription("sub_synth_1", customer_id="cus_synth_1", state="canceled")
    (held,) = [e for e in events_of(env) if e.status == "needs_review"]
    out = svc.recover("retry_event", held.public_id, actor_user_id=env.users[1], reason="b1r regression", idempotency_key="b1r-key-000001")
    assert out["status"] == "completed", out
    row = [e for e in events_of(env) if e.public_id == held.public_id][0]
    assert row.status == "processed" and row.reconciliation_json["incompatible_payload"] == "not_interpreted"
    assert plan_of(env, env.users[0])["plan_code"] == "basic" and link_of(env, env.users[0]).provider_state == "canceled"
    replay = svc.recover("retry_event", held.public_id, actor_user_id=env.users[1], reason="b1r regression", idempotency_key="b1r-key-000001")
    assert replay["replayed"] is True


def test_held_incompatible_refund_is_recovered_by_authoritative_read_and_takes_no_facts_from_the_payload(env):
    svc = grant_first(env)
    env.reader.payments["ch_synth_1"] = "sub_synth_1"                                         # the charge named by the refund event resolves to the subscription
    svc.accept(refund_event(api_version=OLD, amount=1999, refunded=1999))
    (held,) = [e for e in events_of(env) if e.status == "needs_review"]
    assert held.normalized_json == {"kind": "refund", "api_incompatible": True, "object_id": "ch_synth_1"}
    out = svc.recover("retry_event", held.public_id, actor_user_id=env.users[1], reason="b1r refund", idempotency_key="b1r-key-000002")
    assert out["status"] == "completed"
    link = link_of(env, env.users[0])
    assert link.refund_state == "none"                                                        # the payload's "fully refunded" claim was NOT applied
    row = [e for e in events_of(env) if e.public_id == held.public_id][0]
    assert row.reconciliation_json["facts"] == "refund_dispute_facts_not_applied_from_incompatible_payload"
    assert plan_of(env, env.users[0])["plan_code"] == "premium"                                # authoritative subscription still active: access follows the provider


def test_held_incompatible_invoice_and_dispute_resolve_through_authoritative_reads(env):
    svc = grant_first(env)
    env.reader.invoices["in_synth_1"] = InvoiceSnapshot("in_synth_1", "sub_synth_1", "paid", 1999, 0, "EUR", "pi_1", False)
    env.reader.disputes["dp_synth_1"] = DisputeSnapshot("dp_synth_1", "ch_synth_1", "pi_1", "needs_response", 1999, "EUR", False)
    env.reader.payments["ch_synth_1"] = "sub_synth_1"
    svc.accept(invoice_event(api_version=OLD))
    svc.accept(dispute_event(api_version=OLD))
    for i, held in enumerate([e for e in events_of(env) if e.status == "needs_review"]):
        out = svc.recover("retry_event", held.public_id, actor_user_id=env.users[1], reason="b1r reads", idempotency_key=f"b1r-key-10000{i}")
        assert out["status"] == "completed", out
    assert link_of(env, env.users[0]).dispute_state == "none"                                  # dispute status in the incompatible payload was not applied


def test_an_unresolvable_held_event_ends_in_review_never_silently_ignored(env):
    svc = grant_first(env)
    svc.accept(sub_event("customer.subscription.deleted", api_version=OLD, sub="sub_unknown_1"))
    (held,) = [e for e in events_of(env) if e.status == "needs_review"]
    env.reader.set_subscription("sub_unknown_1", customer_id="cus_other")                      # exists at the provider but has no trusted checkout record: unknown ownership
    out = svc.recover("retry_event", held.public_id, actor_user_id=env.users[1], reason="b1r unknown", idempotency_key="b1r-key-000003")
    assert out["status"] != "completed" or out["result"] != "reconciled"
    assert [e.status for e in events_of(env) if e.public_id == held.public_id][0] in ("quarantined", "needs_review")
    assert plan_of(env, env.users[0])["plan_code"] == "premium" and plan_of(env, env.users[1])["plan_code"] == "basic"


def test_stale_entitlement_protection_an_older_read_never_overwrites_newer_state(env):
    svc = grant_first(env)
    env.reader.set_subscription("sub_synth_1", customer_id="cus_synth_1", state="canceled")
    accept_and_process(env, svc, sub_event("customer.subscription.deleted"))
    assert plan_of(env, env.users[0])["plan_code"] == "basic"
    svc.accept(sub_event(api_version=OLD, eid="evt_synth_late_1"))
    env.reader.set_subscription("sub_synth_1", state="active")                                # a later (wrong) provider answer: canceled is terminal
    (held,) = [e for e in events_of(env) if e.status == "needs_review"]
    r = svc.process(held.public_id)
    assert plan_of(env, env.users[0])["plan_code"] == "basic" and r.status in ("skipped", "needs_review")


def test_null_provider_reader_leaves_a_held_event_untouched(env):
    svc = ProviderEventService(env.sf, environment="sandbox", reader=NullStateReader(), policy=SYNTHETIC_POLICY, clock=lambda: env.clock_now[0])
    svc.accept(sub_event(api_version=OLD))
    (held,) = events_of(env)
    assert ops(env, reader=False).readiness()["provider_state_reader"] == "not_wired_null_reader"
    assert svc.process(held.public_id).status == "skipped" and svc.sweep()["events"] == 0
    for fn in (NullStateReader().get_invoice, NullStateReader().get_dispute):
        with pytest.raises(ProviderStateUnavailable):
            fn("x_1")
    again = events_of(env)[0]
    assert (again.status, again.attempt_count) == ("needs_review", 0) and plan_of(env, env.users[0])["plan_code"] == "basic"


# ---------------------------------------------------------------- authorization over real HTTP (reuses the F1 / E persona fixtures) -------------------------

from tests.test_billing_ops_w12_4d_e import OPS, elevate, http  # noqa: E402,F401


def _held(http):
    from src.persistence import utcnow
    with http.repo.session_factory() as s:
        ev = BillingProviderEvent(public_id="h" * 32, provider=P.PROVIDER_STRIPE_MP, environment="sandbox", provider_event_id="evt_held_000001", event_type="customer.subscription.deleted",
                                  received_at=utcnow(), status="needs_review", failure_category="unsupported_api_version", attempt_count=0, api_version=OLD,
                                  normalized_json={"kind": "subscription", "api_incompatible": True, "object_id": "sub_h_1"})
        s.add(ev)
        s.commit()
        return ev.public_id


@pytest.mark.parametrize("role", ["operations_admin", "support_operator", "security_privacy_admin", "user"])
def test_unauthorized_roles_cannot_recover_a_held_event(http, role):
    ref = _held(http)
    _, ck = http.user(role)
    r = http.c.post(f"{OPS}/events/{ref}/retry", json={"reason": "not allowed"}, headers={"Idempotency-Key": f"b1r-deny-{role}-1"}, cookies=ck)
    assert r.status_code == 403


def test_billing_recovery_needs_step_up_and_with_the_null_reader_is_refused_not_applied(http):
    ref = _held(http)
    _, ck = http.user("billing_admin")
    no_step = http.c.post(f"{OPS}/events/{ref}/retry", json={"reason": "no step up"}, headers={"Idempotency-Key": "b1r-nostep-0001"}, cookies=ck)
    assert no_step.status_code in (401, 403)
    elevate(http, ck)
    r = http.c.post(f"{OPS}/events/{ref}/retry", json={"reason": "authorized but Null reader"}, headers={"Idempotency-Key": "b1r-auth-00001"}, cookies=ck)
    assert r.status_code == 200 and r.json()["status"] == "refused" and r.json()["result"] == "reader_unavailable"
    with http.repo.session_factory() as s:
        assert s.scalar(select(BillingProviderEvent.status).where(BillingProviderEvent.public_id == ref)) == "needs_review"


def test_held_events_show_in_the_admin_overview_over_http(http):
    _held(http)
    _, ck = http.user("billing_admin")
    ov = http.c.get(f"{OPS}/overview", cookies=ck)
    assert ov.status_code == 200 and ov.json()["events"]["held_unsupported_api_version"] == 1 and ov.json()["events"]["awaiting_operator"] == 1


def test_the_unapproved_runtime_policy_grants_nothing_even_after_recovery(env):
    reader_for(env)
    svc = service(env, policy=runtime_policy())
    svc.accept(checkout_event(api_version=OLD, ref="REFAAAA0"))
    (held,) = events_of(env)
    assert plan_of(env, env.users[0])["plan_code"] == "basic" and held.status == "needs_review"


def test_incompatible_events_cannot_reach_the_entitlement_bridge_directly():
    root = Path(__file__).resolve().parents[1]
    text = (root / "src/billing/reconcile.py").read_text()
    accept = text[text.index("    def accept"):text.index("    # ------------------------------------------------------------------ processing")]
    assert "evaluate_and_apply" not in accept and "_reconcile_subscription" not in accept and "Subscription" not in accept


def test_kill_switches_remain_off_and_no_real_reader_is_built():
    assert (P.LIVE_BILLING_ENABLED, P.EXTERNAL_CHECKOUT_AUTHORIZED, P.STRIPE_WEBHOOK_AUTHORIZED, P.RECONCILE_SCHEDULER_ENABLED, P.PROVIDER_READS_AUTHORIZED,
            P.PAID_ENTITLEMENT_POLICY_APPROVED) == (False,) * 6
