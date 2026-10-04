"""P10B-W10.7: governed AI and model administration. Offline and deterministic: temp DB, the W10.9 worker, no provider, no network.
The load-bearing property under test: a configuration is never active without a PASSED evaluation of its exact hash and a DISTINCT second approver."""

from __future__ import annotations

import copy
import socket
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import select, text, update
from sqlalchemy.exc import IntegrityError

from src.ai_admin import catalogue as C
from src.ai_admin import config as K
from src.ai_admin.evaluator import EVALUATOR_VERSION, evaluate
from src.ai_admin.resolver import GovernedResolver, environment_name, install_resolver, runtime_view, uninstall_resolver
from src.ai_admin.service import AIConfigService, AIConflict, AIForbidden, AINotFound, AIValidationError
from src.application import admin_audit as A
from src.application import admin_permissions as perm
from src.jobs.service import JobService
from src.jobs.worker import Worker
from src.llm import governed
from src.llm import models as M
from src.llm.policy import OPERATION_POLICY, ModelOperation, resolve_policy
from src.persistence import AIConfigActivation, AIConfigApproval, AIConfigEvaluation, AIConfigVersion, User
from tests.test_admin_foundation_w10_1 import Env

API = "/api/v1"
ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture()
def env():
    e = Env()
    yield e
    e.close()


def sf(env):
    return env.accounts.session_factory


class Rig:
    def __init__(self, env, environment="staging"):
        self.env = env
        self.jobs = JobService(sf(env))
        self.resolver = install_resolver(sf(env), environment=environment, ttl_s=60)
        self.svc = AIConfigService(sf(env), jobs=self.jobs, resolver=self.resolver, environment=environment)
        self.worker = Worker(self.jobs, services=SimpleNamespace(ai_admin=SimpleNamespace(session_factory=sf(env))))
        self.a, _ = env.user("platform_admin")
        self.b, _ = env.user("platform_admin")
        self.c, _ = env.user("platform_admin")

    def drain(self):
        for _ in range(10):
            if self.worker.run_once() == "idle":
                break

    def evaluated(self, config=None, author=None):
        d = self.svc.create_draft(name="cfg", notes="", config=config, base_version_id=None, actor_user_id=author or self.a)
        self.svc.validate(d["public_id"], actor_user_id=self.a)
        self.svc.request_evaluation(d["public_id"], actor_user_id=self.a)
        self.drain()
        return d["public_id"]

    def approved(self, config=None, author=None):
        pid = self.evaluated(config, author)
        ap = self.svc.request_approval(pid, reason="ready", actor_user_id=self.b)
        self.svc.decide_approval(ap["public_id"], approve=True, reason="ok", actor_user_id=self.c)
        return pid

    def state(self, pid):
        return self.svc.get_version(pid)["state"]


@pytest.fixture()
def rig(env):
    r = Rig(env)
    yield r
    uninstall_resolver()


def cfg(**profiles):
    c = K.baseline_config()
    c["profiles"].update(profiles)
    return c


# ---------------- catalogue + config ---------------------------------------------------------------------------------------

def test_catalogue_is_code_defined_and_matches_the_registry():
    assert set(C.CATALOGUE) == {"luna", "terra", "sol"}
    for entry in C.CATALOGUE.values():
        assert entry.slug == M.default_slug(entry.tier)
        assert entry.supports_tools and entry.supports_structured_output and not entry.supports_temperature
    assert C.BASELINE_PROFILES == {"fast": "luna", "balanced": "terra", "advanced": "sol"}


def test_baseline_normalises_validates_and_hashes_stably():
    base = K.normalise(K.baseline_config())
    assert K.passed(K.validate(base))
    assert K.config_hash(base) == K.config_hash(K.normalise(copy.deepcopy(base)))
    shuffled = {"operations": dict(reversed(list(base["operations"].items()))), "profiles": dict(reversed(list(base["profiles"].items()))), "schema": 1}
    assert K.config_hash(K.normalise(shuffled)) == K.config_hash(base)
    assert K.diff_from_baseline(base) == []


def test_hash_changes_with_content_and_with_catalogue_version():
    base = K.normalise(K.baseline_config())
    changed = copy.deepcopy(base)
    changed["operations"]["orchestration"]["max_retries"] = 1
    assert K.config_hash(changed) != K.config_hash(base)
    assert K.config_hash(base, "other") != K.config_hash(base)


def test_tunable_operations_exclude_deterministic_and_realtime():
    names = {o.value for o in K.tunable_operations()}
    assert "specialist_evidence_analysis" not in names and "realtime_voice" not in names
    assert names == set(K.baseline_config()["operations"])


@pytest.mark.parametrize("bad", [
    {"profiles": {"fast": "openai/gpt-5.6-sol", "balanced": "terra", "advanced": "sol"}},
    {"profiles": {"fast": "luna", "balanced": "terra"}},
    {"profiles": {"fast": "luna", "balanced": "terra", "advanced": "sol", "extra": "sol"}},
    {"operations": {"specialist_evidence_analysis": {"max_retries": 1}}},
    {"operations": {"realtime_voice": {"timeout_s": 20}}},
    {"operations": {"orchestration": {"temperature": 0.2}}},
    {"operations": {"orchestration": {"min_capability": "fast"}}},
    {"operations": {"orchestration": {"max_retries": True}}},
    {"operations": {"orchestration": {"max_retries": 1.5}}},
    {"prompt": "x"}, {"secret": "x"}, {"schema": 2}, "text", [], None,
])
def test_malformed_or_code_defined_fields_are_rejected_without_echo(bad):
    with pytest.raises(K.ConfigError) as exc:
        K.normalise(bad)
    assert "gpt" not in str(exc.value) and "secret" not in str(exc.value).lower()


