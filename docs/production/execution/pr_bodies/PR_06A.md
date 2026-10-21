# 06A: Seven-language inventory, locale boundaries and Russian exclusion

**Branch:** `feat/06a-locale-boundaries`  **Head SHA:** `f7b2e03 (corrections in progress)`  **Compare URL:** https://github.com/moaltamimi-unbiasedtalent/Intelligent-Interview-Coach/pull/new/feat/06a-locale-boundaries
**Programme:** Ask4Mo Production Roadmap V2.2, S1 full R1.0 scope (owner-approved), first engineering wave.

## Requirements and package IDs
Package 06A. REQ-LANG-01, 07, 11, 12, 13, 14; LG-01, LG-02, LG-07, LG-13, LG-14.

## Change summary
Code-defined `ACTIVE_CANDIDATE_LOCALES` (en, de, fr, es, it, pt, nl) with `effective_locale`; Russian rejected (422) for new preferences, registration, chat, agent runs and interview creation but preserved in catalogues, prompts and code; a stored Russian preference reads back as English without rewriting the row or changing geography; capabilities expose the active locales; selectors show seven languages; generated per-language audit (2382 keys per language, 0 missing) and `language_readiness.json` (no language qualified: LG-01 and LG-14 PASS with evidence, LG-02/07/12/13 ENGINEERING DRAFT, the rest NOT RUN or NOT STARTED); separation tests; claims gate extended.

## Acceptance criteria
Seven selectable languages; zero production-qualified languages; fourteen gates required per enabled locale (enforcement is package 06H); no qualified translations yet; Russian excluded from active selection and its skipped tests visibly excluded from passing totals.

## Tests and evidence
Python full suite 5172 passed on the repo venv and 5170 on the fresh venv (0 failed); vitest 1087; affected Playwright 49+103 passed, 14 skipped (dormant Russian specs); tsc, lint, ruff and the language evaluators pass. Evidence: docs/production/execution/evidence/06A_EVIDENCE.md (being corrected).
Local green tests do not replace GitHub CI: the PR's own checks are the CI evidence.

## Risks and limitations
Native and legal review and live per-language quality unvalidated; market mapping neither approved nor implemented; stale active docs (CLAUDE.md, README) and the evidence statements are being corrected on this branch; gate-driven activation is NOT in this PR (package 06H).

## Dependency and merge order
Seventh (independent). 06H is stacked on it. Re-run the dry-run merge after the corrections. Overall first-wave order: 02K, 01B0, 03K, 05A, 01A, 03A, 06A; then stacked 02A (on 02K), 01B (on 01B0), 06H (on 06A); shared agent-policy order 01B, then 01D, then 01C. A dry-run merge of all seven branches onto main produced no conflicts (tests/contracts/__init__.py is an identical empty file on three branches).

## Boundaries honoured
No production deployment, no paid provider call, no Stripe or billing activation, no destructive data operation, no historical evidence rewritten, no gate weakened, no R1.0 scope reduced. Do not merge until required CI, review and acceptance evidence exist.
