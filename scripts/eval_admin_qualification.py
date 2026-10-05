#!/usr/bin/env python
"""P10B-W10.14 integrated Admin qualification guard (deterministic, offline, 0 paid/live calls).

An INTEGRATED evaluator, not a duplicate implementation test: it reconciles the canonical permission registry, the code-defined role presets, the route dependency graph, the
frontend destination table and the W10 domain boundaries, and asserts the final least-privilege decision (ROLE-W10-01 closed): platform_admin is a broad but NOT universal
operator and specialist high-risk permissions stay with their domain roles. ``--markdown`` renders the machine-generated matrices used by the W10.14 document.
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
    check("permissions_exactly_43", len(perm.PERMISSIONS) == 43 and len(set(perm.PERMISSIONS)) == 43, str(len(perm.PERMISSIONS)))
    check("roles_exactly_user_plus_six_presets", set(perm.ROLE_PRESETS) == set(M.ROLES) and perm.permissions_for_role("user") == frozenset(), ",".join(M.ROLES))
    pa = perm.ROLE_PRESETS["platform_admin"]
    check("role_w10_01_closed_least_privilege_platform_admin_not_universal",
          set(perm.PERMISSIONS) - pa == set(M.PLATFORM_ADMIN_ABSENT) and len(pa) == 28 and "platform.integrations.secret.rotate" not in pa,
          f"{len(pa)} of 43 permissions; {len(set(perm.PERMISSIONS) - pa)} specialist permissions absent by decision")
    check("specialist_permissions_owned_by_domain_roles",
          all([r for r in M.ROLES if p in perm.ROLE_PRESETS[r] and r != "platform_admin"] for p in M.PLATFORM_ADMIN_ABSENT - {"platform.integrations.secret.rotate"})
          and not [r for r in M.ROLES if "platform.integrations.secret.rotate" in perm.ROLE_PRESETS[r]], "secret rotation intentionally unassigned")
    check("unknown_missing_candidate_default_deny", all(perm.permissions_for_role(x) == frozenset() for x in (None, "", "ghost", "user", "PLATFORM_ADMIN")))
    check("no_wildcard_or_content_or_break_glass_permission", not [p for p in perm.PERMISSIONS if "*" in p or any(f in p for f in perm.BANNED_PERMISSION_FRAGMENTS)])
    check("permission_matrix_deterministic_two_builds", M.matrix_hash() == M.matrix_hash() and len(M.permission_matrix()) == 43, M.matrix_hash())

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
    check("every_privileged_mutation_audited_in_handler_or_service", [r["path"] for r in inv if not r["audited_in_handler"]] == ["/admin/step-up"], f"{len(inv)} mutating routes")
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
    billing_src = code_only("\n".join(p.read_text(encoding="utf-8") for p in (ROOT / "src/billing").glob("*.py")))
    check("billing_state_never_writes_entitlements_or_tier", not re.search(r"PlanRepository|EntitlementService|\bSubscription\b|\.assign\(|platform_tier|\btier\s*=", billing_src) and "MOCK" in billing_src.upper(), "billing != entitlement")
    check("billing_and_reports_say_mock_not_live", "MOCK BILLING" in read("frontend/components/admin/BillingView.tsx").upper() and "NOT LIVE REVENUE" in read("frontend/components/admin/ReportsView.tsx").upper()
          and not re.search(r"stripe|paddle|adyen|checkout\.session", billing_src, re.I))
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
    check("one_alembic_head_0025_and_no_new_migration", mig[-1].startswith("0025_security_audit_incidents") and len(mig) == 25 and len({m[:4] for m in mig}) == 25, mig[-1])
    check("no_w11_or_rc_code", not list((ROOT / "docs/capstone").rglob("W11*")) and not list((ROOT / "docs/capstone").rglob("RC-P10-003*")) and not (ROOT / "artifacts/capstone/p10/RC-P10-003").exists())

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
    check("role_w10_01_recorded_closed", "ROLE-W10-01" in doc and "CLOSED" in doc and "ROLE-W10-01" in read("docs/capstone/admin/ADMIN_ARCHITECTURE_DECISIONS.md"))
    check("w10_13_doc_records_docs_pr_129", "#129" in read("docs/capstone/admin/W10_13_SECURITY_AUDIT_INCIDENT_MANAGEMENT.md") and "disclosed contamination with stable post-incident qualification baseline" in read("docs/capstone/admin/W10_13_SECURITY_AUDIT_INCIDENT_MANAGEMENT.md"))
    check("tests_exist", all(x in read("tests/test_admin_qualification_w10_14.py") for x in ("test_route_x_persona_matrix_over_http_is_exactly_the_preset_expectation", "test_role_w10_01_platform_admin_is_least_privilege_not_universal",
                                                                                     "test_privacy_and_secret_sentinels_never_appear_in_any_admin_surface")))
    return out


def main() -> int:
    if "--markdown" in sys.argv:
        from tests import _admin_matrix as M
        for title, fn in (("PERMISSION MATRIX", M.md_permission_matrix), ("ROUTE INVENTORY", M.md_route_inventory), ("MUTATION INVENTORY", M.md_mutation_inventory),
                          ("PAGE INVENTORY", M.md_page_inventory), ("NAV MATRIX", M.md_nav_matrix)):
            print(f"\n<!-- {title} -->\n{fn()}\n")
        return 0
    print("ASK4MO - P10B-W10.14 FULL ADMIN QUALIFICATION GUARD (least-privilege domain separation is authoritative)\n")
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
