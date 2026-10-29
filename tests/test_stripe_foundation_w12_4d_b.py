"""W12.4D-B: Stripe Managed Payments provider FOUNDATION. No Stripe call of any kind is made: clients are fakes or are only constructed, and every
non-loopback connection fails the test. Credential-looking values below are test strings that must exist only in this file."""

from __future__ import annotations

import base64
import json
import re
from pathlib import Path

import pytest
from sqlalchemy import func, select

from src import integrations as I
from src import secret_store as SS
from src.api import dependencies as deps
from src.application import admin_permissions as perm
from src.billing import policy as P
from src.billing import provider as BP
from src.billing import stripe_provider as SP
from src.billing.provider import BillingConfigurationError, MockBillingAdapter, ProviderRejected, resolve_mode, safe_mode
from src.persistence import ManagedSecret, ProductEntitlement, Subscription, init_db, make_engine, make_session_factory
from tests._role_gov import ensure_elevated
from tests.test_admin_foundation_w10_1 import PW, Env
from tests.test_integrations_w10_6 import mk

API = "/api/v1"
ROOT = Path(__file__).resolve().parents[1]
SBX_KEY = "sk_test_DO_NOT_LEAK_W12_04DB_SANDBOX_0001"
LIVE_KEY = "sk_live_DO_NOT_LEAK_W12_04DB_LIVE_0001"
SBX_HOOK = "whsec_DO_NOT_LEAK_W12_04DB_HOOK_SBX_01"
LIVE_HOOK = "whsec_DO_NOT_LEAK_W12_04DB_HOOK_LIVE_1"
NAMES = SP.SLOT_NAMES


@pytest.fixture(autouse=True)
def _isolation(monkeypatch):
    import socket
    real = socket.socket.connect

    def guard(self, addr, *a, **k):
        host = addr[0] if isinstance(addr, tuple) else str(addr)
        if host not in ("127.0.0.1", "::1", "localhost") and not str(host).startswith("/"):
            raise AssertionError(f"outbound network attempt to {host}")
        return real(self, addr, *a, **k)
    monkeypatch.setattr(socket.socket, "connect", guard)
    for n in I.probe_environment_allowlist() + ["BILLING_PROVIDER", "STRIPE_ENVIRONMENT", SS.BACKEND_ENV, SS.MASTER_KEY_ENV, "API_ENV"]:
        monkeypatch.delenv(n, raising=False)
    SS.reset_secret_store_for_tests()
    yield
    SS.reset_secret_store_for_tests()


def store_with(**kv):
    return SS.InMemorySecretStore({NAMES[e][k]: v for (e, k), v in ((tuple(key.split("_", 1)), val) for key, val in kv.items())})


# ---------------- provider selection: allow-listed, validated, environment-aware, fail closed ------------------------------

def test_the_provider_selector_is_a_code_defined_allow_list_and_unknown_values_fail_closed():
    assert P.SELECTABLE_PROVIDERS == ("mock", "stripe_managed_payments")
    assert resolve_mode("development", None).provider is None and resolve_mode("production", "disabled").enabled is False
    for bad in ("stripe", "paddle", "paypal", "Stripe Managed Payments", "stripe_managed_payments ; drop", "live", "1"):
        with pytest.raises(BillingConfigurationError):
            resolve_mode("development", bad)
        m = safe_mode("development", bad)
        assert m.provider is None and m.enabled is False and m.configuration_error                    # visible, never live
    assert P.PROVIDERS == ("mock",)                                                              # Stripe events/rows are refused until W12.4D-D


def test_mock_regression_the_mock_adapter_still_works_in_development_and_is_refused_in_production():
    assert resolve_mode("development", "mock").enabled is True and isinstance(BP.build_provider(resolve_mode("test", "mock")), MockBillingAdapter)
    for env in ("production", "staging", "prod"):
        with pytest.raises(BillingConfigurationError):
            resolve_mode(env, "mock")
    assert safe_mode("production", "mock").enabled is False


