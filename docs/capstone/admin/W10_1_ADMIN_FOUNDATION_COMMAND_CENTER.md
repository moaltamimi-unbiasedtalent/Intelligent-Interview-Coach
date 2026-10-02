# P10B-W10.1 - Admin Shell, Permission & Audit Foundation, Command Center

**Status:** implemented on branch `feat/p10b-w10-1-admin-foundation`; **COMPLETE: merged to `main` in PR #110 (merge commit 301173d, qualified head 26422b9). W10.2 is NOT STARTED.**
Migration-free (Alembic head stays `0014_opportunities`). No new dependency. No paid or live provider call.

## 1. Purpose and scope
W10.1 is the first admin implementation wave. It replaces the single coarse `platform_admin` gate with an explicit, default-deny permission framework, makes privileged audit fail-closed, gives `/admin/providers` an allowlist response, and replaces the one-page console with a capability-aware shell and a truthful Command Center. It does not add support, billing, subscriptions, jobs, knowledge administration, privacy workflows, feature flags or incidents (those are W10.2+).

## 2. Owner decisions honoured
AD-01 admin UI English-only; AD-02 no break-glass (no permission, no code path, guarded); AD-03 mock billing only (untouched); AD-04 provider configuration is externally managed (the console reports, never rotates); AD-08 role presets are code-defined (no role tables, no custom roles).

## 3. Implementation audit (before editing)
Verified against code at `main` e13bfc4: roles `user` / `platform_admin` in `users.platform_role` (`String(32)`, no DB CHECK); one coarse gate `require_platform_admin`; eight admin routes plus reviewer, evaluation, knowledge-diagnostics and `/auth/admin/audit`; the local `_audit` helper and `set_pause` swallowed audit failures (SEC-W10-02); every `set_*` repository method opened its own session and committed (so audit could not be atomic); `/admin/providers` echoed `EMAIL_PROVIDER` raw (SEC-W10-06); `audit_events` already had `request_id`, `actor_user_id`, `target_*`, `result`, `context` (so no schema change was required); `request.state.request_id` came from `RequestIdMiddleware` (W9.1).

## 4. Implementation matrix
| Route | Method | Previous guard | Mutation | Required permission | Audit | Response sensitivity |
|---|---|---|---|---|---|---|
| `/admin/home` | GET | platform_admin | No | `platform.overview.read` | denial only | operational metadata |
| `/admin/users` | GET | platform_admin | No | `platform.users.read` | denial only | account metadata (email) |
| `/admin/users/{id}/role` | POST | platform_admin | Yes | `platform.users.role.assign` | atomic, success | enum change |
| `/admin/users/{id}/tier` | POST | platform_admin | Yes | `platform.subscriptions.manage` | atomic, success | enum change |
| `/admin/users/{id}/status` | POST | platform_admin | Yes | `platform.users.manage` | atomic, success | enum change |
| `/admin/workspaces` | GET | platform_admin | No | `platform.workspaces.read` | denial only | workspace metadata |
| `/admin/privacy-requests` | GET | platform_admin | No | `platform.privacy.read` | denial only | metadata (queue is not operational, SEC-W10-04) |
| `/admin/feedback` | GET | platform_admin | No | `platform.reports.read` | denial only | aggregate counts |
| `/admin/pause` | GET | platform_admin | No | `platform.flags.read` | denial only | booleans |
| `/admin/pause/{capability}` | POST | platform_admin | Yes (in-memory) | `platform.flags.manage` | audit-first, fail-closed | boolean change |
| `/admin/providers` | GET | platform_admin | No | `platform.integrations.read` | denial only | allowlist schema |
| `/admin/audit` | GET | platform_admin | No | `platform.audit.read` | denial only | safe audit metadata |
| `/auth/admin/audit` | GET | platform_admin | No | `platform.audit.read` | denial only | caller's own events |
| `/reviewer/knowledge/*` (5) | GET | platform_admin | No | `platform.knowledge.read` | denial only | knowledge diagnostics |
| `/reviewer/config-versions`, `/reviewer/prompt-lab/*` (3) | GET | platform_admin | No | `platform.ai.read` | denial only | config/experiment metadata |
| `/reviewer/retention/inventory` | GET | platform_admin | No | `platform.privacy.read` | denial only | retention inventory |
| `/evaluation/*` (4) | GET | platform_admin | No | `platform.ai.read` | denial only | offline evaluation metrics |
| `/knowledge/diagnostics` | GET | platform_admin | No | `platform.knowledge.read` | denial only | runtime counts |

