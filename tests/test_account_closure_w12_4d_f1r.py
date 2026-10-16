# ruff: noqa: F811
"""W12.4D-F1R: subscription-aware account closure (owner decision A) and the dedicated billing recovery permission (owner decision B). FULLY OFFLINE: synthetic
provider state, no Stripe call of any kind, isolated databases, every non-loopback socket fails the test."""

from __future__ import annotations

import threading
from datetime import timedelta
from pathlib import Path

import pytest
from sqlalchemy import func, select, update

from src.application.account_deletion_service import AccountDeletionService, SubscriptionResolutionRequired
from src.billing import closure as CL
from src.billing.closure import ClosureService
from src.billing.provider_state import ProviderStateUnavailable
from src.persistence import (
    BillingAccountClosure, BillingCheckoutSession, BillingCommercialTerms, BillingProviderLink, BillingProviderPrice, PlanVersion, PreparationMemory, User, utcnow,
)
from tests.test_webhooks_w12_4d_d import (  # noqa: F401  (shared fixtures and factories)
    _no_network, accept_and_process, checkout_event, count, env, invoice_event, link_of, plan_of, reader_for, refund_event, service, sub_event,
)

ROOT = Path(__file__).resolve().parents[1]
OPS = "/api/v1/admin/billing/operations"


def closure(env, reader_available=True):
    return ClosureService(env.sf, reader_available=reader_available, clock=lambda: env.clock_now[0])


def live(env, **state):
    """User 0 with a verified provider subscription in ``state`` (through the real reconciliation path)."""
    reader_for(env, **state)
    svc = service(env)
    accept_and_process(env, svc, checkout_event(ref="REFAAAA0"))
    return svc


def set_state(env, svc, **state):
    env.clock_now[0] += timedelta(seconds=5)
    env.reader.set_subscription("sub_synth_1", **state)
    return accept_and_process(env, svc, sub_event())


def case_of(env, uid=None):
    with env.sf() as s:
        q = select(BillingAccountClosure)
        if uid:
            q = q.where(BillingAccountClosure.user_id == uid)
        return s.scalars(q).all()


def drop_checkouts(env):
    with env.sf() as s:
        s.execute(BillingCheckoutSession.__table__.delete().where(BillingCheckoutSession.status.in_(("open", "pending_creation"))))
        s.commit()


# ================================================================ A. ROOT CAUSE AND NORMAL CLOSURE ====================================================

def test_F1_07_root_cause_the_deletion_path_had_no_billing_awareness():
    """The route and the privacy job both call ``AccountDeletionService.delete_account`` directly; before W12.4D-F1R it deleted provider links without a check."""
    svc = (ROOT / "src/application/account_deletion_service.py").read_text()
    assert "SubscriptionResolutionRequired" in svc and "preserve_billing_reference" in svc
    assert "ClosureService" in (ROOT / "src/api/routes/auth.py").read_text() and "begin_retained_erasure" in (ROOT / "src/privacy/runtime.py").read_text()


def test_no_subscription_closes_normally_with_no_case(env):
    drop_checkouts(env)
    assert closure(env).request(env.users[0]) == {"proceed": True, "blocking": False, "reasons": [], "case": None}
    summary = AccountDeletionService(env.sf).delete_account(env.users[0])
    assert summary.existed and count(env, BillingAccountClosure) == 0
    with env.sf() as s:
        assert s.get(User, env.users[0]) is None and s.get(User, env.users[1]) is not None


@pytest.mark.parametrize("terminal", ["canceled", "incomplete_expired"])
def test_a_terminal_subscription_permits_closure(env, terminal):
    svc = live(env)
    set_state(env, svc, state=terminal, latest_invoice_state="paid")
    drop_checkouts(env)
    assert closure(env).request(env.users[0])["proceed"] is True
    AccountDeletionService(env.sf).delete_account(env.users[0])
    with env.sf() as s:
        assert s.get(User, env.users[0]) is None and s.scalar(select(func.count()).select_from(BillingProviderLink)) == 0


# ================================================================ B. UNRESOLVED STATES REQUIRE RESOLUTION ==============================================

