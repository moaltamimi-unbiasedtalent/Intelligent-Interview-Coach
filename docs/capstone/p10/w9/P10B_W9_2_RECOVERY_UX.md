# P10B-W9.2 — Recovery, Degraded States & In-Place Retry

Implementation record. Scope: make candidate-facing READ surfaces recover gracefully after a backend
outage (the transport/error foundation was built in W9.1). No backend/schema/migration changes. No RC.
0 paid/live provider calls.

- **Baseline:** branch `fix/p10b-w9-1-service-resilience` @ `5984953` (W9.1). New branch
  `fix/p10b-w9-2-recovery-ux` from it. Alembic head `0014_opportunities` (unchanged). RC-P10-002
  immutable.

---

## 1. Pilot defect closed

During human testing the backend became unavailable. Progress showed BOTH "Couldn't load practice
progress." AND a large "Something went wrong" with connection-failure wording; History showed the
catastrophic state with no in-place recovery. W9.2 fixes PAGE BEHAVIOUR: one coherent recoverable
error per page, degraded (not blanked) content when only one region fails, in-place Retry, and
recovery without browser reload or re-login.

## 2. ErrorState inventory (verified)

**14** `ErrorState` usages. Retry-capable **before: 3**, **after: 10** (+7). Classification:

| # | File | Class | Retry before | Retry after | Note |
|---|---|---|---|---|---|
| 1 | `opportunities/OpportunitiesClient.tsx` | A read list | ✅ | ✅ | pre-existing |
| 2 | `opportunities/OpportunityHome.tsx` | A read | ✅ | ✅ | pre-existing |
| 3 | `company/CompanyResearchClient.tsx` | A read (submit) | ✅ | ✅ | pre-existing |
| 4 | `progress/ProgressClient.tsx` (memory) | A read | ❌ | ✅ | redesigned (§4) |
| 5 | `progress/ProgressClient.tsx` (practice, section) | A read | ❌ | ✅ | new section error (§4) |
| 6 | `progress/ProgressClient.tsx` (both, page) | A read | ❌ | ✅ | new page-level (§4) |
| 7 | `interview/HistoryClient.tsx` | A read list | ❌ | ✅ | §5 |
| 8 | `interview/HistoryDetailClient.tsx` | A read (404 stays not-found) | ❌ | ✅ | retry only on service error |
| 9 | `interview/InterviewReport.tsx` | A read | ❌ | ✅ | idempotent report GET |
| 10 | `preparation/SourcesClient.tsx` | A read | ❌ | ✅ | knowledge GET |
| 11 | `memory/MemoryManager.tsx` (Settings) | A read | ❌ | ✅ | memory GET |
| 12 | `interview/PracticeClient.tsx` (loadError) | A read (session load via `ctrl.reload`) | ❌ | ✅ | GET reload, no write replay |
| 13 | `agent/AgentPrepareWorkspace.tsx` | D not-found + B write | ❌ | ❌ | intentionally non-retryable (§7) |
| 14 | `review/AgentInspector.tsx` | reviewer/diagnostic | ❌ | ❌ | deferred (§7) |
| — | `review/RagDiagnosticsClient.tsx` | reviewer/diagnostic | ❌ | ❌ | deferred (§7) |
| — | `review/EvaluationClient.tsx` | reviewer/diagnostic | ❌ | ❌ | deferred (§7) |

(Progress is counted once in the "14" grep as one file usage; the redesign renders up to 3 distinct
`ErrorState` instances — a page-level one when both fail, or per-region section ones — so the rendered
ErrorState count is higher than the source-usage count. Rows 4–6 describe those rendered instances.)

## 3. Intentionally non-retryable surfaces (and why)

- **`AgentPrepareWorkspace`** — the `ErrorState` shown is the *not-found* case (a bookmarked run that
  no longer exists); it already offers "Start new preparation". A generic Retry would just 404 again.
  The other error path there is a chat/action **write** (send/resume) — never auto-retried.
