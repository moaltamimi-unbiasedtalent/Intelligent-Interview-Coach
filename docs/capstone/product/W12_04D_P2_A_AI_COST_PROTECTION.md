# W12.4D-P2-A: AI cost protection and usage metering

Status: **CODE QUALIFIED OFFLINE. AI usage protection and metering implemented. Limit ENFORCEMENT is OFF (observe mode). Premium entitlements are NOT activated.**
No Stripe call, no plan allowance, no Basic or Premium behaviour, no model-routing change, no change to existing candidate access. One additive migration (`0032_ai_operation_events`).
Starting point: `main` `5c8f92331754b16fc3910a96b19e2fcefefe8897` (P1-A final decisions merged); previous Alembic head `0031_account_closure`, now `0032_ai_operation_events` (single head).

## 1. Confirmed existing exposure (VERIFIED before any change)

* `cost_interview_user` (120) and `cost_career_user` (60) were defined in `src/api/rate_limit.py` and referenced **nowhere else** (`git grep` on `origin/main`): no call site. Their unit is **requests per window per authenticated user** (3,600 s sliding window; `RateLimitPolicy(name, limit, window_seconds, scope)`). They are not tokens, money, weighted operations or allowances.
* Practice (`/interviews/*`) and Career (`/career/*`) therefore had **no per-user ceiling and no operator pause** (only `agent`, `current_market`, `ocr`, `realtime_voice` and registration were pausable). Mo (agent) already had a hard 60/h ceiling and a pause; company research 30/h and a pause; uploads 40/h.
* Provider-backed operations reachable (every LLM call; a candidate operation can need several):

| Surface | Operation | Provider calls | Cost drivers |
| --- | --- | --- | --- |
| Practice | setup (`POST /interviews`) | strategy generation, then first-question generation (2 logical calls) | JD up to 8,000 chars, background 4,000, company context 4,000, output up to 3,072 to 4,096 tokens |
| Practice | answer feedback (`/answers`) | evaluation; a JSON repair call when output fails validation | answer up to 6,000 chars plus bounded history, 7-dimension rubric output |
| Practice | next question, Deep Dive start, Deep Dive answer and next | one generation or evaluation each (+ repair) | bounded history |
| Practice | report (`POST /report`) | one large synthesis (+ repair) | all answers and evaluations: the largest context |
| Career | chat (`/career/chat`) | retrieval (embeddings or local) plus synthesis, structured output up to 4,096 tokens | RAG context, JD, background |
| Career | job analysis, questions | one structured generation each | JD |
| Career | gap analysis, preparation plan | none (deterministic) | none |
| Mo (agent) | runs | tool-using loop, several calls | already limited and metered (unchanged) |
| Company research | research | no model (fetch plus deterministic) | external fetch; already limited |
* Provider retries: the OpenRouter client retries once on a transient network error, timeout or status 429, 502 or 503 (`MAX_TRANSIENT_RETRIES = 1`); structured-output repair is a second model call. The highest-cost paths are **report, setup, answer feedback and Career chat**.

## 2. Effective protection implemented

`src/ai_protection.py` provides one admission and metering seam, the async dependency `ai_operation(workflow, operation)`, wired onto exactly the provider-backed routes (seven Practice POSTs, three Career POSTs; a test asserts the set and that no read-only route and no deterministic route is wired).

* **Identity:** the authenticated user id (never client input; spoofed headers are ignored, tested). The key is `user:<id>`; no cross-user leakage (tested).
* **Admission order:** (1) durable operator pause, which refuses before any provider is built and fails closed if the pause store is unreadable; (2) per-user request ceiling; (3) the global ceiling `cost_global`.
* **Observe mode is the default.** `AI_COST_LIMITS_ENFORCED = False` (a code constant, like the billing gates; no setting, startup or Admin action flips it). While False nothing is refused for exceeding a ceiling; the would-be refusal is recorded (`ai_operation_events.limit_observed`) so a rollout can be sized from evidence. **Existing user access is unchanged.** Enforcement is a reviewed, owner-approved release (section 9).
* **Enforcement behaviour (tested with the constant flipped):** HTTP 429 with `Retry-After`, code `ai_usage_limit`, bounded facts `capability`, `temporary: true`, `retry_after_seconds`; fixed safe copy; the refused request never reaches the endpoint (no provider work); other users unaffected; concurrent requests cannot both slip under the ceiling (20 concurrent requests against a ceiling of 5 give exactly 5 successes).
* **No new numbers were invented.** The existing 120 and 60 per hour definitions are reused as observation thresholds and are NOT approved as product allowances. No Basic or Premium allowance exists.
* **Not changed:** agent, research, upload and realtime protections; read-only routes (history, progress, report fetch, complete, recover, Deep Dive return); gap analysis and preparation plan.

## 3. Operator controls

