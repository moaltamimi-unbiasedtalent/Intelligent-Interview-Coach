# 03D2 Evidence: Command Center and AI operations views (REQ-OWN-01 frontend half, C1 to C5, PG-08)

Branch `feat/03d2-command-center-views`, from `origin/main` f5cf7cb. Migration: **none**. Backend change: **none** (no genuine API gap found; see below). Playwright port 3127.

## Requirement mapping (REQ-OWN-01 C1 to C5, frontend half)
| Requirement | Covered | How | NOT covered |
|---|---|---|---|
| Dashboard tiles and charts chosen by meaning | Yes | Seven sections over the 03D1 routes, rendered by `frontend/components/admin/CommandCenterDashboard.tsx`: platform health, AI operations, job queue health, knowledge readiness, alerts, auth and security signals, candidate activity. Counts, rates and latencies are tiles (one figure with its evidence); a breakdown of ONE measure across the buckets of ONE dimension (usage by workflow, model profile, operation; failures by category; jobs by state; alerts by severity) is a horizontal bar chart (a comparison question); a rate with numerator and denominator also gets a meter. No decorative chart, no trend line is drawn (the read model returns no time series, so none is invented) | Time-series trends: the 03D1 contract has none |
| Every figure shows period, numerator, denominator, coverage, evidence status, suppression state | Yes | `MetricTile`: figure, "Evidence:" text label, partial-coverage label, Period, "n of d" (or "none provided"), Coverage, Suppression text, definition (numerator and denominator subjects, source, missing-data behaviour) from the permission-filtered definitions endpoint | |
| `unavailable`, `not_captured`, suppressed render as such, never zero | Yes | One formatter (`lib/admin/commandCenterFormat.ts`); bars are NOT drawn for a suppressed or unavailable bucket (never a zero-length bar); the type guard REJECTS a number under a missing state | |
| Cost in integer micro-USD, "known cost, partial coverage", currencies never combined | Yes | `formatMicroUsd` (integer arithmetic, no float, never rounded, `USD` always printed); the wording is shown on every cost tile and cost chart; the guard rejects a non-integer or negative `cost_micro_usd` | |
| Permissions exactly as the API | Yes | A section is shown only when the account holds the section's route permission (mirrors the route docstring); named sections not permitted are listed as "Not permitted"; a server 403 renders "Not permitted", never an error; the definitions endpoint is the server-filtered one | The permission map in `commandCenterSections.ts` is a UX mirror; the server stays the authority |
| Client-boundary validation (lesson of PR #228) | Yes | `lib/admin/commandCenterGuard.ts` (explicit guards for sections, metrics, buckets, components, definitions, built on the frozen 03K enums). The checks live INSIDE `api.admin.commandCenterSection/Definitions`, so a malformed 200 throws and the section shows the existing Admin error text ("That request could not be processed.") while the other sections still render | |
| Accessibility | Yes (programmatic) | h2/h3/h4 headings; labelled `section` regions; `figure` + `figcaption`; every chart has a data table (in a keyboard-operable `details`) and prints every value; status in text not colour; native `select` for period; `ScrollRegion` for tables; Playwright asserts no horizontal overflow at 768 and 1280 in light and dark | No WCAG certification and no screen-reader session is claimed |
| Frozen contracts | Yes | `metricContract.ts`, `.schema.json`, `AdminShell.tsx`, `capabilities.ts`, `nav-items.ts` NOT edited | |
| Admin UI English only | Yes | No i18n keys added; locale audit unaffected | |
| No new dependency | Yes | Bars are HTML; no chart library | |

Placement inside the merged shell: `CommandCenter.tsx` (Overview destination) gains `<CommandCenterDashboard />` and `AIView.tsx` (AI and models destination) gains `<AiOperationsDashboard />`; no navigation file changed.

## Backend: no gap
The 03D1 responses carry period, window, numerator, denominator, coverage, evidence, suppression, micro-USD and bucket breakdowns. Nothing needed a new route. Minor observation (not changed): bucket labels equal their keys (for example `career_ai`), so the UI humanises them for display and keeps the raw key in the data table.

## Changes
New: `frontend/lib/admin/{commandCenterGuard,commandCenterFormat,commandCenterSections}.ts`, `frontend/components/admin/CommandCenterDashboard.tsx`, `frontend/tests/command-center-03d2.test.tsx`, this file. Modified: `CommandCenter.tsx` (2 lines), `AIView.tsx` (3 lines), `lib/api/client.ts` (two admin functions, one import pair), `frontend/e2e/admin.spec.ts` (handlers and 5 specs), `frontend/e2e/fixtures/admin-responses.json` (8 new keys `/admin/command-center/*`, merged from `scripts/gen_w11_admin_fixture.py`, all existing content byte-for-byte preserved: 0 deleted lines), `frontend/tests/admin-shell-w10-1.test.tsx` and `ai-w10-7.test.tsx` (their hand-written `api.admin` mocks gained the two new functions, assertions unchanged).

## Security and privacy impact
Read-only GETs of aggregate responses; no candidate content, identifier, e-mail, address or credential is rendered (the response schemas are allowlists and the e2e asserts no candidate-content strings). Cohort suppression is displayed exactly as served; the UI never reveals a count behind a suppressed value.

## Tests (commands and results)
- `npx vitest run tests/command-center-03d2.test.tsx`: 25 passed (recorded real responses accepted; 6 malformed-section negatives; figure-under-missing-state; bad micro-USD; bucket state/value disagreement; malformed definitions; client throws on malformed 200; formatter never zero; micro-USD conversion; tiles; chart plus table equivalent; permission hiding; 403; period refetch; AI operations view).
- `npx vitest run` (all): 123 files, 1307 tests passed. `npx tsc --noEmit`: clean. `npm run lint`: clean. `npm run build`: success.
- `E2E_PORT=3127 npx playwright test e2e/admin.spec.ts e2e/w11-visual-a11y.spec.ts e2e/admin-navigation-03a.spec.ts e2e/admin-ux-w12-5.spec.ts e2e/admin-knowledge-identity.spec.ts e2e/admin-users-03c.spec.ts e2e/admin-plans-03b.spec.ts e2e/admin-speech.spec.ts e2e/admin-secrets.spec.ts`: all passed (79 in the run recorded; includes the 5 new 03D2 specs and the W11 Admin visual/a11y at 768 and 1280, light and dark, which now render the dashboard from the recorded fixture).
- Python (canary `$HOME/.cache/ask4mo/ci_venv/bin/python`; the repo venv could not be invoked from this sandboxed agent, so it was NOT run): `ruff check .` pass; `scripts/ci_test_shards.py verify --shards 4` OK (300 files); all 47 evaluators run by CI exit 0; full backend suite result: see the final report.

## Risks and limits
- Human, live-staging and gate evidence still missing: no real-browser assistive-technology review, no staging run against real data volumes, PG-08 is not marked PASS here (the lead decides gates). The dashboard was exercised against an empty database fixture (mostly `not_captured`, `suppressed`, `unavailable`) and against hand-built populated data; there is no production-like populated capture.
- Each section fetches independently on mount and on period change (up to 8 GETs on the Overview, plus one more on the AI destination); no polling, no auto-retry.
- Metric tiles carry no `aria-labelledby` group (their `h4` is the structure): an accessible-name group titled "Provider calls" would have matched the existing W10.7 e2e assertion that no provider-name input exists (`getByLabel(/provider/)`). Charts keep a labelled `figure`.

## Throughput
Started 2026-10-22 05:22Z; first push: see the final report; rework rounds: 2 (an existing vitest suite needed its `api.admin` mock extended; a data-table coverage cell wording was corrected).
