# ruff: noqa: F811
"""W12.4D-E: customer and Admin billing operations. FULLY OFFLINE: provider state comes from ``FakeStateReader``, events are synthetic and signed with a synthetic
secret, every non-loopback socket fails the test. ``SYNTHETIC_POLICY`` is not an owner decision; it only lets deterministic tests exercise the bridge."""

from __future__ import annotations

import json
import threading
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import func, select

from src.billing import policy as P
from src.billing.entitlement_bridge import UNAPPROVED_POLICY
from src.billing.provider_state import CheckoutAssociation, NullStateReader, ProviderStateUnavailable
from src.billing.reconcile import ProviderEventService
from src.persistence import (
    BillingCheckoutSession, BillingCommercialTerms, BillingProviderEvent, BillingProviderLink, BillingProviderPrice, BillingRecoveryAction, PlanVersion,
    Subscription, utcnow,
)
from tests.test_webhooks_w12_4d_d import (  # noqa: F401  (fixtures and factories shared with the W12.4D-D suite)
    SYNTHETIC_POLICY, _no_network, accept_and_process, checkout_event, count, env, link_of, plan_of, reader_for, service, sub_event,
)

ROOT = Path(__file__).resolve().parents[1]
OPS = "/api/v1/admin/billing/operations"
READS = ["/overview", "/readiness", "/subscriptions", "/checkouts", "/events", "/reconciliation", "/recovery-actions"]


# ---------------------------------------------------------------- HTTP fixture seeded over the app's own database ----------------------------------------

@pytest.fixture()
def http():
    from tests.test_admin_foundation_w10_1 import Env
    e = Env()
    yield e
    e.app.dependency_overrides.clear()
    e.close()


def seed_billing(sf, user_id: int, index: int = 0):
    """terms + mapping + an open checkout for ``user_id`` in an arbitrary database."""
    with sf() as s:
        pv = s.scalar(select(PlanVersion).where(PlanVersion.plan_code == "premium"))
        terms = s.scalar(select(BillingCommercialTerms).where(BillingCommercialTerms.plan_version_id == pv.id))
        if terms is None:
            terms = BillingCommercialTerms(public_id="t" * 32, plan_version_id=pv.id, version=1, amount_minor=1999, currency="EUR", billing_interval="month",
                                           visibility="public", state="active")
            s.add(terms)
            s.flush()
            s.add(BillingProviderPrice(public_id="p" * 32, commercial_terms_id=terms.id, provider=P.PROVIDER_STRIPE_MP, environment="sandbox", provider_product_id="prod_1",
                                       provider_price_id="price_test_1", amount_minor=1999, currency="EUR", billing_interval="month", status="active"))
            s.flush()
        price = s.scalar(select(BillingProviderPrice))
        s.add(BillingCheckoutSession(public_id=f"REFOPS{index:02d}", user_id=user_id, plan_version_id=pv.id, commercial_terms_id=terms.id, price_mapping_id=price.id,
                                     provider=P.PROVIDER_STRIPE_MP, environment="sandbox", provider_session_id=f"cs_test_o{index}", status="open", idempotency_key=f"idem-ops-{index:04d}",
                                     checkout_url="https://checkout.stripe.com/x", provider_attempts=1, created_at=utcnow(), expires_at=utcnow() + timedelta(minutes=30)))
        s.commit()


def ops_service(sf, reader=None, policy=UNAPPROVED_POLICY):
    return ProviderEventService(sf, environment="sandbox", reader=reader or NullStateReader(), policy=policy)


def add_event(sf, status="quarantined", category="unknown_ownership", event_id="evt_ops_000001", env_name="sandbox", sub="sub_ops_1", **kw):
    with sf() as s:
        ev = BillingProviderEvent(public_id=event_id.replace("evt_", "").ljust(32, "0")[:32], provider=P.PROVIDER_STRIPE_MP, environment=env_name, provider_event_id=event_id,
                                  event_type="customer.subscription.updated", received_at=utcnow(), status=status, failure_category=category, attempt_count=kw.pop("attempts", 1),
                                  normalized_json={"kind": "subscription", "subscription_id": sub}, **kw)
        s.add(ev)
        s.commit()
        return ev.public_id


def admin(http, role):
    return http.user(role)


def elevate(http, ck):
    """Fresh password step-up for THIS session through the billing-scoped route (same StepUpService; billing admins do not hold platform.users.role.assign)."""
    from tests.test_admin_foundation_w10_1 import PW
    r = http.c.post(f"{OPS}/step-up", json={"password": PW}, cookies=ck)
    assert r.status_code == 200 and r.json()["elevated"] is True, r.text
    return ck


# ================================================================ 1. AUTHORIZATION (real HTTP, persona matrix) ==================================

@pytest.mark.parametrize("role,allowed", [("platform_admin", True), ("billing_admin", True), ("operations_admin", False), ("support_operator", False),
                                          ("knowledge_admin", False), ("security_privacy_admin", False), ("user", False)])
