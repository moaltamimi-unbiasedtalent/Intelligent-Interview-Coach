"""W12.4D-P5-B: the four baseline evaluators that failed before this wave were REMEDIATED (stale literal expectations replaced by behavioural/structural invariants), not
weakened. Each invariant is pinned here with a NEGATIVE regression: the same helper must still FAIL on a genuine defect. Evaluator thresholds and safety sets are untouched."""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load(name):
    spec = importlib.util.spec_from_file_location(f"eval_{name}_under_test", ROOT / f"scripts/eval_{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ROUTE = (ROOT / "src/api/routes/company.py").read_text()
PRICING = (ROOT / "frontend/lib/pricing.ts").read_text()


# ------------------------------------------------------------------ eval_company_intelligence
def test_the_company_endpoint_gating_invariant_passes_today_and_fails_when_a_guard_is_removed_or_wrong():
    m = _load("company_intelligence")
    assert m.endpoint_is_gated(ROUTE)[0] is True
    for needle in ("_principal=Depends(require_entitlement(Capability.CURRENT_MARKET_RESEARCH)),", '_pause=Depends(require_not_paused("current_market")),', '_cost=Depends(cost_limit("cost_research_user")),'):
        assert needle in ROUTE
        assert m.endpoint_is_gated(ROUTE.replace(needle, ""))[0] is False                       # each guard is individually required
    assert m.endpoint_is_gated(ROUTE.replace("Capability.CURRENT_MARKET_RESEARCH", "Capability.AGENT"))[0] is False      # the WRONG capability does not satisfy it
    assert m.endpoint_is_gated(ROUTE.replace('"current_market"', '"agent"'))[0] is False
    assert m.endpoint_is_gated("def company_intelligence(:")[0] is False
    assert m.endpoint_is_gated(ROUTE.replace("def company_intelligence", "def something_else"))[0] is False            # the guards must be on THE endpoint
    assert m.endpoint_is_gated(ROUTE.replace("require_entitlement(", "require_capability("))[0] is True              # the former guard name is still accepted


# ------------------------------------------------------------------ eval_marketing_product_trust
def test_the_positioning_contrast_invariant_passes_today_and_fails_without_a_contrast():
    m = _load("marketing_product_trust")
    en = (ROOT / "frontend/lib/i18n/messages/en.ts").read_text()
    assert m.why_section_contrasts_with_one_off_preparation(en) is True
    flat = 'whyTitle: "Why Ask4Mo", why1Title: "Built around your job", why1Body: "Preparation is organised per Opportunity.", why2Title: "x", why5Title: "y"'
    assert m.why_section_contrasts_with_one_off_preparation(flat) is False
    assert m.why_section_contrasts_with_one_off_preparation('whyTitle: "t", why1Body: "We beat generic tools", why5Title: "y"') is False          # a contrast word is required too


@pytest.mark.parametrize("mutate", [lambda t: t.replace('ctaKind: "unavailable"', 'ctaKind: "request"'), lambda t: t.replace("purchasable: false,\n  },\n];", "purchasable: true,\n  },\n];"),
                                    lambda t: t.replace("ctaHref: null", 'ctaHref: "/checkout"'), lambda t: t.replace("BILLING_ENABLED = false", "BILLING_ENABLED = true")])
def test_the_premium_not_purchasable_invariant_passes_today_and_fails_on_any_purchase_path(mutate):
    for name in ("marketing_product_trust", "release_candidate"):
        m = _load(name)
        fn = getattr(m, "premium_is_not_purchasable", None) or m.premium_is_presentation_only
        assert fn(PRICING) is True
        assert fn(mutate(PRICING)) is False


def test_the_frontend_billing_invariant_flags_payment_collection_but_not_admin_labels_or_the_redirect_allow_list():
    m = _load("marketing_product_trust")
    real = {p.name: p.read_text(encoding="utf-8", errors="ignore") for p in (ROOT / "frontend").rglob("*.ts*")
            if not any(x in str(p) for x in ("node_modules", "/.next/", ".spec.ts", ".test.ts"))}
    assert m.frontend_billing_violations(real) == []
    assert m.frontend_billing_violations({"BillingView.tsx": "label = 'Stripe Managed Payments (sandbox)'", "trustedRedirect.ts": "const HOSTS = ['checkout.stripe.com']"}) == []
    for bad in ("import { loadStripe } from '@stripe/stripe-js'", '<script src="https://js.stripe.com/v3/">', '<input autoComplete="cc-number" />', "const card number = 4242", "createCheckout(plan)"):
        assert m.frontend_billing_violations({"Bad.tsx": bad}) == ["Bad.tsx"], bad


# ------------------------------------------------------------------ eval_opportunity_journey
def test_the_opportunity_migration_invariant_passes_today_and_fails_on_a_destructive_change():
    m = _load("opportunity_journey")
    mig = (ROOT / "migrations/versions/0014_opportunities.py").read_text()
    later = [p.read_text() for p in sorted((ROOT / "migrations/versions").glob("0*.py")) if p.name > "0014_opportunities.py"]
    assert m.migration_is_additive(mig, later)[0] is True
    bad_up = mig.replace("def upgrade() -> None:", 'def upgrade() -> None:\n    op.drop_table("legacy")', 1)
    assert m.migration_is_additive(bad_up, later)[0] is False
    for destructive in ('def upgrade():\n    op.drop_table("opportunities")\n\ndef downgrade():\n    pass', 'def upgrade():\n    op.drop_column("opportunities", "notes")\n\ndef downgrade():\n    pass',
                        'def upgrade():\n    op.rename_table("opportunities", "jobs")\n\ndef downgrade():\n    pass'):
        assert m.migration_is_additive(mig, later + [destructive])[0] is False
    assert m.migration_is_additive(mig, later + ['def upgrade():\n    pass\n\ndef downgrade():\n    op.drop_table("opportunities")'])[0] is True     # a DOWNGRADE may drop it
    assert m.migration_is_additive("", later)[0] is False


# ------------------------------------------------------------------ the evaluators themselves
@pytest.mark.parametrize("name", ["company_intelligence", "marketing_product_trust", "opportunity_journey", "release_candidate"])
def test_every_check_of_the_remediated_evaluators_passes_and_their_safety_sets_are_intact(name):
    m = _load(name)
    results = m.run()
    assert all(ok for ok, _ in results.values()), {k: v for k, v in results.items() if not v[0]}
    assert m.SAFETY <= set(results)                                                             # no safety check was removed from the evaluator
    assert len(results) >= {"company_intelligence": 24, "marketing_product_trust": 32, "opportunity_journey": 32, "release_candidate": 27}[name]


def test_the_plan_entitlement_limit_invariant_accepts_the_portable_boolean_form_and_still_rejects_a_weaker_constraint():
    """eval_admin_entitlements pinned the PostgreSQL-incompatible literal ``enabled = 1``; the portable form carries the same invariant (limit >= 1 and enabled)."""
    pat = re.compile(r"limit_value IS NULL OR \(limit_value >= 1 AND enabled(?: = 1)?\)")
    assert pat.search("limit_value IS NULL OR (limit_value >= 1 AND enabled)") and pat.search("limit_value IS NULL OR (limit_value >= 1 AND enabled = 1)")
    assert not pat.search("limit_value IS NULL OR (limit_value >= 0 AND enabled)") and not pat.search("limit_value IS NULL OR (limit_value >= 1)")
    for rel in ("migrations/versions/0016_plans_entitlements.py", "src/persistence.py"):
        assert pat.search((ROOT / rel).read_text())