27 routes, 0 ungated. `/review/agent` (Agent Inspector) stays owner-scoped and is deliberately not an admin route (W9.3 architecture preserved).

## 5. Permission registry
`src/application/admin_permissions.py` holds the canonical **43** permissions, identical to the W10.0 master-plan list (a test and the evaluator compare the code with the document). No break-glass, impersonation, view-as or content-inspection permission exists. Route code uses named constants so a typo is an import error, and `require_permission` rejects an unregistered string at definition time.

## 6. Role presets (AD-08)
Six code-defined presets: `platform_admin`, `support_operator`, `billing_admin`, `knowledge_admin`, `security_privacy_admin`, `operations_admin`. Each is a frozen subset of the registry; every preset includes `platform.overview.read`. `platform_admin` keeps all pre-W10 legitimate access (overview, users read/manage/role.assign, workspaces read, subscriptions, privacy read, reports read, flags, integrations read, audit read, ai/knowledge read, releases/security read) and holds **no** content-inspection permission. Presets for later waves are deliberately conservative subsets. The role vocabulary in `persistence.PLATFORM_ROLES` is widened to the six presets (plain column, no migration) and a test keeps it identical to the presets.

## 7. Resolver and `require_permission`
`permissions_for_role(role)` is a pure lookup: unknown, empty, `None`, candidate (`user`), wrong-case or padded role strings resolve to the empty set. `require_permission(p)` (in `src/api/dependencies.py`) requires an authenticated principal, an **active** account (a deactivated admin is denied) and the permission in the server-side role's preset. Nothing is read from the browser: spoofed headers or query parameters grant nothing (tested).

## 8. Candidate private-data deny boundary
No admin route, schema or UI component carries CV, document, answer, Mo conversation, memory, evidence, report or preparation-chat fields; there is no impersonation and no break-glass. The evaluator scans the admin schemas and components for such fields and fails on any hit.

## 9. Reviewer, evaluation and knowledge diagnostics decision
These are **admin** (not owner-scoped) surfaces and now require explicit permissions: knowledge diagnostics and readiness need `platform.knowledge.read`; evaluation, config versions and Prompt Lab need `platform.ai.read`; the retention inventory needs `platform.privacy.read`. The candidate's own Agent Inspector remains owner-scoped, exactly as W9.3 decided.

## 10. Route-permission invariant
`src/api/admin_route_invariant.py` discovers every `APIRouter` in `src/api/routes`, selects admin/internal paths (`/admin`, `/reviewer`, `/evaluation`, `/knowledge/diagnostics`, `/auth/admin/audit`) and walks each route's dependency graph for a callable carrying `.permission`. Dependency introspection (not a source regex) means router-level, route-level and nested dependencies all count, and a new admin route without a permission fails the test and the CI evaluator. A synthetic ungated route proves the detector.

## 11. Frontend capability contract
The backend returns the resolved list as `account.admin_permissions` on the authenticated `/auth/me` response (empty for candidates and for inactive accounts). The frontend (`frontend/lib/admin/capabilities.ts`) maps *destinations* to the permission that makes them useful, never roles to permissions, and uses no `localStorage`, `sessionStorage`, IndexedDB or cookie. Tests assert both. A role string alone grants nothing in the UI.

## 12. Admin shell and navigation
`/admin` has a layout with a labelled `nav` showing only operational destinations the server permitted: Overview, Users, Workspaces, Review / Diagnostics, Audit, Provider status. Support, Billing, Subscriptions, Jobs, Knowledge administration, Privacy requests, Incidents and Feature Flags are not listed. The More menu uses the same permission-based visibility. The admin UI is English-only (AD-01). Frontend gating is UX only; the API authorises every request.

## 13. SEC-W10-02 - fail-closed privileged audit
`AccountRepository.set_platform_role/set_tier/set_status` accept an `audit=` spec and add the `audit_events` row to the **same session and transaction** as the state change. If the audit insert or commit fails, the mutation rolls back (tested for role, status and tier with a failing audit row). No distributed transaction is involved. The pause toggle has no database state; it is **audit-first, then apply**, and returns 503 without applying anything if the audit cannot be committed (section 14).

