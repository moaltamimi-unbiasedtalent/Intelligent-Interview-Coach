# Task 07 — measured disposable integration and staging blockers

This branch reuses the existing immutable release and recovery image workflow.
It creates a fresh internal Compose project, synthetic PostgreSQL database, two
API instances, two workers, Redis, ClamAV, Next.js and Caddy with an internal CA.
No ports are published. Linux CI accesses Caddy on its campaign-owned private bridge address; every network remains internal. No original environment or data is mounted.

## Repeatable command

After building a reviewed commit and recovery runner with `scripts/release_images.py`,
run the following from the repository root. Use a new output directory, sufficient
Docker capacity (minimum 8 GiB free after images are built), on a Linux host
with a local Docker daemon. A browser outside a Docker VM cannot use the private
bridge directly; native macOS qualification is NOT claimed:

```sh
python scripts/integration/campaign.py --execute-disposable \
  --manifest /absolute/release/release.json \
  --manifest-sha256 "$(cat /absolute/release/release.sha256)" \
  --runner /absolute/recovery/recovery.json \
  --runner-sha256 "$(cat /absolute/recovery/recovery.sha256)" \
  --expected-sha REVIEWED_COMMIT --out /absolute/new-campaign-directory
```

The frontend image must have the public API build origin
`https://api.staging.example.com/api/v1`. Those reserved names resolve only through
the test browser/curl private-address overrides; there is no public DNS/ACME operation.
Application, worker and migration share one verified image ID; the operator is the
verified derived image. Neither image is published. Ordinary API/worker commands
remain unchanged outside this explicitly guarded fixture topology.

`summary.json` distinguishes PASS/FAIL/SKIP/NOT RUN. `browser-summary.json` contains
only test IDs, status and timing. `safe-logs.json` contains log hashes/counts and
fixed event classifications; raw logs are intentionally not exported.
`service-evidence.json` contains state/health/exit status only. The private directory
holds synthetic session material; never upload it or browser traces. Cleanup checks
campaign labels on containers, networks and volumes before Compose down. No image,
cache or unrelated resource pruning is performed.

## Deliberate boundaries and unqualified work

API_ENV remains staging, with zero activated languages. Fixture account creation
uses the real invitation, authentication and captured-email domain services; it is
not evidence of successful hosted registration. New language-bearing HTTP activity
must remain refused. Only the agent dependency uses a deterministic local model
and a no-retrieval stub; authentication, ownership, SSE, PostgreSQL checkpointers,
registry, scanner and budget enforcement remain real. No AI quality claim follows.
ClamAV runs the real daemon with an offline harmless EICAR signature database;
production signature currency and coverage remain unqualified.

Initial driver covers startup/schema/private roots, sessions/ownership/admin,
actual worker diagnostic jobs, completed-run SSE/reconnect, conservative shared
ledger fixtures, real clamd, connected browser/Caddy and dependency outages.
The expanded driver also exercises existing-fixture HITL, active cancellation, API
process loss, real worker crash/lease/retry, failed migrations, inaccessible roots
and encrypted transfer/restore into a held target with real API/worker refusals.
Those additions still require actual built-image campaign evidence. Positive new
language-bearing journeys remain blocked by activation policy. The expanded edge observer measures initial-event flushing and heartbeat
comments, disconnects/reconnects without execution and remains connected during
upstream API termination; its real-stack results are still pending; subsystem CI is not substituted for
connected proof.
The release report must carry those gaps until actual execution evidence exists.

## Evidence and qualification boundary

Baseline main: `992682c3fa9c891f5710c993e7d595f363b8c811`; seven mandatory workflows
succeeded. Local expanded regression: 263 passed, 46 skipped. Ruff, TypeScript and
issue reconciliation pass. Local full-stack execution is blocked by Docker
capacity; no cleanup of unrelated resources is authorized. Source-bound connected
evidence is recorded below; current-head results are linked in PR #273. See the
pre-change audit for two narrow startup repairs. Qualification has not passed.

