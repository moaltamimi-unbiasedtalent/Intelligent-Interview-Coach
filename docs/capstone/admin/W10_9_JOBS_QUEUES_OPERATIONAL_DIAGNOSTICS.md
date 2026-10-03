# P10B-W10.9 - Jobs, Queues & Operational Diagnostics

**Status:** implemented on branch `feat/p10b-w10-9-jobs-operational-diagnostics`; **complete when merged to `main`**. **W10.8 is NOT STARTED.**
One additive migration (`0018_jobs`). No new dependency. No external broker. 0 paid/live calls.

## 1. Starting point
`main` `b4c01cba6a4fdf9a73cc95a9f4dae4b6d968e02f` (W10.6 complete), clean tree, Alembic head `0017_integrations`.

## 2. Branch
`feat/p10b-w10-9-jobs-operational-diagnostics`.

## 3. Background-work audit
Searched `src` for background tasks, threads, subprocess, polling, sleeps, schedulers, queues and fire-and-forget work.
| Workflow | Current execution model | Durable? | Retry? | Idempotent? | Candidate for W10.9? |
|---|---|---|---|---|---|
| Interview/AI generation, RAG answering | synchronous inside the HTTP request | n/a | provider client has bounded retry (`openrouter_client`) | n/a | No (candidate-latency path, paid providers) |
| Document parsing / OCR | synchronous in the upload request | n/a | none | upload is owner-scoped | No (W10.8 owns ingestion) |
| Knowledge ingestion / indexing | synchronous / offline scripts | no | none | re-index is repeatable | No (W10.8) |
| Company-page research | synchronous, SSRF-guarded fetch | no (cache only) | none | read-only | No |
| Integration connection test | synchronous Admin request (W10.6) | result row | none | overwrite of latest result | **Yes** (optional queued form) |
| Agent run checkpoints | LangGraph SQLite checkpointer, per-run thread locks | yes (checkpoint) | resume | by run id | No (separate mechanism) |
| Rate limiting, session store, pause | in-process locks | no | n/a | n/a | No |
| Evaluation / RAGAS | offline CLI scripts | no | none | repeatable | No |
| Cleanup, export, deletion | synchronous requests (W9.8) | no | none | yes | No (W10.10) |
No `asyncio.create_task`, `BackgroundTasks`, thread pool, multiprocessing, scheduler or cron-style worker exists. The `subprocess` uses are two bounded `git` calls for build metadata. The durable framework is therefore built first; only two real job types prove it and nothing existing was migrated.

## 4. Approved architecture
DB-backed queue plus a separate worker process (decision AD-05). PostgreSQL claims with `FOR UPDATE SKIP LOCKED`; SQLite claims with an atomic conditional UPDATE. No Celery, Redis queue, RabbitMQ, Kafka, APScheduler or cron worker.

## 5. Job registry
`src/jobs/registry.py`, code-defined. A job type defines its code, label, payload schema (pydantic, `extra="forbid"`), handler, summary function, retry policy (max attempts, backoff base and cap), lease length, idempotency strategy, manual-retry and queued-cancel flags, whether Admin may enqueue it, an extra required permission and its dependencies. Admin supplies a job type code only; it can never name a function, handler or command, and there is no shell job.

## 6. Initial job types
- `diagnostic_noop`: operational no-op that proves queue, worker and lease end to end (max 2 attempts, 30 s lease).
- `integration_connection_test`: runs the same bounded W10.6 probe (adapter-defined destination, no URL input; payload is one registry code that must support a test). Needs `platform.integrations.manage` in addition to `platform.jobs.manage`. Synchronous testing from the integration page is unchanged.
Knowledge/RAG, privacy and billing jobs are not implemented.

## 7. Data model
`jobs`: id, public_id (uuid hex, unique), job_type, state, priority, payload_json, payload_version, idempotency_key, attempts, max_attempts, manual_retries, available_at, lease_owner, lease_expires_at, heartbeat_at, started_at, finished_at, last_error_category, last_error_message_safe, created_by_user_id (FK SET NULL), created_at, updated_at. `job_workers`: worker_id, status, started_at, last_seen_at, jobs_succeeded, jobs_failed. Nothing stores a secret, header, stack trace, provider response or private candidate content.

## 8. State machine
`queued -> running -> succeeded | failed | queued (retry, with a future available_at)`; `queued -> cancelled`; `failed -> queued` (manual retry). There is no retry_wait state: a queued job with attempts > 0 and a future `available_at` is shown as "waiting to retry". A CHECK constraint requires a running job to hold an owner and lease and every other state to hold none. An expired lease is reclaimable (reaper) and never becomes succeeded. Transitions exist only in `JobService`; no route edits state.

## 9. Payload safety
Per-type schema validation, `extra="forbid"`, and a defence-in-depth rejection of credential-shaped keys (secret, token, password, credential, authorization, api_key, bearer, cookie, private_key) before validation. Validation errors never echo the submitted input. Payloads reference records by id. Admin never sees a raw payload: only the type's `summarize` output.

