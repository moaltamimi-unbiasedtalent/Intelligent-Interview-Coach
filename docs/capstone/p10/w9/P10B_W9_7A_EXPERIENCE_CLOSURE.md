# P10B-W9.7A — Localization, Visual UX & Runtime Closure

Bounded post-W9.7 closure driven by direct visual inspection of the running product plus W9.7 findings.
**No migration created or edited**, no new locale, no Russian speech, 0 paid/live calls, no RC, Pilot 2 not
resumed, W9.8 not started, P10C not begun.

## 1. Baseline

From W9.7 `feat/p10b-w9-7-russian-locale` @ `4ae9ff4` (ancestry intact: 4ae9ff4 ← a82081e ← 847215b ←
dc655ff ← 4483f32 ← 7fc600b ← c9cdff5 ← 5984953). New branch `fix/p10b-w9-7a-experience-closure`.
Alembic repo head `0014_opportunities` (unchanged). No RC-P10-003.

## 2. Visual findings from manual QA

1. Authenticated Home: four feature blocks still English under other interface languages.
2. A Mo/career answer showed `Evidence (from sources):`, `No sources were retrieved.`,
   `Tool results (calculated):`, `None provided.`, `Recommendation:` in English.
3. `I don't have enough reliable evidence to answer that confidently...` English.
4. The Home "Prepare for a specific job" card showed a blank rectangle where its action should be.
5. A recoverable error rendered as a large, dominant, catastrophic-looking card.
6. (W9.7 follow-up) Russian typography mismatch; local dev authenticated requests returning 500.

## 3. Home feature blocks: root cause

`app/app/page.tsx` (a server component) rendered the four blocks from a hardcoded **array of string tuples**
(`[["Prepare with evidence", "Grounded ..."], ...].map(([title, body]) => ...)`). It was never in the
catalogue, so it could not change with the interface language. **Why every guard missed it:** the W9.6/W9.6A
scanner inspected only (a) JSX text nodes `>text<`, (b) a fixed set of JSX attributes and (c) string values
under named object keys (`title:`, `q:`, ...). Strings inside an array literal are none of these, and in JSX
they appear as `{title}` expressions. The catalogue-parity tests only compare catalogues with each other, so
text that is not in a catalogue is invisible to them.

## 4. Response presentation: root cause and ownership

Audit result - the strings are **not** one thing:
- `Evidence (from sources):` / `Tool results (calculated):` / `Recommendation:` are written by the
  **model**, because the backend synthesis prompt (`src/copilot/rag/synthesis.py`) instructs it to use
  those exact English headings. `No sources were retrieved.` / `None provided.` are the model's own words
  for the prompt's `(none retrieved)` / empty blocks. They are **Mo prose** (model output + a response-
  template dictated by a prompt), **not** application-rendered chrome. So the premise "UI labels follow the
  interface language" does not apply to them; they belong to the **Mo conversation language**.
- The Career chat path (`/career/chat`, used by Prepare when the Agent Coach is off) had **no language
  handling at all**: it never received the conversation language, so Mo's answer and these headings were
  English regardless of the setting (the Agent path already had `response_language_directive`).
- The deterministic fallback summary used when the model is unavailable (`The assistant model is currently
  unavailable...`, `Tool results (calculated):`, `Retrieved N narrative passage(s)`, the insufficient-evidence
  sentence) is likewise deterministic Mo text, previously English-only.
- Genuine **UI chrome** found adjacent to the screenshot text (interface-owned): `Career evidence: n
  source(s)` (Career answer + Agent sources), the `source`/`Source` fallback label, the screen-reader
  `Sources: ...` list, `Question n of m`, and `Last updated: ... · Engineering draft` on legal pages. All were
  English literals inside JSX mixed with `{}` expressions (another scanner blind spot).

## 5. Insufficient-evidence note: language ownership (final)

The sentence is rendered by the frontend (`CareerAnswer.tsx`), but it is **first-person, inside Mo's reply
bubble, and stands in for Mo's own prose**. Final ownership: **Mo conversation language**, not the interface
language. The three response-template headings, the backend insufficient-evidence sentence and the
deterministic fallback follow the same dimension.

