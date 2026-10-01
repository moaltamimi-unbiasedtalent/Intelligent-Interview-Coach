# P10B-W9.6 — Full-App Localization Completion

Implementation record. Frontend localization + a backend locale-source consolidation (no behaviour
change). **No migration**, no new API, no RC, no Pilot 2, no P10C work, 0 paid/live calls. Russian
(W9.7) explicitly deferred.

- **Baseline:** branch `fix/p10b-w9-5-welcome-tutorial-v2` @ `dc655ff` (W9.5). New branch
  `fix/p10b-w9-6-full-localization` from it. Ancestry intact
  (dc655ff ← 4483f32 ← 7fc600b ← c9cdff5 ← 5984953 ← 334ffbd ← 80354f3). Alembic head
  `0014_opportunities` (unchanged). RC-P10-002 immutable; no RC-P10-003.

## 1. Pilot finding addressed

- **PF (localization):** switching the interface language left large parts of the product in English —
  Prepare/Mo, Practice/Interview, Opportunities/Documents/Company/Workspaces, Progress/Memory, the
  public legal/trust/marketing/help pages, and shared chrome (navigation, loading/error states, aria
  labels). The wave's promise: **changing the interface language changes every Ask4Mo-owned
  candidate-facing string across the product**, for all seven locales (en/de/fr/es/it/pt/nl).

## 2. What changed

### 2.1 Machine-checkable guard (the audit AND the gate)
- **`frontend/scripts/scan-i18n.mjs`** — a bounded, deterministic scanner over `components/` + `app/`
  `.tsx`. It flags visible JSX text nodes and a small set of candidate-facing attribute literals
  (`placeholder`/`aria-label`/`title`/`label`/`description`/`alt`), and ignores code tokens (TS
  generics, arrow fns, identifiers, inline-ternary/method-call expression fragments, URLs, ISO codes,
  symbols). Reviewer/admin surfaces are excluded (`/review/`, `/admin/`, `components/i18n/`, tests).
  One explicit file-level exception with a reason:
  - `components/agent/AgentInspector.tsx` — reviewer/diagnostic, rendered only on the platform-admin
    Review surface (W9.3); English-ops per the i18n standard.
- **`frontend/tests/no-hardcoded-english.test.ts`** — a vitest guard that execs the scanner and
  asserts **zero** offenders.
- **`scripts/eval_i18n_l10n.py`** — new invariant `no_hardcoded_candidate_english` that shells the
  scanner (`node scripts/scan-i18n.mjs --count`, cwd = frontend) and soft-passes only if node is
  absent in the eval environment.

Final scanner result: **0 candidate-facing hardcoded-English offenders** in 0 files.

### 2.2 Translation content (per-domain fragments, merged centrally)
New keys were authored as five per-domain fragments under `frontend/lib/i18n/messages/w96/`, each
with identical keys across all seven locales (compile-time enforced in each fragment, re-verified by
`tests/i18n.test.tsx`):

| Fragment | Surfaces | New keys / locale |
| --- | --- | --- |
| `prepare.ts` | Prepare / Mo / Agent / Coach | 207 |
| `practice.ts` | Practice / Interview / History / Feedback | 96 |
| `surfaces.ts` | Opportunity / Documents / Company / Workspaces | 9 |
| `legal.ts` | Privacy / Terms / AI-transparency / About / Help / Marketing / Trust | 134 |
| `shell.ts` | Progress / Memory / Home / common / states / nav | 81 |
| **Total** | | **527 keys × 7 locales = 3,689 strings** |

- **`frontend/lib/i18n/messages/w96/index.ts`** aggregates the five fragments into one per-locale
  `w96` object (deep-merged, English fallback per fragment) and exports `mergeW96Into()`.
- **`frontend/lib/i18n/catalog.ts`** deep-merges `w96[locale]` onto each base locale catalogue in
  `CATALOGS` (additive — only adds namespaces/keys the base does not define), and the `translate`
  English fallback now reads the **merged** English catalogue so W9.6 namespaces resolve in the
  fallback path too.

### 2.3 Component localization (~70 files + 5 new client content components)
Every candidate-facing string across the five domains now renders via `useT()`/`translate()`. Server
pages whose body was hardcoded English were split into `"use client"` content components so they can
use the hook: `PrivacyContent`, `TermsContent`, `AiTransparencyContent`, `AboutContent`,
`HelpPageContent`. Shared chrome was localized at the source so it localizes everywhere at once:
`LoadingState`/`ErrorState` default labels, nav aria-labels, `Logo` aria, `Skip to content`, the four
`Suspense` fallbacks in `app/{prepare,sign-in,reset-password,verify-email}/page.tsx` (now use the
localized `LoadingState` default).