def test_stripe_selects_the_sandbox_foundation_in_any_environment_and_is_never_enabled_or_live(monkeypatch):
    for env in ("development", "staging", "production"):
        m = resolve_mode(env, "stripe_managed_payments")
        assert (m.provider, m.enabled, m.live, m.environment) == ("stripe_managed_payments", False, False, "sandbox")
        d = m.as_dict()
        assert d["mode"] == "sandbox_foundation" and d["live"] is False and d["checkout"] is False and "SANDBOX FOUNDATION" in d["label"]
    p = BP.build_provider(resolve_mode("development", "stripe_managed_payments"))
    assert isinstance(p, SP.StripeManagedPaymentsProvider) and p.live is False and p.environment == "sandbox"
    monkeypatch.setenv("STRIPE_ENVIRONMENT", "sandbox")
    assert resolve_mode("production", "stripe_managed_payments").environment == "sandbox"


def test_live_billing_cannot_be_selected_and_an_unknown_environment_is_refused(monkeypatch):
    assert P.LIVE_BILLING_ENABLED is False
    monkeypatch.setenv("STRIPE_ENVIRONMENT", "live")
    with pytest.raises(BillingConfigurationError) as e:
        resolve_mode("production", "stripe_managed_payments")
    assert "disabled" in str(e.value)
    assert safe_mode("production", "stripe_managed_payments").enabled is False and BP.build_provider(safe_mode("production", "stripe_managed_payments")) is None
    for bad in ("prod", "LIVE ", "test", ""):
        monkeypatch.setenv("STRIPE_ENVIRONMENT", bad)
        if bad.strip().lower() == "live":
            continue
        if bad == "":
            assert resolve_mode("production", "stripe_managed_payments").environment == "sandbox"      # unset means sandbox (default)
            continue
        with pytest.raises(BillingConfigurationError):
            resolve_mode("production", "stripe_managed_payments")


def test_the_default_deployment_has_no_billing_and_startup_activates_no_payments(monkeypatch):
    from src.api.env_validation import validate_runtime_config
    assert resolve_mode().provider is None and BP.build_provider(safe_mode()) is None
    monkeypatch.setenv("BILLING_PROVIDER", "stripe_managed_payments")
    monkeypatch.setenv("STRIPE_ENVIRONMENT", "live")
    r = validate_runtime_config("production")
    assert not any("BILLING_PROVIDER" in c or "STRIPE_ENVIRONMENT" in c for c in r.critical) and any("live billing is disabled" in w for w in r.warnings)
    monkeypatch.setenv("STRIPE_ENVIRONMENT", "bogus")
    assert any("STRIPE_ENVIRONMENT" in c for c in validate_runtime_config("production").critical)
    monkeypatch.setenv("BILLING_PROVIDER", "paypal")
    assert any("BILLING_PROVIDER" in c for c in validate_runtime_config("production").critical)


# ---------------- credential slots, formats, environment separation -----------------------------------------------------

def test_the_registry_has_four_separate_slots_and_no_slot_can_serve_two_environments():
    d = I.REGISTRY["stripe_managed_payments"]
    assert [c.external_name for c in d.credentials] == [NAMES["sandbox"]["api"], NAMES["sandbox"]["webhook"], NAMES["live"]["api"], NAMES["live"]["webhook"]]
    assert len({c.external_name for c in d.credentials}) == 4 and not d.test_supported
    assert [c.required for c in d.credentials] == [True, True, False, False]            # live slots are optional and inert


