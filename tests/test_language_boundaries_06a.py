"""06A (REQ-LANG-01/11/12/14, LG-14): active Candidate locales, Russian exclusion, fallback, Admin English-only.

Deterministic, 0 paid/live calls. Covers:
  * the code-defined ACTIVE_CANDIDATE_LOCALES (seven) and its exposure through GET /capabilities (backward compatible);
  * new selections, sessions and conversations refuse a non-active locale with the standard 422 validation shape;
  * an account whose STORED preference is a non-active locale falls back to the default for display, with the stored
    value and the career geography untouched and no data migration;
  * Russian code, catalogue and prompt allow-lists are preserved; zh/hi/ar are NOT registered;
  * Admin catalogues and components stay English-only.
"""

from __future__ import annotations

import re
import typing
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import TypeAdapter, ValidationError
from sqlalchemy import select

from src import prompts
from src.agent.policies import RESPONSE_LANGUAGE_NAMES
from src.api.schemas.agent import AgentRunRequest
from src.api.schemas.auth import PreferencesRequest, RegisterRequest
from src.api.schemas.career import CareerChatRequest
from src.api.schemas.interview import CreateInterviewRequest, InterviewConfigIn
from src.locales import (
    ACTIVE_CANDIDATE_LOCALES,
    DEFAULT_ACTIVE_LOCALE,
    DOCUMENT_LANGUAGE_CODES,
    LANGUAGE_NAMES,
    SUPPORTED_LOCALE_CODES,
    AppLocale,
    effective_locale,
    is_active_locale,
)
from src.persistence import UserPreference
from src.voice.realtime import SUPPORTED_REALTIME_LOCALES
from tests._auth_factories import build_auth_app, cookies_for, login_token, register

ROOT = Path(__file__).resolve().parent.parent
FE = ROOT / "frontend"
PW = "correcthorsebattery"
SEVEN = ("en", "de", "fr", "es", "it", "pt", "nl")


def test_active_locales_are_the_seven_and_code_defined():
    assert ACTIVE_CANDIDATE_LOCALES == SEVEN
    assert typing.get_args(AppLocale) == SEVEN
    assert "ru" not in ACTIVE_CANDIDATE_LOCALES
    assert set(ACTIVE_CANDIDATE_LOCALES) <= set(SUPPORTED_LOCALE_CODES)
    assert isinstance(ACTIVE_CANDIDATE_LOCALES, tuple)  # immutable: no runtime mutation
    # Not environment- or Admin-configurable: the definition does not read os.environ or a database.
    src = (ROOT / "src/locales.py").read_text(encoding="utf-8")
    assert not re.search(r"^\s*(import os|from os|import sqlalchemy|from sqlalchemy)", src, re.M)
    assert "os.environ" not in src and "getenv(" not in src


def test_effective_locale_fallback_is_read_time_only():
    assert effective_locale("de") == "de"
    for stored in ("ru", "zh", None, "", "xx"):
        assert effective_locale(stored) == DEFAULT_ACTIVE_LOCALE
    assert is_active_locale("nl") and not is_active_locale("ru")


def test_russian_is_preserved_in_the_catalogue_but_not_selectable():
    assert "ru" in SUPPORTED_LOCALE_CODES and "ru" in LANGUAGE_NAMES
    assert prompts._CONVERSATION_LANGUAGE_NAMES["ru"] == RESPONSE_LANGUAGE_NAMES["ru"] == "Russian"
    assert (FE / "lib/i18n/messages/ru.ts").exists()
    assert (ROOT / "tests/test_w97_russian_locale.py").exists()


def test_no_mandarin_hindi_arabic_locale_is_registered():
    for code in ("zh", "hi", "ar", "zh-CN", "cmn"):
        assert code not in SUPPORTED_LOCALE_CODES and code not in LANGUAGE_NAMES
        assert code not in ACTIVE_CANDIDATE_LOCALES
    fe = (FE / "lib/i18n/locales.ts").read_text(encoding="utf-8")
    assert not re.search(r'code: "(zh|hi|ar)"', fe)
    assert not any((FE / f"lib/i18n/messages/{c}.ts").exists() for c in ("zh", "hi", "ar"))


def test_speech_and_document_languages_are_unchanged():
    assert len(SUPPORTED_REALTIME_LOCALES) == 7 and "ru" not in SUPPORTED_REALTIME_LOCALES
    assert DOCUMENT_LANGUAGE_CODES == SEVEN


def test_frontend_active_list_matches_backend_exactly():
    ts = (FE / "lib/i18n/locales.ts").read_text(encoding="utf-8")
    m = re.search(r"ACTIVE_CANDIDATE_LOCALES: readonly AppLocale\[\] = \[([^\]]*)\]", ts)
    assert m, "frontend ACTIVE_CANDIDATE_LOCALES not found"
    assert tuple(re.findall(r'"(\w+)"', m.group(1))) == ACTIVE_CANDIDATE_LOCALES
    for rel in ("components/i18n/LanguageMenu.tsx", "components/i18n/ConversationLanguageField.tsx", "components/settings/LanguageSettings.tsx"):
        text = (FE / rel).read_text(encoding="utf-8")
        # 06H: selectors render the server-offered subset, which is derived from SELECTABLE_LOCALES (never APP_LOCALES); see offeredLocales.ts.
        assert "useOfferedLocales" in text and "options.map" in text and "APP_LOCALES.map" not in text, rel
    assert "SELECTABLE_LOCALES.filter" in (FE / "lib/i18n/offeredLocales.ts").read_text(encoding="utf-8")


