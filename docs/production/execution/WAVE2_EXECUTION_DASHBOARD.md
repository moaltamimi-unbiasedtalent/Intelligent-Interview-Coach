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

## 3. Wave 2 packages started (agents run in isolated worktrees; they push branches, the owner opens PRs; none is merged)
| Package | Branch | State | Depends on (merged) | Notes |
|---|---|---|---|---|
| PREP-HEAD | chore/migration-head-agnostic | started | none | converts ~40 head-literal checks to version-independent invariants, with negative tests; no real migration |
| 01A | feat/01a-injection-corpus (head 6b2dbc2 before update) | started | none | merge main into the branch; documented investigation of 54.5% held-out detection and 19.7% benign false positives; held-out frozen, never tuned against, measured once, no thresholds |
| 02B | feat/02b-embedding-integrity | started | 02K, 02A | fail-closed embedder and manifest enforcement; offline seven-language benchmark only; paid run needs OD-BUDGET |
| 02C | feat/02c-clamav-scanning | started | 02K, 05A | real clamd INSTREAM client, fail-closed, fake clamd server in tests |
| 06H | feat/06h-language-activation | started | 06A | LG-01..LG-14 fail-closed enforcement; synthetic fixtures only; zero real language qualified |
| 03D1 | feat/03d1-command-center-metrics | started | 03K, 03A | Command Center read model, backend only |

**Queued next (waiting for the prep branch, because they may need a migration, and for local capacity):** 03B, 03C, 03E1, 04A, 04B, 04E. Then 05B, 05C, 05E, 06C, 08A0. 01D starts only after 01A is integrated and 01C after 01D (shared order 01B, 01D, 01C; 01B is merged). 02D, 02E and 06F need named external reviewers or datasets (section 6) and are prepared, not started. 04C needs 01A merged; 04D needs the hosted topology (05A merged, live staging blocked on OD-HOSTED). 03D2 and 03E2 wait for the 03D1 and 03E1 contracts to merge.

Migration discipline: current head `0040_knowledge_alert_categories`. A package may add a revision only if it truly needs one; the lead re-chains in merge order so there is never a second head. Reserved order when needed: 04E 0041, 03E1 0042, 04A 0043, 04B 0044, 03C 0045, 03B 0046.

## 4. Requirements accepted
None newly accepted in this wave yet. Accepted from wave 1 means code merged with green CI, not gate PASS: see the tracker. This dashboard records an acceptance only after the PR merges with evidence.

## 5. Critical-path forecast (recomputed from observed data, not from hope)
- Engineering authoring has been fast; engineering effort estimates are therefore likely conservative for contract and scaffold work. Using the model's sensitivity table (profile D ramp 12/18/24), full scope completes day 33 (Wed 9 Dec 2026) at 100% of estimate, day 26 (Mon 30 Nov) at 50%, day 23 (Thu 26 Nov) at 25% and day 21 (Tue 24 Nov) at 10%. Wave 1 supports the lower scales only for packages of its kind.
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
Immediately (no blocker): 03B, 03C, 03E1, 04A, 04B, 04E, 05E (legal/privacy engineering part), 05C, 06C, 08A0, and 05B (backup and restore code and offline drills; live drills wait for OD-HOSTED). After 01A integrates: 01D, then 01C, then 04C.