40/45 packages remain integrated. PG and LG approvals, owner budget/Redis/hosting,
key/erasure custody, retention/RTO/RPO, native/legal review and freeze/go-no-go
remain unchanged. Hosted deployment, live providers, email and releasing recovery
hold require separate authorization. Task 08 starts only after review, merge,
green main and the owner's specifically authorized staging scope.

First image run on `f8ab77382558cffe5a6d2e283dd5cb741e3f763d`: 16 actual image tests and 19 operator tests passed. The connected preflight stopped before service creation with `loopback_tls_port_occupied`; the privileged-port bind probe was replaced with a listener check so an unprivileged CI user does not misreport EACCES as an occupied port. No connected success is inferred from that run.

Second image run on `ec8335cc43e90c132f06fabcfbeb5c447417ef80`: 16 image
checks and 19 operator checks passed. The connected campaign verified images and
started actual healthy PostgreSQL, Redis and ClamAV, then failed during bootstrap;
application/proxy/browser scenarios were NOT RUN. Owned cleanup passed. A bounded
local RAM-backed diagnostic reproduced the fixture's `IndexIncompatibleError`.
The fixture now preserves staging's rejection of hash embeddings and leaves the
knowledge collection empty. Its account/run setup and five core probes pass in
a single-API old-image/current-code diagnostic; that is explicitly not release-image,
full-stack, scanner or multi-instance qualification. [Machine evidence](evidence/WAVE4_TASK07_INTEGRATION.json).

The knowledge/source/index recovery scope is therefore an empty, unactivated
collection with strict hash-embedding refusal. Actual approved embedding/source
qualification remains open. Real synthetic document bytes, accounts, checkpoint
and unsettled control state, and conservative monetary entries are the connected
recovery targets. No language or embedding guard has been bypassed.

