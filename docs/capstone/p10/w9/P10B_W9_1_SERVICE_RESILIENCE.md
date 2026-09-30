# P10B-W9.1 — Service Resilience & Truthful Error Handling

Implementation record. Scope is strictly W9.1 (the error/resilience foundation). No product
pages were redesigned; Progress/History page-level recovery and duplicate-error removal are
W9.2. No RC created. 0 paid/live provider calls.

- **Baseline SHA:** `main` @ `80354f3` (PR #100 merged; Alembic head `0014_opportunities`).
- **Branch:** `fix/p10b-w9-1-service-resilience` (from `docs/p10b-w9-audit` @ `334ffbd`, which
  carries the committed W9 audit docs).
- **Migrations:** none (none required).

---

## 1. Root causes addressed

- **PF-01 (P1):** an otherwise-unhandled 500 was produced by Starlette's `ServerErrorMiddleware`,
  which runs OUTSIDE the user middleware, so the response bypassed `CORSMiddleware` and
  `RequestIdMiddleware`. Cross-origin, the browser blocked the header-less response and `fetch()`
  rejected, so the frontend classified a **server bug** as a **network failure** and told the
  candidate to "check your connection."
- **PF-02 (P1):** CORS was installed conditionally (`if settings.frontend_origins:`) and only
  production failed fast when it was missing, so a mis-set/absent allow-list could make every error
  look like a browser network failure.
- **Frontend taxonomy too coarse:** every failed `fetch()` became `kind: "network"` with copy that
  blamed the user's connection; there was no offline/unreachable/server/rate-limit distinction and
  no bounded retry.

## 2. Middleware architecture — before / after

**Before** (`add_middleware` prepends; framework wraps user middleware in `ServerErrorMiddleware`):

```
ServerErrorMiddleware (base-Exception -> 500, OUTERMOST)   <- 500 built here, no CORS/req-id
  SecurityHeaders -> RequestId -> CORS -> ExceptionMiddleware -> routes
```
Handled typed errors (422/409/503/404/401/403) returned through CORS and got headers; an
**unhandled 500 did not** (no `Access-Control-Allow-Origin`, no `X-Request-Id` header).

**After** (W9.1) — a new `CatchAllErrorMiddleware` is the INNERMOST user middleware and CORS is
the OUTERMOST:

```
ServerErrorMiddleware (last-resort safety net only)
  CORSMiddleware (OUTERMOST user mw)
    SecurityHeadersMiddleware
      RequestIdMiddleware
        CatchAllErrorMiddleware   <- converts unhandled exceptions to the safe 500 envelope
          ExceptionMiddleware (typed handlers) -> routes
```
`CatchAllErrorMiddleware` catches any otherwise-unhandled exception and returns the single safe
envelope from INSIDE the stack, so the response flows back out through `RequestId` (stamps
`X-Request-Id`) and `CORS` (stamps `Access-Control-Allow-Origin`). The registered
`@app.exception_handler(Exception)` remains as a last-resort net returning the identical contract
(`safe_internal_error_response`).

Files: `src/api/main.py` (order + CORS added last), `src/api/middleware.py`
(`CatchAllErrorMiddleware`), `src/api/exception_handlers.py` (shared `safe_internal_error_response`).

## 3. CORS policy

- Exact configured allow-list only; **never** wildcard-with-credentials
  (`allow_origins=list(settings.frontend_origins)`, `allow_credentials=True`).
- **Dev/test:** safe localhost defaults when `FRONTEND_ORIGINS` is unset (`ApiSettings.from_env`);
  fully testable.
- **Staging & production:** `enforce_runtime_config()` now fails fast for **both** environments when
  a required critical (incl. `FRONTEND_ORIGINS`) is missing — the app refuses to boot rather than
  serving header-less/permissive responses (previously only production raised). File:
  `src/api/env_validation.py`.
- CORS is installed as the outermost middleware so its headers reach **every** eligible response,
  including the catch-all 500.

## 4. Backend error contract

One safe envelope everywhere: `{"error": {"code", "message", "request_id"}}`. Distinguishable codes
preserved/covered: `unauthorized` (401), `forbidden` (403), `not_found` (404),
`conflict`/`duplicate_submission` (409), `validation_error`/`invalid_request`/
`missing_interview_handoff_config` (422), `not_configured`/`service_unavailable`/`persistence_error`/
`session_unreadable` (503), and `internal_error` (500). Expected HTTP errors keep their status —
they are never converted to a 500. No stack trace, exception text, SQL, path, secret or provider
payload is ever returned (verified by test).

## 5. Frontend error taxonomy — before / after

**Before:** `network | validation | conflict | unavailable | server | unknown`; every fetch failure
→ `network` → "We couldn't connect right now. Please check your connection and try again."

**After** (`frontend/lib/api/errors.ts`):
`offline | unreachable | unauthenticated | forbidden | notFound | validation | conflict |
rateLimited | unavailable | server | unknown`.

| Condition | kind | candidate-facing meaning |
|---|---|---|
| device reports offline | `offline` | "You're offline. Check your internet connection and try again." |
| fetch failed, browser online | `unreachable` | "Ask4Mo can't reach the service right now…" (never blames the user) |
| 401 | `unauthenticated` | session/auth copy; not auto-retried |
| 403 | `forbidden` | permission copy (not a connectivity failure) |
| 404 | `notFound` | contextual not-found |
| 422/other 4xx | `validation` | input rejected |
| 409 | `conflict` | conflict copy |
| 429 | `rateLimited` | honours `Retry-After` |
| 502/503/504 | `unavailable` | temporary Ask4Mo unavailability |
| other 5xx received | `server` | "Ask4Mo hit a problem while processing that request…" (not network) |

`offline` vs `unreachable` is decided by `navigator.onLine` in `client.ts` via the pure
`unreachableError(isOnline)` helper. The new shared strings were added to the i18n `states`
namespace across **all 7 locales** (`stateKeyForError(kind)` maps a kind to its `states.*` key) so
W9.1 adds no new hardcoded-English debt; `ApiError.userMessage` remains the English fallback.
Comprehensive surface localization is W9.6.

## 6. Retry policy (`frontend/lib/api/retry.ts`)

Conservative, transport-level, bounded — never autonomous repetition of expensive work.
- **Only idempotent GET/HEAD** are auto-retried. Writes (POST/PATCH/DELETE) are **never** retried —
  so career chat, agent messages, Practice answers, uploads, handoffs and memory mutations can
  never execute twice from a retry.
- Retryable conditions (GET only): `unreachable`, `server`, `unavailable`, `rateLimited`. `offline`
  and ordinary 4xx are never retried.
- **≤ 2 additional attempts** (3 total). Exponential backoff (300ms base, ×2, cap 4000ms) + small
  jitter; **honours `Retry-After`** for 429/503. Timing (`wait`) and jitter (`rand`) are injectable
  for deterministic tests.
- **AbortController** stops retries immediately (already-aborted signal, abort during backoff, and
  an `AbortError` from the attempt all short-circuit with no further attempts).

## 7. Request-ID / observability

`RequestIdMiddleware` still generates a server-side UUID per request (client-provided ids ignored)
and now, because it is outside the catch-all, stamps `X-Request-Id` on success, expected errors AND
catastrophic 500s. The catch-all also stamps it defensively. The id is echoed in every error body
and correlates the single safe log line (class name only; traceback in dev only). `X-Request-Id`
stays in `expose_headers`. No raw request/response logging was added; no private data added for
observability.

## 8. Files changed

Backend:
- `src/api/main.py` — middleware order (CatchAll inner, CORS outermost), comments.
- `src/api/middleware.py` — `CatchAllErrorMiddleware` + module logger.
- `src/api/exception_handlers.py` — shared `safe_internal_error_response`; unhandled handler reuses it.
- `src/api/env_validation.py` — staging joins production in fail-fast on criticals.

Frontend:
- `frontend/lib/api/errors.ts` — new taxonomy, `unreachableError`, `parseRetryAfter`,
  `stateKeyForError`, `retryAfterMs`.
- `frontend/lib/api/retry.ts` — NEW bounded retry module.
- `frontend/lib/api/client.ts` — offline/unreachable classification, Retry-After capture, GET retry
  wiring; upload never retried.
- `frontend/lib/i18n/messages/{en,de,fr,es,it,pt,nl}.ts` — new `states` error keys (all 7 locales).

Tests:
- `tests/test_service_resilience_w9_1.py` — NEW (backend).
- `frontend/tests/api-errors.test.ts` — extended (taxonomy, offline/unreachable, Retry-After, keys).
- `frontend/tests/api-retry.test.ts` — NEW (retry policy).
- `frontend/tests/api.test.ts`, `frontend/tests/career-api.test.ts` — updated to the truthful
  `unreachable` classification (behavioural alignment, not a weakening).
- `frontend/e2e/service-resilience.spec.ts` — NEW (E2E).

Docs: this file; `P10B_W9_CURRENT_STATE.md`, `P10B_W9_IMPLEMENTATION_PLAN.md` updated.

## 9. Tests added / results

- Backend `tests/test_service_resilience_w9_1.py` (**7 tests, all pass**): unhandled-500 carries CORS + request-id
  + safe body (no leak) for an allowed origin; disallowed origin not reflected; normal response has
  request-id + CORS; 404 stays 404 and 422 stays 422 (not 500); staging AND production fail closed
  without `FRONTEND_ORIGINS`.
- Frontend `api-errors.test.ts` + `api-retry.test.ts`: offline vs unreachable; 500 is `server` not
  network; 401/403/404/409/422/429; `Retry-After` parse + carry; request-id propagation; safe GET
  retry; retry exhaustion (bounded); no retry for POST; no retry for ordinary 4xx; abort cancels
  retry; deterministic backoff.
- E2E `service-resilience.spec.ts` (2 tests): unreachable API → truthful Ask4Mo wording (never
  "check your connection") → Retry recovers without reload; browser-offline → offline wording.

## 10. Security / privacy assessment

- No authentication/authorization change; owner-scoping, HITL, provenance, scoring untouched.
- Production/staging **fail closed** on missing CORS config; no wildcard-with-credentials.
- 500 responses expose only a generic message + request id — verified no stack/SQL/path/secret leak.
- No raw request/response logging; the correlation id is a random UUID, not user data.
- CORS is transport policy, not authorization — the server-side authz boundary is unchanged.

## 11. Known limitations (handed to later waves)

- **Surfaces still render English error copy.** The new strings live in the i18n catalogue, but most
  surfaces still show `ApiError.message`/`userMessage` (English). Wiring every surface to
  `stateKeyForError` is **W9.6**.
- **Page-level recovery** (Progress/History wired Retry, duplicate-error removal, degraded regions)
  is **W9.2**. W9.1 proves the transport foundation on the already-wired Opportunities surface.
- The `.env` `OPENROUTER_MODEL_*` local-override test artifact (13 failures) is unchanged and out of
  scope here; new W9.1 tests are hermetic (they neutralise those vars / don't depend on them). Full
  release-suite hermeticity is W9.12.

## 12. Verification commands & final results

All commands run locally; **0 paid/live provider calls**.

**Backend** (`ANONYMIZED_TELEMETRY=False PYTHONPATH="$PWD" .venv/bin/pytest -q`):
- **2468 tests collected** (was 2461; +7 new W9.1 tests).
- As-is from the project cwd: **13 failed, 3 skipped, 2452 passed.** The 13 failures are exactly the
  pre-existing `.env` `OPENROUTER_MODEL_*` override artifact in 5 files (`test_config`,
  `test_model_registry`, `test_evaluation_service`, `test_interview_service`, `test_report_service`)
  — **isolated re-run of those 5 files with the overrides unset = 0 failed (exit 0)**, proving they
  are an environment artifact, not product defects. **No W9.1 regression** (the earlier
  `test_history_idempotency` interaction was resolved by asserting the new safe-500 contract; it now
  passes, 10/10).
- `ruff check .` — clean.
- Targeted: `tests/test_service_resilience_w9_1.py` 7/7; `tests/test_api.py`,
  `tests/test_p8_hardening.py`, `tests/test_auth_failclosed.py`, `tests/test_career_chat_schema.py`
  (PR #100 regression) all pass.

**Frontend** (`cd frontend`):
- `npm run typecheck` — clean. `npm run lint` — clean.
- `npm test` (vitest) — **308 passed, 54 files** (was 282; +`api-retry.test.ts` 15, +`api-errors.test.ts`
  extended to 17).
- `npm run build` — success, 37 static pages.
- `E2E_PORT=3100 npx playwright test` — **121 passed** (was 119; +2 in `service-resilience.spec.ts`).

**Deterministic evaluators** (all PASS, 0 paid/live): `eval_release_candidate` (27/27),
`eval_security` (prompt-injection detection), `eval_identity_platform` (safety invariants = 1.0),
`eval_i18n_l10n`, `eval_rate_limits`.

## 13. Confirmations

- **0 paid/live provider calls.** No RC created. No migration. RC-P10-002 unchanged/immutable.
- Not started: W9.2+, Russian, full localization, Opportunity/Welcome/Tutorial changes, P10C.

## 14. W9.2 handoff

W9.2 should: wire `onRetry` (to `useCallback` refetch) across the 11 unwired `ErrorState` usages
(esp. Progress/History); collapse Progress's two independent error UIs into one page-level banner;
render page regions independently so a single failed fetch does not blank the page; add a
restart-recovery E2E for Progress/History; and begin routing surfaces through `stateKeyForError`
where it overlaps with W9.6.