## 14. Route atomicity record
Role, tier and status: atomic. Pause: not a database mutation, so true atomicity does not apply; the guarantee is the ordering (no applied change without a committed audit row). No route was left non-atomic or stopped. Process-local pause is still not durable (SEC-W10-05 closes in W10.11; the Command Center labels it).

## 15. Failed-authorization semantics
A denied request returns 403 and writes a best-effort `admin.access.denied` audit event (actor, permission, method, path, reason, request id). If that audit write fails the failure is logged and access **stays denied**: a failed audit never grants access (tested). Denial auditing covers authenticated callers only; unauthenticated requests are already rejected by the identity layer.

## 16. SEC-W10-03 - canonical event names, request id, safe metadata
`src/application/admin_audit.py` centralises event-name constants (`admin.platform_role_change`, `admin.entitlement_change`, `admin.account_status_change`, `platform.pause_toggled`, `admin.access.denied`; historic names kept so history and existing evaluators remain valid) and `build_audit` rejects unknown names and any context key that looks like a secret or candidate content. Each event records actor, target, result, optional reason, the W9.1 request id (`request.state.request_id`) in the existing `audit_events.request_id` column, and a safe before/after summary (a single enum value). The audit view now returns `request_id` and the context for admin events only. No schema change was needed.

## 17. SEC-W10-06 - provider allowlist schema
`GET /admin/providers` returns `ProvidersResponse` (`src/api/schemas/admin.py`): explicit fields, `extra="forbid"`, no open mapping. Rows carry `provider_id`, `label`, `configured`, `enabled`, `externally_managed`, `writable` (always false), `status`, `health` ("Health not tested"), `live_validation` and a fixed-vocabulary `mode`. Environment values are only read to answer "is it set?" and are never echoed (a sentinel test sets ten secret-like values and asserts none appear). The email row reports `console` or `brevo`, not the raw variable. Configured is not healthy; no provider is contacted.

## 18. Command Center - release and build metadata
Build metadata comes from deployment-injected `APP_GIT_SHA` and `APP_BUILD_TIME` (the API Dockerfile now accepts them as `ARG`/`ENV` build args, a build-metadata aid only, not a dependency) plus the package version and `API_ENV`. Absent values are reported truthfully as `unknown`; values are sanitised to a safe character set; the app never shells out to git.

## 19. Command Center - migration status
The repository's Alembic head is read from the migration scripts on disk and compared with the database `alembic_version`. States: `match`, `mismatch` (with a warning that Ask4Mo never migrates automatically) and `unknown` (scripts or table absent). No migration is ever run.

## 20. Command Center - health, rate limiting, pause, privacy queue
Health is a cheap internal database ping only; provider health is "not tested". Rate limiting is shown as in-memory, per process, unless a shared store is active (it is not live). Pause state is labelled process-local and non-durable. The privacy-request queue is shown as "not available yet" with no count and no fake zero (SEC-W10-04 belongs to W10.10). Diagnostic links appear only for callers with the matching permission. Render makes no network call and no subprocess (tested).

## 21. Test evidence - backend
`tests/test_admin_foundation_w10_1.py`: permission matrix P1-P10 (registry, presets, default deny, vocabulary parity, route invariant incl. a negative control, candidate denial on every admin route, per-role reach, spoofing, deactivated admin, role-assign), audit AUD1-AUD8 (request id, before/after, rollback on audit failure for role/tier/status, pause fail-closed, denial audit, failed denial audit, unknown names, forbidden keys), provider PR1-PR6, Command Center C1-C10. Full backend result: **2603 passed, 3 skipped, 0 failed, 0 errors** (`python -m pytest`, 148.7 s, authoritative summary line captured; 2,606 collected; 37 new). The 3 skips are unchanged and expected: live Adzuna integration (needs `RUN_ADZUNA_INTEGRATION=1` and credentials), a Streamlit-context component render, and a RAGAS adapter test that is skipped because ragas is installed. `ruff check .` clean. Test isolation verified after the run: dev-store fingerprint unchanged and `git status --porcelain` empty.

