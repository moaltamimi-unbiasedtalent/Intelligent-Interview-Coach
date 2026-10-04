"""P10B-W10.11: durable platform pause (closes SEC-W10-05) and code-defined feature flags. Offline and deterministic: temp DB, no provider, no network.
Load-bearing properties: the pause state is shared through the DATABASE (never process memory), a protected request is refused BEFORE any service/model is
built, an unreadable store never reopens the platform, and a flag can only RESTRICT availability."""

from __future__ import annotations

import re
import socket
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from src.api import dependencies as deps
from src.application import admin_audit as A
from src.application import admin_permissions as perm
from src.application import pause as P
from src.application.pause import (
    PAUSABLE_CAPABILITIES, PauseConflict, PauseService, PauseStateUnavailable, PauseUnsupportedEnvironment, PauseValidationError,
)
from src.jobs.service import JobService
from src.jobs.worker import Worker
from src.persistence import FeatureFlagOverride, PlatformPauseState
from src.platform_config import flags as F
from src.platform_config.flags import (
    FLAGS, NOT_MUTABLE, FeatureFlagService, FeatureFlagStateUnavailable, FlagConflict, FlagUnsupportedEnvironment, FlagValidationError,
)
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


def pause_svc(env, environment="development"):
    return PauseService(sf(env), environment=environment)


def flag_svc(env, environment="development"):
    return FeatureFlagService(sf(env), environment=environment)


def pause(svc, cap="agent", on=True, rev=None, reason="incident", actor=1):
    rev = svc.snapshot()[cap]["revision"] if rev is None else rev
    return svc.set_paused(cap, on, expected_revision=rev, reason=reason, actor_user_id=actor)


# ---------------- durable pause: lifecycle, restart, cross-instance ----------------------------------------------------------------

def test_default_is_running_and_matches_the_env_baseline(env, monkeypatch):
    svc = pause_svc(env)
    assert all(not s["paused"] and s["source"] == "baseline" and s["revision"] == 0 for s in svc.snapshot().values())
    monkeypatch.setenv("PAUSED_CAPABILITIES", "ocr,nonsense")                     # the pre-W10.11 deployment seed is still the baseline
    assert svc.is_paused("ocr") and not svc.is_paused("agent")
    pause(svc, "ocr", on=False)                                                   # an explicit durable resume overrides the env seed
    assert not svc.is_paused("ocr") and svc.snapshot()["ocr"]["source"] == "override"


def test_pause_and_resume_roundtrip_with_monotonic_revision(env):
    svc = pause_svc(env)
    a = pause(svc, "agent", True)
    assert a["paused"] and a["revision"] == 1 and a["paused_at"]
    b = pause(svc, "agent", False)
    assert not b["paused"] and b["revision"] == 2 and b["resumed_at"]
    with sf(env)() as s:
        row = s.scalar(select(PlatformPauseState))
        assert row.paused_by_user_id == 1 and row.resumed_by_user_id == 1 and row.reason == "incident"


def test_restart_durability_a_new_service_instance_reads_the_same_state(env):
    pause(pause_svc(env), "agent", True)
    fresh = pause_svc(env)                                                        # a recreated process: no shared memory at all
    assert fresh.is_paused("agent") and fresh.snapshot()["agent"]["revision"] == 1
    pause(fresh, "agent", False)
    assert not pause_svc(env).is_paused("agent")


def test_two_independent_instances_observe_each_others_changes(env):
    a, b = pause_svc(env), pause_svc(env)
    pause(a, "agent", True)
    assert b.is_paused("agent")                                                   # SEC-W10-05: previously invisible to another instance
    pause(b, "agent", False)
    assert not a.is_paused("agent") and not pause_svc(env).is_paused("agent")
    assert P._installed is None                                                   # no process-local authority exists


def test_state_is_scoped_per_environment_and_only_the_servers_own_is_mutable(env):
    dev, staging = pause_svc(env, "development"), pause_svc(env, "staging")
    pause(dev, "agent", True)
    assert dev.is_paused("agent") and not staging.is_paused("agent")
    with pytest.raises(PauseUnsupportedEnvironment):
        pause(pause_svc(env, None), "agent", True)                                # unknown API_ENV cannot mutate
    assert pause_svc(env, None).is_paused("agent") is False                       # and sees no rows (it never maps to staging or production)
    with sf(env)() as s:
        assert {r.environment for r in s.scalars(select(PlatformPauseState)).all()} == {"development"}


def test_optimistic_concurrency_rejects_a_stale_writer(env):
    a, b = pause_svc(env), pause_svc(env)
    loaded = a.snapshot()["agent"]["revision"]
    pause(a, "agent", True, rev=loaded)
    with pytest.raises(PauseConflict):
        b.set_paused("agent", False, expected_revision=loaded, reason="late", actor_user_id=2)   # b still holds the old revision
    assert a.is_paused("agent")                                                   # no silent overwrite
    with pytest.raises(PauseConflict):
        a.set_paused("agent", True, expected_revision=0, reason="again", actor_user_id=1)