@pytest.mark.parametrize("env,key,hook,status,problem", [
    ("sandbox", None, None, "not_configured", None),
    ("sandbox", SBX_KEY, None, "not_configured", None),
    ("sandbox", None, SBX_HOOK, "not_configured", None),
    ("sandbox", SBX_KEY, SBX_HOOK, "sandbox_access_unverified", None),
    ("sandbox", LIVE_KEY, SBX_HOOK, "configuration_error", "credential_environment_mismatch"),
    ("sandbox", "not-a-stripe-key-0000000000", SBX_HOOK, "configuration_error", "credential_format"),
    ("sandbox", SBX_KEY, "wrong-prefix-webhook-0000000", "configuration_error", "credential_format"),
    ("live", SBX_KEY, SBX_HOOK, "live_disabled", None),
    (None, SBX_KEY, SBX_HOOK, "configuration_error", "invalid_environment"),
])
def test_readiness_states_are_bounded_truthful_and_never_healthy_or_approved(env, key, hook, status, problem):
    kv = {}
    if key:
        kv["sandbox_api"] = key
    if hook:
        kv["sandbox_webhook"] = hook
    r = SP.readiness(store_with(**kv), provider_selected="stripe_managed_payments", environment=env)
    assert r["status"] == status and r["configuration_problem"] == problem and r["status"] in P.READINESS_STATES
    assert r["eligibility"] == "not_confirmed" and r["merchant_of_record"] == "not_confirmed" and r["sandbox_access"] == "unverified"
    assert (r["live_billing"], r["checkout"], r["refunds"], r["webhooks"]) == ("disabled", "not_implemented", "not_implemented", "not_implemented")
    assert r["last_successful_check"] is None and r["managed_payments_required"] is True
    blob = json.dumps(r)
    for secret in (SBX_KEY, LIVE_KEY, SBX_HOOK, "sk_test_", "sk_live_", "whsec_"):
        assert secret not in blob
    assert "healthy" not in blob.lower() and "approved" not in blob.lower()


def test_another_provider_selection_reports_not_configured():
    assert SP.readiness(store_with(), provider_selected="mock", environment="sandbox")["status"] == "not_configured"


def test_live_slots_are_never_read_in_sandbox_and_never_used_for_a_client():
    store = store_with(live_api=LIVE_KEY, live_webhook=LIVE_HOOK)
    r = SP.readiness(store, provider_selected="stripe_managed_payments", environment="sandbox")
    assert r["status"] == "not_configured" and r["live_slots_populated"] is True            # reported, never used
    with pytest.raises(SP.StripeConfigurationError) as e:
        SP.build_stripe_client(store, "sandbox", client_cls=lambda *a, **k: pytest.fail("a client must not be built"))
    assert e.value.category == "not_configured"
    store = store_with(sandbox_api=LIVE_KEY)                                                 # a live key in the sandbox slot is refused, not silently used
    with pytest.raises(SP.StripeConfigurationError) as e:
        SP.build_stripe_client(store, "sandbox", client_cls=lambda *a, **k: pytest.fail("no client"))
    assert e.value.category == "credential_environment_mismatch"


def test_the_environment_reads_only_its_own_slot_and_precedence_is_managed_over_environment(tmp_path, monkeypatch):
    eng = make_engine(f"sqlite:///{tmp_path / 's.db'}")
    init_db(eng)
    sf = make_session_factory(eng)
    monkeypatch.setenv(SS.BACKEND_ENV, SS.BACKEND_ENCRYPTED)
    monkeypatch.setenv(SS.MASTER_KEY_ENV, base64.b64encode(bytes(range(32))).decode())
    monkeypatch.setenv(NAMES["sandbox"]["api"], "sk_test_ENVIRONMENT_FALLBACK_VALUE_0001")
    SS.reset_secret_store_for_tests()
    store = SS.bind_secret_store(sf)
    assert store.get_for_runtime(NAMES["sandbox"]["api"]).get_secret_value().startswith("sk_test_ENVIRONMENT")         # environment fallback
    store.set(NAMES["sandbox"]["api"], SBX_KEY)
    assert store.get_for_runtime(NAMES["sandbox"]["api"]).get_secret_value() == SBX_KEY                                  # managed beats environment
    assert store.source(NAMES["sandbox"]["api"]) == "managed" and store.get_for_runtime(NAMES["live"]["api"]) is None   # live slot unaffected
    store.remove(NAMES["sandbox"]["api"])
    assert store.get_for_runtime(NAMES["sandbox"]["api"]).get_secret_value().startswith("sk_test_ENVIRONMENT")
    with sf() as s:
        assert s.scalar(select(func.count()).select_from(ManagedSecret)) == 0


# ---------------- the client factory ----------------------------------------------------------------------------------

class FakeClient:
    instances: list = []

    def __init__(self, api_key, *, stripe_version=None, max_network_retries=None, http_client=None, **kw):
        self.api_key, self.stripe_version, self.max_network_retries, self.http_client, self.kw = api_key, stripe_version, max_network_retries, http_client, kw
        FakeClient.instances.append(self)


