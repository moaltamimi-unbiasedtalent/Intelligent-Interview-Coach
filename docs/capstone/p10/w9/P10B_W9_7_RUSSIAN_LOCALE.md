# P10B-W9.7 — Russian Locale #8

Implementation record. Russian (`ru`) becomes the eighth Ask4Mo interface + Mo-conversation language, and
the slogan **"Ask More. Be More."** is locked as a permanent, untranslated brand invariant. **No
migration**, no new API, no geography/taxonomy/speech change, no RC, Pilot 2 not resumed, 0 paid/live calls.

## 1. Baseline

- From W9.6A `fix/p10b-w9-6a-help-localization-closure` @ `a82081e` (ancestry intact: a82081e ← 847215b ←
  dc655ff ← 4483f32 ← 7fc600b ← c9cdff5 ← 5984953 ← 334ffbd ← 80354f3). New branch
  `feat/p10b-w9-7-russian-locale`. Alembic head `0014_opportunities` (unchanged). RC-P10-002 immutable;
  no RC-P10-003.

## 2. Requirement

Add Russian across the same candidate-facing experience W9.6/W9.6A localize (7 -> 8 locales) without
coupling language to any other capability, and make `Ask More. Be More.` exactly English in every
locale, now and in future.

**Owner decision recorded (slogan form):** the spec text wrote `Ask More, Be More` (comma), but the
established brand canon everywhere in the repo is **`Ask More. Be More.`** (README, presentation notes
that say "exact capitalisation/punctuation", `brand.test.tsx`, E2E, marketing, 23 occurrences, 0 with a
comma). The owner confirmed the established form. **The protected string is `Ask More. Be More.`**

## 3. The 7 -> 8 insertion-point audit (classified)

Categories: 1 application locale · 2 conversation language · 3 speech/dictation capability · 4 external
taxonomy / document-language capability · 5 geography · 6 unrelated.

| # | Location | Category | W9.7 action |
|---|---|---|---|
| 1 | `src/locales.py` `SUPPORTED_LOCALE_CODES`, `AppLocale` | 1+2 | **+ `ru`** (single source) |
| 2 | `src/persistence.py` `SUPPORTED_LOCALES` (re-export) | 1+2 | automatic |
| 3 | `src/api/schemas/{auth,interview,agent}.py` (`AppLocale`) | 1+2 | automatic |
| 4 | `src/auth_repository.py` `set_interface_locale` / `set_conversation_language` | 1+2 | automatic |
| 5 | `src/prompts.py` `_CONVERSATION_LANGUAGE_NAMES` (Practice) | 2 | **+ `ru: "Russian"`** |
| 6 | `src/agent/policies.py` `RESPONSE_LANGUAGE_NAMES` (Mo/Prepare) | 2 | **+ `ru: "Russian"`** |
| 7 | `frontend/lib/i18n/locales.ts` `APP_LOCALES` | 1 | **+ `ru` / "Русский"** |
| 8 | `lib/i18n/catalog.ts` `CATALOGS` | 1 | **+ `ru`** |
| 9 | `lib/i18n/messages/ru.ts` (+ `ru-parts/{a,b,c}.ts`), `w96/ru/*`, `w96/help/ru.ts`, `w96/index.ts` | 1 | **new** |
| 10 | `LanguageMenu`, `ConversationLanguageField`, `LanguageSettings`, `InterviewSessionSetup` | 1+2 | automatic (iterate `APP_LOCALES`) |
| 11 | `app/layout.tsx`, `lib/i18n/cookie.ts`, `I18nProvider` (`toSupportedLocale`, `<html lang>`) | 1 | automatic |
| 12 | `DictationControl` `DICTATION_LANGUAGES`, `useDictationLanguage` | 3 | **unchanged** (7) |
| 13 | `lib/speech/ttsLocales.ts` (TTS), `src/voice/realtime.py` `SUPPORTED_REALTIME_LOCALES` | 3 | **unchanged**; added `isSpeechOutputLocale` to hide controls (see §12) |
| 14 | `src/documents/ocr.py` `TESSERACT_LANGS`, `documents_service` `language_hint` | 4 (document/OCR language) | **decoupled**: new `DOCUMENT_LANGUAGE_CODES` (7) so `ru` is not silently accepted as an OCR language |
| 15 | `src/copilot/knowledge/governance.py` `SUPPORTED_LANGUAGES`, `multi_agent_eval` fixtures | 4 (KB/taxonomy) | **unchanged** (7) |
| 16 | `src/persistence.py` `CAREER_GEOGRAPHIES`, `schemas/auth.py` `CareerGeography`, `CareerGeographyField` | 5 | **unchanged** (no `ru` market) |
| 17 | Evaluators/tests hard-coding "seven" locales | 6/1 | updated to eight (derived from the canonical source where possible) |