Third image run on `f0ea5371fe992db6ec482363ed2190f2612689cb`: all actual
application, worker, frontend, database, Redis and scanner health checks passed;
Caddy was running and the one-shot migration exited successfully. The host edge
probe failed, so product scenarios were NOT RUN. Caddy 2.11.7 and Redis 8.2.9 were
observed. The runner no longer relies on port publishing on an internal network:
Linux CI reaches the private Caddy bridge address directly, keeping all networks
internal and publishing no host port. See Docker's [internal-network guidance](https://docs.docker.com/compose/how-tos/networking/#internal-networks)
and [host bridge access](https://docs.docker.com/engine/network/port-publishing/#gateway-modes).
Cleanup again removed only campaign-owned resources. This observation is startup
proof, not a successful connected application or browser campaign.

## Measured connected campaign — d8144725 (26 October 2026)

Exact source: `d81447254bd2a85f5a27bc37a3a07bc62cc2e192`.
[Image/campaign run](https://github.com/moaltamimi-unbiasedtalent/Intelligent-Interview-Coach/actions/runs/40292438392).
This source-bound snapshot ran for 314.162 seconds: **23 PASS, 3 FAIL, 6 NOT RUN,
0 SKIP**. Later runner observations are qualified separately by the
[current PR checks and safe artifacts](https://github.com/moaltamimi-unbiasedtalent/Intelligent-Interview-Coach/pull/273/checks).
The PR description records the final head and its outcomes; this historical
snapshot is preserved rather than relabelled as a newer run.

| Artifact | Actual identity |
|---|---|
| API, second API, both workers, migrate | `sha256:6a323a50cd96e3556013147302c325eb35d82bc6e896ed560a1444ce41eeb34c` |
| Next.js | `sha256:ee3d23b736460f150b75d821183a30c4f6dee7d6d413e3447e08fe3b3487dd81` |
| Recovery operator | `sha256:09eb2e0917ff6947a3af005cc389330b87f7ad79931a98b67b47513bd0966f4a` |
| Release manifest SHA-256 | `c2db9823ca208ded9b67acb7f296e2337fb54ab242118bfe88a0500fb5721286` |
| Operator manifest SHA-256 | `4e06fed04a85a4dc5bc4a35ce4f23a4a807174575aa25e09550b33497b34ab5c` |

Actual versions: PostgreSQL **16.15**, Redis **8.2.9**, ClamAV **1.4.6**, Caddy
**2.11.7**. Application UID: **10001**. Exactly one app Alembic head:
`0048_agent_run_controls`. The five backend roles used identical content IDs,
shared private named-volume identities and the matching reviewed frontend.
The topology had two ordinary API instances and two workers, with fault/held
profiles bringing the defined service count to 18. No host ports or external
networks were enabled. Offline clamd definitions cover the harmless EICAR fixture
only; signature currency and real malware coverage remain unqualified.

| Area | Measured observation |
|---|---|
| Identity and persistence | Captured-email/invitation fixtures; real shared sessions, expired-session rejection, logout, profile/opportunity/history reads and owner boundaries; candidate Admin access refused |
| Documents | Real clean upload 201, byte-identical owner download, foreign access 404, EICAR upload 422; separate surviving-candidate bytes |
| Agent | Existing synthetic runs use the real graph/PG checkpoint; two SSE reads produce zero model calls; HITL resume 200 and duplicate 409 |
| Cancellation | Independent continuation refused 409; cancellation settles execution while usage remains incomplete; no provider call |
| Proxy stream | TLS 1.3; first events observed at 53.4/53.2 ms, one idle heartbeat, no model execution on reconnect; local measurements do not certify hosted performance/TLS |
| Worker | Actual diagnostic job claimed once; a killed diagnostic worker's expired lease retries once and succeeds at attempt 2; active idempotency key creates no duplicate |
| Budget | Eight concurrent direct ledger-fixture admissions stay within the synthetic ceiling; unknown reservation survives, retries refuse, kill persists; real serving governors remain CLOSED without approval |
| Browser | EDGE-01 and AUTH-01 transport checks pass; UI-01 times out at 45 seconds; every page records 12 inline-script CSP refusals. No successful end-user sign-in UI journey is claimed |
| Restart | API/worker restart keeps revision 0048; one-shot migration stays separate |
| Recovery | Encrypted verified set transferred to an independent disposable local volume; backup 1.400 s, restore 1.287 s, 686,457 bytes; erasure reapplied for one account, one file and six checkpoints; a surviving owner's checkpoint/control remains |
| Recovery admission | Actual held API returns 503; real worker makes zero claims; monetary unknowns remain; recovery hold is never cleared |
| Resource observations | Docker free space before: 82,437,554,176 bytes; after owned cleanup: 82,068,942,848 bytes. This is a free-space observation, not peak resource or production capacity/RTO/RPO certification |

### Failure injections A–L

| Case | Initial condition and injection | User/DB observation and recovery |
|---|---|---|
| A PostgreSQL | Healthy source; stop only its owned DB | Readiness 503; readiness returns after restart, but the later agent operation cannot enter its model. A bounded diagnostic confirms cached checkpoint reads return 500 after connection loss and 200 after explicit API restart; POST272-04 remains open |
| B Redis | Healthy shared limiter; stop owned Redis | The first immediate readiness sample remains cached 200, so the initial test FAILS. Existing probes have a two-second cadence. The revised runner requires 503 within a bounded five-second observation, checks the public state header and exercises synthetic local/deny policies; production policies are unchanged |
| C Worker | Claimed diagnostic job with explicit eight-second fixture lease; SIGKILL holder | Real normal workers reap/retry and complete attempt 2; active duplicate enqueue refused. Production lease/default topology are unchanged |
| D API streaming loss | New existing-run fixture; attempt slow continuation | NOT INJECTED in this snapshot: the model never enters after the DB outage. The revised runner records the checkpoint defect, labels an explicit recovery restart, then separately attempts actual upstream termination while an owner stream is connected |
| E Scanner | Healthy clamd; stop owned scanner | Scan refuses; restart restores real clean/EICAR results. No fake scanner or unsigned production definitions are accepted |
| F Provider errors | Typed deterministic timeout/429 model exceptions | Safe failed result; usage stays incomplete. No real transport/provider execution |
| G Budget exhaustion | Shared PG typed synthetic ledger | Cap/retry refusal and persistent unknown reservation/kill; no owner marker |
| H Cancellation | Active scripted model and independent API | Concurrent producer 409, cancel 200, execution settled, usage incomplete; no zero-cost inference |
| I Image mismatch | Existing genuine-image preflight suite | 16 image checks pass, including digest/metadata/worker substitution and incompatible/unsettled rollback refusal. No mismatched release is promoted and no database downgrade is attempted |
| J Migration | Healthy source; one-shot migrator targets a nonexistent disposable DB | Migrator exits 1; API/worker dependents do not run; healthy source stays at 0048 |
| K Private root | Separate fault API points at inaccessible `/proc` root | API remains unhealthy and cannot enter readiness. No original/private-volume permissions are changed; this is a configured-root failure, not a real disk-device failure |
| L Recovery hold | Restore into a new empty disposable database | Persistent DB/file hold, erasure reapplication, API 503 and worker zero claims. Hold release requires external named operational authority |

### Focused follow-up PRs required

- **POST272-03 / P1 — Caddy CSP and Next.js hydration.** The actual configured edge
  blocks Next's inline bootstrap and the user sign-in flow fails. Prepare a
  reviewed CSP/hydration repair with real browser proof; retain strict script,
  origin, frame and connection boundaries. Do not add permissive directives to
  make this campaign green.
- **POST272-04 / P1 — Checkpoint connection recovery.** The app keeps one official
  PostgreSQL saver connection alive. Database connection loss leaves agent reads
  failing even after general readiness recovers. The owned RAM-backed diagnostic
  measured 500, then 200 only after an explicit process restart. Qualify a safe
  connection lifecycle in a separate PR; never replay an uncertain execution or
  settle unknown usage as zero. The campaign records the workaround separately
  and keeps the original defect check failed.

The two narrowly repaired startup defects (POST272-01 fresh knowledge mount
ownership and POST272-02 CLOSED/offline guard conflict) are verified by the actual
non-root connected startup. They do not repair the two defects above.

### Remaining qualification and release decisions

Six scenarios remain NOT RUN for owner/hosted dependencies: new activated-language
registration/interviews; positive interview/career generation; live AI/approved
embeddings; real email/OIDC; hosted TLS/network and scanner-definition freshness;
and named-authority release of recovery hold. Synthetic scope excludes AI quality,
semantic retrieval and a populated approved Knowledge Sources restore. Independent
backup/erasure-key custody, off-host storage, retention, monitoring/alerts and
approved RTO/RPO remain open. Native macOS/full-image execution was not run because
Docker has only about 674 MB free; no unrelated Docker resources were pruned.

R1.0 remains **40/45**. Open packages: **00A, 00B, 07B, 07C, 08A**. Engineering and
qualification are separate: Tasks 01–06 are merged; Task 07's report identifies
staging blockers. [All PG-01–PG-15 states and LG-01–LG-14 language states remain
in the release tracker](RELEASE_READINESS_TRACKER.md). Only the existing PG-11
machine check remains PASS. Every language has 0/14 human-approved gates and none
is hosted-active. OD-HOSTED, OD-BUDGET, H-REDIS-POLICY, embedding/source/market,
reviewer/legal/native, custody and release-owner decisions receive no approval.

Priorities: review this focused draft and its exact-head results; remediate
POST272-03 and POST272-04 in separate PRs with disposable qualification; reconcile
and rerun this campaign on merged green main; then prepare Task 08's specifically
authorized staging plan. No deployment, provisioning, registry publication, paid
call, real email, production/original SQLite migration or language activation is
authorized by these results.
