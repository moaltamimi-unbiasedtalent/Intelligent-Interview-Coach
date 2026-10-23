# 03E2 Evidence: Reports catalogue, builder and export views (REQ-OWN-04 frontend half, PG-14)

Two PRs. **PR 1** `feat/03e2-report-views` (this section set): the Admin UI over the merged 03E1 API (catalogue, governed builder, preview, charts with data-table equivalents, saved configuration management, CSV and JSON export with the audited refusal-aware flow). **PR 2** `feat/03e2-pdf-export` (branched from PR 1): the governed PDF export; its evidence is appended under "PR 2" below when delivered. Migration: **none**. Permissions: **none added** (registry stays 44). Frozen contracts (`src/reporting/contract.py`, `frontend/lib/admin/metricContract.*`) and the 03A shell files (`AdminShell.tsx`, `capabilities.ts`, `nav-items.ts`) are untouched.

## Requirement mapping (REQ-OWN-04 frontend half; OD-REPORT-EXPORT provisional default)
| Requirement | Covered | How | NOT covered |
|---|---|---|---|
| Report catalogue | Yes, in code and tests | `ReportBuilderView` lists the report types the API returns for the caller (`GET registry`), with description, window set and metric count | |
| Builder over registry choices only; cannot submit an unregistered metric, an unregistered dimension or a free-text filter | Yes | Report type, metrics, window, grouping, chart and comparison are `select`s and checkboxes built from the registry response; filter values are only the bucket labels a grouped preview returned (and only labels the server's label pattern accepts). The only text input on the page is the saved-report NAME (vitest asserts exactly one textbox). The draft is normalised against the registry on every change; the server re-validates | A name is free text by design (server regex, 422 `bad_name`) |
| Validation messages from the API's stable problem codes | Yes | `GET validate` runs on every definition change; its `problems[].code` and message are shown verbatim; run, save and export stay disabled until `valid`. 422 bodies of preview/export/save are parsed for `[code] message` | |
| Preview | Yes | `GET preview`, stale marker when the definition changes after a run | |
| Charts with data-table equivalent | Yes | SVG bar chart (`role="img"` with a full text summary) for numeric, `ok` values only; a data table is ALWAYS rendered under it (suppressed/unavailable rows labelled). Chart kind `table` renders the table only | Registered metrics have no time breakdown, so the `trend` kind compares the groups or the previous period (stated under the chart); no free-form time series |
| Suppressed buckets and unavailable metrics render as such, never as zero | Yes | `figureText`/table cells print the state ("Suppressed: small cohort", "Unavailable", "Not captured"); no bar is drawn for a non-ok value; guards reject a non-ok state that carries a figure; vitest asserts no `0` cell | |
| Saved configuration management: create, rename, update with `expected_revision`, delete, share flag | Yes | `ReportSaved.tsx`; every write sends the revision it was based on; a 409 is shown as "changed elsewhere" with nothing overwritten; read-only shared items offer no write controls; invalid stored definitions are listed as "No longer valid" and cannot be loaded | Revision re-sync after a 409 is manual (reload) |
| CSV and JSON export, audited, refusal-aware | Yes | `POST export` via a dedicated binary download helper: a file exists only on a 2xx with the expected content type; a 403, 422 or **503 (audit could not be written)** shows an explicit error and "No file was downloaded." and creates no Blob/URL (vitest and Playwright assert it) | |
| Commercial reports only for the commercial permission | Yes | The commercial family is requested only when `platform.reports.commercial.read` is held (and the standard family only with `platform.reports.read`); vitest asserts the other family is never requested; the server remains authoritative | |
| Client-boundary validation of every response (lesson of PR #228) | Yes | `frontend/lib/admin/reportBuilder.ts` type guards for registry, validate, preview, saved item and list, applied inside the API client (`checked`); a malformed 200 throws `malformed_response` and renders the explicit Admin error or inline error, never a crash. The pre-existing fixed reports endpoint (`/admin/reports/{kind}`) had no shape check and crashed on a malformed 200 (found while writing the Playwright mock); it now has `isAdminReport` and an explicit error state | |
| Accessibility and layout | Yes (programmatic) | `e2e/admin-reports-03e2.spec.ts`: builder with preview at 1280 and 768 px, light and dark: no document or content overflow, an h1, every control named, every input labelled, chart SVG named. Wide tables sit in the existing `ScrollRegion`. No WCAG certification is claimed | No screen-reader or manual audit |
| Admin UI English only | Yes | No i18n catalogue change; `eval_locale_inventory` not affected | |
| Export formats beyond CSV, JSON, PDF (for example XLSX) | **Out of scope, not built** | | XLSX and any other format |

## Changes
- `frontend/lib/admin/reportBuilder.ts` (new): types, guards, query builder, problem-code parser, helpers.
- `frontend/lib/api/client.ts`: `api.admin.reportBuilder.{standard,commercial}` (registry, validate, preview, saved, create, update, remove, exportReport), `checked`/`malformed`/`download` helpers; `api.admin.report` now guarded.
- `frontend/components/admin/ReportBuilderView.tsx`, `ReportResult.tsx`, `ReportSaved.tsx` (new); `ReportsView.tsx` gains a "Standard reports" / "Catalogue and builder" switch (the existing view is unchanged otherwise).
- `frontend/e2e/fixtures/admin-responses.json`: ONLY the four `/admin/report-builder/**` keys, produced by `scripts/gen_w11_admin_fixture.py` and merged (the other keys the script now emits belong to other packages and were deliberately not merged).
- `src/api/main.py`: CORS `expose_headers` now also lists `Content-Disposition` and `X-Export-Rows`. Without it a cross-origin browser (frontend 3015, API 8020) cannot read the audited export's file name and row count (found by the Playwright run); `tests/test_report_builder_ui_03e2.py` asserts it and that a foreign origin is not reflected. Exposing these two header names reveals nothing the response body does not.
- Tests: `frontend/tests/admin-report-builder-03e2.test.tsx` (22), `frontend/e2e/admin-reports-03e2.spec.ts` (10), `tests/test_report_builder_ui_03e2.py` (1).

## Security and privacy impact
No new route, permission, migration or data path. The UI submits only registry ids; the server re-validates, re-authorises and audits (unchanged 03E1 behaviour). No candidate content or identifier is rendered (aggregates only). Saved definitions hold no results. A file is created in the browser only after a 2xx audited response. CORS: two header names exposed to the already allowed frontend origins.

## Tests and commands
See the "Test results" section (PR 1 and PR 2 results are recorded together at the end of this file once run).

## Risks and limitations
- The registry labels of grouped buckets are the only filter choices; a grouped preview must be run first (by design, to avoid free text).
- The `trend` chart kind is a comparison of groups/periods because no registered metric has a time breakdown.
- Filters cover one grouping dimension (the 03E1 rule).
- Automated verification only: not an independent accessibility, security or privacy review.

## Remaining human / operational evidence (not done, not claimed)
Owner decision OD-REPORT-EXPORT is provisional (CSV, JSON, PDF). Live-staging run of the builder with real Admin accounts; manual keyboard and screen-reader pass; independent security review of the export path; PG-14 stays IN PROGRESS until the lead and owner decide. No gate is marked PASS here.

## Throughput
Start 2026-10-22 07:22 CEST. First push: see report. Rework rounds PR 1: 2 (Playwright found the unguarded fixed-reports crash and the CORS header gap; vitest found a stale-registry bug on family switch, fixed by keying the family body).