## 22. Test evidence - frontend
`frontend/tests/admin-shell-w10-1.test.tsx` (A1-A7: server-permitted navigation, six operational destinations and no future ones, candidate denial, role string grants nothing, More menu parity, no storage and no role map, truthful Command Center, provider status, accessibility) plus updated nav-security and more-menu tests. Full frontend result: 73 files, 528 unit tests passing (13 new); `tsc --noEmit`, `next lint`, `next build` and the i18n scanner (0 offenders) clean.

## 23. Test evidence - browser journey
`frontend/e2e/admin.spec.ts` (network-mocked, like the previous admin spec): a platform admin sees the Command Center, build metadata, the six destinations and no future ones, the diagnostic link, the Audit page with request id and before/after, and safe provider status; a limited role sees only its destinations; a candidate is denied; unauthenticated users are redirected. Server authorization and audit are proven by the Python suites against a real SQLite database. Full Playwright result: **200 passed** in the final qualification (serial, `E2E_PORT=3017`, no retries, no timeout changes), confirmed in two further full runs. Disclosure: in one earlier full run the admin journey test failed once (the click on the Audit link did not navigate within 10 s); the same test then failed once more when re-run immediately, and could not be reproduced in 40+ later runs (cold and warm server, with and without tracing) or in the two full suites, so the cause is unproven and it is recorded as an unreproduced intermittent. If it recurs in CI it will be investigated as a W10.1 defect first. Boundary: this journey mocks the network, which is acceptable because permission and audit behaviour are tested against a real database in Python and the browser test verifies capability-aware navigation only. Additionally, the Command Center, Providers and Audit pages were checked once in the browser against a real local backend on a freshly migrated database (migration state `match`, build metadata from injected env, provider rows "Health not tested", no secret in any response).

## 24. W10.1 evaluator
`scripts/eval_admin_foundation.py` (added to CI): canonical count 43 and equality with the design document, no break-glass, six presets as subsets, vocabulary parity, default-deny resolver, every admin route gated, no coarse gate in use, provider schema has no secret-like fields or open dict, audit fail-closed wiring, event constants only, request id flow, Command Center never shells out or migrates, privacy queue withheld, pause labelled, frontend has no role map or storage, no candidate-content fields in the admin UI, only six operational destinations, no migration, no new infrastructure dependency. `scripts/eval_admin_design.py` stays green (two W10.0 "not yet built" checks were updated to "built as designed"). Result: all 28 CI evaluators pass, including `eval_admin_foundation` (33 checks) and `eval_admin_design`; `eval_realtime_voice` and `eval_voice_experience` now read the provider status from its new schema/builder files (marker strings updated, same invariants).

## 25. Accessibility
Semantic `nav` with an accessible name, `aria-current="page"`, native links (keyboard operable), visible focus rings, table captions and column/row headers, status carried by text ("Up to date", "Revision mismatch", "Configured", "Health not tested") with a decorative marker, `role="alert"` for the migration warning and failed loads. No new colour-only signal.

## 26. Performance impact
Measured with `next build` on `main` e13bfc4 versus this branch (First Load JS): `/admin` 1.57 kB / 108 kB to 2.7 kB / 113 kB (re-measured in the final qualification: unchanged); the four new admin sub-routes are 1.95 to 2.19 kB (about 109 kB each) and load only for operators; `/review` 1.77 kB to 2.16 kB (guard now permission-aware); shared-by-all 102 kB to 103 kB. Extra requests: none on candidate pages; the Command Center issues one `GET /admin/home` (the old console issued five requests on one page; each sub-page now issues one). Server side: `/admin/home` adds one cheap `SELECT 1`, one `alembic_version` read and an Alembic script-directory read (cached by the OS); no provider call. No bundle optimisation was attempted (pending item).

## 27. Security review
Default deny at one choke point; permissions resolved only from the server-side role; deactivated accounts denied; no browser-supplied role or permission is honoured; privileged changes audited atomically; failed denial audit cannot grant access; provider response is an allowlist; Command Center exposes no secret, no candidate content and makes no provider call; no break-glass. Residual risks are in section 30.

## 27a. Privacy review
Admin data remains metadata. No candidate content field was added to any schema or screen. Audit context stores only enum before/after values, reasons capped at 200 characters and request ids. The denial audit records the path and method, never request bodies or query values.

