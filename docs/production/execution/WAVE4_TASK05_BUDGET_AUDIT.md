# Wave 4 Task 05 — budget audit and qualification

Baseline: PR #270 merged at `d5ff56d9a353c8efeee5dcf6740904a72e704346`.
All five main workflows succeeded: CI 40162476517; Redis 40162476575;
durable admission 40162476504; migration image 40162476498;
immutable images 40162476436. Browser E2E is PR/on-demand; the previous
PR's identical-tree result is historical, not a main-SHA Browser run.

## Findings before changes

The existing 05C governor already reserved worst-case spend in SQL, bounded
request tokens/retries/timeouts, settled actual usage conservatively, retained
unknown outcomes, and provided a durable kill switch and read-only Admin view.
It was opt-in even on hosted processes. Non-allowlisted hosts passed through;
SDK-compatible alternate endpoints could escape. Integrity disagreement was
reported but did not block admission. Concurrency was process-local. Approval
had no environment/expiry/pricing validity contract. Admin checked marker
presence rather than equality. A dedupe window allowed retrying old ambiguous
calls. A three-character token estimate was not a conservative multilingual
bound. These are engineering defects, not evidence of observed real overspend.

## Spending-path inventory

| Path | Existing transport and boundary | Task 05 outcome |
|---|---|---|
| Practice: strategy, question, evaluation, report, deep dive and repair | `src/interview_service.py` → `src/openrouter_client.py`, HTTPX | Every attempt reserves through sync send; required output cap, byte input bound, priced model, class/interview allocation; 429 retries bounded; unknown retries refused |
| Career chat, job analysis, question generation, synthesis | `src/copilot/llm/openrouter.py`, LangChain ChatOpenAI → OpenAI HTTPX | Same sync/async send boundary; agent operation category; every repair or continuation is another durable reservation |
| Ask Mo, specialists, tool-internal LLM calls, continue/resume | same model factory; `src/agent/nodes.py`, existing streaming disabled | No new tool or permission; SSE remains safe graph progress, not provider token streaming; monetary governor independent of durable user-run admission |
| OpenRouter semantic embeddings, knowledge jobs | `src/copilot/openrouter_embeddings.py`, HTTPX | Model/host/category guard and reservation per batch/attempt; embedding category requires an approved allocation |
| Alternate OpenAI-compatible semantic embeddings | `src/copilot/embeddings.py`, OpenAIEmbeddings → HTTPX | Paid endpoint classification applies even on an alternate host; only explicitly permitted/priced hosts/models can pass; local hash embeddings make no paid request |
| RAGAS and language/agent/judge/feedback evaluations | `src/copilot/evaluation/ragas_adapter.py`, `src/language_quality/human_eval_generate.py`, paid scripts via `script_guard.py` | Existing paid-script approval/CI prohibitions retained; existing active governor cannot substitute another budget class; HTTPX covers SDK calls/retries |
| Admin evaluations | `src/ai_admin/jobs.py` registered through `src/jobs/registry.py` | No new Admin inference adapter; current offline evaluation jobs stay offline; future paid adapters require inventory/qualification |
| Legacy capstone/demo live evaluation | `src/p10e/httpguard.py`, `src/demo_live/guard.py`, separate historical file ledgers | Direct live guard installation refuses hosted environments; historical authorization is never a production budget. Offline fixtures/local historical contracts remain intact |
| Provider key/model/pricing probes | `src/integrations.py`, `src/pricing_service.py`, `src/llm/budget/models_probe.py` | Free metadata only under valid open governor on configured host; unknown endpoints refused; no live probe run |
| Whisper hosted audio | `src/speech/stt_whisper.py`, HTTPX multipart | Existing activation flags stay disabled; unsupported paid endpoint is refused on hosted systems, no audio pricing/settlement qualification claimed |
| OpenAI realtime token minting/client session | `src/voice/realtime.py`, HTTPX then browser session | Hosted endpoint refused; a token-mint request cannot authorize an unmetered browser inference session; existing activation remains off |
| Legacy Google Cloud Speech | `src/speech_service.py`, optional Google SDK/gRPC | Non-HTTPX bypass found; SDK construction explicitly refused on hosted environments, including cached clients; local/test fixtures preserved |
| Legacy Gemini live token minting | `src/live_interview.py`, optional Google GenAI SDK | Hosted default minter explicitly refused before SDK construction; no qualification of browser realtime spending |
| Self-hosted Whisper/Kyutai, browser dictation, deterministic retrieval | local engines/browser/deterministic stores | No application-paid provider call; unchanged |
| Research source fetching, identity, email | ordinary HTTPX/urllib source/identity/email adapters | Not model inference; safe non-AI HTTP remains usable while budget is closed; no live email/source call made |

