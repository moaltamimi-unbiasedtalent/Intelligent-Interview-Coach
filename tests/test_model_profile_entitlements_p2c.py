"""W12.4D-P2-C: gated Basic/Premium AI model-profile authorization, fallback safety and the quality-evaluation framework. FULLY OFFLINE: recording fakes stand in for
every provider-backed service, entitlement state is synthetic, and every non-loopback socket fails the test. ``MODEL_PROFILE_ENFORCED`` is a code constant that is
OFF; tests flip it on an isolated module attribute only. Nothing here is Stripe evidence, and mocked runs say nothing about model QUALITY."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import Request
from fastapi.testclient import TestClient

from src import constants
from src.api import dependencies as deps
from src.api.main import create_app
from src.application import model_profile_access as MP
from src.application.interview_service import InterviewApplicationService
from src.llm.models import ModelProfile, known_profile_for_slug, model_id
from src.model_quality import harness as H
from tests.test_api import _config_body, _evaluation, _FakeClient, _FakeEval, _FakeRepo, _FakeReport, _question, _strategy, _usage

ROOT = Path(__file__).resolve().parents[1]
FAST, BALANCED, ADVANCED = ModelProfile.FAST, ModelProfile.BALANCED, ModelProfile.ADVANCED


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    import socket

    real = socket.socket.connect

    def guarded(self, address, *a, **k):
        host = address[0] if isinstance(address, tuple) else str(address)
        if host not in ("127.0.0.1", "::1", "localhost", "testserver") and not str(host).startswith("/"):
            raise AssertionError(f"network access attempted: {address}")
        return real(self, address, *a, **k)
    monkeypatch.setattr(socket.socket, "connect", guarded)


@pytest.fixture(autouse=True)
def _fresh_limiter():
    from src.api import rate_limit as rl
    rl.reset_rate_limiter(rl.InMemoryRateLimiter())
    yield
    rl.reset_rate_limiter(rl.InMemoryRateLimiter())


@pytest.fixture()
def on(monkeypatch):
    monkeypatch.setattr(MP, "MODEL_PROFILE_ENFORCED", True)


class Plans:
    """Synthetic EntitlementService stand-in: user id -> plan summary. Never a real subscription, never Stripe."""

    def __init__(self, table=None, boom=()):
        self.table, self.boom = table or {}, set(boom)

    def plan_summary(self, user_id, **k):
        if user_id in self.boom:
            raise RuntimeError("entitlement unreadable")
        return self.table.get(user_id, {"plan_code": "basic", "source": "fallback_default"})


PREMIUM = {"plan_code": "premium", "source": "subscription", "entitlements": {"premium_preview": {"enabled": True}}}
EXPIRED = {"plan_code": "basic", "source": "fallback_default"}                           # an ended subscription resolves to the Basic fallback
FORGED = {"plan_code": "premium", "source": "fallback_default"}                           # a premium LABEL that is not an active subscription
PREVIEW_ONLY = {"plan_code": "basic", "source": "subscription", "entitlements": {"premium_preview": {"enabled": True}}}


def policy(**plans):
    return MP.ModelProfileAccessPolicy(Plans(plans))


# ================================================================ 1. NAMING AND DEFAULTS =====================================================================

def test_the_official_profiles_are_fast_balanced_advanced_and_there_is_no_medium_profile():
    assert [p.value for p in ModelProfile] == ["fast", "balanced", "advanced"]
    assert [p.name for p in ModelProfile] == ["FAST", "BALANCED", "ADVANCED"]
    assert not any("medium" == p.value or "medium" == p.name.lower() for p in ModelProfile)
    assert set(MP.PROFILE_DESCRIPTIONS) == set(ModelProfile)


def test_the_gate_is_a_disabled_code_constant_and_practice_keeps_its_balanced_default():
    assert MP.MODEL_PROFILE_ENFORCED is False and MP.PRACTICE_DEFAULT_PROFILE is BALANCED
    from src.models import ModelSettings
    assert ModelSettings().model == constants.DEFAULT_MODEL == model_id(BALANCED)                # an existing Basic account is NOT moved to Fast


def test_no_new_text_in_the_policy_module_or_catalogue_makes_a_quality_price_or_upgrade_claim():
    blob = " ".join(MP.PROFILE_DESCRIPTIONS.values()).lower()
    for word in ("best", "better", "faster", "smarter", "premium", "upgrade", "price", "$", "€", "guarantee", "most accurate"):
        assert word not in blob, word


# ================================================================ 2. THE CANONICAL POLICY (ENFORCED) =========================================================

@pytest.mark.parametrize("profile", ["fast"])
def test_basic_may_use_fast(on, profile):
    assert policy().authorize(1, profile, workflow="practice") is FAST


@pytest.mark.parametrize("profile", ["balanced", "advanced"])
@pytest.mark.parametrize("workflow", ["practice", "agent"])
def test_basic_is_refused_balanced_and_advanced_before_anything_else(on, profile, workflow):
    with pytest.raises(MP.ModelProfileNotAuthorized):
        policy().authorize(1, profile, workflow=workflow)


@pytest.mark.parametrize("profile", ["fast", "balanced", "advanced"])
def test_premium_may_use_all_three(on, profile):
    assert policy(**{}).decide(1).reason == "basic"
    p = MP.ModelProfileAccessPolicy(Plans({7: PREMIUM}))
    assert p.authorize(7, profile, workflow="agent") is ModelProfile(profile)


def test_defaults_when_nothing_is_requested(on):
    p = MP.ModelProfileAccessPolicy(Plans({7: PREMIUM}))
    assert p.authorize(1, None, workflow="practice") is FAST                                      # target allocation for Basic (not active until qualified)
    assert p.authorize(7, None, workflow="practice") is BALANCED                                  # Premium keeps the existing Balanced default


@pytest.mark.parametrize("state,plan", [("expired", EXPIRED), ("forged label", FORGED), ("premium_preview only", PREVIEW_ONLY)])
def test_only_an_active_premium_subscription_is_premium(on, state, plan):
    p = MP.ModelProfileAccessPolicy(Plans({3: plan}))
    assert p.decide(3).reason == "basic" and p.decide(3).allowed == frozenset({FAST}), state
    with pytest.raises(MP.ModelProfileNotAuthorized):
        p.authorize(3, "advanced", workflow="practice")


def test_an_unreadable_or_unknown_subscription_state_never_grants_premium(on):
    p = MP.ModelProfileAccessPolicy(Plans({4: PREMIUM}, boom={4}))
    d = p.decide(4)
    assert d.reason == "unresolved" and d.allowed == frozenset({FAST})
    with pytest.raises(MP.ModelProfileNotAuthorized):
        p.authorize(4, "balanced", workflow="agent")
    odd = MP.ModelProfileAccessPolicy(Plans({5: {"plan_code": "enterprise_gold", "source": "subscription"}}))
    assert odd.decide(5).allowed == frozenset({FAST})


@pytest.mark.parametrize("bad", ["openai/gpt-5.6-sol", "openai/gpt-5.6-terra", "gpt-5", "medium", "Fast", "FAST", " fast", "advanced ", "", "premium", "../x", 7, ["fast"]])
def test_a_provider_model_id_alias_wrong_case_or_unsupported_profile_is_rejected(on, bad):
    with pytest.raises(MP.ModelProfileInvalid):
        policy().authorize(1, bad, workflow="practice")


def test_cross_user_isolation_and_no_caching(on):
    plans = Plans({1: PREMIUM})
    p = MP.ModelProfileAccessPolicy(plans)
    assert p.authorize(1, "advanced", workflow="agent") is ADVANCED
    with pytest.raises(MP.ModelProfileNotAuthorized):
        p.authorize(2, "advanced", workflow="agent")                                               # another user is unaffected
    plans.table[1] = EXPIRED
    with pytest.raises(MP.ModelProfileNotAuthorized):
        p.authorize(1, "advanced", workflow="agent")                                               # a plan change applies on the very next call


def test_a_synthetic_decision_is_refused_in_a_hosted_environment(monkeypatch):
    monkeypatch.setenv("API_ENV", "production")
    with pytest.raises(ValueError):
        MP.ModelProfileAccessPolicy(Plans(), override=lambda uid: "premium")
    monkeypatch.setenv("API_ENV", "test")
    assert MP.ModelProfileAccessPolicy(Plans(), override=lambda uid: "premium") is not None


# ================================================================ 3. DEFAULT-DISABLED BEHAVIOUR ==============================================================

def test_while_disabled_nothing_changes_for_any_candidate_and_no_selector_exists_for_practice():
    p = policy()
    d = p.decide(1)
    assert (d.enforced, d.reason, d.default) == (False, "gate_disabled", BALANCED) and d.allowed == frozenset(ModelProfile)
    assert p.authorize(1, None, workflow="practice") is None                                      # untouched: today's behaviour
    assert p.authorize(1, "balanced", workflow="practice") is BALANCED
    for refused in ("fast", "advanced"):
        with pytest.raises(MP.ModelProfileNotAvailable):
            p.authorize(1, refused, workflow="practice")                                           # not a working free selector while Premium is inactive
    assert p.authorize(1, None, workflow="agent") is None                                          # Mo: exactly what the candidate sent, as today
    assert p.authorize(1, "advanced", workflow="agent") is ADVANCED
    assert p.catalogue(1)["selector_active"] is False


def test_an_override_cannot_enable_the_gate_and_premium_labels_change_nothing_while_disabled():
    p = MP.ModelProfileAccessPolicy(Plans({1: PREMIUM}), override=lambda uid: "premium")
    assert p.decide(1).reason == "gate_disabled"


# ================================================================ 4. FALLBACK AND FLOOR SAFETY ===============================================================

def test_the_existing_operation_floor_can_raise_a_profile_so_the_authorized_guard_is_required():
    from src.llm.policy import ModelOperation, resolve_policy
    raised = resolve_policy(ModelOperation.ORCHESTRATION, FAST)
    assert raised.profile is BALANCED and raised.capability_capped is True                         # documented existing behaviour (no authorized set supplied)


def test_with_an_authorized_set_a_floor_raise_is_a_controlled_failure_not_a_silent_escalation():
    from src.llm.policy import ModelOperation, resolve_policy
    with pytest.raises(MP.ModelProfileNotAuthorized):
        resolve_policy(ModelOperation.ORCHESTRATION, FAST, authorized=frozenset({FAST}))
    ok = resolve_policy(ModelOperation.ORCHESTRATION, FAST, authorized=frozenset(ModelProfile))
    assert ok.profile is BALANCED


def test_fallbacks_only_go_down_and_only_inside_the_authorized_set():
    assert MP.authorized_fallbacks(ADVANCED, FAST, frozenset(ModelProfile)) == [BALANCED, FAST]
    assert MP.authorized_fallbacks(ADVANCED, FAST, frozenset({FAST})) == [FAST]
    assert MP.authorized_fallbacks(FAST, FAST, frozenset(ModelProfile)) == []                      # nothing below Fast: a controlled failure, never a switch up
    assert all(p is not ADVANCED for p in MP.authorized_fallbacks(BALANCED, FAST, frozenset(ModelProfile)))
    from src.llm.policy import ModelOperation, resolve_policy
    r = resolve_policy(ModelOperation.STRUCTURED_GENERATION, ADVANCED, authorized=frozenset({BALANCED, ADVANCED}))
    assert all(p in {BALANCED, ADVANCED} for p in r.fallback_profiles)


def test_the_live_request_path_performs_no_cross_profile_fallback():
    """Inspection-backed: no live code consumes ``fallback_profiles``; a call uses one model and retries the SAME model (bounded transient retry)."""
    offenders = []
    for path in (ROOT / "src").rglob("*.py"):
        rel = str(path.relative_to(ROOT))
        if rel.startswith(("src/llm/policy.py", "src/ai_admin", "src/agent/multi_agent_eval.py", "src/application/prompt_lab", "src/config_versions.py", "src/api/schemas/admin.py")):
            continue
        if "fallback_profiles" in path.read_text(encoding="utf-8"):
            offenders.append(rel)
    assert offenders == []


# ================================================================ 5. PRACTICE ROUTE ==========================================================================

class RecordingDomain:
    def __init__(self):
        self.calls = []

    def generate_strategy(self, config, settings):
        self.calls.append(("strategy", settings.model))
        return _strategy(), _usage()

    def generate_next_question(self, config, settings, *, current_question_number, history):
        self.calls.append(("question", settings.model))
        return _question(current_question_number), _usage()


def practice_client(plans, domain):
    app = create_app()
    repo = _FakeRepo()

    def _interview():
        return InterviewApplicationService(config=None, services=(domain, _FakeEval(), _FakeReport(), _FakeClient()))

    from tests._interview_factories import make_durable_store
    store = make_durable_store()
    app.dependency_overrides[deps.get_career_service] = lambda: None
    app.dependency_overrides[deps.get_interview_service] = _interview
    app.dependency_overrides[deps.get_repository] = lambda: repo
    app.dependency_overrides[deps.get_app_config] = lambda: None
    app.dependency_overrides[deps.get_session_store] = lambda: store

    def _uid(request: Request) -> int:
        return int(request.headers["x-test-user"])
    app.dependency_overrides[deps.get_current_user_id] = _uid
    app.dependency_overrides[deps.get_entitlement_service] = lambda: plans
    return TestClient(app, raise_server_exceptions=False)


def create(c, user, **extra):
    body = {**_config_body(), **extra}
    return c.post("/api/v1/interviews", json=body, headers={"x-test-user": str(user)})


def test_practice_default_is_balanced_while_the_gate_is_disabled_for_every_plan():
    domain = RecordingDomain()
    c = practice_client(Plans({2: PREMIUM}), domain)
    for user in (1, 2):
        assert create(c, user).status_code == 200
    assert {m for _t, m in domain.calls} == {constants.DEFAULT_MODEL}                              # Basic AND Premium: Balanced, exactly as before


def test_while_disabled_a_profile_selector_is_not_working_and_no_provider_is_called():
    domain = RecordingDomain()
    c = practice_client(Plans({2: PREMIUM}), domain)
    for profile in ("fast", "advanced"):
        r = create(c, 2, model_profile=profile)
        assert r.status_code == 422 and r.json()["error"]["code"] == "model_profile_not_available" and domain.calls == []
    assert create(c, 2, model_profile="balanced").status_code == 200                              # the existing default is accepted (backward compatible)


@pytest.mark.parametrize("bad", ["openai/gpt-5.6-sol", "medium", "FAST", "x", 5])
def test_malformed_or_raw_model_ids_fail_validation_in_every_state(on, bad):
    domain = RecordingDomain()
    c = practice_client(Plans(), domain)
    assert create(c, 1, model_profile=bad).status_code == 422 and domain.calls == []


def test_enforced_basic_defaults_to_fast_and_a_denied_profile_never_reaches_a_provider(on):
    domain = RecordingDomain()
    c = practice_client(Plans({2: PREMIUM}), domain)
    assert create(c, 1).status_code == 200
    assert {m for _t, m in domain.calls} == {constants.LOW_COST_MODEL}                             # the TARGET allocation, reachable only with the gate on
    domain.calls.clear()
    for profile in ("balanced", "advanced"):
        r = create(c, 1, model_profile=profile)
        assert r.status_code == 403 and r.json()["error"]["code"] == "model_profile_not_authorized"
        assert "Basic" not in r.text and "upgrade" not in r.text.lower() and "premium" not in r.text.lower() and profile not in r.text
    assert domain.calls == []                                                                      # authorization happened before any provider invocation


def test_enforced_premium_reaches_each_authorized_profile_through_the_mocked_provider(on):
    for profile, slug in (("fast", constants.LOW_COST_MODEL), ("balanced", constants.DEFAULT_MODEL), ("advanced", constants.HIGH_CAPABILITY_MODEL)):
        domain = RecordingDomain()
        c = practice_client(Plans({2: PREMIUM}), domain)
        assert create(c, 2, model_profile=profile).status_code == 200
        assert {m for _t, m in domain.calls} == {slug}                                             # the slug comes from the server registry, never the client


def test_the_client_cannot_choose_a_provider_endpoint_or_model_id(on):
    domain = RecordingDomain()
    c = practice_client(Plans({2: PREMIUM}), domain)
    r = create(c, 2, model_profile="advanced", model="openai/gpt-4", base_url="https://evil.test", provider="x")
    assert r.status_code == 200 and {m for _t, m in domain.calls} == {constants.HIGH_CAPABILITY_MODEL}      # unknown fields are ignored, never used


def test_a_forged_premium_flag_or_preview_cannot_unlock_profiles_through_the_api(on):
    domain = RecordingDomain()
    c = practice_client(Plans({3: FORGED, 4: PREVIEW_ONLY}), domain)
    for user in (3, 4):
        r = c.post("/api/v1/interviews", json={**_config_body(), "model_profile": "advanced"},
                   headers={"x-test-user": str(user), "x-plan": "premium", "x-tier": "premium"})
        assert r.status_code == 403
    assert domain.calls == []


def test_practice_idempotent_replay_keeps_the_original_profile(on):
    domain = RecordingDomain()
    c = practice_client(Plans({2: PREMIUM}), domain)
    h = {"x-test-user": "2", "idempotency-key": "p2c-replay-0001"}
    first = c.post("/api/v1/interviews", json={**_config_body(), "model_profile": "advanced"}, headers=h)
    again = c.post("/api/v1/interviews", json={**_config_body(), "model_profile": "advanced"}, headers=h)
    assert first.status_code == again.status_code == 200 and first.json()["session_id"] == again.json()["session_id"]
    assert len(domain.calls) == 2                                                                  # strategy + first question once; the replay generated nothing


# ================================================================ 5b. OWNER DECISION A: DOWNGRADE AND MID-SESSION CONTINUATION ================================

class RecordingEval:
    def __init__(self):
        self.calls = []

    def evaluate_answer(self, config, question, answer, settings):
        self.calls.append(settings.model)
        return _evaluation(), _usage()


def session_client(plans, domain, evaluator):
    """Like ``practice_client`` but with a recording evaluator and access to the durable store (to prove nothing is lost or switched)."""
    from tests._interview_factories import make_durable_store
    app = create_app()
    repo = _FakeRepo()
    store = make_durable_store()

    def _interview():
        return InterviewApplicationService(config=None, services=(domain, evaluator, _FakeReport(), _FakeClient()))
    app.dependency_overrides[deps.get_career_service] = lambda: None
    app.dependency_overrides[deps.get_interview_service] = _interview
    app.dependency_overrides[deps.get_repository] = lambda: repo
    app.dependency_overrides[deps.get_app_config] = lambda: None
    app.dependency_overrides[deps.get_session_store] = lambda: store

    def _uid(request: Request) -> int:
        return int(request.headers["x-test-user"])
    app.dependency_overrides[deps.get_current_user_id] = _uid
    app.dependency_overrides[deps.get_entitlement_service] = lambda: plans
    return TestClient(app, raise_server_exceptions=False), store


def hdr(user):
    return {"x-test-user": str(user)}


def stored_model(store, session_id, user):
    return store.load_state(session_id, user).data.settings.model


def test_decision_a_a_former_premium_account_cannot_keep_making_balanced_or_advanced_calls_and_nothing_is_lost_or_switched(on):
    plans = Plans({2: PREMIUM})
    domain, ev = RecordingDomain(), RecordingEval()
    c, store = session_client(plans, domain, ev)
    made = create(c, 2, model_profile="advanced").json()
    sid = made["session_id"]
    assert stored_model(store, sid, 2) == constants.HIGH_CAPABILITY_MODEL
    before_calls = len(domain.calls)
    assert c.post(f"/api/v1/interviews/{sid}/answers", json={"answer": "first answer"}, headers=hdr(2)).status_code == 200      # still Premium: continues on Advanced
    assert ev.calls == [constants.HIGH_CAPABILITY_MODEL]
    plans.table.pop(2)                                                                                # Premium ends: the account is Basic from the next request
    for path, body in ((f"/api/v1/interviews/{sid}/next-question", None), (f"/api/v1/interviews/{sid}/answers", {"answer": "second"})):
        r = c.post(path, json=body, headers=hdr(2)) if body else c.post(path, headers=hdr(2))
        assert r.status_code == 403 and r.json()["error"]["code"] == "model_profile_not_authorized", path
        assert "advanced" not in r.text.lower() and "upgrade" not in r.text.lower() and "premium" not in r.text.lower()
    assert len(domain.calls) == before_calls and ev.calls == [constants.HIGH_CAPABILITY_MODEL]       # no further provider invocation of any profile
    assert stored_model(store, sid, 2) == constants.HIGH_CAPABILITY_MODEL                              # NOT silently switched to Fast mid-session
    state = c.get(f"/api/v1/interviews/{sid}", headers=hdr(2))
    assert state.status_code == 200 and state.json()["session_id"] == sid                              # the stored session and its data stay readable
    plans.table[2] = PREMIUM                                                                           # re-upgrade restores continuation on the same session
    assert c.post(f"/api/v1/interviews/{sid}/next-question", headers=hdr(2)).status_code == 200
    assert stored_model(store, sid, 2) == constants.HIGH_CAPABILITY_MODEL


def test_decision_a_an_existing_balanced_session_cannot_continue_under_enforcement_for_basic_and_is_never_silently_switched(monkeypatch):
    plans = Plans()
    domain, ev = RecordingDomain(), RecordingEval()
    c, store = session_client(plans, domain, ev)
    sid = create(c, 1).json()["session_id"]                                                           # created while the gate is disabled: Balanced, exactly as today
    assert stored_model(store, sid, 1) == constants.DEFAULT_MODEL
    assert c.post(f"/api/v1/interviews/{sid}/answers", json={"answer": "a"}, headers=hdr(1)).status_code == 200
    ev_before, dom_before = len(ev.calls), len(domain.calls)
    monkeypatch.setattr(MP, "MODEL_PROFILE_ENFORCED", True)                                           # the gate is switched on later
    r = c.post(f"/api/v1/interviews/{sid}/next-question", headers=hdr(1))
    assert r.status_code == 403 and r.json()["error"]["code"] == "model_profile_not_authorized"
    assert (len(ev.calls), len(domain.calls)) == (ev_before, dom_before)
    assert stored_model(store, sid, 1) == constants.DEFAULT_MODEL                                      # the session was neither switched nor altered
    assert c.get(f"/api/v1/interviews/{sid}", headers=hdr(1)).status_code == 200                         # and stays readable


def test_decision_a_basic_sessions_created_under_enforcement_use_fast_and_continue_normally(on):
    plans = Plans()
    domain, ev = RecordingDomain(), RecordingEval()
    c, store = session_client(plans, domain, ev)
    sid = create(c, 1).json()["session_id"]
    assert stored_model(store, sid, 1) == constants.LOW_COST_MODEL
    assert c.post(f"/api/v1/interviews/{sid}/answers", json={"answer": "a"}, headers=hdr(1)).status_code == 200
    assert c.post(f"/api/v1/interviews/{sid}/next-question", headers=hdr(1)).status_code == 200
    assert {m for m in ev.calls} == {constants.LOW_COST_MODEL} and {m for _t, m in domain.calls} == {constants.LOW_COST_MODEL}


def test_decision_a_a_premium_account_defaults_to_balanced_and_may_continue_on_it(on):
    plans = Plans({2: PREMIUM})
    domain, ev = RecordingDomain(), RecordingEval()
    c, store = session_client(plans, domain, ev)
    sid = create(c, 2).json()["session_id"]
    assert stored_model(store, sid, 2) == constants.DEFAULT_MODEL
    assert c.post(f"/api/v1/interviews/{sid}/answers", json={"answer": "a"}, headers=hdr(2)).status_code == 200


def test_decision_a_every_provider_backed_practice_step_is_guarded_and_an_existing_report_stays_readable():
    import inspect

    from src.api.routes import interview
    src = inspect.getsource(interview)
    for name in ("submit_answer", "next_question", "start_deep_dive", "submit_deep_dive_answer", "next_deep_dive", "generate_report"):
        body = src[src.index(f"def {name}("):]
        body = body[:body.index("\n@router") if "\n@router" in body else len(body)]
        assert "_guard_session_profile(" in body and "get_model_profile_policy" in body, name
    for read_only in ("get_interview", "get_report", "return_from_deep_dive", "complete_interview", "recover_interview"):
        body = src[src.index(f"def {read_only}("):]
        body = body[:body.index("\n@router") if "\n@router" in body else len(body)]
        assert "_guard_session_profile(" not in body, read_only                                          # stored data and report fetches are never blocked by a profile
    report = src[src.index("def generate_report("):]
    assert report.index("if session.data.report is None:") < report.index("_guard_session_profile(")      # guarded only when generation (a provider call) is needed


def test_decision_a_while_disabled_no_session_step_is_affected_and_no_extra_work_is_done(monkeypatch):
    plans = Plans()
    domain, ev = RecordingDomain(), RecordingEval()
    c, store = session_client(plans, domain, ev)
    sid = create(c, 1).json()["session_id"]
    called = []
    real = MP.ModelProfileAccessPolicy.assert_authorized
    monkeypatch.setattr(MP.ModelProfileAccessPolicy, "assert_authorized", lambda self, u, p: called.append(p) or real(self, u, p))
    assert c.post(f"/api/v1/interviews/{sid}/answers", json={"answer": "a"}, headers=hdr(1)).status_code == 200
    assert c.post(f"/api/v1/interviews/{sid}/next-question", headers=hdr(1)).status_code == 200
    assert stored_model(store, sid, 1) == constants.DEFAULT_MODEL and MP.MODEL_PROFILE_ENFORCED is False   # Balanced, exactly as before


def test_decision_a_other_users_are_unaffected_by_one_users_downgrade(on):
    plans = Plans({2: PREMIUM, 3: PREMIUM})
    domain, ev = RecordingDomain(), RecordingEval()
    c, store = session_client(plans, domain, ev)
    s2 = create(c, 2, model_profile="advanced").json()["session_id"]
    s3 = create(c, 3, model_profile="advanced").json()["session_id"]
    plans.table.pop(2)
    assert c.post(f"/api/v1/interviews/{s2}/answers", json={"answer": "a"}, headers=hdr(2)).status_code == 403
    assert c.post(f"/api/v1/interviews/{s3}/answers", json={"answer": "a"}, headers=hdr(3)).status_code == 200


# ================================================================ 6. MO (AGENT) ROUTES ========================================================================

class RecordingAgent:
    def __init__(self, stored_profile="advanced"):
        self.runs, self.continues, self.gets, self.stored = [], [], 0, stored_profile

    def run(self, request, request_id=None):
        self.runs.append(request.profile)
        raise RuntimeError("stop after recording")

    def get_run(self, run_id, user_id, request_id=None):
        self.gets += 1
        return SimpleNamespace(profile=self.stored)

    def continue_run(self, run_id, user_id, message, request_id=None):
        self.continues.append(message)
        raise RuntimeError("stop after recording")

    def resume(self, *a, **k):
        self.continues.append("resume")
        raise RuntimeError("stop after recording")


def agent_client(plans, service):
    app = create_app()
    repo = _FakeRepo()
    app.dependency_overrides[deps.get_repository] = lambda: repo
    app.dependency_overrides[deps.get_agent_service] = lambda: service

    def _uid(request: Request) -> int:
        return int(request.headers["x-test-user"])
    app.dependency_overrides[deps.get_current_user_id] = _uid
    app.dependency_overrides[deps.get_entitlement_service] = lambda: plans
    return TestClient(app, raise_server_exceptions=False)


def run(c, user, **body):
    return c.post("/api/v1/agent/run", json={"goal": "prepare", **body}, headers={"x-test-user": str(user)})


def test_mo_keeps_todays_behaviour_while_the_gate_is_disabled():
    svc = RecordingAgent()
    c = agent_client(Plans(), svc)
    run(c, 1)
    run(c, 1, profile="advanced")
    assert svc.runs == [None, "advanced"] and svc.gets == 0                                        # unchanged, and no extra read


def test_enforced_basic_mo_runs_fast_by_default_and_cannot_request_more_before_any_service_call(on):
    svc = RecordingAgent()
    c = agent_client(Plans({2: PREMIUM}), svc)
    run(c, 1)
    assert svc.runs == ["fast"]
    svc.runs.clear()
    for profile in ("balanced", "advanced"):
        r = run(c, 1, profile=profile)
        assert r.status_code == 403 and r.json()["error"]["code"] == "model_profile_not_authorized"
    assert svc.runs == []                                                                          # no provider path was entered after the denial


def test_enforced_premium_mo_may_use_each_profile(on):
    svc = RecordingAgent()
    c = agent_client(Plans({2: PREMIUM}), svc)
    for profile in ("fast", "balanced", "advanced"):
        run(c, 2, profile=profile)
    assert svc.runs == ["fast", "balanced", "advanced"]


def test_a_malformed_agent_profile_fails_validation_and_never_reaches_the_service(on):
    svc = RecordingAgent()
    c = agent_client(Plans({2: PREMIUM}), svc)
    for bad in ("openai/gpt-5.6-sol", "medium", "ADVANCED"):
        assert run(c, 2, profile=bad).status_code == 422
    assert svc.runs == []


def test_a_downgraded_account_cannot_keep_spending_an_old_run_profile(on):
    svc = RecordingAgent(stored_profile="advanced")
    c = agent_client(Plans(), svc)                                                                 # user 1 is Basic now; the run was started on Advanced
    r = c.post("/api/v1/agent/runs/run_old_1/messages", json={"message": "continue"}, headers={"x-test-user": "1"})
    assert r.status_code == 403 and r.json()["error"]["code"] == "model_profile_not_authorized" and svc.continues == []
    r2 = c.post("/api/v1/agent/runs/run_old_1/resume", json={"action_id": "a1", "decision": "approve"}, headers={"x-test-user": "1"})
    assert r2.status_code == 403 and svc.continues == []
    premium = agent_client(Plans({1: PREMIUM}), RecordingAgent(stored_profile="advanced"))
    assert premium.post("/api/v1/agent/runs/run_old_1/messages", json={"message": "continue"}, headers={"x-test-user": "1"}).status_code != 403


def test_continue_and_resume_make_no_extra_read_while_the_gate_is_disabled():
    svc = RecordingAgent(stored_profile="advanced")
    c = agent_client(Plans(), svc)
    c.post("/api/v1/agent/runs/run_old_1/messages", json={"message": "continue"}, headers={"x-test-user": "1"})
    assert svc.gets == 0 and svc.continues == ["continue"]


# ================================================================ 7. METERING ATTRIBUTION AND RETRY ACCOUNTING ==============================================

def test_metering_attributes_the_actual_model_and_its_profile_and_counts_every_attempt(tmp_path):
    from sqlalchemy import select

    from src import ai_protection as AP
    from src.persistence import AIOperationEvent, User, init_db, make_engine, make_session_factory
    engine = make_engine(f"sqlite:///{tmp_path / 'm.db'}")
    init_db(engine)
    sf = make_session_factory(engine)
    with sf() as s:
        u = User(subject="u", provider="local", email="u@x.test")
        s.add(u)
        s.commit()
        uid = u.id
    for i, profile in enumerate(ModelProfile):
        scope = AP.AiOperationScope(user_id=uid, workflow="practice", operation="t", op_key=f"k{i}")
        scope.attempt(); scope.attempt()                                                            # a transient retry: two HTTP attempts, one logical operation
        scope.call_ok(model=model_id(profile), input_tokens=10, output_tokens=5, cost_usd=None, latency_ms=20)
        assert AP.persist_scope(sf, scope, status="succeeded", category=None) is True
    with sf() as s:
        rows = s.scalars(select(AIOperationEvent).order_by(AIOperationEvent.id)).all()
    assert [r.model_profile for r in rows] == ["fast", "balanced", "advanced"]
    assert all(r.provider_attempts == 2 and r.calls_ok == 1 and r.cost_usd_micros is None and r.cost_source == "unavailable" for r in rows)
    assert [known_profile_for_slug(r.model_id).value for r in rows] == ["fast", "balanced", "advanced"]


# ================================================================ 8. PLAN-AWARE CATALOGUE ====================================================================

def test_the_catalogue_endpoint_is_read_only_metadata_with_no_slug_price_or_upgrade(on):
    c = agent_client(Plans({2: PREMIUM}), RecordingAgent())
    basic = c.get("/api/v1/model-profiles", headers={"x-test-user": "1"}).json()
    premium = c.get("/api/v1/model-profiles", headers={"x-test-user": "2"}).json()
    assert basic["selector_active"] is True and basic["default"] == "fast"
    assert {p["id"]: p["authorized"] for p in basic["profiles"]} == {"fast": True, "balanced": False, "advanced": False}
    assert premium["default"] == "balanced" and all(p["authorized"] for p in premium["profiles"])
    text = str(basic).lower()
    for word in ("openai/", "gpt", "price", "upgrade", "checkout", "$", "€", "premium", "medium"):
        assert word not in text, word


def test_while_disabled_the_catalogue_reports_an_inactive_selector():
    c = agent_client(Plans(), RecordingAgent())
    body = c.get("/api/v1/model-profiles", headers={"x-test-user": "1"}).json()
    assert body["selector_active"] is False and body["default"] == "balanced"
    assert c.get("/api/v1/model-profiles").status_code in (401, 422, 500)                          # authenticated only


# ================================================================ 9. PRESERVED CONTROLS ======================================================================

def test_billing_gates_other_rollouts_and_permissions_are_unchanged():
    from src import ai_protection as AP
    from src.application import admin_permissions as perm
    from src.application import history_access as HA
    from src.billing import policy as P
    assert (P.LIVE_BILLING_ENABLED, P.EXTERNAL_CHECKOUT_AUTHORIZED, P.STRIPE_WEBHOOK_AUTHORIZED, P.RECONCILE_SCHEDULER_ENABLED, P.PROVIDER_READS_AUTHORIZED,
            P.PAID_ENTITLEMENT_POLICY_APPROVED) == (False,) * 6
    assert AP.AI_COST_LIMITS_ENFORCED is False and HA.HISTORY_RESTRICTIONS_ENFORCED is False and MP.MODEL_PROFILE_ENFORCED is False
    assert len(perm.PERMISSIONS) == 44


def test_the_policy_modules_contain_no_billing_or_entitlement_writer():
    for name in ("model_profile_access.py", "plan_state.py"):
        text = (ROOT / "src/application" / name).read_text().lower()
        code = text.split('"""', 2)[2]
        for banned in ("stripe", "src.billing", "subscription(", "insert(", "set_plan", "premium_preview", "session.add"):
            assert banned not in code, (name, banned)


