"""04D: the offline fakes and the launcher guards behind the real-stack Candidate journey, and the API-level Start Interview journey they make possible.

Everything here is OFFLINE evidence (fixture model replies, a temp database, no provider, no network). The real-browser journey is frontend/e2e/candidate-journey-04d.spec.ts;
this file proves the pieces it stands on, and that the SAME backend path completes a Start Interview journey on a healthy stack and fails honestly when the provider is down.
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from scripts.e2e import journey_fakes as F
from scripts.e2e import journey_stack as S
from src import models
from src.openrouter_client import ServerError
from src.structured_output import build_structured_response_format
from tests._auth_factories import build_auth_app, cookies_for, login_token, register

ROOT = Path(__file__).resolve().parents[1]
PW = "journey-passphrase-synthetic-1"
SCHEMAS = ("InterviewStrategy", "InterviewQuestion", "AnswerEvaluation", "FinalInterviewReport")


@pytest.fixture(autouse=True)
def _no_external_network(monkeypatch):
    """The in-process TestClient also uses httpx; only a request to a real host is a violation."""
    real_sync, real_async = httpx.Client.send, httpx.AsyncClient.send

    def guard(request):
        if (request.url.host or "") != "testserver":
            raise AssertionError(f"an external network request was attempted: {request.url.host}")

    def sync(self, request, **k):
        guard(request)
        return real_sync(self, request, **k)

    async def asynch(self, request, **k):
        guard(request)
        return await real_async(self, request, **k)

    monkeypatch.setattr(httpx.Client, "send", sync)
    monkeypatch.setattr(httpx.AsyncClient, "send", asynch)


def _messages(question_number: int) -> list[dict]:
    return [{"role": "system", "content": "x"}, {"role": "user", "content": f"Return the required JSON for question number {question_number}. Do not repeat."}]


def _ask(client: F.FixtureChatClient, schema_name: str, **extra):
    cls = getattr(models, schema_name)
    fmt = build_structured_response_format(cls)
    result = client.create_chat_completion(model="m", messages=extra.pop("messages", _messages(1)), temperature=None, max_tokens=100, response_format=fmt, **extra)
    return cls.model_validate(json.loads(result.content))


# ---------------------------------------------------------------------------------------------------------------------------------- the fixtures
def test_the_fixtures_are_one_synthetic_file_shared_with_the_browser_suite():
    fx = F.load_fixtures()
    assert F.FIXTURES_PATH == ROOT / "frontend/e2e/journey/fixtures.json"
    assert fx["candidate"]["emailDomain"].endswith(".invalid")
    assert len(fx["interview"]["questions"]) >= 2 and fx["interview"]["evaluation"]["overall_score"] == 74
    # The browser definition reads the same file (a static guarantee that the two modes cannot drift apart).
    assert 'from "./fixtures.json"' in (ROOT / "frontend/e2e/journey/env.ts").read_text()
    assert "fixtures.json" in (ROOT / "scripts/e2e/journey_fakes.py").read_text()


@pytest.mark.parametrize("schema_name", SCHEMAS)
def test_every_fixture_reply_validates_against_the_real_schema(schema_name):
    obj = _ask(F.FixtureChatClient("healthy"), schema_name)
    assert obj is not None


def test_a_question_reply_follows_the_question_number_the_service_asks_for():
    c = F.FixtureChatClient("healthy")
    qs = F.load_fixtures()["interview"]["questions"]
    first = _ask(c, "InterviewQuestion", messages=_messages(1))
    second = _ask(c, "InterviewQuestion", messages=_messages(2))
    again_first = _ask(c, "InterviewQuestion", messages=_messages(1))          # another interview's first question is the first fixture again, not the third
    assert (first.question, second.question, again_first.question) == (qs[0], qs[1], qs[0])
    assert (first.question_id, second.question_id) == (1, 2)


def test_provider_down_raises_the_clients_own_provider_error_and_counts_calls():
    c = F.FixtureChatClient("provider_down")
    with pytest.raises(ServerError) as exc:
        _ask(c, "InterviewStrategy")
    assert exc.value.status_code == 503 and "key" not in exc.value.message.lower()
    assert c.calls == ["InterviewStrategy"]


def test_keyless_is_the_absence_of_a_client_not_a_fake():
    with pytest.raises(ValueError):
        F.FixtureChatClient("keyless")


def test_the_scripted_agent_model_answers_plainly_or_fails_like_a_down_provider():
    from langchain_core.messages import HumanMessage

    ok = F.ScriptedAgentModel("healthy").bind_tools([]).invoke([HumanMessage(content="hi")])
    assert ok.content == F.load_fixtures()["mo"]["reply"] and not ok.tool_calls
    with pytest.raises(RuntimeError):
        F.ScriptedAgentModel("provider_down").invoke([HumanMessage(content="hi")])


def test_the_career_stub_fails_loudly_never_silently():
    with pytest.raises(RuntimeError, match="retrieval is not available"):
        F.NoRetrievalCareerService().search_knowledge("x")


# ---------------------------------------------------------------------------------------------------------------------------------- launcher guards
@pytest.mark.parametrize("port", [3000, 3015, 8020, 8030])
def test_the_launcher_refuses_the_live_stack_ports(port):
    with pytest.raises(SystemExit, match="live stack"):
        S._check_ports(port)


def test_the_launcher_defaults_are_unique_and_never_the_live_ports():
    assert {S.DEFAULT_API_PORT, S.DEFAULT_WEB_PORT}.isdisjoint(S.FORBIDDEN_PORTS)
    assert len(S.ALL_LANGUAGES) == 7 and "ru" not in S.ALL_LANGUAGES


def test_the_launcher_is_offline_and_hosted_like_by_construction():
    text = (ROOT / "scripts/e2e/journey_stack.py").read_text()
    assert '"API_ENV": "staging"' in text                        # fail-closed identity, invitation always required
    assert 'ASK4MO_PROVIDER_MODE"] = "offline"' in text         # the offline guard refuses every non-loopback request
    assert "FILE_SCAN_PROVIDER" not in text                      # the fake scanner is refused in hosted environments and is not used here
    assert "pkill" not in text and "killall" not in text         # exact PIDs only


# ---------------------------------------------------------------------------------------------------------------------------------- API-level Start Interview journey
def _world(variant: str):
    app, repo, _mail = build_auth_app(env="staging")             # hosted-like: no anonymous identity, an invitation is required
    from src.api import dependencies as deps
    from src.interview.session_repository import DurableInterviewSessionStore

    store = DurableInterviewSessionStore(repo.session_factory)     # bound to THIS database (the store is resolved through Depends)
    app.dependency_overrides[deps.get_session_store] = lambda: store
    client = F.install_offline_interview_services(app, variant)
    return app, repo, client


def _signed_in(app, repo, email="start@example.com"):
    from src.invitations import repository as R
    from src.application import admin_audit as A

    code = R.new_code()
    audit = A.build_audit(event_type=A.ADMIN_INVITATION_ISSUED, actor_user_id=None, request_id=None, target_type="invitation", origin="cli")
    R.InvitationRepository(repo.session_factory).issue(code_hash=R.hash_code(code), ttl_days=1, email=None, issued_by_user_id=None, audit=audit)
    c = TestClient(app)
    c.__enter__()
    assert c.post("/api/v1/auth/register", json={"email": email, "password": PW, "invitation_code": code}).status_code == 201
    return c, cookies_for(login_token(c, email, PW))


CREATE = {"configuration": {"target_role": "Senior Product Manager", "industry_or_sector": "Software", "career_level": "senior", "number_of_questions": 2, "conversation_language": "en"}}


@pytest.fixture()
def labelled_languages(monkeypatch):
    """Hosted environments offer only qualified languages and none is qualified yet; this is the same override the offline launcher applies."""
    from src import language_activation as LA

    act = LA.Activation(mode=LA.MODE_LABELLED, offered=tuple(LA.ACTIVE_CANDIDATE_LOCALES), qualified=(), locales={}, file_error=None)
    monkeypatch.setattr(LA, "current", lambda *, today=None: act)


def test_start_interview_to_report_completes_on_a_healthy_hosted_like_stack(labelled_languages):
    app, repo, fake = _world("healthy")
    c, ck = _signed_in(app, repo)
    r = c.post("/api/v1/interviews", json=CREATE, cookies=ck)
    assert r.status_code == 200, r.text                                         # the owner-named regression: Start Interview succeeds
    body = r.json()
    sid = body["session_id"]
    assert body["state"] == "AWAITING_ANSWER" and body["current_question"]["question"] == F.load_fixtures()["interview"]["questions"][0]
    a = c.post(f"/api/v1/interviews/{sid}/answers", json={"answer": "I measured a twelve percent lift."}, cookies=ck).json()
    assert a["last_evaluation"]["overall_score"] == 74
    n = c.post(f"/api/v1/interviews/{sid}/next-question", cookies=ck).json()
    assert n["question_number"] == 2 and n["current_question"]["question"] == F.load_fixtures()["interview"]["questions"][1]
    c.post(f"/api/v1/interviews/{sid}/answers", json={"answer": "x" * 40}, cookies=ck)
    assert c.post(f"/api/v1/interviews/{sid}/next-question", cookies=ck).json()["state"] == "INTERVIEW_COMPLETE"
    rep = c.post(f"/api/v1/interviews/{sid}/report", cookies=ck)
    assert rep.status_code == 200 and rep.json()["report"]["overall_readiness_score"] == 71
    hist = c.get("/api/v1/history/interviews", cookies=ck).json()["interviews"]
    prog = c.get("/api/v1/progress", cookies=ck).json()
    assert len(hist) == 1 and hist[0]["target_role"] == "Senior Product Manager"
    assert (prog["interviews_completed"], prog["answers_evaluated"]) == (1, 2)
    # One strategy, two questions, two evaluations, one report: nothing was generated twice.
    assert fake.calls.count("InterviewStrategy") == 1 and fake.calls.count("InterviewQuestion") == 2
    assert fake.calls.count("AnswerEvaluation") == 2 and fake.calls.count("FinalInterviewReport") == 1


def test_a_down_provider_fails_the_start_once_without_claiming_success_or_retrying(labelled_languages):
    app, repo, fake = _world("provider_down")
    c, ck = _signed_in(app, repo, "down@example.com")
    r = c.post("/api/v1/interviews", json=CREATE, cookies=ck)
    assert r.status_code == 503 and r.json()["error"]["code"] in ("service_unavailable", "ai_provider_unavailable")
    assert "current_question" not in r.json() and "session_id" not in r.json()
    assert fake.calls == ["InterviewStrategy"], "the provider was called exactly once: no silent retry into duplicates"
    assert c.get("/api/v1/history/interviews", cookies=ck).json()["interviews"] == []
    assert PW not in r.text


def test_registration_in_a_hosted_like_stack_is_refused_without_an_invitation(labelled_languages):
    app, repo, _fake = _world("healthy")
    with TestClient(app) as c:
        assert register(c, "uninvited@example.com", PW).status_code == 403