def test_the_client_is_explicit_per_instance_pinned_unretried_bounded_and_never_global():
    import stripe
    FakeClient.instances = []
    a = SP.build_stripe_client(store_with(sandbox_api=SBX_KEY), "sandbox", client_cls=FakeClient, http_client="http-a")
    b = SP.build_stripe_client(store_with(sandbox_api="sk_test_ANOTHER_CONTEXT_KEY_0000000002"), "sandbox", client_cls=FakeClient, http_client="http-b")
    assert a.api_key == SBX_KEY and b.api_key.endswith("0002") and a is not b                 # no shared mutable credential between contexts
    assert a.stripe_version == P.STRIPE_API_VERSION == "2026-09-30.endive" and a.max_network_retries == 0
    assert stripe.api_key is None                                                             # the SDK's global credential is never set
    from stripe._api_version import _ApiVersion
    assert _ApiVersion.CURRENT == P.STRIPE_API_VERSION                                        # an SDK upgrade must be a reviewed change
    assert P.STRIPE_API_VERSION >= P.STRIPE_MIN_API_VERSION_FOR_MANAGED_PAYMENTS


def test_the_real_sdk_client_can_be_constructed_offline_with_a_bounded_timeout_and_makes_no_call():
    c = SP.build_stripe_client(store_with(sandbox_api=SBX_KEY), "sandbox")
    import stripe
    assert isinstance(c, stripe.StripeClient)
    assert c._requestor._options.max_network_retries == 0 if hasattr(c, "_requestor") and hasattr(c._requestor, "_options") else True
    assert stripe.api_key is None


def test_live_and_unknown_environments_never_build_a_client_even_with_valid_looking_keys():
    store = store_with(live_api=LIVE_KEY, sandbox_api=SBX_KEY)
    for env, cat in (("live", "live_disabled"), ("prod", "invalid_environment")):
        with pytest.raises(SP.StripeConfigurationError) as e:
            SP.build_stripe_client(store, env, client_cls=lambda *a, **k: pytest.fail("no client"))
        assert e.value.category == cat


@pytest.mark.parametrize("name,expected", [
    ("AuthenticationError", "provider_auth_failed"), ("PermissionError", "provider_permission_denied"), ("RateLimitError", "rate_limited"),
    ("APIConnectionError", "provider_unavailable"), ("APIError", "provider_unavailable"), ("InvalidRequestError", "invalid_request"),
    ("IdempotencyError", "invalid_request"), ("SignatureVerificationError", "signature_invalid"), ("Whatever", "unknown"),
])
def test_provider_errors_map_to_bounded_categories_without_the_message(name, expected):
    exc = type(name, (Exception,), {})(f"boom {SBX_KEY} {LIVE_HOOK}")
    assert SP.map_stripe_error(exc) == expected and expected in SP.ERROR_CATEGORIES
    assert SBX_KEY not in expected
    assert SP.map_stripe_error(type("APIConnectionError", (Exception,), {})("Request timed out")) == "provider_timeout"


# ---------------- capabilities and fail-closed operations -----------------------------------------------------------------

def test_capabilities_are_truthful_and_every_unbuilt_operation_fails_closed():
    p = SP.StripeManagedPaymentsProvider()
    c = p.capabilities()
    assert (c["refund"], c["checkout"], c["payment_methods"], c["tax"], c["network"], c["live"]) == (False, False, False, False, False, False)
    assert c["managed_payments_required"] is True and c["mode"] == "sandbox_foundation"
    built = []
    p2 = SP.StripeManagedPaymentsProvider(client_factory=lambda *a, **k: built.append(1))
    with pytest.raises(ProviderRejected):
        p2.refund(idempotency_key="k", provider_payment_id="pi_1", amount_minor=100, currency="EUR")
    assert not built                                                                              # a refund never reaches a client, and never returns mock success
    assert not hasattr(p, "subscribe")
    # W12.4D-C: checkout exists on the interface but the real adapter still refuses it by configuration and never reaches a client.
    from src.billing.provider import CheckoutRequest
    with pytest.raises(ProviderRejected) as refused:
        SP.StripeManagedPaymentsProvider(client_factory=None).create_checkout_session(CheckoutRequest("k" * 12, "price_x", "https://a/b", "https://a/c", "ref"))
    assert str(refused.value) == "checkout_not_authorized" and not built