- **`/review/*` reviewer/diagnostic surfaces** (`AgentInspector`, `RagDiagnosticsClient`,
  `EvaluationClient`) — read-only and safely refetchable, but **not candidate-facing** (developer/
  reviewer console). Out of W9.2's candidate-recovery scope; W9.3 governs `/review` visibility.
- **All write/mutation error states** (e.g. memory delete, feedback submit, interview answer submit)
  are never given an auto-Retry — writes must not be replayed.

## 4. Progress — architecture before / after

**Before:** `PracticeProgress` (child) silently owned the `/progress` network lifecycle and rendered a
small non-recoverable "Couldn't load practice progress." on error; `ProgressClient` (parent)
independently owned the `/memory` lifecycle with a non-retry `ErrorState`. Two independent lifecycles →
on a full outage, two competing error messages; no coordinated degraded/recovery state.

**After:** `ProgressClient` owns BOTH read lifecycles (`/progress` + `/memory`) via one small explicit
`Resource<T>` shape (`{status, data, error, retrying}`) per region, each with its own
`AbortController` ref (latest-wins). `PracticeProgress` is now a **pure presentational** component
(`{ data }`). No global state, no server-side endpoint merging — the resources stay logically
independent. Errors render through the W9.1 truthful taxonomy (`t(stateKeyForError(err.kind))`).

## 4a. Progress state matrix (implemented + tested)

| Practice | Memory | UI |
|---|---|---|
| loading | loading | memory skeleton; practice quiet |
| success | loading | practice tiles + memory skeleton |
| loading | success | memory content; practice appears when ready |
| success | success | both visible |
| **error** | success | **section** practice error + Retry; memory content usable |
| success | **error** | practice tiles; **section** memory error + Retry |
| **error** | **error** | **ONE page-level** error + one Retry (reloads both) |
| empty (0 interviews) | — | practice renders nothing (not an error) |
| — | empty (0 memories) | memory empty state (not an error) |

Zero practice sessions and zero saved memories are valid empty data, never errors.

## 5. History changes

`HistoryClient` refactored to a race-safe `load(isRetry)` (AbortController ref, latest-wins), an
in-place Retry using the W9.1 taxonomy (`t(stateKeyForError(err.kind))`), and a `retrying` state.
Empty history stays an **EmptyState** ("No completed interviews yet"), never an error. Unmount aborts
the pending request. `HistoryDetailClient` keeps its distinct **not-found** state for 404 (never
retried as a service error); only genuine service/network/server errors get an in-place Retry.

## 6. Other surfaces changed

`InterviewReport`, `SourcesClient`, `MemoryManager` (Settings), `PracticeClient` (session-load via the
existing `useInterview().reload()`) — each refactored to a race-safe re-runnable GET with an in-place
Retry + `retrying` state and AbortController cleanup. No IA/navigation/copy-hierarchy/empty-state
changes; no write error state touched.

## 7. Shared `ErrorState` UX (accessibility)

`components/ui/States.tsx` `ErrorState` gained (backwards-compatible): `variant` ("page" default |
"section" compact inline for a degraded region), `retrying` (disables the Retry button + `aria-busy`,
so repeated clicks cannot stack loads), and `retryLabel`/`retryingLabel`. Retry is a real keyboard-
accessible `<button>`; technical details (reference id) stay secondary in a `<details>`; no stack/
internal detail is exposed. `role="alert"` is retained, and the design guarantees at most ONE alert at
a time in the failure cases (both-fail collapses to a single page-level error), avoiding duplicate
screen-reader announcements.

## 8. Auth / session recovery

Unchanged authorization architecture. A temporary outage never clears session state: read failures are
classified `unreachable`/`server`/`unavailable` (W9.1) and never a 401, so `AuthProvider` stays
`unknown` (not `unauthenticated`) and `RouteGuard` keeps rendering the route (no redirect to sign-in).
When the backend returns, the same valid HttpOnly session resolves and Retry recovers the read in
place. Proven by the E2E (auth `/auth/me` stays valid throughout; URL stays on `/progress` and
`/history` after recovery) and by backend `eval_restart_recovery`.

## 9. Request / race / abort behaviour

