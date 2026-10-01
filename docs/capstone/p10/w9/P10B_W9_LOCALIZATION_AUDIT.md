# P10B-W9 — Localization Audit (Full-app L10n + Russian 8th locale)

Audit phase. No runtime code changed. Findings #6 (completeness) and #7 (add `ru`).

> **Update (W9.6 DELIVERED):** Finding #6 (full-app completeness) is closed on branch
> `fix/p10b-w9-6-full-localization` (see `P10B_W9_6_FULL_LOCALIZATION.md`). The ≈190 audited hardcoded
> strings — and more found by the scanner — are now localized; **527 new keys × 7 locales** added as
> five fragments merged in `catalog.ts`; a deterministic scanner + vitest guard + `eval_i18n_l10n`
> invariant keep candidate-facing hardcoded English at **0**. Backend locale allowlists consolidated to
> `src/locales.py` (§7.3). Finding #7 (`ru`) is **W9.7, NOT started** — insertion points documented.
> Deferred: page `metadata` titles, Help article bodies; legal-copy drafts await human/legal review.

**Requirement:** changing the interface language must change EVERY Ask4Mo-owned candidate-facing
string. Do NOT translate user content, CV/JD text, employer material, evidence quotations, or official
source names (provenance).

---

## 1. i18n architecture & the single sources of truth

- **Supported-locale list (type-level SoT):** `frontend/lib/i18n/locales.ts:17-25` — `APP_LOCALES`
  (drives `AppLocale`, `SUPPORTED_LOCALE_CODES`, `DEFAULT_APP_LOCALE`, `toSupportedLocale`, labels).
- **Catalogue registry:** `frontend/lib/i18n/catalog.ts:11-19` — hard-codes the seven
  `messages/{code}` imports and the `CATALOGS` record (NOT derived from `APP_LOCALES`), so `ru` needs a
  manual import + record entry + a new `messages/ru.ts`.
- **Resolution:** account `interface_locale` → cookie → browser → English (`I18nProvider.tsx:44-58`);
  `translate()` falls back to English then the key (`catalog.ts:39`).

### Catalogue coverage — IN SYNC (guarded)
All seven catalogues are identical in shape: **688 keys, 24 namespaces each**. Enforced by the
`Catalog` TypeScript type (compile-time) AND `frontend/tests/i18n.test.tsx:21-36` (runtime key-parity +
no-blank-values). A future `ru.ts` missing any key fails typecheck and this test — catalogue drift is
already covered. (`eval_release_candidate`'s `seven_locale_namespace_parity` also asserts the 24
namespaces.)

## 2. Hardcoded candidate-facing English — the real gap (finding #6)

Localization is architecturally complete but **coverage is not**: ~42 candidate-facing components and
most `app/*` pages render English literals outside `useT()`/`translate()`. **≈190 distinct
candidate-facing strings.** (Reviewer/diagnostic surfaces `/review/*`, `/admin` are intentionally
English-exempt per the i18n standard.)

| Surface | ~count | Evidence (file:line) |
|---|---|---|
| Prepare / Mo chrome (`components/agent/*`) | ~50 | `AgentConversation.tsx:88`; `JourneyChrome.tsx:15-17,64-67`; `PendingHumanActionCard.tsx:44,193`; `AgentContextRail.tsx`, `usage.tsx`, `AgentComposer.tsx`, `AgentAnswer.tsx`, `AgentSources.tsx` |
| Interview / Practice / History (`components/interview/*`) | ~45 | `InterviewEvaluation.tsx:10,25-35`; `DeepDivePanel.tsx`; `InterviewReport.tsx`; `ReportView.tsx`; `HistoryClient.tsx`; `InterviewAnswerComposer.tsx` |
| Progress (`components/progress/*`) | ~23 | `ProgressClient.tsx:16,25-28,78-108`; `PracticeProgress.tsx:46-53` |
| Legal / Trust pages | ~40 | `app/privacy/page.tsx:23-28,…`; `app/terms/page.tsx:20-30`; `app/ai-transparency/page.tsx`; `app/about/page.tsx`; `components/marketing/TrustContent.tsx:11-29` |
| Authenticated Home cards | 8 | `app/app/page.tsx:21-26` (feature cards) |
| **API error messages** | 7 | `frontend/lib/api/errors.ts:41-51,74` (`ApiError.userMessage`) — candidate-facing, bypass i18n entirely |
| Empty/error/loading defaults | 3+ (high blast radius) | `components/ui/States.tsx` |
| Coach composer | 3 | `components/coach/CoachComposer.tsx` |
| Page metadata titles/descriptions | ~30 | `app/*/page.tsx` `export const metadata` (e.g. `app/app/page.tsx:5`) |