@pytest.mark.parametrize("state,invoice,cancel,reason", [
    ("active", "paid", False, "live_subscription"), ("trialing", "none", False, "live_subscription"), ("past_due", "failed", False, "payment_unresolved"),
    ("unpaid", "failed", False, "payment_unresolved"), ("active", "paid", True, "cancellation_scheduled"), ("incomplete", "open", False, "live_subscription"),
    ("paused", "none", False, "live_subscription")])
def test_unresolved_states_require_resolution_and_nothing_is_deleted(env, state, invoice, cancel, reason):
    live(env, state=state, latest_invoice_state=invoice, cancel_at_period_end=cancel)
    out = closure(env).request(env.users[0])
    assert out["proceed"] is False and reason in out["reasons"] and out["case"]["status"] in ("requested", "awaiting_provider")
    with pytest.raises(SubscriptionResolutionRequired):
        AccountDeletionService(env.sf).delete_account(env.users[0])
    with env.sf() as s:
        assert s.get(User, env.users[0]) is not None and s.scalar(select(func.count()).select_from(BillingProviderLink)) == 1       # the relationship is intact


def test_scheduled_cancellation_is_pending_not_terminated_and_a_request_is_never_a_cancellation(env):
    live(env, cancel_at_period_end=True)
    out = closure(env).request(env.users[0])
    c = out["case"]
    assert c["status"] == "awaiting_provider" and c["subscription_resolution"] == "pending_confirmation" and c["provider_cancellation"] == "guided"
    assert c["provider_cancellation"] != "confirmed" and link_of(env).provider_state == "active"


def test_unknown_provider_state_fails_closed_to_review(env, monkeypatch):
    live(env, state="paused", latest_invoice_state="none")
    monkeypatch.setattr(CL, "PROVIDER_LINK_STATES", tuple(s for s in CL.PROVIDER_LINK_STATES if s != "paused"))      # a state outside the known vocabulary
    out = closure(env).request(env.users[0])
    assert out["proceed"] is False and "state_unknown" in out["reasons"]
    assert out["case"]["status"] == "needs_review" and out["case"]["review_required"] is True and out["case"]["subscription_resolution"] == "unavailable"


def test_an_open_checkout_that_can_still_be_completed_blocks_closure_until_it_expires(env):
    out = closure(env).request(env.users[1])                                         # the fixture gives every candidate an OPEN checkout
    assert out["proceed"] is False and out["reasons"] == ["checkout_in_progress"]
    env.clock_now[0] += timedelta(hours=1)
    with env.sf() as s:
        s.execute(update(BillingCheckoutSession).where(BillingCheckoutSession.user_id == env.users[1]).values(expires_at=env.clock_now[0] - timedelta(minutes=5)))
        s.commit()
    assert closure(env).request(env.users[1])["proceed"] is True


def test_null_provider_reader_never_invents_a_cancellation(env):
    live(env)
    c = closure(env, reader_available=False).request(env.users[0])["case"]
    assert c["subscription_resolution"] == "unavailable" and c["provider_cancellation"] == "guided" and c["status"] == "requested"
    with env.sf() as s:
        assert s.scalar(select(BillingAccountClosure)).failure_category == "provider_reader_unavailable"


def test_provider_timeout_leaves_a_durable_pending_case(env):
    svc = live(env)
    closure(env).request(env.users[0])
    env.reader.fail = ProviderStateUnavailable("provider_timeout")
    env.clock_now[0] += timedelta(seconds=5)
    out = svc.accept(sub_event())
    assert svc.process(out["public_id"]).status == "retry"
    cases = case_of(env, env.users[0])
    assert len(cases) == 1 and cases[0].status in ("requested", "awaiting_provider") and link_of(env).provider_state == "active"


# ================================================================ C. IDEMPOTENCY AND CONCURRENCY ======================================================

def test_duplicate_requests_share_one_case(env):
    live(env)
    a, b = closure(env).request(env.users[0]), closure(env).request(env.users[0])
    assert a["case"]["requested_at"][:19] == b["case"]["requested_at"][:19] and len(case_of(env)) == 1


