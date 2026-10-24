# Wave 4 Task 03 — immutable local images and safe promotion preparation

Reviewed 24 October 2026. Baseline: PR #268 merged at `95fd2a3c3de5ee8af64c3f5c538b8a4824ce3ff2`. Main [CI 40097363556](https://github.com/moaltamimi-unbiasedtalent/Intelligent-Interview-Coach/actions/runs/40097363556), [durable admission 40097363420](https://github.com/moaltamimi-unbiasedtalent/Intelligent-Interview-Coach/actions/runs/40097363420) and [migration image 40097363464](https://github.com/moaltamimi-unbiasedtalent/Intelligent-Interview-Coach/actions/runs/40097363464) all succeeded before infrastructure edits.

**Staging-readiness engineering, pending PR review/merge. No deployment, image publication, cloud provisioning, original/hosted database migration, paid model call, live email, language activation or gate approval.** [Measured local evidence](evidence/WAVE4_TASK03_IMAGES.json). The complete 45-package/five-layer status remains in [the dashboard](PROJECT_STATUS_DASHBOARD.md).

## 1. Problem and artifact identity

The existing Compose topology built API, worker and migration separately, and had no verified release/rollback pointer. `scripts/release_images.py` now builds one API application image and one matching frontend from an explicit full Git SHA. It uses `git archive` into a fresh temporary root, preserving the existing build context layout while excluding untracked environments, databases, node_modules, caches and unpublished artwork. No checkout/worktree is moved, cloned, reset or cleaned.

`release.json` records both **local Docker content-addressed image IDs**, source SHA, shared UTC build-start stamp, normalized actual image creation times, native platform, actual Python/Node/OS dependency metadata, dependency-file hashes, source/build-input hashes, the single migration chain/head, reviewed compatibility policy, prompt asset hashes and activation-record hash. These are local image IDs, **not registry distribution references**; `registry_digest` is explicitly null. No upload or remote digest is invented.

The API, worker and migrate roles are generated from one manifest entry, never separate operator-supplied tags. Frontend labels/env and its public API build URL are checked against the same release, and the proxy API domain is pinned to that URL. Both images retain their existing non-root users/commands. Frontend build dependencies come from the lockfile, are pruned for runtime without rewriting the lockfile, and Next.js telemetry is disabled.

API image verification reads actual source/migration/prompt/activation bytes in the image and compares them with the committed snapshot. Native probes verify dependency metadata and uid, using no external network and read-only filesystems. The helper rejects missing fields, unknown/duplicate JSON fields, incorrect SHA/anchor, malformed/missing/substituted image IDs, wrong metadata, mixed platforms, changed source assets, unsupported registry records and mismatched actual image contents. A normal image built without release metadata cannot become a verified release accidentally.

One API build is performed per bundle; all backend roles reuse it. A second build, even at the same SHA, is a different candidate requiring a new manifest review. Existing output directories are refused. The base images and Python dependency ranges are not made reproducible locks by this task: final image IDs freeze the observed result; recorded inventories identify it. No reproducible-byte or formal SBOM/signature claim is made.

## 2. Trust boundary and local/offline workflow

Use the checked-out, reviewed release tool. Supply a full 40-character commit SHA. A CI candidate is not an approval. Keep the canonical manifest SHA-256 from review in a trusted channel separate from the files; do not recalculate and bless an unreviewed replacement. Checksums are integrity checks, not signatures or protection against someone who can change the files and trusted anchors together.

```sh
python scripts/release_images.py build --sha <reviewed-40-char-SHA> \
  --api-base-url https://api.staging.example.com/api/v1 --out <NEW-bundle-directory>
python scripts/release_images.py verify --manifest <bundle>/release.json \
  --expected-sha <reviewed-SHA> --manifest-sha256 <trusted-manifest-hash>
python scripts/release_images.py export --manifest <bundle>/release.json \
  --expected-sha <reviewed-SHA> --manifest-sha256 <trusted-manifest-hash> --out <NEW-transfer-directory>
python scripts/release_images.py import --manifest <bundle>/release.json \
  --expected-sha <reviewed-SHA> --manifest-sha256 <trusted-manifest-hash> \
  --archive <transfer>/images.tar.gz --archive-sha256 <trusted-archive-hash>
```

Export saves the exact two IDs into a checksummed compressed archive. Import checks the trusted manifest/source/expected SHA and archive digest, loads locally, then verifies the actual loaded images again. It does not start them. No push/login or registry-promotion command exists. Verification uses local inspection and `--pull never`; generated application services use `pull_policy: never`.