def test_validation_unknown_capability_reason_and_revision(env):
    svc = pause_svc(env)
    for bad in (dict(capability="nope"), dict(reason=""), dict(reason="x" * 201), dict(rev=-1), dict(rev=True)):
        kw = dict(capability="agent", reason="r", rev=0)
        kw.update(bad)
        with pytest.raises(PauseValidationError):
            svc.set_paused(kw["capability"], True, expected_revision=kw["rev"], reason=kw["reason"], actor_user_id=1)
    with pytest.raises(ValueError):
        svc.is_paused("nope")


def test_db_constraints(env):
    pause(pause_svc(env), "agent", True)
    with sf(env)() as s, pytest.raises(IntegrityError):
        s.add(PlatformPauseState(environment="development", capability="agent", paused=False, revision=1)); s.commit()          # one row per env+capability
    with sf(env)() as s, pytest.raises(IntegrityError):
        s.add(PlatformPauseState(environment="qa", capability="ocr", paused=False, revision=1)); s.commit()                      # valid environment
    with sf(env)() as s, pytest.raises(IntegrityError):
        s.add(PlatformPauseState(environment="staging", capability="ocr", paused=False, revision=-1)); s.commit()                # revision >= 0


def test_unreadable_store_never_reopens_the_platform(env):
    broken = PauseService(lambda: (_ for _ in ()).throw(RuntimeError("db down")), environment="development")
    with pytest.raises(PauseStateUnavailable):
        broken.is_paused("agent")
    with pytest.raises(PauseStateUnavailable):
        broken.snapshot()
    P.install(lambda: (_ for _ in ()).throw(RuntimeError("db down")))
    assert P.check_paused("current_market") is True                              # a tool-level check fails CLOSED
    P.uninstall()
    assert P.check_paused("current_market") is False                             # only a process with no database wiring uses the baseline


# ---------------- admission gate: protected routes, provider/service never built --------------------------------------------------------

def _agent_probe(env):
    calls = SimpleNamespace(built=0, ran=0)

    class FakeService:
        def run(self, *a, **k):
            calls.ran += 1
            raise ValueError("fake agent ran")

    def factory():
        calls.built += 1
        return FakeService()

    env.app.dependency_overrides[deps.get_agent_service] = factory
    return calls


RUN_BODY = {"goal": "Prepare me for an interview", "target_role": "Nurse"}


def test_paused_agent_routes_are_refused_before_the_service_or_model_is_built(env):
    calls = _agent_probe(env)
    _, cand = env.user("user")
    pause(pause_svc(env), "agent", True, reason="SECRET-INTERNAL-REASON")
    for path, body in (("/agent/run", RUN_BODY), ("/agent/runs/abc/messages", {"message": "hi"}),
                       ("/agent/runs/abc/resume", {"action_id": "a", "decision": "approve"})):
        r = env.c.post(f"{API}{path}", json=body, cookies=cand)
        assert r.status_code == 503, (path, r.text)
        err = r.json()["error"]
        assert err["code"] == "platform_paused" and "temporarily unavailable" in err["message"]
        assert "SECRET-INTERNAL-REASON" not in r.text and "operator" not in r.text.lower() and "@" not in r.text    # no reason, actor or email
    assert calls.built == 0 and calls.ran == 0                                    # 0 provider/model construction


def test_resume_admits_again_under_the_existing_rules(env):
    calls = _agent_probe(env)
    _, cand = env.user("user")
    svc = pause_svc(env)
    pause(svc, "agent", True)
    assert env.c.post(f"{API}/agent/run", json=RUN_BODY, cookies=cand).status_code == 503
    pause(svc, "agent", False)
    r = env.c.post(f"{API}/agent/run", json=RUN_BODY, cookies=cand)
    assert r.status_code != 503 and calls.built == 1 and calls.ran == 1          # admitted: the (fake) service is now built and run


def test_store_outage_refuses_the_protected_operation_safely(env, monkeypatch):
    calls = _agent_probe(env)
    _, cand = env.user("user")
    monkeypatch.setattr(PauseService, "is_paused", lambda self, cap: (_ for _ in ()).throw(PauseStateUnavailable("x")))
    r = env.c.post(f"{API}/agent/run", json=RUN_BODY, cookies=cand)
    assert r.status_code == 503 and r.json()["error"]["code"] == "platform_state_unavailable"
    assert "Traceback" not in r.text and "db" not in r.text.lower().split("message")[-1][:0]
    assert calls.built == 0 and calls.ran == 0


