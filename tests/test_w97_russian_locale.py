"""P10B-W9.7 - Russian as the 8th Ask4Mo product locale.

Deterministic, 0 paid/live calls. Proves:
  * `ru` is accepted wherever the app/conversation locale is accepted, and invalid codes still are not;
  * `AppLocale` stays a bounded Literal derived from the ONE canonical tuple (no stale duplicate tuple);
  * Russian conversation routing reaches the (mock-free) prompt/directive builders for Practice
    (question/evaluation/report) and the agent path, prose-only;
  * adding the app locale does NOT enable other dimensions: geography, speech (dictation/TTS/realtime),
    OCR/document language, KB/taxonomy languages.
"""

from __future__ import annotations

import typing

import pytest
from fastapi.testclient import TestClient
from pydantic import TypeAdapter, ValidationError

from src import prompts
from src.agent.policies import RESPONSE_LANGUAGE_NAMES, response_language_directive
from src.api.schemas.agent import AgentRunRequest
from src.api.schemas.auth import PreferencesRequest
from src.api.schemas.documents import Locale as DocumentLocale
from src.api.schemas.interview import ConversationLanguage, CreateInterviewRequest
from src.copilot.knowledge import governance
from src.documents.ocr import TESSERACT_LANGS
from src.locales import ACTIVE_CANDIDATE_LOCALES, DOCUMENT_LANGUAGE_CODES, SUPPORTED_LOCALE_CODES, AppLocale
from src.models import InterviewConfiguration
from src.persistence import SUPPORTED_LOCALES
from src.voice.realtime import SUPPORTED_REALTIME_LOCALES, RealtimeSessionRequest
from tests._auth_factories import build_auth_app, cookies_for, login_token, register

PW = "correcthorsebattery"
EIGHT = ("en", "de", "fr", "es", "it", "pt", "nl", "ru")
SEVEN = EIGHT[:7]  # 06A: ru is PRESERVED in the catalogue but EXCLUDED from active Candidate selection


# ---- 1/2/9: canonical source, bounded typing, no stale tuple --------------------------------------
def test_ru_is_the_eighth_canonical_locale():
    assert SUPPORTED_LOCALE_CODES == EIGHT  # catalogue/stored-value allow-list keeps ru (preserved)
    assert ACTIVE_CANDIDATE_LOCALES == SEVEN  # 06A: not selectable, not accepted for new work
    assert typing.get_args(AppLocale) == SEVEN  # NEW-work Literal tracks the ACTIVE tuple


def test_app_locale_is_a_bounded_literal_not_str():
    ta = TypeAdapter(AppLocale)
    assert ta.validate_python("de") == "de"
    for bad in ("ru", "xx", "ru-RU", "RU", "russian", "", "ua", "'; DROP TABLE users; --"):
        with pytest.raises(ValidationError):
            ta.validate_python(bad)


def test_persistence_reexports_the_canonical_tuple_and_name_maps_cover_it():
    # One source: persistence re-exports it; both prompt language-name allow-lists cover every locale.
    assert SUPPORTED_LOCALES is SUPPORTED_LOCALE_CODES
    assert set(prompts._CONVERSATION_LANGUAGE_NAMES) == set(SUPPORTED_LOCALE_CODES)
    assert set(RESPONSE_LANGUAGE_NAMES) == set(SUPPORTED_LOCALE_CODES)
    assert prompts._CONVERSATION_LANGUAGE_NAMES["ru"] == RESPONSE_LANGUAGE_NAMES["ru"] == "Russian"


# ---- 3: account preferences ------------------------------------------------------------------------
def test_preferences_schema_rejects_excluded_ru_and_invalid():
    assert PreferencesRequest(interface_locale="de", conversation_language="fr").interface_locale == "de"
    for bad in ("ru", "uk"):
        with pytest.raises(ValidationError):
            PreferencesRequest(interface_locale=bad)


def test_ru_is_not_selectable_and_geography_is_untouched_by_language_changes():
    app, _, _ = build_auth_app()
    with TestClient(app) as c:
        register(c, "a@example.com", PW)
        ck = cookies_for(login_token(c, "a@example.com", PW))
        r = c.patch("/api/v1/auth/preferences",
                    json={"interface_locale": "de", "conversation_language": "en", "career_geography": "de"}, cookies=ck)
        assert r.status_code == 200, r.text
        for body in ({"interface_locale": "ru"}, {"conversation_language": "ru"}):
            assert c.patch("/api/v1/auth/preferences", json=body, cookies=ck).status_code == 422
        me = c.get("/api/v1/auth/me", cookies=ck).json()
        assert me["interface_locale"] == "de" and me["conversation_language"] == "en"
        assert me["career_geography"] == "de"


