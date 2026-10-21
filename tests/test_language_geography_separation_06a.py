"""06A (REQ-LANG-07, LG-07): changing interface, conversation or session language never changes career geography.

Deterministic, 0 paid/live calls. Flows: account preferences, onboarding, Opportunity, interview creation, agent run
and Career chat. Language is never an input to geography; geography is an explicit account/session/query value.
"""

from __future__ import annotations

import inspect
import itertools
import os
import tempfile

os.environ.setdefault("DOCUMENT_STORAGE_DIR", tempfile.mkdtemp(prefix="ask4mo_06a_"))

import pytest
from fastapi.testclient import TestClient

from src.api.schemas.agent import AgentRunRequest
from src.api.schemas.interview import CreateInterviewRequest, InterviewConfigIn
from src.copilot.knowledge.router import detect_country
from src.locales import ACTIVE_CANDIDATE_LOCALES
from tests._auth_factories import build_auth_app, cookies_for, login_token, register

PW = "correcthorsebattery"


def _client_with_account(geo: str = "de"):
    app, repo, _ = build_auth_app()
    c = TestClient(app)
    c.__enter__()
    register(c, "a@example.com", PW)
    ck = cookies_for(login_token(c, "a@example.com", PW))
    r = c.patch("/api/v1/auth/preferences", json={"career_geography": geo}, cookies=ck)
    assert r.status_code == 200, r.text
    return c, ck


def _geo(c, ck) -> str:
    return c.get("/api/v1/auth/me", cookies=ck).json()["career_geography"]


@pytest.mark.parametrize("iface,conv", list(itertools.product(("en", "de", "nl"), ("fr", "es", "pt", "it"))))
def test_account_language_changes_never_change_geography(iface, conv):
    c, ck = _client_with_account("de")
    try:
        assert c.patch("/api/v1/auth/preferences", json={"interface_locale": iface, "conversation_language": conv}, cookies=ck).status_code == 200
        assert _geo(c, ck) == "de"
        for loc in ACTIVE_CANDIDATE_LOCALES:
            c.patch("/api/v1/auth/preferences", json={"interface_locale": loc}, cookies=ck)
            c.patch("/api/v1/auth/preferences", json={"conversation_language": loc}, cookies=ck)
            assert _geo(c, ck) == "de"
    finally:
        c.__exit__(None, None, None)


def test_onboarding_language_choices_never_set_or_change_geography():
    app, _, _ = build_auth_app()
    with TestClient(app) as c:
        register(c, "a@example.com", PW)
        ck = cookies_for(login_token(c, "a@example.com", PW))
        assert _geo(c, ck) in ("", None)  # a fresh account has no geography; language must not invent one
        for loc in ("de", "fr", "es", "nl"):
            assert c.patch("/api/v1/auth/preferences", json={"interface_locale": loc, "conversation_language": loc}, cookies=ck).status_code == 200
            assert c.post("/api/v1/auth/onboarding", json={"step": 2}, cookies=ck).status_code == 200
            assert _geo(c, ck) in ("", None)
        assert c.patch("/api/v1/auth/preferences", json={"career_geography": "fr"}, cookies=ck).status_code == 200
        assert c.patch("/api/v1/auth/preferences", json={"interface_locale": "de"}, cookies=ck).status_code == 200
        assert c.post("/api/v1/auth/onboarding", json={"complete": True}, cookies=ck).status_code == 200
        assert _geo(c, ck) == "fr"


def test_opportunity_country_is_independent_of_every_language_setting():
    c, ck = _client_with_account("nl")
    try:
        r = c.post("/api/v1/opportunities", json={"target_role": "Product Manager", "company_country": "de"}, cookies=ck)
        assert r.status_code == 201, r.text
        oid = r.json()["id"]
        assert r.json()["company_country"] == "DE"
        for loc in ("fr", "es", "it", "pt"):
            c.patch("/api/v1/auth/preferences", json={"interface_locale": loc, "conversation_language": loc}, cookies=ck)
            got = c.get(f"/api/v1/opportunities/{oid}", cookies=ck).json()
            assert got["company_country"] == "DE"
            assert _geo(c, ck) == "nl"
        # An opportunity created without a country gets none because of the language.
        r2 = c.post("/api/v1/opportunities", json={"target_role": "Nurse"}, cookies=ck)
        assert r2.json()["company_country"] in (None, "")
    finally:
        c.__exit__(None, None, None)


def test_interview_creation_has_no_geography_input_and_session_language_is_prose_only():
    # The interview configuration carries a session language and NO geography/country field at all.
    for model in (InterviewConfigIn, CreateInterviewRequest):
        names = set(model.model_fields)
        assert not {n for n in names if "geograph" in n or "country" in n or "market" in n}, model
    cfg = InterviewConfigIn(target_role="Nurse", industry_or_sector="healthcare", career_level="senior", conversation_language="fr")
    assert cfg.conversation_language == "fr"


def test_agent_run_has_no_language_derived_geography():
    names = set(AgentRunRequest.model_fields)
    assert "conversation_language" in names
    assert not {n for n in names if "geograph" in n or "country" in n}
    # Geography detection is a pure function of the query text: it has no language/locale parameter.
    params = list(inspect.signature(detect_country).parameters)
    assert params == ["query"]
    assert detect_country("salary in Germany") == "DE" and detect_country("salary in the UK") == "UK"


def test_career_chat_passes_language_but_never_geography():
    from src.api.schemas.career import CareerChatRequest as ApiReq
    from src.application.career_service import CareerApplicationService
    from src.application.models import CareerChatRequest as AppReq

    seen: dict = {}

    class _Spy:
        def answer(self, query, **kw):
            seen.clear()
            seen.update(kw, query=query)
            return "ok"

    svc = CareerApplicationService(config=None, service=_Spy())  # type: ignore[arg-type]
    for loc in ACTIVE_CANDIDATE_LOCALES:
        assert ApiReq(question="x", conversation_language=loc).conversation_language == loc
        svc.chat(AppReq(query="Salary in Germany?", conversation_language=loc))
        assert seen["conversation_language"] == loc
        assert not {"geography", "country", "interface_locale", "resolved_country"} & set(seen)