# ---- new work refuses a non-active locale (existing 422 validation shape) -------------------------
@pytest.mark.parametrize("bad", ["ru", "RU", "ru-RU", "zh", "xx"])
def test_new_work_schemas_reject_non_active_locales(bad):
    with pytest.raises(ValidationError):
        TypeAdapter(AppLocale).validate_python(bad)
    with pytest.raises(ValidationError):
        PreferencesRequest(interface_locale=bad)
    with pytest.raises(ValidationError):
        PreferencesRequest(conversation_language=bad)
    with pytest.raises(ValidationError):
        RegisterRequest(email="a@example.com", password=PW, locale=bad)
    with pytest.raises(ValidationError):
        AgentRunRequest(goal="Prepare me", conversation_language=bad)
    with pytest.raises(ValidationError):
        CareerChatRequest(question="x", conversation_language=bad)
    with pytest.raises(ValidationError):
        InterviewConfigIn(target_role="Nurse", industry_or_sector="healthcare", career_level="senior", conversation_language=bad)
    with pytest.raises(ValidationError):
        CreateInterviewRequest(preparation_context={"target_role": "PM"}, conversation_language=bad)


@pytest.mark.parametrize("good", SEVEN)
def test_new_work_schemas_accept_every_active_locale(good):
    assert PreferencesRequest(interface_locale=good, conversation_language=good).interface_locale == good
    assert AgentRunRequest(goal="Prepare me", conversation_language=good).conversation_language == good


def test_http_rejects_russian_with_the_standard_validation_error_shape():
    app, _, _ = build_auth_app()
    with TestClient(app) as c:
        register(c, "a@example.com", PW)
        ck = cookies_for(login_token(c, "a@example.com", PW))
        r = c.patch("/api/v1/auth/preferences", json={"interface_locale": "ru"}, cookies=ck)
        assert r.status_code == 422
        r2 = c.patch("/api/v1/auth/preferences", json={"interface_locale": "zz"}, cookies=ck)
        assert r2.status_code == 422 and r.json().keys() == r2.json().keys()  # same envelope as any other invalid locale


def test_capabilities_exposes_active_locales_backward_compatibly():
    app, _, _ = build_auth_app()
    with TestClient(app) as c:
        body = c.get("/api/v1/capabilities").json()
        assert body["active_candidate_locales"] == list(ACTIVE_CANDIDATE_LOCALES)
        assert body["default_locale"] == "en"
        for old in ("career_intelligence", "interview_practice", "live_interview_enabled", "agentic_rag", "realtime_voice_enabled"):
            assert old in body  # existing keys unchanged


def test_stored_russian_preference_falls_back_without_touching_geography_or_data():
    app, repo, _ = build_auth_app()
    with TestClient(app) as c:
        register(c, "a@example.com", PW)
        ck = cookies_for(login_token(c, "a@example.com", PW))
        assert c.patch("/api/v1/auth/preferences", json={"career_geography": "de"}, cookies=ck).status_code == 200
        # Simulate a legacy account: write 'ru' straight into the stored preference (no API accepts it any more).
        with repo.session_factory() as s:
            pref = s.scalar(select(UserPreference))
            pref.interface_locale = "ru"
            pref.conversation_language = "ru"
            s.commit()
        me = c.get("/api/v1/auth/me", cookies=ck).json()
        assert me["interface_locale"] == "en" and me["conversation_language"] == "en"  # display fallback
        assert me["career_geography"] == "de"  # language never moves the market
        with repo.session_factory() as s:  # no data migration, no rewrite on read
            pref = s.scalar(select(UserPreference))
            assert pref.interface_locale == "ru" and pref.conversation_language == "ru"
        # The owner can pick an active language and everything keeps working.
        assert c.patch("/api/v1/auth/preferences", json={"interface_locale": "fr"}, cookies=ck).status_code == 200
        me = c.get("/api/v1/auth/me", cookies=ck).json()
        assert me["interface_locale"] == "fr" and me["career_geography"] == "de"


def test_existing_sessions_with_a_stored_russian_config_keep_loading():
    # The persisted interview configuration stores the language as a plain string, never the new-work Literal.
    from src.models import InterviewConfiguration

    cfg = InterviewConfiguration(
        target_role="Registered Nurse", industry_or_sector="healthcare", career_level="senior",
        interview_types=["behavioural"], interviewer_persona="neutral", difficulty="moderate",
        response_detail="standard", number_of_questions=3, conversation_language="ru")
    assert cfg.conversation_language == "ru"
    assert "CONVERSATION LANGUAGE" in prompts.build_task_system_prompt(prompts.TASK_EVALUATION, "zero_shot", cfg)


# ---- Admin stays English-only (REQ-LANG-12) ------------------------------------------------------
def test_admin_surfaces_are_english_only():
    offenders = []
    for base in (FE / "components/admin", FE / "app/admin"):
        for p in base.rglob("*.tsx"):
            text = p.read_text(encoding="utf-8")
            if re.search(r"\buseT\(|\buseI18n\(|\btranslate\(|from \"@/components/i18n|from \"@/lib/i18n/catalog", text):
                offenders.append(str(p.relative_to(FE)))
    assert offenders == []
    en = (FE / "lib/i18n/messages/en.ts").read_text(encoding="utf-8")
    assert not re.search(r"^  admin\w*: \{", en, re.M)  # no Admin namespace in any candidate catalogue
    for loc in (ACTIVE_CANDIDATE_LOCALES + ("ru",)):
        assert not re.search(r"^  admin\w*: \{", (FE / f"lib/i18n/messages/{loc}.ts").read_text(encoding="utf-8"), re.M)
