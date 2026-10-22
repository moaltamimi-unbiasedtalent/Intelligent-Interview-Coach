# Wave 2 Execution Dashboard

Updated 2026-10-22. Strategy S1 (full R1.0 scope, owner-approved). Target 30 November 2026, conditional on every mandatory gate. Main @ `f9a06a9`.

## 1. Integration baseline (Phase 1)
- Main `f9a06a9` is the merge of PR #214. GitHub CI on it (re-read 2026-10-22): all 10 check runs reported so far completed with success. The push-triggered run reports fewer check runs than a PR run (no Next.js Playwright or Legacy Streamlit smoke entry was listed), so the last PR head, a7559a9, with 12 of 12 successful checks, remains the stronger evidence for the integrated tree.
- Merged: #213 docs, #214 06A, #215 02K, #216 03A, #217 01B0, #218 05A, #219 03K, #220 01B, #221 02A. No open PR. 01A is NOT merged and has no PR (its branch is being updated, section 3).
- Reconciliation and package validation: `reconcile_issues.py check` and `execution_packages.py check` pass (45 packages, every R1.0 item in exactly one package, acyclic).
- **No production gate is PASS because a code PR merged.** Evidence still missing is listed in section 6 and in `RELEASE_READINESS_TRACKER.md` section 7.

## 2. Measured first-wave throughput (real PR timestamps, UTC 2026-10-21)
| PR | Package | Open to merge | Rework rounds after open |
|---|---|---|---|
| #215 | 02K | 0h41m | 0 |
| #217 | 01B0 | 0h41m | 0 |
| #219 | 03K | 0h41m | 0 |
| #220 | 01B | 0h49m | 0 |
| #218 | 05A | 1h35m | 2 (obsolete Phase 00 assertion; merge conflict) |
| #221 | 02A | 2h22m | 2 (stale migration-head allowlists, hidden behind the first failing evaluator) |
| #216 | 03A | 3h15m | 1 (evaluator counted group ids as destinations) |
| #214 | 06A | 3h51m | 1 (esbuild missing in Python CI shards) |

Reading: owner review is fast when it is available, so reviewer latency was not the binding constraint in wave 1. The real cost was CI hygiene: five of eight needed 1 to 2 rework rounds for hard-coded migration heads and cross-branch assertions that only CI exposes (CI stops at the first failing evaluator). Wave 2 therefore starts with a prep branch that makes every head-literal check version-independent, because eight parallel PRs may each add a migration. This is evidence about process, not a verified effort ratio: wave 1 was interface contracts, scaffolds and one additive migration, with no human qualifier, licence, native reviewer or live staging in the path.

## 3. Wave 2 packages delivered (isolated worktrees; branches pushed; NO PR exists for any of them, so no GitHub CI has run; nothing is merged)
Heads were verified on `origin` by the lead. "Local" results are not CI.

