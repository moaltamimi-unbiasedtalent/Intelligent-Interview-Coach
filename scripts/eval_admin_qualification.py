#!/usr/bin/env python
"""P10B-W10.14 integrated Admin qualification guard (deterministic, offline, 0 paid/live calls).

An INTEGRATED evaluator, not a duplicate implementation test: it reconciles the canonical permission registry, the code-defined role presets, the route dependency graph, the
frontend destination table and the W10 domain boundaries. CURRENT runtime (AD-W12-01, owner approved): platform_admin is the owner / orchestrator holding ALL 43 canonical
control-plane permissions while the specialist presets stay least-privilege delegated roles and no permission inspects candidate content. The W10.14 decision (ROLE-W10-01: 28 / 43)
is HISTORICAL EVIDENCE: it is asserted only against the W10.14 document, never as current behaviour. ``--markdown`` renders the machine-generated matrices.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# TEST ISOLATION (hard requirement): MUST be imported before any application code so DATABASE_URL/.env/Chroma are temp-only and any non-temp engine fails fast.
import tests.conftest  # noqa: E402,F401


def read(rel: str) -> str:
    p = ROOT / rel
    return p.read_text(encoding="utf-8") if p.exists() else ""


def code_only(text: str) -> str:
    """Strip docstrings and comments so a sentence that says "never touches entitlements" cannot trip a code check."""
    text = re.sub(r'"""(.|\n)*?"""', "", text)
    return re.sub(r"#.*", "", text)


def run() -> dict[str, tuple[bool, str]]:
    out: dict[str, tuple[bool, str]] = {}

    def check(name: str, ok: bool, detail: str = "") -> None:
        out[name] = (bool(ok), detail)

    from fastapi.testclient import TestClient

    from src.api.admin_route_invariant import ungated
    from src.application import admin_permissions as perm
    from tests import _admin_matrix as M
    from tests._auth_factories import account_repo, build_auth_app, cookies_for, login_token, register

    routes = M.routes()
    all_routes_src = "\n".join(f.read_text(encoding="utf-8") for f in (ROOT / "src/api/routes").glob("*.py"))
    ui = "\n".join(p.read_text(encoding="utf-8") for p in (ROOT / "frontend/components/admin").glob("*.tsx"))
    ci = read(".github/workflows/ci.yml")

    # ---- role / permission model
    check("permissions_are_the_original_43_plus_only_billing_recover", len(perm.PERMISSIONS) == 44 and len(set(perm.PERMISSIONS)) == 44 and len(set(perm.PERMISSIONS) - {"platform.billing.recover"}) == 43, str(len(perm.PERMISSIONS)))
    check("roles_exactly_user_plus_six_presets", set(perm.ROLE_PRESETS) == set(M.ROLES) and perm.permissions_for_role("user") == frozenset(), ",".join(M.ROLES))
    pa = perm.ROLE_PRESETS["platform_admin"]
    check("ad_w12_01_platform_admin_owns_all_canonical_permissions",
          pa == perm.PERMISSION_SET and len(pa) == 44 and set(perm.PERMISSIONS) - pa == set() and len(M.W10_14_PLATFORM_ADMIN_ABSENT) == 15 and M.W10_14_PLATFORM_ADMIN_ABSENT <= pa,
          f"{len(pa)} of 44 permissions (the 15 W10.14-absent permissions added by AD-W12-01, plus billing.recover from W12.4D-F1R)")
    check("specialist_roles_remain_least_privilege_delegated_subsets",
          {r: len(perm.ROLE_PRESETS[r]) for r in M.ROLES if r != "platform_admin"} == {"support_operator": 7, "billing_admin": 11, "knowledge_admin": 6, "security_privacy_admin": 11, "operations_admin": 11}
          and all(perm.ROLE_PRESETS[r] < pa for r in M.ROLES if r != "platform_admin")
          and [r for r in M.ROLES if "platform.integrations.secret.rotate" in perm.ROLE_PRESETS[r]] == ["platform_admin"], "secret rotation authorized for the owner only; the store is still read-only")
    ruleset = read("src/application/admin_permissions.py")
    check("owner_preset_reuses_the_registry_and_no_role_name_authorization",
          "ROLE_PLATFORM_ADMIN: PERMISSION_SET" in ruleset and not re.search(r"==\s*[\"']platform_admin[\"']|in\s*\(\s*[\"']platform_admin", read("src/api/dependencies.py")))
    check("no_private_content_permission_even_for_the_owner", not [p for p in pa if re.search(r"break|impersonat|view_as|candidate|content|\bcv\b|memory|answer|conversation|evidence|document", p)])
    check("unknown_missing_candidate_default_deny", all(perm.permissions_for_role(x) == frozenset() for x in (None, "", "ghost", "user", "PLATFORM_ADMIN")))
    check("no_wildcard_or_content_or_break_glass_permission", not [p for p in perm.PERMISSIONS if "*" in p or any(f in p for f in perm.BANNED_PERMISSION_FRAGMENTS)])
    check("permission_matrix_deterministic_two_builds", M.matrix_hash() == M.matrix_hash() and len(M.permission_matrix()) == 44, M.matrix_hash())

    # ---- routes
    check("every_privileged_route_permission_gated", ungated() == [] and len(routes) > 0, f"{len(routes)} routes, {len(ungated())} ungated")
    check("route_x_persona_matrix_complete", len(M.route_persona_expectations()) == len(routes) * len(M.PERSONAS), f"{len(routes)} x {len(M.PERSONAS)} = {len(routes) * len(M.PERSONAS)} cases")
    check("every_route_maps_to_a_known_domain", not [r.path for r in routes if M.domain_of(r.path) == "UNMAPPED"], f"{len(M.DOMAINS)} domains")
    check("only_registry_permissions_are_required_by_routes", {p for r in routes for p in r.permissions} <= perm.PERMISSION_SET
          and (perm.PERMISSION_SET - {p for r in routes for p in r.permissions}) == set(M.UNROUTED_PERMISSIONS),
          "unrouted registry permissions: " + ",".join(sorted(x.replace("platform.", "") for x in M.UNROUTED_PERMISSIONS)))
    nocomment = "\n".join(l for l in all_routes_src.splitlines() if not l.lstrip().startswith("#"))
    check("zero_direct_role_name_authorization_in_routes", not re.search(r"require_platform_admin\(|is_platform_admin\(|platform_role\s*(==|!=)\s*[\"']", nocomment), "permission strings are the only authority")
    inv = M.mutation_inventory()
    check("every_privileged_mutation_audited_in_handler_or_service", [r["path"] for r in inv if not r["audited_in_handler"]] == ["/admin/billing/operations/step-up", "/admin/knowledge/test-retrieval", "/admin/step-up"], f"{len(inv)} mutating routes (the retrieval test is a read-only POST with no mutation)")
    check("get_routes_do_not_mutate", not [r.path for r in routes if r.methods == ("GET",) and re.search(r"\.(add|delete|commit)\(|\.enqueue\(|build_audit\(", __import__("inspect").getsource(r.route.endpoint))])
    check("no_generic_config_or_role_endpoint", not re.search(r'"/admin/(config|settings|env|roles|permissions)"', all_routes_src) and not [r.path for r in routes if r.path.endswith(("/role",)) and "/members/" not in r.path and r.methods != ("GET",)])

    # ---- HTTP: candidate denied everywhere (GET routes), real app on a temp DB
    app, repo, _ = build_auth_app()
    with TestClient(app) as c:
        register(c, "cand@x.com", "correcthorsebattery")
        ck = cookies_for(login_token(c, "cand@x.com", "correcthorsebattery"))
        gets = [r for r in routes if r.methods == ("GET",)]
        denied = all(c.get("/api/v1" + re.sub(r"\{[^}]+\}", "0", r.path), cookies=ck).status_code == 403 for r in gets)
        check("candidate_denied_every_admin_get_route_over_http", denied, f"{len(gets)} routes")
        register(c, "sup@x.com", "correcthorsebattery")
        sck = cookies_for(login_token(c, "sup@x.com", "correcthorsebattery"))
        account_repo(repo).set_platform_role(c.get("/api/v1/auth/me", cookies=sck).json()["user_id"], "support_operator")
        billing = [r for r in gets if "platform.billing.read" in r.permissions]
        check("support_operator_denied_billing_over_http", billing and all(c.get("/api/v1" + re.sub(r"\{[^}]+\}", "0", r.path), cookies=sck).status_code == 403 for r in billing), f"{len(billing)} billing routes")

    import json as _json
    check("frontend_role_fixture_matches_backend_presets", _json.loads(read("frontend/tests/fixtures/admin-role-permissions.json") or "{}") == _json.loads(_json.dumps(M.role_fixture())), "navigation expectation is generated from code")

    # ---- boundaries
    check("no_break_glass_no_impersonation_no_view_as_no_generic_browser",
          not re.search(r"break.?glass|impersonat|view.?as|act.?as", " ".join(r.path.lower() for r in routes)) and not re.search(r"def\s+\w*(impersonat|break_?glass|view_as)", all_routes_src.lower())
          and not [p for p in perm.PERMISSIONS if any(f in p for f in ("impersonat", "break_glass", "view_as"))])
    schemas = read("src/api/schemas/admin.py")
    bad = ("document_text", "extracted_text", "cv_text", "answer_text", "preparation_messages", "memory_summary", "evidence_text", "raw_response", "uploaded_file_bytes", "password_hash", "token_hash", "api_key", "client_secret")
    check("admin_schemas_have_no_private_content_or_secret_fields", not [b for b in bad if re.search(rf"^\s+{b}\s*:", schemas, re.M)], "allow-list exception: transcript_visible_to_admin (constant False)")
    check("admin_ui_reads_no_private_content_or_secret_fields", not [b for b in bad if re.search(rf"\.{b}\b", ui)])
    check("secret_value_read_path_confined_to_store_and_adapters", not [p for p in (ROOT / "src/api").rglob("*.py") if "get_for_runtime" in p.read_text(encoding="utf-8")], "never an admin route/schema")

    # ---- domain boundaries (static, with the behavioural proofs in the named tests)
    # W12.4D-D: the dedicated bridge is the single audited place provider-verified state may touch access; it is checked on its own (sole writer, no tier, no EntitlementService write).
    billing_src = code_only("\n".join(p.read_text(encoding="utf-8") for p in (ROOT / "src/billing").glob("*.py") if p.name != "entitlement_bridge.py"))
    bridge_only = code_only(read("src/billing/entitlement_bridge.py"))
    check("entitlement_bridge_sole_provider_writer_no_tier_no_plan_repository", len([p for p in (ROOT / "src").rglob("*.py") if re.search(r"source=[\"']provider[\"']", p.read_text(encoding="utf-8"))]) == 1 and not re.search(r"PlanRepository|\.assign\(|platform_tier|\btier\s*=|EntitlementService", bridge_only), "provider access only through the bridge")
    check("billing_state_never_writes_entitlements_or_tier", not re.search(r"PlanRepository|EntitlementService|\bSubscription\b|\.assign\(|platform_tier|\btier\s*=", billing_src) and "MOCK" in billing_src.upper(), "billing != entitlement")
    check("billing_and_reports_say_mock_not_live", "MOCK BILLING" in read("frontend/components/admin/BillingView.tsx").upper() and "NOT LIVE REVENUE" in read("frontend/components/admin/ReportsView.tsx").upper()
          and not re.search(r"paddle|adyen|stripe\.api_key|stripe\.checkout|\.subscriptions\.create", billing_src, re.I)
          and billing_src.count("checkout.sessions.create") == code_only(read("src/billing/stripe_provider.py")).count("checkout.sessions.create") == 1)     # W12.4D-C: the ONLY Checkout Session creation is the fail-closed Stripe adapter call (Managed Payments guard, constant-gated); no global key
    check("flags_never_grant_entitlement_or_authorization", not re.search(r"^\s*(from|import)\s+.*(entitlements|admin_permissions|billing)", read("src/platform_config/flags.py"), re.M), "flags only restrict")
    check("ai_governance_intact", all(x in read("src/ai_admin/service.py") for x in ("evaluation", "approver")) and "force" not in re.sub(r"#.*", "", read("src/api/routes/admin_ai.py")).lower().replace("enforce", ""), "no force/bypass; distinct approver + hash-bound evaluation")
    check("knowledge_approval_governed", "KNOWLEDGE_APPROVE" in read("src/api/routes/admin_knowledge.py") and "approve" in read("src/knowledge_admin/service.py"))
    check("privacy_reuses_account_deletion_service", "AccountDeletionService" in read("src/privacy/jobs.py") + read("src/privacy/runtime.py"), "no second deletion engine")
    check("reports_aggregate_only_get_and_min_cohort_5", all(r.methods == ("GET",) for r in routes if r.path.startswith("/admin/reports")) and "REPORTING_MIN_COHORT = 5" in read("src/reporting/definitions.py"))
    check("audit_db_protection_present", "append_only_trigger_ddl" in read("src/persistence.py") and "trg_" in read("migrations/versions/0025_security_audit_incidents.py") and "audit_events" in read("migrations/versions/0025_security_audit_incidents.py"))
    check("direct_role_change_route_absent_and_two_person_flow_present", '"/users/{user_id}/role"' not in all_routes_src and "/role-changes/{public_id}/approve" in all_routes_src and "set_platform_role(" not in all_routes_src)
    check("step_up_preserved_password_only_5_minutes_oidc_fails_closed", "STEP_UP_WINDOW_SECONDS = 5 * 60" in read("src/admin_security/stepup.py") and "StepUpUnavailable" in read("src/admin_security/stepup.py") and "not multi-factor" in read("src/admin_security/stepup.py").lower())
    pkg = "\n".join(p.read_text(encoding="utf-8") for p in (ROOT / "src/admin_security").glob("*.py"))
    check("no_external_paging", not re.search(r"(^\s*(import|from)\s+(smtplib|requests|httpx|urllib|boto3)\b)|\b(slack|pagerduty|twilio|webhook|sendgrid)\b", pkg, re.I | re.M))

    # ---- migrations / scope
    mig = sorted(p.name for p in (ROOT / "migrations/versions").glob("0*.py"))
    check("one_alembic_head_0031_after_the_w12_4b_to_w12_4d_f1r_migrations", mig[-1].startswith("0031_account_closure") and len(mig) == 31 and len({m[:4] for m in mig}) == 31, mig[-1])
    check("no_w11_or_rc_code", not list((ROOT / "docs/capstone").rglob("W11*")) and not list((ROOT / "docs/capstone").rglob("RC-P10-003*")))   # W10.14-era guard: no W11/RC docs by name; the RC artifact is governed by eval_w11_integrated / eval_rc_p10_003 after the post-W11 owner-approved action

    # ---- evaluator / test isolation
    iso_bad = []
    for rel in sorted(set(re.findall(r"scripts/eval_[a-z_]+\.py", ci))):
        t = read(rel)
        touches = re.search(r"create_app|build_auth_app|make_engine\(|InterviewRepository\(|ApiSettings|TestClient|create_engine\(|sqlite", t)
        if touches and "tests.conftest" not in t:
            iso_bad.append(rel)
    check("every_db_touching_ci_evaluator_bootstraps_test_isolation", not iso_bad, ", ".join(iso_bad) or f"{len(set(re.findall(r'scripts/eval_[a-z_]+[.]py', ci)))} CI evaluators checked")
    check("ci_runs_this_evaluator", "scripts/eval_admin_qualification.py" in ci)

    # ---- documentation (ROLE-W10-01)
    plan = read("docs/capstone/admin/ADMIN_PLATFORM_MASTER_PLAN.md")
    doc = read("docs/capstone/admin/W10_14_FULL_ADMIN_QUALIFICATION.md")
    check("master_plan_no_longer_claims_all_permissions", "all non-break-glass permissions" not in plan and "least-privilege" in plan.lower())
    check("w10_14_historical_28_of_43_record_preserved", "ROLE-W10-01" in doc and "CLOSED" in doc and re.search(r"28 ?(of|/) ?43", doc) is not None and "ROLE-W10-01" in read("docs/capstone/admin/ADMIN_ARCHITECTURE_DECISIONS.md"))
    ad = read("docs/capstone/admin/AD_W12_01_PLATFORM_ADMIN_OWNER_ORCHESTRATOR.md")
    check("ad_w12_01_recorded_implemented_and_history_preserved", "IMPLEMENTED" in ad and "43 / 43" in ad and re.search(r"28 ?(of|/) ?43", ad) is not None)
    check("w10_13_doc_records_docs_pr_129", "#129" in read("docs/capstone/admin/W10_13_SECURITY_AUDIT_INCIDENT_MANAGEMENT.md") and "disclosed contamination with stable post-incident qualification baseline" in read("docs/capstone/admin/W10_13_SECURITY_AUDIT_INCIDENT_MANAGEMENT.md"))
    check("tests_exist", all(x in read("tests/test_admin_qualification_w10_14.py") for x in ("test_route_x_persona_matrix_over_http_is_exactly_the_preset_expectation", "test_ad_w12_01_current_runtime_platform_admin_owns_all_43_canonical_permissions", "test_w10_14_historical_record_stays_28_of_43",
                                                                                     "test_privacy_and_secret_sentinels_never_appear_in_any_admin_surface")))
    return out


def main() -> int:
    if "--markdown" in sys.argv:
        from tests import _admin_matrix as M
        for title, fn in (("PERMISSION MATRIX", M.md_permission_matrix), ("ROUTE INVENTORY", M.md_route_inventory), ("MUTATION INVENTORY", M.md_mutation_inventory),
                          ("PAGE INVENTORY", M.md_page_inventory), ("NAV MATRIX", M.md_nav_matrix)):
            print(f"\n<!-- {title} -->\n{fn()}\n")
        return 0
    print("ASK4MO - P10B-W10.14 FULL ADMIN QUALIFICATION GUARD (AD-W12-01: platform_admin = 43 / 43; specialist roles least-privilege)\n")
    res = run()
    failed = False
    for name in sorted(res):
        ok, detail = res[name]
        failed |= not ok
        print(f"  {name:72s} {'PASS' if ok else 'FAIL'}  {detail}")
    print(f"\nChecks: {len(res)}   Paid LLM calls: 0   Live calls: 0")
    print("\nRESULT: " + ("FAIL" if failed else "PASS"))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