def test_every_read_route_needs_billing_read(http, role, allowed):
    _, ck = admin(http, role)
    for path in READS:
        r = http.c.get(OPS + path, cookies=ck)
        assert (r.status_code == 200) is allowed, (role, path, r.status_code)
        if not allowed:
            assert r.status_code == 403


def test_unauthenticated_and_invalid_sessions_never_reach_billing_diagnostics(http):
    for path in READS:
        assert http.c.get(OPS + path, cookies={"ask4mo_session": "bogus"}).status_code == 401


@pytest.mark.parametrize("role,allowed", [("platform_admin", True), ("billing_admin", True), ("operations_admin", False), ("support_operator", False), ("user", False)])
def test_recovery_actions_need_billing_recover_and_a_fresh_step_up(http, role, allowed):
    _, ck = admin(http, role)
    ref = add_event(http.repo.session_factory)
    if allowed:
        elevate(http, ck)
    r = http.c.post(f"{OPS}/events/{ref}/retry", json={"reason": "operator retry"}, headers={"Idempotency-Key": f"key-{role}-0001"}, cookies=ck)
    assert (r.status_code == 200) is allowed, (role, r.status_code, r.text)
    if allowed:
        assert r.json()["status"] == "refused" and r.json()["result"] == "reader_unavailable"      # the runtime Null reader: refused, never "completed"


def test_a_recovery_attempt_is_audited_in_the_same_transaction_with_actor_reason_and_outcome(http):
    from src.auth_repository import AuditRepository
    uid, ck = admin(http, "billing_admin")
    elevate(http, ck)
    ref = add_event(http.repo.session_factory)
    r = http.c.post(f"{OPS}/events/{ref}/retry", json={"reason": "audit me please"}, headers={"Idempotency-Key": "audit-key-0001"}, cookies=ck)
    assert r.status_code == 200 and r.json()["status"] == "refused"
    rows = AuditRepository(http.repo.session_factory).recent(limit=50, event_type="admin.billing_recovery")
    assert len(rows) == 1
    row = rows[0]
    row = row if isinstance(row, dict) else row.__dict__
    ctx = row.get("context") or {}
    assert row.get("actor_user_id") == uid and row.get("result") == "failure" and ctx.get("action") == "retry_event" and ctx.get("category") == "reader_unavailable"
    assert ctx.get("reason") == "audit me please"
    replay = http.c.post(f"{OPS}/events/{ref}/retry", json={"reason": "audit me please"}, headers={"Idempotency-Key": "audit-key-0001"}, cookies=ck)
    assert replay.json()["replayed"] is True
    assert len(AuditRepository(http.repo.session_factory).recent(limit=50, event_type="admin.billing_recovery")) == 1      # a replay runs nothing and writes no duplicate audit action


def test_billing_admin_cannot_rotate_secrets_or_recover_and_perm_registry_is_unchanged():
    from src.application import admin_permissions as perm
    ba, ops_ = perm.permissions_for_role("billing_admin"), perm.permissions_for_role("operations_admin")
    assert "platform.integrations.secret.rotate" not in ba and "platform.jobs.manage" not in ba and "platform.integrations.secret.rotate" not in ops_
    assert "platform.billing.read" not in ops_ and "platform.billing.recover" in ba and "platform.billing.recover" not in ops_ and len(perm.PERMISSIONS) == 44
    assert perm.permissions_for_role("support_operator").isdisjoint({"platform.billing.read", "platform.jobs.manage"})


def test_recovery_request_validation(http):
    _, ck = admin(http, "platform_admin")
    elevate(http, ck)
    ref = add_event(http.repo.session_factory)
    url = f"{OPS}/events/{ref}/retry"
    assert http.c.post(url, json={"reason": "operator retry"}, cookies=ck).status_code == 422                                   # idempotency key required
    assert http.c.post(url, json={"reason": "operator retry"}, headers={"Idempotency-Key": "short"}, cookies=ck).status_code == 422
    assert http.c.post(url, json={"reason": "x"}, headers={"Idempotency-Key": "valid-key-0001"}, cookies=ck).status_code == 422
    assert http.c.post(url, json={"reason": "operator retry", "status": "processed"}, headers={"Idempotency-Key": "valid-key-0002"}, cookies=ck).status_code == 422
    assert http.c.post(url, json={"reason": "operator retry", "provider_subscription_id": "sub_x"}, headers={"Idempotency-Key": "valid-key-0003"}, cookies=ck).status_code == 422


def test_list_filters_are_validated_not_passed_to_sql(http):
    _, ck = admin(http, "billing_admin")
    for q in ("/subscriptions?state=drop%20table", "/checkouts?status=paid", "/events?status=%27or%271", "/events?event_type=charge.captured", "/events?environment=prod"):
        assert http.c.get(OPS + q, cookies=ck).status_code == 422, q
    assert http.c.get(OPS + "/events?page_size=1000", cookies=ck).status_code == 422
    assert http.c.get(OPS + "/events?page=0", cookies=ck).status_code == 422


# ================================================================ 2. TRUTHFUL OVERVIEW AND READINESS ==============================================

