#!/usr/bin/env python
"""P10B-W11 integrated cross-plane guard (deterministic, offline, 0 paid/live calls).

Checks invariants that span the candidate product and the Admin control plane (it does NOT repeat the W10.14 Admin checks): the release matrix is the integrated gate,
candidate vs Admin separation, authorization != entitlement != capability != billing, the support-content exception, reporting without candidate drilldown, the protected
language dimensions and slogan, the agent architecture (11 tools = 6 + 3 + 2, exactly 3 specialists, no Evaluation specialist), a single Alembic head, the permanent
W10.13 contamination disclosure, and that W11 itself created no release candidate.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# TEST ISOLATION (hard requirement): before any application import (temp DATABASE_URL, no .env, non-temp engines fail fast).
import tests.conftest  # noqa: E402,F401


def read(rel: str) -> str:
    p = ROOT / rel
    return p.read_text(encoding="utf-8") if p.exists() else ""


def run() -> dict[str, tuple[bool, str]]:
    out: dict[str, tuple[bool, str]] = {}

    def check(name: str, ok: bool, detail: str = "") -> None:
        out[name] = (bool(ok), detail)

    from fastapi.testclient import TestClient

    from src.agent.registry import career_tool_registry
    from src.agent.specialists.registry import SpecialistName
    from src.application import admin_permissions as perm
    from src.locales import DOCUMENT_LANGUAGE_CODES, SUPPORTED_LOCALE_CODES
    from src.persistence import KNOWLEDGE_LANGUAGES
    from tests import _admin_matrix as M
    from tests._auth_factories import build_auth_app, cookies_for, login_token, register

    matrix = read("docs/capstone/p10/P10B_RELEASE_ACCEPTANCE_MATRIX.md")
    w1014 = read("docs/capstone/admin/W10_14_FULL_ADMIN_QUALIFICATION.md")
    w11 = read("docs/capstone/p10/P10B_W11_INTEGRATED_REQUALIFICATION.md")
    rows = re.findall(r"^\| (R-\d+) \|", matrix, re.M)

    # ---- the gate itself
    check("w10_14_is_complete_and_the_admin_platform_is_qualified", "W10.14 COMPLETE" in w1014 and "ADMIN PLATFORM QUALIFIED" in w1014 and "ROLE-W10-01" in w1014, "W10.14 document")
    check("release_matrix_is_the_integrated_gate", len(rows) >= 98 and "Integrated Release Acceptance Matrix" in matrix and "R-53" in rows and "R-81" in rows and "W9.13" in matrix, f"{len(rows)} rows, W9.13 history preserved")
    check("w11_document_records_no_rc_creation_by_w11", "RC-P10-003" in w11 and ("NOT created" in w11 or "has not been created" in w11 or "NOT been created" in w11), "W11 document")
    check("w10_13_contamination_disclosure_remains", "disclosed contamination with stable post-incident qualification baseline" in read("docs/capstone/admin/W10_13_SECURITY_AUDIT_INCIDENT_MANAGEMENT.md")
          and "disclosed contamination with stable post-incident qualification baseline" in w11, "permanent disclosure")
    # Process-aware: W11 itself created no RC. After the separately owner-approved RC action RC-P10-003 may exist, but only as a separate, valid artifact.
    rc = ROOT / "artifacts/capstone/p10/RC-P10-003"
    if not rc.exists():
        check("post_w11_rc_if_present_is_separate_and_valid", True, "RC-P10-003 absent (W11 guard holds)")
    else:
        try:
            man = json.loads(read("artifacts/capstone/p10/RC-P10-003/manifest.json"))
        except ValueError:
            man = {}
        narrative = read("docs/capstone/p10/RC_P10_003_RELEASE_CANDIDATE.md")
        check("post_w11_rc_if_present_is_separate_and_valid",
              (rc / "manifest.json").exists() and (rc / "gate_results.md").exists() and man.get("release_candidate_sha") == "54aad500ec937b4828984c32c64b77746534633d"
              and bool(narrative) and "separate owner-approved" in str(man.get("creation", "")) and "W11 did NOT create" in narrative
              and ("RC-P10-003 has NOT been created" in w11 or "RC-P10-003 has not been created" in w11 or "NOT created" in w11),
              "separate owner-approved post-W11 artifact; the W11 document still records that W11 did not create it")

    # ---- candidate vs Admin
    check("permissions_43_and_platform_admin_28", len(perm.PERMISSIONS) == 43 and len(perm.ROLE_PRESETS["platform_admin"]) == 28)
    routes = M.routes()
    check("no_break_glass_no_impersonation", not re.search(r"break.?glass|impersonat|view.?as|act.?as", " ".join(r.path.lower() for r in routes))
          and not [p for p in perm.PERMISSIONS if any(f in p for f in ("impersonat", "break_glass", "view_as"))])
    app, repo, _ = build_auth_app()
    with TestClient(app) as c:
        register(c, "w11cand@x.com", "correcthorsebattery")
        ck = cookies_for(login_token(c, "w11cand@x.com", "correcthorsebattery"))
        sample = ["/admin/home", "/admin/users", "/admin/security/events", "/admin/reports/product", "/admin/audit", "/admin/support/tickets", "/admin/billing", "/admin/ai"]
        check("candidate_cannot_reach_admin", all(c.get("/api/v1" + p, cookies=ck).status_code == 403 for p in sample), f"{len(sample)} representative routes")

    # ---- separation of planes
    billing = re.sub(r'"""(.|\n)*?"""|#.*', "", "\n".join(p.read_text(encoding="utf-8") for p in (ROOT / "src/billing").glob("*.py")))
    check("billing_never_writes_entitlements_or_tier", not re.search(r"PlanRepository|EntitlementService|\bSubscription\b|\.assign\(|\btier\s*=", billing))
    flags = read("src/platform_config/flags.py")
    check("flags_never_grant_entitlement_or_authorization", not re.search(r"^\s*(from|import)\s+.*(entitlements|admin_permissions|billing)", flags, re.M))
    pause = read("src/application/pause.py")
    check("pause_never_grants_anything", not re.search(r"^\s*(from|import)\s+.*(entitlements|admin_permissions|billing)", pause, re.M))
    ai = read("src/ai_admin/resolver.py") + read("src/llm/governed.py")
    check("model_configuration_never_touches_entitlements", not re.search(r"^\s*(from|import)\s+.*(entitlements|admin_permissions|billing)", ai, re.M))
    check("reporting_has_no_candidate_drilldown", all(r.methods == ("GET",) and "{" not in r.path for r in routes if r.path.startswith("/admin/reports")) and routes, "aggregate-only, no id path")
    holders = sorted(r for r in M.ROLES if "platform.support.read" in perm.ROLE_PRESETS[r])
    check("support_content_exception_is_explicitly_scoped", holders == ["platform_admin", "support_operator"], ", ".join(holders))
    check("support_internal_notes_have_no_candidate_route", not re.search(r"internal_note", read("src/api/routes/support.py")), "candidate support routes never mention internal notes")

    # ---- protected dimensions
    check("interface_8_conversation_8_document_7_kb_7", len(SUPPORTED_LOCALE_CODES) == 8 and len(DOCUMENT_LANGUAGE_CODES) == 7 and len(KNOWLEDGE_LANGUAGES) == 7, "8 / 8 / 7 / 7")
    check("russian_excluded_from_speech_kb_documents", "ru" in SUPPORTED_LOCALE_CODES and "ru" not in DOCUMENT_LANGUAGE_CODES and "ru" not in KNOWLEDGE_LANGUAGES
          and "ru" not in __import__("src.voice.realtime", fromlist=["x"]).SUPPORTED_REALTIME_LOCALES)
    check("no_geography_inference_from_language", not re.search(r"language_to_country|infer_geography_from_language", "\n".join(p.read_text(encoding="utf-8") for p in (ROOT / "src").rglob("*.py"))))
    check("protected_slogan_exact", 'export const BRAND_SLOGAN = "Ask More. Be More.";' in read("frontend/lib/brand.ts"))

    # ---- agent architecture
    reg = career_tool_registry(MagicMock())
    tools = reg.names()
    spec = {"AnalyzeRoleOpportunity", "FindCandidateEvidence", "BuildCoachingStrategy"}
    human = {"ProposePreparationMemory", "RequestPracticeHandoff"}
    career = [t for t in tools if t not in spec and t not in human]
    check("eleven_tools_six_career_three_specialists_two_human_action", len(tools) == 11 and len(career) == 6 and spec <= set(tools) and human <= set(tools))
    names = sorted(m.value for m in SpecialistName)
    check("exactly_three_specialists_no_evaluation_specialist", names == ["candidate_evidence", "interview_strategy", "role_opportunity"], ", ".join(names))
    ev = read("src/evaluation_service.py") + read("src/models.py")
    check("evaluation_is_model_produced_and_schema_validated", "overall_score: OverallScore" in ev and "BaseGenerationService" in read("src/evaluation_service.py") and "AnswerEvaluation" in read("src/evaluation_service.py")
          and not re.search(r"overall_score\s*=\s*(sum|round|int|mean|statistics)", ev) and (ROOT / "tests/test_evaluation_contract.py").exists(), "no deterministic scoring formula")

    # ---- schema / scope
    mig = sorted(p.name for p in (ROOT / "migrations/versions").glob("0*.py"))
    check("one_alembic_head_0025", mig[-1].startswith("0025_security_audit_incidents") and len(mig) == 25, mig[-1])
    ci = read(".github/workflows/ci.yml")
    try:
        import yaml
        wf = yaml.safe_load(read(".github/workflows/ci.yml"))
        steps = [s.get("run", "") for s in wf["jobs"]["python"]["steps"]]
        referenced = sorted(set(re.findall(r"scripts/eval_[a-z_0-9]+\.py", "\n".join(steps))))
        check("ci_workflow_is_valid_yaml_and_its_evaluator_steps_exist", all((ROOT / r).exists() for r in referenced) and len(referenced) >= 40 and "python" in wf["jobs"], f"valid YAML; {len(referenced)} evaluator scripts referenced and present")
    except Exception as exc:  # noqa: BLE001 - an unparseable workflow is exactly the defect this guards
        check("ci_workflow_is_valid_yaml_and_its_evaluator_steps_exist", False, f"ci.yml does not parse: {str(exc)[:120]}")
    check("ci_runs_the_w11_evaluators", "scripts/eval_w11_integrated.py" in ci and "scripts/eval_release_matrix.py" in ci and "scripts/eval_admin_qualification.py" in ci)
    shell = read("frontend/components/layout/AppShell.tsx") + read("frontend/components/layout/PrimaryNavigation.tsx") + read("frontend/components/layout/MobileNavigation.tsx")
    check("layout_w11_01_navigation_handoff_is_coherent_at_lg", "lg:flex" in shell and "lg:hidden" in shell and "lg:pb-20" in shell and not re.search(r"\bmd:(flex|hidden|pb-20)\b", shell), "primary nav, mobile nav and main padding all hand off at lg (1024px)")
    check("tests_exist", all(x in read("tests/test_integrated_w11.py") for x in ("test_k2_candidate_support_ticket", "test_k3_admin_deactivation", "test_k4_admin_plan_assignment", "test_k5_operations_pause",
                                                                         "test_k6_flag_off", "test_k7_only_approved", "test_k8_only_an_approved", "test_k9_candidate_deletion", "test_k10_workspace",
                                                                         "test_k11_two_person", "test_q_private_sentinels", "test_r_secret_sentinels")))
    return out


def main() -> int:
    print("ASK4MO - P10B-W11 INTEGRATED CANDIDATE + ADMIN GUARD (the RC is NOT created by W11)\n")
    res = run()
    failed = False
    for name in sorted(res):
        ok, detail = res[name]
        failed |= not ok
        print(f"  {name:66s} {'PASS' if ok else 'FAIL'}  {detail}")
    print(f"\nChecks: {len(res)}   Paid LLM calls: 0   Live calls: 0")
    print("\nRESULT: " + ("FAIL" if failed else "PASS"))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