| Interface | Conversation | UI labels (sources summary, Source, SR list) | Mo-owned text (note, headings, fallback) |
|---|---|---|---|
| German | English | German | **English** |
| English | German | English | **German** |
| Russian | English | Russian | **English** |
| English | Russian | English | **Russian** |
| Russian | Russian | Russian | Russian |

Source titles, URLs, years, calculated values, the candidate's text and the model's answer are verbatim.
Proven deterministically (backend prompt/fallback tests, frontend matrix, real-browser E2E of the request body
and rendering). No model call.

## 6. Opportunity blank-control: root cause

`OpportunityEntry` rendered an `aria-hidden` pulsing placeholder (`h-10 w-48 bg-surface-2`, no text) whenever
`count === null`. `count` was set to `null` and **never resolved** whenever auth status was not
`"authenticated"` (`loading`, `unauthenticated`, or `unknown`). `AuthProvider` sets `unknown` when `/auth/me`
fails with anything but 401, and `RouteGuard` deliberately renders children in that state. So any backend
fault on `/auth/me` (e.g. the local dev DB schema lag) left the unlabeled blank rectangle on screen
permanently. It was a state-machine bug, not a colour/CSS bug (the button text colour, i18n key and styles were
all correct).

## 7. Error-state visual root cause

`ErrorState` had two tiers, and the default `page` tier was the large centred "catastrophic" card (`px-6
py-10 text-center`, large heading) used for every recoverable read failure. Measured with the same scenario
(History failing, request id present): **232px tall = 29% of viewport (desktop), 257px = 33% (390px)**.

## 8. Fixes implemented

- **Home:** `HomeFeatureBlocks` client component over catalogue keys `home.feat{1-4}{Title,Body}` (8
  locales).
- **Response/Mo ownership:** `conversation_language` (bounded `AppLocale`, optional) threaded
  `CareerChatRequest` (API + application layer) -> `CareerIntelligenceService.answer` ->
  `build_evidence_messages` / `build_synthesis_messages` / `_fallback_answer`. New bounded module
  `src/copilot/rag/localized.py` (headings, insufficient sentence, fallback strings, safe directive for all 8
  locales). **English/default is byte-identical** (asserted). The frontend sends the account conversation
  language only (never the interface locale or geography). `LANGUAGE_NAMES` is now the single copy in
  `src/locales.py` (prompts.py/policies.py derive from it).
- **UI chrome:** keys `practice.questionProgress`, `prepare.evidenceSourcesOne/Other/sourceUntitled/
  sourcesAria`, `marketing.lastUpdated`; Mo note key `coach.insufficientEvidence`. New catalogue fragment
  `w96/closure.ts` (15 keys × 8 locales).
- **Opportunity action:** bounded loading state machine (see §6): placeholder only while auth/list is
  genuinely pending, labelled (`role=status` + localized "loading"), capped at 4s; every settled state
  (auth failure, request failure, hang timeout) shows the safe default create action.