| Package | Branch | Head | Base | Migration | Local result | Notes |
|---|---|---|---|---|---|---|
| PREP-HEAD | chore/migration-head-agnostic | ec14963 | main | none | 44 proof tests; 1123 affected tests pass with a throwaway 0041; 46 evaluators green | converts 28 test files and 13 evaluators from the hard-coded head `0040` to a chain check; open and merge FIRST |
| 01A | feat/01a-injection-corpus | b3acd4b | main (merged in) | none | 281 targeted pass; 46 evaluators | held-out detection 54.5% to 77.3% (weakly contaminated), benign FP 14.3% unchanged; needs a human security review |
| 02B | feat/02b-embedding-integrity | 135070c | main | none | 91 new; full suite 5609 pass | hosted fail-closed embedder and manifest enforcement; production-embedder benchmark NOT RUN |
| 02C | feat/02c-clamav-scanning | 164d839 | main | none | 54 new; 282 targeted pass | verified only against a fake clamd; no real clamd |
| 06H | feat/06h-language-activation | a0d01c8 | main | none | 211 language tests; full suite 5615 pass | zero languages qualified; hosted fails closed until a complete approved record exists |
| 03D1 | feat/03d1-command-center-metrics | 89f6e66 | main | none | 46 new; 269 related pass | backend only, 8 GET routes |
| 03B | feat/03b-admin-plans | 72bb7fd | PREP-HEAD | none | 33 new; full suite 5589 pass | 9 routes; billing stays mock |
| 03C | feat/03c-admin-users | 5fd21d6 | PREP-HEAD | none | 18 new | 7 action routes; bulk actions not built (OD-BULK-ACTIONS) |
| 03E1 | feat/03e1-reports-builder | 0c3638b | PREP-HEAD | **0041_report_configurations** | 107 new | 20 routes; edited the privacy evaluator |
| 04E | feat/04e-invitation-only | 54c4bf0 | PREP-HEAD | **0041_registration_invitations** | 90 new; full suite 5646 pass | hosted invitation-required, fail-closed |
| 04A | feat/04a-story-bank | a7b0713 | PREP-HEAD | **0041_story_bank_completion** | 31 backend + 47 frontend new; full suite 5587 pass | one-line change in the evidence specialist under src/agent |
| 04B | feat/04b-workspaces | 0d3d9ed | PREP-HEAD | none | 52 backend + 34 frontend new; evaluator 29 gates | security fix: invitation acceptance needs a verified email |

