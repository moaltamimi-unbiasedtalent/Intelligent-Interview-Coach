"""P10B-W10.5: MOCK billing. Offline and deterministic: temp DB, the mock adapter (no network), temp job runtime. MOCK BILLING: NOT LIVE.
The load-bearing property under test: billing state is NEVER entitlement state."""

from __future__ import annotations

import re
import socket
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from src.application import admin_audit as A
from src.application import admin_permissions as perm
from src.application.account_deletion_service import AccountDeletionService
from src.billing import policy as P
from src.billing.runtime import BillingRuntime
from src.billing.provider import (
    MOCK_ALLOWED_ENVS, BillingConfigurationError, MockBillingAdapter, ProviderRejected, ProviderRetryable, build_provider, resolve_mode, safe_mode,
)
from src.billing.service import BillingConflict, BillingForbidden, BillingService, BillingValidationError, validate_amount, validate_currency
from src.entitlements import EntitlementService
from src.jobs.service import JobService
from src.jobs.worker import Worker
from src.persistence import (
    BillingApprovalRequest, BillingCommercialTerms, BillingCustomer, BillingInvoice, BillingPayment, BillingProviderSubscription, BillingRefund,
    PlanVersion, ProductEntitlement, Subscription, User, utcnow,
)
from src.plans_repository import PlanRepository
from tests.test_admin_foundation_w10_1 import Env

API = "/api/v1"
ROOT = Path(__file__).resolve().parents[1]
MOCK = resolve_mode("test", "mock")


@pytest.fixture()
def env():
    e = Env()
    yield e
    e.close()


def sf(env):
    return env.accounts.session_factory


class Rig:
    """service + mock provider + job worker over the Env database."""

    def __init__(self, env):
        self.env = env
        self.provider = MockBillingAdapter()
        self.jobs = JobService(sf(env))
        self.svc = BillingService(sf(env), provider=self.provider, mode=MOCK, jobs=self.jobs)
        rt = BillingRuntime(session_factory=sf(env), provider=self.provider, mode=MOCK, jobs=self.jobs)
        self.worker = Worker(self.jobs, services=SimpleNamespace(billing=rt))

    def plan_version(self, code="basic"):
        with sf(self.env)() as s:
            PlanRepository(sf(self.env)).assignable_plans()
            return s.scalar(select(PlanVersion.id).where(PlanVersion.plan_code == code, PlanVersion.status == "active"))

    def ev(self, kind, ref, **data):
        return self.svc.ingest_event(MockBillingAdapter.event(kind, ref, **data), process_inline=True)

    def paid_invoice(self, uid, tag="a", amount=2000, cur="EUR", plan_version_id=None):
        self.ev("customer_created", f"cus_{tag}", customer_ref=f"cus_{tag}", user_id=uid)
        self.ev("invoice_opened", f"inv_{tag}", invoice_ref=f"inv_{tag}", customer_ref=f"cus_{tag}", amount_due_minor=amount, currency=cur)
        self.ev("payment_succeeded", f"pay_{tag}", payment_ref=f"pay_{tag}", invoice_ref=f"inv_{tag}", amount_minor=amount, currency=cur)
        self.ev("invoice_paid", f"inp_{tag}", invoice_ref=f"inv_{tag}")
        with sf(self.env)() as s:
            return s.scalar(select(BillingPayment.public_id).where(BillingPayment.provider_payment_id == f"pay_{tag}"))

    def drain(self, n=10):
        out = []
        for _ in range(n):
            r = self.worker.run_once()
            if r == "idle":
                break
            out.append(r)
        return out


@pytest.fixture()
def rig(env):
    return Rig(env)


TERMS = dict(amount_minor=1099, currency="EUR", interval="month", trial_days=None, visibility="internal")


# =========================================================== mode, guard, adapter
def test_mock_cannot_run_in_production_or_live_and_the_default_is_disabled():
    assert resolve_mode("production", None).enabled is False and resolve_mode("development", None).enabled is False     # disabled by default
    assert resolve_mode("test", "mock").enabled and resolve_mode("development", "mock").enabled
    for env in ("production", "prod", "live", "staging", "preview", ""):
        if env == "":
            continue
        with pytest.raises(BillingConfigurationError):
            resolve_mode(env, "mock")
    for other in ("stripe", "adyen", "paypal", "live"):
        with pytest.raises(BillingConfigurationError):
            resolve_mode("development", other)
    m = safe_mode("production", "mock")
    assert m.enabled is False and m.live is False and m.configuration_error and build_provider(m) is None
    assert safe_mode("development", "mock").as_dict()["live"] is False
    from src.api.dependencies import DEV_ENVS
    assert tuple(MOCK_ALLOWED_ENVS) == tuple(DEV_ENVS)


