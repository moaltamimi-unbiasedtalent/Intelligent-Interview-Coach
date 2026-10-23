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

## Tests and commands (PR 1)
Run on the PR 1 tree (fresh-dependency canary `~/.cache/ask4mo/ci_venv`, which exists):
- `cd frontend && npx tsc --noEmit && npm run lint && npx vitest run`: clean; 123 files, 1304 tests passed (22 new in `admin-report-builder-03e2.test.tsx`).
- `npm run build` then `E2E_PORT=3128 npx playwright test e2e/admin-reports-03e2.spec.ts e2e/reports.spec.ts e2e/w11-visual-a11y.spec.ts e2e/admin-navigation-03a.spec.ts -g "03E2|W10.12|Admin|admin"`: 26 passed (10 new, 2 existing W10.12 report specs and the W11 Admin visual/a11y specs unchanged and green).
- `python -m pytest -p no:cacheprovider tests/test_report_builder_ui_03e2.py tests/test_report_builder_03e1.py -q` on the canary and on the repo venv: pass (100 tests each).
- `ruff check .`, `scripts/ci_test_shards.py verify --shards 4` (301 files), and the admin, doc-consistency, i18n, release and hosting evaluators: pass. The FULL backend suite and ALL CI evaluators were run once on the PR 2 head (a strict superset of PR 1; the only backend change in PR 1 is the CORS header), see "Tests and commands (PR 2)".

## Risks and limitations
- The registry labels of grouped buckets are the only filter choices; a grouped preview must be run first (by design, to avoid free text).
- The `trend` chart kind is a comparison of groups/periods because no registered metric has a time breakdown.
- Filters cover one grouping dimension (the 03E1 rule).
- Automated verification only: not an independent accessibility, security or privacy review.

## Remaining human / operational evidence (not done, not claimed)
Owner decision OD-REPORT-EXPORT is provisional (CSV, JSON, PDF). Live-staging run of the builder with real Admin accounts; manual keyboard and screen-reader pass; independent security review of the export path; PG-14 stays IN PROGRESS until the lead and owner decide. No gate is marked PASS here.

## Throughput
Start 2026-10-22 07:22 CEST. First push: see report. Rework rounds PR 1: 2 (Playwright found the unguarded fixed-reports crash and the CORS header gap; vitest found a stale-registry bug on family switch, fixed by keying the family body).

---

# PR 2: governed PDF export (`feat/03e2-pdf-export`, branched from PR 1)

## Requirement mapping (OD-REPORT-EXPORT provisional default: governed CSV, JSON and PDF)
| Requirement | Covered | How | NOT covered |
|---|---|---|---|
| Server-side PDF of the same already-suppressed aggregates | Yes, in code and tests | `format: "pdf"` on the existing `POST .../export` (both families); `src/reporting/report_pdf.py` renders the SAME `export_rows` the CSV/JSON use; nothing is recomputed. Tests compare the PDF state, value, group and unit columns row by row with the JSON rows and the (formula-neutralised) CSV | |
| Authorization identical to the other formats; same commercial gating | Yes | No new route, no new permission (still 44): the one handler gates `platform.reports.read` / `platform.reports.commercial.read` exactly as for CSV and JSON. `test_pdf_authorization_matrix_over_the_seven_personas_equals_the_other_formats` runs csv, json and pdf for all 7 personas (`tests/_admin_matrix.py` `PERSONAS` and `expected_allowed`) on both families and asserts the same status for every format; plus commercial cross-family, saved-shared and anonymous cases. `tests/_admin_matrix.py` needed no change (no route added) | |
| Audited BEFORE sending; if the audit write fails nothing is exported | Yes | Order in the handler: validate, run preview, bound-check, RENDER the PDF, write the audit row (fail-closed 503), only then return the bytes. `test_a_pdf_that_cannot_be_audited_is_not_sent` (503, JSON error body, no `%PDF`, no data in the body). A refused or too-large PDF writes no audit row (`test_a_refused_pdf_is_never_audited`) | |
| Bounded size and rows | Yes | `PDF_MAX_ROWS = 500`, `PDF_MAX_PAGES = 60`, `PDF_MAX_BYTES = 1,000,000`, all checked before the audit and before any byte is sent (stable problem `export_too_large`, 422); the CSV/JSON bound (2000 rows) is unchanged. The bounds are lower than CSV on purpose (a human-read document) | |
| No candidate identifiers or content | Yes | The PDF contains only the export rows (registry labels, bucket labels from the suppressed pipeline, states, figures, units) plus the registry title, window and the privacy note; asserted: no e-mail address, sentinel, password, cookie, `user_id` | |
| Safe file name from registry values only | Yes | `export_filename` now also accepts `pdf` (still only report id slug + closed window + format + date; nothing from a saved name or request text) | |
| No active content, no external resource fetch | Yes | The writer can express only a catalog, a page tree, two standard non-embedded fonts, an info dictionary (title, producer) and text-show operators (see the module docstring); no JavaScript, action, link, annotation, form, attachment, image, XObject, URI or embedded font exists in its vocabulary. Tests parse the file strictly with pypdf and assert every dictionary key is in a fixed allow-list, the catalog has only `/Type` and `/Pages`, pages have no `/Annots` or `/AA`, and a real export contains none of 20 active-content or URL byte patterns. Response header `Content-Security-Policy: default-src 'none'; sandbox` | |
| Deterministic output for tests | Yes | No timestamp, no `/ID`, no random value in the file; same input gives the same bytes (test) | The preview's own `generated_at` (data) is printed |
| Injection and escaping of text in the PDF | Yes | Strings are reduced to printable ASCII (non-ASCII becomes `?`, control characters dropped) and backslash, `(` and `)` are escaped; a hostile corpus (a string that tries to close the literal and start `/Launch` and `/JavaScript` objects, unbalanced parentheses, backslashes, control characters, emoji, fake PDF markers, 400-character words) is rendered, strictly parsed, shown as page TEXT and creates no object or key | Characters outside ASCII are not rendered (Admin labels are ASCII) |
| UI control | Yes | "Export PDF" next to CSV and JSON, same refusal-aware flow: only a 2xx `application/pdf` response creates a file; 422 (too large), 403, 503 (audit failure) or a wrong content type shows an explicit error and "No file was downloaded." | |
| Formats beyond CSV, JSON and PDF (XLSX etc.) | **Out of scope, not built** (the schema still rejects `xlsx` with 422, tested) | | XLSX |

