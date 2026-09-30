# P10B-W9 — Implementation Plan

Audit phase. **No runtime code changed by this task.** This is the proposed, wave-structured plan for
P10B-W9. Nothing here is implemented yet; each wave has an explicit STOP condition and awaits approval.

**Global constraints (every wave):** RC-P10-002 immutable; 0 paid/live provider calls unless
explicitly authorised; never print/log/commit the OpenRouter key; do not weaken tests, security,
provenance, HITL, scoring semantics or ownership; keep interface language independent of
conversation/dictation/geography; do not change authority-level semantics; commit trailer
`Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`. Each wave: branch from the prior wave tip
(or main), PR, do not auto-merge, deterministic gates green before the next wave.

**Complexity key:** S (≤~1 day) · M (2–3 days) · L (multi-day).

---

## W9.1 — Service resilience & truthful error handling  *(P1, blocks Pilot 2)*

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

## W9.2 — Progress/History recovery & degraded states  *(P2)*

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

## W9.3 — Security/menu investigation & remediation  *(Low, but before Pilot 2)*

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

## W9.4 — Opportunity discoverability  *(P1, before Pilot 2)*

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

## W9.5 — Welcome + Tutorial v2  *(P1/P2, before Pilot 2)*

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

## W9.6 — Full-app localization completion  *(P1, before Pilot 2)*

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

## W9.7 — Russian locale #8  *(feature)*

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

## W9.8 — Privacy / Data control UX  *(P2)*

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

## W9.9 — Trust + visual hierarchy polish  *(P2)*

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

## W9.10 — Product comparison foundation  *(P3 / feature)*

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

## W9.11 — Architecture / documentation consistency  *(P3)*

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

## W9.12 — Full deterministic release requalification  *(gate)*

- **Objective:** the whole deterministic suite is green and the test-env artifact is intrinsically
  isolated, so a replacement RC can be qualified.
- **Scope:** make the 13 `.env` `OPENROUTER_MODEL_*`-dependent tests neutralise the override intrinsically
  (a fixture that resets the model env for the default-slug assertions) — **without weakening any
  assertion**; run full backend `pytest`, `ruff`, frontend lint/typecheck/vitest/build, `npm run e2e`
  (incl. the new resilience/localization/security specs), and every deterministic evaluator (0
  paid/live).
- **Files:** `tests/conftest.py` or the 5 affected test files; CI config.
- **Acceptance:** 0 failed backend (incl. isolation), all frontend gates, all evals PASS, 0 paid/live;
  no unresolved P0/P1.
- **Dependencies:** W9.1–W9.11. **Risk:** low. **Complexity:** M.
- **STOP:** produce the RC readiness assessment against ACCEPTANCE_GATES. **Do NOT create RC-P10-003 in
  this task** — creation is a separate, explicitly-approved step after the gate.

---

## Recommended sequence

**Before resuming Pilot 2 (P0/P1):** W9.1 → W9.2 → W9.3 → W9.4 → W9.5 → W9.6 → W9.11 (docs/comment; cheap).
**Can follow (P2/P3):** W9.7 (Russian), W9.8 (Data Center), W9.9 (Trust/visual), W9.10 (comparison).
**Always last:** W9.12 requalification, then (separately approved) cut the replacement RC.

Waves are independent PRs; W9.6 depends on the string-producing waves before it, so land W9.1–W9.5 first
then sweep localization in W9.6, then W9.7 Russian on top of the canonical locale source.
