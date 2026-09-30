# P10B-W9 — Service Resilience & Truthful Error Handling Audit

Audit phase. No runtime code changed. Focus: pilot finding #4 (backend unavailable →
"Something went wrong" + "check your connection" on Progress/History) and #13 (500 masked as
network). Middleware layering was verified firsthand against `src/api/main.py` +
`src/api/exception_handlers.py`.

---

## 1. Frontend/backend failure taxonomy (current)

**Frontend `ApiError.kind`** (`frontend/lib/api/errors.ts:8-14`): `network | validation | conflict |
unavailable | server | unknown`. There is **no `offline` kind** and **no `navigator.onLine`
check** anywhere.

| Condition | kind | user-facing string |
|---|---|---|
| `fetch` throws (backend down / DNS / offline / **CORS-blocked 5xx**) | `network` | "We couldn't connect right now. Please check your connection and try again." |
| 401 / 403 / 404 / 422 / 429 | `validation` | "Please check the information and try again." |
| 409 | `conflict` | "This is already being processed. Please wait a moment and try again." |
| 500 / 502 (reaching the client) | `server` | "That request couldn't be processed. Please try again." |
| 503 | `unavailable` | "That feature isn't available right now. Please try again shortly." |
| body parse fallback | `unknown` | "Request failed." |

Evidence: `frontend/lib/api/errors.ts:39-61,73-74`; `frontend/lib/api/client.ts:104-144`
(`request()`), `:84-102` (`upload()`).

**Backend error envelope** (`src/api/exception_handlers.py`): handled types map to safe envelopes —
`ValidationError`→422, `Configuration/Unavailable/Persistence`→503, `Conflict/DuplicateSubmission`→409,
`Session*`→422/503, `HTTPException`→404/401/403, `RequestValidationError`→422. The catch-all
`@app.exception_handler(Exception)`→500 (`:115-133`) logs only class name (`exc_info` in dev only),
puts `request_id` in the body, and returns a generic message. All safe.

## 2. Progress / History screenshot analysis (finding #4)

**Progress** = `frontend/app/progress/page.tsx` → `ProgressClient` which also renders
`PracticeProgress`. **Two independent fetches:** `api.memory.list` (`ProgressClient.tsx:41`) and
`api.progress.get` (`PracticeProgress.tsx:22`). Under a backend outage both fail and render, stacked:
1. `PracticeProgress.tsx:37` → *"Couldn't load practice progress."* (muted line)
2. `ProgressClient.tsx:95` → `ErrorState` → *"Something went wrong"* + *"We couldn't connect right now. Please check your connection and try again."*

This is exactly the pilot screenshot. **Duplicate catastrophic messaging is a confirmed defect.**
Neither `ErrorState` is given `onRetry`, and both fetch once in `useEffect`, so **recovery requires a
full page reload** (no re-login — see §6).

**History** = `frontend/app/history/page.tsx` → `HistoryClient` (one fetch, `HistoryClient.tsx:20`).
One `ErrorState` at `:42`, no `onRetry`, fetch inline in `useEffect` → full-page error, reload to
recover. No duplicate message (single call).

## 3. Generic network-error analysis + 500/CORS analysis (finding #13)

The frontend **does** separate server errors from connectivity: a well-formed 500 that reaches JS is
classified `server` ("That request couldn't be processed"), *not* the connect message. The connect
message appears only when `fetch()` itself rejects and no response reaches JS
(`frontend/lib/api/client.ts:126-134`). So the question is purely: **does a 500 reach the browser?**

**Firsthand-verified mechanism (two independent causes):**

1. **Config-independent (P1).** `@app.exception_handler(Exception)` is registered for the *base*
   `Exception` (`exception_handlers.py:115`). Starlette installs base-`Exception`/500 handling on the
   **outermost `ServerErrorMiddleware`**, above all user middleware. Effective nesting
   (outer→inner): `ServerErrorMiddleware → SecurityHeaders → RequestId → CORS → ExceptionMiddleware →
   routes` (`add_middleware` prepends; `main.py:108-117`). A truly *unhandled* exception propagates
   up past `CORSMiddleware` (which never sees a response to post-process), so the 500 JSONResponse is
   emitted by `ServerErrorMiddleware` **without `Access-Control-Allow-Origin` and without the
   `X-Request-Id` response header**. The browser blocks it cross-origin → `fetch` throws → frontend
   `network` → "check your connection." Handled typed errors (422/409/503/404/401/403) run in the
   inner `ExceptionMiddleware`, return *through* CORS, get headers, and classify correctly.
2. **Config-dependent (medium).** CORS is added conditionally: `if settings.frontend_origins:`
   (`main.py:107-115`). If `FRONTEND_ORIGINS` is empty/misconfigured in a deployment, **no** response
   carries CORS headers — even handled 4xx/503 — so *every* error masks as `network`. This is the
   most likely explanation for the pilot's environment showing "check your connection" on multiple
   pages at once during a backend blip.

**Net:** PR #100 removed one *trigger* of a 500 (the schema mismatch) but not the *class* — the next
unhandled 500 reproduces the identical false "connection" message. Both causes must be closed.

## 4. `ErrorState` retry/recovery assessment