def test_mock_adapter_is_offline_deterministic_and_idempotent(monkeypatch):
    import httpx
    monkeypatch.setattr(socket, "socket", lambda *a, **k: (_ for _ in ()).throw(AssertionError("network")))
    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", lambda *a, **k: (_ for _ in ()).throw(AssertionError("network")))
    a = MockBillingAdapter()
    assert a.live is False and a.capabilities()["network"] is False and a.capabilities()["checkout"] is False and "NOT LIVE" in a.capabilities()["label"]
    r1 = a.refund(idempotency_key="k1", provider_payment_id="p", amount_minor=5, currency="EUR")
    r2 = a.refund(idempotency_key="k1", provider_payment_id="p", amount_minor=5, currency="EUR")
    assert r1 == r2 and r1.provider_refund_id.startswith("mock_re_")
    assert a.refund(idempotency_key="k2", provider_payment_id="p", amount_minor=5, currency="EUR").provider_refund_id != r1.provider_refund_id
    assert MockBillingAdapter.event("invoice_paid", "x") == MockBillingAdapter.event("invoice_paid", "x")
    a.fail_next = ["retryable", "rejected"]
    with pytest.raises(ProviderRetryable):
        a.refund(idempotency_key="k3", provider_payment_id="p", amount_minor=1, currency="EUR")
    with pytest.raises(ProviderRejected):
        a.refund(idempotency_key="k3", provider_payment_id="p", amount_minor=1, currency="EUR")


def test_api_states_mock_not_live_machine_readably_and_never_live_when_misconfigured(env, monkeypatch):
    _, ck = env.user("billing_admin")
    monkeypatch.setenv("BILLING_PROVIDER", "mock")
    o = env.c.get(f"{API}/admin/billing", cookies=ck).json()
    assert o["mode"]["provider"] == "mock" and o["mode"]["live"] is False and o["mode"]["mode"] == "mock" and o["mode"]["enabled"] is True
    assert "NOT LIVE" in o["mode"]["label"] and o["mode"]["checkout"] is False
    monkeypatch.setenv("API_ENV", "production")
    o = env.c.get(f"{API}/admin/billing", cookies=ck).json()
    assert o["mode"]["enabled"] is False and o["mode"]["live"] is False and o["mode"]["configuration_error"]
    assert "LIVE BILLING" not in o["mode"]["label"].replace("NOT LIVE BILLING", "")
    monkeypatch.delenv("BILLING_PROVIDER")
    monkeypatch.setenv("API_ENV", "test")
    assert env.c.get(f"{API}/admin/billing", cookies=ck).json()["mode"]["enabled"] is False


# =========================================================== commercial terms, amounts, no invented price
def test_no_price_is_seeded_and_unconfigured_means_unconfigured(env, rig):
    env.user("user")
    t = rig.svc.list_terms()
    assert t["items"] and all(i["configured"] is False and i["current"] is None for i in t["items"])
    with sf(env)() as s:
        assert s.scalar(text("select count(*) from billing_commercial_terms")) == 0
        for table in ("billing_customers", "billing_invoices", "billing_payments", "billing_refunds", "billing_events"):
            assert s.scalar(text(f"select count(*) from {table}")) == 0


def test_money_is_integer_minor_units_and_inputs_are_validated():
    for bad in (-1, 1.5, True, "10", None, P.MAX_AMOUNT_MINOR + 1):
        with pytest.raises(BillingValidationError):
            validate_amount(bad)
    assert validate_amount(0) == 0 and validate_amount(1099) == 1099
    for bad in ("eur", "EU", "EURO", 12, None, "E1R"):
        with pytest.raises(BillingValidationError):
            validate_currency(bad)
    for kw in (dict(interval="week"), dict(visibility="secret"), dict(trial_days=0), dict(trial_days=366), dict(trial_days=True), dict(amount_minor=9.99)):
        with pytest.raises(BillingValidationError):
            BillingService.validate_terms(**{**TERMS, **kw})


def test_price_change_requires_a_different_authorised_administrator_and_versions_are_immutable(env, rig):
    b1, c1 = env.user("billing_admin"); b2, c2 = env.user("billing_admin"); _, plat = env.user("platform_admin"); _, sup = env.user("support_operator")
    pv = rig.plan_version("premium")
    body = {"plan_version_id": pv, "amount_minor": 1099, "currency": "EUR", "interval": "month", "trial_days": 14, "visibility": "public", "reason": "Test terms"}
    for ck in (plat, sup):
        assert env.c.post(f"{API}/admin/billing/price-changes", json=body, cookies=ck).status_code == 403
    for bad in ({**body, "amount_minor": 10.5}, {**body, "amount_minor": True}, {**body, "currency": "eur"}, {**body, "reason": ""}, {**body, "interval": "day"}):
        assert env.c.post(f"{API}/admin/billing/price-changes", json=bad, cookies=c1).status_code == 422
    r = env.c.post(f"{API}/admin/billing/price-changes", json=body, cookies=c1)
    assert r.status_code == 201 and r.json()["status"] == "pending"
    aid = r.json()["public_id"]
    assert env.c.post(f"{API}/admin/billing/price-changes", json=body, cookies=c2).status_code == 409                     # one pending per plan version
    assert env.c.post(f"{API}/admin/billing/price-changes/{aid}/approve", cookies=c1).status_code == 403                  # no self-approval
    assert env.c.post(f"{API}/admin/billing/price-changes/{aid}/approve", cookies=plat).status_code == 403                # no platform_admin bypass
    assert env.c.get(f"{API}/admin/billing/terms", cookies=c1).json()["items"][-1]["configured"] is False                 # nothing active yet
    ok = env.c.post(f"{API}/admin/billing/price-changes/{aid}/approve", cookies=c2)
    assert ok.status_code == 200 and ok.json()["status"] == "executed" and ok.json()["decided_by_user_id"] == b2
    terms = {i["plan_version_id"]: i for i in env.c.get(f"{API}/admin/billing/terms", cookies=c1).json()["items"]}[pv]
    assert terms["configured"] and terms["current"]["version"] == 1 and terms["current"]["amount_minor"] == 1099 and terms["current"]["trial_days"] == 14
    assert env.c.post(f"{API}/admin/billing/price-changes/{aid}/approve", cookies=c2).status_code == 409                  # decided once
    body2 = {**body, "amount_minor": 1299, "visibility": "private", "trial_days": None}
    a2 = env.c.post(f"{API}/admin/billing/price-changes", json=body2, cookies=c2).json()["public_id"]
    assert env.c.post(f"{API}/admin/billing/price-changes/{a2}/approve", cookies=c1).status_code == 200
    terms = {i["plan_version_id"]: i for i in env.c.get(f"{API}/admin/billing/terms", cookies=c1).json()["items"]}[pv]
    assert terms["current"]["version"] == 2 and [h["state"] for h in terms["history"]] == ["active", "retired"]
    assert {h["version"]: h["amount_minor"] for h in terms["history"]} == {1: 1099, 2: 1299}                             # history preserved unchanged
    a3 = env.c.post(f"{API}/admin/billing/price-changes", json={**body, "amount_minor": 1}, cookies=c1).json()["public_id"]
    assert env.c.post(f"{API}/admin/billing/price-changes/{a3}/reject", cookies=c1).status_code == 403
    assert env.c.post(f"{API}/admin/billing/price-changes/{a3}/reject", cookies=c2).json()["status"] == "rejected"
    names = {e["event_type"] for e in env.events()}
    assert {A.ADMIN_BILLING_PRICE_CHANGE_REQUESTED, A.ADMIN_BILLING_PRICE_CHANGE_APPROVED, A.ADMIN_BILLING_PRICE_ACTIVATED,
            A.ADMIN_BILLING_PRICE_CHANGE_REJECTED} <= names
    with sf(env)() as s, pytest.raises(IntegrityError):                                                                    # DB: one active per plan version
        s.add(BillingCommercialTerms(public_id="z" * 32, plan_version_id=pv, version=9, amount_minor=1, currency="EUR", billing_interval="month",
                                     visibility="public", state="active", created_at=utcnow()))
        s.commit()