The governor is an application transport boundary, not an OS egress firewall.
No current inference path using requests/aiohttp/raw sockets was found. Optional
Google SDK paths are specifically refused as above. Adding a transport, custom
SDK HTTP client, streaming endpoint, direct browser credential or provider must
include a new inventory entry and refusal/accounting tests; it is not implicitly
qualified by this HTTPX wrapper. Redirect following is disabled for governed
requests so HTTPX cannot redirect internally around the outer send hook.

## Enforcement and durable accounting

Hosted API and worker install a closed governor if enforce mode is missing.
The demonstration file ledger is never selected in a hosted process. Non-AI
traffic continues. Hosted open construction requires PostgreSQL, matching marker,
explicit non-development class and validated owner approval. Environment,
period/expiry, pricing effective/expiry dates, USD currency, named responsibilities,
total monetary/request ceilings and per-class/category/request limits are checked.
Expiry and marker are rechecked before each call. Byte-based input bounding is
intentionally conservative and may refuse inputs previously admitted; it does
not truncate candidate data or invent a lower cost.

The existing global control row serializes admission and settlement on PostgreSQL.
It also serializes a durable active-reservation concurrency check across API and
worker. Every configured class and category counter must agree with entries before
admission; disagreement fails closed, with no repair. Total spend includes all
classes, settled actual cost and reserved/unknown worst cases. Stop thresholds
prevent normal admission from reaching hard caps. Provider overruns retain the
larger reported cost and atomically engage the kill switch, even when token usage
is missing. Negative/malformed usage stays unknown. Unknown fingerprints do not
expire into automatic retry eligibility. Process interruption leaves reservations
held; it can exhaust concurrency until reviewed, deliberately preferring refusal.

A `policy:<SHA256>` control row binds the first admitted owner configuration to
the ledger without a schema migration. Different policy hashes refuse admission.
This is metadata in the existing control table, not a second ledger or an approval
marker. A configuration/price/period change requires authorized reconciliation;
there is no automatic period reset, counter deletion, unknown release or rollover.
An environment kill presented at valid construction is latched in the durable
control so removing the variable on restart cannot clear it. Kill affects new admissions after its transaction commits; already admitted calls
can finish and must settle. Request rate limiting/Redis remains independent.

## Immutable runtime and recovery limits

Image provenance records hosted budget policy capability 2, verified through the
source-hashed governor inside the built application image. Promotion and rollback
refuse incapable images. API, worker and one-shot migrate keep the same immutable
application ID; migration order/dependencies stay unchanged. Rollback never
migrates/downgrades, clears counters, changes policy metadata or resets kill state.

The generator pins API/worker to enforce/production. Without an explicit
`--budget-config-file` it pins an empty config path, keeping AI closed. With that
option it mounts the same absolute operator file read-only at
`/run/secrets/ai-budget.json`; no contents are copied into plans/images/manifests.
The owner marker remains in the existing private runtime secret delivery; the
generator creates none. Runtime host file ownership/group permissions must be
qualified for container UID 10001 before deployment; rejecting world-accessible
files alone does not prove the container can read one. Failure to read closes AI.
The example keeps emergency kill true pending actual authorization.

On ambiguous usage, outage or integrity disagreement: stop new AI admission using
the durable kill switch, drain producers, preserve the ledger, collect bounded
entry IDs/states and obtain provider usage evidence under authorized access.
The named reconciliation/incident owner must review any correction and sign an
audit record before an operator changes policy/counters or resumes. No repair,
resume CLI, reset, refund assumption, automatic downgrade or production rollback
is added. The application cannot undo a provider's inaccurate/late invoice; an
overrun kills future spending but cannot reverse an already incurred charge.
The monetary stop/hard gap and pricing validity are owner decisions.

OD-BUDGET, OD-HOSTED and H-REDIS-POLICY stay OPEN. See
[owner specification](OD_BUDGET_SPECIFICATION_TASK05.md). No actual owner budget,
marker, pricing approval, paid activation or deployment exists from this task.

## Qualification record

All Task 05 provider responses and approval values are synthetic fixtures.
Initial qualification: 37/37 tests including five PostgreSQL 16 independent-process
races. Expanded budget/monitoring/release suite: 216 passed before the final total
request/price-expiry additions. Final results and exact-head CI belong in the
focused PR/evidence record; these intermediate counts do not qualify later heads.
The original SQLite database remains untouched at its last observed 0027; no
inference about its current revision is made by opening it.

40/45 engineering packages remain integrated; 00A/00B/07B/07C/08A stay open.
No PG/LG approval changes. Task 06 encrypted backups/restore/erasure preservation
is separate after this PR is reviewed, merged and main is green. Hosted policy
approval, infrastructure/secret/monitoring ownership, recovery drills, scanner,
provider/source/language qualification and human/legal reviews remain blockers.


### Validation progress (25 October 2026)

