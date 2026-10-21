# 05A: Complete the staging topology as code (not deployed)

**Branch:** `feat/05a-staging-topology`  **Head SHA:** `0a7d6fb`  **Compare URL:** https://github.com/moaltamimi-unbiasedtalent/Intelligent-Interview-Coach/pull/new/feat/05a-staging-topology
**Programme:** Ask4Mo Production Roadmap V2.2, S1 full R1.0 scope (owner-approved), first engineering wave.

## Requirements and package IDs
Package 05A. PG-01 partial; REQ-OWN-05 K1/K3/K6 prerequisites; EX-12.1 to EX-12.6, EX-12.14, EX-12.15; H-ENV; H-WORKER; Phase 00 gap G1.

## Change summary
Staging Compose now has db, migrate, api, worker, web, caddy and clamav: the job worker shares the authoritative `COPILOT_DATA_DIR` and a persistent `knowledge-data` volume with the api, the documents volume is shared with the worker, ClamAV is internal-only, the api healthcheck uses `/api/v1/ready` (hosted: data-root writability gates; worker heartbeat and scanner status are reported), staging and production refuse `FILE_SCAN_PROVIDER=fake`, backup and restore scripts include the knowledge data root, plus README and operations notes. NOT deployed; the deployment freeze stays until OD-HOSTED.

## Acceptance criteria
Compose parses with exactly the seven services and shared data root and volumes; no real secrets in the files; hosted readiness and config guard tests pass; backup and restore round trip verified with stubs.

## Tests and evidence
114 passed, 1 skipped (29 new) under both venvs; ruff clean; scripts/eval_hosting_readiness.py PASS. Evidence: docs/production/execution/evidence/05A_EVIDENCE.md.
Local green tests do not replace GitHub CI: the PR's own checks are the CI evidence.

## Risks and limitations
Never run through `docker compose config` or `up`; the ClamAV image tag, healthcheck and start period are unconfirmed; worker claiming tested on SQLite only; embedder is still the hash fallback until REVIEW-04; knowledge-data starts empty (02A); no real restore drill (05B). Deployment needs OD-HOSTED.

## Dependency and merge order
Fourth (independent). 05A owns deploy/docker-compose.staging.yml; 02A and 02C must not edit it. Overall first-wave order: 02K, 01B0, 03K, 05A, 01A, 03A, 06A; then stacked 02A (on 02K), 01B (on 01B0), 06H (on 06A); shared agent-policy order 01B, then 01D, then 01C. A dry-run merge of all seven branches onto main produced no conflicts (tests/contracts/__init__.py is an identical empty file on three branches).

## Boundaries honoured
No production deployment, no paid provider call, no Stripe or billing activation, no destructive data operation, no historical evidence rewritten, no gate weakened, no R1.0 scope reduced. Do not merge until required CI, review and acceptance evidence exist.