def test_inactive_approver_and_missing_permission_cannot_approve(env, rig):
    b1, _ = env.user("billing_admin"); b2, _ = env.user("billing_admin")
    pv = rig.plan_version("premium")
    a = rig.svc.request_price_change(pv, **TERMS, reason="x", actor_user_id=b1)
    with sf(env)() as s:
        s.get(User, b2).status = "deactivated"
        s.commit()
    with pytest.raises(BillingForbidden):
        rig.svc.decide_price_change(a["public_id"], approve=True, actor_user_id=b2)
    plat_id, _ = env.user("platform_admin")
    with pytest.raises(BillingForbidden):
        rig.svc.decide_price_change(a["public_id"], approve=True, actor_user_id=plat_id)
    with pytest.raises(BillingForbidden):
        rig.svc.decide_price_change(a["public_id"], approve=True, actor_user_id=b1)


def test_audit_failure_rolls_back_price_activation(env, rig, monkeypatch):
    b1, _ = env.user("billing_admin"); b2, _ = env.user("billing_admin")
    pv = rig.plan_version("premium")
    a = rig.svc.request_price_change(pv, **TERMS, reason="x", actor_user_id=b1)
    import src.billing.service as S
    monkeypatch.setattr(S, "_stage", lambda *a_, **k: (_ for _ in ()).throw(RuntimeError("audit down")))
    with pytest.raises(RuntimeError):
        rig.svc.decide_price_change(a["public_id"], approve=True, actor_user_id=b2, audit_decision={"event_type": "x"})
    monkeypatch.undo()
    with sf(env)() as s:
        assert s.scalar(text("select count(*) from billing_commercial_terms")) == 0
        assert s.scalar(select(BillingApprovalRequest.status)) == "pending"


# =========================================================== the load-bearing invariant: billing != entitlement
def snapshot(env, uid):
    es = EntitlementService(sf(env))
    resolved = {k: v.to_dict() for k, v in es.resolve_all(uid).items()}
    with sf(env)() as s:
        subs = [(x.id, x.plan_version_id, x.status, x.source) for x in s.scalars(select(Subscription).where(Subscription.user_id == uid)).all()]
        tier = s.scalar(select(ProductEntitlement.tier).where(ProductEntitlement.user_id == uid))
    return resolved, subs, tier