def _check(config, code):
    return next(c for c in K.validate(K.normalise(config)) if c.code == code)


def test_semantic_validation_checks():
    assert _check(cfg(fast="terra", balanced="terra", advanced="terra"), "profile_allowed").passed
    assert not _check(cfg(fast="sol"), "profile_allowed").passed            # sol is not approved for Fast
    assert not _check(cfg(fast="terra", balanced="luna", advanced="sol"), "tier_monotonic").passed
    ok = cfg(); ok["operations"] = {"orchestration": {"max_output_tokens": 100}}
    assert not _check(ok, "tunable_bounds").passed
    ok = cfg(); ok["operations"] = {"orchestration": {"timeout_s": 180, "max_retries": 3}}
    assert not _check(ok, "time_budget").passed
    assert _check(cfg(), "no_raw_provider_slug").passed
    assert _check(cfg(), "capability_support").passed and _check(cfg(), "floors_preserved").passed


# ---------------- governed seam + resolver ---------------------------------------------------------------------------------

def test_no_active_config_is_byte_identical_to_code_defaults(env):
    before = {p: (M.model_id(p), M.spec(p)) for p in M.ModelProfile}
    pol = {(o, p): resolve_policy(o, p).to_dict() for o in ModelOperation for p in M.ModelProfile}
    install_resolver(sf(env), environment="staging", ttl_s=0)
    assert governed.current() is None
    assert {p: (M.model_id(p), M.spec(p)) for p in M.ModelProfile} == before
    assert {(o, p): resolve_policy(o, p).to_dict() for o in ModelOperation for p in M.ModelProfile} == pol
    for p in M.ModelProfile:
        assert M.model_id(p) == M.code_model_id(p)


def test_env_override_still_wins_when_nothing_is_active(env, monkeypatch):
    monkeypatch.setenv("OPENROUTER_MODEL_FAST", "vendor/custom-fast")
    install_resolver(sf(env), ttl_s=0)
    assert M.model_id(M.ModelProfile.FAST) == "vendor/custom-fast"
    assert M.profile_for_model("vendor/custom-fast") is M.ModelProfile.FAST
    assert runtime_view()["profiles"]["fast"]["source"] == "environment_override"


def test_governed_snapshot_changes_slug_and_tunables_only(rig):
    legal = cfg(fast="terra")
    legal["operations"] = {"orchestration": {"max_output_tokens": 2048, "timeout_s": 90.0, "max_retries": 1}}
    pid = rig.approved(legal)
    rig.svc.activate(pid, reason="go", actor_user_id=rig.c)
    snap = governed.current()
    assert snap and snap.version_public_id == pid
    assert M.model_id(M.ModelProfile.FAST) == C.slug_for("terra") and M.model_id(M.ModelProfile.ADVANCED) == C.slug_for("sol")
    r = resolve_policy(ModelOperation.ORCHESTRATION, M.ModelProfile.BALANCED)
    assert (r.max_output_tokens, r.timeout_s, r.max_retries) == (2048, 90.0, 1)
    base = OPERATION_POLICY[ModelOperation.ORCHESTRATION]
    assert (r.capability, r.structured_output, r.requires_tools, r.temperature) == (base.capability, base.structured_output, base.requires_tools, base.temperature)
    assert resolve_policy(ModelOperation.SPECIALIST_EVIDENCE_ANALYSIS, None).model_id is None
    assert resolve_policy(ModelOperation.REALTIME_VOICE, None).model_id is None


def test_resolver_fails_closed_on_every_integrity_problem(rig):
    pid = rig.approved()
    rig.svc.activate(pid, reason="go", actor_user_id=rig.c)
    assert rig.resolver().version_public_id == pid
    with sf(rig.env)() as s:
        v = s.scalar(select(AIConfigVersion).where(AIConfigVersion.public_id == pid))
        tampered = copy.deepcopy(v.config_json); tampered["operations"]["orchestration"]["max_retries"] = 3
        s.execute(update(AIConfigVersion).where(AIConfigVersion.id == v.id).values(config_json=tampered)); s.commit()
    rig.resolver.invalidate()
    assert rig.resolver() is None and rig.resolver.last_error == "hash_mismatch"
    assert M.model_id(M.ModelProfile.BALANCED) == M.code_model_id(M.ModelProfile.BALANCED)


def test_resolver_rejects_hand_edited_rows(rig):
    pid = rig.approved()
    rig.svc.activate(pid, reason="go", actor_user_id=rig.c)

    def reset(**vals):
        with sf(rig.env)() as s:
            s.execute(update(AIConfigVersion).where(AIConfigVersion.public_id == pid).values(**vals)); s.commit()
        rig.resolver.invalidate()

    reset(state="evaluated"); assert rig.resolver() is None and rig.resolver.last_error == "version_not_approved"
    reset(state="approved"); assert rig.resolver() is not None
    with sf(rig.env)() as s:
        s.execute(update(AIConfigEvaluation).values(status="failed")); s.commit()
    rig.resolver.invalidate()
    assert rig.resolver() is None and rig.resolver.last_error == "no_passed_evaluation"


def test_resolver_survives_missing_tables_and_caches():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    bad = GovernedResolver(sessionmaker(bind=create_engine("sqlite://")), environment="staging", ttl_s=60)
    assert bad() is None and bad.last_error == "load_failed"
    n = bad.loads
    bad(); bad()
    assert bad.loads == n                                   # cached within the TTL
    bad.invalidate(); bad()
    assert bad.loads == n + 1


