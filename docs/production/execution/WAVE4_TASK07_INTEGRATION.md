# Task 07 — reconciled disposable qualification and external release gates

## Reconciled connected qualification — 27 October 2026

Implementation merge `939b7f020609850a56cf5b15cbcefb6ec328c284` retains original PR #273 `bc75b4c772e5468934d033fe565eac5b921e4927` and reviewed main `ef2e97ef88b4f4b67640c4c677f3ef3247594cd2` as its parents. PRs #274–276 are merged; all seven main-push baseline workflows succeeded. Two semantic conflicts were resolved: the immutable workflow runs **both** CSP and full connected campaigns with separate safe uploads; the release tracker retains dated historical blocks under a current-state header. All reviewed CSP/checkpoint/History application changes remain identical to main. Existing Task 07 startup repairs, probes and evidence remain present. No new application permission or migration was introduced.

**Mandatory offline qualification PASS:** **29 PASS / 0 FAIL / 0 SKIP / 6 NOT RUN**, 268.381 seconds. The machine result remains `PARTIAL_EXTERNAL_DEPENDENCIES` to preserve the external qualification boundary. The historical **27 PASS / 2 FAIL / 6 NOT RUN** snapshot below is unchanged. Its two confirmed application defects are repaired by merged PRs #274/#275 and verified here; PR #276's History repair is retained. The historical image-optimizer stall's root cause remains **inconclusive**.

| Measured artifact at `939b7f02` | Identity |
|---|---|
| API / API B / both workers / one-shot migration | `sha256:3236a8afe03ae1adb9620d27f65ac0d2da5bf332f215df67db3f5b1b003a8410` |
| Production Next.js | `sha256:ee56b434f465b1c5b8d555dc65a373060c4ebe5ec691b58ca8f279d58bec6e9b` |
| Recovery operator | `sha256:f08d227feb4f4b373f8b0bcb721c6b3c1c0cec4a919952542c4ffe8bb3899b2d` |
| Release manifest canonical SHA-256 | `10437c97faf47f48889000c3aadb593a1406ea7d25393a6bdb092946bac9c0d1` |
| Operator manifest canonical SHA-256 | `e52931c3fade04cbb49680c33f27ea1b72bb2e790d2b99fbfcc926692c1c8329` |
| Build started | `2026-10-27T11:10:52Z` |
| Sole Alembic head | `0048_agent_run_controls` |
| Prompt-assets hash | `a00e7b3ab6b17d9c058dc9da69d5f8923ecadb8f2fa938fdc7bac89d04b3ad97` |
| Language activation hash (unchanged) | `05a0f9f5d182d0614d03006cf23d0e559fa2e3684db0ad6f18fff60a333aa4c1` |

Canonical anchors use the existing release helper's normalized JSON, not pretty-printed file-byte hashes. Manifests include dependency/OS/runtime metadata, source hashes and local immutable image IDs; registry publication was not performed. [Image, CSP, connected and operator evidence](https://github.com/moaltamimi-unbiasedtalent/Intelligent-Interview-Coach/actions/runs/40494036211) records fresh builds; historical images were not reused. A following evidence-only commit has its own exact-head CI/images at [PR #273 checks](https://github.com/moaltamimi-unbiasedtalent/Intelligent-Interview-Coach/pull/273/checks); the measured identities above belong specifically to `939b7f02`.

The real topology used PostgreSQL 16.15, Redis 8.2.9, Caddy 2.11.7, ClamAV 1.4.6, two APIs, two workers and a separate recovery operator/restore destination. All networks were internal and no host ports were published. Non-root UID 10001, shared backend image/private named volumes, migration helper and successful one-shot 0048 migration were observed. Failed migration exited 1 and left API/worker dependents stopped. Inaccessible private storage stayed unhealthy. Owned cleanup passed without pruning unrelated resources.

Both existing APIs returned checkpoint HTTP 200 **before and after** the real database outage. Container/start/restart identities remained unchanged, explicit restart was false and model calls remained zero. The restart workaround has been removed from the current campaign. SSE reconnect did not execute the model; HITL duplicate resume returned 409; cancellation settled execution with incomplete usage preserved. API SIGKILL retained unsettled/unknown usage and refused takeover with 409. Budget ceilings/unknown reservations/kill state, Redis outage/refusal/recovery, scanner refusal/clean/EICAR, worker lease retry, owner isolation, trusted proxy/CORS and private-storage refusal all passed.

Connected Playwright **3/3 passed**: edge, real cross-origin auth and hydrated UI sign-in, authenticated History/Opportunities reads, actual images, nonce-less injection refusal, UI logout and revoked session. The intentional injection produced one expected CSP refusal; bootstrap refusals were zero. Separate CSP qualification also passed two negative injections, nonce rotation/spoof refusal and secure session/logout. Primary Browser evidence and full suite totals are listed in the CI record below; assertions and timeouts were not relaxed.

