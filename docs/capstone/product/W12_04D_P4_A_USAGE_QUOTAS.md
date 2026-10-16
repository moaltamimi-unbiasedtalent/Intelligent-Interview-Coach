# W12.4D-P4-A Basic/Premium usage quotas and entitlement foundation

Status: **CODE QUALIFIED. QUOTA ARCHITECTURE IMPLEMENTED. NUMERICAL ALLOWANCES NOT APPROVED. CANDIDATE ENFORCEMENT DISABLED. PAID SUBSCRIPTIONS NOT ACTIVATED.**

Starting point: main `406e95b37a59f1537ac2bc25309e5daffdb6aaa4` (P3 merged as PR #172). Alembic head moves from `0032_ai_operation_events` to `0033_usage_quotas` (additive, two tables).

## 1. Current metering assessment
P2-A records one `ai_operation_events` row per LOGICAL operation that reached a provider (unique `op_key`, provider attempts, known tokens and cost, NULL when unknown, bounded failure category). Admission (`ai_operation`) applies the operator pause, then request-per-hour buckets (`cost_interview_user`, `cost_career_user`, `cost_global`) in observe mode (`AI_COST_LIMITS_ENFORCED = False`). Logical identity is `workflow:operation:user:session:idempotency-key-or-uuid`. Limiter: atomic Redis Lua with a local fallback during an outage; never run against a live Redis. The ledger is written AFTER the work and only when a provider was reached, so it cannot serve as an admission control. The buckets `cost_research_user`, `cost_upload_user`, `cost_agent_user` and `cost_realtime_user` exist but no route applies them.

## 2. Quota architecture and the three layers
1. Operational rate limiting: bursts and abuse, REQUESTS per short window (unchanged).
2. Product usage quotas (new, `src/application/usage_quota.py`): authorized consumption in explicit PRODUCT units per UTC period.
3. Provider cost accounting (unchanged): actual attempts, tokens and reported cost.
A request count is not money and a quota unit is not a billing record. Quota code never reads or writes the provider ledger. A released reservation does not erase provider consumption already recorded (tested).

## 3. Entitlement integration
Plan is read through the existing `plan_state.resolve_plan_state` over `EntitlementService` (Premium = ACTIVE Premium-plan subscription). `premium_preview`, a Premium LABEL without an active subscription, an expired subscription, an unknown plan code and an unreadable entitlement all resolve to Basic, never Premium and never unlimited. No second entitlement authority, no writer, no client-supplied plan (the service signature takes only the authenticated user id).

## 4. Quota feature inventory
| Feature | Existing metering | Operational limit | Quota unit | Reliable enforcement | Bypass routes considered |
|---|---|---|---|---|---|
| Interview Practice | yes (`practice`) | `cost_interview_user` | `session_started` (the `setup` operation) | yes, one reservation before provider work | follow-up steps consume nothing, so replays and extra steps cannot drain or evade it; reservations keyed by `op_key` |
| Career AI | yes (`career`) | `cost_career_user` | `ai_generation` (`chat`, `job_analysis`, `questions`) | yes | one generation maps to exactly one unit |
| Mo chat (agent) | no | `cost_agent_user` unapplied | none yet | needs `ai_operation` wiring first | NOT ENFORCEABLE today; not introduced |
| Company research | no | `cost_research_user` unapplied | none yet | needs metering first | NOT ENFORCEABLE today |
| Deep Dive | yes, part of Practice | Practice bucket | none (consumes under the session) | n/a | avoids double counting |
| Document processing, resume uploads | no | `cost_upload_user` unapplied | none yet | needs metering first | NOT ENFORCEABLE today |
| Opportunity workflows | no | none | none | needs design | deferred |
| Model-profile usage | metadata in the ledger | none | none (authorization is P2-C) | n/a | not a quota |
Only Interview Practice and Career AI need product quotas for the initial launch; the others are listed as gaps for P4-B or later, because nothing there is metered yet.

## 5. Quota units and counting policy
One candidate action consumes at most ONE unit of ONE feature. Units are not interchangeable (`session_started` and `ai_generation`). Provider attempts, structured-output repairs and transient retries inside a logical operation are never separate units. A retry or duplicate with the same logical identity (idempotency key) holds the same unit. No numerical allowance is approved.

## 6. Atomic admission and reservation lifecycle
`UsageQuotaService.reserve` runs in ONE database transaction: insert the reservation (unique `op_key`; a concurrent duplicate loses on the constraint) and apply `UPDATE usage_quota_counters SET used = used + 1 WHERE used < limit`. Zero rows updated means exhausted and the whole transaction rolls back. This is safe across threads and across processes sharing the database. Lifecycle: reserved to committed (operation succeeded) or released (it failed; the unit is returned). Transitions are single-use. `reap_expired` releases a reservation stuck in `reserved` after 15 minutes (a crashed worker). A retry with the same key after a released attempt takes one unit again, never two.

## 7. Idempotency
Reservation identity is the `op_key` already used by the P2-A ledger (idempotency header, else a fresh UUID). A request without an idempotency key is a new logical operation by definition.

## 8. Distributed enforcement
Counters live in the application database, the shared durable store for all instances, so quotas do not depend on any in-process counter. Tested: concurrent threads and a real four-process run never exceed the allowance (SQLite). PostgreSQL row-level atomicity of the conditional UPDATE is standard behaviour but has not been run against the production database engine in this wave. Live Redis validation of the P2-A limiter remains pending and is an activation dependency for layer 1, not for layer 2.

## 9. Failure behaviour (enforcement on)
Quota store unavailable: `QuotaUnavailable`, HTTP 503 `usage_quota_unavailable`, only for the quota-gated provider operation, before any provider call; reads, history and saved work stay available. No policy or no allowance for the plan: `QuotaNotConfigured`, same 503, fail closed. Unknown or unreadable entitlement: Basic allowance. Finalization failure never raises into the candidate request; an unfinalized reservation is recovered by expiry. Disabled gate: none of this runs. No production fail-closed policy is activated; it needs owner approval and deployment readiness.

## 10. Subscription transitions and periods
Counters are keyed by user, feature and UTC period, not by plan. A downgrade applies the Basic allowance to what is already consumed (nothing is deleted or rewritten); a re-upgrade applies the Premium allowance to the same count. Periods: hour, day, month on UTC calendar boundaries (server clock only). The subscription billing period is NOT supported (it needs the billing-period data of an activated subscription) and the `Allowance` constructor rejects it. A retry of the same logical operation across a boundary keeps its original period. The reset period is not a commercial decision made here.

## 11. Data model (migration 0033)
`usage_quota_counters` (unique user, feature, period start; `used >= 0`) and `usage_quota_reservations` (unique `op_key`; state check; index on state and expiry). Both cascade on account deletion, hold no candidate content, and are empty until enforcement is enabled. Upgrade, downgrade and re-upgrade tested; ORM and migration columns agree.

## 12. Candidate API metadata
`GET /usage-quotas` (read-only, authenticated, caller-scoped): `enforcement_active`, `policy_version` and per feature `status` (available, exhausted, not_configured, unavailable), `period`, `allowance`, `used`, `remaining`, `reset_at`. While enforcement is disabled the response carries no allowance at all. The gate is not exposed or settable through any API. Exhaustion is the stable 429 code `usage_quota_exhausted` with `feature`, `period`, `reset_at`, `retry_after_seconds`; fixed safe copy without plan, price or upgrade wording.

## 13. Frontend presentation
`UsageQuotaPanel` on Account renders nothing unless the server says enforcement is active, shows only server numbers, shows an unapproved feature as "not set up" without a number, has no link, button or commercial wording, and holds no plan-to-allowance rule. New error kind `quotaExhausted` and fragment `w12p4a` (8 locales, no ninth). No checkout is activated.

## 14. Security tests
`tests/test_usage_quota_p4a.py` (46 tests): Basic and Premium policy, forged/preview/expired/unknown/unreadable plan, plan never from the client, production refusal of a synthetic override, missing configuration fails closed, invalid allowance, duplicate and retry accounting, concurrent threads and four-process run, user isolation, borrowed op_key, commit/release/reap, periods and boundaries, transitions, store failure, route integration (denial before provider call, safe envelope with no commercial wording, only session start consumes, failed operation returns the unit but keeps the provider ledger, replayed key is one unit, missing policy fails closed, endpoint caller-scoped, forged headers ignored), structural checks (all gates off, 44 permissions, migration head). Frontend: 7 tests (panel inert when disabled, malformed payload, server-only numbers, no number when not configured, no controls, error mapping, eight-locale keys).

## 15. Performance
One indexed reservation insert plus one conditional UPDATE per quota-gated operation, only while enforcement is on; zero database work while disabled (tested: no table touched, no entitlement read). No formal load test was run in this wave.

## 16. Cost integration
Provider attribution, known and unknown tokens, attempts, latency and reported cost are untouched. No per-token price or monetary threshold is introduced. Measurement gaps remain: Career attempts are `calls_only`, research, upload and agent operations are not metered.

## 17. Rollout gates (all False)
`USAGE_QUOTAS_ENFORCED` (new), `AI_COST_LIMITS_ENFORCED`, `HISTORY_RESTRICTIONS_ENFORCED`, `MODEL_PROFILE_ENFORCED`, and the six billing gates. Existing Practice routing, history and model behaviour are unchanged. Activation requires: owner-approved numerical allowances for both plans and both features (`QuotaPolicy.complete()`), approved reset periods, live Redis validation, a PostgreSQL concurrency run, and an owner-approved failure policy.

## 18. Known limitations
No allowance, period or price is approved. Plan-family checks in P2-B and P2-C were not migrated to plan data (smallest safe scope; no behaviour change). Research, upload, agent and Opportunity quotas are not possible until those operations are metered. The `reap_expired` job is not scheduled yet. No billing-period quota. Four evaluators fail identically on main (`eval_company_intelligence`, `eval_marketing_product_trust`, `eval_opportunity_journey`, `eval_release_candidate`) and are unresolved pending independent triage.

## 19. Required owner decisions
Numerical Basic and Premium allowances, reset periods, whether Practice should count started or completed sessions, the production failure policy, grandfathering of existing candidates, and activation timing.

## 20. Programme dependencies (unchanged)
Numerical allowances and reset periods not approved; AI operational enforcement, history enforcement and model enforcement disabled; live Redis validation pending; model-quality evaluation pending; Basic-to-Fast not approved; Premium pricing not approved; Ask4Mo UG incorporation pending; dedicated Stripe onboarding pending; Brevo live verification deferred; research-cache evaluator isolation unresolved; product coverage `insufficient_evidence` 94% (n=412) BELOW GATE; RC-P10-004 not created.

## 21. P4-B readiness
Ready to start on owner instruction. P4-B can build on the reservation service (progress trends and comparison entitlements, scheduling `reap_expired`, metering of the remaining operations). Not started here.
