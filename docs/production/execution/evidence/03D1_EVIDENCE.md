# 03D1 Evidence: Command Center metrics and AI operations read model (REQ-OWN-01 backend; REQ-OWN-04 C2 dependency)

Branch `feat/03d1-command-center-metrics` from `origin/main` f9a06a9. Backend only: no frontend page, no Admin shell/navigation change, no TypeScript change (the 03K `MetricResult` type already fits every figure; 03D2 can add a thin response type). No migration (Alembic head stays `0040_knowledge_alert_categories`). No permission added (registry stays 44).

## Requirement mapping (REQ-OWN-01, backend half)
| ID | Covered | How | NOT covered |
|---|---|---|---|
| C1 dashboards: registrations, activation, interview start/completion | Yes (backend) | `/candidate-activity` delegates to `ReportingService.product` (equal to `/admin/reports/product` by test), cohort suppressed under 5 | "Active users" (not in the 03K registry), trend series (no time dimension is served; periods are 7d/30d/90d/all_time) |
| C1 AI failure rate and latency; model usage and cost | Yes | `/ai-operations`: usage units, calls, known tokens, known cost (exact micro-USD), coverage, operation failure rate, retries, p50/p95 latency, provider-call outcomes, by workflow/model profile/operation/model | Fallback-to-lower-tier count: no fact exists, so `ai_op_model_fallbacks` is always `not_captured` |
| C1 retrieval and source health; worker and indexing failures | Yes | `/knowledge` (versions by state, failed, awaiting review, index records, knowledge alerts, retrieval outcomes and error rate), `/jobs` (queue, stale leases, workers, failure rate, duration) | Live guard findings (served by the existing readiness view, not duplicated) |
| C1 security and incident indicators | Yes | `/security-signals`, `/alerts` (counts only) | |
| C1 support ticket trends | No | Existing `/admin/reports/operations` | all |
| C1 deployment and provider readiness | Partly | `/health` (database, migration state, pause, rate limiting, "providers not probed") | Provider readiness stays in `/admin/readiness` |
| C2 period, numerator, denominator, coverage, missing-data state | Yes | Every figure is a 03K `MetricResult` (`build_result` + `check_result`), plus `evidence` status, coverage text, partial flag | |
| C3 AI operations view | Partly | Usage, cost, outcomes, model configuration state, pause state, request-ceiling and quota mode | Prompt versions (wait for 01B), agent execution status, evaluation results, registered-model listing (existing `/admin/ai/*` routes remain the source) |
| C4 config changes validated/permissioned/audited | N/A | No mutation exists in this package | |
| C5 no path to private content | Yes | Allowlist schemas, banned-field sweeps, no per-user rows | |

## Changes
- New `src/reporting/command_center.py`: 61-metric registry (validated by `validate_registry` at import), 11 new dimensions (18 in total with the 03K ones), `CommandCenterService`.
- New `src/api/schemas/command_center.py` (all models `extra=forbid`), `src/api/routes/admin_command_center.py` (8 GET routes under `/admin/command-center`), router include in `src/api/main.py`.
- `tests/_admin_matrix.py`: one DOMAINS entry ("command center metrics") so the new routes are mapped, not UNMAPPED (nothing loosened).
- New `tests/test_command_center_03d1.py` (46 tests).
- Not touched: `src/reporting/{contract,definitions,service,suppression}.py`, `frontend/lib/admin/metricContract.*`, Admin shell, nav, capabilities.

## Routes and permissions (all existing; GET only)
`/definitions` and `/health`: `platform.overview.read` (landing permission of every preset; definitions filtered to the metrics whose own permission the caller holds). `/ai-operations`: `platform.ai.read`. `/jobs`: `platform.jobs.read`. `/knowledge`: `platform.knowledge.read`. `/alerts` and `/security-signals`: `platform.security.read` (alerts are read through the security domain today). `/candidate-activity`: `platform.reports.read` (same data as `/admin/reports/product`). Allowed personas per route are written by hand in the test and compared with the code-derived matrix.
Reads are not audit-logged: the existing `/admin/reports/*` reads are not either, and these responses contain no record-level data. Denials are audited by `require_permission` as everywhere.

## Security and privacy impact
Aggregates only; no identifier, e-mail, address, path, credential, free text, alert/knowledge/job text, or per-user row. Candidate-derived figures are cohort metrics (floor `REPORTING_MIN_COHORT = 5`, suppressed value null with no numerator/denominator/cost/breakdown, rates also need non-small numerator and complement, bucket partitions get secondary suppression). Operational metrics (jobs, alerts, security counts, platform telemetry) have no candidate cohort. Cost is exact integer micro-USD (`cost_micro_usd`), unknown tokens/cost are excluded and the metric labelled partial; a bucket with no known value is `unavailable`, never zero. Double counting: tokens/cost only from `ai_usage_facts`; operation outcomes/retries/latency only from `ai_operation_events`; platform telemetry only from `operational_metric_events` (tested by adding an operation row carrying tokens and cost and asserting the usage totals do not move).

## Tests and commands (offline)
| Check | Result |
|---|---|
| `tests/test_command_center_03d1.py`, /tmp/ci_venv | 46 passed |
| 03d1 + `tests/contracts` + admin qualification + foundation + reporting + completeness + navigation, repo venv (relative path `../../../.venv/bin/python`; the sandbox refused the absolute path) | 269 passed (last run, subset without completeness/navigation) |
| `ruff check .` | pass |
| `ci_test_shards.py verify --shards 4` | OK, 281 test files |
| All 46 CI evaluators (`scripts/eval_*` per ci.yml), run twice (before and after the last metric additions) | 46 PASS both times |
| Full `pytest tests -n 3 --dist loadfile`, /tmp/ci_venv | see final report |
| Frontend | not touched; tsc not run |

## Risks and limitations
- Fixture numbers prove arithmetic and suppression on seeded data; no live data was available. Real coverage depends on W10.12 / P2-A capture starting from their dates.
- Retries are derived as provider attempts minus completed calls on operations with exact attempt evidence only (labelled partial otherwise).
- `ai_op_model_fallbacks` is a registered metric that is never populated until a fallback event is recorded.
- Differencing across overlapping periods is not prevented (same residual limitation as W10.12).
- Aggregation of usage facts and operation rows is done in Python over the window (same pattern as the existing AI economics report); very large windows may need SQL grouping later.

## Remaining human/operational evidence
Owner review of the metric definitions and the per-route permission choices; 03D2 views; CI on a PR (not available until a PR exists).

## Throughput
Start 2026-10-22 01:23; first push: see final report; rework rounds: 2 (rate-disclosure expectations in fixtures; guard-literal wording); CI: not available until a PR exists. SHA: see final report.