def test_concurrent_requests_make_one_logical_case(env):
    live(env)
    out = []
    ts = [threading.Thread(target=lambda: out.append(closure(env).request(env.users[0])["proceed"])) for _ in range(8)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert out == [False] * 8 and len(case_of(env)) == 1


# ================================================================ D. PROVIDER EVENTS DURING CLOSURE ====================================================

def test_webhooks_during_closure_keep_the_case_consistent_and_confirm_cancellation(env):
    svc = live(env, state="past_due", latest_invoice_state="failed")
    assert closure(env).request(env.users[0])["case"]["status"] == "requested"
    set_state(env, svc, state="active", latest_invoice_state="paid", cancel_at_period_end=True)
    assert case_of(env)[0].status == "awaiting_provider" and case_of(env)[0].subscription_resolution == "pending_confirmation"      # scheduled, still not terminal
    set_state(env, svc, state="canceled", latest_invoice_state="paid")                 # verified provider cancellation
    c = case_of(env)[0]
    assert (c.status, c.subscription_resolution, c.provider_cancellation) == ("resolved", "confirmed", "confirmed")
    drop_checkouts(env)
    assert closure(env).request(env.users[0])["proceed"] is True                       # now the normal closure may complete
    AccountDeletionService(env.sf).delete_account(env.users[0])
    done = case_of(env)
    assert len(done) == 1 and done[0].status == "completed" and done[0].user_id is None and done[0].completed_at is not None


def test_a_late_event_after_completion_corrupts_nothing(env):
    svc = live(env)
    closure(env).request(env.users[0])
    set_state(env, svc, state="canceled")
    drop_checkouts(env)
    AccountDeletionService(env.sf).delete_account(env.users[0])
    env.clock_now[0] += timedelta(seconds=5)
    env.reader.set_subscription("sub_synth_1", state="active")
    out, r = accept_and_process(env, svc, sub_event())
    assert r.status in ("quarantined", "needs_review") and count(env, BillingProviderLink) == 0 and case_of(env)[0].status == "completed"


def test_a_refund_during_closure_is_preserved_as_a_financial_fact(env):
    svc = live(env)
    closure(env).request(env.users[0])
    env.reader.payments["pi_synth_1"] = "sub_synth_1"
    env.clock_now[0] += timedelta(seconds=5)
    accept_and_process(env, svc, refund_event())
    assert link_of(env).refund_state == "full" and case_of(env)[0].status in ("requested", "awaiting_provider")


# ================================================================ E. ISOLATION ===========================================================================

def test_closure_of_one_candidate_never_touches_another(env):
    live(env)
    drop_checkouts(env)
    assert closure(env).request(env.users[1])["proceed"] is True
    AccountDeletionService(env.sf).delete_account(env.users[1])
    assert link_of(env, env.users[0]) is not None and count(env, BillingProviderLink) == 1
    assert case_of(env) == []


# ================================================================ F. ERASURE IS SEPARATE AND NEVER POSTPONED ==========================================

def test_privacy_erasure_proceeds_independently_and_retains_only_the_minimum_billing_reference(env):
    live(env)
    with env.sf() as s:
        s.add(PreparationMemory(user_id=env.users[0], category="role", summary="private interview coaching note"))
        s.commit()
    preserve = closure(env, reader_available=False).begin_retained_erasure(env.users[0], "p" * 32)
    assert preserve is True
    summary = AccountDeletionService(env.sf).delete_account(env.users[0], preserve_billing_reference=True)
    assert summary.existed and summary.deleted_rows.get("account_anonymised_billing_reference_retained") == 1
    with env.sf() as s:
        shell = s.get(User, env.users[0])
        assert shell.email is None and shell.display_name is None and shell.subject == f"closed:{env.users[0]}" and shell.status == "deletion_requested" and shell.provider == "closed"
        assert s.scalar(select(func.count()).select_from(PreparationMemory).where(PreparationMemory.user_id == env.users[0])) == 0       # content is erased
        assert s.scalar(select(func.count()).select_from(BillingProviderLink).where(BillingProviderLink.user_id == env.users[0])) == 1    # the minimum reference stays
        case = s.scalar(select(BillingAccountClosure))
    assert (case.status, case.erasure_status, case.retention_basis, case.review_required, case.privacy_request_public_id) == ("erased_reference_retained", "restricted", "unresolved_provider_obligation", True, "p" * 32)
    assert plan_of(env, env.users[0])["plan_code"] == "basic"                                  # no access remains for the closed account


def test_the_retained_reference_is_purged_when_the_subscription_is_confirmed_ended(env):
    svc = live(env)
    closure(env).begin_retained_erasure(env.users[0], None)
    AccountDeletionService(env.sf).delete_account(env.users[0], preserve_billing_reference=True)
    set_state(env, svc, state="canceled", latest_invoice_state="paid")
    with env.sf() as s:
        assert s.get(User, env.users[0]) is None and s.scalar(select(func.count()).select_from(BillingProviderLink)) == 0
        case = s.scalar(select(BillingAccountClosure))
    assert case.status == "completed" and case.erasure_status == "fulfilled" and case.user_id is None and case.retention_basis is None and case.review_required is False


def test_erasure_without_an_unresolved_subscription_is_the_normal_full_deletion(env):
    drop_checkouts(env)
    assert closure(env).begin_retained_erasure(env.users[0], None) is False
    AccountDeletionService(env.sf).delete_account(env.users[0])
    with env.sf() as s:
        assert s.get(User, env.users[0]) is None
    assert case_of(env) == []


def test_the_privacy_deletion_job_is_wired_to_the_retained_erasure_path():
    src = (ROOT / "src/privacy/runtime.py").read_text()
    assert src.index("begin_retained_erasure") < src.index("service.delete_account(subject, preserve_billing_reference=preserve)")


# ================================================================ G. HTTP: CANDIDATE ROUTE, SUMMARY, ISOLATION ==========================================

@pytest.fixture()
def http():
    from tests.test_admin_foundation_w10_1 import Env
    e = Env()
    yield e
    e.app.dependency_overrides.clear()
    e.close()


def make_live_link(sf, user_id, state="active"):
    with sf() as s:
        pv = s.scalar(select(PlanVersion).where(PlanVersion.plan_code == "premium"))
        t = s.scalar(select(BillingCommercialTerms))
        if t is None:
            t = BillingCommercialTerms(public_id="t" * 32, plan_version_id=pv.id, version=1, amount_minor=1999, currency="EUR", billing_interval="month", visibility="public", state="active")
            s.add(t)
            s.flush()
            s.add(BillingProviderPrice(public_id="p" * 32, commercial_terms_id=t.id, provider="stripe_managed_payments", environment="sandbox", provider_product_id="prod_1",
                                       provider_price_id="price_test_1", amount_minor=1999, currency="EUR", billing_interval="month", status="active"))
            s.flush()
        pr = s.scalar(select(BillingProviderPrice))
        s.add(BillingProviderLink(public_id=f"link{user_id:028d}", provider="stripe_managed_payments", environment="sandbox", provider_subscription_id=f"sub_http_{user_id}",
                                  provider_customer_id=f"cus_http_{user_id}", user_id=user_id, plan_version_id=pv.id, commercial_terms_id=t.id, price_mapping_id=pr.id,
                                  provider_state=state, latest_invoice_state="paid", created_at=utcnow(), updated_at=utcnow()))
        s.commit()


def test_http_delete_with_a_live_subscription_is_a_409_with_a_recorded_case_and_the_account_stays(http):
    uid, ck = http.user()
    make_live_link(http.repo.session_factory, uid)
    r = http.c.post("/api/v1/auth/account/delete", cookies=ck)
    assert r.status_code == 409 and r.json()["error"]["code"] == "subscription_resolution_required"
    assert "Cancel it with the seller of record" in r.json()["error"]["message"] and "erasure" in r.json()["error"]["message"]
    assert http.c.get("/api/v1/auth/me", cookies=ck).status_code == 200                              # the account is intact and signed in
    again = http.c.post("/api/v1/auth/account/delete", cookies=ck)
    assert again.status_code == 409
    with http.repo.session_factory() as s:
        assert s.scalar(select(func.count()).select_from(BillingAccountClosure)) == 1               # idempotent: one case
    sm = http.c.get("/api/v1/billing/summary", cookies=ck).json()
    assert sm["closure"]["status"] in ("requested", "awaiting_provider") and sm["closure"]["provider_cancellation"] == "guided"
    assert "sub_http" not in http.c.get("/api/v1/billing/summary", cookies=ck).text                  # no provider identifier is exposed


def test_http_delete_proceeds_normally_once_the_subscription_is_terminal_and_other_users_see_no_case(http):
    uid, ck = http.user()
    uid2, ck2 = http.user()
    make_live_link(http.repo.session_factory, uid)
    assert http.c.post("/api/v1/auth/account/delete", cookies=ck).status_code == 409
    assert http.c.get("/api/v1/billing/summary", cookies=ck2).json()["closure"] is None
    with http.repo.session_factory() as s:
        s.execute(update(BillingProviderLink).where(BillingProviderLink.user_id == uid).values(provider_state="canceled"))
        s.commit()
    done = http.c.post("/api/v1/auth/account/delete", cookies=ck)
    assert done.status_code == 200
    with http.repo.session_factory() as s:
        assert s.get(User, uid) is None and s.get(User, uid2) is not None
        case = s.scalar(select(BillingAccountClosure))
    assert case.status == "completed" and case.user_id is None


def test_http_a_candidate_cannot_delete_or_close_another_candidates_account(http):
    uid_a, ck_a = http.user()
    uid_b, ck_b = http.user()
    make_live_link(http.repo.session_factory, uid_b)
    assert http.c.post("/api/v1/auth/account/delete", cookies=ck_a).status_code == 200            # A deletes only A
    with http.repo.session_factory() as s:
        assert s.get(User, uid_b) is not None and s.scalar(select(func.count()).select_from(BillingProviderLink).where(BillingProviderLink.user_id == uid_b)) == 1


# ================================================================ H. DEDICATED RECOVERY PERMISSION AND STEP-UP ==========================================

def _event(http):
    from tests.test_billing_ops_w12_4d_e import add_event
    return add_event(http.repo.session_factory)


def _retry(http, ck, ref, key):
    return http.c.post(f"{OPS}/events/{ref}/retry", json={"reason": "operator retry"}, headers={"Idempotency-Key": key}, cookies=ck)


def test_recovery_without_step_up_is_refused_for_every_recovery_route(http):
    _, ck = http.user("billing_admin")
    ref = _event(http)
    for path in (f"{OPS}/events/{ref}/retry", f"{OPS}/events/{ref}/requeue", f"{OPS}/subscriptions/{ref}/reconcile"):
        r = http.c.post(path, json={"reason": "operator retry"}, headers={"Idempotency-Key": "nostepup-key-001"}, cookies=ck)
        assert r.status_code == 403 and r.json()["error"]["code"] == "step_up_required", path
    with http.repo.session_factory() as s:
        from src.persistence import BillingRecoveryAction
        assert s.scalar(select(func.count()).select_from(BillingRecoveryAction)) == 0               # refused BEFORE anything was recorded


def test_an_expired_step_up_is_refused(http):
    from tests.test_billing_ops_w12_4d_e import elevate
    from src.persistence import AuthSession
    uid, ck = http.user("billing_admin")
    ref = _event(http)
    elevate(http, ck)
    assert _retry(http, ck, ref, "elevated-key-001").status_code == 200
    with http.repo.session_factory() as s:
        s.execute(update(AuthSession).where(AuthSession.user_id == uid).values(elevated_until=utcnow() - timedelta(minutes=1)))
        s.commit()
    r = _retry(http, ck, ref, "elevated-key-002")
    assert r.status_code == 403 and r.json()["error"]["code"] == "step_up_required"


def test_billing_admin_and_platform_admin_can_step_up_but_other_roles_cannot(http):
    from tests.test_admin_foundation_w10_1 import PW
    for role, ok in (("billing_admin", True), ("platform_admin", True), ("operations_admin", False), ("support_operator", False), ("user", False)):
        _, ck = http.user(role)
        r = http.c.post(f"{OPS}/step-up", json={"password": PW}, cookies=ck)
        assert (r.status_code == 200) is ok, role
    _, ck = http.user("billing_admin")
    assert http.c.post(f"{OPS}/step-up", json={"password": "wrong-password"}, cookies=ck).status_code == 403


def test_operations_admin_cannot_bypass_through_the_generic_job_apis(http):
    """platform.jobs.manage no longer confers billing recovery: not the billing routes, and not the generic job retry of a failed billing job."""
    from src.jobs.service import JobService
    from src.billing import policy as P
    from src.persistence import Job
    uid, ck = http.user("operations_admin")
    jobs = JobService(http.repo.session_factory)
    view, _ = jobs.enqueue(P.JOB_PROCESS_PROVIDER_EVENT, {"event_id": "a" * 32}, idempotency_key="bypass-test")
    with http.repo.session_factory() as s:
        s.execute(update(Job).where(Job.public_id == view["public_id"]).values(state="failed", finished_at=utcnow(), last_error_category="internal_error"))
        s.commit()
    r = http.c.post(f"/api/v1/admin/jobs/{view['public_id']}/retry", cookies=ck)
    assert r.status_code == 409                                                                  # not a retryable job type any more
    with http.repo.session_factory() as s:
        assert s.scalar(select(Job).where(Job.public_id == view["public_id"])).state == "failed"
    assert _retry(http, ck, _event(http), "bypass-key-0001").status_code == 403
    from src.jobs.registry import REGISTRY
    assert REGISTRY[P.JOB_PROCESS_PROVIDER_EVENT].manual_retry is False and REGISTRY[P.JOB_PROVIDER_RECONCILE].manual_retry is False
    assert REGISTRY[P.JOB_PROVIDER_RECONCILE].admin_enqueue is False                              # and no generic enqueue either


def test_billing_admin_cannot_rotate_secrets_and_cannot_use_generic_job_management(http):
    _, ck = http.user("billing_admin")
    assert http.c.post("/api/v1/admin/integrations/stripe_managed_payments/credentials/sandbox_api_key", json={"value": "sk_test_x"}, cookies=ck).status_code == 403
    assert http.c.get("/api/v1/admin/jobs", cookies=ck).status_code == 403


def test_recovery_with_the_null_reader_is_unavailable_not_successful_even_when_authorized(http):
    from tests.test_billing_ops_w12_4d_e import elevate
    _, ck = http.user("billing_admin")
    elevate(http, ck)
    r = _retry(http, ck, _event(http), "nullreader-key-01")
    assert r.status_code == 200 and r.json()["status"] == "refused" and r.json()["result"] == "reader_unavailable"


def test_recovery_cannot_refund_reprice_or_grant(env):
    from src.persistence import BillingApprovalRequest, BillingRefund, Subscription
    svc = service(env)
    reader_for(env)
    out = svc.accept(checkout_event(ref="REFAAAA0"))
    svc.recover("retry_event", out["public_id"], actor_user_id=env.users[0], reason="operator retry", idempotency_key="norefund-key-01")
    assert count(env, BillingApprovalRequest) == 0 and count(env, BillingRefund) == 0
    with env.sf() as s:
        assert s.scalar(select(func.count()).select_from(BillingCommercialTerms)) == 1               # no price change
    assert plan_of(env, env.users[0])["plan_code"] in ("basic", "premium")
    src = (ROOT / "src/billing/reconcile.py").read_text()
    assert "Subscription(" not in src and Subscription is not None


def test_permission_registry_and_role_matrix_for_billing_recover():
    from src.application import admin_permissions as perm
    assert len(perm.PERMISSIONS) == 44 and perm.BILLING_RECOVER in perm.PERMISSION_SET
    holders = sorted(r for r in perm.ADMIN_ROLES if perm.BILLING_RECOVER in perm.permissions_for_role(r))
    assert holders == ["billing_admin", "platform_admin"]
    assert perm.SECRET_ROTATE not in perm.permissions_for_role("billing_admin")
    assert perm.JOBS_MANAGE not in perm.permissions_for_role("billing_admin")
    for role in ("operations_admin", "support_operator", "knowledge_admin", "security_privacy_admin", "user", None, "ghost"):
        assert perm.BILLING_RECOVER not in perm.permissions_for_role(role)


def test_kill_switches_and_unrelated_controls_are_untouched():
    from src.billing import policy as P
    assert (P.LIVE_BILLING_ENABLED, P.EXTERNAL_CHECKOUT_AUTHORIZED, P.STRIPE_WEBHOOK_AUTHORIZED, P.RECONCILE_SCHEDULER_ENABLED, P.PAID_ENTITLEMENT_POLICY_APPROVED) == (False,) * 5
    src = (ROOT / "src/billing/closure.py").read_text()
    for banned in ("import stripe", "requests.", "httpx", "StripeStateReader", "build_stripe_client"):
        assert banned not in src                                                                      # no provider call exists in the closure path


# ================================================================ I. AUDIT AND MIGRATION ================================================================

def test_closure_request_is_audited_once_and_without_provider_identifiers(env):
    rows = []
    live(env)
    cs = ClosureService(env.sf, reader_available=True, audit=type("A", (), {"record": staticmethod(lambda **k: rows.append(k))})(), clock=lambda: env.clock_now[0])
    cs.request(env.users[0])
    cs.request(env.users[0])
    assert [r["event_type"] for r in rows] == ["billing.account_closure_requested"]                  # a retry writes no duplicate audit fact
    blob = str(rows)
    assert "sub_synth" not in blob and "cus_synth" not in blob and "@" not in blob


def _alembic(tmp_path, monkeypatch):
    from alembic.config import Config
    url = f"sqlite:///{tmp_path / 'c.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    cfg = Config("alembic.ini")
    cfg.set_main_option("script_location", "migrations")
    cfg.set_main_option("sqlalchemy.url", url)
    return cfg, url


def test_migration_0031_upgrade_preserves_history_constraints_and_downgrade_fails_closed(tmp_path, monkeypatch):
    from alembic import command
    from alembic.script import ScriptDirectory
    from sqlalchemy import create_engine, inspect, text
    cfg, url = _alembic(tmp_path, monkeypatch)
    command.upgrade(cfg, "0030_billing_recovery")
    with create_engine(url).begin() as c:
        c.execute(text("INSERT INTO billing_recovery_actions (public_id, action, reason, idempotency_key, status, created_at) VALUES ('" + "d" * 32 + "', 'retry_event', 'r', 'f1r-mig-1', 'completed', '2026-01-01')"))
    command.upgrade(cfg, "head")
    insp = inspect(create_engine(url))
    assert "billing_account_closures" in insp.get_table_names() and ScriptDirectory.from_config(cfg).get_heads() == ["0032_ai_operation_events"]
    assert {i["name"]: i for i in insp.get_indexes("billing_account_closures")}["uq_bac_one_active_per_user"]["unique"] == 1
    with create_engine(url).connect() as c:
        assert c.execute(text("SELECT COUNT(*) FROM billing_recovery_actions")).scalar() == 1           # existing financial history untouched
    command.downgrade(cfg, "0030_billing_recovery")                                                  # empty: reversible
    assert "billing_account_closures" not in inspect(create_engine(url)).get_table_names()
    command.upgrade(cfg, "head")
    with create_engine(url).begin() as c:
        c.execute(text("INSERT INTO billing_account_closures (public_id, status, subscription_resolution, provider_cancellation, erasure_status, review_required, requested_at) "
                       "VALUES ('" + "e" * 32 + "', 'requested', 'required', 'guided', 'not_requested', 0, '2026-01-01')"))
    with pytest.raises(Exception, match="Refusing to downgrade"):
        command.downgrade(cfg, "0030_billing_recovery")
    with create_engine(url).connect() as c:
        assert c.execute(text("SELECT COUNT(*) FROM billing_account_closures")).scalar() == 1