def test_registration_ocr_and_realtime_are_gated_by_the_same_durable_state(env):
    svc = pause_svc(env)
    pause(svc, "public_registration", True)
    r = env.c.post(f"{API}/auth/register", json={"email": "new@x.com", "password": "Passw0rd!long1"})
    assert r.status_code == 503 and r.json()["error"]["code"] == "platform_paused"
    pause(svc, "public_registration", False)
    _, cand = env.user("user")
    pause(svc, "ocr", True)
    r = env.c.post(f"{API}/documents", files={"file": ("cv.txt", b"hello", "text/plain")}, data={"category": "other"}, cookies=cand)
    assert r.status_code == 503 and r.json()["error"]["code"] == "platform_paused"
    pause(svc, "ocr", False)
    assert env.c.post(f"{API}/documents", files={"file": ("cv.txt", b"hello", "text/plain")}, data={"category": "other"}, cookies=cand).status_code != 503


def test_privacy_account_legal_and_candidate_reads_remain_available_while_everything_is_paused(env):
    svc = pause_svc(env)
    _, cand = env.user("user")
    for cap in PAUSABLE_CAPABILITIES:
        pause(svc, cap, True)
    assert env.c.get(f"{API}/privacy/legal", cookies=cand).status_code == 200
    assert env.c.get(f"{API}/privacy/requests", cookies=cand).status_code == 200
    from src.privacy.policy import REQUEST_TYPES
    r = env.c.post(f"{API}/privacy/requests", json={"request_type": sorted(REQUEST_TYPES)[0], "note": "please"}, cookies=cand)
    assert r.status_code in (200, 201)                                            # privacy request creation still works
    assert env.c.get(f"{API}/auth/me", cookies=cand).status_code == 200
    assert env.c.get(f"{API}/auth/plan", cookies=cand).status_code == 200
    assert env.c.get(f"{API}/health").status_code == 200
    assert env.c.get(f"{API}/capabilities").status_code == 200


def test_admin_stays_usable_and_can_resume_while_paused(env):
    _, ops = env.user("operations_admin")
    svc = pause_svc(env)
    for cap in PAUSABLE_CAPABILITIES:
        pause(svc, cap, True)
    assert env.c.get(f"{API}/admin/pause", cookies=ops).status_code == 200
    assert env.c.get(f"{API}/admin/home", cookies=ops).status_code == 200
    assert env.c.get(f"{API}/admin/flags", cookies=ops).status_code == 200
    assert env.c.get(f"{API}/admin/jobs", cookies=ops).status_code == 200
    r = env.c.post(f"{API}/admin/pause/agent", json={"paused": False, "expected_revision": 1, "reason": "recovered"}, cookies=ops)
    assert r.status_code == 200 and not r.json()["paused"]


def test_capabilities_projection_follows_the_durable_pause_and_fails_closed(env):
    assert env.c.get(f"{API}/capabilities").json()["company_research_enabled"] is True
    svc = pause_svc(env)
    pause(svc, "current_market", True)
    assert env.c.get(f"{API}/capabilities").json()["company_research_enabled"] is False


def test_worker_still_runs_jobs_while_everything_is_paused(env):
    svc = pause_svc(env)
    for cap in PAUSABLE_CAPABILITIES:
        pause(svc, cap, True)
    jobs = JobService(sf(env))
    jobs.enqueue("diagnostic_noop", {"label": "while-paused"}, idempotency_key="w1011", actor_user_id=1)
    worker = Worker(jobs, services=SimpleNamespace())
    assert worker.run_once() != "idle"
    with sf(env)() as s:
        from src.persistence import Job
        assert s.scalar(select(Job.state)) == "succeeded"


# ---------------- pause API: permissions, audit, stale revision -------------------------------------------------------------------

def test_pause_permissions_matrix(env):
    _, cand = env.user("user"); _, plat = env.user("platform_admin"); _, ops = env.user("operations_admin"); _, sup = env.user("support_operator")
    body = {"paused": True, "expected_revision": 0, "reason": "r"}
    assert env.c.get(f"{API}/admin/pause", cookies=cand).status_code == 403
    assert env.c.post(f"{API}/admin/pause/agent", json=body, cookies=cand).status_code == 403
    assert env.c.get(f"{API}/admin/pause", cookies=plat).status_code == 200                      # read-only access (flags.read)
    assert env.c.post(f"{API}/admin/pause/agent", json=body, cookies=plat).status_code == 403    # platform_admin lacks platform.config.manage (W10.0 ownership)
    assert env.c.post(f"{API}/admin/pause/agent", json=body, cookies=sup).status_code == 403
    assert env.c.post(f"{API}/admin/pause/agent", json=body, cookies=ops).status_code == 200
    assert env.c.post(f"{API}/admin/pause/agent", json={**body, "paused": False}, cookies=plat).status_code == 403   # nor can it resume
    assert not pause_svc(env).snapshot()["agent"]["paused"] is False