Two new pausable capabilities, `practice_ai` and `career_ai` (`src/application/pause.py`). Pausing refuses only NEW provider-backed operations (HTTP 503 `platform_paused`, the existing fixed safe copy, no internal reason); history, reports already stored, account and privacy controls and the worker are unaffected. Existing Admin authorization (`platform.config.manage`), expected revision, required reason and same-transaction audit apply unchanged; the permission registry stays 44. Both default to running (no row inherits the env baseline). The Admin configuration screen has English labels for both. No financial entitlement is touched.

## 4. Distributed limiter findings and policy

* `RedisRateLimiter` uses one Lua script (trim, count, add, expire) so a single Redis serialises concurrent callers; the in-memory limiter is per process and is **not** distributed protection (`distributed = False`).
* Verified here: the adapter against a shared fake store with two limiter instances (one global window, user isolation), window expiry returning slots, concurrent threads, and **four real OS processes** sharing one sqlite-backed store that emulates the script's atomic semantics (exactly the ceiling allowed across 60 attempts). **The Lua script itself has not been executed against a live Redis in CI; live distributed enforcement is NOT claimed.**
* Defects fixed: a store outage silently fell back per process with no per-bucket policy, and the `degraded` flag never cleared after recovery.
* **Explicit failure policy** (`RateLimitPolicy.on_store_failure`): `local` (default for every cost bucket, stated in code): degrade to a bounded per-process window (never unlimited, never offline; capacity during an outage is up to N times the ceiling for N processes); `deny`: refuse (fail closed), implemented and tested but used by no bucket today. `limiter_status()` reports `backend`, `degraded` and `effectively_distributed` honestly (an in-process or degraded limiter is never reported as distributed).
* Known remaining limits: the window uses the calling process's clock (clock skew between replicas shifts windows; moving the clock into the script is a follow-up needing a live Redis to validate); the in-memory limiter never evicts idle keys.

## 5. Usage metering

New table `ai_operation_events` (migration 0032): ONE row per LOGICAL candidate operation that reached a provider: user, workflow (`practice` or `career`), operation, provider (`openrouter`), model profile and actual provider model id, status, bounded failure category, `provider_attempts` and `attempt_coverage`, calls ok and failed, input, output and total tokens with `token_coverage`, cost in integer micro-USD with `cost_source`, latency, `limit_observed`, start and completion times. A row is written only when the operation touched a provider (writes are bounded by costly work, not by request volume), idempotently on a unique `op_key` (same user, route, session and `Idempotency-Key`), and never raises into the request. Existing `ai_usage_facts` (Mo runs and Practice calls) is unchanged in shape.
* **KNOWN, ESTIMATED, UNKNOWN:** tokens and cost are KNOWN only when the provider reported them (`reported`); anything else is NULL with coverage `unknown` or `partial`. No ESTIMATED value is written by this layer because no model price could be verified (section 7). A provider answer that omitted usage, or reported zero tokens, is stored as UNKNOWN, never as 0.
* **Defect fixed:** `record_practice_usage` stored a call with no provider usage as `0` tokens, coverage "complete" and a calculated 0.0 cost; it is now UNKNOWN (NULL tokens, coverage unknown, cost unavailable).
* **Privacy:** no prompt, answer, CV or document content, transcript, model response, credential or request body is stored (the schema has no free-text column; tested). Only the owning user id identifies a row; rows cascade on account deletion. **Retention of these rows is not set: an owner and legal decision is required** (no period was invented).

## 6. Token, retry and concurrency accounting

* **Token accounting:** the OpenRouter client reports each completed call's `usage` (and OpenRouter-reported cost when present) into the scope; structured-output repair and retries aggregate into the same operation. Career runs through LangChain: a callback reports each invocation and any usage metadata the provider returned; when none is returned the operation is UNKNOWN. Attempts for Career are `calls_only` coverage because SDK-internal retries are invisible.
* **Logical operation versus provider attempts:** one row per logical operation; `provider_attempts` counts every HTTP attempt (exact for Practice, including failed transient attempts), `calls_ok` and `calls_failed` count model completions and failures. A repair is one operation with two calls (tested); a transient retry is one operation with two attempts (tested with the real client against a mock transport).
* **Failures:** a failure after a billable call keeps the consumed tokens and marks the operation `failed` (tested); a timeout with no completion is `failed` with unknown tokens (a failed attempt without a response has no usage evidence, so provider consumption in that case is UNKNOWN, not zero); an operation that never reached a provider writes no row.
* **Duplicates and concurrency:** the same `Idempotency-Key` is one logical operation (tested sequentially and with eight concurrent submissions). Without a key each request is its own operation, so a duplicate submission that does provider work is counted as provider consumption; Practice's own operation lease and idempotent create prevent most duplicate work upstream. Worker-crash and cancelled-client cases: a crash before the scope exits writes no row (consumption is then UNMETERED, a documented gap; the provider call outcome is still recorded by the existing operational telemetry).