Two silent couplings were found and removed rather than inherited: (a) the documents `language_hint`
validated against the app-locale list while OCR silently fell back to English for an unmapped language;
(b) `toSpeechLocale("ru")` falls back to `en-US`, so a Russian answer would have been read by an
English voice (and realtime would have been coerced to `en` by the server).

## 4. Backend locale changes

`src/locales.py` is the one source: `SUPPORTED_LOCALE_CODES` (8) and `AppLocale` Literal (8, still a
bounded Literal, never `str`). New separate `DOCUMENT_LANGUAGE_CODES` / `DocumentLanguage` (7, OCR packs).
`src/prompts.py` and `src/agent/policies.py` carry the display name `Russian` (the model only ever sees a
name from the allow-list; unknown/injection strings yield no directive). `src/api/schemas/documents.py`
and `documents_service` use `DocumentLanguage`/`DOCUMENT_LANGUAGE_CODES`. No migration, no route change.

## 5. Frontend locale changes

`APP_LOCALES` + `{ code: "ru", label: "Russian", nativeLabel: "Русский" }` (the selectors render
`nativeLabel`, so there is no second Russian-specific selection system). `catalog.ts` merges `ru` like the
other locales. `w96/index.ts` now attaches a Russian block per fragment (each typed against that
fragment's English shape) and **throws if a fragment lacks any supported locale** (the previous silent
`?? en` fallback was removed, so a missing Russian block can no longer hide behind English).

## 6. Catalogue key count

**1,428 keys × 33 namespaces per locale, identical in all 8 locales (11,424 strings)** = 759 base
(`en.ts`) + the W9.6/W9.6A fragments (prepare 207, practice 96, surfaces 9, legal 134, shell 81, help 144 =
671; 2 keys overlap base namespaces). One key was added in this wave: `prepare.contextTab` (see §20 -
a W9.6A regression fix). Russian parity is compile-time enforced (`Catalog`, `Pick<Catalog,...>`,
`LegalFragment`, derived fragment types, `help/index.ts`) and re-verified by `tests/i18n.test.tsx` and
`tests/russian-locale.test.tsx` (key set, non-blank, identical `{placeholders}`).

## 7. Russian terminology map (engineering decisions)

Formal "вы"; no em/en dash (repo rule; colon/comma/parentheses instead); «ёлочки» quotes.

| Concept | Russian | Note |
|---|---|---|
| Opportunity | **вакансия** | verbs «добавить», never «создать/опубликовать» (those read as an employer posting a vacancy); «целевая вакансия» when clarity needs it. Internal route/API/object names stay `Opportunity`. |
| Prepare / Practice | Подготовка / Тренировка | practice interview = «тренировочное собеседование» |
| Progress / History | Прогресс / История | |
| Documents / Sources | Документы / Источники | |
| Evidence | подтверждения | "evidence gap" = пробел в подтверждениях |
| Workspace | рабочее пространство | distinct from вакансия |
| Memory | память | «Память Mo» |
| Interview / Coach | собеседование / коуч | «ИИ-коуч по собеседованиям» |
| Company / Role / JD | компания / должность / описание вакансии | |
| Report / Evaluation / Feedback | отчёт / оценка / обратная связь | |
| Deep Dive / Story Bank | Углублённый разбор / Банк историй | |
| Settings / Account / Help | Настройки / Аккаунт / Справка | |
| Interface / conversation / dictation language | язык интерфейса / язык общения с Mo / язык диктовки | three separate controls |

Verbatim (never translated): Ask4Mo, Mo, **Ask More. Be More.**, CV, JD, OCR, file formats, plan names
(Basic, Premium), Glassdoor/Kununu/Google/LinkedIn, O*NET/ESCO, RAGAS, user content and source names.