def test_billing_never_changes_entitlements_subscriptions_or_tier(env, rig):
    uid, _ = env.user("user"); b1, _ = env.user("billing_admin"); b2, _ = env.user("billing_admin")
    base = snapshot(env, uid)
    assert base[1], "the user has a W10.4 subscription"
    pv = rig.plan_version("premium")
    steps = []

    def check(label):
        assert snapshot(env, uid) == base, label
        steps.append(label)

    a = rig.svc.request_price_change(pv, **TERMS, reason="x", actor_user_id=b1); check("price requested")
    rig.svc.decide_price_change(a["public_id"], approve=True, actor_user_id=b2); check("price created")
    a = rig.svc.request_price_change(pv, **{**TERMS, "amount_minor": 2599}, reason="x", actor_user_id=b2)
    rig.svc.decide_price_change(a["public_id"], approve=True, actor_user_id=b1); check("price changed")
    rig.ev("customer_created", "cus_n", customer_ref="cus_n", user_id=uid); check("customer mirrored")
    rig.ev("subscription_updated", "s1", subscription_ref="sub_n", customer_ref="cus_n", plan_version_id=pv, state="active"); check("provider sub active")
    rig.ev("subscription_updated", "s2", subscription_ref="sub_n", customer_ref="cus_n", plan_version_id=pv, state="past_due",
           grace_until="2026-12-01T00:00:00+00:00"); check("provider sub past_due")
    rig.ev("invoice_opened", "i1", invoice_ref="inv_n", customer_ref="cus_n", subscription_ref="sub_n", amount_due_minor=2599, currency="EUR"); check("invoice opened")
    rig.ev("payment_failed", "p1", payment_ref="pay_f", invoice_ref="inv_n", amount_minor=2599, currency="EUR", failure_category="declined"); check("payment failed + invoice past_due")
    rig.ev("payment_succeeded", "p2", payment_ref="pay_n", invoice_ref="inv_n", amount_minor=2599, currency="EUR"); check("payment succeeded")
    with sf(env)() as s:
        pay = s.scalar(select(BillingPayment.public_id).where(BillingPayment.provider_payment_id == "pay_n"))
        assert s.scalar(select(BillingInvoice.state)) == "past_due"
    ra = rig.svc.request_refund(pay, amount_minor=1000, reason="x", actor_user_id=b1); check("refund requested")
    rig.svc.decide_refund(ra["public_id"], approve=True, actor_user_id=b2); check("refund approved")
    assert rig.drain() == ["succeeded"]; check("refund executed")
    rig.ev("subscription_updated", "s3", subscription_ref="sub_n", customer_ref="cus_n", plan_version_id=pv, state="cancelled"); check("provider sub cancelled")
    with sf(env)() as s:
        assert s.scalar(select(BillingProviderSubscription.provider_state)) == "cancelled"
        assert s.scalar(select(Subscription.status).where(Subscription.user_id == uid, Subscription.status == "active")) == "active"   # NOT ended
    assert len(steps) == 13
    # the reverse: an admin plan assignment is access only and creates no billing record
    PlanRepository(sf(env)).assign("premium", user_id=uid)
    with sf(env)() as s:
        assert s.scalar(text("select count(*) from billing_customers")) == 1                                              # only the one mirrored above
        assert s.scalar(text("select count(*) from billing_invoices")) == 1


def test_billing_modules_never_touch_subscriptions_entitlements_or_the_tier():
    import ast

    def code_only(path):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and node.body and isinstance(node.body[0], ast.Expr) \
                    and isinstance(getattr(node.body[0], "value", None), ast.Constant) and isinstance(node.body[0].value.value, str):
                node.body = node.body[1:] or [ast.Pass()]
        return ast.unparse(tree)

    src = " ".join(code_only(p) for p in [*(ROOT / "src/billing").glob("*.py"), ROOT / "src/api/routes/admin_billing.py"])
    for banned in ("Subscription(", "ProductEntitlement", "PlanEntitlement", "EntitlementService", "PlanRepository", "tier ", ".tier", "assign("):
        assert banned not in src.replace("BillingProviderSubscription", "BPS").replace("provider_subscription", "ps"), banned


# =========================================================== events: normalised and idempotent
def test_duplicate_events_are_one_record_one_transition_and_unknown_fields_are_rejected(env, rig):
    uid, _ = env.user("user")
    rig.ev("customer_created", "c", customer_ref="cus_d", user_id=uid)
    evt = MockBillingAdapter.event("invoice_opened", "dup", invoice_ref="inv_d", customer_ref="cus_d", amount_due_minor=500, currency="EUR")
    v1, c1 = rig.svc.ingest_event(evt, process_inline=True)
    v2, c2 = rig.svc.ingest_event(evt, process_inline=True)
    assert c1 and not c2 and v1["public_id"] == v2["public_id"]
    rig.svc.process_event(v1["public_id"])                                                                                  # replay
    with sf(env)() as s:
        assert s.scalar(text("select count(*) from billing_events")) == 2 and s.scalar(text("select count(*) from billing_invoices")) == 1
    for bad in (("invoice_paid", {"invoice_ref": "x", "card_number": "4242"}), ("nonsense", {}), ("invoice_paid", {}), ("invoice_opened", {"invoice_ref": "x"})):
        with pytest.raises(BillingValidationError):
            rig.svc.record_event("mock", "e_bad", bad[0], bad[1])
    with pytest.raises(BillingValidationError):
        rig.svc.record_event("stripe", "e1", "invoice_paid", {"invoice_ref": "x"})
    rig.svc.record_event("mock", "e_unknown_cust", "invoice_opened", {"invoice_ref": "i9", "customer_ref": "nobody", "amount_due_minor": 1, "currency": "EUR"})
    with pytest.raises(BillingValidationError):
        rig.svc.process_event(rig.svc.record_event("mock", "e_unknown_cust", "invoice_opened", {"invoice_ref": "i9", "customer_ref": "nobody", "amount_due_minor": 1, "currency": "EUR"})[0]["public_id"])


def test_concurrent_duplicate_ingest_creates_one_event(env, rig):
    uid, _ = env.user("user")
    evt = MockBillingAdapter.event("customer_created", "race", customer_ref="cus_r", user_id=uid)
    out, barrier = [], threading.Barrier(6)

    def go():
        barrier.wait()
        out.append(rig.svc.record_event(evt["provider"], evt["provider_event_id"], evt["event_type"], evt["data"]))

    ts = [threading.Thread(target=go) for _ in range(6)]
    [t.start() for t in ts]; [t.join() for t in ts]
    assert len({v["public_id"] for v, _ in out}) == 1 and sum(1 for _, created in out if created) == 1