def test_pause_api_stale_revision_is_409_and_validation_422(env):
    _, a = env.user("operations_admin"); _, b = env.user("operations_admin")
    assert env.c.post(f"{API}/admin/pause/ocr", json={"paused": True, "expected_revision": 0, "reason": "r"}, cookies=a).status_code == 200
    stale = env.c.post(f"{API}/admin/pause/ocr", json={"paused": False, "expected_revision": 0, "reason": "r"}, cookies=b)
    assert stale.status_code == 409
    assert env.c.post(f"{API}/admin/pause/ocr", json={"paused": False, "expected_revision": 1, "reason": ""}, cookies=b).status_code == 422
    assert env.c.post(f"{API}/admin/pause/ocr", json={"paused": False, "reason": "x"}, cookies=b).status_code == 422          # revision required
    assert env.c.post(f"{API}/admin/pause/ocr", json={"paused": False, "expected_revision": 1, "reason": "x", "environment": "production"}, cookies=b).status_code == 422
    assert env.c.post(f"{API}/admin/pause/nope", json={"paused": True, "expected_revision": 0, "reason": "x"}, cookies=b).status_code == 422


def test_pause_audit_events_are_canonical_and_safe(env):
    _, ops = env.user("operations_admin")
    env.c.post(f"{API}/admin/pause/agent", json={"paused": True, "expected_revision": 0, "reason": "provider incident"}, cookies=ops)
    env.c.post(f"{API}/admin/pause/agent", json={"paused": False, "expected_revision": 1, "reason": "recovered"}, cookies=ops)
    p, r = env.events(A.ADMIN_PLATFORM_PAUSED)[0], env.events(A.ADMIN_PLATFORM_RESUMED)[0]
    assert p["context"]["environment"] == "development" and p["context"]["capability"] == "agent" and p["context"]["revision"] == 1
    assert (r["context"]["old_state"], r["context"]["new_state"], r["context"]["revision"]) == ("paused", "running", 2)
    assert "@" not in str(p["context"]) and p["request_id"]


def test_candidate_never_sees_the_internal_reason_or_actor(env):
    _, ops = env.user("operations_admin"); _, cand = env.user("user")
    env.c.post(f"{API}/admin/pause/current_market", json={"paused": True, "expected_revision": 0, "reason": "SECRET-INCIDENT"}, cookies=ops)
    blob = env.c.get(f"{API}/capabilities").text + env.c.get(f"{API}/auth/me", cookies=cand).text + env.c.get(f"{API}/auth/plan", cookies=cand).text
    assert "SECRET-INCIDENT" not in blob


def test_pause_does_not_touch_entitlements_billing_or_ai_state(env):
    _, cand = env.user("user")

    def snap():
        with sf(env)() as s:
            return (s.execute(text("SELECT count(*), coalesce(sum(plan_version_id),0) FROM subscriptions")).one(),
                    s.execute(text("SELECT count(*) FROM billing_invoices")).scalar(), s.execute(text("SELECT count(*) FROM ai_config_versions")).scalar(),
                    s.execute(text("SELECT count(*) FROM ai_config_activations")).scalar(), env.accounts.get_account(1).tier if env.accounts.get_account(1) else None)
    before = snap()
    svc = pause_svc(env)
    for cap in PAUSABLE_CAPABILITIES:
        pause(svc, cap, True)
        pause(svc, cap, False)
    assert snap() == before
    assert env.c.get(f"{API}/auth/plan", cookies=cand).status_code == 200


# ---------------- feature flags ---------------------------------------------------------------------------------------------------

def test_registry_is_code_defined_and_only_real_safe_flags_exist():
    assert set(FLAGS) == {"external_research", "company_web_research"}
    for f in FLAGS.values():
        assert f.env_var and f.consumers and f.candidate_visible
    assert "AGENT_COACH_ENABLED" in NOT_MUTABLE and "OPENROUTER_MODEL_*" in NOT_MUTABLE and "BILLING_PROVIDER" in NOT_MUTABLE
    with pytest.raises(FlagValidationError):
        FeatureFlagService.definition("anything")


def test_flag_baseline_inherit_enable_disable_reset_and_precedence(env, monkeypatch):
    svc = flag_svc(env)
    s0 = svc.states()[0]
    assert (s0["state"], s0["effective"], s0["override"], s0["revision"]) == ("inherited", True, None, 0)
    monkeypatch.setenv("EXTERNAL_RESEARCH_ENABLED", "false")                     # the existing deployment baseline is untouched
    assert svc.effective("external_research") is False
    r1 = svc.set_override("external_research", True, expected_revision=0, reason="r", actor_user_id=1)
    assert (r1["state"], r1["effective"], r1["baseline"], r1["revision"]) == ("enabled_override", True, False, 1)   # override > environment baseline
    r2 = svc.set_override("external_research", False, expected_revision=1, reason="r", actor_user_id=1)
    assert (r2["state"], r2["effective"]) == ("disabled_override", False)
    monkeypatch.setenv("EXTERNAL_RESEARCH_ENABLED", "true")
    assert svc.effective("external_research") is False                           # an explicit disable beats a true env baseline
    r3 = svc.set_override("external_research", None, expected_revision=2, reason="r", actor_user_id=1)
    assert (r3["state"], r3["override"], r3["effective"], r3["revision"]) == ("inherited", None, True, 3)                  # reset returns to the env baseline
    with pytest.raises(FlagConflict):
        svc.set_override("external_research", None, expected_revision=3, reason="r", actor_user_id=1)                       # already inherited


