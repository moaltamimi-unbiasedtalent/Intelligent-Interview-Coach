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
LOCALES = ["en", "de", "fr", "es", "it", "pt", "nl"]
PW = "correcthorsebattery"


def read(rel: str, base: Path = FE) -> str:
    p = base / rel
    return p.read_text(encoding="utf-8") if p.exists() else ""


def run() -> dict[str, tuple[bool, str]]:
    results: dict[str, tuple[bool, str]] = {}

    def check(name: str, ok: bool, detail: str = "") -> None:
        results[name] = (bool(ok), detail)

    # 1) locale registry — seven catalogue files + typed registry.
    files_ok = all((FE / f"lib/i18n/messages/{c}.ts").exists() for c in LOCALES)
    locales_ts = read("lib/i18n/locales.ts")
    registry_ok = all(f'"{c}"' in locales_ts for c in LOCALES)
    check("locale_registry", files_ok and registry_ok, "7 catalogue files + typed locale registry")

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
    help_ok = all("languages:" in read(f"lib/i18n/messages/{c}.ts") and "gettingStarted:" in read(f"lib/i18n/messages/{c}.ts") for c in LOCALES)
    check("help_localization", help_ok, "help namespace present in all 7 catalogues (titles/notes)")
    val_ok = all("weakPassword" in read(f"lib/i18n/messages/{c}.ts") and "incorrectCredentials" in read(f"lib/i18n/messages/{c}.ts") for c in LOCALES)
    check("validation_message_localization", val_ok, "auth validation/error messages in all 7 catalogues")

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

    return results


SAFETY = {
    "language_geography_separation",
    "conversation_directive_injection_safe",
    "cross_user_locale_isolation",
    "unsupported_locale_rejected_api",
    "fallback_correctness",
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
