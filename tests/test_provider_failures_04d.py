"""04D (DEMO-02, REQ-CAND-01, IR-DEMO-KEY): the AI provider mode, accurate provider-failure answers, the Start Interview regression, the explicit offline switch and the safe record of a failure.

Offline evidence only: fixture model replies or no client at all, a temp database, no provider, no network, no paid call.

THE OWNER-NAMED START INTERVIEW REGRESSION. The failure observed earlier: a KEYLESS stack answered Start Interview with 503 ``service_unavailable`` and a message about a missing OpenRouter key; the Candidate UI
(which renders fixed copy by status) showed the same generic "temporarily unavailable" it shows for a passing outage, and a keyless stack looked exactly like the live one. ``test_keyless_start_interview_*``
below assert the stable code ``ai_not_configured`` with fixed copy that names no provider, key or variable; they FAIL against the pre-04D server (code ``service_unavailable``, the key hint in the body).
"""

from __future__ import annotations

import os
import tempfile

os.environ.setdefault("DOCUMENT_STORAGE_DIR", tempfile.mkdtemp(prefix="ask4mo_04d_docs_"))

import logging
import re

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from scripts.e2e import journey_fakes as F
from src import constants
from src.api import dependencies as deps
from src.application import provider_mode as PM
from src.core import secrets as S
from src.interview.session_repository import DurableInterviewSessionStore
from src.persistence import OperationalMetricEvent
from src.reporting import telemetry
from tests._auth_factories import build_auth_app, cookies_for, login_token, register

API = "/api/v1"
PW = "correcthorsebattery"
CANARY = "sk-or-v1-0123456789abcdef0123456789abcdef0123456789abcdef04D0CANARY0"       # a test value, never a credential
CREATE = {"configuration": {"target_role": "Senior Product Manager", "industry_or_sector": "Software", "career_level": "senior", "number_of_questions": 2, "conversation_language": "en"}}
KEYSHAPES = (re.compile(r"sk-or-v1-[0-9a-f]{20,}"), re.compile(r"sk-[A-Za-z0-9_-]{24,}"), re.compile(r"AIza[0-9A-Za-z_-]{30,}"), re.compile(r"(?i)bearer\s+[A-Za-z0-9._-]{20,}"))