The measured offline round trip removed only this task's web-image tags without force, observed verification refusal while it was absent, loaded the saved archive and verified the original IDs/content again. Native engine/store/platform compatibility is a precondition, not a universal portability claim. A different store/platform that cannot preserve/resolve the verified IDs is refused. Future registry publication, signing/attestation and multi-platform/distribution-digest handling require a separate authorized design.

Docker references: [image inspection](https://docs.docker.com/reference/cli/docker/image/inspect/), [Compose pull policy](https://docs.docker.com/reference/compose-file/services/#pull_policy), [local archive loading](https://docs.docker.com/reference/cli/docker/image/load/).

## 3. State observation and plan-only profiles

The tool never loads a private .env by default or uses DATABASE_URL as a source fallback. `observe-disposable` accepts only an explicit RELEASE_TEST_DATABASE_URL naming a file under the system temporary directory or a loopback p5b_* PostgreSQL database. It performs read-only schema/count queries. It refuses an unversioned nonempty database, multiple revision rows, or a current-head schema missing run controls. It cannot be used to inspect the original development SQLite or an arbitrary hosted database.

```sh
# Supply a disposable test URL through RELEASE_TEST_DATABASE_URL, never a real target.
python scripts/release_images.py observe-disposable --attest-drained --out <NEW-state.json>
python scripts/release_images.py prepare --manifest <bundle>/release.json \
  --expected-sha <reviewed-SHA> --manifest-sha256 <trusted-manifest-hash> \
  --state <fresh-reviewed-state.json> --mode promote --env-file <absolute-runtime-env-file> --out <NEW-plan-directory>
python scripts/release_images.py check-compose --manifest <bundle>/release.json \
  --expected-sha <reviewed-SHA> --manifest-sha256 <trusted-manifest-hash> \
  --state <same-fresh-state.json> --mode promote --env-file <absolute-runtime-env-file> --profile <plan>/compose.yml
```

`prepare` creates only a new compose.yml, reviewed Caddyfile copy and plan.json. Runtime env contents are never copied into images, manifests or plans. `check-compose` privately captures Docker's resolved configuration (which can contain secrets), checks bounded identity/topology fields, and never logs/persists that resolved document. It verifies profile/proxy checksums, API/worker/migrate image identity, frontend/proxy association, fixed staging/production modes, commands, non-root-image use, absence of build/privilege/entrypoint overrides and original persistent-volume names/targets. It refuses a changed runtime database identity, including namespace-option differences, without recording credentials.

The state file contains revision, unsettled-run/active-job counts, observation time and a non-secret logical database-identity hash. Credentials are excluded from that hash. It must be at most five minutes old and bind to the prepared plan and resolved runtime database. **Drain is an operator attestation, not something this tool proves.** Pause admissions, drain/stop all writers (including old binaries), keep them paused through the change, and repeat the observation immediately before an authorized operation. Matching configured identities is not proof of physical server identity or health. Observe in the correct namespace; do not bypass a fingerprint mismatch.

A future hosted observation needs separate authorization and reviewed target/server/checkpoint identity evidence; the disposable observer does not grant it. Plans cannot remove TOCTOU risk from active writers. This tool has no deploy/up/start/down, SQL write, migration, downgrade, restore, usage-settlement or force-unlock action.

## 4. Migration and application rollback policy

Promotion preserves the original one-shot `bash scripts/migrate.sh`, `restart: no`, healthy PostgreSQL requirement and API/worker `service_completed_successfully` dependency. The exact verified API image supplies that job and both processes. API/worker default startup never runs migrations. Only an authorized future operation may execute a prepared profile.

Use `prepare` and `check-compose` with **--mode rollback** for a separately reviewed previous release. Its profile removes migrate and its dependency entirely; no Alembic command runs during application rollback. Existing PostgreSQL/ClamAV health dependencies and persistent volume identities remain. Do not combine this profile with the base build file or additional overlays; the verifier refuses unexpected services/builds and mixed image identities.

`deploy/release-policy.json` is conservative: compatible schema revisions are **only the image's exact single migration head**, currently 0048. Unknown/newer/older revisions refuse application rollback. Promotion can plan an ordered upgrade from base/an ancestor, but cannot plan a downgrade or an unknown revision. A migration/policy mismatch fails build until reviewed; compatibility ranges are never guessed. A schema match is necessary, not a claim that every data/checkpoint format or operational journey is qualified.

Any active job, unsettled producer, stale/unknown state or missing drain attestation refuses preparation. Unsettled agent usage is never changed, zeroed or silently released. Incompatibility means stop/forward-fix or use a separately authorized recovery procedure—not automatic database downgrade/restore. [The existing backup/restore runbook](../BACKUP_RESTORE_RUNBOOK.md) remains authoritative for that separate work.

## 5. Actual local verification and CI

Local candidate images were built from committed source **6ec1eb3a0bc5ee7c81d1cbbb5e3cb90c722df25b**, Linux arm64. The final PR's metadata-only/doc/tool refinements have a later commit; CI builds and verifies that exact PR head separately. Do not attribute the local image IDs to the later commit.

- Manifest anchor: `49e3e8a12a8be0a03c6597c9008a746460da049bd053ee4fa1c0dfc6192ca98c`.
- API/worker/migrate ID: `sha256:33b7a8cfa08da58f870d65f9f3b48bc6d86255128110e78c4a9f0e8e086c0876`.
- Frontend ID: `sha256:52e0220960fdfd9fb8bc8cb31f59d0102b92ada740ad89aae10f605e7c68fe8c`.
- **9 real-image tests passed**, including native file/metadata inventories, immutable Compose resolution, wrong-image/metadata/DB refusal, schema-incompatible/unsettled rollback refusal, checksum-protected offline export/missing-image refusal/import, and the frontend default command serving Ask4Mo inside a disposable network-none container with no host ports.
- The same API ID was given a verified, unique test alias solely because Dockerfile FROM needs a named local reference. The **3 existing migration-image tests passed** against it: repeat-safe PostgreSQL head upgrade, preservation on a synthetic failed upgrade, and actual Compose startup blocking. The alias never appears in release profiles.
- A network-none built-image synthetic probe verified PR #268 durable admission and retained actual cumulative usage (2 fake calls/18 tokens/1,800 micro-USD), disabled billing and zero offered staging languages. No provider was contacted. The original 50-case PostgreSQL admission CI remains required.
- Initial real verification exposed Docker's local-offset timestamp presentation; the tool now normalizes actual times to UTC. Failed candidates had no valid release manifest. A real Compose check exposed logical versus physical volume-name representation; both are now checked correctly. No refusal assertion was weakened.
- Focused regressions passed; the existing rollback-rehearsal case lacking a registered current-head seeder remains skipped, not qualified. Exact final counts/run links are in the PR. It belongs in the later backup/recovery milestone, not this change.

`.github/workflows/immutable-release.yml` checks out the exact candidate SHA with history, builds once per role, runs these real tests, and uploads metadata/build logs only. It never uploads image archives to a registry or invokes deployment. Full repository CI, Browser E2E, durable-admission and migration-image workflows remain enabled. Their final SHA-bound results are recorded in the PR; no main-SHA browser result is invented.

## 6. Project status and remaining dependencies

**40/45 engineering packages remain integrated.** Task 03 is a focused 05A readiness follow-up, pending review/merge; POST265-01/02 are merged. 00A/00B/07B/07C/08A remain open/incomplete. Live staging/multi-worker/proxy/provider/recovery qualification is NOT RUN. Human qualification and all PG/LG records are unchanged: only PG-11 accepted, zero qualified hosted languages. All original worktrees/refs/private files are preserved; the original database remains untouched at its last observed 0027 (21 pending revisions).

The next focused task should be **shared Redis rate limiting and an explicit outage policy**, after this PR is reviewed, merged and green. Dependencies: owner choice of managed/internal Redis and region/isolation (OD-HOSTED), the recorded H-REDIS-POLICY behavior, pinned compatible client/server artifacts, and disposable concurrency/outage tests. Do not claim per-process fallback is distributed fail-closed.

Separate subsequent milestones remain:

- Fresh OD-BUDGET ceilings/pricing/marker/config and explicit AI-budget enforcement; no paid validation before authorization.
- PostgreSQL client tools/backup runner, off-host encrypted sets and independent erasure ledger, key custody, retention/legal decisions, current-head rollback seeder, safe restore profile and authorized measured restore/rollback drills. No backup/restore implementation changed here.
- Owner hosting/region/domains, infrastructure image digests (PostgreSQL/ClamAV/Caddy retain existing tags), secret delivery, TLS/proxy/health/monitoring/on-call, actual volume permissions/persistence and all-writer rollout/drain evidence.
- Real scanner/signature/EICAR qualification; licensed source/embedder/index decisions and reliability; 07B/07C residual live evidence; reviewer/legal appointments and per-language approval; finally 08A freeze and owner go/no-go.

None of these gaps is closed by an image build, a plan or CI. Stop before provisioning, deployment, registry publication or live paid evaluation until separately authorized.