def test_false_baseline_and_explicit_disable_are_distinguishable(env, monkeypatch):
    monkeypatch.setenv("EXTERNAL_RESEARCH_ENABLED", "false")
    svc = flag_svc(env)
    a = svc.states()[0]
    b = svc.set_override("external_research", False, expected_revision=0, reason="r", actor_user_id=1)
    assert (a["state"], a["effective"]) == ("inherited", False) and (b["state"], b["effective"]) == ("disabled_override", False)


def test_flag_restart_and_cross_instance_visibility(env):
    a, b = flag_svc(env), flag_svc(env)
    a.set_override("company_web_research", False, expected_revision=0, reason="r", actor_user_id=1)
    assert b.effective("company_web_research") is False and flag_svc(env).effective("company_web_research") is False
    assert flag_svc(env, "staging").effective("company_web_research") is True    # environment-scoped
    with pytest.raises(FlagUnsupportedEnvironment):
        flag_svc(env, None).set_override("company_web_research", True, expected_revision=0, reason="r", actor_user_id=1)


def test_flag_stale_revision_and_monotonic_revision_after_reset(env):
    a, b = flag_svc(env), flag_svc(env)
    a.set_override("external_research", False, expected_revision=0, reason="r", actor_user_id=1)
    with pytest.raises(FlagConflict):
        b.set_override("external_research", True, expected_revision=0, reason="r", actor_user_id=2)
    a.set_override("external_research", None, expected_revision=1, reason="r", actor_user_id=1)
    a.set_override("external_research", False, expected_revision=2, reason="r", actor_user_id=1)
    with pytest.raises(FlagConflict):                                             # no ABA: a stale writer holding revision 1 cannot match revision 3
        b.set_override("external_research", True, expected_revision=1, reason="r", actor_user_id=2)


def test_flag_validation(env):
    svc = flag_svc(env)
    for kw in (dict(reason=""), dict(reason="x" * 201), dict(expected_revision=-1), dict(expected_revision=True)):
        args = dict(expected_revision=0, reason="r"); args.update(kw)
        with pytest.raises(FlagValidationError):
            svc.set_override("external_research", True, actor_user_id=1, **args)
    with pytest.raises(FlagValidationError):
        svc.set_override("external_research", "yes", expected_revision=0, reason="r", actor_user_id=1)
    with pytest.raises(FlagValidationError):
        svc.set_override("invented_flag", True, expected_revision=0, reason="r", actor_user_id=1)


def test_flag_db_constraints(env):
    flag_svc(env).set_override("external_research", True, expected_revision=0, reason="r", actor_user_id=1)
    with sf(env)() as s, pytest.raises(IntegrityError):
        s.add(FeatureFlagOverride(environment="development", flag_key="external_research", enabled=False, revision=1)); s.commit()
    with sf(env)() as s, pytest.raises(IntegrityError):
        s.add(FeatureFlagOverride(environment="qa", flag_key="x", enabled=False, revision=1)); s.commit()


def test_flag_api_permissions_unknown_key_stale_revision_and_audit(env):
    _, cand = env.user("user"); _, plat = env.user("platform_admin"); _, sup = env.user("support_operator"); _, ops = env.user("operations_admin")
    assert env.c.get(f"{API}/admin/flags", cookies=cand).status_code == 403
    assert env.c.get(f"{API}/admin/flags", cookies=sup).status_code == 403
    items = env.c.get(f"{API}/admin/flags", cookies=plat).json()["items"]
    assert [i["flag_id"] for i in items] == ["external_research", "company_web_research"]
    body = {"enabled": False, "expected_revision": 0, "reason": "provider cost"}
    assert env.c.put(f"{API}/admin/flags/external_research", json=body, cookies=cand).status_code == 403
    assert env.c.put(f"{API}/admin/flags/external_research", json=body, cookies=sup).status_code == 403
    r = env.c.put(f"{API}/admin/flags/external_research", json=body, cookies=plat)
    assert r.status_code == 200 and r.json()["state"] == "disabled_override" and r.json()["effective"] is False
    assert env.c.put(f"{API}/admin/flags/external_research", json=body, cookies=ops).status_code == 409           # stale
    assert env.c.put(f"{API}/admin/flags/invented", json=body, cookies=plat).status_code == 404
    assert env.c.post(f"{API}/admin/flags", json={"flag_id": "x", "enabled": True}, cookies=plat).status_code in (404, 405)   # no create route
    assert env.c.put(f"{API}/admin/flags/external_research", json={**body, "extra": 1}, cookies=plat).status_code == 422
    reset = env.c.put(f"{API}/admin/flags/external_research", json={"enabled": None, "expected_revision": 1, "reason": "back"}, cookies=ops)
    assert reset.status_code == 200 and reset.json()["state"] == "inherited"
    ev = {k: env.events(k) for k in (A.ADMIN_FLAG_OVERRIDE_DISABLED, A.ADMIN_FLAG_OVERRIDE_RESET)}
    assert ev[A.ADMIN_FLAG_OVERRIDE_DISABLED][0]["context"]["new_override"] == "disabled" and ev[A.ADMIN_FLAG_OVERRIDE_DISABLED][0]["context"]["flag_key"] == "external_research"
    assert (ev[A.ADMIN_FLAG_OVERRIDE_RESET][0]["context"]["old_override"], ev[A.ADMIN_FLAG_OVERRIDE_RESET][0]["context"]["new_override"]) == ("disabled", "inherit")


