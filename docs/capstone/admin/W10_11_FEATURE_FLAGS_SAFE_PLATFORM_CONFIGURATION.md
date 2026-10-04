# P10B-W10.11 - Feature Flags and Safe Platform Configuration (durable pause, closes SEC-W10-05)

**Status:** implemented on branch `feat/p10b-w10-11-flags-safe-platform-config`; **complete when merged to `main`**. **W10.12 is NOT STARTED.**
One additive migration (`0023_platform_config`). No new dependency. 0 paid/live calls. Permission registry stays at 43.

## 1. Starting point
Starting main `43fbf65` (W10.7 merged as PR #124). Alembic head entering the wave: `0022_ai_model_admin`.

## 2. Branch
`feat/p10b-w10-11-flags-safe-platform-config`.

## 3. SEC-W10-05 pre-fix behaviour (reproduced on `main` code)
`PauseRegistry` was an in-memory set. Reproduced with two registry instances standing for two replicas: replica A paused `agent`; replica B reported `False`. A process restart (module reseed) returned `False` again. The Admin UI labelled the state process-local.

## 4. Root cause
The pause authority was process memory (`src/application/pause.py`: a module-level `PauseRegistry`, seeded from `PAUSED_CAPABILITIES` at boot). Nothing durable and nothing shared existed.

## 5. Old pause architecture (audited)
| Component | Authority | Durable? | Cross-process? | W10.11 action |
|---|---|---|---|---|
| `application/pause.py` registry | process memory | no | no | replaced by `PauseService` over `platform_pause_states` |
| `api/guards.py` `ensure_not_paused` / `require_not_paused` | the registry | no | no | now read the durable service, fail closed |
| `/admin/pause` (admin.py) | the registry, audit-first not same-transaction | no | no | moved to `admin_config.py`; revision + reason + same-transaction audit |
| Command Center / provider status pause field | the registry | no | no | durable state; unreadable store reported as unavailable |
| agent tool `ResearchCurrentMarket` | the registry | no | no | `check_paused` (durable, fail closed) |
| `/capabilities` realtime and research projections | the registry | no | no | request-scoped durable read, fail closed |
| `eval_hosting_readiness.py`, `eval_admin_foundation.py` | expected the process-local design | n/a | n/a | updated to the durable design |

## 6. Durable runtime-state model
`platform_pause_states`: one row per (environment, pausable capability): `paused`, `revision`, `paused_at/by`, `resumed_at/by`, `updated_at`, internal `reason`. A row is an EXPLICIT pause or resume; NO row means "inherit the deployment baseline" (the existing `PAUSED_CAPABILITIES` environment seed), so the migration changes no behaviour. The audited scope is per capability (five fixed capabilities), not one global switch: that is the pre-existing product semantics and it is preserved. There is no single "pause everything" row and no generic state table.

## 7. Environment semantics
Reuses the W10.7 vocabulary (`development`, `staging`, `production`; `dev/local/test/testing` -> development). The SERVER decides (`API_ENV`). No request field exists to name an environment. An unrecognised value cannot mutate pause state or flag overrides (409) and reads see no rows (it never maps to staging or production).

## 8. Pause scope (code-owned)
Fixed capabilities: `agent` (Mo run, continue and resume), `current_market` (company research and the agent research tool), `ocr` (document upload, replace, reprocess), `realtime_voice` (session minting), `public_registration`. Pause refuses NEW candidate activity of that kind only. Candidate model-backed Interview Practice has never been a pausable capability and is intentionally not added here (no new product semantics); it is the one notable activity the existing list does not cover.

## 9. Protected operations and the gate
One mechanism: `require_not_paused(capability)` (a FastAPI dependency) and `ensure_not_paused(capability, service)` for routes that gate inline. Agent routes place the dependency after authentication and BEFORE the agent service dependency, so the service/model is never constructed when paused. `/agent/runs/{id}/messages` and `/resume` are now protected too (they were not before). Guarded by the evaluator.

## 10. Routes deliberately available while paused
Authentication and session, `/auth/*` (me, plan, preferences), Data and Privacy (`/privacy/*`, export, deletion), legal pages, history and Opportunity reads, health and readiness, `/capabilities`, every Admin route.

## 11. Privacy and account availability
Never gated. Tested while every capability is paused: legal status, privacy request list and creation, account and plan reads.

## 12. Admin recovery
Admin authentication, `/admin/pause` (read and resume), Command Center, flags, jobs and the rest stay available; a pause can always be undone from the Configuration page.

## 13. Job-worker boundary
Pause is not a worker kill switch. The queue code has no pause reference (evaluator-guarded). A deterministic W10.9 fixture job runs to `succeeded` while every capability is paused.

## 14. Provider-call admission
Refusal happens before the service or provider is built. Tests count constructions (0 while paused) and the real worker/manual QA confirm it.

## 15. Pause DB-failure semantics
An unreadable store raises `PauseStateUnavailable` and the protected request is refused (503, code `platform_state_unavailable`, fixed copy, no raw error). `check_paused` (agent tool) returns paused on failure. Availability projections report the capability unavailable. The platform never reopens on a lookup failure. Only a process with no database wiring at all (a bare unit test) uses the baseline.

## 16. Restart durability
A new `PauseService` instance reads the same row (tested), and the manual QA restarted a whole app instance.

## 17. Cross-process consistency
No cache: each admission is one indexed read (about 0.1 ms). Two independent services over one database observe each other's pause and resume at once. Manual QA used two app instances plus a separate worker process on one database. No claim stronger than "the next request sees the committed state" is made.

## 18. Optimistic concurrency
Mutations carry `expected_revision`; a compare-and-swap UPDATE rejects a stale writer (409). Two administrators racing: the second gets a conflict, never a silent overwrite.

## 19. Candidate pause error and copy
HTTP 503, stable machine code `platform_paused` with fixed copy (and `platform_state_unavailable` for an unreadable store). The frontend maps the code to kind `paused` and the localized key `states.platformPaused` in all eight locales; no English matching. Wired into the Mo run UI and Company research; other surfaces use the shared state message.

## 20. Internal reason boundary
The reason (required, 200 chars) is Admin metadata: stored on the row and in the audit context, shown only to Admin, never in a candidate response (tested across `/capabilities`, `/auth/me`, `/auth/plan` and error envelopes).

## 21. Feature-flag audit
| Flag / setting | Source | Default | Consumer | Candidate-visible | Classification | Action |
|---|---|---|---|---|---|---|
| `EXTERNAL_RESEARCH_ENABLED` | env | on | research service, `/capabilities` | yes | SAFE FEATURE FLAG | `external_research` |
| `COMPANY_WEB_RESEARCH_ENABLED` | env | on | research service | yes | SAFE FEATURE FLAG | `company_web_research` |
| `AGENT_COACH_ENABLED` | env | off | `/capabilities` UI cutover only; the agent API is not flag-gated | yes | READ-ONLY ENVIRONMENT CAPABILITY | not mutable (a toggle would be frontend-only) |
| `INTERVIEW_LIVE_ENABLED` | env | off | experimental Live | yes | READ-ONLY ENVIRONMENT CAPABILITY | not mutable (needs provider credentials) |
| `REALTIME_VOICE_ENABLED` | env | off | realtime availability | yes | SECRET / INTEGRATION (W10.6) | not mutable; availability is controlled by the durable pause |
| `FEATURE_GOOGLE_LOGIN`, `AUTH_REQUIRED`, `TRUST_PROXY` | env | off | authentication | n/a | SECURITY CONFIG | not mutable |
| `AGENT_EXTERNAL_OBSERVABILITY_ENABLED` | env | off | observability | no | INTEGRATION (W10.6) | not mutable |
| `BILLING_PROVIDER` | env | disabled | billing | no | BILLING (W10.5) | not mutable |
| `OPENROUTER_MODEL_*` | env | code | model registry | no | AI CONFIG (W10.7) | not mutable |

## 22. Mutable flag registry
`src/platform_config/flags.py`: exactly `external_research` and `company_web_research`. No fake, demo or experiment flags; no percentage, user, workspace, country or role targeting.

## 23. Non-mutable flags and configuration
`NOT_MUTABLE` classifies the settings above and the Admin Flags page lists them with their owner. Forbidden items (database, API_ENV, secrets, CORS, hosts, cookies, signing keys, provider credentials, billing provider, model catalogue, entitlements, legal retention, malware bypass, audit fail-open, permissions and roles) have no mutable route or schema.

## 24. Flag precedence
Durable override for this environment > existing environment variable and its default. No override: exactly the pre-W10.11 behaviour (tested with the env variable set both ways).

## 25. Inherit / override semantics
Tri-state: inherited (no row, or a row whose `enabled` is NULL after a reset), enabled override, disabled override. A reset keeps the row so `revision` stays monotonic (no stale-write ABA after reset and re-set). A `false` baseline and an explicit disable are distinguishable.

## 26. Backend flag enforcement
The research service and `/capabilities` evaluate the durable effective value; the UI is not the control. With the flag disabled the real company-research route returns an `unavailable` report and contacts no provider (tested with sockets disabled). `company_web_research` is effective only while `external_research` is.

## 27. Entitlement separation
A flag is conjunctive: `available = existing_authorized_capability AND flag`. The flag module reads no subscription, entitlement, billing, AI or role data (source-guarded). Changing a flag leaves subscriptions, tier and entitlement counts unchanged (tested). No real flag maps to an entitled capability, so a service-level invariant test documents the conjunctive design instead of inventing a flag.

## 28. Billing separation
Flag and pause changes create no invoice, payment, term or refund (tested).

## 29. AI-governance separation
No flag or pause touches W10.7: AI configuration, activation and approval counts are unchanged by pause/resume and flag changes (tested).

## 30. Safe platform configuration audit
W10.0 intended `platform.config.manage` for "safe system configuration". Audit result: no runtime setting other than the pause qualifies (code-defined key, typed bounded value, non-secret, not a security or storage boundary, runtime-safe, with a real consumer). None was invented. The capability matrix says so.

## 31. Forbidden mutable settings
See 23. Static and evaluator guards fail if an Admin schema or route mentions database URLs, `API_ENV`, secrets, keys, passwords, CORS, hosts, cookies, signing, payment providers, model slugs or retention.

## 32. No generic editor
There is no key/value, JSON, environment-variable or `.env` editor: typed request models only, no open dicts, no create-flag route (guarded).

## 33. Permissions
`platform.flags.read`, `platform.flags.manage`, `platform.config.manage`. Count stays 43.

## 34. Role ownership
Following the W10.0 matrix: pause changes need `platform.config.manage` (operations administrator); flag changes need `platform.flags.manage` (platform and operations administrators); reads need `platform.flags.read`. Consequence to note: the pre-W10.11 pause route used `platform.flags.manage`, so `platform_admin` could pause; it no longer can (403), because the matrix assigns pause to the operations administrator. No preset was broadened. ROLE-W10-01 (platform_admin completeness) stays for W10.14.

## 35. Audit
Canonical events: `admin.platform_paused`, `admin.platform_resumed`, `admin.flag_override_enabled`, `admin.flag_override_disabled`, `admin.flag_override_reset`. Context: environment, capability or flag key, old and new state/override, old and new effective value, revision. The change and its audit row commit in ONE transaction; an audit failure rolls the change back (tested for pause and flags).

## 36. Command Center
Shows Running / Paused / Unavailable prominently (text, not colour only) and the count of feature overrides. No secrets and no candidate data.

## 37. Migration
`0023_platform_config` (from `0022_ai_model_admin`): `platform_pause_states` (unique environment+capability, valid environment, revision >= 0) and `feature_flag_overrides` (unique environment+key, valid environment, nullable `enabled`, revision >= 0). Nothing seeded. Flag-key membership is enforced by the service because keys are code-defined.

## 38. Backend tests
Backend: 2983 passed, 4 skipped (baseline 2942). Frontend: 736 unit tests. Playwright: 215 passed. All 37 CI evaluators pass.
`tests/test_platform_config_w10_11.py` (lifecycle, restart, two-instance, environment, concurrency, outage, gate-before-provider, privacy/Admin/worker availability, authorization matrix, audit and rollback, reason boundary, entitlement/billing/AI separation, flag semantics and baseline compatibility, migration, static guards) plus updated pause tests in the P8, company-intelligence and admin-foundation suites.

## 39. Frontend tests
`tests/platform-config-w10-11.test.tsx` (Configuration, Flags, candidate error contract in eight locales, no PUT retry, source guards) and the updated admin-shell test.

## 40. Playwright
`e2e/platform-pause.spec.ts`: two independent browser pages share one stateful mock standing for the durable backend (the real database, restart and multi-process behaviour is proven by the backend tests and the manual QA). Pause, blocked-before-provider, privacy page, Admin availability, resume, flag disable, capability projection, reset, and a stale-revision conflict.

## 41. Evaluator
`scripts/eval_admin_platform_config.py` (33 checks, in CI): durable authority, no process-local registry, restart and cross-instance state, concurrency, fail-closed admission, gate before the service, privacy/Admin not gated, worker not paused, code-defined restriction-only flags, no editor, environment, permissions, audit, migration, and the SEC-W10-05 closure test inventory.

## 42. Hosting-readiness evaluator update
`eval_hosting_readiness.py` now asserts the durable `PauseService` and the absence of the in-memory registry; `eval_admin_foundation.py` and `eval_admin_design.py` were updated to the durable design and the two new destinations. No unrelated hosting check was weakened.

## 43. Isolation
Tests and evaluators use temp databases. Dev DB, schema, checkpoint, Chroma and `evaluations/` fingerprints are unchanged. One disclosed exception: an ad-hoc probe I ran OUTSIDE pytest (it reused a test helper whose fake research service writes to the default `data/cache/external`) rewrote and I then removed one fixture-derived cache entry (`be293349...json`, fake "Acme" test data); I regenerated the same entry, so the research cache is functionally identical but that file's `_cached_at` byte differs and the aggregate cache fingerprint no longer equals the earlier baseline. No other store was touched, and no further out-of-pytest runs were made.

## 44. Manual QA
Two real app instances plus a separate worker process on one temp database, no provider key: 28 checks pass (pause visible across instances, blocked with 0 fake-provider constructions, privacy and Admin usable, worker ran a fixture job while paused, restart persistence, stale revision rejected, resume observed, audit present, reason absent from candidate responses, flag lifecycle, cross-instance visibility, backend enforcement, unknown flag and stale revision rejected, no entitlement/billing/AI change, no secret exposure).

## 45. Performance
Service layer: pause admission about 0.1 ms, flag lookup about 0.1 ms, pause snapshot and flag states below 0.1 ms. New admin pages about 1.5 to 1.9 kB each (114 kB first load; shared 103 kB). No cache was needed, so no TTL or convergence caveat exists.

## 46. Dependencies
None added.

## 47. Alembic head
`0023_platform_config` (single head).

## 48. SEC-W10-05 closure evidence
Closed only because all criteria hold and are tested: (1) authority is durable; (2) restart keeps the state; (3) independent instances share it through the database; (4) protected operations enforce it server-side; (5) no provider is built while blocked; (6) a lookup failure does not reopen the platform; (7) Admin can resume; (8) optimistic concurrency prevents stale overwrite; (9) audit is same-transaction and fail-closed; (10) the lifecycle is proven end to end (backend tests, evaluator, manual QA). Remaining caveat: Practice is not a pausable capability (see 8).

## 49. ROLE-W10-01
Still deferred to W10.14.

## 50. W10.12 handoff
Durable runtime state, governed flags and closed SEC-W10-05. Reporting must stay read-only over the already separated domains and must not become an authorization or control path.

## 51. Paid/live call count
0.