Well-localized already (for contrast): Settings, Auth forms, Opportunities, Company, Documents,
Marketing `*Content`, navigation/menus, voice controls.

## 3. Backend locale awareness

Production files that must become 8-locale aware for `ru` (and today hard-code the 7-tuple):

| File:line | What |
|---|---|
| `src/persistence.py:110` | `SUPPORTED_LOCALES` (used by `auth_repository.py:411,417`, `documents_service.py:60,82`) |
| `src/api/schemas/auth.py:101` | `interface_locale: Literal[…]` |
| `src/api/schemas/auth.py:102` | `conversation_language: Literal[…]` |
| `src/api/schemas/interview.py:18` | `ConversationLanguage = Literal[…]` |
| `src/api/schemas/documents.py:16` | `Locale = Literal[…]` |
| `src/api/schemas/agent.py:30` | `conversation_language: Literal[…]` |
| `src/agent/policies.py:97-105` | `RESPONSE_LANGUAGE_NAMES` (Mo prose directive) |
| `src/prompts.py:204-207` | `_CONVERSATION_LANGUAGE_NAMES` (Practice generation directive) |
| `src/voice/realtime.py:53` | `SUPPORTED_REALTIME_LOCALES` (`voice.py:79` derives) |
| `src/documents/ocr.py:31` | `TESSERACT_LANGS` (add `"ru":"rus"` + Tesseract `rus` pack in `deploy/Dockerfile.api`) |
| `src/copilot/knowledge/governance.py:31` | `SUPPORTED_LANGUAGES` — **ESCO caveat below** |

The language directives are allow-list-only (unknown code → no directive), so adding `"ru":"Russian"`
is the only change needed for Mo prose + Practice generation to speak Russian safely.

**Do NOT add `ru` to:** `src/persistence.py:120` `CAREER_GEOGRAPHIES` or `src/api/schemas/auth.py:104`
`CareerGeography` (labour-market geography, decoupled from language). `src/coaching_style.py` needs no
change (tone directives are language-independent).

## 4. Russian 8th-locale impact map (finding #7)

Full footprint to make the product 8-locale aware:
- **Core i18n (3):** `locales.ts:17-25` (+`ru` object), `catalog.ts:11-19` (import + record), **new
  `frontend/lib/i18n/messages/ru.ts`** (688 keys / 24 namespaces, typed `Catalog`).
- **Frontend speech allowlists (2):** `frontend/lib/speech/ttsLocales.ts:12,15-25` (`ru:"ru-RU"`),
  `frontend/components/ui/DictationControl.tsx:45-52` (`{code:"ru-RU"}`).
- **Backend production (8):** the table in §3.
- **Eval scripts (~15, CI gates):** `eval_i18n_l10n.py:22`, `eval_realtime_voice.py:203`,
  `eval_prepare_practice_integration.py:44`, `eval_onboarding_personalisation.py:130`,
  `eval_voice_experience.py:62`, `eval_dictation_experience.py:116`, `eval_documents_evidence.py:65`,
  `eval_opportunity_journey.py:203`, `eval_company_intelligence.py:178`,
  `eval_marketing_product_trust.py:26`, and `eval_release_candidate` (namespace parity).
- **Backend tests (~8):** `tests/test_realtime_voice.py:134`, `test_wave4_language_api.py:71`,
  `test_conversation_language.py:28`, `test_wave4_practice_language.py:16`,
  `test_documents_pipeline.py:210`.
- **Frontend tests (3):** `tests/i18n.test.tsx:18`, `voice-output.test.tsx:43`, `no-emdash.test.ts:12`.
- **Docker:** Tesseract `rus` language pack in `deploy/Dockerfile.api`.

**ESCO / taxonomy caveat (must be honoured):** `governance.py:31` `SUPPORTED_LANGUAGES` feeds the
governance coverage matrix and the "UI support ≠ KB content coverage" boundary (`governance.py:297`).
Adding `ru` as a UI language must NOT be represented as ESCO/occupation-taxonomy Russian coverage. Any
Ask4Mo-generated Russian occupation term is a UI rendering, not an official taxonomy translation, and
the coverage matrix must keep reporting Russian KB content as absent/unvalidated. The canonical layer
already supports this via `ConfidenceBasis.CURATED_MANUAL` + `ASK4MO_CURATED_SOURCE` (see
P10C_HANDOFF_IMPACT §4).

