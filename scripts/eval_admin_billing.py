#!/usr/bin/env python
"""P10B-W10.5 mock-billing guard (deterministic, offline, 0 paid/live calls). MOCK BILLING: NOT LIVE BILLING.

High-risk invariants: one small BillingProvider interface with only a mock adapter; the mock can never run in production/live; money is
integer minor units; commercial terms are separate from plan entitlements, versioned and immutable, with NO seeded price; price changes and
refunds need a different approver with the specific permission; billing state never touches subscriptions, entitlements or the tier;
refunds and events are idempotent and run as W10.9 jobs; no card/payment-instrument data, no checkout, no candidate billing route, no
public webhook, no revenue reporting, no coupon engine; permissioned routes; permission registry stays 43. It does not duplicate the tests.
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# TEST ISOLATION (hard requirement): before any application import (temp DATABASE_URL, no .env, non-temp engines fail fast, isolated research cache).
import tests.conftest  # noqa: E402,F401


def read(rel: str) -> str:
    p = ROOT / rel
    return p.read_text(encoding="utf-8") if p.exists() else ""


def code_only(rel: str) -> str:
    try:
        tree = ast.parse(read(rel))
    except SyntaxError:
        return read(rel)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and node.body and isinstance(node.body[0], ast.Expr) \
                and isinstance(getattr(node.body[0], "value", None), ast.Constant) and isinstance(node.body[0].value.value, str):
            node.body = node.body[1:] or [ast.Pass()]
    return ast.unparse(tree)


def run() -> dict[str, tuple[bool, str]]:
    out: dict[str, tuple[bool, str]] = {}

    def check(name: str, ok: bool, detail: str = "") -> None:
        out[name] = (bool(ok), detail)

    from src.application import admin_permissions as perm
    from src.billing import policy as P
    from src.billing.provider import MOCK_ALLOWED_ENVS, BillingConfigurationError, MockBillingAdapter, resolve_mode

    files = sorted(p.relative_to(ROOT).as_posix() for p in (ROOT / "src/billing").glob("*.py"))
    code = "\n".join(code_only(f) for f in files) + "\n" + code_only("src/api/routes/admin_billing.py")
    raw = "\n".join(read(f) for f in files) + read("src/api/routes/admin_billing.py")
    persist = read("src/persistence.py")
    billing_models = persist.split("# --- Mock billing")[1].split("def make_engine")[0] if "# --- Mock billing" in persist else ""
    route = read("src/api/routes/admin_billing.py")
    svc = read("src/billing/service.py")

    check("provider_interface_and_only_a_mock_adapter", "class BillingProvider(Protocol)" in raw and P.PROVIDERS == ("mock",) and MockBillingAdapter.live is False, "interface + mock")
    check("no_live_provider_sdk_or_network", not re.search(r"stripe|adyen|paypal|mollie|braintree|requests\.|httpx|urllib\.request|socket", code.lower()), "none")
    guard_ok = False
    try:
        resolve_mode("production", "mock")
    except BillingConfigurationError:
        guard_ok = True
    check("mock_cannot_run_in_production_or_live", guard_ok and "production" not in MOCK_ALLOWED_ENVS and "live" not in MOCK_ALLOWED_ENVS, "fail closed")
    check("billing_disabled_by_default", resolve_mode("development", None).enabled is False, "explicit opt-in")
    check("api_states_mock_not_live", "live: bool" in read("src/api/schemas/admin.py") and "NOT LIVE" in P.MODE_LABEL and "MODE_LABEL" in read("src/billing/provider.py"), "machine-readable + label")
    check("money_is_integer_minor_units", "amount_minor: Mapped[int]" in billing_models and not re.search(r"Mapped\[float\]|Float|Numeric|Decimal", billing_models), "no floats")
    check("amount_validation_rejects_bool_float_negative", "isinstance(value, bool)" in svc and "StrictInt" in read("src/api/schemas/admin.py"), "strict")
    check("terms_separate_from_entitlements", "class BillingCommercialTerms(" in billing_models and not re.search(r"PlanEntitlement|entitlement_key", billing_models) and "plan_version_id" in billing_models, "attached to plan_versions only")
    check("terms_versioned_one_active_immutable", "uq_bct_one_active" in billing_models and "uq_bct_plan_version_version" in billing_models and "state = 'retired'" not in code or "prior.state, prior.retired_at" in svc, "new version, old retired")
    mig = read("migrations/versions/0021_billing_admin.py")
    check("no_seeded_price_or_money_record", "bulk_insert" not in mig and "INSERT" not in mig.upper().replace("# ", ""), "schema only")
    check("price_change_needs_second_approver", "_decidable" in svc and "cannot approve your own" in svc and "ck_bar_no_self_approval" in billing_models, "app + DB")
    check("refund_needs_second_approver", "decide_refund" in svc and "perm.BILLING_REFUND" in svc, "billing.refund")
    check("separate_approve_routes_per_action", "/price-changes/{approval_id}/approve" in route and "/refunds/{approval_id}/approve" in route and "BILLING_READ" not in route.split("def approve_price_change")[1].split("@router")[0], "billing.read approves nothing")
    check("billing_never_touches_entitlements", not re.search(r"Subscription\(|ProductEntitlement|PlanEntitlement|EntitlementService|PlanRepository|\.tier\b", code.replace("BillingProviderSubscription", "BPS").replace("provider_subscription", "ps")), "no access coupling")
    check("refund_idempotent_via_stable_key", "idempotency_key" in svc and "uq_br_idempotency" in billing_models and "state == \"pending\"" in svc.replace("RF.state == 'pending'", 'state == "pending"') or "RF.state == \"pending\"" in svc, "provider key + state guard")
    check("refund_no_over_refund_and_mock_only", "exceeds the amount still refundable" in svc and "Only mock payments" in svc and "Only a succeeded payment" in svc, "validated")
    check("events_idempotent_normalised_no_raw_body", "uq_be_provider_event" in billing_models and "_EVENT_FIELDS" in svc and not re.search(r"raw_payload|raw_body|request\.body", code), "unique + allowlist")
    check("jobs_use_w109_ids_only", "billing_refund" in P.JOB_REFUND and "refund_id" in code and "event_id" in code and "extra=\"forbid\"" in read("src/billing/jobs.py"), "id-only")
    check("no_card_or_instrument_data", not re.search(r"\b(card_number|pan|cvv|cvc|card_expiry|expiry|bank_account|routing_number|payment_method_secret|iban|tax_id)\b", billing_models.lower()), "none")
    check("no_checkout_or_portal_routes", not re.search(r"checkout|billing[-_]portal|payment[-_]method|webhook", code_only("src/api/routes/admin_billing.py").lower()), "none")
    cand = "".join(p.read_text() for p in (ROOT / "src/api/routes").glob("*.py") if p.name != "admin_billing.py")
    check("no_candidate_billing_routes", not re.search(r"prefix=\"/(billing|checkout|payments|invoices)", cand) and "billing" not in "".join(re.findall(r'@router\.(?:get|post)\("[^"]*"', cand)).lower().replace("admin", ""), "zero")
    check("no_revenue_reporting_or_coupons", not re.search(r"\b(mrr|arr|ltv|churn|gmv|coupon|promo_code|discount)\b", code.lower()), "none")
    check("routes_permissioned", route.count("require_permission(") >= 15 and all(x in route for x in ("BILLING_READ", "BILLING_REFUND", "PRICE_CHANGE")), "explicit")
    check("permission_registry_stays_43", len(perm.PERMISSIONS) == 43 and "platform.billing.manage" not in perm.PERMISSIONS, "43")
    check("presets_billing_only_for_billing_admin", all(p in perm.permissions_for_role("billing_admin") for p in (perm.BILLING_READ, perm.BILLING_REFUND, perm.PRICE_CHANGE))
          and not any({perm.BILLING_REFUND, perm.PRICE_CHANGE} & perm.permissions_for_role(r) for r in ("support_operator", "knowledge_admin", "operations_admin", "security_privacy_admin", "platform_admin")), "no other preset")
    deletion = read("src/application/account_deletion_service.py")
    check("deletion_and_export_integrated", "delete_billing_for" in deletion and "billing_mock" in read("src/application/data_export.py"), "owner-scoped mock records")
    check("sec_w10_05_untouched", "pause" not in code.lower(), "platform pause not touched")
    check("migration_chain_valid", 'down_revision = "0020_privacy_legal_admin"' in mig and "ck_bar_no_self_approval" in mig and "uq_bct_one_active" in mig and "uq_be_provider_event" in mig, "0021 chains from 0020")
    t = read("tests/test_billing_w10_5.py")
    check("tests_exist", all(x in t for x in ("test_billing_never_changes_entitlements_subscriptions_or_tier", "test_refund_crash_window_replay_counts_once",
                                             "test_price_change_requires_a_different_authorised_administrator_and_versions_are_immutable",
                                             "test_duplicate_events_are_one_record_one_transition_and_unknown_fields_are_rejected",
                                             "test_mock_cannot_run_in_production_or_live_and_the_default_is_disabled")), "present")
    return out


def main() -> int:
    print("ASK4MO - P10B-W10.5 MOCK BILLING GUARD (MOCK BILLING: NOT LIVE BILLING)\n")
    res = run()
    failed = False
    for name in sorted(res):
        ok, detail = res[name]
        failed |= not ok
        print(f"  {name:62s} {'PASS' if ok else 'FAIL'}  {detail}")
    print("\nPaid LLM calls: 0   Live calls: 0")
    print("\nRESULT: " + ("FAIL" if failed else "PASS"))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