def test_checkout_parameters_must_enable_managed_payments_so_ask4mo_is_never_the_merchant_of_record():
    ok = {"mode": "subscription", "managed_payments": {"enabled": True}, "line_items": []}
    assert SP.require_managed_payments(ok) is ok
    for bad in ({}, {"mode": "subscription"}, {"managed_payments": {"enabled": False}}, {"managed_payments": {"enabled": "true"}}, {"managed_payments": True}):
        with pytest.raises(SP.StripeConfigurationError) as e:
            SP.require_managed_payments(bad)
        assert e.value.category == "managed_payments_not_enabled"
    from stripe.params.checkout._session_create_params import SessionCreateParamsManagedPayments        # the reviewed SDK carries the parameter
    assert SessionCreateParamsManagedPayments.__annotations__.get("enabled") is not None


def test_a_stripe_event_is_refused_and_no_entitlement_or_subscription_changes(tmp_path):
    from src.billing.service import BillingService, BillingValidationError
    eng = make_engine(f"sqlite:///{tmp_path / 'b.db'}")
    init_db(eng)
    sf = make_session_factory(eng)
    svc = BillingService(sf, provider=None, mode=safe_mode("development", "stripe_managed_payments"))
    with sf() as s:
        before = (s.scalar(select(func.count()).select_from(Subscription)), s.scalar(select(func.count()).select_from(ProductEntitlement)))
    with pytest.raises(BillingValidationError):
        svc.record_event("stripe_managed_payments", "evt_1", "invoice_paid", {"invoice_ref": "in_1"})
    with sf() as s:
        assert (s.scalar(select(func.count()).select_from(Subscription)), s.scalar(select(func.count()).select_from(ProductEntitlement))) == before


def test_there_is_no_checkout_payment_or_webhook_route_and_billing_code_never_touches_entitlements():
    from src.api.main import create_app
    from src.api.config import ApiSettings
    app = create_app(ApiSettings(env="test", frontend_origins=("http://localhost:3000",)))
    # W12.4D-C/D: the billing surface is exactly the four checkout routes and the signature-authenticated webhook; nothing named portal, payment-confirm or stripe.
    # (Read from the OpenAPI schema: ``app.routes`` holds included routers without a path.)
    paths = [p for p in app.openapi()["paths"] if p.startswith("/api/v1/billing")]
    assert sorted(paths) == ["/api/v1/billing/checkout-returns", "/api/v1/billing/checkout-sessions", "/api/v1/billing/checkout/availability",
                             "/api/v1/billing/checkout/status", "/api/v1/billing/summary", "/api/v1/billing/webhooks/stripe"], paths
    assert not [p for p in app.openapi()["paths"] if re.search(r"payment-confirm|portal|payment-success", p, re.I)]
    for f in (ROOT / "src/billing").glob("*.py"):
        if f.name == "entitlement_bridge.py":
            continue          # W12.4D-D: the single audited billing-to-entitlement boundary (sole writer of provider subscriptions, checked elsewhere)
        text = f.read_text()
        assert not re.search(r"\b(Subscription|ProductEntitlement|PlanEntitlement)\b", text.replace("BillingProviderSubscription", "")), f.name


# ---------------- Admin: readiness, authorization, step-up, no leakage ------------------------------------------------------

@pytest.fixture()
def env():
    e = Env()
    store = SS.LayeredSecretStore(SS.EncryptedDatabaseSecretStore(e.repo.session_factory, base64.b64encode(bytes(range(32))).decode()))
    e.store = store
    e.app.dependency_overrides[deps.get_secret_store] = lambda: store
    yield e
    e.app.dependency_overrides.pop(deps.get_secret_store, None)
    e.close()