## PDF approach and dependency justification
Checked first: `pyproject.toml` and the installed packages. `pypdf` (base dependency) is a reader/writer and cannot lay out a table; `fpdf2` is installed but only in the `dev` extra (test tooling), so using it in the API would have required promoting it to a runtime dependency (it pulls `Pillow`, `fonttools` and `defusedxml`; Pillow is a compiled wheel). The report is a plain ASCII table, so a ~200-line dependency-free writer is smaller, has no supply-chain or font-licensing surface, cannot express active content by construction and is byte-deterministic. **No dependency was added; `pyproject.toml` is unchanged.** `pypdf` (already a base dependency, `>=4.0,<6.0`) is used only by the TESTS to parse the output strictly and to read the content stream. Trade-off: text-only layout in a monospaced standard font (no charts, no logo, no non-ASCII glyphs); a nicer layout would be a later, owner-approved change and could then adopt a library.

## Changes (PR 2)
- `src/reporting/report_pdf.py` (new); `src/api/routes/admin_report_builder.py` (pdf branch: render before audit, PDF headers); `src/api/schemas/report_builder.py` (`format` Literal gains `pdf`); `src/reporting/report_builder.py` (`export_filename` accepts `pdf`).
- `frontend/components/admin/ReportBuilderView.tsx`: PDF button and copy; vitest (+1) and Playwright (+1) cases.
- `tests/test_report_pdf_03e2.py` (new, 21 test cases including parametrisations).
- Migration: none. Permissions: none. `tests/_admin_matrix.py` and the route invariants: unchanged because no route was added (the existing invariant test still asserts exactly the same 20 routes and `len(PERMISSIONS) == 44`).

## Security and privacy impact (PR 2)
Same data as CSV/JSON (already suppressed, aggregates only), same authorization, audit before send, fail-closed. New: a binary output whose only possible content is text from registry/suppressed data, escaped; response `no-store`, `nosniff`, a restrictive CSP. A PDF reader has nothing to execute in the file.

## Tests and commands (PR 2)
All on the PR 2 head, fresh-dependency canary (`~/.cache/ask4mo/ci_venv/bin/python`, Python 3.11):
- `python -m pytest -p no:cacheprovider -n 3 --dist loadfile -q` (FULL backend suite, once): exit 0; 6297 passed, 43 skipped, 0 failed (counted from the progress output).
- `python -m pytest -p no:cacheprovider tests/test_report_pdf_03e2.py tests/test_report_builder_03e1.py tests/test_report_builder_ui_03e2.py -q`: all pass on the canary AND on the repo venv.
- `ruff check .`: All checks passed. `python scripts/ci_test_shards.py verify --shards 4`: OK (302 files).
- All 47 `scripts/eval_*` commands of `.github/workflows/ci.yml` (run through a small runner with the CI arguments): 47 of 47 exit 0.
- `cd frontend && npx tsc --noEmit && npm run lint && npx vitest run`: clean; 123 files, 1305 tests passed. `npm run build`; `E2E_PORT=3128 npx playwright test e2e/admin-reports-03e2.spec.ts`: 11 passed.
- Not run: the full Playwright suite (only the specs touched and the related Admin and report specs), and a visual check of a real export in a PDF viewer (layout verified structurally and by content-stream parsing, not by eye).

## Risks and limitations (PR 2)
- Layout is a monospaced table; very long labels wrap up to 6 lines per cell and are then truncated with `...` (registry labels are far shorter).
- Non-ASCII text becomes `?` (Admin labels and registry values are ASCII; a future localised label would need a font strategy).
- A PDF holds at most 500 rows and 60 pages; wider exports must use CSV or JSON.
- Automated verification only: not an independent security or privacy review of the export path.

## Remaining human / operational evidence (not done, not claimed)
Owner confirmation of OD-REPORT-EXPORT (CSV, JSON, PDF) and of the PDF layout; a manual open of a real export in a PDF viewer and on paper; live-staging run with real Admin accounts and audit-log inspection; independent security review. PG-14 stays IN PROGRESS; no gate is marked PASS here.

## Throughput (both PRs)
Start 2026-10-22 07:22 CEST. PR 1 first push 07:44 CEST. PR 2 first push: see the report. Rework rounds PR 2: 2 (a content-stream test helper replaced a text-position helper that pypdf's extractor invalidates; two test assumptions about formula-neutralised CSV values and a seeded `@cmd` label were corrected; no product change).
