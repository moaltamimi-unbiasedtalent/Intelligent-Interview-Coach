# Wave 4 Task 01 — POST265-01 migration entrypoint

Baseline: PR #266 merged at `560aba5cc4b3f0d6940ed6221053f2ed459027a4`. Main CI [40022997608](https://github.com/moaltamimi-unbiasedtalent/Intelligent-Interview-Coach/actions/runs/40022997608) succeeded. The repair branch is `fix/staging-migration-entrypoint`; this work is pending PR review/merge, not integrated or deployed. The project remains **40/45 integrated**, with 00A/00B/07B/07C/08A open or incomplete.

## Root cause and repair

Compose's one-shot migrate service runs `bash scripts/migrate.sh` in the image's `/app` working directory. The Dockerfile copied the root `scripts/` directory, while the wrapper exists only in `deploy/scripts/migrate.sh`. The image therefore lacked the configured entrypoint.

The sole deployment behavior change is `COPY deploy/scripts/migrate.sh ./scripts/migrate.sh` in `deploy/Dockerfile.api`, before the existing ownership change and `USER appuser`. Build context, architecture, wrapper, Alembic graph, container command, one-shot service and API/worker migration dependencies are unchanged. There is no migration on API/worker boot and no automatic downgrade.

## Reproducible real-image checks

```sh
docker build -f deploy/Dockerfile.api -t ask4mo-migration-test:wave4 .
RUN_MIGRATION_IMAGE_TESTS=1 MIGRATION_TEST_IMAGE=ask4mo-migration-test:wave4 \
  .venv/bin/python -m pytest -q -o addopts='' -p no:cacheprovider tests/test_staging_migration_image.py
```

The new CI workflow performs the same build and explicitly enables these tests on an Ubuntu runner; the normal backend suite skips this Docker-only module unless explicitly enabled. A missing image/daemon/database fails the enabled job, rather than silently skipping.

Local real-image regression: **3 passed** on Docker 29.5.2 / Compose 5.5.0, Linux arm64. Built image identity: `sha256:55cf7aa274a3dbb26e7e3930fd69f1ae643d7703c2cefd4bb87ab76dc4913ef0`.

- The actual image contains the configured helper and Alembic config in `/app`; execution uses non-root uid 10001, the default command remains uvicorn, and no migration entrypoint is added to application startup.
- The exact Compose migration command upgraded a fresh disposable PostgreSQL 16 database to the dynamically discovered single head, currently `0048_agent_run_controls`. A second execution succeeded at the same head and preserved a pre-existing synthetic sentinel row.
- A disposable derived image injects a synthetic failing revision after that head. The revision deletes a synthetic sentinel and raises. The upgrade exits nonzero, PostgreSQL rolls the deletion back, and the prior revision remains unchanged. With the production `service_completed_successfully` dependency copied into startup probes, neither API nor worker starts after migration failure. Probe commands replace application commands only in the test topology; no application deployment occurs.
- No host ports, private volumes or existing database URL/env file are used. PostgreSQL uses tmpfs. Test containers, network and the fault-injection image are removed afterward. A Docker-VM host bind-mount issue in the initial test harness was fixed by building the disposable fault image; no production code or assertion was weakened.

The synthetic failure proves transactional failure preservation for the exercised PostgreSQL upgrade; it is not a guarantee that all future migrations are reversible. There is no automatic retry, restore or downgrade. Existing backup, forward-fix and nonempty-0048 downgrade safeguards remain mandatory.

Additional local validation: **180 passed** across migration, topology/security, fail-closed language activation and OpenAPI contracts; **116 passed** across release-evidence, reconciliation and package-register suites. Ruff, diff hygiene, shard allocation, generated five-layer matrix freshness, issue reconciliation and the hosting-readiness/product-positioning/release-matrix/admin-design evaluators passed. Frontend code is unchanged; the standard repository CI performs its full frontend/backend/evaluator/browser checks on the PR.

## R1.0 disposition and remaining work

The local development SQLite database remains untouched at its previously observed 0027 revision (21 revisions outstanding). No original database was opened for this test or upgraded, downgraded, deleted or restored. All original branches/worktrees and authored local assets/environment/database files are preserved. Generated Python caches may change during checks.

This repair removes POST265-01 only after its PR is reviewed, merged and green. It does not close PG-01 or PG-09. Staging/production deployment and hosted verification remain NOT RUN; human qualification and production/language approval records are unchanged. Only PG-11 retains PASS and no language is qualified for hosted activation.

Remaining staging blockers include owner hosting/region/domain authorization, immutable image pointers, backup/restore tools and encrypted off-host recovery drills, Redis/client/outage policy, budget governor wiring, real scanner/signature checks, source/embedding/index qualification and qualified-language journeys. See [the gap-based plan](STAGING_READINESS_PLAN_POST265.md). The previous PR #266 Browser result (667 passed, 14 skipped, one candidate multi-page network-idle timeout) remains unresolved historical evidence, not a passing check inferred from this repair.

Next, **only after this repair is reviewed, merged and green**, prepare POST265-02 separately: durable owner-scoped cross-instance admission for unsettled runs, unchanged actual usage accounting, and disposable PostgreSQL concurrency/Stop/HITL/settlement qualification. No part of that implementation is included here. 00A appointments, 00B scope decisions, authorized 07B/07C evidence, independent qualification and 08A freeze/go-no-go remain required.

No cloud deployment, paid AI, live email, production migration, legal approval or language activation occurred. PR checks and final regression counts are recorded in the PR description at its exact commit.