### 2.4 Shared fallback stability fix (`components/i18n/I18nProvider.tsx`)
`useI18n()`'s provider-less fallback previously returned a **fresh object (new `t`) every render**.
Consumers use `t` as a `useCallback`/`useEffect` dependency (correctly, per `exhaustive-deps`), so an
unstable `t` made those callbacks change identity each render and re-fire their effects — e.g. a
data-load effect refetching and clobbering optimistic state (surfaced by the MemoryManager unit
tests). The fallback is now memoised once, identity-stable. With a provider, `t` was already stable
(the context value is memoised on `[locale, setLocale]`). The three consumers that referenced `t`
without listing it (`FeedbackControl`, `HistoryDetailClient`, `InterviewReport`) now list it — safe
and warning-free now that `t` is stable.

### 2.5 Backend canonical locale source (consolidation, no behaviour change)
- **`src/locales.py`** (new) — single source of truth: `SUPPORTED_LOCALE_CODES` (7 codes) and
  `AppLocale` (`Literal[...]`). Docstring marks it as the W9.7 insertion point for `"ru"`, and notes
  the deliberately-separate speech/taxonomy/geography lists.
- **`src/persistence.py`** re-exports `SUPPORTED_LOCALES` from it; the Pydantic allowlists in
  `src/api/schemas/{auth,interview,agent,documents}.py` now use `AppLocale` instead of inline
  `Literal["en",...]`. One place to change for W9.7; no runtime behaviour change.

## 3. Invariants preserved

- **Four independent dimensions stay separate:** interface locale ≠ Mo conversation language ≠
  dictation language ≠ labour-market geography. A language choice never changes geography. Proven by
  `eval_i18n_l10n` (`conversation_locale_separation`, `dictation_locale_separation`,
  `language_geography_separation`) and E2E E3.
- **User/source content is never translated:** candidate answers, CV/JD text, Mo/model-generated
  evaluation & report prose (which follows `conversation_language`), source citations, company/role
  names, provider names and technical IDs are rendered verbatim. Proven by E2E "user/source content
  is never translated".
- **Server/client boundary:** page `metadata` titles remain object-literal exports (not scanner-
  flagged, cannot use `t()` from a server component) and are documented as a deferred, architecture-
  bound item (see §5).
- **No new raw-model path, no new endpoint, no migration, no RC.**

## 4. Gates (all green; 0 paid, 0 live)

- Frontend: `npm run typecheck` ✓ · `npm run lint` ✓ (0 warnings) · `npm run build` ✓ ·
  `npm test` **343 passed** (60 files, incl. i18n parity + hardcoded-English guard) ·
  `node scripts/scan-i18n.mjs` **0 offenders**.
- E2E (`E2E_PORT=3100`): new `e2e/localization.spec.ts` **11 passed** (E1 German core journey;
  E2/E4 seven-locale public `/trust`; E3 interface≠conversation independence; E5 non-English error
  chrome; user/source-content boundary). Regression check over 10 likely-affected specs
  (i18n, progress, opportunities, settings-memory, service-recovery, service-resilience,
  welcome-tutorial, onboarding, navigation, marketing) **50 passed**.
- Evaluators (deterministic): `eval_i18n_l10n` PASS (incl. new scanner invariant) ·
  `eval_release_candidate` PASS (27) · `eval_security` PASS (all attacks detected, 0 FP) ·
  `eval_identity_platform` PASS (1.0) · `eval_opportunity_journey` PASS ·
  `eval_onboarding_personalisation` PASS · `eval_dictation_experience` PASS ·
  `eval_voice_experience` PASS.
- Backend: `ruff check src/` ✓ · locale-source imports resolve · targeted suite
  (`test_wave4_language_api`, `test_conversation_language`, `test_documents_pipeline`, `test_api`,
  `test_auth_api`) passes (0 failures).

## 5. Limitations & deferred (truthful)

- **Legal/privacy/terms/AI-transparency translations are engineering drafts.** Meaning is preserved
  (no claim added, strengthened or weakened), diacritics correct, no em dash — but **human/legal
  review is pending** before these are treated as authoritative localized legal copy.
- **Page `metadata` titles** (server-component `export const metadata`) remain English. Localizing
  them needs a request-locale-aware `generateMetadata` path and is deferred as architecture-bound
  (not a candidate-facing rendered string; not scanner-flagged).
- **Help article bodies** (`HelpCenter.tsx` `SECTIONS`, ~130 Q/A strings) remain the pre-existing
  documented localization backlog; all actual scanner offenders in that file were localized. Pre-
  existing em dashes there are outside this wave's no-em-dash customer-file scope.
- Live/human translation-quality validation is UNVALIDATED (deterministic parity + rendering only).

## 6. W9.7 (Russian) insertion points — do NOT action now

- `src/locales.py`: add `"ru"` to `SUPPORTED_LOCALE_CODES` and `AppLocale` (one place; backend done).
- `frontend/lib/i18n/locales.ts`: add the `ru` entry to `APP_LOCALES`.
- Add `frontend/lib/i18n/messages/ru.ts` (base catalogue) and a `ru` block to each
  `frontend/lib/i18n/messages/w96/*.ts` fragment (parity enforced by `tests/i18n.test.tsx`).
- Keep speech (`ttsLocales`/`DICTATION_LANGUAGES`), taxonomy and geography lists separate — do not
  add `ru` to them as part of interface localization.
