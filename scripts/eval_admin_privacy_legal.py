#!/usr/bin/env python
"""P10B-W10.10 privacy/legal guard (deterministic, offline, 0 paid/live calls).

High-risk invariants: a durable privacy-request queue (SEC-W10-04), W9.8 domain services reused (no admin deletion engine), the
preparation-run ownership index with no chat content and no checkpoint scan (PRIV-W9-01), versioned legal documents with immutable
published versions and recorded acceptance without fabricated history or IP/device (PRIV-W9-02), consent kept separate from legal
acceptance, no compliance or retention claims, no private-content exposure to Admin, and permissioned routes. It does not duplicate
the test suite.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def read(rel: str) -> str:
    p = ROOT / rel
    return p.read_text(encoding="utf-8") if p.exists() else ""


def run() -> dict[str, tuple[bool, str]]:
    out: dict[str, tuple[bool, str]] = {}

    def check(name: str, ok: bool, detail: str = "") -> None:
        out[name] = (bool(ok), detail)

    persist = read("src/persistence.py")
    req, leg, prep, rt = (read(f"src/privacy/{n}.py") for n in ("requests", "legal", "preparation", "runtime"))
    routes = {n: read(f"src/api/routes/{n}.py") for n in ("admin_privacy", "admin_legal", "privacy")}
    privacy_code = req + leg + prep + rt + read("src/privacy/jobs.py") + read("src/privacy/policy.py") + "".join(routes.values())
    check("durable_request_queue", "class PrivacyRequest(" in persist and "def create(" in req and "def list(" in req, "privacy_requests table + service")
    check("candidate_creates_only_own_request", "user_id: int = Depends(get_current_user_id)" in routes["privacy"] and "user_id" not in read("src/api/schemas/privacy.py").split("class PrivacyRequestCreate")[1].split("class PrivacyRequestView")[0], "owner-scoped, no user_id in body")
    check("request_transitions_server_side", "TRANSITIONS" in read("src/privacy/policy.py") and "not in P.TRANSITIONS" in req, "legal-transition table")
    check("completion_needs_result_evidence", "ck_privacy_requests_completed_evidence" in persist, "DB check")
    check("w98_deletion_service_reused", "AccountDeletionService(" in rt and "def delete_account" not in privacy_code, "no second deletion engine")
    check("no_admin_export_of_candidate_data", "build_candidate_export" not in privacy_code and "export_user_data" not in privacy_code, "export stays self-service")
    check("deletion_is_a_w109_job", "JOB_ACCOUNT_DELETE" in routes["admin_privacy"] and "execute-deletion" in routes["admin_privacy"], "job-based")
    check("admin_accounts_not_deletable_via_request", 'platform_role != "user"' in rt, "refused")
    check("deletion_completes_only_when_purged", "RetryableJobError" in rt and "complete_system" in rt and rt.index("RetryableJobError") < rt.index("complete_system"), "no false success")
    check("preparation_index_has_no_content", "class PreparationRun(" in persist and not re.search(r"messages|conversation|transcript|state_json|chat_text", persist.split("class PreparationRun(")[1].split("class LegalDocument(")[0]), "ids and state only")
    agent = read("src/application/agent_service.py")
    check("new_runs_indexed_before_checkpoint", agent.index("self._run_index.register") < agent.index("self._graph.invoke(initial"), "index first, fail-closed")
    check("per_user_lookup_indexed_no_scan", "run_ids_for_owner" in prep and not re.search(r"checkpointer\.list|\.alist\(|list_threads|get_state_history|FROM checkpoints", privacy_code + agent + read("src/application/account_deletion_service.py")), "indexed query, no store scan")
    check("deletion_uses_index", "run_ids_for_owner" in read("src/application/account_deletion_service.py") and "purge_failed" in read("src/application/account_deletion_service.py"), "index + failure surfaced")
    check("backfill_verifies_owner_never_assigns_ambiguous", "ambiguous_skipped" in prep and "owner != str(user_id)" in prep, "verified references only")
    check("migration_does_not_scan_checkpoints", not re.search(r"checkpoint|langgraph|get_tuple", read("migrations/versions/0020_privacy_legal_admin.py").lower().replace("never scans or touches the agent checkpoint store", "").replace("scans", "")), "relational only")
    check("legal_documents_versioned_and_unique_current", "uq_ldv_one_published" in persist and "uq_ldv_document_version" in persist, "one published per document")
    check("published_immutable", "A published or retired version is immutable" in leg and 'v.state != "draft"' in leg, "service guard")
    check("no_legal_version_delete_route", not re.search(r"router\.delete", routes["admin_legal"]) and "s.delete(v" not in leg and "s.delete(doc" not in leg, "no delete")
    check("acceptance_unique_per_user_version", "uq_legal_acceptance_user_version" in persist, "unique")
    check("no_ip_device_fingerprint_anywhere", not re.search(r"\b(ip|ip_address|device|device_id|fingerprint|user_agent)\b\s*:\s*Mapped", persist.split("class PrivacyRequest(")[1].split("def make_engine")[0]) and "ip_address" not in read("migrations/versions/0020_privacy_legal_admin.py").split("def upgrade")[1], "none")
    mig0020 = read("migrations/versions/0020_privacy_legal_admin.py")
    check("no_fabricated_acceptance", mig0020.count("op.bulk_insert(") == 2 and "INSERT INTO legal_acceptances" not in mig0020.upper().replace("INSERT INTO LEGAL_ACCEPTANCES", "INSERT INTO legal_acceptances") and "legal_acceptances" not in mig0020.split("op.bulk_insert(docs")[1].split("def downgrade")[0], "seeds documents and baseline versions only")
    seed = mig0020.split("op.bulk_insert(versions")[1].split("def downgrade")[0]
    check("baseline_version_marked_not_invented", "is_baseline" in persist and '"is_baseline": True' in seed and "effective_at" not in seed and "content_hash" not in seed, "no effective date or hash seeded")
    check("acceptance_sources_code_defined", 'ACCEPTANCE_SOURCES = ("signup", "settings", "reacceptance")' in read("src/privacy/policy.py") and "ck_legal_acceptances_source" in persist, "bounded")
    check("no_forced_reacceptance", "reacceptance" not in routes["privacy"] and "force" not in leg.lower().replace("forced", "x"), "not enforced")
    check("consent_separate_from_acceptance", "UserPreference" not in leg and "not consent" in leg.lower(), "distinct concepts")
    check("no_compliance_or_certification_claims", not re.search(r"gdpr compliant|legally compliant|fully compliant|certified|complete dsar|all legally required", privacy_code.lower()), "none")
    check("no_hardcoded_retention_period", not re.search(r"\b\d+\s*(years?|months?|days?)\b.{0,40}retain|retain.{0,40}\b\d+\s*(years?|months?|days?)\b", privacy_code.lower()), "none")
    schema = read("src/api/schemas/admin.py")
    block = schema[schema.index("class PrivacyRequestRow"):] if "class PrivacyRequestRow" in schema else ""
    check("no_private_content_in_admin_schemas", block != "" and not re.search(r"\b(cv|transcript|answers|memories|conversation|evidence|export_data|ip_address|device)\b\s*:", block), "metadata only")
    check("admin_routes_permissioned", all(routes[n].count("require_permission(") >= 3 for n in ("admin_privacy", "admin_legal")) and "PRIVACY_READ" in routes["admin_privacy"] and "LEGAL_MANAGE" in routes["admin_legal"], "explicit")
    check("uses_existing_permissions", all(f'"{p}"' in read("src/application/admin_permissions.py") for p in ("platform.privacy.read", "platform.privacy.execute", "platform.legal.manage")), "no new permission")
    check("rate_limited_candidate_requests", 'enforce("privacy_request_user"' in routes["privacy"] and '"privacy_request_user"' in read("src/api/rate_limit.py"), "bucket")
    check("privacy_jobs_id_only", all(x in read("src/privacy/jobs.py") for x in ("request_id", "after_id", "run_id")) and "extra=\"forbid\"" in read("src/privacy/jobs.py"), "ids only")
    check("sec_w10_05_untouched", "pause" not in privacy_code.lower(), "platform pause not touched")
    mig = read("migrations/versions/0020_privacy_legal_admin.py")
    check("migration_chain_valid", 'down_revision = "0019_knowledge_admin"' in mig and "ck_ldv_published_hash" in mig and "uq_ldv_one_published" in mig, "0020 chains from 0019")
    t = read("tests/test_privacy_legal_w10_10.py")
    check("tests_exist", all(x in t for x in (
        "test_end_to_end_request_lifecycle_assignment_audit_and_candidate_status",
        "test_admin_deletion_runs_the_same_service_clears_the_account_and_completes_only_when_everything_is_purged",
        "test_new_runs_are_indexed_before_the_checkpoint_and_without_chat_content",
        "test_historical_backfill_uses_only_references_verifies_owner_never_assigns_ambiguous_and_never_scans",
        "test_acceptance_is_versioned_timestamped_idempotent_and_survives_a_new_version",
        "test_baseline_documents_exist_with_a_truthful_baseline_version_and_no_fabricated_acceptance")), "present")
    return out


def main() -> int:
    print("ASK4MO - P10B-W10.10 PRIVACY AND LEGAL GUARD\n")
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