def test_event_job_processes_through_the_w109_worker_idempotently(env, rig):
    uid, _ = env.user("user")
    rig.svc.ingest_event(MockBillingAdapter.event("customer_created", "j", customer_ref="cus_j", user_id=uid))
    assert rig.drain() == ["succeeded"]
    rig.svc.ingest_event(MockBillingAdapter.event("customer_created", "j", customer_ref="cus_j", user_id=uid))             # duplicate: no second job needed
    assert rig.drain() == []
    with sf(env)() as s:
        assert s.scalar(text("select count(*) from billing_customers")) == 1 and s.scalar(select(text("state")).select_from(text("billing_events"))) == "processed"
        assert s.scalar(text("select payload_json from jobs where job_type='billing_process_event' limit 1")) is not None


# =========================================================== refunds
def test_refund_validation_second_approval_execution_and_no_over_refund(env, rig):
    uid, _ = env.user("user"); b1, c1 = env.user("billing_admin"); b2, c2 = env.user("billing_admin"); _, plat = env.user("platform_admin")
    pay = rig.paid_invoice(uid, "r1", 2000)
    for bad in (0, -5, 2001, 1.5, True):
        assert env.c.post(f"{API}/admin/billing/payments/{pay}/refunds", json={"amount_minor": bad, "reason": "x"}, cookies=c1).status_code == 422
    assert env.c.post(f"{API}/admin/billing/payments/{pay}/refunds", json={"amount_minor": 100, "reason": "x"}, cookies=plat).status_code == 403
    assert env.c.post(f"{API}/admin/billing/payments/{'0' * 32}/refunds", json={"amount_minor": 100, "reason": "x"}, cookies=c1).status_code == 404
    req = env.c.post(f"{API}/admin/billing/payments/{pay}/refunds", json={"amount_minor": 1200, "reason": "Duplicate charge"}, cookies=c1)
    assert req.status_code == 201 and req.json()["status"] == "pending" and req.json()["proposed"]["currency"] == "EUR"
    aid = req.json()["public_id"]
    assert env.c.post(f"{API}/admin/billing/refunds/{aid}/approve", cookies=c1).status_code == 403                       # no self-approval
    assert env.c.post(f"{API}/admin/billing/refunds/{aid}/approve", cookies=plat).status_code == 403
    assert env.c.post(f"{API}/admin/billing/price-changes/{aid}/approve", cookies=c2).status_code == 404                  # wrong action route
    ok = env.c.post(f"{API}/admin/billing/refunds/{aid}/approve", cookies=c2)
    assert ok.status_code == 200 and ok.json()["status"] == "approved"                                                      # queued, NOT yet executed
    assert env.c.get(f"{API}/admin/billing/refunds", cookies=c1).json()["items"][0]["state"] == "pending"
    assert env.c.get(f"{API}/admin/billing/payments/{pay}", cookies=c1).json()["refundable_minor"] == 800                 # the pending refund is reserved
    assert env.c.post(f"{API}/admin/billing/payments/{pay}/refunds", json={"amount_minor": 900, "reason": "x"}, cookies=c1).status_code == 422
    assert rig.drain() == ["succeeded"]
    d = env.c.get(f"{API}/admin/billing/payments/{pay}", cookies=c1).json()
    assert d["refunded_minor"] == 1200 and d["refundable_minor"] == 800 and d["refunds"][0]["state"] == "succeeded" and d["refunds"][0]["mock"] is True
    assert d["refunds"][0]["provider_refund_id"].startswith("mock_re_")
    assert env.c.get(f"{API}/admin/billing/approvals?action=refund", cookies=c1).json()["items"][0]["status"] == "executed"
    r2 = env.c.post(f"{API}/admin/billing/payments/{pay}/refunds", json={"amount_minor": 800, "reason": "rest"}, cookies=c2).json()["public_id"]
    assert env.c.post(f"{API}/admin/billing/refunds/{r2}/reject", cookies=c2).status_code == 403
    assert env.c.post(f"{API}/admin/billing/refunds/{r2}/reject", cookies=c1).json()["status"] == "rejected"
    assert {A.ADMIN_BILLING_REFUND_REQUESTED, A.ADMIN_BILLING_REFUND_APPROVED, A.ADMIN_BILLING_REFUND_EXECUTED, A.ADMIN_BILLING_REFUND_REJECTED} <= {e["event_type"] for e in env.events()}
    blob = " ".join(str(e) for e in env.events() if e["event_type"].startswith("admin.billing_"))
    assert "card" not in blob.lower() and "Duplicate charge" not in blob


def test_refund_rejects_failed_payments_currency_mismatch_and_duplicate_pending_requests(env, rig):
    uid, _ = env.user("user"); b1, _ = env.user("billing_admin")
    rig.ev("customer_created", "c", customer_ref="cus_x", user_id=uid)
    rig.ev("invoice_opened", "i", invoice_ref="inv_x", customer_ref="cus_x", amount_due_minor=500, currency="EUR")
    rig.ev("payment_failed", "pf", payment_ref="pay_x", invoice_ref="inv_x", amount_minor=500, currency="EUR", failure_category="declined")
    with sf(env)() as s:
        failed = s.scalar(select(BillingPayment.public_id))
    with pytest.raises(BillingConflict):
        rig.svc.request_refund(failed, amount_minor=100, reason="x", actor_user_id=b1)
    with pytest.raises(Exception):
        rig.ev("payment_succeeded", "pm", payment_ref="pay_m", invoice_ref="inv_x", amount_minor=500, currency="USD")        # invoice currency mismatch
    uid2, _ = env.user("user")
    good = rig.paid_invoice(uid2, "y", 700)
    rig.svc.request_refund(good, amount_minor=100, reason="x", actor_user_id=b1)
    with pytest.raises(BillingConflict):
        rig.svc.request_refund(good, amount_minor=100, reason="y", actor_user_id=b1)                                        # one pending request per payment