## 28. Documentation changes
This document; matrix rows relabelled; master plan section 33 and roadmap row updated; `docs/README.md`, `CLAUDE.md` (durable rules); `deploy/Dockerfile.api` build args; evaluator and CI step.

## 29. Defects closed and not closed
Closed: SEC-W10-02 (atomic fail-closed audit), SEC-W10-03 (canonical events, request id, denial audit), SEC-W10-06 (provider allowlist). **Not closed (by design):** SEC-W10-01 (deactivation does not revoke sessions; W10.2), SEC-W10-04 (privacy queue is not operational; W10.10), SEC-W10-05 (process-local pause; W10.11).

## 30. Accepted limitations and risks
Admin role assignment has no second approver or step-up. This is not a W10.1 failure: W10.0 did not require it in this wave, and it is recorded as a security-hardening consideration for W10.13 (role-assignment workflow design may pull it into W10.2); `platform.users.role.assign` is held only by `platform_admin`. Model-profile activation approval belongs to the W10.7 AI administration design and is separate. The five non-`platform_admin` presets can be assigned but only reach the surfaces that exist today (overview, users, workspaces, providers, audit, diagnostics) until their waves land. Denial auditing can create rows for repeated probing by authenticated candidates (bounded by the existing auth rate limits; retention policy arrives with W10.13). `/admin/audit` returns the 500 most recent events at most. Distributed rate limiting and durable pause remain not live. The browser journey uses mocked network responses (backend behaviour is covered by the Python suites).

## 31. Standing items unchanged
PRIV-W9-01 and PRIV-W9-02 OPEN; POLICY-01 and POLICY-02 unchanged; LEGACY-01; A11Y-W9-13-01; native-Russian and legal-copy review, live generated-language validation, metadata localisation and bundle optimisation pending.

## 32. Scope not started
W10.2 (users, sessions, SEC-W10-01), support, billing, subscriptions UI, jobs, knowledge administration, GDPR workflows, feature flags, incidents, P10C, RC-P10-003 and Pilot 2 are NOT started.

## 33. Integration record
Branch `feat/p10b-w10-1-admin-foundation` from `main` e13bfc4. PR #110, merge commit `301173db0fc1e75ff8a4f734b6804564ada52614` (merge commit; qualified head `26422b9`; all required CI green before merge). Local `main` fast-forwarded and verified equal to `origin/main` with a clean tree. Alembic head `0014_opportunities`. SEC-W10-02/03/06 CLOSED; SEC-W10-01 (W10.2), SEC-W10-04 (W10.10), SEC-W10-05 (W10.11) OPEN. The role-assignment second approver is carried to W10.13.

## 34. Rollback
Revert the PR. There is no migration and no data change; role strings written with the new presets remain valid strings, and an older build would simply treat them as non-admin (default deny).

## 35. Recommendation
Proceed to W10.2 (users, access and workspaces; closes SEC-W10-01) after owner approval. Do not start it from this wave.

## 36. Post-merge reliability correction: shared Next.js navigation (W10.1 hotfix)
**Classification:** W10.1 post-merge reliability correction. This section supersedes the "unreproduced intermittent" disclosure in section 23.

**Observations.** (1) Local qualification: the Admin journey's click on the Audit link did not navigate within 10 s (twice in about 12 runs, then unreproducible in 40+ runs without load). (2) CI run 37035935937 on branch `docs/p10b-w10-1-complete` (a docs-only branch): `e2e/navigation.spec.ts` Flow 4 clicked "Review & Diagnostics" and the URL stayed on `/prepare` for 10 s (199 passed, 1 failed). `navigation.spec.ts` is byte-identical on `main` and on that branch, so the docs branch did not cause it; it is a pre-existing shared defect. Flows 6 and the mobile Sources flow already carried comments about earlier dropped Link navigations that had been masked with `Promise.all([waitForURL, click])`.