@pytest.fixture(autouse=True)
def _isolation(monkeypatch):
    """No network (loopback test transport only) and a clean provider environment for every test."""
    for name in ("OPENROUTER_API_KEY", "ASK4MO_PROVIDER_MODE", "COPILOT_EMBEDDING_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    real_sync, real_async = httpx.Client.send, httpx.AsyncClient.send

    def guard(request):
        if (request.url.host or "") != "testserver":
            raise AssertionError(f"an external network request was attempted: {request.url.host}")

    monkeypatch.setattr(httpx.Client, "send", lambda self, request, **k: (guard(request), real_sync(self, request, **k))[1])

    async def asynch(self, request, **k):
        guard(request)
        return await real_async(self, request, **k)

    monkeypatch.setattr(httpx.AsyncClient, "send", asynch)
    from src import language_activation as LA

    act = LA.Activation(mode=LA.MODE_LABELLED, offered=tuple(LA.ACTIVE_CANDIDATE_LOCALES), qualified=(), locales={}, file_error=None)
    monkeypatch.setattr(LA, "current", lambda *, today=None: act)
    yield
    # create_app() installs the process-wide demo provider control when ASK4MO_PROVIDER_MODE is set. monkeypatch restores the variable but not that control, and a leaked control
    # makes every later test in the same worker (here tests/test_ai_budget_probe_and_scripts_05c.py) fail with guard_conflict. Remove it BEFORE monkeypatch undoes its patches.
    from src.demo_live.guard import ProviderControl

    if ProviderControl._active is not None:
        ProviderControl._active.uninstall()


def _stack(variant: str, *, env: str = "test"):
    app, repo, _mail = build_auth_app(env=env)
    store = DurableInterviewSessionStore(repo.session_factory)
    app.dependency_overrides[deps.get_session_store] = lambda: store
    fake = F.install_offline_interview_services(app, variant)
    return app, repo, fake, store


def _user(app, email="u04d@example.com"):
    c = TestClient(app)
    c.__enter__()
    assert register(c, email, PW).status_code in (200, 201)
    return c, cookies_for(login_token(c, email, PW))


# ------------------------------------------------------------------------------------------------------------- provider mode
def test_the_mode_is_not_configured_on_a_keyless_stack_and_never_live():
    app, *_ = _stack("keyless")
    c, ck = _user(app)
    body = c.get(f"{API}/capabilities", cookies=ck).json()
    assert body["ai_provider_mode"] == "not_configured"
    assert PM.resolve_provider_mode() == "not_configured"


def test_the_mode_is_live_only_when_a_credential_is_configured_and_never_exposes_it(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", CANARY)
    app, *_ = _stack("keyless")
    c, ck = _user(app)
    r = c.get(f"{API}/capabilities", cookies=ck)
    assert r.json()["ai_provider_mode"] == "live"
    assert CANARY not in r.text and "sk-or" not in r.text


def test_the_offline_switch_reports_offline_even_when_a_key_is_present(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", CANARY)
    monkeypatch.setenv("ASK4MO_PROVIDER_MODE", "offline")
    app, *_ = _stack("keyless")
    c, ck = _user(app)
    assert c.get(f"{API}/capabilities", cookies=ck).json()["ai_provider_mode"] == "offline"


def test_an_unreadable_configuration_is_unknown_never_live(monkeypatch):
    monkeypatch.setattr(PM, "provider_credential_configured", lambda: (_ for _ in ()).throw(RuntimeError("unreadable")))
    assert PM.resolve_provider_mode() == "unknown"


def test_admin_provider_status_carries_the_same_mode(monkeypatch):
    from src.application.admin_providers import build_providers_response

    assert next(p for p in build_providers_response().providers if p.provider_id == "openrouter").mode == "not_configured"
    monkeypatch.setenv("OPENROUTER_API_KEY", CANARY)
    row = next(p for p in build_providers_response().providers if p.provider_id == "openrouter")
    assert (row.mode, row.configured, row.health) == ("live", True, "Health not tested") and CANARY not in row.model_dump_json()
    monkeypatch.setenv("ASK4MO_PROVIDER_MODE", "offline")
    row = next(p for p in build_providers_response().providers if p.provider_id == "openrouter")
    assert (row.mode, row.configured) == ("offline", False)                      # offline reads no credential, so none is "configured"


# ------------------------------------------------------------------------------------------------------------- the Start Interview regression
def test_keyless_start_interview_is_not_configured_with_fixed_copy_and_no_provider_detail():
    app, repo, _fake, _store = _stack("keyless")
    c, ck = _user(app)
    r = c.post(f"{API}/interviews", json=CREATE, cookies=ck)
    assert r.status_code == 503
    err = r.json()["error"]
    assert err["code"] == "ai_not_configured"                                    # the defect answered "service_unavailable", identical to a passing outage
    assert err["message"] == constants.AI_FAILURE_MESSAGES["ai_not_configured"]
    assert not re.search(r"(?i)openrouter|api[_ ]?key|environment variable|streamlit|secrets", r.text)     # the defect's message named the provider and the variable
    assert "session_id" not in r.json() and c.get(f"{API}/history/interviews", cookies=ck).json()["interviews"] == []


def test_a_passing_provider_outage_is_a_different_code_from_not_configured():
    app, _repo, fake, _store = _stack("provider_down")
    c, ck = _user(app)
    r = c.post(f"{API}/interviews", json=CREATE, cookies=ck)
    assert r.status_code == 503 and r.json()["error"]["code"] == "ai_provider_unavailable"
    assert r.json()["error"]["message"] == constants.AI_FAILURE_MESSAGES["ai_provider_unavailable"]
    assert fake.calls == ["InterviewStrategy"]                                    # one provider call: nothing retried silently
    assert constants.AI_FAILURE_MESSAGES["ai_provider_unavailable"] != constants.AI_FAILURE_MESSAGES["ai_not_configured"]


def test_a_healthy_stack_still_starts_the_interview():
    app, _repo, fake, _store = _stack("healthy")
    c, ck = _user(app)
    r = c.post(f"{API}/interviews", json=CREATE, cookies=ck)
    assert r.status_code == 200 and r.json()["state"] == "AWAITING_ANSWER"
    assert fake.calls == ["InterviewStrategy", "InterviewQuestion"]


def test_a_failed_start_leaves_nothing_resumable_and_a_retry_starts_exactly_one_setup():
    app, _repo, fake, _store = _stack("provider_down")
    c, ck = _user(app)
    headers = {"Idempotency-Key": "practice-setup:attempt-1"}
    for _ in range(3):                                                               # three user-initiated presses of Start, same attempt key, provider down
        assert c.post(f"{API}/interviews", json=CREATE, cookies=ck, headers=headers).status_code == 503
    assert c.get(f"{API}/interviews", cookies=ck).json()["sessions"] == [], "a failed start must not leave an empty 'in progress' interview behind"
    assert fake.calls == ["InterviewStrategy"] * 3                                    # exactly one provider call per press: nothing retried automatically
    fake.variant = "healthy"                                                          # the provider recovers; the same key now starts ONE interview
    ok = c.post(f"{API}/interviews", json=CREATE, cookies=ck, headers=headers)
    assert ok.status_code == 200 and ok.json()["state"] == "AWAITING_ANSWER"
    assert [s["state"] for s in c.get(f"{API}/interviews", cookies=ck).json()["sessions"]] == ["AWAITING_ANSWER"]
    again = c.post(f"{API}/interviews", json=CREATE, cookies=ck, headers=headers)      # a repeat of the SUCCESSFUL create returns the same session, never a second
    assert again.json()["session_id"] == ok.json()["session_id"]
    assert len(c.get(f"{API}/interviews", cookies=ck).json()["sessions"]) == 1


def test_a_failed_start_without_a_key_also_leaves_nothing_behind():
    app, _repo, _fake, _store = _stack("keyless")
    c, ck = _user(app)
    for _ in range(2):
        assert c.post(f"{API}/interviews", json=CREATE, cookies=ck).status_code == 503
    assert c.get(f"{API}/interviews", cookies=ck).json()["sessions"] == []


def test_a_provider_that_fails_mid_interview_leaves_a_coded_recoverable_error_with_fixed_copy():
    app, _repo, fake, _store = _stack("healthy")
    c, ck = _user(app)
    sid = c.post(f"{API}/interviews", json=CREATE, cookies=ck).json()["session_id"]
    fake.variant = "provider_down"
    state = c.post(f"{API}/interviews/{sid}/answers", json={"answer": "I measured a twelve percent lift."}, cookies=ck).json()
    assert state["state"] == "ERROR" and state["error_code"] == "ai_provider_unavailable" and state["error_recoverable"] is True
    assert state["error"] == constants.AI_FAILURE_MESSAGES["ai_provider_unavailable"]                 # never the provider's own text
    calls_after_failure = len(fake.calls)
    fake.variant = "healthy"
    recovered = c.post(f"{API}/interviews/{sid}/recover", cookies=ck).json()
    assert recovered["state"] == "AWAITING_ANSWER" and recovered["error"] is None and recovered["error_code"] is None
    assert len(fake.calls) == calls_after_failure, "recovering changed state only; it made no provider call"


# ------------------------------------------------------------------------------------------------------------- the failure is recorded without secrets
def test_a_provider_failure_is_recorded_as_one_bounded_event_without_secrets(monkeypatch, caplog):
    monkeypatch.setenv("OPENROUTER_API_KEY", CANARY)
    app, _repo, _fake, _store = _stack("provider_down")
    c, ck = _user(app)

    def provider_events() -> list[OperationalMetricEvent]:
        # The app installs its telemetry sink over the configured database while it serves; read from whichever database it wrote to (the process-wide test database).
        with telemetry._sf() as s:
            return list(s.scalars(select(OperationalMetricEvent).where(OperationalMetricEvent.event_type == "provider_call",
                                                                        OperationalMetricEvent.error_category == "ai_provider_unavailable")).all())

    assert c.post(f"{API}/interviews", json=CREATE, cookies=ck).status_code == 503      # warm-up: the sink is installed lazily by the first provider-backed request
    before = len(provider_events())
    with caplog.at_level(logging.DEBUG):
        r = c.post(f"{API}/interviews", json={"configuration": {**CREATE["configuration"], "candidate_background": "PRIVATE-BACKGROUND-MARKER"}}, cookies=ck)
    assert r.status_code == 503
    rows = provider_events()
    assert len(rows) - before == 1                                                # one failure, one event (the one provider call was not retried)
    row = rows[-1]
    assert (row.subsystem, row.operation, row.outcome, row.error_category, row.provider) == ("practice", "practice_strategy", "unavailable", "ai_provider_unavailable", "openrouter")
    stored = " ".join(str(getattr(row, col.name)) for col in OperationalMetricEvent.__table__.columns)
    logged = " ".join(rec.getMessage() for rec in caplog.records)
    for blob in (stored, logged, r.text):
        assert CANARY not in blob and "PRIVATE-BACKGROUND-MARKER" not in blob and "sk-or" not in blob
    assert set(c.name for c in OperationalMetricEvent.__table__.columns) <= {"id", "event_type", "subsystem", "operation", "outcome", "duration_ms", "error_category", "provider", "occurred_at"}


# ------------------------------------------------------------------------------------------------------------- Mo: failure codes
def _agent_app(model_factory):
    from src.application.agent_service import AgentApplicationService
    from src.privacy.preparation import PreparationRunIndex

    app, repo, _mail = build_auth_app()
    svc = AgentApplicationService(model_factory=model_factory, career_service=F.NoRetrievalCareerService(), run_index=PreparationRunIndex(repo.session_factory))
    app.dependency_overrides[deps.get_agent_service] = lambda: svc
    return app, repo


def test_a_mo_run_without_ai_configured_carries_the_not_configured_code():
    from src.agent.errors import AgentConfigurationError

    def factory(profile=None):
        raise AgentConfigurationError("not configured")

    app, _repo = _agent_app(factory)
    c, ck = _user(app)
    body = c.post(f"{API}/agent/run", json={"goal": "Help me prepare"}, cookies=ck).json()
    assert body["status"] == "failed" and body["failure_code"] == "ai_not_configured"


def test_a_mo_run_whose_provider_fails_carries_the_unavailable_code_and_a_healthy_run_carries_none():
    app, _repo = _agent_app(lambda profile=None: F.ScriptedAgentModel("provider_down"))
    c, ck = _user(app)
    body = c.post(f"{API}/agent/run", json={"goal": "Help me prepare"}, cookies=ck).json()
    assert body["status"] == "failed" and body["failure_code"] == "ai_provider_unavailable"
    app2, _repo2 = _agent_app(lambda profile=None: F.ScriptedAgentModel("healthy"))
    c2, ck2 = _user(app2, "healthy04d@example.com")
    ok = c2.post(f"{API}/agent/run", json={"goal": "Help me prepare"}, cookies=ck2).json()
    assert ok["status"] == "completed" and ok["failure_code"] is None


# ------------------------------------------------------------------------------------------------------------- IR-DEMO-KEY: the explicit offline switch
def test_without_the_switch_a_key_from_every_source_is_read_a_positive_control(monkeypatch):
    from src.config import load_config

    monkeypatch.setenv("OPENROUTER_API_KEY", CANARY)
    assert load_config().is_configured is True
    assert S.read_setting("OPENROUTER_API_KEY") == CANARY


def test_with_the_offline_switch_no_provider_key_is_read_from_any_source(monkeypatch):
    import streamlit as st

    from src.config import load_config as interview_config
    from src.copilot.config import load_config as career_config

    monkeypatch.setenv("OPENROUTER_API_KEY", CANARY)                 # an exported variable
    monkeypatch.setenv("COPILOT_EMBEDDING_API_KEY", CANARY)
    monkeypatch.setenv("ASK4MO_PROVIDER_MODE", "offline")
    monkeypatch.setattr(st, "secrets", {"OPENROUTER_API_KEY": CANARY, "COPILOT_EMBEDDING_API_KEY": CANARY, "GEMINI_API_KEY": CANARY})   # Streamlit secrets
    monkeypatch.setattr(S, "_managed_resolver", lambda name: CANARY)  # the Admin-managed store
    assert S.read_streamlit("OPENROUTER_API_KEY") is None
    assert S.read_env("OPENROUTER_API_KEY") is None
    assert S.read_managed("OPENROUTER_API_KEY") is None
    assert S.read_environment_setting("OPENROUTER_API_KEY") is None
    assert S.read_setting("OPENROUTER_API_KEY") is None and S.read_secret("OPENROUTER_API_KEY") is None
    cfg = interview_config()
    assert cfg.is_configured is False and cfg.api_key is None and cfg.gemini_api_key is None
    cc = career_config()
    assert cc.api_key is None and getattr(cc, "embedding_api_key", None) is None
    assert PM.resolve_provider_mode() == "offline"


def test_the_offline_switch_withholds_provider_credentials_only_not_other_settings(monkeypatch):
    monkeypatch.setenv("ASK4MO_PROVIDER_MODE", "offline")
    monkeypatch.setenv("SESSION_COOKIE_NAME", "custom_cookie")
    monkeypatch.setenv("BREVO_API_KEY", "brevo-test-value")
    assert S.read_setting("SESSION_COOKIE_NAME") == "custom_cookie"
    assert S.read_setting("BREVO_API_KEY") == "brevo-test-value"       # identity and email secrets are a different subsystem: the switch is about provider calls


def test_the_offline_switch_never_loads_a_dotenv_file(monkeypatch):
    loaded: list[bool] = []
    monkeypatch.setattr(S, "load_dotenv", lambda *a, **k: loaded.append(True))
    monkeypatch.setattr("src.config.load_dotenv", lambda *a, **k: loaded.append(True))
    monkeypatch.setattr("src.copilot.config.load_dotenv", lambda *a, **k: loaded.append(True))
    from src.config import load_config as interview_config
    from src.copilot.config import load_config as career_config

    interview_config()
    career_config()
    S.load_dotenv_once()
    assert len(loaded) == 3                                              # control: without the switch every loader reads .env
    loaded.clear()
    monkeypatch.setenv("ASK4MO_PROVIDER_MODE", "offline")
    interview_config()
    career_config()
    S.load_dotenv_once()
    assert loaded == []


@pytest.mark.parametrize("value", ["offline", " OFFLINE ", "Offline"])
def test_the_switch_value_is_case_and_space_insensitive(value):
    assert S.offline_switch_active({"ASK4MO_PROVIDER_MODE": value}) is True


@pytest.mark.parametrize("value", ["", "live", "off", "true", "1", None])
def test_only_the_word_offline_activates_the_switch(value):
    env = {} if value is None else {"ASK4MO_PROVIDER_MODE": value}
    assert S.offline_switch_active(env) is False


# ------------------------------------------------------------------------------------------------------------- provider-key hazard: every API response
def _get_routes_without_params(app) -> list[str]:
    return sorted(p for p, ops in app.openapi()["paths"].items() if "get" in ops and "{" not in p)


def test_no_api_response_contains_key_material_when_a_key_is_configured(monkeypatch, caplog):
    """The configured key VALUE (a canary in the test environment) and any key-shaped string must appear in NO response body or header, for a candidate, a platform administrator
    and an anonymous caller, across every parameterless GET route plus the failure and success paths of Start Interview and Mo."""
    monkeypatch.setenv("OPENROUTER_API_KEY", CANARY)
    app, repo, fake, _store = _stack("healthy")
    c, ck = _user(app, "hazard-user@example.com")
    admin = TestClient(app)
    admin.__enter__()
    register(admin, "hazard-admin@example.com", PW)
    from tests._auth_factories import account_repo

    uid = admin.get(f"{API}/auth/me", cookies=cookies_for(login_token(admin, "hazard-admin@example.com", PW))).json()["user_id"]
    account_repo(repo).set_platform_role(uid, "platform_admin")
    admin_ck = cookies_for(login_token(admin, "hazard-admin@example.com", PW))
    anon = TestClient(app)
    seen = 0
    with caplog.at_level(logging.DEBUG):
        for path in _get_routes_without_params(app):
            for who, client, cookies in (("candidate", c, ck), ("admin", admin, admin_ck), ("anonymous", anon, None)):
                r = client.get(f"{API}{path[len('/api/v1'):]}" if path.startswith("/api/v1") else path, cookies=cookies)
                blob = r.text + " ".join(f"{k}: {v}" for k, v in r.headers.items())
                assert CANARY not in blob, (who, path)
                assert not any(p.search(blob) for p in KEYSHAPES), (who, path)
                seen += 1
        # success and failure paths that touch the provider layer
        assert c.post(f"{API}/interviews", json=CREATE, cookies=ck).status_code == 200
        fake.variant = "provider_down"
        failed = c.post(f"{API}/interviews", json=CREATE, cookies=ck)
        assert failed.status_code == 503 and CANARY not in failed.text
    assert seen >= 40, "the sweep must cover the real route surface"
    assert CANARY not in " ".join(rec.getMessage() for rec in caplog.records)


def test_a_provider_error_carrying_a_key_never_reaches_the_candidate(monkeypatch):
    """Even if a provider error message contained a key (a hostile or buggy upstream), the candidate-facing text is the fixed copy."""
    from src.openrouter_client import ServerError

    app, _repo, fake, _store = _stack("provider_down")

    def leaking(**kwargs):
        raise ServerError(f"upstream said: Authorization: Bearer {CANARY}", status_code=503, category="server")

    monkeypatch.setattr(fake, "create_chat_completion", leaking)
    c, ck = _user(app, "leak@example.com")
    r = c.post(f"{API}/interviews", json=CREATE, cookies=ck)
    assert r.status_code == 503 and CANARY not in r.text and "upstream" not in r.text and "Bearer" not in r.text


# ------------------------------------------------------------------------------------------------------------- AC-18: owner-scoped run list
def _index(repo):
    from src.privacy.preparation import PreparationRunIndex

    return PreparationRunIndex(repo.session_factory)


def test_a_candidate_sees_only_their_own_runs_newest_first_and_never_content():
    app, repo, *_ = _stack("healthy")
    a, a_ck = _user(app, "runs-a@example.com")
    b, b_ck = _user(app, "runs-b@example.com")
    uid_a = a.get(f"{API}/auth/me", cookies=a_ck).json()["user_id"]
    uid_b = b.get(f"{API}/auth/me", cookies=b_ck).json()["user_id"]
    idx = _index(repo)
    idx.register("run-a-1", uid_a)
    idx.register("run-b-1", uid_b)
    idx.register("run-a-2", uid_a)
    idx.mark("run-a-2", "ready")
    idx.mark("run-a-1", "failed")
    ra = a.get(f"{API}/agent/runs", cookies=a_ck)
    assert ra.status_code == 200
    ids_a = [r["run_id"] for r in ra.json()["runs"]]
    assert set(ids_a) == {"run-a-1", "run-a-2"} and "run-b-1" not in ids_a
    assert ids_a[0] == "run-a-1"                                                  # most recently updated first
    rb = b.get(f"{API}/agent/runs", cookies=b_ck)
    assert [r["run_id"] for r in rb.json()["runs"]] == ["run-b-1"]
    for run in ra.json()["runs"]:
        assert set(run) == {"run_id", "state", "created_at", "updated_at"}        # ids, state and dates only: no conversation, sources, prompts or user id
    assert "user" not in ra.text.lower()


def test_the_run_list_is_bounded_authenticated_and_excludes_runs_being_purged():
    app, repo, *_ = _stack("healthy")
    c, ck = _user(app, "bounded@example.com")
    uid = c.get(f"{API}/auth/me", cookies=ck).json()["user_id"]
    idx = _index(repo)
    for i in range(12):
        idx.register(f"bounded-{i}", uid)
    idx.register("being-purged", uid)
    idx.mark("being-purged", "purge_failed")
    assert len(c.get(f"{API}/agent/runs", cookies=ck).json()["runs"]) == 12
    assert len(c.get(f"{API}/agent/runs?limit=5", cookies=ck).json()["runs"]) == 5
    assert "being-purged" not in c.get(f"{API}/agent/runs?limit=50", cookies=ck).text
    for bad in ("0", "51", "-1", "abc"):
        assert c.get(f"{API}/agent/runs?limit={bad}", cookies=ck).status_code == 422


def test_the_run_list_is_closed_in_a_hosted_like_environment_and_isolated_across_the_anonymous_identity():
    app, repo, *_ = _stack("healthy", env="staging")
    with TestClient(app) as anon:
        assert anon.get(f"{API}/agent/runs").status_code == 401                    # fail closed: no session, no list
    idx = _index(repo)
    idx.register("someone-elses", 999)
    from src.invitations import repository as R
    from src.application import admin_audit as A

    code = R.new_code()
    audit = A.build_audit(event_type=A.ADMIN_INVITATION_ISSUED, actor_user_id=None, request_id=None, target_type="invitation", origin="cli")
    R.InvitationRepository(repo.session_factory).issue(code_hash=R.hash_code(code), ttl_days=1, email=None, issued_by_user_id=None, audit=audit)
    with TestClient(app) as c:
        assert c.post(f"{API}/auth/register", json={"email": "h@example.com", "password": PW, "invitation_code": code}).status_code == 201
        ck = cookies_for(login_token(c, "h@example.com", PW))
        assert c.get(f"{API}/agent/runs", cookies=ck).json()["runs"] == []


def test_opening_a_listed_run_of_another_candidate_is_not_found():
    from src.application.agent_service import AgentApplicationService
    from src.privacy.preparation import PreparationRunIndex

    app, repo, _mail = build_auth_app()
    svc = AgentApplicationService(model_factory=lambda profile=None: F.ScriptedAgentModel("healthy"), career_service=F.NoRetrievalCareerService(), run_index=PreparationRunIndex(repo.session_factory))
    app.dependency_overrides[deps.get_agent_service] = lambda: svc
    a, a_ck = _user(app, "own-a@example.com")
    b, b_ck = _user(app, "own-b@example.com")
    run_id = a.post(f"{API}/agent/run", json={"goal": "Help me prepare"}, cookies=a_ck).json()["run_id"]
    assert [r["run_id"] for r in a.get(f"{API}/agent/runs", cookies=a_ck).json()["runs"]] == [run_id]
    assert b.get(f"{API}/agent/runs", cookies=b_ck).json()["runs"] == []
    assert b.get(f"{API}/agent/runs/{run_id}", cookies=b_ck).status_code == 404
    assert a.get(f"{API}/agent/runs/{run_id}", cookies=a_ck).status_code == 200
