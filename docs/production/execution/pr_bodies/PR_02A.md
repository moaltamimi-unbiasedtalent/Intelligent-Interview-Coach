# 02A: Permanent Knowledge persistence, environment identity and recovery (REVIEW-04 part 1)

**Branch:** `feat/02a-knowledge-persistence`  **Head SHA:** `a898505f` (verified on origin)  **Compare URL:** https://github.com/moaltamimi-unbiasedtalent/Intelligent-Interview-Coach/pull/new/feat/02a-knowledge-persistence
**Stacked on:** `feat/02k-knowledge-contract` (f5eb3dc). Open after 02K merges, or stacked on it.

## Requirements and package IDs
Package 02A. REQ-OWN-05 K1, K2, K3, K5, K7, K9; REVIEW-04 R1 to R3 (persistence, identity, recovery). Depends on 02K. 02B owns embedding enforcement, 02C the malware scanner.

## Change summary
Root cause of the "empty sources" failure: the governed private-file directory defaulted to `$TMPDIR/ask4mo_knowledge`, so uploads vanished on restart or redeploy. It now defaults to `<data root>/knowledge_private` on the index volume. One runtime configuration object shared by API and worker; worker identity fingerprints in the heartbeat id (no schema change); `KnowledgeServingGuard` refuses governed retrieval and uploads in hosted environments on identity mismatch, empty or missing governed collection, missing files, non-persistent or temp placement and hosted SQLite (retrieval degrades visibly, never returns an empty list silently); extended readiness endpoint and Admin Environment identity panel; replace (idempotent), reindex (id-only job) and retire; backup, verify and restore CLI (`scripts/knowledge_backup.py`, dry-run default, never deletes or overwrites, tamper refused, restore into a separate environment and verified); four in-app alert categories. **One migration: `0040_knowledge_alert_categories`** (data-preserving, fail-closed downgrade, single head); head literals updated across tests, evaluators and docs.

## Acceptance criteria
Sources, versions, files, indexes and attributable retrieval survive restart, redeployment and restore; a wrong or empty environment is refused and reported, never presented as empty knowledge; recovery never overwrites; no secrets or paths serialised.

## Tests and evidence
Offline drills pass: restart persistence, queued job across restart, redeployment in a new interpreter, separate-environment restore, disaster drill, refusal cases, alerts, migration up and down. Full backend suite run sequentially: 5217 passed, 41 skipped, 0 failed (repo venv); 5215 passed, 43 skipped, 0 failed (fresh venv). ruff, shard plan, eval_admin_knowledge, eval_admin_jobs pass; vitest 1087; the four head-literal evaluators pass after fix commit a898505. Evidence: docs/production/execution/evidence/02A_EVIDENCE.md. GitHub CI not yet run.

## Risks and limitations
Proven offline only: not on hosted volumes, PostgreSQL or multiple workers (needs 05A/05B drills and OD-HOSTED). K4 partial (embedder version and compatibility hash unknown until 02B); scanner is 02C; reindex and replace have API routes but no UI buttons; Chroma teardown aborted intermittently in early runs (fixed in the harness, watch CI); backup assumes a quiesced index; guard result cached 15 s; a restore needs an explicit existing approver user because of the approval-evidence CHECK.

## Dependency and merge order
After 02K. It owns the only new migration of this wave: no other package may add a revision before it merges, and any branch hard-coding a head literal must rebase. 05A owns the staging Compose file; 02A does not edit it. Hosted knowledge serving stays refused until the staging topology (05A) and OD-HOSTED exist.