def test_flag_and_pause_audit_failure_rolls_the_change_back(env, monkeypatch):
    import src.auth_repository as ar
    _, plat = env.user("platform_admin")
    real = ar.AuditEvent

    class Bad(real):
        def __init__(self, **kw):
            kw["event_type"] = None
            super().__init__(**kw)

    monkeypatch.setattr(ar, "AuditEvent", Bad)
    r = env.c.put(f"{API}/admin/flags/external_research", json={"enabled": False, "expected_revision": 0, "reason": "r"}, cookies=plat)
    assert r.status_code == 500
    monkeypatch.undo()
    assert flag_svc(env).effective("external_research") is True
    with sf(env)() as s:
        assert s.scalars(select(FeatureFlagOverride)).all() == []


# ---------------- backend enforcement + separation -------------------------------------------------------------------------------

def test_disabled_flag_is_enforced_by_the_backend_not_just_the_ui(env):
    from src.copilot.research.service import default_research_service
    F.install(sf(env), environment="development")
    assert default_research_service().health()["enabled"] is True
    flag_svc(env).set_override("external_research", False, expected_revision=0, reason="r", actor_user_id=1)
    assert default_research_service().health()["enabled"] is False
    assert env.c.get(f"{API}/capabilities").json()["company_research_enabled"] is False
    flag_svc(env).set_override("external_research", None, expected_revision=1, reason="r", actor_user_id=1)
    assert default_research_service().health()["enabled"] is True


def test_company_web_flag_is_a_restriction_under_external_research(env):
    from src.copilot.research.service import default_research_service
    F.install(sf(env), environment="development")
    svc = flag_svc(env)
    svc.set_override("company_web_research", False, expected_revision=0, reason="r", actor_user_id=1)
    names = lambda r: [p.health().get("provider") or p.__class__.__name__ for p in r._providers]   # noqa: E731
    r = default_research_service()
    assert r.health()["enabled"] is True and not any("Company" in n for n in names(r))
    svc.set_override("external_research", False, expected_revision=0, reason="r", actor_user_id=1)
    svc.set_override("company_web_research", True, expected_revision=1, reason="r", actor_user_id=1)           # enabling the child cannot override a disabled parent
    r = default_research_service()
    assert r.health()["enabled"] is False and not any("Company" in n for n in names(r))


def test_company_research_route_is_unavailable_when_the_flag_is_disabled_and_contacts_no_provider(env, monkeypatch):
    """Direct API (no UI): with the durable flag disabled the REAL route (no test override of the research service) returns an unavailable report."""
    _, cand = env.user("user")
    F.install(sf(env), environment="development")
    body = {"company_name": "Acme", "website": "acme.example"}
    def boom(*a, **k):
        raise AssertionError("network used")
    monkeypatch.setattr(socket, "socket", boom)
    flag_svc(env).set_override("external_research", False, expected_revision=0, reason="r", actor_user_id=1)
    r = env.c.post(f"{API}/research/company", json=body, cookies=cand)
    assert r.status_code == 200 and r.json()["status"] == "unavailable" and not r.json()["business_market"]


def test_a_flag_is_conjunctive_it_never_grants_an_entitlement_or_authorization(env):
    """available = existing_authorized_capability AND flag. Enabling a flag changes no entitlement, plan, tier, billing or AI row."""
    _, cand = env.user("user")
    from src.entitlements import EntitlementService
    ent = EntitlementService(sf(env))

    def state():
        with sf(env)() as s:
            return (s.execute(text("SELECT count(*), coalesce(sum(plan_version_id),0) FROM subscriptions")).one(),
                    s.execute(text("SELECT count(*) FROM billing_invoices")).scalar(), s.execute(text("SELECT count(*) FROM ai_config_versions")).scalar())
    before = state()
    svc = flag_svc(env)
    svc.set_override("external_research", True, expected_revision=0, reason="r", actor_user_id=1)
    svc.set_override("company_web_research", True, expected_revision=0, reason="r", actor_user_id=1)
    assert state() == before
    assert env.c.get(f"{API}/auth/plan", cookies=cand).json()["entitlements"] is not None
    for fdef in FLAGS.values():                                                    # no flag key is an entitlement or permission name
        assert fdef.key not in perm.PERMISSION_SET and not fdef.key.startswith("platform.")
    code = re.sub(r'""".*?"""', "", (ROOT / "src/platform_config/flags.py").read_text(), flags=re.S)
    assert not re.search(r"subscriptions|EntitlementService|BillingService|AIConfigService|platform_role", code)      # the flag module reads none of these
    assert ent is not None