def test_empty_billing_state_is_all_zero_and_claims_nothing(http):
    _, ck = admin(http, "billing_admin")
    o = http.c.get(OPS + "/overview", cookies=ck).json()
    assert o["subscriptions"]["total"] == 0 and o["events"]["pending"] == 0 and o["checkouts"]["pending"] == 0
    assert o["revenue_reported"] is False and "never been activated" in o["data_origin"]
    r = o["readiness"]
    assert (r["live_billing"], r["checkout"], r["webhook"], r["provider_state_reader"], r["reconciliation_scheduler"], r["entitlement_policy"]) == (
        "disabled", "not_authorized", "not_authorized", "not_wired_null_reader", "disabled", "not_approved")
    assert r["eligibility"] == "not_confirmed" and r["sandbox_access"] == "unverified" and r["operational"] is False
    assert set(r["kill_switches"].values()) == {False}
    assert "Premium monthly price" in o["open_commercial_decisions"] and "Legal seller entity" in o["open_commercial_decisions"]
    assert o["reconciliation"]["provider_state_reader"] == "not_wired_null_reader" and o["reconciliation"]["last_successful"] is None


def test_overview_reflects_verified_local_state_and_never_revenue(http):
    sf = http.repo.session_factory
    uid, ck = admin(http, "billing_admin")
    seed_billing(sf, uid)
    add_event(sf, "quarantined", "unknown_ownership", "evt_ops_q00001")
    add_event(sf, "needs_review", "retries_exhausted", "evt_ops_n00001")
    add_event(sf, "received", None, "evt_ops_r00001")
    o = http.c.get(OPS + "/overview", cookies=ck).json()
    assert o["events"]["quarantined"] == 1 and o["events"]["needs_review"] == 1 and o["events"]["pending"] == 1 and o["events"]["awaiting_operator"] == 2
    assert o["checkouts"]["pending"] == 1 and "revenue" not in json.dumps(o).replace("revenue_reported", "").replace("No revenue is reported", "").lower()


def test_readiness_reports_credential_state_without_any_secret(http):
    _, ck = admin(http, "billing_admin")
    blob = http.c.get(OPS + "/readiness", cookies=ck).text
    for forbidden in ("sk_test", "sk_live", "whsec_", "secret_value"):
        assert forbidden not in blob


# ================================================================ 3. EVENT MONITOR, DETAIL, PRIVACY ==============================================

def test_event_list_filtering_and_masked_identifiers(http):
    sf = http.repo.session_factory
    _, ck = admin(http, "billing_admin")
    add_event(sf, "quarantined", "unknown_ownership", "evt_ops_q00001")
    add_event(sf, "failed", "provider_timeout", "evt_ops_f00001")
    add_event(sf, "processed", None, "evt_ops_p00001")
    allr = http.c.get(OPS + "/events", cookies=ck).json()
    assert allr["total"] == 3
    q = http.c.get(OPS + "/events?status=quarantined", cookies=ck).json()
    assert [i["status"] for i in q["items"]] == ["quarantined"]
    assert http.c.get(OPS + "/events?environment=live", cookies=ck).json()["total"] == 0
    assert http.c.get(OPS + "/events?event_type=customer.subscription.updated", cookies=ck).json()["total"] == 3
    body = json.dumps(allr)
    for full in ("evt_ops_q00001", "evt_ops_f00001", "evt_ops_p00001"):
        assert full not in body                                                                  # provider ids are masked
    assert all(i["provider_event"].startswith("…") for i in allr["items"])


def test_event_detail_is_safe_audited_and_has_no_payload(http):
    sf = http.repo.session_factory
    uid, ck = admin(http, "billing_admin")
    ref = add_event(sf, "quarantined", "unknown_ownership", "evt_ops_q00002", reconciliation_json={"disposition": "x", "observed_state": "active"})
    d = http.c.get(f"{OPS}/events/{ref}", cookies=ck).json()
    assert d["signature_verified"] is True and d["recoverable"] is True and "Quarantined" in d["classification"]
    assert d["lifecycle"][0]["step"] == "received_and_signature_verified"
    text = json.dumps(d)
    for banned in ("normalized_json", "payload", "signature_header", "email", "last4", "evt_ops_q00002"):
        assert banned not in text
    assert http.c.get(f"{OPS}/events/{'0' * 32}", cookies=ck).status_code == 404
    from src.auth_repository import AuditRepository
    seen = AuditRepository(http.repo.session_factory).recent(limit=50, event_type="admin.billing_event_viewed")
    assert len(seen) == 1


def test_subscription_and_checkout_lists_expose_no_personal_or_provider_data(http, env):
    uid, ck = admin(http, "billing_admin")
    seed_billing(http.repo.session_factory, uid)
    r = http.c.get(OPS + "/checkouts", cookies=ck)
    text = r.text
    assert r.json()["total"] == 1 and "checkout.stripe.com" not in text and "cs_test_" not in text and "@" not in text
    assert r.json()["items"][0]["subscription_linked"] is False


# ================================================================ 4. RECOVERY (service level, fake reader) ===========================================