## 7. Model profiles and provider pricing

* Official names and identifiers: **Fast (`fast`), Balanced (`balanced`), Advanced (`advanced`)**; no Medium profile (a "medium" reasoning-effort hint is metadata, not a profile). Mappings in `src/llm/models.py`: `openai/gpt-5.6-luna`, `openai/gpt-5.6-terra`, `openai/gpt-5.6-sol`, overridable by environment and by the governed Admin configuration.
* **Provider pricing: UNKNOWN.** On 2026-10-16 the OpenRouter models listing did not contain these slugs and exposed no pricing in the form read; nothing was invented. Cost is therefore stored only when OpenRouter reports it per response. Missing inputs: current per-token prices of the three configured slugs, embedding price.
* **Practice routing is unchanged** (server default Balanced). Basic is not switched to Fast; that belongs to P2-C after quality, cost, latency and availability qualification.

## 8. Candidate experience

If enforcement is ever enabled, the candidate receives a stable code (`ai_usage_limit`), mapped to the new `aiLimited` error kind and a localized message in all eight locales (en, de, fr, es, it, nl, pt, ru): a temporary safety limit on AI-generated practice and coaching, saved work and history remain available, try again in a little while. The response also carries `retry_after_seconds` and `Retry-After`; the static message does not print the time (a displayed countdown is a possible P3 refinement). **No Upgrade or price call to action** is shown (tested across locales). Paused operations reuse the existing localized `platform_paused` message. With enforcement off candidates see no change.

## 9. Rollout requirements and existing-user impact

Today: **no existing user is affected** (observe mode records only; the pause switches default to running). Before flipping `AI_COST_LIMITS_ENFORCED`: run observe mode in the hosted environment and review `limit_observed` and per-user operation volumes; validate the Redis limiter against a live Redis and decide the failure policy per bucket; owner approval of the numeric ceilings and of the user-facing wording; communication plan; rollback is flipping the constant back or pausing the capability. Basic and Premium allowances are separate, later decisions (P2-B onward, P4).

## 10. Security and regression testing

`tests/test_ai_cost_protection_p2a.py` (offline): route wiring set; units; observe versus enforce; envelope safety and no commercial wording; identity not spoofable; per-user and global isolation; concurrency; pause (new capabilities, before provider work, reads and the other workflow unaffected, fail closed on an unreadable store); metering of success, missing and zero usage, repair, retry, failure after a billable call, timeout, no-provider, duplicate and concurrent duplicate; career call-only coverage; the real OpenRouter client against a mock transport (retry, unknown usage, timeout, no state leak outside a scope); the LangChain callback; the `ai_usage_facts` fix; the shared limiter (two instances, expiry, four real processes, outage policies, honest status); no tier, billing or model-routing code in the module; billing gates; profile vocabulary; 44-permission registry; migration upgrade, downgrade and re-upgrade; model and migration column agreement; constraint rejection. Frontend `tests/ai-usage-limit-p2a.test.ts` plus the updated error-state kind list. Existing assertions were not weakened: the only edits to existing tests update the expected Alembic head references and the migration allow-list in `scripts/eval_admin_foundation.py` to include `0032_`.

## 11. Remaining abuse and cost risks

Request-count ceilings are not cost ceilings (a long answer costs more than a short one); no per-user concurrency limit for Practice; multi-account free-tier abuse (verified email and a per-IP registration limit are the only controls); per-process limiting without a validated Redis (and up to N times the ceiling during a Redis outage under the `local` policy); embeddings, retrieval and document processing are not metered per user; Career token evidence depends on provider-returned metadata; failed transient attempts have no usage evidence; observe mode records but does not stop spend; scope exit after a crash writes nothing; no Admin cost report reads the new table yet.

## 12. P2-B prerequisites

An approved history entitlement design (ordering, direct-ID refusal, artifact boundary, privacy-export scope) and the P2-A foundations: the admission and metering seam, durable pause for Practice, an operation ledger usable for later quotas (logical operations are countable from `ai_operation_events`), a documented limiter failure policy and a stable candidate error code. P2-B must also decide whether quota counting uses this table or a dedicated counter.

## 13. Outstanding owner decisions and programme dependencies

Owner: numeric ceilings and allowances (Basic and Premium), reset periods, enforcement go-live, `ai_operation_events` retention, Redis failure policy per bucket, whether Basic Practice moves to Fast (P2-C). Programme dependencies still open: W12.4C live Brevo validation; research-cache evaluator isolation; `eval_product_coverage` insufficient-evidence 94 % (n = 412) BELOW GATE and unresolved; Stripe Managed Payments eligibility and sandbox access; Ask4Mo UG incorporation (separate German company, registration pending, dedicated Stripe account required); commercial policy approval; financial-data retention review; W12.4E, W12.4F, W12.5 not started; RC-P10-004 not created; AC-24 partial.