Each surface: a new load aborts the previous in-flight controller (no duplicate concurrent loads); the
settle path checks `signal.aborted` so a stale response can never overwrite a newer success; the Retry
button is disabled while `retrying`; unmount aborts the pending request; there is no infinite retry
loop (a manual Retry starts one fresh bounded cycle; W9.1's transport retry is separately bounded).

## 10. Tests added

Frontend unit:
- `tests/progress-recovery.test.tsx` — P1 both success; P2 practice-fail/memory-ok (memory usable,
  section error, Retry, no page catastrophic); P3 memory-fail/practice-ok; P4 both fail → one
  page-level error + one Retry, no "check your connection"; P5 retry recovers in place, good region
  intact; P6 aborted/late response dropped; P7 unmount aborts.
- `tests/history-recovery.test.tsx` — H1 truthful error + Retry; H2 retry renders + clears; H3 empty
  list is empty state not error; H4 unmount aborts; H5 reference id in technical details.
- `tests/progress.test.tsx` — updated the failure test to the truthful taxonomy + Retry.

E2E: `e2e/service-recovery.spec.ts` — Progress outage → ONE truthful recoverable error → Retry recovers
in place (same route, no reload/login); Progress one-region-fail degraded; History outage → recover;
390px mobile render of the error/Retry.

## 11. Commands & results

- Frontend: `npm run typecheck` clean; `npm run lint` clean; `npm test` (vitest) **320 passed, 56
  files** (was 308; +12 recovery tests); `npm run build` success (37 static pages).
- E2E: `E2E_PORT=3100 npx playwright test service-recovery.spec.ts` **4/4**; full suite **125 passed**
  (was 121; +4 W9.2 recovery specs).
- Backend (no W9.2 changes): targeted regression (`test_service_resilience_w9_1`,
  `test_history_idempotency`, `test_api`, `test_service_progress`, `test_career_history`,
  `test_career_chat_schema`) **0 failed** (hermetic). The 13 `.env` `OPENROUTER_MODEL_*` artifact
  failures are unchanged and isolated (see W9.1 record); W9.2 added no backend code.
- Evaluators: `eval_release_candidate` 27/27, `eval_identity_platform` (1.0), `eval_i18n_l10n`,
  `eval_security` — all PASS, 0 paid/live.

## 12. Accessibility assessment

Retry is a keyboard-focusable `<button>` with `disabled`/`aria-busy` while retrying; `role="alert"`
surfaces the error to assistive tech; at most one alert is shown per failure case (no double
announcement); the reference id lives in a secondary `<details>`; the section variant is a compact
inline box (not a giant catastrophic card) so a degraded region reads proportionately. Mobile (390px)
render verified.

## 13. Security / privacy assessment

No authz/ownership/HITL/provenance change; no write is ever auto-replayed; owner-scoped reads stay
owner-scoped; 404 stays a safe not-found (never another user's data); error bodies expose only a safe
message + request id. CORS/auth unchanged from W9.1.

## 14. Known limitations

- Surface **chrome** strings on Progress/History/etc. (headings, labels, "Something went wrong",
  "Try again") remain English; only the error MESSAGE is routed through the localized taxonomy where
  touched. Full surface localization is **W9.6**.
- Reviewer/diagnostic `/review/*` surfaces are not yet retry-wired (not candidate-facing; W9.3 governs
  `/review`).
- Practice's rich in-flow action errors (answer submit, report generate) are writes and remain
  non-retryable by design.

## 15. Confirmations

0 paid/live provider calls. No migration. No RC created. RC-P10-002 immutable. W9.3 not started.

## 16. W9.3 handoff

W9.3 (Security/menu investigation & remediation) should gate the `/review` menu entry and the
`/review/rag` + `/review/evaluation` pages (and the unauthenticated `knowledge/diagnostics` +
`evaluation/latest` endpoints) behind `platform_role`/a reviewer capability, mirroring the Admin item;
add tests asserting a BASIC user neither sees the `/review` menu item nor loads those endpoints; and an
E2E asserting no privileged nav item renders for a normal user. See `P10B_W9_SECURITY_AUDIT.md`.
