# P10B-W9 — Implementation Plan

Audit phase. **No runtime code changed by this task.** This is the proposed, wave-structured plan for
P10B-W9. Nothing here is implemented yet; each wave has an explicit STOP condition and awaits approval.

**Status (main d6c3493):** W9.1-W9.7, W9.7A and W9.7B (CI onboarding-gate fix: verified redirects) are DELIVERED and merged (PR #101 chain). Remaining: W9.8-W9.13. Forward roadmap: `../../capstone_phase_plan.md`. Note: the "do not auto-merge" wording below is historical; the current rule is the Completed Wave Integration Rule (PR, CI green, merge, sync local main).

**Global constraints (every wave):** RC-P10-002 immutable; 0 paid/live provider calls unless
explicitly authorised; never print/log/commit the OpenRouter key; do not weaken tests, security,
provenance, HITL, scoring semantics or ownership; keep interface language independent of
conversation/dictation/geography; do not change authority-level semantics; commit trailer
`Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`. Each wave: branch from the prior wave tip
(or main), PR, do not auto-merge, deterministic gates green before the next wave.

**Complexity key:** S (≤~1 day) · M (2–3 days) · L (multi-day).

---

## W9.1 — Service resilience & truthful error handling  *(P1, blocks Pilot 2)* — ✅ DELIVERED

> **Status: DELIVERED** on branch `fix/p10b-w9-1-service-resilience`. All W9.1 acceptance gates pass
> (see `P10B_W9_1_SERVICE_RESILIENCE.md`). CORS + `X-Request-Id` now reach every response including
> the catch-all 500; frontend distinguishes offline vs unreachable vs server; bounded GET-only
> retry with Retry-After; staging + production fail closed. No RC created. No migration. 0 paid/live
> calls. W9.2 not started.


- **Objective:** a server 500 or backend outage never tells the user their internet is the problem, and
  every error is honestly classified with a reference id.
- **Scope:** CORS/exception layering; frontend error taxonomy; bounded retry. Fixes PF-01, PF-02,
  PF-06, PF-07, PF-08 (and closes the residual class behind PF-20).
- **Backend:** ensure CORS + `X-Request-Id` on **every** response including the `ServerErrorMiddleware`
  500 (add CORS outermost, or a 500-formatting layer inside CORS, or post-process the base-`Exception`
  response). Make CORS unconditional-with-safe-default and **fail-fast in production** if
  `FRONTEND_ORIGINS` unset. Files: `src/api/main.py:106-118`, `src/api/exception_handlers.py:115-133`,
  `src/api/middleware.py`.
- **Frontend:** split `network` → `offline` (`navigator.onLine===false`) vs `unreachable`; distinct
  messages for 401/403/404/429; honour `Retry-After`; bounded retry (idempotent GET + `Idempotency-Key`
  POST; 2–3 attempts; backoff+jitter; never 4xx). Files: `frontend/lib/api/errors.ts`,
  `frontend/lib/api/client.ts`, `frontend/components/ui/States.tsx`. (Localization of these strings is
  owned by W9.6 but add the keys here.)
- **Schema/migration:** none.
- **Security/privacy:** no new data exposure; keep 500 body generic; reference id is a random request id
  only.
- **Tests:** backend test asserting an allowed-origin 500 carries `Access-Control-Allow-Origin` +
  `X-Request-Id`; frontend unit tests for the new taxonomy + retry (max attempts, no-retry-on-4xx).
- **E2E:** Playwright: kill/restart API, assert Progress/History show an honest "reaching Ask4Mo"
  (not "check your connection") and recover.
- **Evaluators:** extend/keep `eval_restart_recovery`; add an error-taxonomy assertion.
- **Acceptance:** backend outage never blames the user's internet; unhandled 500 classified `server`
  with a reference id; retry bounded and safe.
- **Dependencies:** none. **Risk:** middleware reordering could affect header behaviour — covered by the
  new header test. **Complexity:** M.
- **STOP:** after deterministic gates green + the header/taxonomy tests pass; do not proceed to W9.2
  until reviewed.

## W9.2 — Progress/History recovery & degraded states  *(P2)* — ✅ DELIVERED

> **Status: DELIVERED** on branch `fix/p10b-w9-2-recovery-ux` (see `P10B_W9_2_RECOVERY_UX.md`).
> Progress redesigned into two independent, coherently-degrading regions (one page-level error when
> both fail — never the Pilot's duplicate pattern); History + 5 other candidate read surfaces gained
> race-safe in-place Retry (3→10 retry-capable); `ErrorState` gained a compact `section` variant +
> `retrying`. Recovery works with no reload/re-login. Frontend vitest 320, full E2E 125, build green;
> no backend/schema change; no RC; 0 paid/live. W9.3 not started.


- **Objective:** no duplicate catastrophic errors; every error state recovers in place; partial content
  stays usable. Fixes PF-03, PF-04, PF-05.
- **Frontend:** wire `onRetry` to `useCallback` refetch across the 11 unwired `ErrorState` usages
  (refactor inline `useEffect` fetches to reusable `load()`); render page regions independently;
  collapse Progress's two error UIs to one page-level banner. Files:
  `frontend/components/progress/{ProgressClient,PracticeProgress}.tsx`,
  `frontend/components/interview/{HistoryClient,HistoryDetailClient,InterviewReport,PracticeClient}.tsx`,
  `frontend/components/{memory/MemoryManager,preparation/SourcesClient,review/*,agent/*}.tsx`.
- **Backend/schema:** none. **Security:** none.
- **Tests:** unit tests asserting Progress renders one error banner (not two) and that Retry re-invokes
  the fetch. **E2E:** restart-recovery spec asserts in-place Retry restores Progress + History **without
  reload or re-login**.
- **Acceptance:** Progress/History recover after backend restart; no duplicate messaging; degraded
  content usable.
- **Dependencies:** W9.1 (taxonomy). **Risk:** low. **Complexity:** M.
- **STOP:** after the restart-recovery E2E passes.

## W9.3 — Security/menu investigation & remediation  *(Low, but before Pilot 2)* — ✅ DELIVERED

> **Status: DELIVERED** on branch `fix/p10b-w9-3-security-menu` (see `P10B_W9_3_SECURITY_MENU.md`).
> Internal Review & Diagnostics is now platform-admin-only: the nav item moved to an admin-only
> `INTERNAL_NAV`, `/review` + `/review/rag` + `/review/evaluation` are guarded (safe "Access denied"),
> and `GET /knowledge/diagnostics` + all `/evaluation/*` now require `require_platform_admin`
> (server-authoritative). `/review/agent` stays candidate owner-scoped; `knowledge/sources`+`/snapshot`
> stay candidate-facing; admin does not bypass owner-scoping. New backend authz test (7) + frontend
> nav-security (6) + E2E; all security/admin/workspace/identity/multi-agent/RC evals PASS. No
> migration, no new role, no RC, 0 paid/live. W9.4 not started.


- **Objective:** remove the dev/reviewer surface from candidate view; keep server-side authz intact.
  Fixes PF-09.
- **Frontend:** gate the `/review` `SECONDARY_NAV` entry + `/review/rag` + `/review/evaluation` pages
  behind `platform_role`/reviewer capability (mirror the Admin item). Files:
  `frontend/components/layout/{nav-items.ts,MoreMenu.tsx}`, `frontend/app/review/*`.
- **Backend:** add auth (`get_current_user_id` + role/capability) to `routes/knowledge.py:56-59`
  (diagnostics) and `routes/evaluation.py:20-31` (latest) — or a reviewer capability gate. Confirm no
  other consumer depends on them unauthenticated.
- **Schema:** none. **Security:** this IS the security wave — do not relax any existing gate.
- **Tests:** normal user neither sees `/review` menu item nor loads those endpoints (401/403). **E2E:**
  no privileged nav item renders for a BASIC user.
- **Acceptance:** security concern conclusively classified (route-visibility, done in SECURITY_AUDIT)
  AND fixed; no unauthorized menu/API access.
- **Dependencies:** none. **Risk:** low. **Complexity:** S.
- **STOP:** after the authz tests + E2E pass.

## W9.4 — Opportunity discoverability  *(P1, before Pilot 2)* — ✅ DELIVERED

> **Status: DELIVERED** on branch `fix/p10b-w9-4-opportunity-discoverability` (see
> `P10B_W9_4_OPPORTUNITY_DISCOVERABILITY.md`). New Home `OpportunityEntry` card (concept + adaptive
> Create/View CTA, `data-tour="opportunity-entry"`) placed before the Prepare composer; `?create=1`
> deep-links into the existing inline create flow (no second implementation); ReturnJourney gains a
> "Your opportunities" chip; desktop+mobile nav salience improved (legible default, mobile full
> accessible name, no ambiguous truncation). Opportunity→Prepare governed context verified. New copy
> localized across 7 locales. Frontend-only: vitest 336, full Playwright 129/0-fail, build green; no
> backend/schema/migration; opportunity/security/identity/i18n/RC/marketing evals PASS; 0 paid/live;
> no RC. The Home→Prepare flake is a pre-existing unrelated `nextjs.spec` timing flake (35/35 in
> isolation). W9.5 not started.


- **Objective:** a first-time user finds/creates an Opportunity without moderator help. Fixes PF-10.
- **Frontend:** Opportunity-first CTA on `/app`; add `/opportunities` to `ReturnJourney`; salience for
  the nav item (darker default + icon). Files: `frontend/app/app/page.tsx`,
  `frontend/components/coach/HomeEntry.tsx`, `frontend/components/home/ReturnJourney.tsx`,
  `frontend/components/layout/{PrimaryNavigation,MobileNavigation}.tsx`.
- **Backend/schema:** none. **Security:** none (owner-scoped already).
- **Tests:** unit test the `/app` Opportunity CTA renders and routes to create. **E2E:** Home →
  Opportunity → Prepare reachable without instruction.
- **Evaluators:** `eval_opportunity_journey` stays green.
- **Acceptance:** Opportunity discoverable without moderator instruction.
- **Dependencies:** none (but pairs with W9.5). **Risk:** low. **Complexity:** M.
- **STOP:** after the discoverability E2E passes.

## W9.5 — Welcome + Tutorial v2  *(P1/P2, before Pilot 2)* — ✅ DELIVERED

> **Status: DELIVERED** on branch `fix/p10b-w9-5-welcome-tutorial-v2` (see
> `P10B_W9_5_WELCOME_TUTORIAL_V2.md`). Onboarding completion now renders an intentional Welcome (Mo is
> ready + concept + Create-opportunity / Take-tour / Go-to-workspace, none mandatory) instead of
> dumping into `/app`. Tutorial v2: 9-step Opportunity-centred journey (Opportunity before
> Prepare/Practice), **0 dead targets** (v1 had 4), localized chrome + steps across 7 locales, and
> **account-scoped** state (`ask4mo.tutorial:<user_id>`) closing the shared-browser leak. **No
> migration** (typed-column prefs can't hold it without one; account-scoped localStorage used per the
> non-negotiable rule). vitest 342, full Playwright 132 (131 pass + 1 unrelated batch flake, isolated-green), build green; onboarding/opportunity/
> identity/security/i18n/RC evals PASS; 0 paid/live; no RC. W9.6 now DELIVERED (see below).


- **Objective:** an intentional post-onboarding handoff and an Opportunity-centred, localized,
  account-scoped tour. Fixes PF-11, PF-12.
- **Frontend:** render the completion screen using existing `onboarding.completeTitle/completeBody`;
  route `finish()` there; rewrite `tutorial/steps.ts` to the target journey + real `data-tour` anchors;
  move tour state to the account (reuse `PATCH /auth/preferences`); localize steps + controller chrome.
  Files: `frontend/components/onboarding/OnboardingClient.tsx`, `frontend/components/tutorial/*`,
  `frontend/lib/tutorial/*`, `frontend/lib/i18n/messages/*` (new `tutorial` namespace).
- **Backend:** add `tutorial_completed_at`/`tutorial_version` to preferences (reuse the
  `user_preferences` seam). **Schema/migration:** a small additive column if preferences aren't JSON —
  verify against `0013`/`user_preferences` shape before deciding (prefer no migration if JSON-backed).
- **Security:** none. **Tests:** completion screen renders + routes to create-Opportunity; tour state
  round-trips via preferences; tour steps localized (key-parity). **E2E:** onboarding → completion →
  first-Opportunity; tour has an Opportunity step; no step highlights a missing target.
- **Evaluators:** `eval_onboarding_personalisation` stays green.
- **Acceptance:** onboarding has a clear intentional handoff; tutorial contains Opportunity.
- **Dependencies:** W9.4. **Risk:** medium (tour DOM anchors). **Complexity:** L.
- **STOP:** after onboarding + tour E2E pass.

## W9.6 — Full-app localization completion  *(P1, before Pilot 2)* — ✅ DELIVERED (incl. W9.6A closure)

> **Closure (W9.6A):** W9.6 was conditionally delivered but a gate inconsistency was found — the Help
> Center article bodies (a TS object literal) were still English and the JSX-only scanner did not detect
> them. Closed on branch `fix/p10b-w9-6a-help-localization-closure` (see
> `P10B_W9_6A_LOCALIZATION_CLOSURE.md`): Help Center (12 sections / 66 articles = 144 strings) localized
> across 7 locales as a sixth `help` fragment; scanner extended with an object-literal content pass +
> regression test; a Prepare tab label and the dictation language option labels (now native-name
> endonyms) localized. Gates: typecheck/lint(0)/build green; vitest **350** (61 files); scanner **0**;
> `e2e/help-localization` 11/0; `eval_dictation` read-path updated → PASS; i18n/voice/realtime/RC/identity
> evals PASS; 0 paid/live; no migration, no RC. **Only with W9.6A is W9.6 fully DELIVERED.**

> **Status: DELIVERED** on branch `fix/p10b-w9-6-full-localization` (from W9.5 @ `dc655ff`; see
> `P10B_W9_6_FULL_LOCALIZATION.md`). Every Ask4Mo-owned candidate-facing string across Prepare/Mo,
> Practice/Interview, Opportunities/Documents/Company/Workspaces, Progress/Memory, the public
> legal/trust/marketing/help pages and shared chrome now renders via `useT()`/`translate()`. **527 new
> keys × 7 locales (3,689 strings)** added as five per-domain fragments merged centrally in
> `catalog.ts`. A deterministic scanner (`frontend/scripts/scan-i18n.mjs`) + a vitest guard
> (`no-hardcoded-english.test.ts`) + an `eval_i18n_l10n` invariant drive and keep candidate-facing
> hardcoded English at **0** (one documented allowlist entry: the reviewer-only `AgentInspector`).
> Backend locale allowlists consolidated into `src/locales.py` (W9.7 insertion point). A shared
> `I18nProvider` fallback-stability fix removes an effect-reload bug surfaced by the change. **No
> migration, no API change, no RC.** Gates: typecheck/lint(0 warnings)/build green; vitest 343;
> scanner 0; new `e2e/localization.spec.ts` 11/0 (+50 regression specs green);
> i18n/RC(27)/security/identity(1.0)/opportunity/onboarding/dictation/voice evals PASS; backend ruff +
> locale tests green; 0 paid/live. Human/legal review of legal-copy drafts PENDING; page `metadata`
> titles + Help article bodies deferred (see doc §5). W9.7 (Russian) not started.

- **Objective:** every Ask4Mo-owned candidate-facing string switches with the interface language; a
  guard prevents regressions. Fixes PF-13.
- **Frontend:** route the ≈190 hardcoded strings (LOCALIZATION_AUDIT §2) through `useT()`/`translate()`;
  move `lib/api/errors.ts` messages into an `errors` namespace; localize page metadata where feasible;
  add all new keys across the 7 locales. Files: `frontend/components/{agent,interview,progress,coach}/*`,
  `frontend/app/{app,privacy,terms,ai-transparency,about}/*`, `frontend/components/ui/States.tsx`,
  `frontend/lib/api/errors.ts`, `frontend/lib/i18n/messages/*`.
- **Guard (machine-checkable):** add scoped `eslint-plugin-i18next/no-literal-string` (excluding
  `admin`/`review`) + a `no-emdash`-style deterministic scan seeded with the current offenders;
  extend the key-parity test to assert `CATALOGS`↔`SUPPORTED_LOCALE_CODES`.
- **Backend:** collapse locale allowlists to one canonical source (LOCALIZATION_AUDIT §7.3) with a
  consistency test (prep for W9.7).
- **Schema:** none. **Security:** none (translation is prose-only; do NOT translate user/CV/JD/evidence
  /official source names).
- **Tests:** key-parity + no-literal scan; unit tests that switching locale changes rendered strings on
  Progress/History/Prepare/Trust. **E2E:** switch to a non-English locale, assert no English leaks on
  the core authenticated pages.
- **Evaluators:** `eval_i18n_l10n`, `eval_release_candidate` namespace parity stay green.
- **Acceptance:** all candidate-owned UI localized across supported languages; guard fails on new
  hardcoded English.
- **Dependencies:** W9.1/W9.2/W9.4/W9.5 (so their new strings are localized here or carry keys).
  **Risk:** medium (volume). **Complexity:** L.
- **STOP:** after the guard is green and the locale-switch E2E passes.

## W9.7 — Russian locale #8  *(feature)* — ✅ DELIVERED

> **Status: DELIVERED** on branch `feat/p10b-w9-7-russian-locale` (from W9.6A @ `a82081e`; see
> `P10B_W9_7_RUSSIAN_LOCALE.md`). Russian is the 8th interface + Mo-conversation language (label
> "Русский"): canonical `src/locales.py` + `APP_LOCALES`, a full Russian catalogue (**1,428 keys x 33
> namespaces per locale, exact parity**, incl. the 144 Help strings, Tutorial v2, legal/trust copy), Practice
> and agent prompt routing ("Russian", prose-only, scoring untouched). Russian is NOT a speech/OCR/labour-market/
> ESCO language (speech controls hidden for a `ru` conversation language; separate `DOCUMENT_LANGUAGE_CODES`;
> no geography/taxonomy change). **Permanent brand invariant: `Ask More. Be More.` is never translated in any
> locale** (single `BRAND_SLOGAN`; six existing locales that had translated it were corrected; the scanner
> approves only that exact string). Also fixed a W9.6A regression (`prepare.contextTab`) and a W9.6 evaluator
> read-path break. Gates: vitest 414, backend 2,489 passed/3 skipped/0 failed, full Playwright 166/166 (incl.
> Russian core/first-run/independence/error/Help/speech-boundary), typecheck/lint/build green, scanner 0, 17
> evaluators pass; 0 paid/live; no migration, no RC. Russian translations are ENGINEERING translations
> (native + legal review PENDING; live generated-Russian quality PENDING). W9.8 not started.

> **W9.7A closure (DELIVERED, `fix/p10b-w9-7a-experience-closure`; see `P10B_W9_7A_EXPERIENCE_CLOSURE.md`):**
> post-W9.7 visual QA closure. (1) Home feature blocks localized (8 locales); the scanner gained 3 structural
> passes it was blind to (old 0 -> new 13 on W9.7 sources). (2) Language ownership made explicit and correct:
> the response-template headings, insufficient-evidence note and deterministic fallback are Mo-owned
> (conversation language; `conversation_language` now flows through the Career chat path, English
> byte-identical), UI labels are interface-owned. (3) Opportunity "blank rectangle" = a permanent placeholder
> after a failed `/auth/me`; replaced by a bounded, labelled state machine. (4) Error card 232px/29% -> 162px/20%
> via a section/page/fatal hierarchy (+ localized route error boundary, focus restoration). (5) Inter now
> preloads its Cyrillic subset (W9.7's "system fallback" diagnosis was wrong: Cyrillic was already Inter,
> loaded late). (6) Local dev DB reconciled to Alembic head 0014 using only existing migrations (the chain
> itself failed on a drifted schema; data preserved 25/25 tables, backup kept). Gates: vitest 477, backend
> 2,518/3 skipped/0 failed, Playwright 189/189, 17 evaluators pass, typecheck/lint/build green; 0 paid/live; no
> migration created, no RC. Separate tasks filed: dead Tailwind `token/NN` classes; a test writing to the dev
> DB. W9.8 not started.

- **Objective:** add `ru` end-to-end without coupling language to geography, and without pretending
  generated Russian terms are official taxonomy. Fixes PF-14.
- **Scope/files:** the full footprint in LOCALIZATION_AUDIT §4 — core i18n (+new `ru.ts`), 2 speech
  allowlists, 8 backend files (via the single canonical source from W9.6), ~15 evals, ~11 tests, Docker
  `rus` pack.
- **Backend:** add `ru` to the canonical locale source; `RESPONSE_LANGUAGE_NAMES`/
  `_CONVERSATION_LANGUAGE_NAMES` gain `"ru":"Russian"` (allow-list-only). Do NOT add `ru` to geography
  lists.
- **Schema/migration:** the `interface_locale`/`conversation_language` columns are string-validated, not
  DB enums — verify no migration needed (likely none).
- **Security/provenance:** governance `SUPPORTED_LANGUAGES` gains `ru` as UI-only; coverage matrix keeps
  reporting Russian KB content absent/unvalidated; any curated Russian occupation alias uses
  `ConfidenceBasis.CURATED_MANUAL` + `ASK4MO_CURATED_SOURCE` (never `OFFICIAL_MAPPING`).
- **Tests:** locale-list tests updated to 8; `ru.ts` key-parity; language directive emits Russian;
  geography unchanged by `ru`. **E2E:** product renders in Russian; geography independent.
- **Evaluators:** all 8-locale-aware evals green.
- **Acceptance:** Russian included; interface language independent of conversation/dictation/geography.
- **Dependencies:** W9.6 (canonical locale source + full catalogue coverage). **Risk:** medium
  (translation quality is engineering-draft; label honestly). **Complexity:** L.
- **STOP:** after all 8-locale gates pass; Russian translation quality is engineering-draft, not
  human-validated — state so.

## W9.8 — Privacy & Candidate Data Controls  *(Capstone critical, Cx L)* — ✅ DELIVERED (see `P10B_W9_8_PRIVACY_DATA_CONTROLS.md`; deferred gaps listed there: preparation-chat index, consent history, bulk memory clear)

> Renamed and widened (roadmap reconciliation): a Data & Privacy Center covering what is stored, export, selective deletion (documents, memory, Opportunities, interviews, reports), agent-run/checkpoint implications, workspace/shared-data visibility and revocation, account deletion, retention, consent/legal versions, request status, all 8 locales, preserving audit/legal records. W10.10 is the operator side.

- **Objective:** a read-only "Your Data / Privacy Center" that surfaces every data class and links to
  its existing control. Fixes PF-15 (view/discoverability); no new deletion semantics.
- **Frontend:** a new center listing each class (PILOT_FINDINGS §3) with links to existing
  delete/export. Files: `frontend/app/privacy/*` or a new `/account/data` route +
  `frontend/components/*`.
- **Backend:** none new (reuse existing routes). **Schema:** none.
- **Security/privacy:** respect integrity constraints — history crash-safety
  (`interviews.source_session_id`), checkpoint `delete_thread` only, audit anonymise-don't-delete,
  SET-NULL cascades. Any NEW deletion (e.g. per-completed-report) is **out of scope** until its impact
  is analysed and separately gated.
- **Tests:** the center renders each class + link; no destructive action added. **E2E:** center
  reachable; links resolve.
- **Evaluators:** `eval_account_deletion`, `eval_restart_recovery` stay green.
- **Acceptance:** users can find what they can remove; no regression to audit/legal/history integrity.
- **Dependencies:** W9.6 (localized). **Risk:** low (read-only). **Complexity:** M.
- **STOP:** after the center renders and no integrity gate regresses.

## W9.9 — Trust & Visual Product Polish  *(desirable, Cx M)* — ✅ DELIVERED (see `P10B_W9_9_TRUST_VISUAL_POLISH.md`; deferred P3 polish listed there)

- **Objective:** clearer, more premium Trust presentation + fixed visual hierarchy. Fixes PF-16, PF-17.
- **Frontend:** group Trust `CONTROLS` into ~4 sections + cross-links + localize; nav salience; reserve
  `text-muted` for tertiary; mobile-bar icons; stronger secondary CTA. Files:
  `frontend/components/marketing/TrustContent.tsx`, `frontend/components/layout/*`,
  `frontend/app/globals.css` (class usage, not token overhaul).
- **Backend/schema:** none. **Security:** no new claims; keep Wave 7 claim discipline (no emoji, no em
  dash, no unsupported absolutes).
- **Tests:** Trust sections render + localized; no em-dash regression. **E2E:** Trust readable; AA
  contrast preserved.
- **Evaluators:** `eval_marketing_product_trust` stays green.
- **Acceptance:** Trust grouped + localized; hierarchy improved; accessibility + responsive preserved.
- **Dependencies:** W9.6. **Risk:** low. **Complexity:** M.
- **STOP:** after marketing/trust gate + visual review.

## W9.10 — Product Positioning / Comparison Foundation  *(desirable, Cx S)* — ✅ DELIVERED (see `P10B_W9_10_PRODUCT_POSITIONING.md`)

> Factual only; no unsupported superiority claims; external competitor research needs separate authorization.

- **Objective:** a factual "what's different" comparison scaffold with zero unsupported claims. Fixes
  PF-18.
- **Frontend:** a comparison section using only provable rows + an honest-limits row (UX_REMEDIATION §7).
  Files: `frontend/components/marketing/*`, `frontend/lib/pricing.ts` (read-only reference).
- **Backend/schema:** none. **Security:** no fabricated testimonials/ratings/outcomes; no purchasable
  Premium; external competitor research is a separate authorized task (no scraping).
- **Tests:** claim rows trace to implemented/tested capabilities; marketing gate green.
- **Acceptance:** comparison exists without superiority/unsupported claims.
- **Dependencies:** W9.6, W9.9. **Risk:** medium (claim discipline) — keep to the ledger. **Complexity:** M.
- **STOP:** after the marketing gate confirms no unsupported claim.

## W9.11 — Architecture & Documentation Consistency  *(Capstone critical, Cx M)* — ✅ DELIVERED (see `P10B_W9_11_ARCHITECTURE_DOCUMENTATION_CONSISTENCY.md`)

- **Objective:** remove doc/code contradictions surfaced by the audit. Fixes PF-21, PF-22.
- **Scope:** correct the authority-level comment `src/api/schemas/career.py:37` to "1=official ..
  3=industry" (**semantics unchanged**); correct the stale "five Career tools" docstring
  `src/agent/tools.py:603` → six; add a contract test asserting `SourceOut.authority_level` type stays
  in sync with `KnowledgeEvidence.authority_level`; update CLAUDE.md/specialist docs to state plainly
  "three bounded specialists; evaluation is a separate deterministic service; no Evaluation Specialist."
- **Backend/schema:** none (comment/docstring + one test). **Security:** none.
- **Tests:** the new authority-level contract test; existing specialist/registry tests green (11 tools).
- **Acceptance:** no authority-level semantic inconsistency; docs match code.
- **Dependencies:** none. **Risk:** none. **Complexity:** S.
- **STOP:** after the contract test passes. **Do NOT add an Evaluation Specialist.**

## W9.12 — Engineering Quality & Technical Debt Closure  *(Capstone critical, Cx M-L)*  [new] — ✅ DELIVERED (see `P10B_W9_12_ENGINEERING_QUALITY.md`; TD-W9-01 and TD-W9-02 closed)

- **Scope:** **TD-W9-01** (Tailwind `token/NN` opacity classes: inventory, supported token strategy, light/dark/mobile
  visual regression); **TD-W9-02** (backend test isolation leak: identify path, isolated test DB, prove no dev/prod DB
  writes, defensive guards); metadata localization architecture if deferred; 8-locale bundle/performance review;
  optional locale-aware font subset (TD-W9-03) only if profiling justifies.
- **Acceptance:** TD-W9-01 and TD-W9-02 closed with evidence; no regression; 0 paid/live.
- **Dependencies:** W9.8-W9.11 (any order, ideally after W9.9 for visual work). **STOP:** do not start W9.13.

## W9.13 — Full P10B Requalification  *(gate, Capstone critical, Cx L)*  [formerly W9.12]

- **Objective:** the whole deterministic suite is green and the test-env artifact is intrinsically
  isolated, so a replacement RC can be qualified.
- **Scope:** make the 13 `.env` `OPENROUTER_MODEL_*`-dependent tests neutralise the override intrinsically
  (a fixture that resets the model env for the default-slug assertions) — **without weakening any
  assertion**; run full backend `pytest`, `ruff`, frontend lint/typecheck/vitest/build, `npm run e2e`
  (incl. the new resilience/localization/security specs), and every deterministic evaluator (0
  paid/live).
- **Files:** `tests/conftest.py` or the 5 affected test files; CI config.
- **Acceptance:** 0 failed backend (incl. isolation), all frontend gates, all evals PASS, 0 paid/live;
  no unresolved P0/P1; **TD-W9-01 and TD-W9-02 already closed in W9.12** (verify, do not defer).
- **Dependencies:** W9.1–W9.12. **Risk:** low. **Complexity:** M.
- **STOP:** produce the RC readiness assessment against ACCEPTANCE_GATES. **Do NOT create RC-P10-003 in
  this task** — creation is a separate, explicitly-approved step after the gate.

---

## Recommended sequence (revised at main d6c3493)

Completed: W9.1-W9.7B and W9.8-W9.13 (**P10B QUALIFIED**, engineering decision). Remaining before W10: none, then P10B-W10
(Admin, W10.0-W10.14), P10B-W11 (integrated requalification), RC-P10-003, Pilot 2, P10C-P10F, P11. The canonical
roadmap is `docs/capstone/capstone_phase_plan.md`. W9.9/W9.10 are off the critical path.

---

## Roadmap: P10B-W10 - Platform Administration, Support & Commercial Operations  *(approved, NOT started)*

Superseded by the dedicated plan: `docs/capstone/admin/ADMIN_PLATFORM_MASTER_PLAN.md` (waves W10.0-W10.14) and
`docs/capstone/admin/ADMIN_CAPABILITY_MATRIX.md`. Core principle retained: **platform admin != unrestricted
private-candidate-data superuser.** W10 follows W9.13 and is not part of W9.

## Technical-debt register (W9)

- **TD-W9-01 - Invalid Tailwind opacity-modifier usage.** About 15 classes such as `border-warning/50`,
  `bg-warning/10`, `text-foreground/80` generate no CSS because the project's custom colour tokens are plain
  `var()` values. Impact: intended opacity styling is silently absent; about 10 approved UI elements may change
  appearance when this is fixed properly. Required task: inventory all affected classes, choose a valid
  colour-token strategy, and visually regression-test light/dark/mobile before changing anything. **Open;
  scheduled for W9.12.**
- **TD-W9-02 - Backend test-isolation leak.** A backend test wrote a fixture interview/report into the local
  development database during a full test run (previously hidden by the dev-DB schema lag). Impact: the
  deterministic suite is not fully isolated from local dev persistence. Required task: identify the exact
  test/config path, make tests use isolated temporary databases, and prove no dev/production DB writes during
  the suite. **Open; scheduled for W9.12.** W9.8 finding: `get_memory_service`/`get_memory_repository` call `get_repository()` directly, so a `get_repository` override did not reach them; `build_auth_app` now overrides `get_memory_service` (partial fix; W9.12 must still audit other direct-call dependencies and add a defensive DB guard).
- **TD-W9-03 - Locale-aware font/subset loading (optimization, optional).** W9.7A added the `cyrillic` subset
  to the existing Inter loader (kept; ~18.7 kB woff2 preloaded on every page for every locale, accepted
  provisionally because Russian is a supported language and typography is consistent). A locale-aware
  loading strategy may be evaluated during performance optimization, only with measurement. **Open, low
  priority; optional in W9.12.**