- **Error hierarchy:** `section` (compact, unchanged), `page` (default; proportional: left danger accent,
  small title, filled Retry, collapsed details) and `fatal` (the old large treatment, reserved for the new
  localized route error boundary `app/error.tsx`, which previously did not exist, so a render crash showed
  Next's default English screen). Result: **162px (20%) desktop / 182px (23%) mobile**, ~30% shorter. Retry is
  now a filled accent button with a visible focus ring; details stay collapsed; `<main id="main">` is now
  programmatically focusable and receives focus when a user-activated Retry succeeds (the button is disabled
  during the retry, which makes browsers drop focus to `<body>`, so the logic keys off "Retry was activated"
  rather than "button still focused").
- **Typography:** see §12.

## 9. Scanner changes

`frontend/scripts/scan-i18n.mjs` gained three structural passes + one decode step:
`array-literal` (arrays of >=2 string literals; only multi-word prose counts), `jsx-text-mixed` (text adjacent
to `{}` expressions, without re-matching pure text nodes), HTML-entity decoding (`&rsquo;` contains `;` and
used to trip the code-syntax filter and hide a whole sentence), and a precise TS-declaration exclusion
(`interface X`). Proof on the **previous** sources straight from git: old scanner = 0 offenders on
`app/app/page.tsx` and `CareerAnswer.tsx`; new scanner = **13** across 5 files. Regression tests (positive
and negative: identifier/route/enum/single-word arrays and key references are NOT flagged) and evaluator
invariants `scanner_structural_coverage` (mutation-tested) and `mo_prose_language_ownership`.
Final: **0 unexplained candidate-facing offenders.**

## 10. 8-locale runtime proof

`tests/home-localized.test.tsx` renders the **real** `app/app/page.tsx` in each of en/de/fr/es/it/pt/nl/ru
and asserts localized headings and descriptions, none of the 8 original English strings remaining (non-en), a
resolved, labelled CTA, no raw translation key (checked against every real catalogue key) and the slogan.
E2E repeats this in real Chromium (German, Russian, and all 8). Catalogue: **1,443 keys x 33 namespaces per
locale, identical in all 8** (W9.7's 1,428 + 15).

## 11. Protected slogan

`Ask More. Be More.` unchanged: single `BRAND_SLOGAN`, every locale's tagline is that constant, the scanner
approves only the exact string (new tests also cover it inside rendered arrays), and the Home E2E asserts it
visible and exact in all 8 locales. Nothing in W9.7A touched it.

## 12. Cyrillic font: decision and a correction to W9.7

- **Correction:** W9.7 stated that Inter was latin-only so Russian "fell back to the system font". That was
  wrong. `next/font` self-hosts **all** Inter subsets and emits `@font-face` rules with `unicode-range`; the
  `subsets` option only controls which files are **preloaded**. Measured with Chrome DevTools
  (`CSS.getPlatformFontsForNode`) on the W9.7 configuration: Russian text was already rendered in the **Inter
  webfont** (43 glyphs). What was real: the Cyrillic file was not preloaded, so it loaded late (swap).
- **Change:** `subsets: ["latin", "cyrillic"]` on the existing Inter loader (supported, same family, no manual
  font file). The Cyrillic file (`~18.7 kB` woff2) is now preloaded; measured: both Latin and Cyrillic preloaded.
- **Cost (honest):** `subsets` is static, so the Cyrillic preload happens on **every page for every locale**
  (+~18.7 kB). If that is undesirable, the alternative is dropping the extra preload and accepting a late swap
  for Russian users. Owner decision; JS bundle size is unaffected.
- **Enforced:** E2E asserts Inter/webfont for `h1`, `p` and the error heading on 7 Russian surfaces, no
  overflow, no clipped controls, tutorial card in bounds, at desktop and 390px.

## 13. Local DB migration-state finding

The dev DB is the code-default `sqlite:///data/interview_studio.db` (no `DATABASE_URL` anywhere; local single
file; git-ignored/untracked; no Postgres configured). `alembic_version` = `0006_user_feedback` vs repo head
`0014_opportunities`. **But the DB was not a clean 0006:** all later tables already existed (apparently created
by `create_all`) while 10 columns and 3 indexes added by migrations 0009/0011-0014 to pre-existing tables were
missing (`users.onboarding_completed_at/onboarding_step`, `user_preferences.*` x5, `user_feedback.category`,
`document_versions.failure_kind`, `interviews|interview_sessions.opportunity_id`). That is the real cause of
the 500s (`no such column: users.onboarding_completed_at`).

## 14. Local DB action taken

1. Provenance confirmed (above); `upgrade()` bodies of 0007-0014 verified additive by AST.
2. Backup: `data/backups/interview_studio.pre-w97a-0006.db` (git-ignored).
3. `alembic upgrade head` was attempted on the real file: it **failed** on 0007 (`duplicate column name:
   platform_role`) and changed nothing (file byte-identical to the backup, schema diff empty).
4. Instead, using **only the existing migration chain**: built a fresh head-schema DB with `alembic upgrade
   head` on an empty temp file, copied the data over (common columns only), applied 0013's own backfill intent
   (existing accounts treated as onboarded), verified `integrity_check = ok`, 0 FK violations, **row counts
   identical in all 25 tables** (users 3, interviews 42, reports 42, preparation_memories 5,
   interview_sessions 10, user_feedback 11, opportunities 2), then swapped it in.
5. Result: `alembic current` = `0014_opportunities (head)` = repo head. No migration created or edited.
6. Authenticated smoke (dev-header identity, DEV validation only): `/auth/me`, `/opportunities`, `/progress`,
   `/memory`, `/history/interviews` all 200; `PATCH /auth/preferences {interface_locale: ru}` 200 and
   persisted, `zz` 422; 0 schema errors in the server log.
7. Side effects, disclosed: my smoke created one dev-header user (id 4, provider `api`; the dev header now
   maps to the `api` provider, not the legacy `dev` provider that owns the older rows, unchanged behaviour).
   A full backend test run later wrote one fixture interview into this DB (a pre-existing test-isolation leak
   previously masked by the schema lag); I removed exactly that row and its report, restoring 42/42. The leak is
   filed as a separate task.

## 15. Visual theme QA / 16. Responsive QA

Real Chromium, light and dark (`iic-theme`), desktop 1280 and 390px: Opportunity action (Russian) text contrast
>= 4.5 and a non-`none` keyboard focus outline; error card Retry and body text contrast >= 4.5; skeleton
(`bg-surface-2`) uses existing tokens; no horizontal overflow; error card height bounded (<= 230px desktop,
<= 340px mobile, < 45% of the viewport); controls not clipped. Screenshots reviewed for both themes.
**Sweep finding (not changed):** about 15 classes of the form `token/NN` (e.g. `border-warning/50`,
`bg-warning/10`, `text-foreground/80`) generate **no CSS**, because the colour tokens are plain `var()` hex
values. This includes W9.4's nav-salience class. Fixing it would visibly change ~10 already-approved elements,
so it is reported and filed as a separate task, not folded into this closure; W9.7A code uses none of them.

## 17. Accessibility

Opportunity action: real `<a>` (accessible name = visible text, verified for all 8 locales), keyboard focus ring,
touch-size link, labelled `role=status` loading state. Error state: single `role=alert` (no stacking on retry),
Retry native button (Enter), `aria-busy` while retrying, Technical details is a native `<details>` collapsed by
default and opened with the keyboard in Chromium, request id inside it, no focus trap, focus handed to `<main>`
after a user-activated successful Retry. `<html lang>` still tracks the interface locale (incl. `ru`).

## 18. E2E evidence

New `e2e/experience-closure.spec.ts` (23 tests): Home de/ru + 8-locale; Opportunity (auth failure, hanging
request, light/dark × desktop/390px); Cyrillic font; the five-row language-ownership matrix; error card
(dark/light × desktop/390px, Russian, all 8 locales, section error); Russian surfaces visual QA. **Full
Playwright suite: 189/189 passed** (166 from W9.7 + 23 new).

## 19. Tests and evaluators

- Backend `tests/test_w97a_career_language.py` (29): coverage of all locales, English-prompt byte identity,
  localized headings/directive for 7 languages × 2 builders, injection safety, user-message data identical
  across languages, fallback (English byte-identical + 7 localized), application-layer plumbing, bounded API
  schema.
- Frontend: `home-localized` (9), `opportunity-entry-states` (7), `error-state` (25), `career-answer-language`
  (15), scanner regression additions, dash guard for the new fragment.
- Gates: typecheck, lint (0 warnings), `next build` green; **vitest 477 passed (67 files)**; scanner 0; `ruff`
  clean; **full backend 2,518 passed / 3 skipped (RAGAS guards) / 0 failed** (repo root, `OPENROUTER_MODEL_*`
  pinned to registry defaults).
- All 17 evaluators exit 0, `eval_i18n_l10n` now 23 invariants (2 new).

## 20. Known limitations

- The `Evidence (from sources):` headings are model output instructed by the prompt: they follow the
  conversation language only through prompt instruction (no live-model verification was made; deterministic
  prompt tests only). Live generated-language quality remains pending live validation.
- The dead `token/NN` Tailwind classes (§16) remain until the separate task lands.
- The Cyrillic preload is global (+~18.7 kB per page) (§12).
- Russian plural forms still avoid inflection; page `metadata` titles remain English (as in W9.6).
- Russian translations remain engineering translations (native + legal review pending).

## 21. W9.8 handoff (Privacy / Data Control UX), not started

Candidate-facing "what is stored / export / delete / retention" surface reusing existing account-deletion,
retention and export services; ships all 8 locales; keeps the slogan and scanner guards (the scanner now
catches arrays and mixed JSX text, so new surfaces cannot hide English in tuples); use the new
`ErrorState` tiers and bounded-loading pattern for any data-fetching region.

## 22. Confirmations

No migration created or edited · no new locale · no Russian speech enabled · 0 paid/live calls · no RC ·
Pilot 2 not resumed · W9.8 and P10C not started.
