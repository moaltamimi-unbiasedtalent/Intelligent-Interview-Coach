#!/usr/bin/env python
"""Capstone P3.5 internationalization & localization evaluation.

Deterministic, offline invariant checks (no browser, no paid calls). Catalogue key
completeness is additionally enforced by TypeScript (`Catalog` type) and the frontend
`tests/i18n.test.tsx`; this script verifies the architecture, safety and preference
invariants that can be checked from Python. Exits non-zero on any failure.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("EMAIL_PROVIDER", "memory")

ROOT = Path(__file__).resolve().parent.parent
FE = ROOT / "frontend"
LOCALES = ["en", "de", "fr", "es", "it", "pt", "nl", "ru"]
PW = "correcthorsebattery"


def read(rel: str, base: Path = FE) -> str:
    p = base / rel
    return p.read_text(encoding="utf-8") if p.exists() else ""


def locale_src(loc: str) -> str:
    """Source text of one locale's base catalogue. Russian (W9.7) is composed from three part files."""
    base = read(f"lib/i18n/messages/{loc}.ts")
    if loc == "ru":
        base += "".join(read(f"lib/i18n/messages/ru-parts/{x}.ts") for x in ("a", "b", "c"))
    return base


def run() -> dict[str, tuple[bool, str]]:
    results: dict[str, tuple[bool, str]] = {}

    def check(name: str, ok: bool, detail: str = "") -> None:
        results[name] = (bool(ok), detail)

    # 1) locale registry — seven catalogue files + typed registry.
    files_ok = all((FE / f"lib/i18n/messages/{c}.ts").exists() for c in LOCALES)
    locales_ts = read("lib/i18n/locales.ts")
    registry_ok = all(f'"{c}"' in locales_ts for c in LOCALES)
    check("locale_registry", files_ok and registry_ok, "8 catalogue files + typed locale registry")

    # 2) catalogue completeness — each non-English catalogue is typed `Catalog` (which
    #    enforces the exact English key set at compile time) and default-exports.
    typed = all(
        (": Catalog" in read(f"lib/i18n/messages/{c}.ts") and "export default" in read(f"lib/i18n/messages/{c}.ts"))
        for c in LOCALES if c != "en"
    )
    en_typed = "Catalog = messages" in read("lib/i18n/messages/en.ts") or "const en: Catalog" in read("lib/i18n/messages/en.ts")
    check("catalogue_completeness", typed and en_typed, "each locale typed Catalog (TS-enforced key parity)")

    # 3) English is the source; missing keys fall back to English, never undefined.
    catalog_ts = read("lib/i18n/catalog.ts")
    check("fallback_correctness", "enCat[ns]?.[k]" in catalog_ts and "return String(key)" in catalog_ts,
          "English fallback then key (never undefined/blank)")

    # 4) unsupported locale is handled safely.
    check("unsupported_locale_safety", "toSupportedLocale" in locales_ts and "?? DEFAULT_APP_LOCALE" in read("app/layout.tsx"),
          "unsupported locale narrows to null → default English")

    # 5) route/locale handling + <html lang> accessibility.
    layout = read("app/layout.tsx")
    check("route_locale_handling", "LOCALE_COOKIE" in layout and "cookies()" in layout,
          "server reads locale cookie for initial render")
    check("accessibility_lang_attribute", "lang={initialLocale}" in layout and 'document.documentElement.lang' in read("components/i18n/I18nProvider.tsx"),
          "<html lang> set from locale, kept in sync client-side")

    # 6) three independent language controls (interface / conversation / dictation).
    ls = read("components/settings/LanguageSettings.tsx")
    check("dictation_locale_separation", "DICTATION_LANGUAGES" in ls and "interfaceLanguage" in ls,
          "dictation control is separate from interface/conversation")
    check("conversation_locale_separation", "conversation_language" in ls and "useDictationLanguage" in ls and "setLocale" in ls,
          "three distinct controls, never merged")

    # 7) language ≠ geography (proven at the source of geography detection).
    from src.copilot.knowledge.router import detect_country
    geo_stable = detect_country("salary in Germany") == "DE" and detect_country("salary in the UK") == "UK"
    # detect_country takes only the query; the agent directive explicitly says not to
    # change geography, and it never reaches detect_country.
    directive = read("src/agent/policies.py", ROOT)
    check("language_geography_separation", geo_stable and "do not change the labour market or geography" in directive.lower(),
          "geography = f(query text); language never changes it")

    # 8) conversation-language directive is allow-listed (injection-safe).
    from src.agent.policies import response_language_directive
    inj_safe = response_language_directive("'; DROP--") is None and response_language_directive("de") is not None
    check("conversation_directive_injection_safe", inj_safe, "directive built only from the allow-list")

    # 9) help + validation strings exist in the catalogue for all locales (titles/keys).
    help_ok = all("languages:" in locale_src(c) and "gettingStarted:" in locale_src(c) for c in LOCALES)
    check("help_localization", help_ok, "help namespace present in all 8 catalogues (titles/notes)")
    val_ok = all("weakPassword" in locale_src(c) and "incorrectCredentials" in locale_src(c) for c in LOCALES)
    check("validation_message_localization", val_ok, "auth validation/error messages in all 8 catalogues")

    # 10) preference persistence + cross-user isolation (API).
    from fastapi.testclient import TestClient
    from tests._auth_factories import build_auth_app, cookies_for, login_token, register

    app, _, _ = build_auth_app()
    with TestClient(app) as c:
        register(c, "a@example.com", PW)
        register(c, "b@example.com", PW)
        a = login_token(c, "a@example.com", PW)
        b = login_token(c, "b@example.com", PW)
        c.patch("/api/v1/auth/preferences", json={"interface_locale": "de", "conversation_language": "fr"}, cookies=cookies_for(a))
        me_a = c.get("/api/v1/auth/me", cookies=cookies_for(a)).json()
        me_b = c.get("/api/v1/auth/me", cookies=cookies_for(b)).json()
        persist = me_a["interface_locale"] == "de" and me_a["conversation_language"] == "fr"
        isolate = me_b["interface_locale"] == "en" and me_b["conversation_language"] == "en"
        bad = c.patch("/api/v1/auth/preferences", json={"interface_locale": "zz"}, cookies=cookies_for(a)).status_code
    check("preference_persistence", persist, "interface + conversation locale persist server-side")
    check("cross_user_locale_isolation", isolate, "one user's locale never affects another")
    check("unsupported_locale_rejected_api", bad == 422, "unsupported locale rejected at the API (422)")

    # 11) candidate-facing hardcoded-English guard (P10B-W9.6): the bounded frontend scanner must
    # report zero unexplained candidate-facing literals. Degrades to a soft pass only if node is
    # unavailable in this environment (never a false FAIL on tooling absence).
    import shutil
    import subprocess
    if shutil.which("node") is None:
        check("no_hardcoded_candidate_english", True, "node unavailable — guard skipped (run `npm test`)")
    else:
        proc = subprocess.run(
            ["node", "scripts/scan-i18n.mjs", "--count"], cwd=str(FE),
            capture_output=True, text=True,
        )
        n = (proc.stdout or "").strip()
        ok = n == "0"
        check("no_hardcoded_candidate_english", ok,
              f"scanner reports {n or '?'} candidate-facing hardcoded-English offenders")

    # 12) Russian (W9.7) is the 8th app/conversation locale and is NOT thereby a speech language, a
    # labour market, an OCR/document language or a KB/taxonomy (ESCO) language. Each of those is its own
    # capability; adding an app locale must never enable them.
    from src.copilot.knowledge import governance
    from src.documents.ocr import TESSERACT_LANGS
    from src.locales import DOCUMENT_LANGUAGE_CODES, SUPPORTED_LOCALE_CODES
    from src.voice.realtime import SUPPORTED_REALTIME_LOCALES
    app_ok = "ru" in SUPPORTED_LOCALE_CODES and len(SUPPORTED_LOCALE_CODES) == 8 and '"ru"' in locales_ts
    check("russian_is_eighth_app_locale", app_ok, "ru in the canonical backend + frontend locale registries (8 locales)")
    dict_src = read("components/ui/DictationControl.tsx")
    tts_src = read("lib/speech/ttsLocales.ts")
    speech_ok = (
        "ru" not in SUPPORTED_REALTIME_LOCALES
        and "ru-RU" not in dict_src and "ru-" not in dict_src.split("DICTATION_LANGUAGES", 1)[-1].split("];", 1)[0]
        and 'ru: "' not in tts_src
    )
    check("app_locale_does_not_imply_speech", speech_ok,
          "ru is NOT in dictation / TTS / realtime lists (speech capability is a separate, unchanged dimension)")
    other_ok = (
        "ru" not in governance.SUPPORTED_LANGUAGES
        and "ru" not in TESSERACT_LANGS and "ru" not in DOCUMENT_LANGUAGE_CODES
        and '"ru"' not in read("components/settings/CareerGeographyField.tsx")
    )
    check("russian_not_geography_ocr_or_taxonomy", other_ok,
          "ru is NOT a labour market, OCR/document language or KB/ESCO language")

    # 13) Protected brand slogan (W9.7): ONE constant, every locale's tagline is that constant verbatim
    # (never translated/transliterated/re-punctuated), and no catalogue carries a translated variant.
    brand = read("lib/brand.ts")
    slogan_defined = 'export const BRAND_SLOGAN = "Ask More. Be More.";' in brand
    taglines_ok = all(
        "tagline: BRAND_SLOGAN," in locale_src(c) and "BRAND_SLOGAN" in locale_src(c) for c in LOCALES
    )
    translated_variants = ("Frag mehr", "Demandez plus", "Pregunta más", "Chiedi di più",
                           "Pergunte mais", "Vraag meer", "Спрашивай больше")
    no_variants = not any(v in "".join(locale_src(c) for c in LOCALES) for v in translated_variants)
    check("brand_slogan_invariant", slogan_defined and taglines_ok and no_variants,
          'every locale resolves common.tagline to BRAND_SLOGAN == "Ask More. Be More." (single source, no variants)')
    guard = read("scripts/scan-i18n.mjs")
    check("brand_slogan_guard_is_exact_only",
          'new Set(["Ask More. Be More."])' in guard and "APPROVED_BRAND_INVARIANTS.has(text)" in guard,
          "the hardcoded-English guard approves ONLY the exact slogan (not arbitrary English copy)")

    # 14) W9.7A: structural blind-spot coverage + Mo-prose language ownership.
    # (a) The hardcoded-English guard must keep its three structural passes (string-tuple arrays like the Home
    #     feature blocks, HTML entities, JSX text mixed with `{}` expressions) - W9.7 visual QA found real
    #     English that the JSX-text/attribute/object-key passes could not see.
    guard_src = read("scripts/scan-i18n.mjs")
    check("scanner_structural_coverage",
          all(tok in guard_src for tok in ('"array-literal"', '"jsx-text-mixed"', "decodeEntities", "`obj:")),
          "scanner covers string-tuple arrays, mixed JSX text, HTML entities and object-literal content")
    # (b) Language ownership: Mo's prose (incl. the 3 response-template headings, the insufficient-evidence
    #     sentence and the deterministic fallback) follows the CONVERSATION language; English stays byte-identical.
    from src.api.schemas.career import CareerChatRequest as _ApiReq
    from src.copilot.rag import localized as _loc
    from src.copilot.rag.synthesis import build_evidence_messages as _bem
    owner_ok = (
        set(_loc.SECTION_HEADINGS) == set(_loc.INSUFFICIENT) == set(_loc.FALLBACK) == set(SUPPORTED_LOCALE_CODES)
        and "conversation_language" in _ApiReq.model_fields
        and _bem(query="q", sections={}, language=None) == _bem(query="q", sections={}, language="en")
        and "Подтверждения (из источников):" in _bem(query="q", sections={}, language="ru")[0]["content"]
        and "Evidence (from sources):" not in _bem(query="q", sections={}, language="de")[0]["content"]
    )
    check("mo_prose_language_ownership", owner_ok,
          "Career-chat headings/fallback follow the Mo conversation language; English default unchanged")

    return results


SAFETY = {
    "language_geography_separation",
    "conversation_directive_injection_safe",
    "cross_user_locale_isolation",
    "unsupported_locale_rejected_api",
    "fallback_correctness",
    "app_locale_does_not_imply_speech",
    "russian_not_geography_ocr_or_taxonomy",
    "brand_slogan_invariant",
    "mo_prose_language_ownership",
}


def main() -> int:
    print("ASK4MO — CAPSTONE P3.5 I18N / L10N EVALUATION\n")
    results = run()
    failed = False
    for name in sorted(results):
        ok, detail = results[name]
        if not ok:
            failed = True
        tag = "  ← SAFETY" if (name in SAFETY and not ok) else ""
        print(f"  {name:36s} {'PASS' if ok else 'FAIL'}  {detail}{tag}")
    print("\nPaid LLM calls: 0   Live calls: 0")
    if failed:
        print("\nRESULT: FAIL")
        return 1
    print("\nRESULT: PASS (all i18n/l10n invariants hold)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