## 5. Voice / TTS / STT locale readiness

- **TTS** (`frontend/lib/speech/ttsLocales.ts`): no Russian entry. Pattern to follow: add `ru:"ru-RU"`;
  the honest per-language status (`ttsLanguageStatus`, `:42-51`) would report `configured:true`,
  `browserPlatformAvailable:"depends"`, `deterministicallyTested:true`, `liveHumanQualityTested:false`.
  `toSpeechLocale` safe-falls-back to `en-US`.
- **Dictation/STT** (`components/ui/DictationControl.tsx:45-52`): add `ru-RU`; `useDictationLanguage`
  derives its allowed set automatically.
- **Realtime** (`src/voice/realtime.py:53`): experimental/deferred; coerces unknown → `en` at `:136`.

## 6. Separation of the four dimensions — CONFIRMED independent

Interface language (`interface_locale`, `I18nProvider`), Mo conversation language
(`conversation_language` → `RESPONSE_LANGUAGE_NAMES`/`response_language_directive`, prose-only,
`policies.py:123-124`), Practice/interview language (`InterviewConfiguration.conversation_language` →
`prompts._language_directive`, prose-only), dictation language (BCP-47, device-local
`useDictationLanguage`), and labour-market geography (`career_geography`, derived from query keywords
via `detect_country`, never from language). `eval_i18n_l10n` asserts geography = f(query) and language
never changes it. **No coupling found.** Russian must preserve this: adding `ru` to language lists must
not touch geography lists.

## 7. Machine-checkable guard strategy (finding #6 "prevent future hardcoded English")

**Exists today:** key-parity + no-blank test (`i18n.test.tsx:21-36`); `Catalog` type; locale-list
assertions (`i18n.test.tsx:18`, `voice-output.test.tsx:43`); a copy-quality scan precedent
(`no-emdash.test.ts` scans catalogues + a `CUSTOMER_FILES` list). **Missing:** nothing scans JSX for
untranslated literal text — which is why the §2 gap went undetected.

**Recommended (three layers):**
1. **Keep** the key-parity test; extend it to assert `Object.keys(CATALOGS) === SUPPORTED_LOCALE_CODES`
   and that `SUPPORTED_LOCALE_CODES`, `SUPPORTED_TTS_LOCALES`, `DICTATION_LANGUAGES` stay consistent
   supersets (the frontend allowlists can't silently diverge).
2. **Add an AST/lint scan** for candidate-facing JSX literal text outside `translate()`/`t()`:
   `eslint-plugin-i18next/no-literal-string` (or `react/jsx-no-literals`) scoped to
   `components/**` + `app/**`, excluding `components/**/{admin,review}` and `app/{admin,review}/**`,
   with a symbol/whitespace allowlist. Complement with a deterministic `no-emdash`-style test that
   greps the candidate-facing file list for `>[A-Z]…<` JSX text and `(aria-label|placeholder|title)="[A-Z]…"`
   and fails on new occurrences (seed with the current §2 offenders as a burn-down baseline).
   **Move the six `lib/api/errors.ts` `userMessage` strings into an `errors` i18n namespace.**
3. **Backend guard:** define the locale set ONCE (e.g. in `persistence.py`) and derive the Pydantic
   Literals, `RESPONSE_LANGUAGE_NAMES`, `_CONVERSATION_LANGUAGE_NAMES`, `SUPPORTED_REALTIME_LOCALES`,
   `TESSERACT_LANGS` from it, with a pytest asserting they share one canonical set — so `ru` becomes a
   one-line change server-side instead of eight, and drift is impossible.

## 8. Summary answers

- **(a)** ≈190 hardcoded candidate-facing strings — Prepare/Mo ~50, Interview/History ~45, Progress
  ~23, legal/trust ~40, home 8, API errors 7, states 3+, ~30 metadata titles (§2).
- **(b)** `ru` footprint: 3 core i18n (+new `ru.ts`), 2 speech allowlists, 8 backend prod files,
  ~15 evals, ~8 backend tests, 3 frontend tests, Docker `rus` pack (§4). Do NOT touch geography lists
  or `coaching_style`.
- **(c)** Guard: keep key-parity, add scoped `no-literal-string` lint + `no-emdash`-style scan,
  localize `errors.ts`, collapse backend locale lists to one canonical source with a consistency test
  (§7).
