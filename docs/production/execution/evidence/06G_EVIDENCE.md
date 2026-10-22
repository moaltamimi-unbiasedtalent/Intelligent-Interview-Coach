# 06G Evidence: independent human AI evaluation PROTOCOL AND HARNESS (PG-07; LG-04, LG-05 human part)

Branch `feat/06fg-review-packages` (shared with 06F), **STACKED on `origin/feat/06c-language-ai-behaviour` (head `fa9f02a1`, pushed, not yet merged)**. 06G extends the 06C rating protocol (`06C_RATING_PROTOCOL.md`) and harness (`src/language_quality/rating.py`, `scripts/language_rating_harness.py`), so **this branch merges after 06C**; until then its PR diff includes the 06C commits. **No migration.** No frontend change.

**05C dependency.** The budget governor (05C, `feat/05c-budget-governor`) is NOT in this tree. The generation step therefore refuses today with `governor_absent` (a test pins it) and, once 05C merges, delegates to `src.llm.budget.script_guard.guard_paid_script`. When both are merged the 05C static scan of `scripts/` finds `--live` in `scripts/language_human_eval.py` and requires the text `src.llm.budget` in that file; the script's docstring names it, so the scan is satisfied without a code change. Verified against the 05C test pattern by reading it; the merged state was not run.

## 0. Position, stated plainly

- **PG-07 is NOT passed, LG-04 and LG-05 are NOT approved, and this package cannot approve anything.** No independent rater is named, no budget is approved, no threshold is adopted, no live output was generated, no human rated anything. `language_readiness.json` is untouched.
- **No live call was made and none can be made by this package's tests.** The generation step is a script that refuses without an approved budget marker, a ceiling and the 05C governor; I never ran it live. Offline mode uses labelled FAKE replies.
- **There is no PASS in the code, the schema, the report or the status vocabulary.** The harness reports at best `READY_FOR_OWNER_REVIEW`. Thresholds are the owner's (OD-GATE-THRESHOLDS); the proposals in the report are labelled `PROPOSAL, NOT ADOPTED` and compared only informationally.
- All reviewer data in tests are obviously synthetic (`Selftest Reviewer ...`, `Test Reviewer ...`) and live in temporary directories; no real reviewer data and no invented person is committed.

## 1. Requirement mapping