Every full-suite run reported the same one failure not caused by the package: `test_knowledge_persistence_02a_identity::test_no_forbidden_files_were_touched...` (diffs against a stale branch ref; passes in CI where that ref is absent; a follow-up task is running separately). Some runs also hit a temp-directory or timing flake that passes alone, and the locale audit needs `node_modules` (CI installs it since PR #214).

**Not started:** 05B, 05C, 05E, 06C, 08A0 (local capacity: nine agents ran at once). 01D waits for 01A to integrate; 01C waits for 01D; 04C waits for 01A; 03D2 and 03E2 wait for 03D1 and 03E1 to merge; 04D waits for the hosted topology and OD-HOSTED for live drills. 02D, 02E, 06F need named external reviewers or datasets (section 6).

### Merge-train dry run (local, not CI)
Merging all twelve branches onto `main` in order, then recording which conflict against the cumulative tree:
- Clean: PREP-HEAD, 01A, 02B, 02C, 06H, 03D1, 03E1.
- Conflicts: 03B and 03C in `src/api/main.py` (router registration lines); 04E in `src/api/main.py`, `src/application/admin_audit.py`, `tests/_admin_matrix.py` and the generated `06A_LOCALE_AUDIT.md`; 04A and 04B in `06A_LOCALE_AUDIT.md`.
- These are routine registration and generated-file conflicts, not logic conflicts, but each branch needs a normal `merge main` fix after the previous one lands, as in wave 1.
- **Three branches claim migration 0041** (03E1, 04E, 04A): only one can; the others renumber to the next contiguous number and set `down_revision` at merge. The head-agnostic prep branch makes this a rename, not a test change.
- **Three branches edited `scripts/eval_privacy_controls.py` differently** (03E1 and 04E ignore foreign-key targets, 04A adds a reviewed-migration exception). They will conflict. Recommended resolution: keep 03E1's narrower foreign-key rule (only inside `ForeignKey`/`ForeignKeyConstraint`), drop 04E's broader one, keep 04A's file-name-and-table-bound exception after a human review of it.
- Recommended merge order: PREP-HEAD, then 01A, 02C, 06H, 02B, 03D1, 03E1 (0041), 04E (renumber to 0042), 04A (0043), 03B, 03C, 04B. After each merge the next branch gets a normal `merge main`.

## 4. Requirements accepted
None accepted by this dashboard yet: acceptance is recorded only after a PR merges on green CI and review. Delivered on branches, awaiting PR, CI and review: REQ-OWN-01 (backend), 02, 03, 04 (backend), 05 (K4, K6 code), 06, 07, REQ-BETA-01, REQ-LANG-11/13/14 enforcement, REVIEW-01 (R1 to R3, R6), REVIEW-04 (R1, R4, R5 code).

## 5. Critical-path forecast (recomputed from observed data, not from hope)
- Engineering authoring has been fast; engineering effort estimates are therefore likely conservative for contract and scaffold work. Using the model's sensitivity table (profile D ramp 12/18/24), full scope completes day 33 (Wed 9 Dec 2026) at 100% of estimate, day 26 (Mon 30 Nov) at 50%, day 23 (Thu 26 Nov) at 25% and day 21 (Tue 24 Nov) at 10%. Wave 2 authoring (12 packages in roughly 30 to 75 minutes each, run nine at a time) is consistent with wave 1; again no review, CI or merge time has been observed yet, so no estimate is changed.
- The binding constraint is human and legal lead time, which engineering cannot compress: assumed 20 working days for native review and legal translation qualification (06F), 15 for market source licensing (02D), 15 for privacy and legal readiness (05E), 10 for independent evaluation (06G). **For these to finish by Friday 27 November they must start by Monday 2 November.** They have not started because they need owner action (section 6). Each working day of delay moves the full-scope date by a working day. This is the single largest schedule risk.
- Planning date stays: early to mid December 2026. 30 November holds only if the human lead-time packages start by 2 November AND wave-2 engineering runs at the lower effort scales AND live staging (OD-HOSTED) is approved early enough for the 05B/05C/04D drills. Gate-driven: if any gate is unmet, the date moves and no feature is cut.

## 6. Human resource blockers and owner decisions required
| Item | Needed from | Blocks |
|---|---|---|
| Name the native reviewers for seven languages | Owner | 06F, LG-05/LG-11, every language qualification |
| Legal counsel for translated Terms, Privacy, AI transparency and the privacy/data-rights review | Owner | 06F LG-10, 05E |
| Licensing reviewer / source rights holders; EU geography eligibility | Owner | 02D, 02E coverage claims, source approval (none approved) |
| Independent evaluators for held-out data | Owner | 01A review, 02E, 06G |
| Security reviewer for 01A and 01D | Owner | security gate sign-off |
| OD-HOSTED (hosting authorisation) | Owner | any staging deployment, 05B/05C/04D live drills, 02A hosted persistence proof, real clamd |
| OD-BUDGET (paid calls) | Owner | production-embedder benchmark (02B/02E), live multilingual quality (06C), RAGAS live runs |
| OD-GATE-THRESHOLDS | Owner | any CI gate on injection detection/false-positive rates |
| OD-LANG-02 (market mappings), OD-LANG-03/04 (reviewers, legal translation) | Owner | LG-07, LG-10, LG-11 |
| Review capacity | Owner and reviewers | every PR; wave 1 shows fast turnaround when available |

## 7. Gate status changes
None. No gate moved to PASS. Changed state: gates move to IN PROGRESS only where wave-2 code exists and only as the tracker records. Preserved unchanged: coverage 386/412 against 392 (FAIL), AC-24 PARTIAL, RC-P10-003 artifacts, the capstone acceptance ledger.

## 8. Next packages ready to start
- Ready now, no blocker: 05B (backup, restore and rollback code with offline drills), 05C (observability and resilience), 05E (privacy, legal and data-rights engineering), 06C (AI-language qualification harness), 08A0 (release evidence pipeline).
- Ready after 01A merges: 01D (tool-call authorization), then 01C, then 04C.
- Ready after their backends merge: 03D2 (needs 03D1), 03E2 (needs 03E1).
- Prepare only, awaiting owner-named people or data: 02D, 02E, 06F.
- Lead action needed first: the owner opens the PRs (prep branch first); the lead then runs the merge train above.
