# P10B-W10.12 - Reporting, Analytics and AI Economics

**Status:** **COMPLETE: merged in PR #126, feature head `e4ae300`, main `18eebed`**; Alembic head `0024_reporting_analytics`. Final qualification: backend 3041 passed / 4 skipped / 0 failed; Vitest 745; Playwright 217; 38/38 CI evaluators; Ruff and compileall clean; isolation fingerprints before == after; 0 paid/live calls. **W10.13 is NOT STARTED.**
One additive migration (`0024_reporting_analytics`). No new dependency. 0 paid/live calls. Permission registry stays at 43.

## 1. Starting point
Starting main `ef339a53eadf793bff40eab377bf52efc3457c1c`. Alembic head entering the wave: `0023_platform_config`.

## 2. W10.11 PR/merge
PR #125, merge `ef339a53`. SEC-W10-05 closed. The disclosed W10.11 research-cache incident stands as documented there; W10.12 started from the then-current fingerprints.

## 3. Branch
`feat/p10b-w10-12-reporting-analytics-ai-economics`.

## 4. Reporting source audit (matrix)
| Metric | Requested by W10.0 | Authoritative source | Historical coverage | Safe aggregate? | Missing instrumentation | W10.12 decision |
|---|---|---|---|---|---|---|
| Registrations | yes | `users.created_at` | full | yes (cohort) | none | implemented |
| Onboarding | yes | `users.onboarding_completed_at` (exact) | full; pre-onboarding accounts back-filled completed | yes (cohort) | none | implemented (period completions; rate over period registrants) |
| Opportunities | yes | `opportunities.created_at` | full | yes (cohort) | none | implemented |
| Prepare | yes | `preparation_runs` (source=created) | from the W10.10 index; back-fill rows excluded | yes (cohort) | none | implemented, labelled |
| Practice started | yes | `interview_sessions` + `interviews` | lower bound (abandoned sessions pruned by retention) | yes (cohort) | none | implemented as lower bound |
| Practice completed | yes | `interviews.status` | full | yes (cohort) | none | implemented |
| Activation / return | yes | derived from the three domains above | lower bound | yes (cohort) | none | implemented with explicit definitions |
| Feedback | yes | `user_feedback` rating, category | full | yes (cohort) | none | implemented; comments never read |
| Evaluation quality | yes | `answers.evaluation` numeric `overall_score` | full | yes (cohort) | none | implemented via a DB JSON path (no text loaded) |
| Evaluator runs | yes | none in production | n/a | n/a | structured store | NOT CAPTURED (stated) |
| Retrieval / abstention | yes | none | n/a | operational | event | NEW telemetry from W10.12 |
| Errors / latency / provider failures | yes | none | n/a | operational | events | NEW telemetry from W10.12 |
| Jobs, integrations, knowledge, support | yes | W10.9, W10.6, W10.8, W10.3 | current state / ticket timestamps | operational | none | reused |
| Runtime state | yes | W10.11 | current | operational | none | reused |
| AI usage / cost | yes | per-run runtime objects only; interview `reports.usage` blob | not cross-user queryable | cohort | usage facts | NEW `ai_usage_facts` from W10.12 |
| Access-plan assignments | yes | `subscriptions` | full | yes (cohort) | none | implemented |
| Mock MRR/ARR, failed payments | yes | `billing_*` (MOCK) | mock state | yes | none | implemented, labelled MOCK |
| Churn rate | yes | only current state is stored | none | n/a | cancellation events | UNAVAILABLE (stated) |

## 5. Metrics implemented
See section 4 and the in-product Definitions (`GET /admin/reports/definitions`, from `src/reporting/definitions.py`: 20 metrics with source, definition, cohort policy and coverage).

## 6. Metrics deliberately unavailable
Offline evaluator results (no safe production store), churn rate (no cancellation history), any trend or per-user view, Interview Practice scores per individual, MRR for subscriptions without configured terms.

## 7. Historical coverage boundaries
Product metrics come only from existing rows with exact timestamps. New telemetry and AI usage facts are labelled "Captured since" their first event and are never back-filled; no old checkpoint or chat is scanned.

## 8. Aggregates-only rule
Every route is GET and returns typed aggregate metrics and tables. There is no raw-fact, event, per-user or export route; response schemas contain no identifier or private field (guarded by test and evaluator).

## 9. Minimum cohort constant
`REPORTING_MIN_COHORT = 5` (`src/reporting/definitions.py`). An ENGINEERING privacy control: not an anonymisation guarantee, not a GDPR certification, not a legal threshold.

## 10. Suppression semantics
A candidate-derived cell is shown only when its distinct-candidate cohort reaches the floor. Suppressed: `value = null`, state `suppressed`, text "Suppressed: small cohort". Never the count, "<5" or a range. A rate also needs a qualifying denominator and a numerator and complement that are not small non-zero counts (a 3-of-6 rate would reveal 3).