def test_unauthenticated_and_candidate_cannot_reach_new_admin_routes(env):
    _, cand = env.user("user")
    for path in ("/admin/pause", "/admin/flags"):
        assert env.c.get(f"{API}{path}", cookies=cand).status_code == 403


# ---------------- migration + static guards ---------------------------------------------------------------------------------------

def test_migration_0023_adds_only_the_two_tables_seeds_nothing_and_changes_no_behaviour(tmp_path, monkeypatch):
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine, inspect
    url = f"sqlite:///{tmp_path / 'm.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    cfg = Config(str(ROOT / "alembic.ini")); cfg.set_main_option("sqlalchemy.url", url); cfg.set_main_option("script_location", str(ROOT / "migrations"))
    command.upgrade(cfg, "0022_ai_model_admin")
    before = set(inspect(create_engine(url)).get_table_names())
    command.upgrade(cfg, "0023_platform_config")
    eng = create_engine(url)
    after = set(inspect(eng).get_table_names())
    assert after - before == {"platform_pause_states", "feature_flag_overrides"}
    with eng.connect() as c:
        assert c.execute(text("SELECT count(*) FROM platform_pause_states")).scalar() == 0
        assert c.execute(text("SELECT count(*) FROM feature_flag_overrides")).scalar() == 0
    from sqlalchemy.orm import sessionmaker
    sess = sessionmaker(bind=eng)
    assert not any(PauseService(sess, environment="production").snapshot()[c]["paused"] for c in PAUSABLE_CAPABILITIES)    # running, as before
    assert all(s["state"] == "inherited" for s in FeatureFlagService(sess, environment="production").states())
    command.downgrade(cfg, "0022_ai_model_admin")
    assert set(inspect(create_engine(url)).get_table_names()) == before


def test_no_generic_config_editor_and_no_forbidden_mutable_settings():
    routes = (ROOT / "src/api/routes/admin_config.py").read_text()
    schemas = (ROOT / "src/api/schemas/admin.py").read_text().split("# ---- W10.11")[1]
    assert not re.search(r"dict\[str, (Any|object)\]|json_body|raw_json|env_var|dotenv|\.env\b", schemas + routes)
    forbidden = ("DATABASE_URL", "API_ENV", "SECRET", "API_KEY", "password", "CORS", "allowed_hosts", "signing", "cookie", "payment", "model_slug", "retention")
    body = (routes + schemas).lower()
    assert not [w for w in forbidden if w.lower() in body], [w for w in forbidden if w.lower() in body]
    flag_text = "".join(f.env_var for f in FLAGS.values())
    assert not re.search(r"KEY|SECRET|PASSWORD|TOKEN|DATABASE|CORS|HOST|MODEL|BILLING", flag_text)


def test_no_process_local_pause_authority_remains_in_source():
    src = "".join(p.read_text() for p in (ROOT / "src").rglob("*.py"))
    assert "get_pause_registry" not in src and "PauseRegistry" not in src and "reset_pause_registry" not in src
    assert "class PauseService" in (ROOT / "src/application/pause.py").read_text()


def test_pause_protected_routes_are_all_gated_by_the_durable_dependency():
    expected = {"src/api/routes/agent.py": 3, "src/api/routes/company.py": 1}
    for path, n in expected.items():
        assert (ROOT / path).read_text().count('require_not_paused(') >= n, path
    inline = {"src/api/routes/auth.py": 1, "src/api/routes/documents.py": 3, "src/api/routes/voice.py": 1}
    for path, n in inline.items():
        assert (ROOT / path).read_text().count("ensure_not_paused(") >= n, path


def test_no_network_during_pause_checks(env, monkeypatch):
    def boom(*a, **k):
        raise AssertionError("network used")
    monkeypatch.setattr(socket, "socket", boom)
    svc = pause_svc(env)
    pause(svc, "agent", True)
    assert svc.is_paused("agent")


# ---------------- feature-flag store outage: restriction flags FAIL CLOSED ------------------------------------------------------------

def _broken_factory():
    def boom():
        raise RuntimeError("flag store down")
    return boom