def quarantined_event(env, svc):
    reader_for(env)
    out = svc.accept(checkout_event(ref="REFAAAA0"))
    env.reader.checkouts.clear()                                            # the provider cannot associate the subscription yet
    assert svc.process(out["public_id"]).status == "quarantined"
    reader_for(env)                                                          # ownership evidence becomes available later
    return out["public_id"]


def test_recovery_fails_closed_with_the_null_reader_and_changes_nothing(env):
    svc = ops_service(env.sf)
    ref = quarantined_event(env, service(env))
    r = svc.recover("retry_event", ref, actor_user_id=env.users[0], reason="operator retry", idempotency_key="null-reader-0001")
    assert (r["status"], r["result"]) == ("refused", "reader_unavailable")
    with env.sf() as s:
        ev = s.scalar(select(BillingProviderEvent))
        act = s.scalar(select(BillingRecoveryAction))
    assert ev.status == "quarantined" and ev.operator_retries == 0 and act.status == "refused" and act.actor_user_id == env.users[0] and act.reason == "operator retry"
    assert count(env, BillingProviderLink) == 0
    for action in ("requeue_lease", "reconcile_link"):
        assert svc.recover(action, ref, actor_user_id=env.users[0], reason="operator retry", idempotency_key=f"null-{action}-0001")["result"] == "reader_unavailable"


def test_retry_redrives_the_verified_pipeline_and_replays_are_idempotent(env):
    svc = service(env)
    ref = quarantined_event(env, svc)
    a = svc.recover("retry_event", ref, actor_user_id=env.users[1], reason="ownership evidence arrived", idempotency_key="retry-key-0001")
    assert (a["status"], a["replayed"]) == ("completed", False) and link_of(env) is not None and plan_of(env, env.users[0])["plan_code"] == "premium"
    b = svc.recover("retry_event", ref, actor_user_id=env.users[1], reason="ownership evidence arrived", idempotency_key="retry-key-0001")
    assert (b["replayed"], b["public_id"]) == (True, a["public_id"])
    assert count(env, BillingRecoveryAction) == 1 and count(env, BillingProviderLink) == 1
    again = svc.recover("retry_event", ref, actor_user_id=env.users[1], reason="second look", idempotency_key="retry-key-0002")
    assert (again["status"], again["result"]) == ("refused", "event_not_retryable")                  # a processed event is immutable evidence