def test_refund_crash_window_replay_counts_once(env, rig):
    """Provider succeeds, the worker dies before the local update, the lease expires, another worker replays: one logical refund."""
    uid, _ = env.user("user"); b1, _ = env.user("billing_admin"); b2, _ = env.user("billing_admin")
    pay = rig.paid_invoice(uid, "cw", 3000)
    a = rig.svc.request_refund(pay, amount_minor=1000, reason="x", actor_user_id=b1)
    rig.svc.decide_refund(a["public_id"], approve=True, actor_user_id=b2)
    ghost = rig.jobs.claim("crashed-worker")
    assert ghost.job_type == P.JOB_REFUND
    with sf(env)() as s:
        rf = s.scalar(select(BillingRefund))
        key = rf.idempotency_key
    rig.provider.refund(idempotency_key=key, provider_payment_id="pay_cw", amount_minor=1000, currency="EUR")            # provider acted ...
    with sf(env)() as s:
        assert s.scalar(select(BillingRefund.state)) == "pending"                                                           # ... local state never updated
    import src.jobs.registry as JR
    # expire the lease deterministically
    with sf(env)() as s:
        s.execute(text("update jobs set lease_expires_at='2000-01-01' where state='running'"))
        s.commit()
    assert rig.drain() == ["succeeded"]
    with sf(env)() as s:
        refunds = s.scalars(select(BillingRefund)).all()
        assert len(refunds) == 1 and refunds[0].state == "succeeded" and refunds[0].amount_minor == 1000
        assert s.scalar(select(BillingApprovalRequest.status)) == "executed"
        assert s.scalar(text("select attempts from jobs where job_type='billing_refund'")) == 2
    assert len(set(rig.provider.calls)) == 1 and len(rig.provider.calls) == 2                                              # same key, same provider refund id
    assert rig.svc.execute_refund(refunds[0].public_id) == "succeeded"                                                     # further replay: no-op
    assert JR


def test_refund_provider_failures_are_classified_and_terminal_failure_is_recorded(env, rig):
    uid, _ = env.user("user"); b1, _ = env.user("billing_admin"); b2, _ = env.user("billing_admin")
    pay = rig.paid_invoice(uid, "pf", 3000)
    a = rig.svc.request_refund(pay, amount_minor=500, reason="x", actor_user_id=b1)
    rig.svc.decide_refund(a["public_id"], approve=True, actor_user_id=b2)
    rig.provider.fail_next = ["retryable"]
    assert rig.worker.run_once() == "retry_scheduled"
    with sf(env)() as s:
        assert s.scalar(select(BillingRefund.state)) == "pending"
        s.execute(text("update jobs set available_at='2000-01-01'"))
        s.commit()
    assert rig.worker.run_once() == "succeeded"
    uid2, _ = env.user("user")
    pay2 = rig.paid_invoice(uid2, "pg", 3000)
    a2 = rig.svc.request_refund(pay2, amount_minor=500, reason="x", actor_user_id=b1)
    rig.svc.decide_refund(a2["public_id"], approve=True, actor_user_id=b2)
    rig.provider.fail_next = ["rejected"]
    assert rig.worker.run_once() == "failed"
    with sf(env)() as s:
        assert s.scalars(select(BillingRefund.state).order_by(BillingRefund.id)).all() == ["succeeded", "failed"]
        assert s.scalar(select(BillingApprovalRequest.status).order_by(BillingApprovalRequest.id.desc())) == "failed"
    assert A.ADMIN_BILLING_REFUND_FAILED in {e["event_type"] for e in env.events()}


def test_refund_is_refused_when_billing_is_disabled(env):
    uid, _ = env.user("user"); b1, _ = env.user("billing_admin"); b2, _ = env.user("billing_admin")
    full = Rig(env)
    pay = full.paid_invoice(uid, "dis", 1000)
    a = full.svc.request_refund(pay, amount_minor=100, reason="x", actor_user_id=b1)
    full.svc.decide_refund(a["public_id"], approve=True, actor_user_id=b2)
    off = BillingRuntime(session_factory=sf(env), provider=None, mode=resolve_mode("test", None), jobs=full.jobs)
    assert Worker(full.jobs, services=SimpleNamespace(billing=off)).run_once() == "failed"
    with sf(env)() as s:
        assert s.scalar(select(BillingRefund.state)) == "failed"


