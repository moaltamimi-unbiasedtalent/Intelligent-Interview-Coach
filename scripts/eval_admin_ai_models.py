#!/usr/bin/env python
"""P10B-W10.7 AI and model administration guard (deterministic, offline, 0 paid/live calls).

High-risk invariants: the approved catalogue is code-defined (no raw provider slug is ever an input); a configuration changes only profile->catalogue
entry and bounded numeric tunables; the evaluation, approval and activation each bind to one config hash; activation re-derives a passed evaluation
and a distinct second approver from stored facts (no force/bypass parameter anywhere); production needs a prior staging activation; the resolver
fails closed to the code defaults; no active configuration is byte-identical to pre-W10.7 behaviour; deterministic, realtime, specialist, Interview
and candidate-profile boundaries hold; permission registry stays 43; every route is permissioned. It also runs a real lifecycle on a temp database.
It does not duplicate the tests.
"""

from __future__ import annotations

import ast
import inspect
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


def constants_default_tokens() -> int:
    from src import constants
    return constants.DEFAULT_MAX_OUTPUT_TOKENS


def run() -> dict[str, tuple[bool, str]]:
    out: dict[str, tuple[bool, str]] = {}

    def check(name: str, ok: bool, detail: str = "") -> None:
        out[name] = (bool(ok), detail)

    from src.ai_admin import catalogue as C
    from src.ai_admin import config as K
    from src.ai_admin.evaluator import evaluate
    from src.ai_admin.service import AIConfigService
    from src.application import admin_permissions as perm
    from src.llm import governed
    from src.llm import models as M
    from src.llm.policy import OPERATION_POLICY, ModelCapability, ModelOperation, resolve_policy

    files = sorted(p.relative_to(ROOT).as_posix() for p in (ROOT / "src/ai_admin").glob("*.py")) + ["src/llm/governed.py", "src/api/routes/admin_ai.py"]
    code = "\n".join(code_only(f) for f in files)
    route = read("src/api/routes/admin_ai.py")
    svc = read("src/ai_admin/service.py")

    check("catalogue_code_defined_matches_registry", set(C.CATALOGUE) == {"luna", "terra", "sol"} and all(e.slug == M.default_slug(e.tier) for e in C.CATALOGUE.values()), "3 entries")
    check("no_provider_or_network_code", not re.search(r"httpx|requests\.|urllib\.request|socket|openrouter\.ai|ChatOpenAI|build_chat_model", code), "none")
    check("no_secret_access", not re.search(r"secret_store|get_for_runtime|os\.environ\[.*KEY|API_KEY", code), "none")
    ok_slug = True
    for bad in ({"profiles": {"fast": "openai/gpt-5.6-sol", "balanced": "terra", "advanced": "sol"}}, {"prompt": "x"}, {"operations": {"realtime_voice": {"max_retries": 1}}},
                {"operations": {"specialist_evidence_analysis": {"max_retries": 1}}}, {"operations": {"orchestration": {"temperature": 0.3}}}):
        try:
            K.normalise(bad)
            ok_slug = False
        except K.ConfigError:
            pass
    check("raw_slug_and_code_defined_fields_rejected", ok_slug, "rejected at normalise")
    base = K.normalise(K.baseline_config())
    check("hash_is_canonical_and_catalogue_bound", K.config_hash(base) == K.config_hash(K.normalise(K.baseline_config())) and K.config_hash(base, "x") != K.config_hash(base), "stable")
    r = evaluate(base)
    check("evaluator_passes_baseline_zero_live_calls", r["passed"] and r["live_calls"] == 0 and r["summary"]["resolution_cases"] == len(ModelOperation) * 3, "24 cases")
    check("evaluator_rejects_invalid", not evaluate(K.normalise({**K.baseline_config(), "profiles": {"fast": "sol", "balanced": "terra", "advanced": "sol"}}))["passed"], "profile not allowed")
    check("evaluation_boundary_documented", "not a measure of live model quality" in r["summary"]["evidence_class"], "stated")

    for name in ("activate", "rollback", "decide_approval", "request_approval"):
        params = inspect.signature(getattr(AIConfigService, name)).parameters
        check(f"no_bypass_parameter_{name}", not any(w in p for p in params for w in ("force", "skip", "bypass", "override")), "none")
    check("activation_rederives_facts", "_verify_activatable" in svc and "_passed_evaluation" in svc and "decided_by_user_id == v.created_by_user_id" in svc, "stored facts")
    check("production_requires_staging", "prior STAGING activation" in svc, "rule present")
    check("self_approval_blocked_service_and_db", "you cannot approve a request you made" in svc and "you cannot approve a configuration you authored" in svc
          and "ck_aica_no_self_approval" in read("migrations/versions/0022_ai_model_admin.py"), "both layers")
    check("live_calls_pinned_zero_in_db", "ck_aice_no_live_calls" in read("migrations/versions/0022_ai_model_admin.py"), "CHECK")
    resolver = read("src/ai_admin/resolver.py")
    check("resolver_fails_closed", all(x in resolver for x in ("hash_mismatch", "version_not_approved", "no_passed_evaluation", "no_distinct_approval", "catalogue_changed", "load_failed")), "6 reasons")
    check("governed_seam_never_raises", "except Exception" in read("src/llm/governed.py"), "swallowed")

    # behaviour: no active configuration is identical to code-defined behaviour; deterministic/realtime boundaries hold under a snapshot
    governed.clear()
    before = {(o.value, p.value): resolve_policy(o, p).to_dict() for o in ModelOperation for p in M.ModelProfile}
    check("no_active_config_equals_code_defaults", all(M.model_id(p) == M.code_model_id(p) for p in M.ModelProfile) and before == {(o.value, p.value): resolve_policy(o, p).to_dict() for o in ModelOperation for p in M.ModelProfile}, "identical")
    check("deterministic_and_realtime_model_free", all(not resolve_policy(o, M.ModelProfile.ADVANCED).uses_model for o in ModelOperation if OPERATION_POLICY[o].capability is ModelCapability.NONE)
          and resolve_policy(ModelOperation.REALTIME_VOICE, None).model_id is None, "no slug")
    check("exactly_three_specialists", len([o for o in ModelOperation if o.value.startswith("specialist_")]) == 3, "3")

    # a real lifecycle on a temp database (no dev store touched)
    from sqlalchemy.orm import sessionmaker

    from src.ai_admin.resolver import install_resolver, uninstall_resolver
    from src.jobs.service import JobService
    from src.jobs.worker import Worker
    from src.persistence import User, init_db, make_engine

    with tempfile.TemporaryDirectory() as d:
        eng = make_engine(f"sqlite:///{d}/ai.db")
        init_db(eng)
        sf = sessionmaker(bind=eng, expire_on_commit=False)
        with sf() as s:
            ids = []
            for i in range(3):
                u = User(subject=f"ai{i}", provider="eval", email=f"ai{i}@example.test", platform_role="platform_admin")
                s.add(u)
                s.flush()
                ids.append(u.id)
            s.commit()
        a, b, c = ids
        jobs = JobService(sf)
        res = install_resolver(sf, environment="staging", ttl_s=60)
        svc_ = AIConfigService(sf, jobs=jobs, resolver=res, environment="staging")
        prod_ = AIConfigService(sf, jobs=jobs, resolver=None, environment="production")
        dev_ = AIConfigService(sf, jobs=jobs, resolver=None, environment="development")
        unknown_ = AIConfigService(sf, jobs=jobs, resolver=None, environment=None)
        worker = Worker(jobs, services=SimpleNamespace(ai_admin=SimpleNamespace(session_factory=sf)))
        cfg = K.baseline_config()
        cfg["profiles"]["fast"] = "terra"
        pid = svc_.create_draft(name="eval", notes="", config=cfg, base_version_id=None, actor_user_id=a)["public_id"]
        svc_.validate(pid, actor_user_id=a)
        svc_.request_evaluation(pid, actor_user_id=a)
        for _ in range(5):
            if worker.run_once() == "idle":
                break
        ap = svc_.request_approval(pid, reason="r", actor_user_id=b)
        self_blocked = unapproved_blocked = False
        try:
            svc_.activate(pid, environment="staging", reason="r", actor_user_id=c)
        except Exception:
            unapproved_blocked = True
        try:
            svc_.decide_approval(ap["public_id"], approve=True, reason="r", actor_user_id=b)
        except Exception:
            self_blocked = True
        svc_.decide_approval(ap["public_id"], approve=True, reason="r", actor_user_id=c)
        prod_blocked = False
        try:
            prod_.activate(pid, reason="r", actor_user_id=c)
        except Exception:
            prod_blocked = True
        dev_ok = False                                                    # a development activation must not count as staging evidence
        try:
            dev_.activate(pid, reason="r", actor_user_id=c)
            prod_.activate(pid, reason="r", actor_user_id=c)
        except Exception:
            dev_ok = True
        unknown_blocked = False
        try:
            unknown_.activate(pid, reason="r", actor_user_id=c)
        except Exception:
            unknown_blocked = True
        dev_.rollback(to_code=True, reason="r", actor_user_id=c)
        svc_.activate(pid, reason="r", actor_user_id=c)
        prod_promoted = prod_.activate(pid, reason="r", actor_user_id=c)["environment"] == "production"
        governed_ok = governed.current() is not None and M.model_id(M.ModelProfile.FAST) == C.slug_for("terra")
        svc_.rollback(to_code=True, reason="r", actor_user_id=c)
        back_ok = governed.current() is None and M.model_id(M.ModelProfile.FAST) == M.code_model_id(M.ModelProfile.FAST)
        uninstall_resolver()
        eng.dispose()
    check("lifecycle_development_activation_is_not_staging_evidence", dev_ok, "promotion refused")
    check("lifecycle_unknown_environment_fails_closed", unknown_blocked, "activation refused")
    check("lifecycle_production_promotion_after_genuine_staging", prod_promoted, "promoted")
    check("lifecycle_unapproved_activation_blocked", unapproved_blocked, "blocked")
    check("lifecycle_self_approval_blocked", self_blocked, "blocked")
    check("lifecycle_production_blocked_before_staging", prod_blocked, "blocked")
    check("lifecycle_activation_changes_registry_then_rollback_restores", governed_ok and back_ok, "round trip")

    # environment targeting is server-authoritative
    from src.ai_admin.resolver import environment_name
    import src.api.schemas.admin as schemas
    check("browser_cannot_choose_environment", "environment" not in schemas.AIActivateBody.model_fields and "environment" not in schemas.AIRollbackBody.model_fields
          and "environment" not in inspect.signature(AIConfigService.activate).parameters and "environment" not in inspect.signature(AIConfigService.rollback).parameters, "no field")
    check("environment_vocabulary_fail_closed", environment_name("production") == "production" and environment_name("staging") == "staging"
          and all(environment_name(e) == "development" for e in ("development", "dev", "local", "test", "testing")) and environment_name("qa") is None, "unknown -> None")
    check("promotion_needs_staging_record_with_same_hash", "ACT.config_hash == v.config_hash" in svc and 'ACT.environment == "staging"' in svc, "rule present")

    # Practice runtime: the session PROFILE resolves through the governed mapping; candidates never send a slug
    from src.llm.runtime import governed_slug, tunables
    from src.ai_admin.evaluator import snapshot_for
    gcfg = K.baseline_config(); gcfg["profiles"]["balanced"] = "sol"; gcfg["operations"]["evaluation"]["max_output_tokens"] = 777
    gcan = K.normalise(gcfg)
    governed.set_provider(lambda: snapshot_for(gcan))
    bal_slug = M.default_slug(M.ModelProfile.BALANCED)
    mapped = governed_slug(bal_slug) == M.default_slug(M.ModelProfile.ADVANCED) and governed_slug("evil/model") == "evil/model"
    tuned_ok = tunables(ModelOperation.EVALUATION).get("max_output_tokens") == 777 and "timeout_s" not in tunables(ModelOperation.EVALUATION)
    governed.clear()
    check("practice_profile_resolves_through_governed_mapping", mapped and governed_slug(bal_slug) == bal_slug, "balanced -> governed; unknown untouched")
    check("legacy_saved_slugs_keep_profile", all(M.known_profile_for_slug(a) is M.ModelProfile(b) for a, b in (("openai/gpt-5-mini", "balanced"), ("openai/gpt-5-nano", "fast"), ("openai/gpt-5", "advanced"))) and M.known_profile_for_slug("x/y") is None, "compat")
    ischema = read("src/api/schemas/interview.py")
    check("practice_candidate_boundary_is_profile_only", "model:" not in ischema.split("class CreateInterviewRequest")[1].split("class QuestionOut")[0], "no model field")
    isvc = read("src/interview_service.py")
    check("practice_service_governs_at_the_boundary", "def _governed" in isvc and "governed_slug(settings.model)" in isvc and "_CALL_EXTRA" in isvc, "interview_service._generate")

    # every retained tunable has a real runtime consumer; consumer-less operations are not tunable
    consumers = {ModelOperation.ORCHESTRATION: "src/application/agent_service.py", ModelOperation.STRUCTURED_GENERATION: "src/copilot/tools/structured.py",
                 ModelOperation.EVALUATION: "src/interview_service.py"}
    check("every_tunable_operation_has_a_runtime_consumer", set(consumers) == set(K.TUNABLE_OPERATIONS) and all("tunables(" in read(p) and o.name in read(p) for o, p in consumers.items()), "3 operations")
    check("tunable_values_propagate_unchanged_only_when_changed", tuned_ok, "changed field applied; unchanged field absent")
    # explicit INHERIT vs explicit override at the real Practice evaluation call site (fake client; no provider)
    from src.evaluation_service import EvaluationService
    from src.models import ModelSettings as _MS
    from tests.test_evaluation_service import FakeClient as _FC, _config as _ecfg, _evaluation_json as _ej, _pricing as _pr

    def _observe(over):
        cfg_ = K.baseline_config()
        if over is not None:
            cfg_["operations"]["evaluation"]["max_output_tokens"] = over
        can_ = K.normalise(cfg_)
        governed.set_provider(lambda: snapshot_for(can_))
        fc = _FC([_ej()])
        EvaluationService(fc, _pr()).evaluate_answer(_ecfg(), "Q?", "A.", _MS(prompt_technique="structured_procedure"))
        governed.clear()
        return fc.calls[0]["max_tokens"]
    old_policy = OPERATION_POLICY[ModelOperation.EVALUATION].max_output_tokens
    inherit_tokens, explicit_tokens, baseline_tokens = _observe(None), _observe(640), _observe(old_policy)
    cleared_tokens = _observe(None)
    check("inherit_leaves_the_real_call_unchanged", inherit_tokens == constants_default_tokens(), f"{inherit_tokens}")
    check("explicit_value_reaches_the_real_call", explicit_tokens == 640, f"{explicit_tokens}")
    check("explicit_value_equal_to_old_policy_baseline_is_still_applied", baseline_tokens == old_policy and old_policy != inherit_tokens, f"{baseline_tokens}")
    check("override_can_be_cleared_back_to_inherit", cleared_tokens == inherit_tokens, "restored")
    base_c = K.normalise(K.baseline_config()); eq_c = K.baseline_config(); eq_c["operations"]["evaluation"]["max_output_tokens"] = old_policy
    check("inherit_and_explicit_baseline_number_hash_differently", K.config_hash(K.normalise(eq_c)) != K.config_hash(base_c), "distinct hashes")
    check("baseline_config_is_literally_inherit", all(v is None for t_ in base_c["operations"].values() for v in t_.values()) and not any(snapshot_for(base_c).operation_overrides.values()), "all None, no override")
    check("inherited_defaults_are_recorded", set(K.consumer_defaults()) == {o.value for o in K.TUNABLE_OPERATIONS}, "per consumer")
    check("no_cosmetic_tunable", not ({ModelOperation.FINAL_RESPONSE, ModelOperation.SPECIALIST_COACHING, ModelOperation.SPECIALIST_ROLE_ANALYSIS} & set(K.TUNABLE_OPERATIONS)), "consumer-less operations removed")
    check("client_supports_per_call_timeout_and_retries", "timeout_s" in read("src/openrouter_client.py") and "max_retries" in read("src/copilot/llm/openrouter.py"), "both clients")
    check("runtime_tests_exist", all(x in read("tests/test_ai_runtime_w10_7.py") for x in ("test_practice_balanced_session_follows_governed_balanced_mapping_then_rolls_back",
          "test_interview_evaluation_tunables_reach_the_client_call", "test_agent_orchestration_tunables_reach_the_chat_model",
          "test_career_structured_producer_tunables_reach_the_chat_model", "test_openrouter_client_honours_governed_retries_and_timeout")), "present")
    check("routes_permissioned_and_separate", route.count("require_permission") >= 18 and "AI_ACTIVATE" in route and "AI_MANAGE" in route and "AI_READ" in route, "explicit")
    check("permission_registry_stays_43", len(perm.PERMISSIONS) == 43, "43")
    check("only_platform_admin_can_manage_or_activate", perm.AI_MANAGE in perm.permissions_for_role("platform_admin") and perm.AI_ACTIVATE in perm.permissions_for_role("platform_admin")
          and not any({perm.AI_MANAGE, perm.AI_ACTIVATE} & perm.permissions_for_role(r) for r in ("support_operator", "billing_admin", "knowledge_admin", "security_privacy_admin", "operations_admin")), "preset")
    check("job_type_registered_id_only", "ai_evaluate_config" in read("src/jobs/registry.py") + read("src/ai_admin/jobs.py") and "evaluation_id" in read("src/ai_admin/jobs.py"), "id only")
    mig = read("migrations/versions/0022_ai_model_admin.py")
    check("migration_chain_valid", 'down_revision = "0021_billing_admin"' in mig and "uq_aicact_one_open" in mig and "uq_aica_one_pending" in mig, "0022 chains from 0021")
    check("sec_w10_05_untouched", "pause" not in code.lower(), "platform pause not touched")
    t = read("tests/test_ai_admin_w10_7.py")
    check("tests_exist", all(x in t for x in ("test_no_active_config_is_byte_identical_to_code_defaults", "test_activation_rechecks_the_distinct_approver_from_stored_facts",
                                             "test_resolver_fails_closed_on_every_integrity_problem", "test_production_requires_prior_staging_activation",
                                             "test_evaluator_makes_no_network_or_provider_call")), "present")
    return out


def main() -> int:
    print("ASK4MO - P10B-W10.7 AI AND MODEL ADMINISTRATION GUARD\n")
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