## 8. Interface coverage

Russian covers everything W9.6/W9.6A cover: authenticated Home, Opportunity, Documents, Company,
Prepare/Mo, Practice, Progress, History, Sources, Workspaces, Settings/Account/Auth, Welcome + Tutorial
v2 (9 steps), Help (12 sections / 66 articles / 144 strings), Trust/Privacy/Terms/AI transparency/About,
shared errors/loading/retry, accessibility labels. Proof: exact key parity; only **18 of 1,428** Russian
values lack Cyrillic (14 distinct strings) and every one is an explicit brand/token/placeholder (Ask4Mo, the
slogan, Basic, Premium, Agent Inspector, Knowledge & RAG, `DE`, `acme.com`, Markdown, JSON, `v{n}`,
`name@example.com`, Mo, `€0`) - asserted by an exact allowlist in `tests/russian-locale.test.tsx` ("no silent English").

## 9. Conversation-language support

The product treats the application locales as the Mo/Practice conversation languages, so `ru` is
accepted (Pydantic `AppLocale`) for account `conversation_language`, `AgentRunRequest`, interview
configuration and the preparation handoff. `ru` maps to the explicit instruction name "Russian" in both
prompt builders. Verified deterministically (no model call).

## 10. Practice / interview routing

`prompts.build_task_system_prompt` for STRATEGY, QUESTION, EVALUATION and REPORT with `conversation_language=ru`
contains the trusted "CONVERSATION LANGUAGE ... Russian" directive, which is prose-only: it still says to
keep the same rubric and scoring and not to change the labour market. The user-message DATA sent for scoring is
byte-identical for `en` and `ru`. Scoring, rubric, report structure and weights are untouched
(`tests/test_w97_russian_locale.py`, `tests/test_wave4_*`).

## 11. Interface / conversation / geography independence

Proven in backend (`PATCH /auth/preferences` scenarios A/B/C incl. `career_geography` unchanged), unit
(`LanguageSettings`: Russian UI + English conversation; English UI + Russian conversation sends **only**
`{conversation_language: "ru"}`) and E2E (AD1/AD2). Russian UI + Russian conversation leaves geography
unchanged. `ru` is rejected as a `career_geography`.

## 12. Speech / dictation capability audit (Russian speech is NOT supported)

| Capability | Russian status | Evidence / action |
|---|---|---|
| Dictation (`DICTATION_LANGUAGES`) | not mapped | list stays the 7; selector never offers/auto-selects `ru`; stays on `en-US` |
| Browser speech recognition | not offered; provider/browser support unvalidated | no `ru-RU` code path exists |
| Configured STT provider | none (browser-only) | n/a |
| TTS (`ttsLocales`, Listen) | not mapped; **blocked pending live validation** | new `isSpeechOutputLocale()`; Listen hidden for a `ru` conversation language (otherwise an `en-US` voice would read Cyrillic) |
| Realtime voice | not mapped (`SUPPORTED_REALTIME_LOCALES` = 7); server coerces unknown -> `en` | live-voice control hidden for `ru` (E2E-proven) |

No provider marketing claim is used as evidence. Voice help (`voice.hLangA`, all 8 locales) now says:
"Russian is available as an interface and conversation language, but voice playback is not available for
it yet." `help.languagesHelp` lists eight interface languages. Dictation Help still lists the seven speech
languages. English/German playback and live voice are unchanged (E2E-proven).

## 13. ESCO / taxonomy boundary (documented, not built)

Russian is **not** an ESCO language and no Russian occupation layer exists. `governance.SUPPORTED_LANGUAGES`
stays 7 (UI support != KB content coverage). Any future (P10C) Russian occupation aliases must carry
**Ask4Mo-curated / manual-translation provenance**, never "official ESCO"/"official taxonomy translation".
Source names (O*NET, ESCO...) are never translated. Evaluator invariant `russian_not_geography_ocr_or_taxonomy`.

## 14. Geography boundary

No Russian labour market, salary source or country is added. `CAREER_GEOGRAPHIES`, the schema Literal and
`CareerGeographyField` are unchanged and tests assert `ru` is absent. Formatting uses the Intl layer with
locale `ru` only for date/number formatting; no currency/compensation change.