**Evidence.** The GitHub trace artifact could not be downloaded (the Artifacts API requires authentication and no token is available here), so the failure was reproduced locally instead, with the production server exactly as Playwright starts it (`npm run build` + `npm run start`) and 20 busy-loop processes saturating the CPU. Flow 4 failed 1 time in 100 and the retained trace shows, in order: `goto /prepare`; click More; click the menu item (the click event fired and the item was actionable); the browser requested `/review?_rsc=...` twice (prefetch and navigation) and the `app/review/page` chunk, all HTTP 200; no console error; no `history.pushState`; the URL stayed `/prepare` until the 10 s timeout. So: the click fired, the soft navigation was started and its data was fetched, but the App Router never committed it, silently. `/review` was never reached, no redirect occurred, and no guard or auth refresh was involved. This is the same class as the guard-redirect loss fixed in W9.7B (`redirectVerified`), now seen for user clicks.

**Root cause.** A Next.js App Router soft navigation started shortly after load can be lost without an error on a loaded Linux production server. It is not click-listener timing (the click was handled and the fetches were issued) and not the menu close handler (the item was clicked and the request was issued; closing the menu does not prevent the fetches). Waiting for the URL concurrently with the click (the earlier masking pattern) cannot recover a navigation that never commits.

**Fix (product code, shared once).** `lib/navigation/verified.ts` adds `verifyNavigation`: after the Link starts its own navigation, if the pathname has not changed after 500 ms it retries the soft `router.push` once, and if that is also lost it performs one hard navigation. A pathname change to anywhere ends verification (it never fights a later navigation), same-page links are ignored, and it uses `push`, so browser history is preserved (redirects keep using `redirectVerified`/replace). `components/ui/VerifiedLink.tsx` wraps `next/link` unchanged (same anchor, href, prefetch, keyboard and modified-click behaviour) and adds the verification only for plain same-tab left clicks on internal links. It replaces `next/link` on the app-shell surfaces: wordmark, primary and mobile navigation, More menu (all items: Company research, Documents, Workspaces, Sources, Help, Review and Diagnostics, Admin), account menu, Admin shell and Command Center links, and the Review hub links (Agent Inspector). The earlier Audit-link observation uses the same Link navigation path and is consistent with this mechanism; this could not be proven for that single event, and it is not recurring in the stress runs below.

**Not done on purpose.** No Playwright retries, sleeps, longer timeouts or weakened assertions; `navigation.spec.ts` is unchanged. The earlier `Promise.all` waits in Flow 6 and the mobile Sources flow remain as they were.

**Tests.** `tests/verified-navigation.test.tsx` (first navigation lands: no action; dropped then soft retry succeeds; both lost: exactly one hard navigation; different navigation ends verification; same-page ignored; push only, never replace; cleanup cancels; VerifiedLink renders a normal anchor and recovers a plain click; modified, external and `target=_blank` clicks are not verified) and `tests/navigation-reliability-guard.test.ts` (shell surfaces use `VerifiedLink`; no `router.replace` in the user-navigation path). Four existing test files gained a `useRouter` stub in their `next/navigation` mock.

**Stress evidence (fixed code, production server, CPU saturated).** Flow 4: 300 of 300 passed (before the fix: 1 failure in 100 under the same load). `navigation`, `admin` and `review-access` specs together, 25 repeats each: 350 of 350. Full-suite and gate results are in the hotfix PR.

**Unrelated CI finding on the hotfix branch (not a navigation defect).** CI on `fix/w10-1-navigation-reliability` then failed one Vitest case, `data-privacy-center.test.tsx` F6 ("Unable to find Archive button"; the DOM held the Opportunities heading and a loading skeleton but no rows). `DataPrivacyCenter.tsx`, `lib/hooks/useResource.ts` and the test file were byte-identical to `main`, so this is a pre-existing asynchronous test race in the W9.8 privacy coverage, exposed by CI timing, not caused by the navigation fix. Cause: the test waited for `findByTestId("dp-manage-opportunities")`, but that section container renders synchronously before its `useResource` request is ready, so the immediate `getAllByRole` ran before any row existed. Fix (test only): F6 now waits for the loaded Archive action with `findAllByRole` before asserting the unchanged expected count; three other clear instances of the same pattern (assertions on independently loading sections made with `getBy*` right after awaiting a different section: F13 tail, F5 interview count, F14 tail) now use `findByText`/`waitFor`. No product code, expected values, retries, sleeps or timeouts changed, and no privacy behaviour changed. The old failure could not be reproduced locally (0 of 40 runs of the old file under CPU saturation), so the cause is established from the code path and the CI DOM, not from a local failure.
