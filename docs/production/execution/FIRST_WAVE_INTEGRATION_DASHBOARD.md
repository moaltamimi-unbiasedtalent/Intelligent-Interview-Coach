# First-Wave Integration Dashboard

Superseded on 2026-10-22: PRs #213 to #221 are merged (see `WAVE2_EXECUTION_DASHBOARD.md`). The table below is the historical pre-PR dashboard and is kept unchanged; the live state is the wave 2 dashboard and the tracker. 01A is the only first-wave branch still unmerged.

| Package | Branch | Head SHA (verified on origin) | PR | CI | Review | Local result | Open items |
|---|---|---|---|---|---|---|---|
| 02K | feat/02k-knowledge-contract | f5eb3dc | not opened | not run | none | 125 passed, both venvs | merge before 02A |
| 01B0 | feat/01b0-prompt-contract | 6f6d383 | not opened | not run | none | 462 passed, both venvs | merge before 01B |
| 03K | feat/03k-admin-metric-contract | 8afe350 | not opened | not run | none | 183 passed; vitest 28 | merge before 03D1/03E1 |
| 05A | feat/05a-staging-topology | 0a7d6fb | not opened | not run | none | 114 passed, 1 skipped | compose never run through docker; deploy needs OD-HOSTED |
| 01A | feat/01a-injection-corpus | 6b2dbc2 | not opened | not run | none | 293 passed | held-out detection 54.5%; thresholds need OD-GATE-THRESHOLDS |
| 03A | feat/03a-admin-navigation | 7a6f484 | not opened | not run | none | vitest 1114, Playwright 89, pytest 107 | full backend and standalone build not run by author |
| 06A | feat/06a-locale-boundaries | 5dbe48f (corrections b29b860) | not opened | not run | none | 5172 passed full suite before corrections; 133 affected tests passed after, both venvs | Task 3 corrections delivered; full suite and full Playwright not re-run after the doc commit |
| 01B | feat/01b-versioned-prompts | 7c2b879 | not opened | not run | none | 5286 passed, 0 failed | stacked on 01B0 |
| 02A | feat/02a-knowledge-persistence | a898505 (fix of 9b3f6a0) | not opened | not run | none | 5217 passed, 0 failed (repo venv); 5215 (fresh venv) | stacked on 02K; migration 0040; offline proof only |

Compare URLs and PR descriptions: `docs/production/execution/pr_bodies/PR_<ID>.md`.

## Integration review
- Dry-run merge of the seven first-wave branches onto main in order 02K, 01B0, 03K, 05A, 01A, 03A, 06A: **no conflicts** (106 files). `tests/contracts/__init__.py` is an identical empty file on three branches and merges cleanly.
- Integrated tree, local only: ruff clean, shard plan OK (273 files), tsc 0, lint 0, vitest 113 files / 1131 tests passed. Integrated backend run was in progress (about 48%) when this was written; it is not CI.
- Re-run on 2026-10-21 with corrected 06A (5dbe48f) and 01B (7c2b879) included: all eight branches merge cleanly in order, no conflicts (188 files, local only).
- Third dry-run with all nine branches (02A a898505 included): no conflicts (257 files, local only). It found and fixed two integration defects: 02A's migration 0040 broke four evaluators asserting head 0039 (fixed in a898505); and a Phase 00 test asserted the staging compose still lacks the worker, which fails once 05A merges (fixed in docs commit dc90ac6, merge with or before 05A). The integrated evaluators eval_w11_integrated, eval_rc_p10_003, eval_admin_security, eval_admin_qualification and eval_doc_consistency pass.
- 02A owns the only new migration (0040) this wave: no other package may add a revision until it merges.
- 01B touches `src/agent/policies.py` and `deploy/Dockerfile.api`; the second dry-run included it.

## 06A disposition
Delivered on branch, not merged. Seven selectable languages, zero production-qualified languages, fourteen gates required per enabled locale, no qualified translations yet. Russian catalogues and code preserved; skipped Russian tests documented and excluded from passing totals. Stale eight-language wording in CLAUDE.md, README.md, CLAIM-014 and locale headers is corrected on the branch (main still says eight until merge); 14 Russian Playwright tests stay skipped and are listed in `06A_RUSSIAN_TESTS_EXCLUDED.md`, with passed totals excluding them. Gate-driven activation is **not** in 06A: it is the new package 06H.

## Language activation control (Task 4)
New package **06H** (depends on 06A; decisions OD-LANG-03, OD-LANG-04) enforces LG-01..LG-14 server-side: a locale is offered only with a complete approved record (all 14 PASS, evidence reference, named approver, date, release SHA, none stale). Production fails closed, including when no locale qualifies. Testable now with synthetic fixtures. S1 scope unchanged. Registered in the package register, graph and schedule.

## Merge order (recommended only after GitHub CI, review and acceptance evidence)
1. 02K, then 02A and dependent Knowledge work.
2. 01B0, then 01B, then 01D, then 01C (shared agent policy files).
3. 03K, then 03D1/03E1 dashboard and report backends.
4. 05A (owns staging Compose), 01A (owns ci.yml edits this wave), 03A (owns Admin shell).
5. 06A, then 06H.
The independent contract and scaffold PRs (02K, 01B0, 03K, 05A, 01A, 03A, 06A) can merge in any order once green; use merge commits so stacked branches rebase cleanly.

## Blockers
1. Owner must open the PRs (compare URLs in the PR body files); CI evidence cannot exist until then.
2. No review has happened; reviews of about 58 PRs are the binding constraint.
3. 02A delivered; hosted persistence proof needs 05A/05B drills and OD-HOSTED.
4. Outstanding owner decisions: OD-HOSTED (staging deployment), OD-GATE-THRESHOLDS (injection thresholds), OD-LANG-02/03/04 (market mapping, native reviewers, legal translation), plus the 18 open decisions in the Owner Decision Register.

## Measured throughput (authoring only)
Packages 02K, 01B0, 03K, 05A, 01A, 03A, 06A, 01B were authored in roughly 25 to 60 minutes of wall-clock each by Claude Code sessions against estimates of 2 to 8 engineering days. Those estimates include human review, integration and CI, none of which has yet been measured. The forecast is therefore **unchanged**: planning date early to mid December 2026; 30 November holds only as the low-estimate, unlimited-review-capacity bound. The date is gate-driven and no scope is cut.