# =========================================================== read APIs, permissions, privacy
def test_billing_read_api_permissions_filters_and_safe_fields(env, rig):
    uid, _ = env.user("user"); _, bk = env.user("billing_admin")
    rig.paid_invoice(uid, "v1", 1500)
    rig.ev("customer_created", "c2", customer_ref="cus_v2", user_id=env.user("user")[0])
    for role in ("support_operator", "knowledge_admin", "operations_admin", "security_privacy_admin", "platform_admin", "user"):
        _, ck = env.user(role)
        for path in ("", "/invoices", "/payments", "/refunds", "/customers", "/terms", "/approvals"):
            assert env.c.get(f"{API}/admin/billing{path}", cookies=ck).status_code == 403, (role, path)
    inv = env.c.get(f"{API}/admin/billing/invoices?state=paid", cookies=bk).json()
    assert inv["total"] == 1 and inv["items"][0]["mock"] is True and inv["items"][0]["amount_due_minor"] == 1500
    assert env.c.get(f"{API}/admin/billing/invoices?state=bogus", cookies=bk).status_code == 422
    assert env.c.get(f"{API}/admin/billing/payments?status=failed", cookies=bk).json()["total"] == 0
    detail = env.c.get(f"{API}/admin/billing/invoices/{inv['items'][0]['public_id']}", cookies=bk).json()
    assert detail["payments"][0]["status"] == "succeeded"
    keys = " ".join(str(env.c.get(f"{API}/admin/billing/{p}", cookies=bk).json()) for p in ("", "invoices", "payments", "customers", "refunds")).lower()
    for banned in ("card_number", "cvv", "cvc", "expiry", "bank_account", "routing_number", "payment_method", "iban", "tax_id"):
        assert banned not in keys
    assert env.c.get(f"{API}/admin/billing/payments/{'0' * 32}", cookies=bk).status_code == 404
    assert not any(role in perm.permissions_for_role(r) for r in ("support_operator", "knowledge_admin", "operations_admin", "security_privacy_admin", "platform_admin")
                   for role in (perm.BILLING_READ, perm.BILLING_REFUND, perm.PRICE_CHANGE))
    assert {perm.BILLING_READ, perm.BILLING_REFUND, perm.PRICE_CHANGE} <= perm.permissions_for_role("billing_admin") and len(perm.PERMISSIONS) == 43


def test_command_center_shows_mock_counts_without_revenue(env, rig):
    uid, _ = env.user("user"); _, bk = env.user("billing_admin"); _, sup = env.user("support_operator")
    rig.ev("customer_created", "c", customer_ref="cus_cc", user_id=uid)
    rig.ev("invoice_opened", "i", invoice_ref="inv_cc", customer_ref="cus_cc", amount_due_minor=900, currency="EUR")
    rig.ev("payment_failed", "p", payment_ref="pay_cc", invoice_ref="inv_cc", amount_minor=900, currency="EUR", failure_category="declined")
    b = env.c.get(f"{API}/admin/home", cookies=bk).json()["billing"]
    assert b["mock"] is True and "NOT LIVE" in b["label"] and b["past_due_invoices"] == 1 and b["failed_payments"] == 1
    assert not {"mrr", "arr", "revenue", "churn", "ltv"} & set(b)
    assert "billing" not in env.c.get(f"{API}/admin/home", cookies=sup).json()


def test_export_and_account_deletion_handle_only_the_owners_mock_billing_records(env, rig):
    uid, ck = env.user("user"); other, _ = env.user("user")
    rig.paid_invoice(uid, "own", 1200)
    rig.paid_invoice(other, "oth", 3400)
    exp = env.c.get(f"{API}/auth/account/export", cookies=ck).json()["billing_mock"]
    assert exp["simulated"] is True and "MOCK" in exp["note"] and len(exp["invoices"]) == 1 and exp["invoices"][0]["amount_due_minor"] == 1200
    assert all("provider_customer_id" not in str(v) and "provider_payment_id" not in str(v) for v in exp.values())
    s = AccountDeletionService(sf(env)).delete_account(uid)
    assert s.deleted_rows.get("mock_billing_rows", 0) == 3                                                                   # customer, invoice, payment
    with sf(env)() as s2:
        assert s2.scalar(text("select count(*) from billing_customers")) == 1 and s2.scalar(text("select count(*) from billing_invoices")) == 1
        assert s2.scalar(select(BillingCustomer.user_id)) == other
        assert s2.scalar(text("select count(*) from billing_commercial_terms")) == 0                                       # shared definitions untouched


def test_no_candidate_checkout_route_no_public_webhook_and_no_card_columns():
    from src.api.main import create_app
    paths = set()
    for r in create_app().routes:
        for sub in getattr(r, "routes", [r]):
            paths.add(getattr(sub, "path", ""))
    for p in paths:
        if "billing" in p or "checkout" in p or "payment" in p or "webhook" in p or "invoice" in p:
            assert "/admin/billing" in p, p
    cols = {c.name for t in ("billing_commercial_terms", "billing_customers", "billing_provider_subscriptions", "billing_invoices", "billing_payments",
                             "billing_refunds", "billing_events", "billing_approval_requests")
            for c in __import__("src.persistence", fromlist=["Base"]).Base.metadata.tables[t].columns}
    for banned in ("card_number", "pan", "cvv", "cvc", "expiry", "card_expiry", "bank_account", "routing_number", "payment_method_secret", "raw_payload", "tax_id"):
        assert banned not in cols, banned
    assert {"payment_id", "provider_payment_id"} <= cols                                                                    # harmless fields are fine


def test_job_types_are_id_only_and_billing_code_has_no_provider_sdk():
    from src.jobs.registry import REGISTRY
    assert set(REGISTRY[P.JOB_REFUND].payload_model.model_fields) == {"refund_id"} and set(REGISTRY[P.JOB_PROCESS_EVENT].payload_model.model_fields) == {"event_id"}
    assert not REGISTRY[P.JOB_REFUND].admin_enqueue
    src = " ".join(p.read_text() for p in (ROOT / "src/billing").glob("*.py")).lower()
    for banned in ("import stripe", "adyen", "paypal", "mollie", "braintree", "requests.", "httpx", "urllib.request"):
        assert banned not in src, banned


