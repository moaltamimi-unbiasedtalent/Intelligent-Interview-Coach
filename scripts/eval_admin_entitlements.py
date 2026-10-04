#!/usr/bin/env python
"""P10B-W10.4 entitlement guard (deterministic, offline, 0 paid/live calls).

High-risk invariants of the plan / subscription / entitlement layer: a code-defined registry, no invented quota
or product or price, no billing implementation, product access decided by the entitlement resolver (not by
scattered tier comparisons), subscription subject integrity, immutable active plans, no candidate mutation and
permissioned Admin routes. It does not duplicate the test suite.
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

BILLING_WORDS = re.compile(r"stripe|checkout|invoice|payment_method|currency|webhook|billing_provider|price_id|\bprice\b|\bamount\b|credit_card", re.I)
LOCALES = ("en", "de", "fr", "es", "it", "pt", "nl", "ru")


def read(rel: str) -> str:
    p = ROOT / rel
    return p.read_text(encoding="utf-8") if p.exists() else ""


def code_only(src: str) -> str:
    """Python source without comments and docstrings (so prose that says 'no price' is not a violation)."""
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return src
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module)) and node.body \
                and isinstance(node.body[0], ast.Expr) and isinstance(getattr(node.body[0], "value", None), ast.Constant) \
                and isinstance(node.body[0].value.value, str):
            node.body = node.body[1:] or [ast.Pass()]
    return ast.unparse(tree)


def run() -> dict[str, tuple[bool, str]]:
    out: dict[str, tuple[bool, str]] = {}

    def check(name: str, ok: bool, detail: str = "") -> None:
        out[name] = (bool(ok), detail)

    from src import entitlements as E
    from src.api.admin_route_invariant import admin_routes, ungated
    from src.application import admin_permissions as perm
    from src.application.authorization import BASIC_CAPABILITIES, PREMIUM_CAPABILITIES

    check("registry_is_code_defined_and_matches_existing_access",
          set(E.REGISTRY) == set(PREMIUM_CAPABILITIES) and E.BASIC_KEYS == BASIC_CAPABILITIES, f"{len(E.REGISTRY)} keys")
    check("no_invented_quota", all(d.type is E.EntitlementType.BOOLEAN for d in E.REGISTRY.values()), "every key is boolean; limit support exists but no limit key")
    check("only_real_plan_families", E.PLAN_CODES == ("basic", "premium") and "preview" in E.DEFAULT_PLANS["premium"]["display_name"].lower(),
          "basic, premium (preview); no invented product")
    check("limit_representation_has_one_form",
          'limit_value >= 1 AND enabled = 1' in read("migrations/versions/0016_plans_entitlements.py")
          and "ck_plan_entitlements_limit" in read("src/persistence.py"), "0 never means unlimited or disabled")

    billing_files = ("src/entitlements.py", "src/plans_repository.py", "src/api/routes/admin_plans.py",
                     "src/api/schemas/admin.py", "migrations/versions/0016_plans_entitlements.py")
    def plan_part(f: str) -> str:   # W10.5: commercial schemas live in the separate Billing* block at the END of the admin schemas file
        src = read(f)
        return src.split("# ---- W10.5 mock billing")[0] if f.endswith("schemas/admin.py") else src

    hits = sorted({f for f in billing_files if BILLING_WORDS.search(code_only(plan_part(f)))})
    check("no_billing_price_or_payment_in_plan_code", not hits, ", ".join(hits) or "none")
    models = code_only("PLAN_STATUS_DRAFT" + read("src/persistence.py").split("PLAN_STATUS_DRAFT", 1)[1].split("# --- Integration state")[0])
    check("no_payment_columns_on_plan_models", not BILLING_WORDS.search(models) and "trial" not in models.lower(), "plan/subscription tables carry no payment data")
    check("subscription_sources_are_real", "SUBSCRIPTION_SOURCES = (\"system_default\", \"migration\", \"admin\")" in read("src/persistence.py"), "system_default, migration, admin")

    mig = read("migrations/versions/0016_plans_entitlements.py")
    check("subject_integrity_in_db",
          "ck_subscriptions_one_subject" in mig and "uq_subscriptions_one_active_user" in mig and "uq_subscriptions_one_active_workspace" in mig
          and "uq_plan_entitlements_key" in mig, "XOR subject CHECK; one active per subject; unique entitlement key")
    check("active_plan_definitions_are_immutable",
          "Only a draft plan version can be edited" in read("src/plans_repository.py") and "uq_plan_versions_one_active" in mig, "draft-only edits; one active version per plan")
    check("admin_cannot_invent_entitlement_keys",
          "validate_value(" in read("src/plans_repository.py") and "extra=\"forbid\"" in read("src/api/routes/admin_plans.py"), "registry validation + strict body")
    check("default_subscription_in_account_creation_transaction",
          read("src/auth_repository.py").count("ensure_default_subscription(") >= 2, "password and OIDC creation paths")
    check("legacy_tier_has_one_mutation_path",
          "PlanRepository" in read("src/auth_repository.py").split("def set_tier")[1].split("def set_status")[0]
          and "ent.tier" not in read("src/auth_repository.py").split("def set_tier")[1].split("def set_status")[0], "set_tier delegates to the subscription domain")
    check("deletion_and_export_cover_subscriptions",
          "P.Subscription" in read("src/application/account_deletion_service.py") and '"plan"' in read("src/application/data_export.py"), "deleted with the account; own plan history exported")

    # Product access must not drift back to scattered tier comparisons.
    offenders = []
    allowed = {"src/application/authorization.py", "src/persistence.py", "src/auth_repository.py", "src/admin_repository.py", "src/plans_repository.py", "src/entitlements.py"}
    pat = re.compile(r"tier\s*(==|!=)|==\s*TIER_|!=\s*TIER_|\bin\s+PRODUCT_TIERS|capabilities_for\(|has_capability\(|require_capability")
    for p in (ROOT / "src").rglob("*.py"):
        rel = str(p.relative_to(ROOT))
        if rel in allowed or "__pycache__" in rel:
            continue
        if pat.search(code_only(p.read_text(encoding="utf-8"))):
            offenders.append(rel)
    check("no_scattered_tier_access_checks_in_backend", offenders == [] or offenders == ["src/api/routes/admin.py"],
          ", ".join(offenders) or "access is decided by the entitlement resolver")
    admin_py = code_only(read("src/api/routes/admin.py"))
    check("admin_tier_use_is_filter_validation_only", not re.search(r"tier\s*(==|!=)|\.tier\s*=", admin_py) and "PLAN_CODES" in admin_py, "legacy tier is a list filter and display value")
    fe = ""
    for d in ("components", "lib", "app"):
        for p in (ROOT / "frontend" / d).rglob("*.ts*"):
            if "i18n/messages" in str(p) or "lib/api/types.ts" in str(p):
                continue
            fe += p.read_text(encoding="utf-8")
    check("no_frontend_tier_access_logic", not re.search(r"(?<![A-Za-z_])tier\s*===\s*[\"']|\.tier\s*===", fe), "no tier comparison in the frontend")

    routes = admin_routes()
    plan_routes = [r for r in routes if r.path.startswith("/admin/plans") or r.path.endswith("/plan")]
    used = {p for r in plan_routes for p in r.permissions}
    check("plan_routes_permissioned", len(plan_routes) == 9 and not ungated(routes) and used <= {perm.PLANS_READ, perm.PLANS_MANAGE, perm.SUBSCRIPTIONS_MANAGE},
          f"{len(plan_routes)} routes; {len(routes)} privileged routes all covered")
    cand = read("src/api/routes/auth.py")
    plan_get = cand.split('@router.get("/plan"')[1].split("@router")[0] if '@router.get("/plan"' in cand else ""
    check("candidate_plan_surface_is_read_only", bool(plan_get) and not re.search(r'@router\.(post|put|patch|delete)\("/plan', cand), "GET /auth/plan only")
    check("no_candidate_route_changes_plans", not re.search(r"subscription|assign\(", code_only(cand)), "no subscription write in candidate auth routes")
    check("no_registry_growth", len(perm.PERMISSIONS) == 43, "43 permissions")

    keysets = {}
    for loc in LOCALES:
        body = read(f"frontend/lib/i18n/messages/w104/{loc}.ts").split("plan: {")[-1].split("dataPrivacy:")[0]
        keysets[loc] = set(re.findall(r"^\s+([A-Za-z0-9_]+):", body, re.M))
    check("candidate_plan_copy_in_all_eight_locales", all(keysets[l] == keysets["en"] and len(keysets["en"]) >= 15 for l in LOCALES), f"{len(keysets['en'])} keys x 8")
    en = "\n".join(l for l in read("frontend/lib/i18n/messages/w104/en.ts").splitlines() if not l.lstrip().startswith("//"))
    # W10.5: the candidate notice may SAY there is no checkout ("or offer checkout"); it must still contain no purchase claim.
    check("copy_has_no_price_or_purchase_claim", not re.search(r"[€$£]|buy now|upgrade now|per month|checkout", en.replace("or offer checkout", ""), re.I) and "preview" in en.lower(), "Premium is a preview; nothing to buy")

    heads = sorted(p.name for p in (ROOT / "migrations/versions").glob("0*.py"))
    check("migration_chain_valid", heads[-1].startswith(("0016_", "0017_", "0018_", "0019_", "0020_", "0021_", "0022_")) and 'down_revision = "0015_support_ticketing"' in mig, heads[-1])
    tests = read("tests/test_plans_entitlements_w10_4.py")
    check("tests_exist", all(t in tests for t in ("test_no_subscription_falls_back_to_basic_never_premium", "test_workspace_scope_is_explicit",
                                                  "test_draft_is_editable_active_and_retired_are_immutable", "test_every_privileged_plan_mutation_rolls_back",
                                                  "test_candidate_cannot_change_any_plan", "test_migration_backfill_constraints_and_round_trip")), "present")
    return out


def main() -> int:
    print("ASK4MO - P10B-W10.4 ENTITLEMENT GUARD\n")
    res = run()
    failed = False
    for name in sorted(res):
        ok, detail = res[name]
        failed |= not ok
        print(f"  {name:60s} {'PASS' if ok else 'FAIL'}  {detail}")
    print("\nPaid LLM calls: 0   Live calls: 0")
    print("\nRESULT: " + ("FAIL" if failed else "PASS"))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
