# Task 07 — disposable connected integration (qualification in progress)

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

## Current evidence

Baseline main: `992682c3fa9c891f5710c993e7d595f363b8c811`; seven mandatory workflows
succeeded. Local expanded regression: 260 passed, 46 skipped. Ruff, TypeScript and
issue reconciliation pass. Local full-stack execution is blocked by Docker
capacity; no cleanup of unrelated resources is authorized. Feature-head CI and
connected campaign evidence remain pending. See the pre-change audit for two
narrow startup repairs. Task 07 is not complete yet.

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