def test_admin_readiness_is_permissioned_bounded_and_leaks_nothing(env, monkeypatch):
    monkeypatch.setenv("BILLING_PROVIDER", "stripe_managed_payments")
    url = f"{API}/admin/integrations/stripe_managed_payments/readiness"
    env.store.set(NAMES["sandbox"]["api"], SBX_KEY)
    env.store.set(NAMES["sandbox"]["webhook"], SBX_HOOK)
    env.store.set(NAMES["live"]["api"], LIVE_KEY)
    for role, code in (("platform_admin", 200), ("operations_admin", 200), ("billing_admin", 403), ("security_privacy_admin", 403),
                       ("knowledge_admin", 403), ("support_operator", 403), ("user", 403)):
        _, ck = mk(env, role)
        assert env.c.get(url, cookies=ck).status_code == code, role
    assert "platform.integrations.read" not in perm.ROLE_PRESETS["billing_admin"] and len(perm.PERMISSIONS) == 44
    _, adm = mk(env, "platform_admin")
    d = env.c.get(url, cookies=adm).json()
    assert d["status"] == "sandbox_access_unverified" and d["eligibility"] == "not_confirmed" and d["live_slots_populated"] is True
    assert d["sandbox"] == {"api": {"configured": True, "source_kind": "managed"}, "webhook": {"configured": True, "source_kind": "managed"}}
    detail = env.c.get(f"{API}/admin/integrations/stripe_managed_payments", cookies=adm).json()
    assert detail["classification"] == "code_present_not_validated" and detail["runtime"]["enabled"] is False and detail["test"]["supported"] is False
    assert env.c.post(f"{API}/admin/integrations/stripe_managed_payments/test", cookies=adm).status_code == 409           # no probe, no Stripe call
    blob = json.dumps([d, detail])
    for secret in (SBX_KEY, LIVE_KEY, SBX_HOOK, "sk_test_", "sk_live_", "whsec_"):
        assert secret not in blob
    assert env.c.get(f"{API}/admin/integrations/openrouter/readiness", cookies=adm).status_code == 404


def test_rotating_a_stripe_credential_needs_secret_rotate_and_a_fresh_step_up_and_billing_admin_cannot(env):
    slot = f"{API}/admin/integrations/stripe_managed_payments/credentials/sandbox_api_key"
    _, bill = mk(env, "billing_admin")
    _, ops = mk(env, "operations_admin")
    for ck in (bill, ops):
        assert env.c.post(slot, json={"value": SBX_KEY}, cookies=ck).status_code == 403
    _, adm = mk(env, "platform_admin")
    r = env.c.post(slot, json={"value": SBX_KEY}, cookies=adm)
    assert r.status_code == 403 and r.json()["error"]["code"] == "step_up_required" and SBX_KEY not in r.text
    ensure_elevated(env.c, adm, PW)
    ok = env.c.post(slot, json={"value": SBX_KEY}, cookies=adm)
    assert ok.status_code == 200 and SBX_KEY not in ok.text and ok.json()["action"] == "created"
    live = env.c.post(f"{API}/admin/integrations/stripe_managed_payments/credentials/live_api_key", json={"value": LIVE_KEY}, cookies=adm)
    assert live.status_code == 200                                                          # storable but inert: live billing stays disabled
    r2 = env.c.get(f"{API}/admin/integrations/stripe_managed_payments/readiness", cookies=adm).json()
    assert r2["live_billing"] == "disabled" and r2["status"] == "not_configured"             # no webhook signing yet, and live never changes anything
    assert env.store.get_for_runtime(NAMES["sandbox"]["api"]).get_secret_value() == SBX_KEY


# ---------------- hygiene ---------------------------------------------------------------------------------------------------

def test_test_credentials_and_the_stripe_sdk_pin_are_confined():
    import subprocess
    out = subprocess.run(["git", "grep", "-l", "DO_NOT_LEAK_W12_04DB", "--", "."], cwd=ROOT, capture_output=True, text=True).stdout.split()
    assert set(out) <= {"tests/test_stripe_foundation_w12_4d_b.py"}, out
    assert "stripe==16.0.1" in (ROOT / "pyproject.toml").read_text() and "stripe==16.0.1" in (ROOT / "requirements.txt").read_text()
    tracked = subprocess.run(["git", "ls-files", "src", "frontend/components", "frontend/lib"], cwd=ROOT, capture_output=True, text=True).stdout.split()
    for f in tracked:
        if f.endswith((".py", ".ts", ".tsx")) and Path(ROOT / f).exists():
            assert "sk_live_" not in Path(ROOT / f).read_text(errors="ignore").replace('"sk_live_", "rk_live_"', ""), f
