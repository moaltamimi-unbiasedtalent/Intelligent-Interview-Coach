# P10B-W9.7B - CI fix: onboarding gate redirect (Browser E2E flake)

CI-only failure on PR (branch `fix/p10b-w9-7a-experience-closure`): `Browser E2E / Next.js Playwright (primary)`,
`e2e/onboarding.spec.ts` "E2E 1: new user is gated into onboarding and completes to /app" - `page.waitForURL(/\/onboarding$/)`
timed out after 60 s (188/189 passed). Frontend-only fix; no backend, migration, API or copy change.

## Not a W9 regression: a pre-existing intermittent defect
`Browser E2E` had failed 7 of its last 40 runs across many earlier branches (e.g. on `wave2-onboarding` it alternated
fail / pass / fail / pass). The test file already carried a comment about "the observed CI flake"; an earlier attempt
(`waitForURL` instead of polling) changed the symptom, not the cause.

## Reproduction
Not reproducible on macOS (25/25, and 20/20 under CPU saturation) or in one Linux pass (189/189). Reproduced in the
official CI shape: Linux, Node 20, `CI=true`, production build, container limited to 2 CPUs: **2 of 60**, then **12 of
150** with diagnostics, with Playwright traces retained.

## Root cause (two distinct mechanisms)
1. **Product defect (11 of 12 failures).** `RouteGuard` issues `router.replace("/onboarding")` once, as soon as
   `/auth/me` resolves (~115-290 ms after load, during hydration). Traces show exactly one `router.replace` call, a 200
   `GET /onboarding?_rsc=...`, **no `history.replaceState`**: the Next.js app router silently dropped the soft
   navigation. The guard's effect depends only on resolved state, so it never re-ran and the redirect was lost
   permanently: a new account stayed on `/prepare` (and an anonymous visitor could stay on the "checking your session"
   placeholder). This is user-visible, not just a test problem.
2. **Test-side miss (1 of 12).** The redirect succeeded and the page sat on `/onboarding`, but `page.waitForURL`
   (event-based) timed out. A web-first `toHaveURL` assertion polls the real URL and cannot miss it.

## Fix
- `frontend/lib/auth/redirect.ts` + `RouteGuard`: every guard redirect (onboarding gate, sign-in, auth-only) is now
  **verified**: issue the soft navigation, check the pathname after 500 ms, retry the soft navigation once, then fall
  back to a hard navigation. A dropped soft navigation has no side effects, so the retry is idempotent; cleanup
  cancels verification when the soft navigation lands or the guard unmounts.
- `e2e/onboarding.spec.ts`: the gate is asserted with `toHaveURL` (default timeout; no sleep, no raised timeout, no
  retries, no force), with the corrected diagnosis in the comment.
- Tests: `tests/redirect-verified.test.tsx` (8): landed / dropped-once / always-dropped (hard fallback exactly once) /
  cleanup / query-string, and RouteGuard integration (onboarding gate and sign-in retried).

## Evidence
Linux/Node 20/2 CPUs, production build, `CI=true`: **300/300** (baseline ~8% failure; chance of 0/300 by luck about
1 in 10^10) and the full CI command `npm run e2e` **189/189**. macOS: Playwright 189/189, vitest 485/485 (68 files),
typecheck, lint (0 warnings), scanner 0.

## Residual notes
- The hard-navigation fallback reloads the target route; it only triggers if two soft attempts are dropped.
- A guard-level E2E that forces a dropped soft navigation was not added (Next internals cannot be forced
  deterministically); the ladder is pinned by unit tests with fake timers.