def test_no_api_surface_introduces_a_medium_profile():
    for rel in ("src/api/schemas/interview.py", "src/api/schemas/agent.py"):
        text = (ROOT / rel).read_text()
        assert 'Literal["fast", "balanced", "advanced"]' in text, rel                            # exactly the three official profile ids
    assert "medium" not in (ROOT / "src/api/routes/model_profiles.py").read_text().lower().split('"""', 2)[2]


# ================================================================ 10. QUALITY-EVALUATION FRAMEWORK (OFFLINE VALIDATION ONLY) =================================

def _load_script():
    import importlib.util
    spec = importlib.util.spec_from_file_location("eval_model_quality_harness_under_test", ROOT / "scripts/eval_model_quality_harness.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _ok(task):
    return _load_script()._valid_output(task)


def test_the_scenario_set_is_synthetic_diverse_and_free_of_contact_data():
    sc = H.load_scenarios()
    assert len(sc) >= 10 and H.validate_scenarios(sc) == []
    assert len({s.industry for s in sc}) >= 8 and len({s.career_level for s in sc}) >= 6 and {s.difficulty for s in sc} == {"easy", "moderate", "hard"}
    raw = (ROOT / "evaluations/model_quality/scenarios.json").read_text()
    assert '"synthetic": true' in raw.lower() and "score" not in raw.lower()                       # no benchmark score is stored anywhere in the repository


def test_blinding_hides_profiles_is_reproducible_and_unblinds_only_with_the_key():
    sc = H.load_scenarios()[:3]
    cells = H.run_benchmark(lambda p, s, t: H.RunResult(ok=True, output=_ok(t), latency_ms=10, attempts=1), sc)
    sheet, key = H.blind(cells, seed=3)
    assert all(set(row) == {"scenario_id", "task", "label", "output", "ok"} for row in sheet)
    assert H.blind(cells, seed=3)[1] == key and H.blind(cells, seed=4)[1] != key
    assert set(key.values()) == {"fast", "balanced", "advanced"}


def test_aggregation_keeps_unknowns_unknown_and_never_computes_a_price():
    sc = H.load_scenarios()[:2]

    def runner(profile, s, task):
        if profile == "advanced":
            return H.RunResult(ok=False, error_category="timeout", attempts=2)
        return H.RunResult(ok=True, output=_ok(task), latency_ms=100 if profile == "fast" else 300, attempts=1, input_tokens=None, output_tokens=None, cost_usd=None)
    agg = H.aggregate(H.run_benchmark(runner, sc))
    assert agg["advanced"]["failure_rate"] == 1.0 and agg["fast"]["failure_rate"] == 0.0
    assert agg["fast"]["tokens_known_runs"] == 0 and agg["fast"]["tokens_unknown_runs"] == 4 and agg["fast"]["cost_usd_known_total"] is None
    assert agg["fast"]["latency_ms_p50"] == 100 and agg["advanced"]["retried_runs"] == 4


def test_structural_reliability_uses_the_applications_own_typed_contract():
    assert H.structural_check("question_generation", _ok("question_generation"))["valid"] is True
    assert H.structural_check("answer_feedback", {"overall_score": 500})["valid"] is False
    assert H.structural_check("answer_feedback", None)["reason"] == "no_output"


def test_the_gate_never_qualifies_a_profile_without_real_ratings_and_approved_thresholds():
    agg = {"fast": {"failure_rate": 0.0, "structural_invalid_rate": 0.0}}
    assert H.evaluate_gate(agg, None, None)["verdict"] == "NOT_EVALUATED"
    assert H.evaluate_gate(agg, {"fast|question_relevance": 5.0}, None)["verdict"] == "NOT_EVALUATED"
    assert H.evaluate_gate(agg, {"fast|question_relevance": 5.0}, H.Thresholds("", "", {"question_relevance": 4.0}, 0.1, 0.1))["verdict"] == "NOT_EVALUATED"
    good = H.Thresholds("owner", "documented rationale", {"question_relevance": 4.0}, 0.1, 0.1)
    assert H.evaluate_gate(agg, {"fast|question_relevance": 4.5}, good)["verdict"] == "PASS"
    assert H.evaluate_gate(agg, {"fast|question_relevance": 3.0}, good)["verdict"] == "FAIL"


def test_a_raw_provider_id_can_never_be_benchmarked_and_ratings_are_validated():
    sc = H.load_scenarios()[:1]
    with pytest.raises(ValueError):
        H.run_benchmark(lambda p, s, t: H.RunResult(ok=True), sc, profiles=["openai/gpt-5.6-sol"])
    sheet, key = H.blind(H.run_benchmark(lambda p, s, t: H.RunResult(ok=True, output=_ok(t)), sc), seed=1)
    label = sheet[0]["label"]
    with pytest.raises(ValueError):
        H.apply_ratings(key, [{"scenario_id": sc[0].id, "task": sheet[0]["task"], "label": label, "dimension": "question_relevance", "score": 9}])
    means = H.apply_ratings(key, [{"scenario_id": sc[0].id, "task": sheet[0]["task"], "label": label, "dimension": "question_relevance", "score": 4}])
    assert list(means.values()) == [4]


def test_the_harness_makes_no_provider_call_and_imports_no_provider_client():
    text = (ROOT / "src/model_quality/harness.py").read_text()
    for banned in ("openrouter", "httpx", "requests", "langchain", "openai", "socket", "os.environ"):
        assert banned not in text.lower().split('"""', 2)[2], banned


def test_the_framework_evaluator_passes_and_says_it_is_not_quality_evidence():
    res = _load_script().run()
    assert res and all(ok for ok, _ in res.values())
    assert "NOT" in (ROOT / "scripts/eval_model_quality_harness.py").read_text() and "Fast quality is NOT established" in (ROOT / "scripts/eval_model_quality_harness.py").read_text()