def test_concurrent_retries_process_once_and_preserve_attempt_history(env):
    svc = service(env)
    ref = quarantined_event(env, svc)
    results = []
    ts = [threading.Thread(target=lambda i=i: results.append(svc.recover("retry_event", ref, actor_user_id=env.users[0], reason="concurrent retry",
                                                                           idempotency_key=f"concurrent-key-{i:04d}"))) for i in range(5)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    with env.sf() as s:
        ev = s.scalar(select(BillingProviderEvent))
        decisions = s.scalar(select(func.count()).select_from(__import__("src.persistence", fromlist=["x"]).BillingEntitlementDecision))
    assert ev.status == "processed" and count(env, BillingProviderLink) == 1 and decisions == 1
    assert ev.attempt_count >= 2 and ev.operator_retries >= 1                                        # the true history (one failed attempt before) is kept
    assert sum(1 for r in results if r["status"] == "completed") >= 1


def test_operator_retries_are_bounded(env):
    svc = service(env)
    reader_for(env)
    env.reader.fail = ProviderStateUnavailable("provider_unavailable")
    out = svc.accept(checkout_event(ref="REFAAAA0"))
    last = None
    for i in range(6):
        last = svc.recover("retry_event", out["public_id"], actor_user_id=env.users[0], reason="try again", idempotency_key=f"bounded-key-{i:04d}")
    assert last["result"] in ("operator_retry_limit_reached", "event_not_retryable")
    with env.sf() as s:
        assert s.scalar(select(BillingProviderEvent)).operator_retries <= ProviderEventService.MAX_OPERATOR_RETRIES


def test_requeue_only_releases_an_abandoned_lease(env):
    svc = service(env)
    reader_for(env)
    out = svc.accept(checkout_event(ref="REFAAAA0"))
    with env.sf() as s:
        ev = s.scalar(select(BillingProviderEvent))
        ev.status, ev.lease_until, ev.attempt_count = "processing", env.clock_now[0] + timedelta(minutes=5), 1
        s.commit()
    held = svc.recover("requeue_lease", out["public_id"], actor_user_id=env.users[0], reason="stuck worker", idempotency_key="requeue-key-0001")
    assert held["result"] == "lease_not_abandoned"                                                       # a live lease is never stolen
    env.clock_now[0] += timedelta(minutes=30)
    freed = svc.recover("requeue_lease", out["public_id"], actor_user_id=env.users[0], reason="stuck worker", idempotency_key="requeue-key-0002")
    assert freed["status"] == "completed", freed
    assert link_of(env) is not None


def test_recovery_cannot_forge_edit_or_cross_environment(env):
    svc = service(env)
    assert svc.recover("retry_event", "f" * 32, actor_user_id=env.users[0], reason="unknown id", idempotency_key="forge-key-0001")["result"] == "not_found"
    live = add_event(env.sf, "quarantined", "unknown_ownership", "evt_ops_live01", env_name="live")
    assert svc.recover("retry_event", live, actor_user_id=env.users[0], reason="wrong environment", idempotency_key="forge-key-0002")["result"] == "not_found"
    with pytest.raises(ValueError):
        svc.recover("edit_payment_status", live, actor_user_id=env.users[0], reason="not an action", idempotency_key="forge-key-0003")
    assert count(env, BillingProviderLink) == 0 and plan_of(env, env.users[0])["plan_code"] == "basic"
    with env.sf() as s:
        assert s.scalar(select(BillingProviderEvent).where(BillingProviderEvent.environment == "live")).status == "quarantined"     # nothing touched


def test_reconcile_link_uses_our_record_id_not_a_caller_supplied_provider_id(env):
    svc = service(env)
    reader_for(env)
    accept_and_process(env, svc, checkout_event(ref="REFAAAA0"))
    link = link_of(env)
    env.clock_now[0] += timedelta(seconds=5)
    env.reader.set_subscription("sub_synth_1", state="past_due", latest_invoice_state="failed")
    r = svc.recover("reconcile_link", link.public_id, actor_user_id=env.users[0], reason="manual refresh", idempotency_key="reconcile-key-0001")
    assert r["status"] == "completed" and link_of(env).provider_state == "past_due"
    assert svc.recover("reconcile_link", "sub_synth_1", actor_user_id=env.users[0], reason="provider id as proof", idempotency_key="reconcile-key-0002")["result"] == "not_found"


def test_provider_outage_during_recovery_is_reported_as_failure_not_success(env):
    svc = service(env)
    reader_for(env)
    accept_and_process(env, svc, checkout_event(ref="REFAAAA0"))
    link = link_of(env)
    env.reader.fail = ProviderStateUnavailable("provider_unavailable")
    r = svc.recover("reconcile_link", link.public_id, actor_user_id=env.users[0], reason="manual refresh", idempotency_key="outage-key-0001")
    assert (r["status"], r["result"]) == ("failed", "provider_unavailable")


def test_stale_data_from_a_retry_cannot_imply_success(env):
    svc = service(env)
    reader_for(env)
    accept_and_process(env, svc, checkout_event(ref="REFAAAA0"))
    env.clock_now[0] += timedelta(minutes=10)
    env.reader.set_subscription("sub_synth_1", state="past_due", latest_invoice_state="failed")
    svc.recover("reconcile_link", link_of(env).public_id, actor_user_id=env.users[0], reason="refresh now", idempotency_key="stale-key-0001")
    env.clock_now[0] -= timedelta(minutes=30)                                                              # a lagging read that observed the provider EARLIER
    env.reader.set_subscription("sub_synth_1", state="active", latest_invoice_state="paid")
    svc.recover("reconcile_link", link_of(env).public_id, actor_user_id=env.users[0], reason="refresh again", idempotency_key="stale-key-0002")
    assert link_of(env).provider_state == "past_due"


def test_retry_cannot_grant_premium_directly_under_the_unapproved_runtime_policy(env):
    svc = ops_service(env.sf, reader=env.reader, policy=UNAPPROVED_POLICY)
    reader_for(env)
    out = svc.accept(checkout_event(ref="REFAAAA0"))
    with env.sf() as s:
        s.scalar(select(BillingProviderEvent)).status = "needs_review"
        s.commit()
    r = svc.recover("retry_event", out["public_id"], actor_user_id=env.users[0], reason="retry under runtime policy", idempotency_key="policy-key-0001")
    assert r["status"] == "completed"
    with env.sf() as s:
        assert s.scalar(select(func.count()).select_from(Subscription).where(Subscription.source == "provider")) == 0
    assert plan_of(env, env.users[0])["plan_code"] == "basic" and link_of(env).entitlement_decision == "policy_unapproved"


def test_recovery_creates_no_financial_approval_or_refund(env):
    from src.persistence import BillingApprovalRequest, BillingRefund
    svc = service(env)
    ref = quarantined_event(env, svc)
    svc.recover("retry_event", ref, actor_user_id=env.users[0], reason="operator retry", idempotency_key="fin-key-0001")
    assert count(env, BillingApprovalRequest) == 0 and count(env, BillingRefund) == 0


def test_the_recovery_surface_has_no_edit_delete_or_grant_route(http):
    paths = {p: m for p, m in http.app.openapi()["paths"].items() if p.startswith("/api/v1/admin/billing/operations")}
    posts = sorted(p for p, m in paths.items() if "post" in m)
    assert posts == [f"{OPS}/events/{{reference}}/requeue", f"{OPS}/events/{{reference}}/retry", f"{OPS}/step-up", f"{OPS}/subscriptions/{{reference}}/reconcile"]
    assert not [p for p, m in paths.items() if set(m) & {"put", "patch", "delete"}]


def test_recovery_source_uses_the_existing_pipeline_only():
    import ast
    src = (ROOT / "src/billing/reconcile.py").read_text()
    tree = ast.parse(src)
    fn = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "_do_recover")
    body = ast.unparse(fn)
    assert "evaluate_and_apply" not in body and "Subscription(" not in body and "delete(" not in body.lower() and "self.process(" in body


