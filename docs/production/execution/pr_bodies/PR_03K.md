# 03K: Admin metric and report contract (interface package)

**Branch:** `feat/03k-admin-metric-contract`  **Head SHA:** `8afe350`  **Compare URL:** https://github.com/moaltamimi-unbiasedtalent/Intelligent-Interview-Coach/pull/new/feat/03k-admin-metric-contract
**Programme:** Ask4Mo Production Roadmap V2.2, S1 full R1.0 scope (owner-approved), first engineering wave.

## Requirements and package IDs
Package 03K. REQ-OWN-01 C2; REQ-OWN-04 B1/B2/B4/B5 (contract part). Unblocks 03D1 and 03E1.

## Change summary
Adds `src/reporting/contract.py` (strict pydantic metric, dimension, report and result models; registry validation; missing data never zero; cohort minimum cannot go below 5; no SQL or column names expressible), an adapter over the 21 existing metrics, the API schema module, matching TypeScript types and a committed JSON schema, and a conformance suite. No new metrics, routes, permissions or migrations; `/admin/reports/definitions` is unchanged.

## Acceptance criteria
Contract merged with conformance tests that 03D1 and 03E1 must pass; TS types stay in sync with the Python schema; permission registry stays at 44.

## Tests and evidence
183 passed under both venvs (contract, reporting, openapi contract, admin foundation, access, qualification); ruff clean; shard plan OK; tsc and lint clean; vitest 28 passed. Evidence: docs/production/execution/evidence/03K_EVIDENCE.md.
Local green tests do not replace GitHub CI: the PR's own checks are the CI evidence.

## Risks and limitations
The SQL-like guard is heuristic (the slug and closed-enum design is the real protection); existing reports define no charts because existing metrics have no time dimension; the first commit message says WIP, so squash with a clean message.

## Dependency and merge order
Third (independent). Merge BEFORE any dashboard or report backend (03D1, 03E1). Overall first-wave order: 02K, 01B0, 03K, 05A, 01A, 03A, 06A; then stacked 02A (on 02K), 01B (on 01B0), 06H (on 06A); shared agent-policy order 01B, then 01D, then 01C. A dry-run merge of all seven branches onto main produced no conflicts (tests/contracts/__init__.py is an identical empty file on three branches).

## Boundaries honoured
No production deployment, no paid provider call, no Stripe or billing activation, no destructive data operation, no historical evidence rewritten, no gate weakened, no R1.0 scope reduced. Do not merge until required CI, review and acceptance evidence exist.