- Frontend: 1,534 unit tests; lint/typecheck/build passed.
- Browser E2E: 668 passed, 14 skipped, local mocked-network suite on dedicated port 3145.
- Focused budget/release tests: 163 passed before the final SDK/isolation/kill follow-ups.
- Expanded budget/monitoring/release tests: 216 passed at their recorded intermediate version.
- All 51 extracted deterministic CI evaluator commands passed (see final PR for exact-head run).
- Initial full local backend run found a test isolation leak: hosted app construction now
  installs a global closed guard and an earlier test left it installed. The shared pytest
  fixture now isolates this singleton around every test; production enforcement remains intact.
- Initial durable PostgreSQL rerun had 25 failures because the base environment lacks
  `langgraph.checkpoint.postgres`. An isolated existing adapter is used for the rerun;
  the project's installed environment is unchanged. No passing result is claimed for that failed run.
- Initial real Redis run: 13 passed, four synthetic manifest fixtures refused because they
  lacked hosted budget capability metadata. The fixtures now declare the tested capability;
  original topology/security assertions are unchanged. Final rerun pending.

Final built-image and final-head CI evidence are pending; this is not release approval.


Final local reruns: **108 passed** for budget + durable agent + Interview client,
using the existing isolated PostgreSQL adapter; **17 passed** for real Redis.
The isolated checkpoint adapter emits an existing compatibility deprecation;
passing disposable tests do not replace exact-head CI's freshly resolved dependencies
or hosted qualification. All provider responses remain mocked.


### Final review follow-ups

Incomplete chat usage now retains known input tokens, keeps output/cost unknown
and holds its reservation; only embedding endpoints may infer no completion tokens.
Admin counts distinguish complete from partial usage. Hosted startup also refuses
an inherited local/development governor; legacy P10E/demo live guards cannot replace
the production SQL budget on hosted processes. No historical live result is changed.

The full local backend rerun reached 8,666 passed / 119 skipped with one CLI-isolation
failure: module-level budget scrubbing removed deliberately supplied synthetic CLI
inputs. Cleanup now runs in the pytest fixture, preserving explicit CLI fixtures;
the focused correction passed. A later final PostgreSQL rerun had 131 passed and
38 errors because Docker ran out of disk; those errors are NOT passes. The task's
18 exact cache records (1.71 GB), superseded API image and labeled disposable DB
were removed; no unrelated Docker resource was pruned. Disk capacity remains a
local qualification prerequisite. Final local PostgreSQL qualification uses a new
bounded tmpfs-only test server, with no real database or host data mount.

The local API image from `8ccdbd85ca2094e2e63b6d82087b90efc3053943` was built and
verified at UID 10001 with a read-only root and network disabled: three unsupported
paid requests refused before transport, zero paid calls, safe non-AI HTTP retained.
Image ID: `sha256:0c4c4d4e0d29708fcfda6b75e98bb8eadbe3007332a8131b37e84377fe53ff52`.
It is superseded and removed after evidence capture. The matching local web image
failed with ENOSPC during npm prune, so no complete local bundle is claimed.
Final-commit full image/Compose/migration verification is required in CI.


[Machine-readable evidence and source fingerprints](evidence/WAVE4_TASK05_BUDGET.json).
PR [#271](https://github.com/moaltamimi-unbiasedtalent/Intelligent-Interview-Coach/pull/271)
contains the final exact-head workflow IDs, image manifest/digests and test results.
The historical `36ddedbe` image workflow 40193109476, migration 40193109607,
budget 40193109450, durable admission 40193109501 and Redis 40193109441 passed;
its full CI 40193109418 failed only the corrected CLI-isolation assertion.
No success on that old head is attributed to later code.


The reviewed contract is capability **2**. Intermediate Task 05 prototype images
advertised capability 1 and are deliberately refused by the final promotion and
rollback checks, despite sharing migration head 0048. The source-bound manifest
and actual image probe must both show capability 2. Future changes that strengthen
financial enforcement must review/bump this contract, rather than relying on
schema compatibility alone. Runtime file changes now fail closed before provider
transport; Admin refuses to describe a different loaded policy as operational.
Hosted approval requires an explicit owner provider-host array; local defaults are
not inherited as hosted authorization.


Final local financial qualification: **281 passed, zero skipped**, covering 16
budget PostgreSQL cases and 25 durable-agent PostgreSQL cases in the isolated
PostgreSQL 16 fixture, plus budget/client/demo/P10E/language-CLI regressions.
This includes concurrent kill, real pooled-connection termination/recovery,
configuration-file mutation refusal, partial usage, and missing-control refusal.
The final capability metadata bump has **52 release-unit checks passed**, including
refusal of None/0/1/3 capabilities when reviewed capability 2 is required.
The final exact-head CI additionally rebuilds/executes both images and runs full
backend/frontend/Browser, budget, Redis, migration and durable-admission workflows.
No local complete image bundle or final local full-backend pass is invented.