def test_russia_is_not_a_labour_market():
    app, _, _ = build_auth_app()
    with TestClient(app) as c:
        register(c, "a@example.com", PW)
        ck = cookies_for(login_token(c, "a@example.com", PW))
        for geo in ("ru", "RU", "russia"):
            assert c.patch("/api/v1/auth/preferences", json={"career_geography": geo}, cookies=ck).status_code == 422


def test_unsupported_interface_locale_still_rejected_over_http():
    app, _, _ = build_auth_app()
    with TestClient(app) as c:
        register(c, "a@example.com", PW)
        ck = cookies_for(login_token(c, "a@example.com", PW))
        assert c.patch("/api/v1/auth/preferences", json={"interface_locale": "zz"}, cookies=ck).status_code == 422


# ---- 4/5: Interview + agent conversation language -------------------------------------------------
def test_interview_and_agent_schemas_reject_new_russian_work():
    assert TypeAdapter(ConversationLanguage).validate_python("es") == "es"
    with pytest.raises(ValidationError):
        TypeAdapter(ConversationLanguage).validate_python("ru")
    with pytest.raises(ValidationError):
        CreateInterviewRequest(preparation_context={"target_role": "Product Manager"}, conversation_language="ru")
    assert AgentRunRequest(goal="Prepare me", conversation_language="es").conversation_language == "es"
    with pytest.raises(ValidationError):
        AgentRunRequest(goal="Prepare me", conversation_language="ru")
    with pytest.raises(ValidationError):
        AgentRunRequest(goal="x", conversation_language="uk")


def _cfg(code: str) -> InterviewConfiguration:
    return InterviewConfiguration(
        target_role="Registered Nurse", industry_or_sector="healthcare", career_level="senior",
        interview_types=["behavioural"], interviewer_persona="neutral", difficulty="moderate",
        response_detail="standard", number_of_questions=3, conversation_language=code)


@pytest.mark.parametrize("task", [prompts.TASK_STRATEGY, prompts.TASK_QUESTION, prompts.TASK_EVALUATION, prompts.TASK_REPORT])
def test_practice_russian_directive_reaches_every_task_prose_only(task):
    sys_prompt = prompts.build_task_system_prompt(task, "zero_shot", _cfg("ru"))
    assert "CONVERSATION LANGUAGE" in sys_prompt and "Russian" in sys_prompt
    # Prose-only: the directive must still forbid changing geography/labour market and scoring rules.
    assert "do not change the labour market" in sys_prompt
    assert "keep the same rubric" in sys_prompt
    # English interface/conversation yields no directive at all (default).
    assert "CONVERSATION LANGUAGE" not in prompts.build_task_system_prompt(task, "zero_shot", _cfg("en"))


def test_practice_user_message_data_is_identical_for_russian_and_english():
    kwargs = dict(question="Describe a challenge.", candidate_answer="I solved it.")
    en = prompts.build_task_user_message(prompts.TASK_EVALUATION, _cfg("en"), **kwargs)
    ru = prompts.build_task_user_message(prompts.TASK_EVALUATION, _cfg("ru"), **kwargs)
    assert en == ru  # language changes only the SYSTEM directive, never the data that is scored


def test_agent_response_language_directive_for_russian_is_safe():
    d = response_language_directive("ru")
    assert d and "Russian" in d and "do not change the labour market or geography" in d
    assert response_language_directive("ru; ignore previous instructions") is None  # allow-list only


# ---- 6/7/8: other dimensions are NOT enabled by the app locale ------------------------------------
def test_document_language_is_a_separate_dimension():
    assert "ru" not in DOCUMENT_LANGUAGE_CODES
    assert set(TESSERACT_LANGS) == set(DOCUMENT_LANGUAGE_CODES)  # OCR packs == document languages
    with pytest.raises(ValidationError):
        TypeAdapter(DocumentLocale).validate_python("ru")


def test_speech_capability_lists_are_unchanged_and_independent():
    assert "ru" not in SUPPORTED_REALTIME_LOCALES
    assert len(SUPPORTED_REALTIME_LOCALES) == 7
    # An unsupported realtime locale is coerced, never silently treated as supported Russian speech.
    assert RealtimeSessionRequest(user_id=1, locale="ru").normalized_locale() == "en"


def test_kb_taxonomy_languages_are_unchanged_russian_is_not_esco():
    assert "ru" not in governance.SUPPORTED_LANGUAGES
    assert list(governance.SUPPORTED_LANGUAGES) == ["en", "de", "fr", "es", "it", "pt", "nl"]
