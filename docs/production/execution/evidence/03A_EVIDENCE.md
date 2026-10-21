# 03A evidence: grouped Admin navigation, permission enforcement and Admin-only platform diagnostics

Requirement IDs: REQ-OWN-08 (N1 to N5), ADMIN-01 (including Review and Diagnostics). Branch `feat/03a-admin-navigation`, base `origin/main` 38eabbc.

## Changes

- `frontend/lib/admin/capabilities.ts`: `ADMIN_GROUPS` (the six owner-approved sections, each of the 20 destinations exactly once), `groupedDestinations`, `filterDestinations`, `currentDestination`, `breadcrumbsFor`. The Review destination href is now `/admin/review` with its `anyOf` (`platform.ai.read` or `platform.knowledge.read`) unchanged. `ADMIN_DESTINATIONS` keeps its order and single-line format (`tests/_admin_matrix.py` parses it).
- `frontend/components/admin/AdminShell.tsx`: grouped sidebar. Each section is a disclosure button (`aria-expanded`, `aria-controls`), open by default, collapsible, re-opened when the current page is inside it. Quick navigation is a "Find a section" filter over visible destinations only (no new data; announces the count; Enter focuses the first match; Escape clears). ArrowUp/Down, Home and End move between section buttons and links (Tab order unchanged). Active destination has `aria-current="page"`. Breadcrumb landmark (Admin, section, page, deeper segments). Mobile drawer (menu button naming the current page, Escape closes and refocuses). Visible focus rings. A section with no visible destination is not rendered. Collapsed lists use the `hidden` attribute plus a `hidden` class (a Tailwind `flex` class otherwise overrides the attribute; found by Playwright, not by jsdom).
- Review and Diagnostics moved: `frontend/app/review/{page,rag,evaluation}` to `frontend/app/admin/review/...` (git renames; the index links updated). `frontend/next.config.mjs` adds non-permanent redirects `/review`, `/review/rag`, `/review/evaluation` to `/admin/review...`. `/review/agent` (owner-scoped run details, reached from the Coach link) is NOT redirected and stays a plain page for a Candidate; `app/review/layout.tsx` is unchanged.
- `frontend/components/layout/nav-items.ts`: Review and Diagnostics removed from `INTERNAL_NAV` (the Admin entry remains). `MoreMenu.tsx` renders the internal item's English label directly (type fix; no locale file touched, the unused `nav.review` catalogue key is left in place).
- `frontend/tests/fixtures/admin-role-permissions.json`: only the Review nav href changed (`/review` to `/admin/review`, 3 places). No permission and no route changed, so `tests/_admin_matrix.py` DOMAINS did not need a change. The fixture was edited as a deterministic one-token substitution because the generator order is unchanged; `scripts/eval_admin_qualification.py` (which checks the fixture equals `role_fixture()`) passes.
- `tests/test_admin_qualification_w10_14.py`: the orphan-page check now accepts a static child page under a destination (`/admin/review/rag`, `/admin/review/evaluation`).

## Security impact

Hiding is not authorization. No new permission (registry stays 44), no backend route or guard changed (`git diff` touches no `src/`). The redirect grants nothing: a Candidate following `/review/rag` lands on `/admin/review/rag` and sees the access-denied state (Playwright), and every API call is still authorised server-side. New backend tests in `tests/test_review_diagnostics_authz_w9_3.py`: `billing_admin` and `support_operator` (lacking the permissions) get 403 on the knowledge diagnostics, evaluation and reviewer routes; `knowledge_admin` reaches only the routes its permission covers (200 on diagnostics and evaluation, 403 on retention inventory); a Candidate gets 403 on all of them. Existing tests already cover Candidate and anonymous 403 and Admin 200.

## Tests and results

| Command | Result |
|---|---|
| `cd frontend && npx tsc --noEmit` | clean |
| `npm run lint` | no warnings or errors |
| `npx vitest run` | 111 files, 1114 tests passed (new `admin-navigation-03a.test.tsx`: grouping once-each, placement, per-role-fixture visibility with no empty groups, disclosure, keyboard, quick navigation filters visible items only, breadcrumbs, drawer; existing admin shell, nav-security, W12.5 tests updated) |
| `E2E_PORT=3135 npx playwright test` on admin-navigation-03a, review-access, navigation, admin-ux-w12-5, admin, admin-secrets, admin-speech, product-surfaces, agent-coach, w11-visual-a11y | 89 passed (the W11 Admin visual/a11y 20-destination checks pass; new spec covers expand/collapse, keyboard, order, breadcrumbs, quick navigation, 390px drawer, redirects, Candidate and Admin More menu) |
| `ruff check .` | All checks passed |
| pytest (review authz, admin access W10.2, qualification W10.14, foundation W10.1, completeness W12.4F) under `/tmp/ci_venv` | 107 passed |
| same review-authz and qualification files under the repo `.venv` | passed |
| `scripts/eval_admin_qualification.py` | PASS, 45 checks, 0 paid, 0 live |

Full backend `pytest -q` and `npm run build` were not run in this package (the Playwright web server builds the app, which succeeded).

## Regression evidence

Existing Admin specs stay green (list above). The two mock-fragile specs needed `/admin/home` and `/admin/readiness` stubs because the Command Center error boundary replaces the shell when the mocked response is `{}`; this is a test-mock matter, not a product change. Screenshots: none produced.

## Remaining risks

- The Command Center `diagnostics_links` come from the backend with the old path `/review/rag`; the redirect makes them work (one extra hop). Changing the backend string was left out of scope.
- Redirects are in `next.config.mjs` (server). A static export would drop them; the project has no `output: export`.
- Section collapse state is not persisted (the A4 test forbids browser storage in the shell).
- The Admin "More" entry still requires `platform.overview.read`; an Admin with only `ai.read`/`knowledge.read` (none of the current presets) would not see it, as before for other destinations.
- During setup I ran `pkill -f ci_venv/bin/python` once to stop a hung interpreter before the coordinator's instruction not to; no other process was intended.

## Throughput record

Start 2026-10-21 18:03 UTC. End of work 18:32 UTC at the last test run (push and CI timing in the final report). Estimate 5-7 engineering days; actual wall-clock about 0.5 hour of agent time. Rework rounds: 0 fix commits after first push (none pushed before this commit). CI duration: see final report (no CI run exists until a PR is opened).