## 10. Priority
`low | normal | high`, default normal. Claim order is priority, then `available_at`, then id. No weighting, urgency or SLA semantics.

## 11. PostgreSQL claim
`SELECT ... WHERE state='queued' AND available_at<=now AND attempts<max_attempts ORDER BY priority, available_at, id LIMIT 1 FOR UPDATE SKIP LOCKED`, then the UPDATE to running (attempt+1, lease owner and expiry) and COMMIT, in one short transaction. The handler runs after the commit.

## 12. SQLite claim
Pick a candidate, then ONE conditional `UPDATE ... WHERE id=? AND state='queued' AND attempts=<value read>`. `attempts` changes on every claim, so it is a version token; `rowcount == 1` means this worker won, otherwise it re-reads (up to 5 times) without consuming an attempt. Difference from PostgreSQL: competing workers serialise on SQLite's write lock instead of skipping locked rows. SQLite is for local development and tests; production uses PostgreSQL.

## 13. Leases
Each job type has a lease length. The lease records an operational worker instance id (random hex, no host or address) and an expiry. Every post-claim write (heartbeat, complete, fail) is guarded by `state='running' AND lease_owner=me AND attempts=claimed_attempt`, so a worker that lost its lease can never overwrite a newer owner (it receives `LeaseLost` and discards its result).

## 14. Heartbeat
`JobContext.heartbeat()` renews the lease, only for the current owner of an unexpired lease on a running job; terminal jobs and other owners get `LeaseLost`. No heartbeat thread is run: both initial job types are short, and a long handler calls `heartbeat()` itself.

## 15. Crash recovery
The worker cycle starts with `reap_expired`: a running job whose lease expired returns to `queued` (category `lease_expired`), or to terminal `failed` if its attempts are exhausted. Another worker then claims it. Tested with an injectable clock and verified manually with a real killed lease.

## 16. Idempotency
Enqueue: at most one ACTIVE (queued or running) job per (job_type, idempotency key), enforced by a partial unique index; a duplicate enqueue returns the existing job (`created=false`), including under a concurrent race. A finished job never blocks a later one. Handler: a job can run again after lease expiry, so every handler must be replay-safe (strategy documented per type in the registry): the no-op has no effect; the integration test overwrites the latest result row.

## 17. Attempts
`attempts` increments exactly once, on a successful claim. It does not change when a worker loses the claim race, when the Admin views the queue, or when polling finds nothing. Manual retry resets it to 0 and increments `manual_retries`.

## 18. Retry classification
Retryable: `transient`, `timeout`, `rate_limited`, `unavailable`. Not retryable: `invalid_payload`, `configuration_error`, `unsupported`, `unknown_job_type`, and any unclassified exception (`internal_error`). `lease_expired` is applied by the reaper. Handlers classify their own failures; there is no retry-everything default.

## 19. Backoff
`min(cap, base x 2^(attempt-1))`, deterministic, no jitter, no dependency. The worker never sleeps waiting: it sets `available_at` and releases the job.

## 20. Max attempts
At `attempts == max_attempts` a failed attempt makes the job terminal `failed`; nothing requeues it automatically.

## 21. Failure redaction
Only a category and a fixed per-category message are persisted; exception text is never stored, and the worker logs only the exception class and the job id. Verified with sentinel keys in exception messages.

## 22. Manual retry
`POST /admin/jobs/{id}/retry` (`platform.jobs.manage`): terminal `failed` jobs of a type with `manual_retry`, requeueing the SAME job (no clone), audited atomically. A conflicting active idempotency key returns 409.

## 23. Cancellation
Queued jobs only. Running jobs are not cancellable: Python execution cannot be interrupted safely and no cooperative cancellation is implemented. The UI says so.

## 24. Worker process
`python -m src.jobs.worker`: touch presence, reap expired leases, claim, execute, finalise, idle-poll. `JOB_WORKER_POLL_SECONDS` (bounded 0.5 to 60, default 2). SIGTERM and SIGINT stop it gracefully. It is never started by the API.

## 25. Concurrency model
One job at a time per process; scale by running more processes. Correctness comes from DB claiming, not process-local locks.

## 26. Transaction and crash-window semantics
The claim commits before the handler runs; handler mutations use their own transactions; success is recorded only after the handler returns. If a worker dies after a domain commit but before completing, the lease expires and the job runs again, so replay safety is mandatory (tested: one domain effect after replay). No transactional outbox was needed: Admin enqueue is a direct insert.

## 27. Admin queue and detail
`/admin/jobs`: server-side filters (state, type, priority), search by job reference only, pagination, attempts as "n of m", states as text, stale-lease marker, error category. `/admin/jobs/{id}`: job, execution (lease, heartbeat, worker id), typed input summary, failure, actions (retry, cancel-queued behind confirmation) and recent management audit. English only, permission-derived, VerifiedLink navigation.

## 28. Diagnostics
`GET /admin/jobs/diagnostics`: counts by state and type, retry-waiting, stale leases, oldest ready job age, and worker presence.

