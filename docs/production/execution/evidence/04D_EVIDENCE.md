# 04D Evidence: Candidate journey reliability (REQ-CAND-01, DEMO-02, PG-06)

Two PRs from `origin/main` (f5cf7cb4), no migration, no new permission, no live provider call.
- **PR 1** `feat/04d-journey-tests` (commit 67ef7c46): the real-browser journey suite (one definition, two modes), the offline local-stack launcher, AC-03 tests.
- **PR 2** `feat/04d-provider-mode-and-guards`, STACKED on PR 1 (it edits the same journey files): provider mode, accurate provider-failure copy, owner-scoped run list, key-hazard guard and offline switch, one pricing wording. Open PR 1 first; PR 2 targets `main` after PR 1 merges (or targets PR 1's branch).

Every result below is labelled **OFFLINE** (fixtures, temp database), **MOCKED NETWORK** (Playwright with the network mocked) or **REAL STACK** (real FastAPI + Next.js + Chromium on this machine with offline fixture model replies). **None is live-model qualification. The staging run is NOT RUN (OD-HOSTED not decided).**

## Requirement mapping
| Requirement | Covered | How | NOT covered |
|---|---|---|---|
| REQ-CAND-01 real Candidate journey incl. Start Interview | Yes (MOCKED NETWORK and REAL STACK) | `frontend/e2e/journey/definition.ts`: uninvited refusal, register WITH a valid invitation (hosted-like), sign in, onboarding, Opportunity, reload persistence, AI mode + own run list, Mo, START INTERVIEW (one request, first question), answer + evaluation (7 rubric dimensions), second question, completion, report, History, Progress. Once per language (en, de, fr, es, it, pt, nl) in both modes. A self-check proves the suite FAILS at Start Interview when creation is unavailable | Staging run (NOT RUN, OD-HOSTED); Russian (excluded from R1.0 selection) |
| Start Interview regression (the observed failure) | Yes | Cause found: a keyless backend answered Start Interview with 503 `service_unavailable` (message naming the OpenRouter key); the UI renders fixed copy by status, so it showed the generic "temporarily unavailable" identical to a passing outage, the keyless stack looked identical to live, and every failed press left an empty "SETUP" interview in the resumable list. Regression tests (backend + browser) assert the stable code and fixed copy | Re-run of the original live stack (no such stack available) |
| DEMO-02 provider-mode indicator (Candidate and Admin) | Yes | `/capabilities.ai_provider_mode` + Admin provider row `mode` (+ Admin table shows it); Candidate shell `ProviderModeIndicator`. Vocabulary: live (configuration, not health), offline, not_configured, unknown | Admin copy English-only by decision |
| Accurate, localized provider-unavailable copy; no success claim; no silent duplicate; failure recorded without secrets | Yes | codes `ai_not_configured` / `ai_provider_unavailable`, fixed copy in 8 locales (`states.*`); Practice `error_code`, Mo `failure_code`; failed start discards the empty setup; one idempotency key per setup attempt-series; one bounded `provider_call` event with the cause code only | Mo SSE streaming copy (04C) |
| Opportunity persistence (reload, restart) and AC-03 | Yes | `tests/test_opportunity_persistence_ac03_04d.py` (two Opportunities, chosen JD context reaches the model and the other does not, restart on a FILE database, legacy anonymous rows not adopted, cross-user isolation); journey reload step | PostgreSQL restart |
| IR-AC18-RUNLIST owner-scoped run list | Yes (the run-list clause of AC-18) | `GET /agent/runs` (own runs only, bounded, no content, fail closed hosted), Prepare UI list with explicit error state; 7 backend tests incl. cross-user and hosted-like; browser: only own run listed across 7 candidates on one stack | The other AC-18 clauses (safe specialist events, bounded retrieval evidence, stored evaluation artifacts) are NOT in this package |
| IR-DEMO-KEY implicit key discovery + key-hazard guard | Yes | `ASK4MO_PROVIDER_MODE=offline` reads NO provider credential from .env, Streamlit secrets, environment or the managed store and never loads .env (positive control included). Guard: browser bundle and served pages scanned for the configured (canary) value and key shapes; every parameterless GET route as candidate, admin and anonymous scanned; hostile provider error cannot reach the candidate | |
| CJ-D-02 / I-D02 pricing wording | Yes | one statement `betaPricing.statement` (8 locales) via `BetaPricingStatement` on pricing, home, footer, terms, registration (the plan view keeps its existing, already consistent wording; its test forbids purchase/price words); price field removed; catalogue scan fails on any currency figure or purchase claim | Legal wording review |

## Changes
- PR 1: `frontend/e2e/journey/{definition,env,mockWorld}.ts` + `fixtures.json`, `frontend/e2e/candidate-journey-04d.spec.ts`, `frontend/playwright.journey-real.config.ts`, `scripts/e2e/{journey_stack,journey_fakes}.py`, `tests/test_journey_stack_04d.py`, `tests/test_opportunity_persistence_ac03_04d.py`; small edits: `next.config.mjs` (`distDir` from `NEXT_DIST_DIR`), `tsconfig.json` include, `.gitignore`.
- PR 2 backend: `src/application/provider_mode.py`, `src/core/secrets.py` (offline switch), `src/config.py`, `src/copilot/config.py` (skip .env), `src/constants.py` (codes and fixed copy), `src/interview_service.py` (`ServiceError.code`), `src/session_manager.py` + `src/interview/session_codec.py` (`error_code`, additive JSON key, no migration), `src/application/interview_service.py` (`_fail`, telemetry), `src/api/routes/interview.py` (coded 503, discard failed setup), `src/api/routes/agent_runs.py` (NEW module) + one registration line in `src/api/main.py`, `src/privacy/preparation.py` (`recent_for_owner`), `src/agent/models.py`, `src/application/agent_service.py`, `src/api/schemas/{agent,common,interview}.py`, `src/api/routes/{agent,health}.py`, `src/application/admin_providers.py`, `scripts/eval_marketing_product_trust.py` (pricing invariant updated to the new contract).
- PR 2 frontend: `ProviderModeIndicator`, `BetaPricingStatement`, `RecentRuns`, error kinds `aiNotConfigured` / `aiUnavailable`, Practice/Prepare/setup copy by code, Admin provider mode, i18n fragment `w04d` (8 locales), pricing surfaces, `OnboardingClient` race fix, `playwright.config.ts` (canary key in the web server env), specs `candidate-provider-04d`, `key-hazard-04d`, updated `marketing.spec.ts`, `v4-experience.test.tsx`.
- Shared files touched minimally: `src/api/main.py` (+1 import, +1 router), `playwright.config.ts` (env), `CLAUDE.md` (one section). Not touched: AdminShell, capabilities.ts, nav-items.ts, docker-compose.staging.yml, `src/agent/*` graph code (only the result dataclass gained `failure_code`), `src/copilot/security/*`, frozen contracts, tracker, register.
- Existing assertions CHANGED deliberately, driven by the owner direction "free beta, no purchase claim, no price": `marketing.spec.ts` (price figures replaced by the single statement), `v4-experience.test.tsx` (`priceDisplay` removed, carousel no longer shows a figure), `eval_marketing_product_trust.py` `pricing_basic_free`. Premium "not available, no purchase path" assertions are unchanged. The owner may veto this reading of "no price".
- Locale audit regenerated (`06A_LOCALE_AUDIT.md`).

## Findings while building (for the lead)
1. **Hosted-like needs `API_ENV=staging`**: in development an unauthenticated browser silently becomes the anonymous developer user, so a "journey" there proves nothing about sign-in. The launcher uses staging.
2. **Hosted language activation blocks Practice and Mo**: with no language qualified, staging refuses new language-bearing work (`language_not_activated`). The offline stack overrides ONLY that decision to the development "labelled" mode. A staging journey needs at least one activated language.
3. **Hosted Mo needs semantic embedding credentials**: a hosted environment refuses the hash embedder, so Mo cannot be built without them (503 `not_configured`). The offline stack stubs retrieval (fails loudly if used), so retrieval is NOT exercised by the journey.
4. **Registration is rate limited per IP (8/h, invitation 10/h)**: the suite runs the uninvited probe once; seven languages fit one hour per IP.
5. **Defects found and fixed**: failed starts left empty resumable sessions; the Terms page still said "Premium is EUR 19.99 per month"; the onboarding resume could throw a fast click-through back to step 1 (found by the journey, unit test fails without the fix).
6. Keyless Mo and Practice previously returned English server text that named the provider and the variable; now fixed copy only.

## Security and privacy impact
No credential, provider name, URL, key hint or provider text in any candidate-facing error; failure events carry the cause code only (asserted against a canary key and a private marker in background text); run list is owner-scoped in the SQL filter; offline switch withholds credentials from every source; the web server is built and served with a canary key and the scan proves it is not in the browser output. No new permission (registry stays 44), no migration, no Admin route.

## Tests and commands (labelled)
| Check | Label | Result |
|---|---|---|
| New backend suites `test_journey_stack_04d.py` (19), `test_opportunity_persistence_ac03_04d.py` (5), `test_provider_failures_04d.py` (33): `pytest <files> -p no:cacheprovider` | OFFLINE | 57 passed on the repo venv (ci_venv: included in the full run) |
| Full backend `pytest tests -p no:cacheprovider -n 3 --dist loadfile -q` on `$HOME/.cache/ask4mo/ci_venv` (fresh dependencies; run once, after the last backend edit) | OFFLINE | exit code 0, no failure or error. The per-test count was not captured: the quiet xdist output prints no summary line, and re-running the 15-minute suite only to count was not done |
| Start Interview regression against the PRE-04D server (PR 1 tree + the new fakes + 3 tests copied in a temp directory, then deleted) | OFFLINE | 3 of 3 FAIL as intended: keyless code was `service_unavailable` (expected `ai_not_configured`), provider-down code `service_unavailable`, 2 failed presses left 2 empty SETUP sessions. All 3 pass on the PR 2 tree |
| `ruff check .`; `scripts/ci_test_shards.py verify --shards 4` | | pass; 303 test files, each in exactly one shard |
| 49 evaluators (every `scripts/eval_*` CI runs with its CI arguments, plus `eval_marketing_product_trust` and `eval_locale_inventory`) on ci_venv | OFFLINE | 49 ok, 0 failed (one first-pass failure of `eval_marketing_product_trust`, `pricing_basic_free`, fixed by updating its invariant to the no-price contract). 0 paid or live calls |
| Frontend `tsc --noEmit`, `npm run lint`, `vitest run` | | clean; 124 files, 1342 tests (new: `beta-pricing-04d` 25, `provider-copy-04d` 35, onboarding race test; the race test FAILS when the fix is removed) |
| Playwright PR 1 journey, mocked, `E2E_PORT=3132`, 7 languages + self-check | MOCKED NETWORK | 8 passed |
| Playwright PR 2: `candidate-provider-04d` (keyless x7, provider_down x7, run list, malformed run list), `key-hazard-04d` (3) | MOCKED NETWORK | 18 passed |
| Playwright full suite (68 specs, 481 tests incl. the 04D ones), after the last frontend edit | MOCKED NETWORK | 467 passed, 14 skipped (the skips pre-exist: dormant Russian specs and similar), 0 failed |
| `scripts/e2e/journey_stack.py run` healthy, 3 languages (journey + key hazard) | REAL STACK (offline fixtures) | 6 passed; earlier healthy run: 7 languages passed |
| same, `--variant keyless`, 4 languages | REAL STACK | 7 passed (the original defect's environment: accurate not-configured copy, mode not_configured) |
| same, `--variant provider_down`, 3 languages | REAL STACK | 6 passed |

Commands: `python scripts/e2e/journey_stack.py run [--variant keyless|provider_down] [--languages en,de]`; `cd frontend && E2E_PORT=3132 npx playwright test [spec]`; `pytest tests -n 3 --dist loadfile -q -p no:cacheprovider`; `ruff check .`; `python scripts/ci_test_shards.py verify --shards 4`; evaluators as in `.github/workflows/ci.yml`.

Not run: the journey against hosted staging; any live provider call; PostgreSQL restart; CI (no PR exists). `.next-journey` and `test-results` are ignored build output and are not committed.

## Risks and limits
- The offline stack proves wiring, authorization, persistence and UI; it says nothing about model quality or live provider behaviour.
- `ai_provider_mode=live` is configuration, never health or qualification.
- The mocked world mirrors the real responses observed on the real stack, but is not a substitute for the backend tests.
- A rate limit and the hosted findings above apply to any staging run.

## Remaining human, live-staging and gate evidence
- Journey against a hosted staging stack: **NOT RUN** (OD-HOSTED). How: `scripts/e2e/journey_stack.py` docstring (invitation codes file, `BASE_URL`, `JOURNEY_API_URL`, `JOURNEY_LANGUAGES`, `JOURNEY_EXPECT_AI_MODE`).
- PG-06 stays NOT RUN until that run, streaming/cancellation (04C) and availability and latency targets (OD-GATE-THRESHOLDS).
- Native review of the new copy in 7 languages (engineering translations); legal review of the beta statement and Terms wording.

## Throughput
Start 2026-10-22 08:22 CEST. First push (PR 1) 08:46 CEST. Rework rounds: 3 (launcher hosted-like, fixture-per-interview, keyless pricing path). SHAs: see the final report.