Encrypted transfer/restore used independent disposable local storage: backup 1.434 s, restore 1.312 s, 690,410 bytes. Erasure ledger reapplied (one account/file, six checkpoints); surviving owner checkpoint/control and unknown monetary state remained. Persistent hold returned API 503 and worker zero claims. These observations do not approve production RTO/RPO, off-host custody or hold release.

### Source-bound CI results

- [Encrypted recovery qualification — 40494049889](https://github.com/moaltamimi-unbiasedtalent/Intelligent-Interview-Coach/actions/runs/40494049889): SUCCESS on `939b7f02`.
- [Redis shared limiter regression — 40494047663](https://github.com/moaltamimi-unbiasedtalent/Intelligent-Interview-Coach/actions/runs/40494047663): SUCCESS on `939b7f02`.
- [AI budget governor qualification — 40494044906](https://github.com/moaltamimi-unbiasedtalent/Intelligent-Interview-Coach/actions/runs/40494044906): SUCCESS on `939b7f02`.
- [Agent durable admission regression — 40494041253](https://github.com/moaltamimi-unbiasedtalent/Intelligent-Interview-Coach/actions/runs/40494041253): SUCCESS on `939b7f02`.
- [Staging migration image regression — 40494038630](https://github.com/moaltamimi-unbiasedtalent/Intelligent-Interview-Coach/actions/runs/40494038630): SUCCESS on `939b7f02`.
- [Immutable local release regression — 40494036211](https://github.com/moaltamimi-unbiasedtalent/Intelligent-Interview-Coach/actions/runs/40494036211): SUCCESS on `939b7f02`.
- [Browser E2E — 40494033223](https://github.com/moaltamimi-unbiasedtalent/Intelligent-Interview-Coach/actions/runs/40494033223): SUCCESS on `939b7f02`.
- [CI — 40494014328](https://github.com/moaltamimi-unbiasedtalent/Intelligent-Interview-Coach/actions/runs/40494014328): SUCCESS on `939b7f02`.

Backend **8,726 passed / 181 skipped**, 8,907 reconciled executions; all deterministic security/privacy evaluators and extra guards passed. Frontend **1,561 passed**, types/lint/build PASS. Browser: **672 passed / 14 skipped** primary suite, plus **50 repeated History cases passed** at zero retries; legacy smoke PASS. Release image tests **16 passed**, operator **19 passed**; migration image **3 passed**; durable admission **50 passed** plus **17 PostgreSQL outage scenarios**; AI budget **126 passed**; Redis **17 passed**; recovery **105 passed / 1 image-only skip**, covered separately by actual operator/image and connected runs. Local checks are separate overlapping selections: 114/33 and 141/16, with service/image skips not counted as passes.

### Six historical NOT RUN scenarios, reassessed individually

- `new_hosted_language_registration_and_interviews` — NOT RUN: no hosted language is approved or active; strict registration/activity refusal remains enforced.
- `positive_language_interview_and_career_journeys` — NOT RUN: positive language-bearing production journeys require qualified activation and separate authorization; existing synthetic agent fixtures do not qualify them.
- `live_ai_quality_and_embeddings` — NOT RUN: no paid/provider/embedding authority; only deterministic local model responses and empty unactivated knowledge collection were used.
- `real_email_oidc` — NOT RUN: email was memory capture; no external delivery or live OIDC/IdP activation authorized.
- `hosted_tls_and_signature_freshness` — NOT RUN: private internal CA and offline EICAR-only signatures prove local controls, not public TLS/network or signature currency/coverage.
- `release_recovery_hold` — NOT RUN: restore hold intentionally persists; named operational authority and custody/go-no-go decisions are absent.

### Preservation, release gates and review boundary

Audit: 48 original worktrees (31 dirty), 316 original branch tips and 200 protected/untracked files recorded; all protected hashes, original statuses and branch tips were unchanged before promotion. Original PR head has a backup ref. Original SQLite remains untouched (last observed 0027; no new database inspection). [Preservation/merge audit](WAVE4_TASK07_INTEGRATION_AUDIT.md) and structured evidence retain the private-inventory hash, not secrets or database contents.

**40/45 engineering packages integrated.** 00A/00B/07B/07C/08A remain open/incomplete. PG-01/PG-07 BLOCKED; PG-04/PG-06/PG-09/PG-15 NOT STARTED; PG-02/PG-03/PG-05/PG-08/PG-10/PG-12/PG-13/PG-14 IN PROGRESS; existing PG-11 alone PASS. LG-01–LG-14 have zero human-approved gates per language; zero languages are hosted-active. These are retained acceptance states, not derived from this campaign. Owner decisions remain open for hosting/region/secrets, budget authority, Redis policy, knowledge/licensing/approved embeddings/markets, reviewers/native/legal qualification, backup/erasure-key custody/off-host storage/retention/RTO/RPO, monitoring/alerts and release authority.

Next: owner review of existing PR #273 and its final exact-head green checks, followed by owner-controlled merge and verification of new main. Any Task 08 staging scope requires a separate explicit instruction. No deployment, paid provider call, real email/OIDC, registry publication, real/original database migration, production/language acceptance or automatic PR merge is authorized or performed.

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

## Latest measured implementation — 6680cf37

[Exact-source image and campaign run](https://github.com/moaltamimi-unbiasedtalent/Intelligent-Interview-Coach/actions/runs/40357744233)
on `6680cf3762ee8826164bded72f952c479f820fd7`: **27 PASS / 2 FAIL / 6 NOT RUN**,
0 SKIP, 313.210 seconds. This is the final implementation qualification snapshot.
A documentation-only commit records it; the final head's current CI/image artifacts
remain authoritative at [PR #273 checks](https://github.com/moaltamimi-unbiasedtalent/Intelligent-Interview-Coach/pull/273/checks).
No successful qualification or staging readiness is claimed.

| Artifact | Exact measured identity |
|---|---|
| API / API B / worker / worker B / migrate | `sha256:255960f8d901d0daa865b44769581d529cfd5e9a872e9d08cb00fdc72857e0a4` |
| Next.js | `sha256:caf9d0fb61a1e54f2b024d407a8b51f237ca88da0547c9e40aee383abd174abe` |
| Operator | `sha256:8313694fcb61dc147eb3335a74bd6ab077e84431017a33165d2d84b5a22a75cc` |
| Release manifest SHA-256 | `a661d7010df3e07b55331891b5fcc5d2e81d127550c00668ee355e8d9a742dcc` |
| Operator manifest SHA-256 | `ebb1f66876b5b8c68f486bfeae57df4131f3836882405077599af2290b2b879e` |

PostgreSQL 16.15, Redis 8.2.9, ClamAV 1.4.6 and Caddy 2.11.7 were observed.
Private root/role UID, image/volume identity and the sole 0048 head pass.
Backend CI: **8,711 passed / 164 skipped**, exactly 8,875 reconciled executions.
Frontend CI: **1,534 passed**, type/lint/build pass. Browser E2E and the final
head are reported separately from the connected browser checks.

The new proxy observation passes: forged forwarded headers do not change the
client fingerprint, real forwarded scheme/host remain correct, CORS allows only
the configured origin, HTTP 404 propagates and no internal endpoint is exposed.
The observer records a private HMAC only, never the raw client address.

Redis outage now passes with actual 503/unreachable metadata (observed 0.019 s
in this run), plus synthetic local/deny policies. The bounded observer still
fails if the required shared readiness never refuses; bucket policies are unchanged.
The existing two-second cache can affect other runs' first sample and is not
presented as instantaneous detection or a new production SLO.

The actual checkpoint-read check **FAILS with HTTP 500 after DB restart**.
Only a separately labelled explicit API restart restores HTTP 200, with zero
model calls. That workaround does not fix POST272-04. After it, actual API
SIGKILL while an owner Caddy stream is connected passes: usage remains publicly
incomplete, durable state stays unsettled, takeover returns 409 and no duplicate
execution occurs. The first stream event was observed at 98.3 ms. Cancellation
observations measured 59.2/50.1 ms, one idle heartbeat and zero reconnect calls;
all are local synthetic observations, not hosted performance promises.

The connected browser still has two passing edge/auth transport checks and one
user-UI timeout with 12 inline-script CSP refusals. POST272-03 remains P1.

Backup/transfer/restore passes: **1.343 s / 1.251 s**, **687,212 bytes**. Independent
local destination, integrity/release binding, deletion reapplication, surviving
owner checkpoint/control, preserved monetary unknowns and persistent recovery
hold pass. Actual held API is 503 and worker claims are zero. Hold release stays
NOT RUN. These durations exclude service reconciliation/hold release and are
not approved RTO/RPO. Docker free-space observations were 82,440,867,840 bytes
before and 82,072,326,144 after owned cleanup; peak RAM/CPU was not qualified.

Failures left for separate PRs: POST272-03 and POST272-04. Six owner/hosted gaps
and the 40/45 package / PG / LG / owner-decision status below remain unchanged.
All historical attempts are retained with their original source/image identities.

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
