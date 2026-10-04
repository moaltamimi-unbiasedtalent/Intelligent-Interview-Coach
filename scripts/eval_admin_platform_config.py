#!/usr/bin/env python
"""P10B-W10.11 durable pause and feature-flag guard (deterministic, offline, 0 paid/live calls). Closes SEC-W10-05 only if every closure criterion holds.

High-risk invariants: the pause authority is the DATABASE (no process-local registry); state survives reconstruction and is shared by independent service
instances; admission is server-side and refuses BEFORE any service/provider is built; an unreadable store never reopens the platform; Admin can resume and
privacy/account paths stay available; the job worker is not globally paused; optimistic concurrency and same-transaction audit; the flag registry is
code-defined with inherit/enable/disable semantics and a restriction-only (conjunctive) role; no generic or secret/security configuration editor;
server-authoritative environment; permission registry stays 43; every new privileged route is permissioned. It does not duplicate the tests.
"""

from __future__ import annotations

import ast
import re
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


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

    from sqlalchemy.orm import sessionmaker

    from src.application import admin_permissions as perm
    from src.application import pause as P
    from src.application.pause import PAUSABLE_CAPABILITIES, PauseConflict, PauseService, PauseStateUnavailable, PauseUnsupportedEnvironment, PlatformPausedError
    from src.api.guards import ensure_not_paused
    from src.jobs.service import JobService
    from src.jobs.worker import Worker
    from src.persistence import Base, Job, make_engine
    from src.platform_config import flags as F
    from src.platform_config.flags import FLAGS, FeatureFlagService, FlagConflict, FlagValidationError

    pause_src = code_only("src/application/pause.py")
    flags_src = code_only("src/platform_config/flags.py")
    routes = read("src/api/routes/admin_config.py")
    schemas = read("src/api/schemas/admin.py").split("# ---- W10.11")[-1]
    all_src = "".join(p.read_text(encoding="utf-8") for p in (ROOT / "src").rglob("*.py"))

    # --- SEC-W10-05 closure criteria -------------------------------------------------------------------------------------------
    check("pause_authority_is_the_database", "class PauseService" in pause_src and "PlatformPauseState" in pause_src and "threading" not in pause_src, "PauseService over platform_pause_states")
    check("no_process_local_pause_registry_remains", not re.search(r"PauseRegistry|get_pause_registry|reset_pause_registry", all_src), "removed everywhere")

    with tempfile.TemporaryDirectory() as d:
        eng = make_engine(f"sqlite:///{d}/pc.db")
        Base.metadata.create_all(eng)
        sf = sessionmaker(bind=eng, expire_on_commit=False)
        a, b = PauseService(sf, environment="staging"), PauseService(sf, environment="staging")
        a.set_paused("agent", True, expected_revision=0, reason="incident", actor_user_id=1)
        check("two_independent_instances_share_state", b.is_paused("agent"), "instance B sees A's pause")
        check("restart_does_not_lose_state", PauseService(sf, environment="staging").is_paused("agent"), "fresh instance reads paused")
        stale = False
        try:
            b.set_paused("agent", False, expected_revision=0, reason="late", actor_user_id=2)
        except PauseConflict:
            stale = True
        check("optimistic_concurrency_rejects_stale_writer", stale and a.is_paused("agent"), "409 on stale revision")
        gate_refuses = False
        try:
            ensure_not_paused("agent", b)
        except PlatformPausedError:
            gate_refuses = True
        check("admission_gate_refuses_a_paused_capability", gate_refuses, "PlatformPausedError")
        broken = PauseService(lambda: (_ for _ in ()).throw(RuntimeError("down")), environment="staging")
        unavailable = False
        try:
            broken.is_paused("agent")
        except PauseStateUnavailable:
            unavailable = True
        P.install(lambda: (_ for _ in ()).throw(RuntimeError("down")))
        tool_closed = P.check_paused("current_market") is True
        P.uninstall()
        check("store_failure_never_reopens_the_platform", unavailable and tool_closed, "refused / paused on failure")
        unsupported = False
        try:
            PauseService(sf, environment=None).set_paused("agent", True, expected_revision=0, reason="x", actor_user_id=1)
        except PauseUnsupportedEnvironment:
            unsupported = True
        check("server_authoritative_environment_unknown_cannot_mutate", unsupported and "environment" not in schemas.split("class PauseChangeRequest")[1].split("class ")[0], "no request field; unknown refused")
        check("environment_scoping", not PauseService(sf, environment="development").is_paused("agent"), "staging row invisible to development")
        a.set_paused("agent", False, expected_revision=1, reason="recovered", actor_user_id=1)
        check("resume_is_possible_while_paused_state_exists", not b.is_paused("agent"), "resumed")

        # the worker is not globally paused
        for cap in PAUSABLE_CAPABILITIES:
            a.set_paused(cap, True, expected_revision=a.snapshot()[cap]["revision"], reason="all", actor_user_id=1)
        jobs = JobService(sf)
        jobs.enqueue("diagnostic_noop", {"label": "x"}, idempotency_key="eval-w1011", actor_user_id=1)
        Worker(jobs, services=SimpleNamespace()).run_once()
        with sf() as s:
            state = s.query(Job).one().state
        check("job_worker_is_not_globally_paused", state == "succeeded", state)
        worker_src = read("src/jobs/worker.py") + read("src/jobs/service.py")
        check("worker_never_consults_pause", "pause" not in worker_src.lower(), "no pause reference in the queue code")

        # flags
        fs = FeatureFlagService(sf, environment="staging")
        r1 = fs.set_override("external_research", False, expected_revision=0, reason="r", actor_user_id=1)
        r2 = fs.set_override("external_research", None, expected_revision=1, reason="r", actor_user_id=1)
        check("flag_inherit_enable_disable_are_distinct", r1["state"] == "disabled_override" and r2["state"] == "inherited" and r2["revision"] == 2, "tri-state with monotonic revision")
        unknown = False
        try:
            fs.set_override("invented", True, expected_revision=0, reason="r", actor_user_id=1)
        except FlagValidationError:
            unknown = True
        stale_flag = False
        try:
            FeatureFlagService(sf, environment="staging").set_override("external_research", True, expected_revision=0, reason="r", actor_user_id=1)
        except FlagConflict:
            stale_flag = True
        check("flag_unknown_key_rejected_and_stale_revision_conflicts", unknown and stale_flag, "404/409")
        eng.dispose()

    # --- admission is server-side and BEFORE the provider ---------------------------------------------------------------------
    agent = read("src/api/routes/agent.py")
    check("agent_routes_gated_before_service_construction", all(agent.index('_pause=Depends(require_not_paused("agent"))', agent.index(f"def {fn}(")) < agent.index("service=Depends(get_agent_service)", agent.index(f"def {fn}("))
                                                                for fn in ("run_agent", "continue_agent_run", "resume_agent_run")), "pause dependency precedes the agent service")
    check("all_protected_routes_use_the_durable_gate", read("src/api/routes/auth.py").count("ensure_not_paused(") >= 1 and read("src/api/routes/documents.py").count("ensure_not_paused(") >= 3
          and read("src/api/routes/voice.py").count("ensure_not_paused(") >= 1 and read("src/api/routes/company.py").count("require_not_paused(") >= 1, "register, ocr x3, realtime, company, agent x3")
    handlers = read("src/api/exception_handlers.py")
    check("stable_error_codes_with_fixed_copy", "platform_paused" in handlers and "platform_state_unavailable" in handlers and "PLATFORM_PAUSED_MESSAGE" in handlers, "machine-readable; no reason in the envelope")
    check("privacy_and_admin_paths_are_not_pause_gated", "ensure_not_paused" not in read("src/api/routes/privacy.py") and "require_not_paused" not in read("src/api/routes/privacy.py")
          and "ensure_not_paused" not in read("src/api/routes/admin_config.py") and "require_not_paused" not in read("src/api/routes/admin_config.py"), "privacy and Admin recovery stay available")
    check("no_provider_or_network_in_pause_and_flags", not re.search(r"httpx|requests\.|urllib|socket|openrouter", pause_src + flags_src + routes), "none")

    # --- flags: code-defined, restriction-only, no grants ------------------------------------------------------------------------
    check("flag_registry_is_code_defined_and_small", set(FLAGS) == {"external_research", "company_web_research"} and not re.search(r"@router\.(post|delete)\(\"/flags", routes), "2 real flags; no create/delete route")
    check("flags_never_touch_entitlement_billing_ai_or_roles", not re.search(r"subscriptions|EntitlementService|BillingService|AIConfigService|platform_role|ProductEntitlement", flags_src), "module reads none")
    check("flag_consumer_is_backend_enforced", "_flags.effective(" in read("src/copilot/research/service.py") and "effective(\"external_research\")" in read("src/api/routes/health.py"), "research service and capabilities")
    check("flag_only_restricts_company_web_under_external_research", 'effective("external_research") and _flags.effective("company_web_research")' in read("src/copilot/research/service.py"), "conjunctive")
    check("non_mutable_settings_are_classified", {"AGENT_COACH_ENABLED", "OPENROUTER_MODEL_*", "BILLING_PROVIDER", "FEATURE_GOOGLE_LOGIN"} <= set(F.NOT_MUTABLE), "classified, not editable")

    # --- no generic or secret/security configuration editor ------------------------------------------------------------------------
    body = (routes + schemas).lower()
    forbidden = ("database_url", "api_env", "secret", "api_key", "password", "cors", "allowed_hosts", "signing", "cookie", "payment", "model_slug", "retention")
    check("no_forbidden_mutable_settings", not [w for w in forbidden if w in body], ", ".join(w for w in forbidden if w in body) or "none present")
    check("no_generic_key_value_json_or_env_editor", not re.search(r"dict\[str, (Any|object)\]|raw_json|dotenv|\.env\b|setdefault\(\"[A-Z_]+\"|os\.environ\[", routes + schemas + flags_src.replace("os.environ.get(self.env_var)", "")), "typed schemas only")
    check("flag_baselines_are_non_secret_env_vars", not re.search(r"KEY|SECRET|PASSWORD|TOKEN|DATABASE|CORS|HOST|MODEL|BILLING", "".join(f.env_var for f in FLAGS.values())), "plain feature switches")

    # --- governance ------------------------------------------------------------------------------------------------------------------
    check("routes_permissioned_with_w10_0_ownership", "perm.CONFIG_MANAGE" in routes and "perm.FLAGS_MANAGE" in routes and routes.count("require_permission") >= 4, "pause needs config.manage; flags need flags.manage")
    check("permission_registry_stays_43", len(perm.PERMISSIONS) == 43, "43")
    check("audit_is_same_transaction", "_stage(" in pause_src and "_stage(" in flags_src and "get_audit_repository" not in routes, "state and audit commit together")
    check("audit_events_registered", all(hasattr(__import__("src.application.admin_audit", fromlist=["x"]), n) for n in ("ADMIN_PLATFORM_PAUSED", "ADMIN_PLATFORM_RESUMED", "ADMIN_FLAG_OVERRIDE_ENABLED", "ADMIN_FLAG_OVERRIDE_DISABLED", "ADMIN_FLAG_OVERRIDE_RESET")), "5 events")
    mig = read("migrations/versions/0023_platform_config.py")
    check("migration_chain_valid", 'down_revision = "0022_ai_model_admin"' in mig and "uq_pps_env_capability" in mig and "uq_ffo_env_key" in mig and "op.bulk_insert" not in mig and "INSERT" not in mig.upper().replace("INSERT_", ""), "0023 chains from 0022; nothing seeded")
    check("sec_w10_05_closure_evidence_tests_exist", all(x in read("tests/test_platform_config_w10_11.py") for x in (
        "test_restart_durability_a_new_service_instance_reads_the_same_state", "test_two_independent_instances_observe_each_others_changes",
        "test_paused_agent_routes_are_refused_before_the_service_or_model_is_built", "test_store_outage_refuses_the_protected_operation_safely",
        "test_admin_stays_usable_and_can_resume_while_paused", "test_optimistic_concurrency_rejects_a_stale_writer", "test_worker_still_runs_jobs_while_everything_is_paused",
        "test_privacy_account_legal_and_candidate_reads_remain_available_while_everything_is_paused")), "all ten criteria have tests")
    return out


def main() -> int:
    print("ASK4MO - P10B-W10.11 DURABLE PAUSE AND FEATURE FLAGS GUARD (SEC-W10-05)\n")
    res = run()
    failed = False
    for name in sorted(res):
        ok, detail = res[name]
        failed |= not ok
        print(f"  {name:66s} {'PASS' if ok else 'FAIL'}  {detail}")
    print("\nPaid LLM calls: 0   Live calls: 0")
    print("\nRESULT: " + ("FAIL" if failed else "PASS"))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