## 29. Command Center
With `platform.jobs.read`: queued, running, failed and stale-lease counts only.

## 30. Integration handoff
`integration_connection_test` exists as a queued form of the W10.6 probe. No recurring health monitoring was added.

## 31. Knowledge/RAG handoff
W10.8 can register ingestion, parsing, classification and indexing types in the same registry without changing the framework.

## 32. Privacy handoff
W10.10 may register DSAR, deletion and backfill types. None were implemented; PRIV-W9-01 and PRIV-W9-02 stay open.

## 33. Billing handoff
W10.5 may later register billing sync and webhook types. None were implemented.

## 34. SEC-W10-05 boundary
Nothing here is a platform pause. SEC-W10-05 (durable platform configuration and pause, W10.11) remains OPEN.

## 35. Migration
`0018_jobs` (from `0017_integrations`): `jobs` and `job_workers` with CHECK constraints (state, priority, attempts >= 0, max_attempts >= 1, attempts <= max, manual_retries >= 0, lease-matches-state, error category), unique public id, the partial unique idempotency index, and indexes `ix_jobs_claim (state, available_at, priority)`, `ix_jobs_lease_expiry (state, lease_expires_at)`, `ix_jobs_type_state`, `ix_jobs_created`. Reversible.

## 36. PostgreSQL testing
No PostgreSQL service or driver is part of this repository's CI or dependencies. Covered today: the compiled statement for the PostgreSQL dialect contains `FOR UPDATE SKIP LOCKED` and the code path is asserted. `test_postgres_two_workers_one_claim` runs two-plus competing workers against a real PostgreSQL when `TEST_POSTGRES_URL` points at a disposable migrated database and a driver is installed; it is SKIPPED otherwise (explicit reason). **Real PostgreSQL concurrency was not exercised in this wave.**

## 37. SQLite concurrency testing
File-backed temporary SQLite with real threads: 8 workers over 12 jobs claim each job exactly once with attempts == 1 (losers consume nothing); 10 competing claimers on one job produce one winner; 8 racing enqueues with one key create one active job.

## 38. Backend tests
**2748 passed, 4 skipped, 0 failed, 0 errors** (baseline 2720/3). New `tests/test_jobs_w10_9.py`: 28 run plus 1 skipped. Skips: live Adzuna, Streamlit render, RAGAS (unchanged) and the PostgreSQL test above. Migration, head and route-coverage guards updated.

## 39. Frontend tests
658 unit tests in 81 files (11 new): queue, filters, pagination, stale lease, diagnostics, worker warning, retry and cancel confirmations, read-only role, hidden without permission, no role names, no raw payload. Typecheck, lint and production build clean.

## 40. Playwright
**208 passed** (207 baseline plus the jobs journey), serial, no retries or timeout changes, all mocked.

## 41. Evaluators
**33 of 33** CI evaluators pass, including the new `scripts/eval_admin_jobs.py` (28 checks). Two non-CI scripts (`eval_company_intelligence`, `eval_marketing_product_trust`) fail identically on the unmodified starting `main`; they are pre-existing and unrelated.

## 42. Manual QA
Fresh database migrated to `0018_jobs`, API on its own port, worker as a separate process. Jobs enqueued through the API stayed `queued` until the worker started (the API does not execute jobs); the worker ran the no-op (succeeded) and a malware-scanner connection test (config error, no network, failed with `configuration_error`, 1 of 3 attempts); a queued job was cancelled; manual retry requeued and failed again as expected; Command Center and diagnostics counts matched; no response contained a raw payload; audit rows hold ids and states only. Lease expiry: a ghost worker claimed a job and "crashed"; after the lease passed the job showed a stale lease and a new worker reclaimed it (attempts 2) and completed it. No live provider was called.

## 43. Performance
First Load JS: `/admin/jobs` 118 kB, `/admin/jobs/[id]` 113 kB, `/admin` 115 kB; shared 103 kB unchanged. Query plans (SQLite): claim uses `ix_jobs_claim` (small sort); stale-lease lookup uses the covering `ix_jobs_lease_expiry`; public-id search uses its unique index; state/type grouping scans the covering `ix_jobs_type_state`. The recency-ordered list for one state uses a sort; acceptable at expected volumes, with `ix_jobs_created` available if needed.

## 44. Dependencies
None.

## 45. Alembic head
`0018_jobs` (single head).

## 46. Open items
SEC-W10-04 (W10.10), SEC-W10-05 (W10.11), PRIV-W9-01 and PRIV-W9-02 (W10.10) remain OPEN.

## 47. W10.8 handoff
Register ingestion, parsing, classification, provenance-check and indexing as job types (idempotent, payload by document id, safe summary, explicit retry classification); enqueue through `JobService.enqueue`; run the worker process; observe through `/admin/jobs`. Recurring work would need a separate decision (no scheduler exists).

## 48. External calls
0 paid or live provider calls. 0 external brokers.
