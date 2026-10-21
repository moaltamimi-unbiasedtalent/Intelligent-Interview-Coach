# 03K Evidence: Admin metric and report contract (interface package)

Branch `feat/03k-admin-metric-contract`, base `origin/main` 38eabbc.

## Requirement IDs
REQ-OWN-01 C2 and REQ-OWN-04 B1/B2/B4/B5 (contract part only). No metric, route, permission, migration or behaviour change.

## Contract summary
- `src/reporting/contract.py` (pydantic, `extra=forbid`, strict, frozen): `MetricDefinition` (id, label, description, source, numerator, denominator, unit, period kinds, dimensions allowed, coverage rule, missing behaviour `unavailable|not_captured`, suppression policy, permission), `DimensionDefinition`, `ReportDefinition` (ordered metric ids, allowed filters, `DateRangeRule`, comparison modes, `ChartSpec` kinds trend/funnel/share_of_whole/distribution/table, permission), `MetricResult` (state ok/suppressed/unavailable/not_captured, value or null, numerator, denominator, coverage, partial).
- `validate_registry` (unique ids, referenced metrics/dimensions/filters exist, report permission equals metric permission, periods supported, chart kind fits metric shape) plus `build_result`, `check_result`, `result_from_legacy` shared helpers.
- Adapter: `contract_metrics()` / `contract_reports()` / `default_registry()` map the 21 existing `METRICS` and 4 report endpoints read-only. `definitions.py`, `service.py` and the routes are untouched, so `/admin/reports/definitions` is byte-identical.
- `src/api/schemas/admin_metric_contract.py` (no route), `frontend/lib/admin/metricContract.ts` (TS mirror), committed `frontend/lib/admin/metricContract.schema.json` generated from the Python models.

## Invariants
1. Contract is data: sources are named (`SOURCE_CATALOG` fact tables or named queries), quantities are a closed aggregation plus a slug subject. Slugs match `^[a-z][a-z0-9_]{0,63}$` (no dot, space or quote). Every string field also passes a heuristic SQL-like text guard. The structural protection is the slug and closed-enum design; the regex is defence in depth and tuned not to reject ordinary prose.
2. Missing is a state with null value, numerator and denominator, never zero. A real zero is allowed only as `ok`.
3. Cohort metrics suppress below `REPORTING_MIN_COHORT` (5); a definition can raise but not lower the floor; a suppressed result carries no count.
4. No per-user, raw-row or event-list shape exists.

## Security and privacy impact
Aggregates only; suppression semantics preserved and testable; arbitrary SQL, column names or extra fields cannot be expressed (extra forbidden, slugs, closed enums, registered sources). No candidate content or identifier in the contract. No route or permission added (44 permissions unchanged).

## Tests and results (all on this branch)
| Command | .venv | /tmp/ci_venv |
|---|---|---|
| pytest tests/contracts tests/test_reporting_w10_12.py tests/test_report_service.py tests/test_openapi_contract.py tests/test_admin_foundation_w10_1.py tests/test_admin_access_w10_2.py tests/test_admin_qualification_w10_14.py | 183 passed | 183 passed |

Also: `ruff check .` all passed; `scripts/ci_test_shards.py verify --shards 4` OK (266 files); frontend `tsc --noEmit` clean, `npm run lint` clean, vitest `admin-metric-contract-03k.test.ts` + `admin-shell-w10-1.test.tsx` 28 passed. The full suites run in CI.

## Regression evidence
The existing reporting tests (W10.12, report service), OpenAPI contract and admin foundation/access/qualification (permission matrix) tests are green and unmodified. Conformance test asserts the legacy definitions payload equals the code-defined `METRICS`, and that the report routes are unchanged.

## How 03D1 and 03E1 use it
Run `tests/contracts/test_admin_metric_contract_03k.py` unchanged against their registry (replace `registry_under_test()`); build results with `build_result`; add new fact table names to `SOURCE_CATALOG` as a reviewed change; regenerate the JSON schema and update `metricContract.ts` when the contract changes (tests fail on drift).

## Remaining risks
- SQL-like guard is heuristic (defence in depth only).
- Existing reports define no charts (existing metrics have no time dimension), so chart rules are exercised only by synthetic tests.
- `.venv` and `node_modules` were symlinked locally and are not committed.
- A first local commit (c8f8c55) carried an untested Python suite; the strict-tuple and test-assertion fixes came in the second commit before the first push.

## SHA, CI
See the PR/compare link in the delivery report; CI runs only once a PR exists.

## Throughput record
Start 2026-10-21 18:03 UTC; end 18:37 UTC (about 34 minutes wall clock, including a roughly 15 minute pause for an environment interpreter fault) against an estimate of 2 to 3 engineering days. Rework rounds: 0 fix commits after first push. CI duration: not yet observed.