`ErrorState` (`frontend/components/ui/States.tsx:59-89`) renders Retry only when `onRetry` is passed,
and a collapsible "Reference: {id}" only when `requestId` is truthy. Retry wiring across 14 usages:

**Wired (3):** `OpportunitiesClient.tsx:81`, `OpportunityHome.tsx:89`, `CompanyResearchClient.tsx:158`.
**No retry (11):** `ProgressClient.tsx:95`, `MemoryManager.tsx:81`, `HistoryClient.tsx:42`,
`HistoryDetailClient.tsx:70`, `InterviewReport.tsx:50`, `PracticeClient.tsx:89`,
`EvaluationClient.tsx:38`, `RagDiagnosticsClient.tsx:40`, `SourcesClient.tsx:51`,
`AgentInspector.tsx:73`, `AgentPrepareWorkspace.tsx:104`.

`onRetry` is optional (no dead-prop bug), but the UX result is that most pages offer no in-place
recovery. `ProgressClient` and `MemoryManager` already have a `load` callback that simply isn't passed.

**X-Request-Id surfacing (finding, P2):** request ids are generated server-side
(`src/api/middleware.py:24`) and exposed via `expose_headers=["X-Request-Id"]` — but only on responses
that pass through CORS. For the two cases users most need a reference (network, unhandled 500) the id
is `null`. Fixing §3 makes the id reachable for `server`/`unavailable`.

## 5. Retry/backoff + degraded content

- **No automatic retry/backoff** exists (no retry loop, no backoff, no `navigator.onLine`, no
  react-query/SWR). Only the 3 manual "Try again" buttons. An `Idempotency-Key` path exists for
  interview creation (`client.ts:166-173`), which would make POST retries safe.
- **No partial/degraded render** on multi-fetch pages: a memory failure blanks the whole Progress
  page (`ProgressClient.tsx:97` gates the entire ready branch), even if `/progress` succeeded.

## 6. Recovery + session survival (positive findings)

- **Sessions survive a backend outage and restart.** Auth sessions are DB-backed
  (`src/persistence.py:347-357` `AuthSession`; `src/auth_repository.py:493-505`), not in-process, so a
  restart does not invalidate the HttpOnly cookie. `eval_restart_recovery` PASSes (preferences,
  memory, documents, interviews, memberships, sessions, reports all survive restart *and* restore).
- **No forced logout on outage.** `AuthProvider.refresh` sets `unauthenticated` only on a definitive
  401 (`frontend/components/auth/AuthProvider.tsx:41-57`); any other failure → `unknown`, which
  `RouteGuard` renders (`frontend/components/auth/RouteGuard.tsx:50-53`). So a backend blip does not
  bounce the user to sign-in. Good — keep this.

The gap is purely at the **frontend fetch layer**: it fetches once and has no path back to success
without a reload.

## 7. Recommended resilience architecture (bounded, truthful — NO fake offline mode)

1. **Truthful taxonomy at the source (fixes PF-01/02/06/07).**
   - Guarantee CORS + `X-Request-Id` on **every** response including the `ServerErrorMiddleware` 500:
     either add CORS as the outermost layer, or register a 500-formatting layer *inside* CORS, or wrap
     the app so the base-`Exception` response is post-processed for headers. Make CORS
     unconditional-with-safe-default and **fail-fast in production** if origins are unset, plus a test
     asserting an allowed-origin 500 carries `Access-Control-Allow-Origin` + `X-Request-Id`.
   - Frontend: split `network` into `offline` (only when `navigator.onLine === false`) vs `unreachable`
     ("We're having trouble reaching Ask4Mo" — server-side, not the user's internet). Give
     401/403/404/429 distinct messages; honour `Retry-After` on 429. **Localize all of these**
     (they currently bypass i18n — see LOCALIZATION_AUDIT).
2. **Bounded retry (fixes PF-08).** Small capped retry in `request()`/`upload()`: idempotent GETs (and
   POSTs already carrying `Idempotency-Key`) on `network`/`502`/`503`, max 2–3 attempts, exponential
   backoff + jitter, never on 4xx; subtle "retrying…" state (i18n `retry`/`retrying` keys exist).
3. **Degraded states, not all-or-nothing (fixes PF-03/PF-04-partial).** Render each page region
   independently; Progress shows whichever of memory / practice-progress succeeded; collapse duplicate
   top-level catastrophic messaging to a single page-level banner.
4. **Universal in-place recovery (fixes PF-04/PF-05).** Give every `ErrorState` an `onRetry` wired to a
   `useCallback` refetch (refactor inline `useEffect` fetches to reusable `load()`), optional
   refetch-on-focus. Backend restart then recovers with a click, never a reload or re-login (session
   already survives, §6).
5. **Always show a reference on server faults (PF-06).** Once §1 lands, surface the reference id for
   `server`/`unavailable` so pilots can quote it.

**Explicitly not recommended:** a client-side offline cache / "offline mode" for private preparation
data — it would violate the no-private-data-in-`localStorage` rule and mask real server faults.

## 8. Deterministic evidence captured

`eval_restart_recovery` PASS (DB-layer survive-restart + survive-restore; 0 paid/network).
The gap it does **not** cover — frontend auto-recovery — is a W9.2 test target (a Playwright spec that
kills/restarts the API and asserts an in-place Retry restores Progress/History without reload).