## 11. Reconstruction-risk handling
Partitions (model, workflow, plan, category) use secondary suppression: when exactly one bucket is suppressed the smallest remaining one is suppressed too, so a displayed total cannot isolate the hidden bucket (tested with 4/6/9). No trend or daily breakdown is offered. Residual limitation: differencing across two overlapping periods is not prevented.

## 12. Reporting periods
Fixed: `7d`, `30d` (default), `90d`, `all_time`; UTC; an unknown period is 422; no client date expression exists.

## 13. Registration definition/source
Candidate accounts (`platform_role = user`) by `users.created_at`. No duplicate analytics event.

## 14. Onboarding definition/source
Completions in the period use the exact `onboarding_completed_at`; the rate is the current completion state of the period's registrants. Accounts that predate onboarding were back-filled as completed, which is stated in the metric note.

## 15. Opportunity metrics
Created count, distinct candidates and per-candidate ratio. No role, employer, JD or note is read.

## 16. Prepare metrics
Runs started and the share reaching `ready` from the W10.10 index (source=created only). No checkpoint or chat is read. `ready` means the run finished, not that the answer was good.

## 17. Practice metrics
Sessions started (live sessions plus completed history; a lower bound) and completed interviews. No question, answer or report is read.

## 18. Product activation definition
A candidate's FIRST substantive action: Opportunity creation, Prepare run creation or Practice session creation. An analytics definition, not an access, subscription, billing or AI state. Login, page views, legal acceptance and settings changes do not count.

## 19. Return definition
A returning candidate has substantive activity on at least two distinct UTC dates inside the period (same three domains). No login count or page tracker.

## 20. Feedback reporting
Distinct candidates, rating and safe category counts, with suppression. Comment text, rated content and identity are never read.

## 21. Evaluation-quality reporting
Mean of the stored numeric `overall_score` and the evaluated-answer count, with suppression. The JSON path is evaluated inside the database, so no answer text or narrative is loaded. No individual score is exposed.

## 22. Retrieval/abstention reporting
`operational_metric_events` (type `retrieval`: hit / abstained / error) from `CareerApplicationService.search_knowledge` and chat. No query, evidence or citation is stored; labelled captured-since.

## 23. Operational telemetry model
Table `operational_metric_events`: event_type (request / provider_call / retrieval), subsystem, `operation` (a code-defined label), outcome, optional duration_ms (>= 0), safe error category, provider code, occurred_at. No JSON, identity, path, query, body or exception text. Indexed by time, type and subsystem.

## 24. Operations metrics
Jobs (W10.9), integrations (W10.6; no test on load), knowledge (W10.8), support counts and median resolution time, runtime state (W10.11), plus request/provider/retrieval telemetry. Pure operational facts are not cohort-suppressed.

## 25. Request latency/error semantics
An innermost middleware records only allow-listed candidate operations by route TEMPLATE (never the raw path); Admin traffic is never recorded. Outcomes: success / client_error / server_error / unavailable. Reported: counts, failure rate, nearest-rank p50 and p95.

## 26. Provider-failure telemetry
Recorded at central real-call boundaries only: the OpenRouter client (Practice) and the external research service. Success or a safe category plus latency. No probe is made for reporting. The LangChain agent path has no central hook, so its provider failures are not captured (stated limit).

## 27. AI usage audit
Agent usage existed only as a per-run runtime aggregate (`src/agent/usage.py`) in the checkpoint; Practice `UsageRecord`s live inside the session payload and the report blob. Neither was queryable across users.

## 28. AI usage persistence
`ai_usage_facts`: unique `usage_key`, nullable user (FK CASCADE), workflow (agent / practice), operation, model profile and id, model_calls, nullable input/output/total tokens, integer `cost_usd_micros`, cost source, token and cost coverage, timestamps. CHECKs: non-negative values, total = input + output when known, `unavailable` cost must be NULL. No prompt, answer, query or context.

## 29. Idempotency / double-count prevention
One capture boundary per workflow. Agent: the run's CUMULATIVE aggregate (agent calls plus the model-backed tools inside it, already summed by the ledger) is upserted once under `agent:<run_id>`; a later turn replaces it and a smaller replay never shrinks it. Practice: each canonical `UsageRecord` is recorded once under `practice:<session>:<index>` after the state commit. Tests prove the report equals the canonical ledger exactly once.

## 30. Token coverage
Per usage unit: complete / partial / unknown. Reports show known tokens and the share of units with token data.

## 31. Cost-source semantics
`reported` (provider), `calculated` (existing local pricing metadata), `unavailable` (NULL). Unknown cost is never zero. Agent estimated costs are provider-reported (no resolver is wired).

## 32. Known-cost coverage
Every cost figure is labelled "Known cost (USD, partial coverage)" with the covered share unless coverage is full; units without cost are excluded, not zeroed.

## 33. AI economics metrics
Model calls, known tokens, token and cost coverage, known cost, averages per candidate, usage by workflow and by approved model, and workflows ranked separately by known cost and by tokens. User-linked breakdowns are suppressed; rankings list only visible buckets. No candidate drilldown. No live pricing is fetched.