def test_migration_0021_schema_only_constraints_and_round_trip(tmp_path, monkeypatch):
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine, inspect

    def cfg(url):
        c = Config("alembic.ini"); c.set_main_option("script_location", "migrations"); c.set_main_option("sqlalchemy.url", url)
        return c

    url = f"sqlite:///{tmp_path / 'm.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    command.upgrade(cfg(url), "0020_privacy_legal_admin")
    assert "billing_invoices" not in inspect(create_engine(url)).get_table_names()
    command.upgrade(cfg(url), "head")
    eng = create_engine(url)
    with eng.connect() as c:
        for t in ("billing_commercial_terms", "billing_customers", "billing_provider_subscriptions", "billing_invoices", "billing_payments", "billing_refunds",
                  "billing_events", "billing_approval_requests"):
            assert c.execute(text(f"select count(*) from {t}")).scalar() == 0, t                                          # no seeded price or record
    with eng.begin() as c:
        c.execute(text("insert into users(subject,provider,email,created_at,updated_at) values ('u1','dev','a@b.c','2026-01-01','2026-01-01')"))
        c.execute(text("insert into plan_versions(plan_code,version,display_name,status,created_at) values ('basic',1,'Basic','active','2026-01-01')")) \
            if c.execute(text("select count(*) from plan_versions")).scalar() == 0 else None
    pvid = eng.connect().execute(text("select id from plan_versions limit 1")).scalar()

    def bad(sql, **p):
        with pytest.raises(IntegrityError):
            with eng.begin() as c:
                c.execute(text(sql), p)
    ct = ("insert into billing_commercial_terms(public_id,plan_version_id,version,amount_minor,currency,billing_interval,trial_days,visibility,state,created_at) "
          "values (:p,:pv,:v,:a,:c,:i,:t,:vis,:s,'2026-01-01')")
    ok = dict(p="t1", pv=pvid, v=1, a=100, c="EUR", i="month", t=None, vis="public", s="active")
    with eng.begin() as c:
        c.execute(text(ct), ok)
    bad(ct, **{**ok, "p": "t2", "v": 2, "a": -1}); bad(ct, **{**ok, "p": "t3", "v": 3, "c": "eur"}); bad(ct, **{**ok, "p": "t4", "v": 4, "i": "week"})
    bad(ct, **{**ok, "p": "t5", "v": 5, "vis": "secret"}); bad(ct, **{**ok, "p": "t6", "v": 6, "s": "draft"}); bad(ct, **{**ok, "p": "t7", "v": 7, "t": 0})
    bad(ct, **{**ok, "p": "t8", "v": 8})                                                                                   # second ACTIVE terms for the plan version
    bad(ct, **{**ok, "p": "t9", "v": 1, "s": "retired"})                                                                   # duplicate version
    ar = ("insert into billing_approval_requests(public_id,action_type,target_ref,proposed_json,reason,status,requested_by_user_id,decided_by_user_id,requested_at) "
          "values (:p,:a,:t,'{}','r',:s,:rb,:db,'2026-01-01')")
    base = dict(p="a1", a="refund", t="payment:1", s="pending", rb=1, db=None)
    with eng.begin() as c:
        c.execute(text(ar), base)
    bad(ar, **{**base, "p": "a2", "t": "payment:2", "s": "approved", "db": 1})                                             # self-approval blocked by the database
    bad(ar, **{**base, "p": "a3", "t": "payment:3", "a": "coupon"}); bad(ar, **{**base, "p": "a4", "t": "payment:4", "s": "bogus"})
    bad(ar, **{**base, "p": "a5"})                                                                                         # second pending request for the same target
    cu = "insert into billing_customers(public_id,provider,provider_customer_id,user_id,workspace_id,state,created_at,updated_at) values (:p,:pr,:c,:u,:w,'active','2026-01-01','2026-01-01')"
    with eng.begin() as c:
        c.execute(text(cu), dict(p="c1", pr="mock", c="cus_1", u=1, w=None))
    bad(cu, p="c2", pr="mock", c="cus_2", u=None, w=None); bad(cu, p="c3", pr="mock", c="cus_3", u=1, w=1); bad(cu, p="c4", pr="stripe", c="cus_4", u=1, w=None)
    bad(cu, p="c5", pr="mock", c="cus_1", u=1, w=None)
    ev = "insert into billing_events(public_id,provider,provider_event_id,event_type,normalized_json,state,received_at) values (:p,'mock',:e,:t,'{}','received','2026-01-01')"
    with eng.begin() as c:
        c.execute(text(ev), dict(p="e1", e="evt_1", t="invoice_paid"))
    bad(ev, p="e2", e="evt_1", t="invoice_paid"); bad(ev, p="e3", e="evt_3", t="webhook_raw")
    command.downgrade(cfg(url), "0020_privacy_legal_admin")
    assert "billing_invoices" not in inspect(create_engine(url)).get_table_names()
    command.upgrade(cfg(url), "head")
    assert re.fullmatch(r"0021_billing_admin", (ROOT / "migrations/versions/0021_billing_admin.py").read_text().split('revision = "')[1].split('"')[0])
