# P10B-W9.12 - Engineering Quality & Technical Debt Closure

Engineering wave. **No product-policy change**, no migration (Alembic head `0014_opportunities`), 0 paid/live calls, no RC-P10-003,
Pilot 2 not resumed, W9.13 and W10 not started.

## 1. Baseline
`main` = `931d2a88d64f4eaf0178338f393113ae37072e84` (W9.11 merged, PR #106). Branch `fix/p10b-w9-12-engineering-quality`.

## 2. Engineering audit matrix (9 items)
| ID | Finding | Runtime impact | Security/privacy impact | Disposition |
|---|---|---|---|---|
| TD-W9-01 | alpha utilities on colour tokens emit no CSS | intended tints/borders silently absent (10 distinct classes, 15 uses) | none | FIX NOW (closed) |
| TD-W9-02 | tests wrote to the developer's DB; env/secret leakage | dev data polluted; 13 order-dependent failures | tests could reach real keys/stores | FIX NOW (closed) |
| H1 | sign-in does not require a verified email | users can use the product unverified | account-takeover surface limited (OIDC links only on provider-verified email) | POLICY DECISION REQUIRED (behaviour pinned by tests) |
| H2 | rate limiter process-local | counters not shared across replicas | weaker brute-force protection if scaled out | FIX NOW (adapter boundary + optional Redis adapter; NOT live) |
| H3 | legacy Streamlit-era auth code | none | none | RETAIN `src/auth.py` as legacy (used by the Streamlit app); RETIRE dead `get_current_user` |
| H4 | `/auth/account/delete-request` + client method | no caller; set a status with no completion or recovery path (lock-out hazard) | misleading semantics beside real deletion | RETIRE (removed) |
| H5 | evaluation scores model-produced | n/a | n/a | VERIFIED SAFE: contract pinned by tests; no formula invented |
| H6 | stale "seven locale" comments/docs | none | none | FIX NOW (current-state comments) / banner (historical) |
| H7 | legacy Streamlit UI + `DATA_RETENTION_NOTE` | none | none | RETAIN AS LEGACY (recommendation, section 21) |

## 3-6. TD-W9-01 - Tailwind colour-token opacity (closed)
**Inventory (complete, regex over app/components/lib):** 15 occurrences, 10 distinct classes: `border-accent/40`, `border-accent/50` (x2),
`bg-accent/5`, `border-success/50` (x2), `border-warning/50` (x2), `border-warning/60`, `bg-warning/10`, `bg-surface-2/40`, `text-foreground/70`,
`text-foreground/80`. Files: JourneyChrome, CompanyReport, DeepDivePanel, MobileNavigation, PrimaryNavigation, LegalPage, MarketingHome,
OpportunityStatusBadge. Built-CSS check on `main` confirmed none emitted a rule.
**Root cause:** the tokens are plain `var(--x)` strings; Tailwind cannot derive an alpha variant from a CSS variable, so it drops the utility.
**Fix (smallest, one colour system):** `token()` helper in `frontend/tailwind.config.ts`. Unmodified utilities stay byte-identical (`var(--x)`); an alpha
modifier now emits `color-mix(in srgb, var(--x) <alpha>%, transparent)` of the SAME CSS variable, so light/dark still switch in `globals.css`.
**Visual regression:** computed styles checked in light/dark x desktop/390px on Opportunities (badge borders), AI transparency (draft banner), Home
(card border) and the primary/mobile nav: nav text is now 80%/70% foreground (about 9.2:1 and 6.8:1 on the light background; about 8.4:1 in dark),
borders and the warning banner tint resolve as intended; screenshots of the draft banner (dark) and Opportunities (mobile light) reviewed. Previously
dead styles now apply by design, so a few elements look slightly more tinted than before.
**Guard:** `frontend/tests/tailwind-token-opacity.test.ts` runs Tailwind itself over every `<utility>-<token>/<alpha>` found in source and fails if
any emits no CSS; verified to FAIL against the old config (10 dead classes listed) and pass with the fix. Browser support note: `color-mix` needs a
current evergreen browser (Chrome 111+, Safari 16.2+, Firefox 113+); on older engines only these alpha accents are ignored.

## 7-12. TD-W9-02 - test isolation and the 13 `.env` failures (closed)
**Root causes (all verified):**
1. `load_config()` in `src/config.py`, `src/core/config.py`/`secrets.py` and `src/copilot/config.py` call `load_dotenv`, so the first test that built a config
   copied the developer's `.env` (`OPENROUTER_MODEL_*`, API keys) into `os.environ` for every later test: the 13 model-default failures were
   order-dependent and passed in isolation.
2. Streamlit's `st.secrets` reads the developer's `.streamlit/secrets.toml` and exports its keys into `os.environ` on first access (a second leak path).
3. `DATABASE_URL` defaulted to the real `sqlite:///data/interview_studio.db`; any test that built the real app wrote there (the memory-service leak
   found in W9.8 was one instance; the clean-main baseline run still modified the dev DB).
4. The external-research cache defaulted to `data/cache/external` and one test wrote (and could read) there.
**Stores audited:** development SQLite DB, agent-checkpoint SQLite (derived from the DB path), document store, Chroma/vector dir, knowledge SQLite stores,
external-research cache, feedback-intelligence outputs, `.env`, Streamlit secrets. Only the DB and the research cache were written by tests.
**Implementation (`tests/conftest.py`, no product change):** disable `.env` loading (env flag + no-op `load_dotenv`); scrub provider/model/persistence
variables; point Streamlit secrets at an empty file; force a per-process temp `DATABASE_URL`; refuse any SQLAlchemy engine that is not in-memory or inside
the system temp directory (non-sqlite URLs too) with a clear message; default the research cache to a temp dir; and fail the whole session if any
development store changed. Opt-out only by an explicit `ASK4MO_TEST_ALLOW_DEV_PERSISTENCE=1`. Regression tests: `tests/test_test_isolation.py` (7).
**Result:** the full backend suite passes without any local `.env`/secrets pinning: **2565 passed, 3 skipped, 0 failed**. The 3 skips are the documented RAGAS
installed/absent guards. The dev DB is byte-identical before and after the run. While debugging, a local provider key was echoed once into this session's
tool output (not written to any file, log or commit); rotate that key if the session transcript is retained or shared.

## 13-14. Verified-email policy (decision gate; behaviour unchanged)
Facts: registration creates an `active` account with `email_verified=false` and sends a verification link (Brevo/console/memory sender); `/auth/verify-email`
marks it verified; login checks only password and active status; nothing else in `src/` gates on `email_verified` (it is displayed/exported); OIDC accounts
link to an existing account only when the provider marks the email verified; existing users could be locked out if enforcement were added without a resend
path (resend exists). Classification: **product policy** (also a security hardening choice). Options: A verification required before normal use;
B required only for sensitive capabilities (export, delete, sharing, invitations); C recommended not enforced; D current behaviour retained for Capstone.
Recommendation for the owner: **B** (limits abuse and mis-typed-email risk without blocking onboarding), decided before any public launch. **No change was
made**; `tests/test_email_verification_policy.py` pins today's behaviour so a policy change is deliberate.

## 15-16. Rate limiter
Audit: process-local sliding window; `RateLimiter` protocol and `distributed` flag already existed. Added `RedisRateLimiter` (atomic sliding-window script,
degrades to per-process limiting if Redis errors, never fails the request path) selected ONLY when `RATE_LIMIT_BACKEND=redis|shared` + `REDIS_URL` are set and
the optional `redis` package is installed; otherwise the in-memory limiter is used and the request is reported. **No new dependency was added.** The adapter is
tested against a fake client (shared window across two replicas, degradation, selection logic) and has **not** been run against a live Redis: distributed
limiting is **not live** and is not claimed (`shared_store_active()` is false by default; hosting-readiness still reports `distributed=false`).

## 17-18. Legacy auth and delete-request
`src/auth.py` is used by the legacy Streamlit app (`studio_app.py`, `history_service.resolve_user_id`) and for two shared types: RETAINED, already labelled legacy.
`get_current_user` in `api/dependencies.py` had no caller anywhere (src, tests, scripts): REMOVED. `/auth/account/delete-request` and `api.auth.requestDeletion`
had no caller or test, predate W9.8, only flipped a status and revoked sessions (login then blocked, nothing completed or recoverable) and sat beside the real
`/auth/account/delete`: REMOVED. The `deletion_requested` status constant remains because the admin privacy-request view reads it.

## 19. Evaluation output consistency
Interview evaluation stays LLM-backed. The contract defines seven integer rubric dimensions (1-10), an integer overall score (0-100) and required text fields;
the only stated relationship is qualitative ("overall_score consistent with the criterion scores"), so **no formula was invented**. `tests/test_evaluation_contract.py`
(10) pins bounds, required dimensions, integer-ness and the deliberate independence of overall vs criteria; a possible deterministic tolerance rule is left as an
owner decision (it would be a new product promise).

## 20. Locale comments/docs
Current-state comments corrected (`lib/i18n/locales.ts`, `w96` fragment headers); `docs/capstone/p3_5_i18n_l10n.md` bannered as historical. Verified: Voice-specific
"seven languages" wording is correct and was kept. Test titles that say "seven" were left (historical test names, behaviour unaffected).

## 21. Legacy Streamlit: RETAIN AS LEGACY
Evidence: 18 test files reference it, CI compiles `app.py`, the root `Dockerfile` still launches `streamlit run app.py`, and `DATA_RETENTION_NOTE` renders only there.
Retirement would change submission evidence and test coverage, so it is **not** done; recommend a separate, explicitly approved retirement task.

## 22-23. Evaluator/test mutation audit and clean tree
Ran every CI evaluator from a clean tree and diffed `git status`: `eval_knowledge_expansion.py` and `eval_product_coverage.py` rewrote committed files. Both now
write to a temp directory by default and refresh the committed artifacts only with `--write` (or `ASK4MO_EVAL_WRITE=1`); no other evaluator or test mutates tracked
files. CI gained a final step that fails if tests/evaluators leave any change in the working tree, plus `eval_engineering_quality.py` (14 static invariants).
Clean-tree proof: after the full backend suite and all evaluators, `git status --porcelain` shows only intentional edits.

## 24-28. Verification
Results are in the PR description (frontend, Playwright, evaluators, security regression). Security regression: production auth remains fail-closed and dev identity
dev-only (`tests/test_auth_*`, `eval_identity_platform`), owner scoping and admin boundaries unchanged (`eval_platform_admin`, `eval_workspace_security`), privacy
semantics unchanged (`eval_privacy_controls`, `eval_account_deletion`), no secrets logged, no provider calls. Dependencies: none added.

## 29. Migration
None. Alembic head `0014_opportunities`.

## 30. Open privacy items (not touched; need data-model work)
PRIV-W9-01 (preparation-chat indexing/deletion) and PRIV-W9-02 (consent/legal acceptance persistence): carry into W10.10 / the approved architecture.

## 31. W9.13 handoff
- **Accepted limitations:** PRIV-W9-01; PRIV-W9-02; Russian speech unsupported; engineering translations (native/legal review pending); live generated-language
  quality unvalidated; metadata localization; locale/bundle optimisation; realtime voice and Google OIDC not live-validated; Premium preview; no ticketing; full admin
  platform planned (W10).
- **Unresolved policy decisions (owner):** email-verification policy (recommend B); whether to adopt a deterministic overall-vs-criteria tolerance for evaluation;
  retirement of the legacy Streamlit interface.
- **Production-ready but not live:** shared Redis rate-limit adapter (needs `redis` package, `REDIS_URL`, live validation).
- **Intentionally retained legacy:** Streamlit UI, `src/auth.py`, `DATA_RETENTION_NOTE`, root `Dockerfile` Streamlit entry point.
- W9.13 must re-run the full qualification from a clean tree and confirm the clean-tree CI step passes.

## 32. Paid/live calls
0.
