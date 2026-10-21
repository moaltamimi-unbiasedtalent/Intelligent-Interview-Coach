# 02K: Knowledge runtime, index manifest and scanner contracts (interface package)

**Branch:** `feat/02k-knowledge-contract`  **Head SHA:** `f5eb3dc`  **Compare URL:** https://github.com/moaltamimi-unbiasedtalent/Intelligent-Interview-Coach/pull/new/feat/02k-knowledge-contract
**Programme:** Ask4Mo Production Roadmap V2.2, S1 full R1.0 scope (owner-approved), first engineering wave.

## Requirements and package IDs
Package 02K. REQ-OWN-05 K3/K4; REVIEW-04 R1/R4/R5 (contract part). Unblocks 02A, 02B, 02C and 05B.

## Change summary
Adds `src/knowledge_admin/contracts.py`: `RuntimeIdentity` and builder, `identities_compatible` (typed mismatch report, never raises), `IndexManifestV2` with a deterministic compatibility hash, `embedder_matches`, readers for the existing manifest formats, and the scanner types with a fail-closed `scan_accepted` rule. No behaviour change, no migration, no existing file modified.

## Acceptance criteria
Contract merged with a conformance suite that 02A, 02B and 02C must pass; unknown values stay unknown and never count as a match; no secrets, credentials or absolute paths in any serialised identity or manifest; legacy manifests parse without inventing fields.

## Tests and evidence
125 passed under both the repo venv and the fresh-dependency venv (tests/contracts, knowledge admin, readiness, hardening); ruff clean; shard plan OK. One rework round (3 first-run failures fixed). Evidence: docs/production/execution/evidence/02K_EVIDENCE.md.
Local green tests do not replace GitHub CI: the PR's own checks are the CI evidence.

## Risks and limitations
Database fingerprint hashes a low-entropy string, so it must not be exposed publicly; records built before 02B report as unknown/incompatible until re-indexed; no embedder version source exists yet; the degradation rule is a contract decision 02B may refine; the live ClamAV path is untouched.

## Dependency and merge order
First. No dependency. Merge BEFORE 02A (stacked on it), 02B, 02C. Use a merge commit (not squash) or tell the integration lead so stacked branches can be rebased. Overall first-wave order: 02K, 01B0, 03K, 05A, 01A, 03A, 06A; then stacked 02A (on 02K), 01B (on 01B0), 06H (on 06A); shared agent-policy order 01B, then 01D, then 01C. A dry-run merge of all seven branches onto main produced no conflicts (tests/contracts/__init__.py is an identical empty file on three branches).

## Boundaries honoured
No production deployment, no paid provider call, no Stripe or billing activation, no destructive data operation, no historical evidence rewritten, no gate weakened, no R1.0 scope reduced. Do not merge until required CI, review and acceptance evidence exist.