def test_environment_vocabulary_is_server_authoritative_and_fails_closed():
    assert environment_name("production") == environment_name("prod") == "production"
    assert environment_name("staging") == "staging"
    for dev in ("development", "dev", "local", "test", "testing"):
        assert environment_name(dev) == "development"
    for unknown in ("anything", "qa", "preprod", "stagingg", "Production2"):
        assert environment_name(unknown) is None                         # never staging, never production


def test_resolver_cache_serves_many_calls_with_one_query(rig):
    rig.resolver.invalidate()
    for _ in range(200):
        M.model_id(M.ModelProfile.BALANCED)
    assert rig.resolver.loads <= 2


def test_provider_exception_never_reaches_the_registry():
    governed.set_provider(lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    assert governed.current() is None
    assert M.model_id(M.ModelProfile.FAST) == M.code_model_id(M.ModelProfile.FAST)
    governed.clear()


# ---------------- lifecycle ------------------------------------------------------------------------------------------------

def test_happy_path_lifecycle_and_hash_attribution(rig):
    d = rig.svc.create_draft(name="first", notes="n", config=None, base_version_id=None, actor_user_id=rig.a)
    pid = d["public_id"]
    assert d["state"] == "draft" and d["content_hash"] == K.config_hash(K.normalise(K.baseline_config()))
    assert rig.svc.validate(pid, actor_user_id=rig.a)["state"] == "validated"
    ev = rig.svc.request_evaluation(pid, actor_user_id=rig.a)
    assert ev["status"] == "queued"
    rig.drain()
    detail = rig.svc.get_version(pid)
    assert detail["state"] == "evaluated" and detail["latest_evaluation_passed"]
    e = detail["evaluations"][0]
    assert e["status"] == "passed" and e["content_hash"] == detail["content_hash"] and e["evaluator_version"] == EVALUATOR_VERSION and e["live_calls"] == 0
    assert any(c["code"] == "resolution_matrix" and c["passed"] for c in e["checks"])
    ap = rig.svc.request_approval(pid, reason="ready", actor_user_id=rig.b)
    assert ap["content_hash"] == detail["content_hash"]
    rig.svc.decide_approval(ap["public_id"], approve=True, reason="ok", actor_user_id=rig.c)
    assert rig.state(pid) == "approved"
    act = rig.svc.activate(pid, reason="go", actor_user_id=rig.c)
    assert act["open"] and act["content_hash"] == detail["content_hash"]


def test_only_drafts_are_editable_and_content_freezes(rig):
    d = rig.svc.create_draft(name="x", notes="", config=None, base_version_id=None, actor_user_id=rig.a)
    rig.svc.update_draft(d["public_id"], name="y", actor_user_id=rig.a)
    new = cfg(); new["operations"] = {"orchestration": {"max_retries": 1}}
    updated = rig.svc.update_draft(d["public_id"], config=new, actor_user_id=rig.a)
    assert updated["content_hash"] != d["content_hash"]
    rig.svc.validate(d["public_id"], actor_user_id=rig.a)
    with pytest.raises(AIConflict):
        rig.svc.update_draft(d["public_id"], name="z", actor_user_id=rig.a)
    with pytest.raises(AIConflict):
        rig.svc.validate(d["public_id"], actor_user_id=rig.a)


def test_failed_validation_keeps_draft_and_blocks_evaluation(rig):
    bad = cfg(fast="sol")
    d = rig.svc.create_draft(name="bad", notes="", config=bad, base_version_id=None, actor_user_id=rig.a)
    v = rig.svc.validate(d["public_id"], actor_user_id=rig.a)
    assert v["state"] == "draft" and not v["validation_passed"]
    with pytest.raises(AIConflict):
        rig.svc.request_evaluation(d["public_id"], actor_user_id=rig.a)


def test_create_draft_from_base_copies_content(rig):
    pid = rig.evaluated()
    d2 = rig.svc.create_draft(name="next", notes="", config=None, base_version_id=pid, actor_user_id=rig.a)
    assert d2["content_hash"] == rig.svc.get_version(pid)["content_hash"] and d2["version"] > rig.svc.get_version(pid)["version"]


def test_cannot_approve_or_activate_without_a_passed_evaluation(rig):
    d = rig.svc.create_draft(name="x", notes="", config=None, base_version_id=None, actor_user_id=rig.a)
    rig.svc.validate(d["public_id"], actor_user_id=rig.a)
    with pytest.raises(AIConflict):
        rig.svc.request_approval(d["public_id"], reason="r", actor_user_id=rig.b)
    with pytest.raises(AIConflict):
        rig.svc.activate(d["public_id"], reason="r", actor_user_id=rig.c)


def test_failed_evaluation_blocks_the_path(rig):
    pid = rig.evaluated()
    with sf(rig.env)() as s:                       # simulate a failing verdict for the latest evaluation
        s.execute(update(AIConfigEvaluation).values(status="failed")); s.execute(update(AIConfigVersion).values(state="evaluation_failed")); s.commit()
    with pytest.raises(AIConflict):
        rig.svc.request_approval(pid, reason="r", actor_user_id=rig.b)


def test_evaluation_bound_to_hash_blocks_after_tampering(rig):
    pid = rig.evaluated()
    ap = rig.svc.request_approval(pid, reason="r", actor_user_id=rig.b)
    with sf(rig.env)() as s:
        v = s.scalar(select(AIConfigVersion).where(AIConfigVersion.public_id == pid))
        t = copy.deepcopy(v.config_json); t["operations"]["evaluation"]["max_retries"] = 3
        s.execute(update(AIConfigVersion).where(AIConfigVersion.id == v.id).values(config_json=t)); s.commit()
    with pytest.raises(AIConflict):
        rig.svc.decide_approval(ap["public_id"], approve=True, reason="ok", actor_user_id=rig.c)


def test_stale_evaluator_version_invalidates_the_evaluation(rig, monkeypatch):
    pid = rig.evaluated()
    import src.ai_admin.service as svc_mod
    monkeypatch.setattr(svc_mod, "EVALUATOR_VERSION", "ai-eval-2")
    with pytest.raises(AIConflict):
        rig.svc.request_approval(pid, reason="r", actor_user_id=rig.b)


# ---------------- second approver -------------------------------------------------------------------------------------------

def test_requester_cannot_approve_their_own_request(rig):
    pid = rig.evaluated(author=rig.a)
    ap = rig.svc.request_approval(pid, reason="r", actor_user_id=rig.b)
    with pytest.raises(AIForbidden):
        rig.svc.decide_approval(ap["public_id"], approve=True, reason="ok", actor_user_id=rig.b)


def test_author_cannot_approve_their_own_configuration(rig):
    pid = rig.evaluated(author=rig.a)
    ap = rig.svc.request_approval(pid, reason="r", actor_user_id=rig.b)
    with pytest.raises(AIForbidden):
        rig.svc.decide_approval(ap["public_id"], approve=True, reason="ok", actor_user_id=rig.a)
    assert rig.state(pid) == "evaluated"


def test_approver_needs_active_account_and_activation_permission(env, rig):
    pid = rig.evaluated()
    ap = rig.svc.request_approval(pid, reason="r", actor_user_id=rig.b)
    weak, _ = env.user("operations_admin")
    with pytest.raises(AIForbidden):
        rig.svc.decide_approval(ap["public_id"], approve=True, reason="ok", actor_user_id=weak)
    with sf(env)() as s:
        s.execute(update(User).where(User.id == rig.c).values(status="deactivated")); s.commit()
    with pytest.raises(AIForbidden):
        rig.svc.decide_approval(ap["public_id"], approve=True, reason="ok", actor_user_id=rig.c)


def test_db_forbids_self_decided_approval_rows(rig):
    pid = rig.evaluated()
    ap = rig.svc.request_approval(pid, reason="r", actor_user_id=rig.b)
    with sf(rig.env)() as s, pytest.raises(IntegrityError):
        s.execute(update(AIConfigApproval).where(AIConfigApproval.public_id == ap["public_id"]).values(decided_by_user_id=rig.b)); s.commit()


def test_one_pending_approval_and_rejection_is_terminal(rig):
    pid = rig.evaluated()
    ap = rig.svc.request_approval(pid, reason="r", actor_user_id=rig.b)
    with pytest.raises(AIConflict):
        rig.svc.request_approval(pid, reason="r", actor_user_id=rig.b)
    rig.svc.decide_approval(ap["public_id"], approve=False, reason="no", actor_user_id=rig.c)
    assert rig.state(pid) == "rejected"
    with pytest.raises(AIConflict):
        rig.svc.decide_approval(ap["public_id"], approve=True, reason="ok", actor_user_id=rig.c)
    with pytest.raises(AIConflict):
        rig.svc.activate(pid, reason="go", actor_user_id=rig.c)


def test_activation_rechecks_the_distinct_approver_from_stored_facts(rig):
    pid = rig.approved()
    with sf(rig.env)() as s:                                     # forge: approver == author, bypassing the service
        v = s.scalar(select(AIConfigVersion).where(AIConfigVersion.public_id == pid))
        s.execute(update(AIConfigApproval).where(AIConfigApproval.config_version_id == v.id).values(decided_by_user_id=v.created_by_user_id, requested_by_user_id=rig.b))
        s.commit()
    with pytest.raises(AIForbidden):
        rig.svc.activate(pid, reason="go", actor_user_id=rig.c)
    rig.resolver.invalidate()
    assert rig.resolver() is None


def test_there_is_no_bypass_or_force_in_the_service_surface():
    import inspect
    for name in ("activate", "rollback", "decide_approval", "request_approval"):
        params = inspect.signature(getattr(AIConfigService, name)).parameters
        assert not any(w in p for p in params for w in ("force", "skip", "bypass", "override")), name


# ---------------- activation / environments / rollback ----------------------------------------------------------------------

def svc_for(env, environment):
    """A service for another deployment environment over the SAME database (as a staging and a production process sharing a control plane)."""
    return AIConfigService(sf(env), jobs=JobService(sf(env)), resolver=None, environment=environment)


def test_production_requires_prior_staging_activation_of_the_same_hash(env, rig):
    pid = rig.approved()
    prod = svc_for(env, "production")
    with pytest.raises(AIConflict):
        prod.activate(pid, reason="go", actor_user_id=rig.c)                  # no staging record at all
    rig.svc.activate(pid, reason="stage", actor_user_id=rig.c)                # this rig is a STAGING process
    out = prod.activate(pid, reason="promote", actor_user_id=rig.c)
    assert out["environment"] == "production"
    envs = {e["environment"]: e for e in prod.environments()["items"]}
    assert envs["staging"]["mode"] == envs["production"]["mode"] == "governed" and envs["development"]["mode"] == "code_defaults"
    with sf(env)() as s:                                                      # a tampered hash on the staging record does not satisfy promotion
        s.execute(update(AIConfigActivation).where(AIConfigActivation.environment == "staging").values(config_hash="0" * 64)); s.commit()
        s.execute(update(AIConfigActivation).where(AIConfigActivation.environment == "production").values(deactivated_at=text("CURRENT_TIMESTAMP"))); s.commit()
    with pytest.raises(AIConflict):
        prod.activate(pid, reason="again", actor_user_id=rig.c)


def test_development_activation_is_not_staging_evidence_and_cannot_touch_production(env):
    r = Rig(env, environment="development")
    pid = r.approved()
    assert r.svc.activate(pid, reason="dev", actor_user_id=r.c)["environment"] == "development"
    prod = svc_for(env, "production")
    with pytest.raises(AIConflict):
        prod.activate(pid, reason="promote", actor_user_id=r.c)               # a development activation does not satisfy promotion
    with sf(env)() as s:
        assert [a.environment for a in s.scalars(select(AIConfigActivation)).all()] == ["development"]
    uninstall_resolver()


def test_test_environment_alias_is_development_not_staging(env):
    assert environment_name("test") == "development"
    r = Rig(env, environment=environment_name("test"))
    pid = r.approved()
    r.svc.activate(pid, reason="t", actor_user_id=r.c)
    with pytest.raises(AIConflict):
        svc_for(env, "production").activate(pid, reason="p", actor_user_id=r.c)
    uninstall_resolver()


def test_staging_process_activates_only_staging_and_cannot_write_production(env, rig):
    pid = rig.approved()
    assert rig.svc.activate(pid, reason="s", actor_user_id=rig.c)["environment"] == "staging"
    with sf(env)() as s:
        assert [a.environment for a in s.scalars(select(AIConfigActivation)).all()] == ["staging"]
    import inspect
    assert "environment" not in inspect.signature(AIConfigService.activate).parameters
    assert "environment" not in inspect.signature(AIConfigService.rollback).parameters


def test_production_process_cannot_fabricate_staging_evidence(env):
    r = Rig(env, environment="production")
    pid = r.approved()
    with pytest.raises(AIConflict):
        r.svc.activate(pid, reason="p", actor_user_id=r.c)
    with sf(env)() as s:
        assert s.scalars(select(AIConfigActivation)).all() == []
    uninstall_resolver()


def test_unknown_environment_fails_closed(env):
    r = Rig(env, environment=None)
    assert r.resolver.environment is None
    pid = r.approved()
    with pytest.raises(AIConflict):
        r.svc.activate(pid, reason="x", actor_user_id=r.c)
    with pytest.raises(AIConflict):
        r.svc.rollback(to_code=True, reason="x", actor_user_id=r.c)
    assert r.resolver() is None and r.resolver.last_error == "unsupported_environment"
    assert runtime_view(r.resolver)["environment"] == "unsupported"
    uninstall_resolver()


def test_browser_cannot_choose_the_environment(env):
    r = Rig(env, environment="development")
    _, plat = env.user("platform_admin"); _, b = env.user("platform_admin"); _, c3 = env.user("platform_admin")
    d = env.c.post(f"{API}/admin/ai/configs", json={"name": "x"}, cookies=plat).json()
    pid = d["public_id"]
    env.c.post(f"{API}/admin/ai/configs/{pid}/validate", cookies=plat); env.c.post(f"{API}/admin/ai/configs/{pid}/evaluate", cookies=plat); r.drain()
    ap = env.c.post(f"{API}/admin/ai/configs/{pid}/request-approval", json={"reason": "r"}, cookies=b).json()
    env.c.post(f"{API}/admin/ai/approvals/{ap['public_id']}/approve", json={"reason": "ok"}, cookies=c3)
    for body in ({"environment": "production", "reason": "go"}, {"environment": "staging", "reason": "go"}):
        assert env.c.post(f"{API}/admin/ai/configs/{pid}/activate", json=body, cookies=c3).status_code == 422       # the field does not exist
    assert env.c.post(f"{API}/admin/ai/environments/production/rollback", json={"reason": "x"}, cookies=c3).status_code == 404
    act = env.c.post(f"{API}/admin/ai/configs/{pid}/activate", json={"reason": "go"}, cookies=c3).json()
    assert act["environment"] == "development"                                                                          # the server's own environment
    uninstall_resolver()


def test_one_open_activation_per_environment_and_history_is_append_only(rig):
    p1 = rig.approved(); p2 = rig.approved(cfg(fast="terra"))
    rig.svc.activate(p1, reason="a", actor_user_id=rig.c)
    with pytest.raises(AIConflict):
        rig.svc.activate(p1, reason="again", actor_user_id=rig.c)
    rig.svc.activate(p2, reason="b", actor_user_id=rig.c)
    hist = rig.svc.history(environment="staging")["items"]
    assert [h["open"] for h in hist] == [True, False] and hist[1]["version"] < hist[0]["version"]
    with sf(rig.env)() as s, pytest.raises(IntegrityError):
        s.add(AIConfigActivation(public_id="x" * 32, environment="staging", kind="activate")); s.commit()


def test_rollback_to_previous_then_to_code_defaults(rig):
    p1 = rig.approved(); p2 = rig.approved(cfg(fast="terra"))
    rig.svc.activate(p1, reason="a", actor_user_id=rig.c)
    rig.svc.activate(p2, reason="b", actor_user_id=rig.c)
    assert governed.current().version_public_id == p2
    assert M.model_id(M.ModelProfile.FAST) == C.slug_for("terra")
    back = rig.svc.rollback(to_code=False, reason="bad", actor_user_id=rig.c)
    assert back["kind"] == "rollback" and back["version_ref"] == p1
    assert governed.current().version_public_id == p1
    assert M.model_id(M.ModelProfile.FAST) == C.slug_for("luna")
    rig.svc.rollback(to_code=True, reason="off", actor_user_id=rig.c)
    assert governed.current() is None
    assert M.model_id(M.ModelProfile.FAST) == M.code_model_id(M.ModelProfile.FAST)
    with pytest.raises(AIConflict):
        rig.svc.rollback(to_code=True, reason="again", actor_user_id=rig.c)


def test_rollback_without_earlier_activation_and_retired_target(rig):
    p1 = rig.approved()
    rig.svc.activate(p1, reason="a", actor_user_id=rig.c)
    with pytest.raises(AIConflict):
        rig.svc.rollback(to_code=False, reason="x", actor_user_id=rig.c)
    p2 = rig.approved(cfg(fast="terra"))
    rig.svc.activate(p2, reason="b", actor_user_id=rig.c)
    rig.svc.retire(p1, reason="old", actor_user_id=rig.a)
    with pytest.raises(AIConflict):
        rig.svc.rollback(to_code=False, reason="x", actor_user_id=rig.c)


def test_retire_rules(rig):
    pid = rig.approved()
    rig.svc.activate(pid, reason="a", actor_user_id=rig.c)
    with pytest.raises(AIConflict):
        rig.svc.retire(pid, reason="x", actor_user_id=rig.a)
    rig.svc.rollback(to_code=True, reason="off", actor_user_id=rig.c)
    assert rig.svc.retire(pid, reason="done", actor_user_id=rig.a)["state"] == "retired"
    with pytest.raises(AIConflict):
        rig.svc.activate(pid, reason="a", actor_user_id=rig.c)


def test_production_process_resolves_only_a_production_activation(env):
    st = Rig(env, environment="staging")
    pid = st.approved(cfg(fast="terra"))
    st.svc.activate(pid, reason="a", actor_user_id=st.c)
    uninstall_resolver()
    prod = Rig(env, environment="production")
    assert governed.current() is None                                   # a staging activation never governs a production process
    prod.svc.activate(pid, reason="p", actor_user_id=prod.c)
    assert governed.current().version_public_id == pid
    uninstall_resolver()


def test_invalid_inputs_and_unknown_ids(rig):
    with pytest.raises(AINotFound):
        rig.svc.get_version("0" * 32)
    with pytest.raises(AIValidationError):
        rig.svc.create_draft(name="", notes="", config=None, base_version_id=None, actor_user_id=rig.a)
    with pytest.raises(AIValidationError):
        rig.svc.create_draft(name="x", notes="", config={"profiles": {"fast": "openai/gpt-5.6-sol", "balanced": "terra", "advanced": "sol"}},
                             base_version_id=None, actor_user_id=rig.a)
    pid = rig.approved()
    with pytest.raises(AIValidationError):
        rig.svc.activate(pid, reason="", actor_user_id=rig.c)


# ---------------- evaluator ------------------------------------------------------------------------------------------------

def test_evaluator_passes_baseline_and_reports_zero_live_calls():
    r = evaluate(K.normalise(K.baseline_config()))
    assert r["passed"] and r["live_calls"] == 0 and r["summary"]["resolution_cases"] == len(ModelOperation) * 3
    assert "not a measure of live model quality" in r["summary"]["evidence_class"]


def test_evaluator_makes_no_network_or_provider_call(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("network used")
    monkeypatch.setattr(socket, "socket", boom)
    import httpx
    monkeypatch.setattr(httpx.Client, "send", boom)
    assert evaluate(K.normalise(K.baseline_config()))["passed"]


def test_evaluator_fails_an_invalid_configuration_without_resolving():
    r = evaluate(K.normalise(cfg(fast="sol")))
    assert not r["passed"] and r["summary"]["resolution_cases"] == 0


def test_evaluator_restores_the_previous_provider():
    sentinel = lambda: None  # noqa: E731
    governed.set_provider(sentinel)
    evaluate(K.normalise(K.baseline_config()))
    assert governed._provider is sentinel
    governed.clear()


def test_evaluation_job_is_idempotent_and_records_hash(rig):
    rig.evaluated()
    with sf(rig.env)() as s:
        ev = s.scalar(select(AIConfigEvaluation))
        assert ev.status == "passed" and ev.config_hash and ev.live_calls == 0
        assert rig.svc.run_evaluation(ev.public_id) == "passed"
        assert len(s.scalars(select(AIConfigEvaluation)).all()) == 1
    with pytest.raises(AIConflict):
        d = rig.svc.create_draft(name="x", notes="", config=None, base_version_id=None, actor_user_id=rig.a)
        rig.svc.request_evaluation(d["public_id"], actor_user_id=rig.a)             # a draft cannot be evaluated


def test_evaluation_db_rejects_nonzero_live_calls(rig):
    rig.evaluated()
    with sf(rig.env)() as s, pytest.raises(IntegrityError):
        s.execute(update(AIConfigEvaluation).values(live_calls=1)); s.commit()


def test_duplicate_queued_evaluation_is_refused(rig):
    d = rig.svc.create_draft(name="x", notes="", config=None, base_version_id=None, actor_user_id=rig.a)
    rig.svc.validate(d["public_id"], actor_user_id=rig.a)
    rig.svc.request_evaluation(d["public_id"], actor_user_id=rig.a)
    with pytest.raises(AIConflict):
        rig.svc.request_evaluation(d["public_id"], actor_user_id=rig.a)


# ---------------- boundaries ------------------------------------------------------------------------------------------------

def test_governed_activation_does_not_change_interview_slugs_or_candidate_boundary(rig):
    from src import constants
    from src.application.agent_service import _resolve_profile
    approved_before = dict(constants.APPROVED_MODELS)
    pid = rig.approved(cfg(fast="terra"))
    rig.svc.activate(pid, reason="a", actor_user_id=rig.c)
    assert dict(constants.APPROVED_MODELS) == approved_before
    for p in M.ModelProfile:
        assert M.effective_interview_profile(M.code_model_id(p)) is p
    for raw in ("openai/gpt-5.6-sol", "sol", "gpt-5"):
        with pytest.raises(Exception):
            _resolve_profile(raw)


def test_exactly_three_specialists_and_deterministic_operations_stay_model_free():
    specialists = [o for o in ModelOperation if o.value.startswith("specialist_")]
    assert len(specialists) == 3
    assert resolve_policy(ModelOperation.SPECIALIST_EVIDENCE_ANALYSIS, M.ModelProfile.ADVANCED).uses_model is False


def test_runtime_view_is_safe_and_reports_mode(rig):
    v = runtime_view(rig.resolver)
    assert v["mode"] == "code_defaults" and v["realtime"]["chat_slug"] is None
    blob = str(v).lower()
    assert "api_key" not in blob and "secret" not in blob and "prompt" not in blob


def test_billing_entitlement_and_integration_tables_untouched_by_activation(rig):
    from src.persistence import Subscription
    with sf(rig.env)() as s:
        before = [(x.id, x.plan_version_id) for x in s.scalars(select(Subscription)).all()]
    pid = rig.approved()
    rig.svc.activate(pid, reason="a", actor_user_id=rig.c)
    with sf(rig.env)() as s:
        assert [(x.id, x.plan_version_id) for x in s.scalars(select(Subscription)).all()] == before


# ---------------- audit ------------------------------------------------------------------------------------------------------

def test_every_lifecycle_step_is_audited_with_safe_context(env):
    r = Rig(env)
    _, ca = env.user("platform_admin"); _, cb = env.user("platform_admin"); _, cc = env.user("platform_admin")
    d = env.c.post(f"{API}/admin/ai/configs", json={"name": "api"}, cookies=ca).json()
    pid = d["public_id"]
    env.c.post(f"{API}/admin/ai/configs/{pid}/validate", cookies=ca)
    assert env.c.post(f"{API}/admin/ai/configs/{pid}/evaluate", cookies=ca).status_code == 202
    r.drain()
    ap = env.c.post(f"{API}/admin/ai/configs/{pid}/request-approval", json={"reason": "ok"}, cookies=cb).json()
    assert env.c.post(f"{API}/admin/ai/approvals/{ap['public_id']}/approve", json={"reason": "ok"}, cookies=cc).status_code == 200
    assert env.c.post(f"{API}/admin/ai/configs/{pid}/activate", json={"reason": "go"}, cookies=cc).status_code == 201
    assert env.c.post(f"{API}/admin/ai/rollback", json={"reason": "off", "to_code": True}, cookies=cc).status_code == 201
    for ev in (A.ADMIN_AI_CONFIG_CREATED, A.ADMIN_AI_CONFIG_VALIDATED, A.ADMIN_AI_EVALUATION_REQUESTED, A.ADMIN_AI_EVALUATION_COMPLETED,
               A.ADMIN_AI_APPROVAL_REQUESTED, A.ADMIN_AI_APPROVED, A.ADMIN_AI_ACTIVATED, A.ADMIN_AI_ROLLED_BACK):
        rows = env.events(ev)
        assert rows, ev
        blob = str(rows[0]["context"]).lower()
        assert "config_hash" in blob or ev == A.ADMIN_AI_ROLLED_BACK or "environment" in blob
        assert "prompt" not in blob and "secret" not in blob
    uninstall_resolver()


# ---------------- API + permissions ----------------------------------------------------------------------------------------

def test_permissions_and_route_invariant(env):
    from src.api.admin_route_invariant import admin_routes, ungated
    assert len(perm.PERMISSIONS) == 43
    assert perm.AI_MANAGE in perm.ROLE_PRESETS[perm.ROLE_PLATFORM_ADMIN] and perm.AI_ACTIVATE in perm.ROLE_PRESETS[perm.ROLE_PLATFORM_ADMIN]
    for role in ("support_operator", "billing_admin", "knowledge_admin", "security_privacy_admin", "operations_admin"):
        assert perm.AI_MANAGE not in perm.permissions_for_role(role) and perm.AI_ACTIVATE not in perm.permissions_for_role(role), role
    assert not ungated()
    ai = [r for r in admin_routes() if "/admin/ai" in r.path]
    assert len(ai) >= 18 and all(r.permissions for r in ai)


def test_api_denies_without_permission_and_never_accepts_a_slug(env):
    Rig(env)
    _, plain = env.user("user"); _, ops = env.user("operations_admin"); _, plat = env.user("platform_admin")
    assert env.c.get(f"{API}/admin/ai", cookies=plain).status_code == 403
    assert env.c.get(f"{API}/admin/ai", cookies=ops).status_code == 200                      # read only
    assert env.c.post(f"{API}/admin/ai/configs", json={"name": "x"}, cookies=ops).status_code == 403
    r = env.c.post(f"{API}/admin/ai/configs", json={"name": "x", "settings": {"profiles": {"fast": "openai/gpt-5.6-sol", "balanced": "terra", "advanced": "sol"}}}, cookies=plat)
    assert r.status_code == 422 and "gpt" not in r.text
    assert env.c.post(f"{API}/admin/ai/configs", json={"name": "x", "settings": {"provider_slug": "a/b"}}, cookies=plat).status_code == 422
    assert env.c.post(f"{API}/admin/ai/configs", json={"name": "x", "force": True}, cookies=plat).status_code == 422
    uninstall_resolver()


def test_api_reads_are_allowlist_shaped(env):
    Rig(env)
    _, plat = env.user("platform_admin")
    assert env.c.get(f"{API}/admin/ai/catalogue", cookies=plat).json()["items"][0]["provider_slug"].startswith("openai/")
    cd = env.c.get(f"{API}/admin/ai/code-defined", cookies=plat).json()
    assert any(o["deterministic"] for o in cd["operations"]) and any(o["realtime"] for o in cd["operations"])
    rt = env.c.get(f"{API}/admin/ai/runtime", cookies=plat).json()
    assert rt["mode"] == "code_defaults"
    for path in ("environments", "history", "approvals", "configs"):
        assert env.c.get(f"{API}/admin/ai/{path}", cookies=plat).status_code == 200
    assert env.c.get(f"{API}/admin/ai/configs/{'0' * 32}", cookies=plat).status_code == 404
    uninstall_resolver()


def test_api_self_approval_is_403_and_unknown_environment_422(env):
    r = Rig(env)
    _, ca = env.user("platform_admin")
    d = env.c.post(f"{API}/admin/ai/configs", json={"name": "api"}, cookies=ca).json()
    pid = d["public_id"]
    env.c.post(f"{API}/admin/ai/configs/{pid}/validate", cookies=ca)
    env.c.post(f"{API}/admin/ai/configs/{pid}/evaluate", cookies=ca)
    r.drain()
    ap = env.c.post(f"{API}/admin/ai/configs/{pid}/request-approval", json={"reason": "ok"}, cookies=ca).json()
    assert env.c.post(f"{API}/admin/ai/approvals/{ap['public_id']}/approve", json={"reason": "ok"}, cookies=ca).status_code == 403
    assert env.c.post(f"{API}/admin/ai/configs/{pid}/activate", json={"reason": "go"}, cookies=ca).status_code == 409
    assert env.c.post(f"{API}/admin/ai/configs/{pid}/activate", json={"environment": "qa", "reason": "go"}, cookies=ca).status_code in (409, 422)
    uninstall_resolver()


# ---------------- jobs registry + migration ---------------------------------------------------------------------------------

def test_job_type_registered_without_admin_enqueue():
    from src.jobs.registry import REGISTRY
    d = REGISTRY["ai_evaluate_config"]
    assert d.admin_enqueue is False and d.dependencies == ("ai_admin",)
    assert set(d.payload_model.model_fields) == {"evaluation_id"}


def test_migration_0022_adds_only_ai_tables_and_seeds_nothing(tmp_path, monkeypatch):
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine, inspect
    url = f"sqlite:///{tmp_path / 'm.db'}"
    monkeypatch.setenv("DATABASE_URL", url)      # migrations/env.py reads this
    cfg_ = Config(str(ROOT / "alembic.ini")); cfg_.set_main_option("sqlalchemy.url", url); cfg_.set_main_option("script_location", str(ROOT / "migrations"))
    command.upgrade(cfg_, "0021_billing_admin")
    before = set(inspect(create_engine(url)).get_table_names())
    command.upgrade(cfg_, "0022_ai_model_admin")
    eng = create_engine(url)
    after = set(inspect(eng).get_table_names())
    assert after - before == {"ai_config_versions", "ai_config_evaluations", "ai_config_approvals", "ai_config_activations"}
    with eng.connect() as c:
        for t in after - before:
            assert c.execute(text(f"SELECT count(*) FROM {t}")).scalar() == 0
    command.downgrade(cfg_, "0021_billing_admin")
    assert set(inspect(create_engine(url)).get_table_names()) == before


def test_api_override_can_be_cleared_back_to_inherit_with_an_explicit_null(env):
    Rig(env)
    _, plat = env.user("platform_admin")
    base = env.c.post(f"{API}/admin/ai/configs", json={"name": "inherit"}, cookies=plat).json()
    assert all(v is None for t in base["settings"]["operations"].values() for v in t.values())          # inherit is stored as null
    over = env.c.post(f"{API}/admin/ai/configs", json={"name": "o", "settings": {"operations": {"evaluation": {"max_output_tokens": 2048}}}}, cookies=plat).json()
    assert over["settings"]["operations"]["evaluation"]["max_output_tokens"] == 2048
    assert over["content_hash"] != base["content_hash"]                                                   # a number equal to the old policy value is not inherit
    cleared = env.c.patch(f"{API}/admin/ai/configs/{over['public_id']}", json={"settings": {"operations": {"evaluation": {"max_output_tokens": None}}}}, cookies=plat).json()
    assert cleared["settings"]["operations"]["evaluation"]["max_output_tokens"] is None
    assert cleared["content_hash"] == base["content_hash"]                                                # inherit -> override -> inherit is the same canonical form
    again = env.c.patch(f"{API}/admin/ai/configs/{over['public_id']}", json={"settings": {"operations": {"evaluation": {}}}}, cookies=plat).json()
    assert again["content_hash"] == base["content_hash"]
    assert any(c["field"] == "operation.evaluation.max_output_tokens" for c in env.c.patch(
        f"{API}/admin/ai/configs/{over['public_id']}", json={"settings": {"operations": {"evaluation": {"max_output_tokens": 2048}}}}, cookies=plat).json()["changed_from_baseline"])
    uninstall_resolver()
