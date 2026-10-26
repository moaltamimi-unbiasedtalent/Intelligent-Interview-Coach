# Task 07 — disposable connected integration (qualification in progress)

This branch reuses the existing immutable release and recovery image workflow.
It creates a fresh internal Compose project, synthetic PostgreSQL database, two
API instances, two workers, Redis, ClamAV, Next.js and Caddy with an internal CA.
Only loopback port 443 is published. No original environment or data is mounted.

## Repeatable command

After building a reviewed commit and recovery runner with `scripts/release_images.py`,
run the following from the repository root. Use a new output directory, sufficient
Docker capacity (minimum 8 GiB free after images are built), and free loopback 443:

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
the test browser/curl loopback overrides; there is no public DNS/ACME operation.
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
Active cancellation, HITL, process-loss, retry/lease faults, connected recovery,
failed-migration and inaccessible-volume scenarios require further driver work.
They are NOT RUN, not passes; subsystem CI is not substituted for connected proof.
The release report must carry those gaps until actual execution evidence exists.

## Current evidence

Baseline main: `992682c3fa9c891f5710c993e7d595f363b8c811`; seven mandatory workflows
succeeded. Local focused regression: 198 passed, 17 skipped. Ruff, TypeScript and
issue reconciliation pass. Local full-stack execution is blocked by Docker
capacity; no cleanup of unrelated resources is authorized. Feature-head CI and
connected campaign evidence remain pending. See the pre-change audit for two
narrow startup repairs. Task 07 is not complete yet.

40/45 packages remain integrated. PG and LG approvals, owner budget/Redis/hosting,
key/erasure custody, retention/RTO/RPO, native/legal review and freeze/go-no-go
remain unchanged. Hosted deployment, live providers, email and releasing recovery
hold require separate authorization. Task 08 starts only after review, merge,
green main and the owner's specifically authorized staging scope.