## 15. Help localization

`w96/help/ru.ts` carries all 144 Help strings (same keys/order as English). Russian Help renders section
titles, article questions/bodies, localized search (Unicode case-insensitive Cyrillic: query `СОБЕСЕДОВАН`
finds lowercase content), the Russian no-result message and the replayable tour. Speech descriptions are
translated faithfully (seven speech languages listed; no Russian speech implied).

## 16. Trust / legal translation status

`w96/ru/legal.ts` covers privacy, terms, AI transparency, about, help chrome, marketing and trust (134
keys). Meaning preserved: no strengthened privacy claim, no certification, no liability/AI-governance
change, no Russian-law claim; qualifiers (engineering draft, preview, not integrated) kept.
**RUSSIAN LEGAL/PRIVACY COPY IS AN ENGINEERING TRANSLATION REQUIRING HUMAN/LEGAL REVIEW BEFORE PRODUCTION
RELIANCE.** (release-readiness note, not a candidate-facing warning.)

## 17. Typography / Cyrillic assessment

- The app font is **Inter loaded with `subsets: ["latin"]` only** (`app/layout.tsx`). Cyrillic therefore
  falls through the configured stack (`system-ui, -apple-system, "Segoe UI", Roboto, sans-serif`), whose
  fonts all contain Cyrillic: **no missing-glyph boxes**, but Cyrillic renders in the platform font rather
  than Inter (a subtle typeface mismatch with Latin brand words). **No font was added or changed.**
  Recommendation (owner decision, not done): add the `"cyrillic"` subset to the existing Inter config
  (build-time subset, no font file committed; adds a small payload).
- Real-browser layout probe: 6 routes × (1280px, 390px), Russian: **0 horizontal overflow, 0 page errors**;
  headings wrap naturally; the five-item mobile bottom nav (Вакансии, Подготовка, Тренировка, Прогресс,
  История) fits; the Tutorial/invitation card and Opportunity CTA remain usable.
- Note: all eight catalogues are bundled client-side (existing architecture); First Load JS for pages
  grew from ~285 kB to ~362 kB. Lazy per-locale loading is a future optimisation (not done).

## 18. Protected brand slogan

- **Exact phrase: `Ask More. Be More.`** - never translated, transliterated or re-punctuated, in all 8
  locales and any future locale.
- Single source `frontend/lib/brand.ts` `BRAND_SLOGAN`. Every locale's `common.tagline` is that constant;
  `auth.registerSubtitle` ends with it; the About/legal text embeds it verbatim in every locale.