## 34. W10.4 subscription reporting
Active access-plan assignments by plan and source, and Basic-to-Premium / Premium-to-Basic access-plan changes (direction only for the code-defined plan families). Labelled access assignments, not payments and not paid conversion.

## 35. Mock commercial reporting
Behind `platform.reports.commercial.read`. Every figure is MOCK BILLING - NOT LIVE REVENUE; the contract carries `mock_billing` and a label, and the UI shows a large permanent banner.

## 36. Mock MRR formula
Active mock provider subscriptions with terms: monthly terms use the monthly amount; yearly terms use yearly / 12 in integer minor units with ROUND_HALF_UP.

## 37. Mock ARR formula
Monthly amount x 12; yearly terms use the yearly amount.

## 38. Currency separation
Reported per currency; never summed, converted or combined.

## 39. Commercial coverage
Eligible (active) versus priced subscriptions. A subscription without terms is excluded and the metric is "Unconfigured", never zero revenue. Trialing, past due and cancelled are listed separately and excluded from recurring value.

## 40. Churn decision
Churn rate is unavailable: only the current mock subscription state is stored, not cancellation events. No rate is inferred from current state.

## 41. Failed-payment reporting
Failed mock payments in the period and past-due mock invoices, labelled mock; no card or instrument data exists.

## 42. Permission separation
`platform.reports.read` for product, quality, operations and AI economics; `platform.reports.commercial.read` for commercial. A reports.read-only principal gets 403 on the commercial route and no commercial field anywhere (backend-enforced, tested); the UI shows the Commercial tab only with its permission. No permission or preset was added or changed.

## 43. No user drilldown
No route, field or UI element identifies, lists or links to individual candidates.

## 44. No candidate content
No answer, question, report, chat, memory, document, JD, ticket text, comment, query or prompt is read or returned (service source and schema guards).

## 45. Account export/delete handling
User-linked usage facts are deleted with the account (FK CASCADE plus an explicit delete) and the candidate's OWN usage metadata (workflow, model, tokens, cost where known) is added to the self-service export; Admin aggregates, telemetry and suppression data are never exported. No legal-retention claim.

## 46. Reporting read-only proof
Reading every report leaves users, subscriptions, entitlements, billing, jobs, AI configuration, flags, pause, knowledge, privacy requests, usage facts and telemetry unchanged, with sockets disabled (test and evaluator). The service contains no write, flush or enqueue call.

## 47. Migration
`0024_reporting_analytics` (from `0023_platform_config`): `operational_metric_events` and `ai_usage_facts` with the constraints and indexes above. Nothing seeded or back-filled; with both tables empty every report shows "not captured".

## 48. Backend tests
`tests/test_reporting_w10_12.py` (periods, suppression and reconstruction, product definitions, content boundary, feedback, telemetry, AI usage idempotency/double-count/coverage/cost semantics, constraints, deletion and export, commercial, permissions, read-only, static guards, migration) plus updated guards.

## 49. Frontend tests
`tests/reports-w10-12.test.tsx` (permission split, periods, suppression text, partial coverage, unknown cost, mock banner, tables, no drilldown or role names).

## 50. Playwright
`e2e/reports.spec.ts`: deterministic network fixtures (real SQL is proven by the backend tests and manual QA): aggregate versus suppressed, quality, operations, AI economics with unknown cost, no Commercial without its permission, and the MOCK BILLING warning with configured-terms figures.

## 51. Evaluator
`scripts/eval_admin_reporting.py` (36 checks, in CI): GET-only aggregate API, no raw/per-user route, commercial permission, fixed periods, no private fields, read-only service, suppression and rate rules, partition suppression, unavailable-not-zero, once-and-idempotent usage, NULL unknown, micro-USD, mock labelling, no churn, telemetry bounds, migration and deletion/export wiring.

## 52. Isolation
Tests and evaluators use temp databases. W10.12 started from the then-current protected-store fingerprints (the W10.11 cache incident is not re-claimed) and all six were fingerprinted before and after qualification.

## 53. Manual QA
Fresh migrated temp database with deterministic fixtures, a real Practice session store and no provider key (see the final report).

## 54. Performance
Deterministic fixture of 3,000 candidates, 12,000 Opportunities, 8,000 Prepare runs, 20,000 usage facts and 30,000 telemetry events: product 56 ms, quality 58 ms, operations 60 ms, AI economics 62 ms, commercial 3 ms (SQLite, single process). Indexes cover time, type, workflow, model and user. No cache or warehouse was needed.

## 55. Dependencies
None added (cards, tables and text only; no chart library).

## 56. Alembic head
`0024_reporting_analytics` (single head).

## 57. Live-call count
0.

## 58. ROLE-W10-01
Still deferred to W10.14.

## 59. W10.13 handoff
Safe aggregate reporting, product analytics definitions, bounded operational telemetry, AI usage facts and economics, commercial reporting and the suppression rules. W10.13 adds security events, hardened audit/export and incident management without exposing candidate content.