| Requirement | Covered | How | NOT covered |
|---|---|---|---|
| Blinded rating of interview questions, feedback and Mo answers per language | Protocol and packet builder | `06G_HUMAN_EVAL_PROTOCOL.md`; `human_eval.build_evaluation_packet` over the 06C packet code with 12 roles x 5 task kinds = 60 outputs + 6 policy sentences + 4 controls = 70 items per sheet per language, at least 3 raters (2 refused); reviewers receive exactly the 06C files (pinned by a test) | The rating itself (OPEN) |
| Reviewer independence rules (not the author, not paid by the author's incentives, declared conflicts) | Yes | protocol section 2; `validate_declaration` and `check_independence`: explicit true or false answers, typed signature equals name, named-human rule of 06H, distinct people, conflicts need a written explanation and become `OWNER_DECISION_REQUIRED` (never auto-accepted or auto-rejected); a language is `REVIEWERS_NOT_INDEPENDENT` or `REVIEWERS_UNVERIFIED` unless every slot is eligible | Appointing anyone (owner) |
| Conflict-of-interest declaration template | Yes | `evaluations/language_ai/reviewer_declaration.template.json` (blank, booleans null) and `declaration-template` / `validate-declaration` commands | |
| Sample-size and power guidance per language with honest intervals | Yes | generated `06G_SAMPLE_SIZE_GUIDANCE.md`: items needed for a mean half-width, what 30, 60, 90 and 120 items achieve, items per language to detect a language gap at 80 percent power, zero-event items to bound a rate (rule of three); intervals in the analysis are item-level t (conservative table), Wilson and rule of three | Estimating the real rating spread (needs the first live language) |
| Inter-rater agreement computed offline (Cohen, Krippendorff) | Yes | `cohen_kappa` (none, linear, quadratic weights), `krippendorff_alpha` (nominal, ordinal, interval; missing data; `null` when undefined) and a seeded bootstrap interval. The implementation reproduces the published Krippendorff example (0.743, 0.815, 0.849), cross-checks the weighted kappa against the 06C function and a hand-computed Cohen value | |
| Results schema | Yes | `evaluations/language_ai/human_eval_results.schema.json`, generated from `RESULT_SCHEMA`, with a small validator; the schema forbids `approved: true`, any approver, date or SHA, adopted thresholds, extra keys and the word PASS | |
| Report generator that can NEVER emit PASS | Yes | `render_report_md` raises if its output contains PASS in capitals; statuses have no pass value; tests inject PASS into a note, a status and a limitation | |
| Thresholds are the owner's; proposals labelled | Yes | `PROPOSED_LEVELS` labelled `PROPOSAL, NOT ADOPTED (OD-GATE-THRESHOLDS)`; the comparison is `informational_only: true` | The numbers themselves (owner) |
| Pilot revalidation checklist (sharing, provenance, score interpretation) | Yes | `06G_PILOT_REVALIDATION_CHECKLIST.md` (P2-01 to P2-04, L-AC24) over the existing Pilot 2 pack | The pilot (NOT RUN: real participants) |
| Generation of the review sample through the 05C governor ONLY; refuses without marker and ceiling; never run by me; offline mode fake | Yes | `src/language_quality/human_eval_generate.py` (details in protocol section 5): refuses in CI, without a marker of the owner's shape, with a marker that differs from the configuration's `approval_marker`, without a positive finite ceiling, with a ceiling above the configured evaluation stop, without the configuration, when the governor is absent or refuses. Bounded output tokens, timeout, zero retries, one reply per prompt, resumable, request cap. Exactly one provider-client construction, inside `live_responder`, after the gate | The live path was never executed (no governor in this tree, no budget) |
| Selftest end to end on fake data | Yes | `python scripts/language_human_eval.py selftest`: generation (offline), packet, fake correlated ratings, fake declarations, analysis, schema validation of 7 records, report; also a CI step | |
| Single readiness checklist mapped to `language_readiness.json` | Yes | `docs/production/language_review/OWNER_READINESS_CHECKLIST.md` (shared with 06F) | |

## 2. Changes

New: `src/language_quality/human_eval.py`, `src/language_quality/human_eval_generate.py`, `scripts/language_human_eval.py`, `evaluations/language_ai/human_eval_bank_extension.json` (six profession-neutral roles, engineering translations), generated `human_eval_results.schema.json` and `reviewer_declaration.template.json`, `docs/production/execution/evidence/06G_HUMAN_EVAL_PROTOCOL.md`, generated `06G_SAMPLE_SIZE_GUIDANCE.md`, `06G_PILOT_REVALIDATION_CHECKLIST.md`, `tests/test_language_human_eval_06g.py`.
Modified: `.github/workflows/ci.yml` (one step: 06G self-test and artefact currency; no node needed). The 06C module and tests are unchanged (06C prompts are byte-identical inside the extended bank, pinned by a test).
Not touched: the readiness record, `src/llm/*`, `src/agent/*`, `src/copilot/security/*`, the frozen contracts, the tracker and the register.

## 3. Design notes and findings

- **Unit of analysis is the item.** Three raters rate the same 60 items; an item's rating is the mean of its raters, and intervals use the number of items. This is stated in the guidance and the report; rater effects are not modelled, so the interval is a little too narrow, which is why agreement is reported beside it.
- **Flags are counted per item** (flagged if any rater flagged it) over the 66 non-control items (60 model outputs and 6 deterministic policy sentences), so zero events bound the rate at 3/66, about 4.5 percent, not 5 percent.
- **Fake data and real status are separated.** A fake packet always yields `SELFTEST_ONLY`; the READY path is exercised in tests with synthetic non-fake packets in a temporary directory.
- **Why the live responder is minimal.** The live responder calls the repository's OpenRouter client with the model from the registry profile, the product's conversation-language directive and a neutral coach instruction. It does not run the full Mo or Practice product path (that needs sessions, a knowledge base and user state). The packet builder accepts any outputs file that covers the prompt bank exactly, so an operator may supply end-to-end product outputs instead. This is a stated limit, not hidden.
- The control items, rubric and blinding of 06C are reused unchanged; 06G only raises the rater minimum to three and enlarges the sample.

## 4. Tests and commands

| Check | Result |
|---|---|
| `PY -m pytest -p no:cacheprovider -q tests/test_language_human_eval_06g.py` | 34 passed (repo venv and canary) |
| `PY scripts/language_human_eval.py selftest` | selftest OK: 7 languages, status SELFTEST_ONLY, approved=False |
| `PY scripts/language_human_eval.py sync --check` | 06G artefacts current |
| `ruff check .` | All checks passed |
| `PY scripts/ci_test_shards.py verify --shards 4` | OK, each test file in exactly one shard |
| CI evaluators (every `scripts/eval_*` step of `ci.yml`, plus the 06G steps) | 49 evaluator commands from `ci.yml` run, 0 failed (every `scripts/eval_*` step incl. `eval_language_ai_behaviour`, `eval_i18n_l10n`, `eval_admin_*`, `eval_release_matrix`, `eval_w11_integrated`, plus the two 06G steps); the working tree stayed clean (evaluators write to temp) |
| Full backend suite `-n 3 --dist loadfile -q` (once, final tree) | 6,930 tests: 6,888 passed, 41 skipped (pre-existing skips, unchanged), 1 failed. The one failure, `tests/test_test_isolation.py::test_identity_evaluator_never_touches_the_developer_database_or_a_caller_supplied_one`, was a crash of the child evaluator process at interpreter exit under load (`libc++abi: recursive_mutex lock failed`, return code -6) while the evaluator itself printed `RESULT: PASS`; the same test passes when run alone and `scripts/eval_identity_platform.py` passes in the evaluator run. It touches nothing of this package. An earlier full run was interrupted by the tooling before its summary line, so the run reported here is the second |
| Fresh-dependency canary | the two new test files: 62 passed under the canary (`$HOME/.cache/ask4mo/ci_venv`); the full suite was run on the repo venv only |

Negative tests include: invalid sample (two raters; base-only outputs); every refusal reason of the generation step with a check that no refusal echoes the marker and that the governor is not called before the cheaper checks pass; a failing responder stops the run without a retry; a duplicate prompt or output is refused; the live CLI refuses and writes nothing without marker, without ceiling and in CI; a result record with `approved` true, an approver, a SHA, adopted thresholds, an extra key, an unknown language or a PASS is rejected; a missing sheet, an invalid value, failed controls, a duplicated reviewer and a declared conflict each give the specific status; statistics at their edges (n = 0 or 1, zero events, constant raters, systematic disagreement gives a negative alpha, undefined alpha is `null`).

## 5. Risks and limits

- Three raters at 60 items give wide agreement intervals; the guidance shows what precision costs. The owner may enlarge the sample (price it with the 05C governor first).
- The live responder is not the product path (section 3). Real per-language model behaviour is NOT VALIDATED by this package.
- Rater effects are not modelled; the item-level interval is somewhat too narrow with three raters.
- The proposed levels are engineering proposals chosen so a modest sample can demonstrate them; they have no authority until the owner adopts or changes them.
- The extension roles are engineering translations of role nouns; a native rater may flag an awkward word. The templates reuse 06C's generic phrasing, so a gendered or article mismatch in a role phrase is possible.
- Until 05C merges, the live step cannot run at all (fail closed), which is the intended state.

## 6. Missing human, live and gate evidence (all NOT RUN / OPEN)

Named independent raters and their declarations (OD-LANG-03); the approved budget and marker (OD-BUDGET); owner-approved thresholds (OD-GATE-THRESHOLDS); the governed live generation; the blinded rating; the report and the named approver's decision for LG-04, LG-05 and PG-07; the Pilot 2 sessions with real participants (P2-01 to P2-04, AC-24); citation and KB human reviews (C-CITE, C-KB-HUMAN) which need their own review sheets.

## 7. Owner decisions needed

1. OD-BUDGET: approve a budget and the marker; size it from `06G_SAMPLE_SIZE_GUIDANCE.md` (60 outputs per language x 7 languages = 420 replies for the default sample).
2. OD-LANG-03: appoint three independent raters per language and collect declarations; decide any `OWNER_DECISION_REQUIRED` case in writing.
3. OD-GATE-THRESHOLDS: adopt, change or reject the proposed levels in `PROPOSED_LEVELS`.
4. Decide whether a live responder over the product path (Mo and Practice with synthetic data) is wanted instead of the minimal responder, which needs a separate package.
5. Merge order: 05C, then 06C, then this branch (the generation step needs 05C in the tree to run at all).

## 8. SHA and throughput

- SHA: code commits `bcb05082` (06F) and `fa926f9f` (06G), pushed to `origin/feat/06fg-review-packages`; the final head is the evidence commit on top (an evidence file cannot name its own commit; the final report states it after `git ls-remote origin feat/06fg-review-packages`). `origin/main` was f5cf7cb and already in the base, so no merge or conflict resolution was needed. Expected conflict when other packages land: `.github/workflows/ci.yml` (one added step).
- Throughput: started 2026-10-22 about 14:30 CEST; first push 15:26 CEST; rework rounds: 2 (three test expectations of mine were wrong and were corrected against the formulas; the self-test directory was not created when `--out` was given).