# ================================================================ 5. SCHEDULER ================================================================

def _jobs(env):
    from src.jobs.service import JobService
    return JobService(env.sf)


def test_scheduler_is_disabled_by_default_and_refuses_without_a_reader(env):
    from src.billing.scheduler import schedule_tick
    assert P.RECONCILE_SCHEDULER_ENABLED is False
    assert schedule_tick(env.sf, _jobs(env), reader_available=True)["reason"] == "scheduler_disabled"                    # the production default
    assert schedule_tick(env.sf, _jobs(env), reader_available=False, enabled=True)["reason"] == "provider_state_reader_unavailable"
    from src.persistence import Job
    assert count(env, Job) == 0


def test_scheduler_is_idempotent_per_bucket_across_concurrent_instances(env):
    from src.billing.scheduler import schedule_tick
    from src.persistence import Job
    now = utcnow()
    out = []
    ts = [threading.Thread(target=lambda: out.append(schedule_tick(env.sf, _jobs(env), reader_available=True, enabled=True, now=now))) for _ in range(6)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert count(env, Job) == 1 and sum(1 for o in out if o["scheduled"]) == 1
    later = schedule_tick(env.sf, _jobs(env), reader_available=True, enabled=True, now=now + timedelta(seconds=P.RECONCILE_SCHEDULE_BUCKET_SECONDS + 1))
    assert later["scheduled"] is True and count(env, Job) == 2


def test_a_finished_job_does_not_cause_a_second_job_in_the_same_bucket(env):
    from src.billing.runtime import BillingRuntime
    from src.billing.scheduler import schedule_tick
    from src.jobs.worker import Worker
    from src.persistence import Job
    svc = service(env)
    jobs = _jobs(env)
    now = utcnow()
    assert schedule_tick(env.sf, jobs, reader_available=True, enabled=True, now=now)["scheduled"]
    assert Worker(jobs, services=SimpleNamespace(billing=BillingRuntime(session_factory=env.sf, provider_events=svc, jobs=jobs))).run_once() == "succeeded"
    assert schedule_tick(env.sf, jobs, reader_available=True, enabled=True, now=now)["reason"] == "already_scheduled_for_this_bucket" and count(env, Job) == 1


def test_scheduled_sweep_is_deterministic_bounded_and_tolerates_a_provider_outage(env):
    from src.billing.runtime import BillingRuntime
    from src.billing.scheduler import schedule_tick
    from src.jobs.worker import Worker
    reader_for(env)
    with env.sf() as s:
        cs = s.scalar(select(BillingCheckoutSession).where(BillingCheckoutSession.user_id == env.users[0]))
        cs.browser_returned_at = env.clock_now[0]
        s.commit()
    svc, jobs = service(env), _jobs(env)
    env.reader.fail = ProviderStateUnavailable("provider_unavailable")
    schedule_tick(env.sf, jobs, reader_available=True, enabled=True, now=utcnow())
    w = Worker(jobs, services=SimpleNamespace(billing=BillingRuntime(session_factory=env.sf, provider_events=svc, jobs=jobs)))
    assert w.run_once() == "succeeded" and link_of(env) is None                                           # outage: nothing guessed, the job did not crash
    env.reader.fail = None
    schedule_tick(env.sf, jobs, reader_available=True, enabled=True, now=utcnow() + timedelta(hours=1))
    assert w.run_once() == "succeeded" and link_of(env) is not None


def test_the_runtime_graph_cannot_schedule_and_there_is_no_resident_loop():
    from src.billing.wiring import build_provider_events
    from src.persistence import make_engine, make_session_factory
    svc = build_provider_events(make_session_factory(make_engine("sqlite://")))
    assert svc.reader_available() is False
    src = (ROOT / "src/billing/scheduler.py").read_text()
    assert "while True" not in src and "sleep(" not in src and "stripe" not in src.lower().replace("no stripe call", "")


# ================================================================ 6. CANDIDATE BILLING SUMMARY =====================================================

def _co(env):
    from src.billing.checkout import CheckoutService
    return CheckoutService(env.sf, app_base_url="https://app.example.test", clock=lambda: env.clock_now[0])


def _summary(env, i=0, plan="basic"):
    return _co(env).summary(env.users[i], plan)


def test_summary_free_and_checkout_states(env):
    with env.sf() as s:
        s.execute(BillingCheckoutSession.__table__.delete())
        s.commit()
    assert _summary(env)["state"] == "free"
    seed_billing(env.sf, env.users[0], 5)
    assert _summary(env)["state"] == "checkout_pending"
    with env.sf() as s:
        s.scalar(select(BillingCheckoutSession).where(BillingCheckoutSession.public_id == "REFOPS05")).browser_returned_at = env.clock_now[0]
        s.commit()
    sm = _summary(env)
    assert sm["state"] == "confirmation_pending" and sm["subscription"] == "confirmation_pending" and sm["entitlement"]["changed_by_billing"] is False


@pytest.mark.parametrize("state,invoice,cancel,refund_dispute,expected,sub_word", [
    ("active", "paid", False, None, "active", "active"), ("active", "paid", True, None, "cancel_at_period_end", "cancel_scheduled"),
    ("trialing", "none", False, None, "trialing", "confirmation_pending"), ("past_due", "failed", False, None, "past_due", "past_due"),
    ("unpaid", "failed", False, None, "past_due", "past_due"), ("canceled", "paid", False, None, "canceled", "canceled"),
    ("incomplete_expired", "open", False, None, "expired", "expired"), ("active", "open", False, None, "confirmation_pending", "confirmation_pending"),
    ("active", "paid", False, ("refund", "full"), "refunded", "active"), ("active", "paid", False, ("dispute", "open"), "disputed", "active"),
])
def test_summary_lifecycle_labels_come_only_from_verified_link_state(env, state, invoice, cancel, refund_dispute, expected, sub_word):
    reader_for(env, state=state, latest_invoice_state=invoice, cancel_at_period_end=cancel, current_period_end=env.clock_now[0] + timedelta(days=20))
    svc = service(env)
    accept_and_process(env, svc, checkout_event(ref="REFAAAA0"))
    if refund_dispute:
        with env.sf() as s:
            link = s.scalar(select(BillingProviderLink))
            setattr(link, f"{refund_dispute[0]}_state", refund_dispute[1])
            s.commit()
    sm = _summary(env)
    assert sm["state"] == expected and sm["subscription"] == sub_word
    assert sm["interval"] == "month" and sm["verified_at"] is not None
    assert (sm["cancellation_effective_at"] is not None) is (expected == "cancel_at_period_end")
    assert set(sm) >= {"state", "subscription", "payment", "entitlement"}                              # four separate dimensions, never one boolean


def test_summary_management_receipts_and_timeline_are_truthful(env):
    reader_for(env)
    accept_and_process(env, service(env), checkout_event(ref="REFAAAA0"))
    sm = _summary(env, plan="premium")
    assert sm["management"] == {"where": "link", "url": None, "url_verified": False}
    assert sm["receipts"] == {"shown_here": False, "where": "link_email"}
    assert [e["kind"] for e in sm["timeline"]] and {e["kind"] for e in sm["timeline"]} <= {"checkout_started", "subscription_linked", "access_granted", "access_ended", "access_reviewed"}
    assert not any(k in sm for k in ("invoices", "invoice_history", "card", "payment_method", "provider_subscription_id", "customer_id"))


def test_summary_is_owner_scoped_and_new_subscription_after_cancellation_is_shown(env):
    reader_for(env)
    svc = service(env)
    accept_and_process(env, svc, checkout_event(ref="REFAAAA0"))
    with env.sf() as s:                                                    # candidate 1 has never started a checkout
        s.execute(BillingCheckoutSession.__table__.delete().where(BillingCheckoutSession.user_id == env.users[1]))
        s.commit()
    other = _summary(env, 1)
    assert other["state"] == "free" and other["timeline"] == [] and other["interval"] is None
    env.clock_now[0] += timedelta(seconds=5)
    env.reader.set_subscription("sub_synth_1", state="canceled")
    accept_and_process(env, svc, sub_event("customer.subscription.deleted"))
    assert _summary(env)["state"] == "canceled"
    from src.billing.checkout import CheckoutService
    from tests.test_webhooks_w12_4d_d import _CheckoutProvider
    mode = SimpleNamespace(provider=P.PROVIDER_STRIPE_MP, environment="sandbox", enabled=False, live=False)
    co = CheckoutService(env.sf, provider=_CheckoutProvider(), mode=mode, app_base_url="https://app.example.test", api_env="production",
                         readiness=lambda: "sandbox_access_unverified", clock=lambda: env.clock_now[0])
    new = co.create(env.users[0], "premium", "summary-new-key-01")
    env.clock_now[0] += timedelta(seconds=5)
    env.reader.set_subscription("sub_synth_2", customer_id="cus_synth_1")
    env.reader.checkouts["cs_test_new1"] = CheckoutAssociation("cs_test_new1", new["checkout_id"], "sub_synth_2", False)
    accept_and_process(env, svc, checkout_event(session="cs_test_new1", ref=new["checkout_id"], sub="sub_synth_2"))
    assert _summary(env)["state"] == "active"


def test_summary_endpoint_requires_a_session_and_returns_only_own_data(http):
    assert http.c.get("/api/v1/billing/summary", cookies={"ask4mo_session": "bogus"}).status_code == 401
    uid, ck = http.user()
    r = http.c.get("/api/v1/billing/summary", cookies=ck)
    assert r.status_code == 200 and r.json()["state"] == "free" and r.json()["management"]["url"] is None
    assert r.json()["entitlement"]["changed_by_billing"] is False and r.json()["timeline"] == []
    assert "/api/v1/billing/summary" in http.app.openapi()["paths"]


def test_candidates_cannot_reach_any_admin_billing_diagnostic(http):
    _, ck = http.user()
    for path in READS:
        assert http.c.get(OPS + path, cookies=ck).status_code == 403


# ================================================================ 7. KILL SWITCHES, POLICY, LEAKAGE =============================================

def test_kill_switches_and_entitlement_boundaries_are_unchanged():
    assert (P.LIVE_BILLING_ENABLED, P.EXTERNAL_CHECKOUT_AUTHORIZED, P.STRIPE_WEBHOOK_AUTHORIZED, P.RECONCILE_SCHEDULER_ENABLED, P.PAID_ENTITLEMENT_POLICY_APPROVED) == (False,) * 5
    callers = sorted(p.relative_to(ROOT).as_posix() for p in (ROOT / "src").rglob("*.py") if "evaluate_and_apply(" in p.read_text(encoding="utf-8"))
    assert callers == ["src/billing/entitlement_bridge.py", "src/billing/reconcile.py"]
    writers = sorted(p.relative_to(ROOT).as_posix() for p in (ROOT / "src").rglob("*.py") if 'source="provider"' in p.read_text(encoding="utf-8"))
    assert writers == ["src/billing/entitlement_bridge.py"]


def test_synthetic_policy_still_refused_in_hosted_environments(env, monkeypatch):
    monkeypatch.setenv("API_ENV", "production")
    with pytest.raises(ValueError):
        service(env, policy=SYNTHETIC_POLICY)


def test_admin_surface_never_leaks_secrets_private_content_or_raw_payloads(http):
    sf = http.repo.session_factory
    uid, ck = admin(http, "platform_admin")
    seed_billing(sf, uid)
    ref = add_event(sf, "needs_review", "retries_exhausted", "evt_ops_leak01")
    parts = [http.c.get(OPS + p, cookies=ck).text for p in READS] + [http.c.get(f"{OPS}/events/{ref}", cookies=ck).text]
    blob = "\n".join(parts).lower()
    for banned in ("sk_test", "sk_live", "whsec", "stripe-signature", "password", "api_key", "card_number", "resume", "answer_text", "@example", "checkout.stripe.com"):
        assert banned not in blob, banned


def test_billing_operations_source_has_no_stripe_sdk_and_no_network():
    for rel in ("src/billing/operations.py", "src/api/routes/admin_billing_ops.py", "src/billing/scheduler.py"):
        text = (ROOT / rel).read_text()
        for banned in ("import stripe", "requests.", "httpx", "urllib.request", "socket"):
            assert banned not in text, (rel, banned)


# ================================================================ 8. MIGRATION 0030 ==============================================================

def _alembic(tmp_path, monkeypatch):
    from alembic.config import Config
    url = f"sqlite:///{tmp_path / 'o.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    cfg = Config("alembic.ini")
    cfg.set_main_option("script_location", "migrations")
    cfg.set_main_option("sqlalchemy.url", url)
    return cfg, url


def test_migration_0030_upgrade_from_0029_downgrade_safety_and_single_head(tmp_path, monkeypatch):
    from alembic import command
    from alembic.script import ScriptDirectory
    from sqlalchemy import create_engine, inspect, text
    cfg, url = _alembic(tmp_path, monkeypatch)
    command.upgrade(cfg, "0029_provider_webhooks")
    with create_engine(url).begin() as c:
        c.execute(text("INSERT INTO billing_provider_events (public_id, provider, environment, provider_event_id, event_type, received_at, status, attempt_count, normalized_json) "
                       "VALUES ('" + "a" * 32 + "', 'stripe_managed_payments', 'sandbox', 'evt_keep_1', 'invoice.paid', '2026-01-01', 'received', 2, '{}')"))
    command.upgrade(cfg, "head")
    insp = inspect(create_engine(url))
    assert "billing_recovery_actions" in insp.get_table_names()
    with create_engine(url).connect() as c:
        row = c.execute(text("SELECT attempt_count, attempt_limit, operator_retries FROM billing_provider_events")).one()
    assert tuple(row) == (2, 6, 0)                                                                        # history preserved, defaults applied
    assert ScriptDirectory.from_config(cfg).get_heads() == ["0039_speech_governance"]
    command.downgrade(cfg, "0029_provider_webhooks")                                                      # empty recovery table: allowed
    assert "billing_recovery_actions" not in inspect(create_engine(url)).get_table_names()
    command.upgrade(cfg, "head")
    with create_engine(url).begin() as c:
        c.execute(text("INSERT INTO billing_recovery_actions (public_id, action, reason, idempotency_key, status, created_at) "
                       "VALUES ('" + "b" * 32 + "', 'retry_event', 'operator retry', 'migration-key-1', 'completed', '2026-01-01')"))
    with pytest.raises(Exception, match="Refusing to downgrade"):
        command.downgrade(cfg, "0029_provider_webhooks")                                                  # fail closed: the only record of operator interventions
    assert "billing_recovery_actions" in inspect(create_engine(url)).get_table_names()
    with create_engine(url).connect() as c:
        assert c.execute(text("SELECT COUNT(*) FROM billing_recovery_actions")).scalar() == 1