- **Pre-existing violation corrected:** the seven existing locales had *translated* the slogan (e.g. de
  "Frag mehr. Sei mehr.", fr "Demandez plus. Devenez plus.", es "Pregunta más. Sé más.", it "Chiedi di più.
  Diventa di più.", pt "Pergunte mais. Seja mais.", nl "Vraag meer. Word meer.") in `common.tagline` and
  `auth.registerSubtitle` (12 strings, 6 files). All now use the constant.
- Guard: `scripts/scan-i18n.mjs` approves **only the exact string** (`APPROVED_BRAND_INVARIANTS`), reported
  separately ("approved brand invariants: N", currently 0 literals in scanned `.tsx`, since it resolves
  through the catalogue); `Ask more. Be more.`, `Ask More, Be More`, `ASK MORE. BE MORE.`,
  `Ask More. Be More. Today` and any other English copy are still flagged.
- Enforcement: `tests/brand-slogan-invariant.test.ts` (24 tests: all 8 locales' tagline equality;
  subtitle/About embed; **every** "ask more" occurrence in any catalogue is the exact phrase; no Cyrillic
  transliteration; guard exact-match behaviour) and `eval_i18n_l10n` (`brand_slogan_invariant`,
  `brand_slogan_guard_is_exact_only`, mutation-tested). E2E asserts the slogan visible and unchanged under
  the Russian interface on `/app` and `/about`.

## 19. Tests

- Backend `tests/test_w97_russian_locale.py` (17): canonical tuple + Literal lock-step, bounded typing,
  persistence re-export, preferences accept/reject (HTTP), interface/conversation/geography independence,
  Russia not a market, Interview/Agent schemas, Practice directive for all four tasks (prose-only),
  identical scoring data, agent directive injection-safety, document/OCR, speech, KB lists unchanged.
  Updated: `test_conversation_language`, `test_wave4_language_api`, `test_wave4_practice_language`.
- Frontend `tests/russian-locale.test.tsx` (20: R1-R16 incl. "no silent English"), `brand-slogan-invariant`
  (24), em/en-dash guards over all Russian files, updated `i18n`, `wave1-foundation`, `prepare` tests.

## 20. W9.6A regression found and fixed in this wave

The full E2E run exposed `nextjs.spec` "prepare workspace is responsive": in W9.6A I had re-pointed the
mobile tab label to `nav.prepare`, silently changing the English "Preparation" -> "Prepare" (and edited the
unit test to match instead of preserving the copy). Fixed with a dedicated `prepare.contextTab` key
(English unchanged "Preparation"; per-locale values reuse each locale's existing `opportunity.prepStatus`
wording; Russian "Подготовка") and the unit test restored. The earlier marketing evaluator read-path break
from W9.6 (Trust copy moved into the catalogue) was likewise found and fixed (see §21).

## 21. Evidence (all 0 paid/live)

- Unit: **vitest 414 passed (63 files)**; typecheck, lint (0 warnings), `next build` green; scanner **0**.
- Backend: full suite **2,489 passed, 3 skipped (RAGAS guards), 0 failed** (run from repo root with the
  three `OPENROUTER_MODEL_*` vars pinned to registry defaults so the gitignored `.env` overrides cannot
  interfere); `ruff check .` clean; compileall clean.
- E2E (`E2E_PORT=3100`): **full Playwright 166/166**, including the new `russian-locale.spec.ts` (8: core
  journey over 10 routes, first-run, UI ru/conv en, UI en/conv ru, error + in-place retry, Help, content
  boundary, public /trust+/about) and `russian-speech.spec.ts` (3: no Listen/live voice for ru; en/de
  unchanged).
- Evaluators (17, all exit 0): i18n_l10n (21 invariants incl. 5 new), release_candidate, identity_platform,
  security, opportunity_journey, onboarding_personalisation, dictation_experience, voice_experience,
  realtime_voice, marketing_product_trust, company_intelligence, prepare_practice_integration,
  documents_evidence, knowledge_governance, workspace_security, platform_admin, multi_agent. Fixed
  stale read paths/contract counts in `eval_marketing_product_trust` (W9.6 breakage) and
  `eval_prepare_practice_integration` (8 locales, derived from `src/locales.py`).

## 22. Human / native / legal / live status

- Implementation completeness: **validated** (parity, rendering, independence, boundaries).
- **Native-speaker Russian language review: PENDING.** Translations are ENGINEERING translations.
- **Legal review of Russian legal/privacy/terms copy: PENDING.**
- **Live generated-Russian quality (Mo/Practice prose): PENDING live validation** (no model call made).
- The slogan stays English by brand design and is not a localization defect.

## 23. Known limitations

Russian has no speech (dictation/playback/live voice) support; no Russian occupation/ESCO layer; no
Russian labour market or salary data; Cyrillic renders in the system fallback font (Inter subset is
latin-only); plural forms for count strings are worded to avoid Russian few/many inflection rather than
implementing CLDR plural rules; page `metadata` titles remain English (architecture-bound, as in W9.6);
all catalogues are bundled into the client (+~77 kB first load).

## 24. W9.8 handoff (Privacy / Data Control UX)

Scope for W9.8 only (not started): a candidate-facing Privacy/Data control surface (what is stored, export,
delete, retention) reusing existing account-deletion/retention/export services; must ship with all 8
locales (add keys to `en.ts` + the 7 locale files + `ru-parts`, and fragment `ru` blocks), keep the
slogan invariant, and respect the scanner/eval guards. Russian legal/privacy copy still needs legal review
before any production reliance.

## 25. Confirmations

No migration · no geography change · no taxonomy change · no unsupported speech enablement · 0 paid/live
calls · no RC created · Pilot 2 not resumed · W9.8 not started · P10C not begun.
