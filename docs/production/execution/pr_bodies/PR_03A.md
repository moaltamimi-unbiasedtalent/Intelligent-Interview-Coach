# 03A: Grouped Admin navigation and Admin-only Review and Diagnostics (REQ-OWN-08)

**Branch:** `feat/03a-admin-navigation`  **Head SHA:** `7a6f484`  **Compare URL:** https://github.com/moaltamimi-unbiasedtalent/Intelligent-Interview-Coach/pull/new/feat/03a-admin-navigation
**Programme:** Ask4Mo Production Roadmap V2.2, S1 full R1.0 scope (owner-approved), first engineering wave.

## Requirements and package IDs
Package 03A. REQ-OWN-08 N1 to N5 (ADMIN-01); owner-approved six sections.

## Change summary
Six owner-approved Admin sections placing all 20 destinations once; collapsible keyboard-accessible sidebar, breadcrumbs, quick navigation over visible destinations only, mobile drawer; Review and Diagnostics moved under `/admin/review` with redirects from the old URLs and removed from the Candidate More menu while `/review/agent` stays owner-scoped for Candidates. No new permission (registry stays 44) and no backend authorization change; new backend 403 tests cover the diagnostics routes.

## Acceptance criteria
All destinations reachable and permission-aware; a group with no visible destination is hidden; backend permissions still enforced regardless of the UI; Candidate cannot reach platform diagnostics.

## Tests and evidence
vitest 1114, Playwright 89 (new navigation spec plus admin and a11y specs), pytest 107 under the fresh venv (two files also under the repo venv), tsc, lint, ruff; eval_admin_qualification PASS. Evidence: docs/production/execution/evidence/03A_EVIDENCE.md.
Local green tests do not replace GitHub CI: the PR's own checks are the CI evidence.

## Risks and limitations
Command Center diagnostics links still carry the old `/review/rag` path (works through one redirect); redirects live in next.config.mjs; section collapse state is not persisted; the role fixture was edited by one token rather than regenerated (the qualification evaluator verifies it); full backend suite and a standalone build were not run by the author.

## Dependency and merge order
Sixth (independent). 03A owns frontend/components/admin/AdminShell.tsx, frontend/lib/admin/capabilities.ts and frontend/components/layout/nav-items.ts; 03B to 03E rebase on it. Overall first-wave order: 02K, 01B0, 03K, 05A, 01A, 03A, 06A; then stacked 02A (on 02K), 01B (on 01B0), 06H (on 06A); shared agent-policy order 01B, then 01D, then 01C. A dry-run merge of all seven branches onto main produced no conflicts (tests/contracts/__init__.py is an identical empty file on three branches).

## Boundaries honoured
No production deployment, no paid provider call, no Stripe or billing activation, no destructive data operation, no historical evidence rewritten, no gate weakened, no R1.0 scope reduced. Do not merge until required CI, review and acceptance evidence exist.