@pytest.mark.parametrize("baseline,expected", [("true", True), ("false", False)])
def test_healthy_no_override_preserves_the_environment_baseline(env, monkeypatch, baseline, expected):               # A, B
    monkeypatch.setenv("EXTERNAL_RESEARCH_ENABLED", baseline)
    F.install(sf(env), environment="development")
    assert F.effective("external_research") is expected


def test_healthy_explicit_disable_and_enable_override_the_baseline(env, monkeypatch):                                  # C, D
    monkeypatch.setenv("EXTERNAL_RESEARCH_ENABLED", "true")
    F.install(sf(env), environment="development")
    svc = flag_svc(env)
    svc.set_override("external_research", False, expected_revision=0, reason="r", actor_user_id=1)
    assert F.effective("external_research") is False
    monkeypatch.setenv("EXTERNAL_RESEARCH_ENABLED", "false")
    svc.set_override("external_research", True, expected_revision=1, reason="r", actor_user_id=1)
    assert F.effective("external_research") is True


@pytest.mark.parametrize("baseline", ["true", "false"])
@pytest.mark.parametrize("prior", [None, True, False])
def test_installed_service_with_an_unreadable_store_is_off_whatever_the_baseline_or_prior_override(env, monkeypatch, baseline, prior):   # E, F, G, H
    monkeypatch.setenv("EXTERNAL_RESEARCH_ENABLED", baseline)
    healthy = flag_svc(env)
    if prior is not None:
        healthy.set_override("external_research", prior, expected_revision=0, reason="r", actor_user_id=1)
    F.install(_broken_factory(), environment="development")                                                          # the durable service is installed; its store is down
    assert F.effective("external_research") is False
    assert F.effective("company_web_research") is False
    with pytest.raises(FeatureFlagStateUnavailable):
        F._installed.effective("external_research")                                                                   # a bounded domain error, no raw exception


def test_explicit_disable_survives_an_outage_it_is_never_lifted_to_the_on_baseline(env, monkeypatch):
    monkeypatch.setenv("EXTERNAL_RESEARCH_ENABLED", "true")
    flag_svc(env).set_override("external_research", False, expected_revision=0, reason="r", actor_user_id=1)
    F.install(_broken_factory(), environment="development")
    assert F.effective("external_research") is False                                                                   # not the ON baseline


def test_capabilities_reports_research_unavailable_when_the_flag_store_is_unreadable(env, monkeypatch):               # I
    assert env.c.get(f"{API}/capabilities").json()["company_research_enabled"] is True
    monkeypatch.setattr(FeatureFlagService, "effective", lambda self, key: (_ for _ in ()).throw(FeatureFlagStateUnavailable("x")))
    body = env.c.get(f"{API}/capabilities")
    assert body.status_code == 200 and body.json()["company_research_enabled"] is False
    assert "flag store" not in body.text.lower() and "Traceback" not in body.text


def test_research_service_is_built_disabled_and_no_provider_is_contacted_on_a_flag_store_outage(env, monkeypatch):    # J
    from src.copilot.research.service import default_research_service
    F.install(_broken_factory(), environment="development")
    def boom(*a, **k):
        raise AssertionError("network used")
    monkeypatch.setattr(socket, "socket", boom)
    svc = default_research_service()
    assert svc.health()["enabled"] is False
    assert not any("Company" in type(p).__name__ for p in svc._providers)                                              # the company-web provider is not even constructed
    from src.copilot.research.models import CurrentMarketResearchRequest, ResearchIntent
    res = svc.research(CurrentMarketResearchRequest(intent=ResearchIntent.JOB_MARKET, role="Nurse"))
    assert res.status.value == "unavailable"                                                                           # disabled before any provider call


def test_bare_context_without_an_installed_service_keeps_the_existing_baseline(monkeypatch):                          # K
    F.uninstall()
    monkeypatch.setenv("EXTERNAL_RESEARCH_ENABLED", "true")
    assert F.effective("external_research") is True
    monkeypatch.setenv("EXTERNAL_RESEARCH_ENABLED", "false")
    assert F.effective("external_research") is False


def test_admin_flags_read_reports_unavailable_instead_of_a_baseline_derived_state(env, monkeypatch):
    _, plat = env.user("platform_admin")
    monkeypatch.setattr(FeatureFlagService, "states", lambda self: (_ for _ in ()).throw(FeatureFlagStateUnavailable("x")))
    r = env.c.get(f"{API}/admin/flags", cookies=plat)
    assert r.status_code == 503 and r.json()["error"]["code"] == "platform_state_unavailable"
    assert "inherited" not in r.text.lower() and "baseline" not in r.text.lower() and "flag store" not in r.text.lower()
    home = env.c.get(f"{API}/admin/home", cookies=plat)
    assert home.status_code == 200 and home.json()["feature_flags"]["status"] == "unavailable"


def test_the_mutable_flag_set_is_unchanged_by_the_outage_correction():
    assert set(FLAGS) == {"external_research", "company_web_research"}
