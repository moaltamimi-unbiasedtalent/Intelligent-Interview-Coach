# Whole-Project Status Dashboard

Updated 2026-10-22 after Wave 3a and the first Wave 3b packages were built (the milestone of record: 21 Wave 3 branches pushed, none yet merged). Source of truth is the repository and GitHub, never an assumption. A package is complete only when its code is on `main`; a gate is PASS only with an evidence artefact; **engineering completion is not production readiness**. This dashboard is refreshed after each wave and major integration milestone.

## 1. Current wave and roadmap phase
- Roadmap: Production Roadmap V2.2, strategy S1 (full R1.0 scope, owner-approved). Phase 00 is closed; engineering Waves 1 and 2 are merged; **Wave 3a is built** (08A0, 05B, 05C, 05E, 06C, 01D, 03D2, 03E2) together with most of Wave 3b (02E, 04D, 04F, 05D, 06B, 06D, 06E, 07A) and the OpenRouter embedding adapter: **21 branches pushed, none merged, none with a PR**, because the lead cannot open pull requests and the owner has not yet opened them (`WAVE3_PR_QUEUE.md`). Building now: 03C bulk actions, 04B ownership transfer, 02D approval filter and licensing pack, 06F and 06G review packages. Waiting for 01D to merge: 01C, 04C, 07B.
- `main` @ `f5cf7cb` (merge of PR #235). Alembic head `0043_story_bank_completion`. Branches already claim 0044 (05C budget ledger, 05D delivery events, 04B transfers) and 0045 (05C alerts); the lead renumbers at merge so the chain stays linear.

## 2. All 45 packages: five separate layers
Engineering = code merged on `main` (with the PR number and merge SHA); CI = GitHub checks; live staging = nothing is deployed, so every live cell is NOT RUN; human qualification = people and owner decisions; gate acceptance = the production or language gate. (Generated from `scripts/production/execution_packages.py` and `scripts/production/wave_matrix.py`; a test fails if it goes stale.)

<!-- MATRIX:START -->
| Package | 1 Engineering | 2 CI | 3 Live staging | 4 Human qualification | 5 Production-gate acceptance |
|---|---|---|---|---|---|
| 00A | PARTIAL: Phase 00 sign-off recorded (PRs #211, #212, #213) | documentation PRs #211 to #213 merged, CI green | n/a | Owner names reviewers, counsel and legal qualifiers (OPEN) | PG-07 BLOCKED until reviewers are named |
| 00B | DELIVERED as a proposal (PRs #211, #212) | documentation PRs #211 to #213 merged, CI green | n/a | Owner disposition of the ten reclassifications (OPEN) | PG-11 PASS (machine-checked); no reclassification applied |
| 01A | MERGED (PR #223, merge 7549973) | PR CI green (12 of 12); re-read on main | NOT RUN (injection screen on hosted stack) | Human security review (9 questions); independent held-out author (OPEN) | PG-03 IN PROGRESS; thresholds unapproved (OD-GATE-THRESHOLDS) |
| 01D | BRANCH PUSHED, NO PR | no PR yet | n/a | Security review of tool authorization | PG-03 (REVIEW-01 R4/R5) |
| 01B0 | MERGED (PR #217, merge 0d75acd) | PR CI green (12 of 12); re-read on main | n/a | none | PG-12 IN PROGRESS |
| 01B | MERGED (PR #220, merge 335d303) | PR CI green (12 of 12); re-read on main | NOT RUN (Docker image with prompts/ not built) | none | PG-12 IN PROGRESS (01D, 01C outstanding) |
| 01C | NOT STARTED | no PR yet | n/a | none | PG-12 (REVIEW-03) |
| 02K | MERGED (PR #215, merge 657e456) | PR CI green (12 of 12); re-read on main | n/a | none | PG-05 IN PROGRESS (contract) |
| 02A | MERGED (PR #221, merge 191cbc5) | PR CI green (12 of 12); re-read on main | NOT RUN (hosted volumes, PostgreSQL, multi-worker; OD-HOSTED) | none | PG-05 IN PROGRESS |
| 02B | MERGED (PR #227, merge 6acdbc1) | PR CI green (12 of 12); re-read on main | NOT RUN (production embedder, hosted refusal; OD-HOSTED, OD-EMBED) | Embedder choice and benchmark approval (OD-EMBED, OD-BUDGET) | PG-05 NOT MET (retrieval quality unmeasured) |
| 02C | MERGED (PR #226, merge 568b8f3) | PR CI green (12 of 12); re-read on main | NOT RUN (real clamd, EICAR, outage drill; OD-HOSTED) | none | PG-05 IN PROGRESS |
| 02D | NOT STARTED | no PR yet | n/a | Licensing reviewer and owner; per-market signed approval (OPEN, long lead) | PG-05 (licence and market qualification) |
| 02E | BRANCH PUSHED, NO PR | no PR yet | NOT RUN | Frozen coverage measure approval (OD-COVERAGE); independent datasets | PG-05 (retrieval quality, coverage) |
| 03A | MERGED (PR #216, merge f921892) | PR CI green (12 of 12); re-read on main | NOT RUN (live Admin walkthrough) | none | PG-08 IN PROGRESS |
| 03B | MERGED (PR #230, merge a4f540d) | PR CI green (12 of 12); re-read on main | NOT RUN (live Admin walkthrough) | Plan limit values (OD-PLAN-LIMITS) | PG-08 IN PROGRESS |
| 03C | MERGED (PR #231, merge 6bcfbf5) | PR CI green (12 of 12); re-read on main | NOT RUN (live Admin walkthrough) | Bulk-action policy (OD-BULK-ACTIONS) | PG-08 IN PROGRESS |
| 03K | MERGED (PR #219, merge 20241f4) | PR CI green (12 of 12); re-read on main | n/a | none | PG-14 IN PROGRESS (contract) |
| 03D1 | MERGED (PR #224, merge ac029ad) | PR CI green (12 of 12); re-read on main | NOT RUN (live data) | none | PG-08 IN PROGRESS (03D2 outstanding) |
| 03D2 | BRANCH PUSHED, NO PR | no PR yet | NOT RUN | none | PG-08 |
| 03E1 | MERGED (PR #232, merge 0d84e7e) | PR CI green (12 of 12); re-read on main | NOT RUN (live data) | Export formats (OD-REPORT-EXPORT) | PG-14 IN PROGRESS (03E2 outstanding) |
| 03E2 | BRANCH PUSHED (2 PRs), NO PR | no PR yet | NOT RUN | Export formats (OD-REPORT-EXPORT) | PG-14 |
| 04A | MERGED (PR #234, merge 4d7e57a) | PR CI green (12 of 12); re-read on main | NOT RUN (restart on staging) | Native review of 116 strings (LG-10/11) | PG-13 IN PROGRESS (06B outstanding) |
| 04B | MERGED (PR #233, merge e4aed13) | PR CI green (12 of 12); re-read on main | NOT RUN (PostgreSQL invitation race and row locks) | Transfer rules (OD-WS-TRANSFER); native review | PG-13 IN PROGRESS (06B outstanding) |
| 04C | NOT STARTED | no PR yet | NOT RUN (streaming on staging) | none | PG-06 |
| 04D | BRANCH PUSHED (2 PRs), NO PR | no PR yet | NOT RUN (journeys on a staging stack) | none | PG-06 |
| 04E | MERGED (PR #228, merge a763fdf) | PR CI green (12 of 12); re-read on main | NOT RUN (first-admin bootstrap, live Google) | Invitation email and issuer decisions (OPEN) | PG-02 IN PROGRESS (05D outstanding) |
| 04F | BRANCH PUSHED, NO PR | no PR yet | NOT RUN (browser dictation check) | Legal reviewer and test participants | PG-04 |
| 05A | MERGED (PR #218, merge 9b6b109) | PR CI green (12 of 12); re-read on main | NOT RUN (nothing deployed; OD-HOSTED) | Hosting authorisation (OPEN) | PG-01 BLOCKED |
| 05B | BRANCH PUSHED, NO PR | no PR yet | NOT RUN (restore drill, PostgreSQL paths; OD-HOSTED) | none | PG-09 |
| 05C | BRANCH PUSHED (2 PRs), NO PR | no PR yet | NOT RUN (synthetic outage on staging; OD-HOSTED) | AI budget (OD-BUDGET) | PG-09 |
| 05D | BRANCH PUSHED, NO PR | no PR yet | NOT RUN (live Brevo, Google, Redis; OD-HOSTED) | none | PG-02 |
| 05E | BRANCH PUSHED (2 PRs), NO PR | no PR yet | n/a | Legal counsel sign-off per offered language (long lead) | PG-04 |
| 06A | MERGED (PR #214, merge f9a06a9) | PR CI green (12 of 12); re-read on main | n/a | Native review of the audit baseline | PG-10 IN PROGRESS; LG-01 and LG-14 evidence exists, none approved by a named human |
| 06B | BRANCH PUSHED, NO PR | no PR yet | NOT RUN (journeys per language) | Native-speaker review | LG-03, LG-09 per language; PG-13 |
| 06C | BRANCH PUSHED, NO PR | no PR yet | NOT RUN (live Mo quality) | Blinded native-reader rating (OD-BUDGET) | LG-04, LG-05 per language |
| 06D | BRANCH PUSHED, NO PR | no PR yet | NOT RUN (production embedder; OD-EMBED) | Sample review | LG-06 per language |
| 06E | BRANCH PUSHED, NO PR | no PR yet | NOT RUN | none | LG-08 per language; PG-03 |
| 06F | NOT STARTED | no PR yet | n/a | Seven native reviewers and legal qualifiers (calendar-bound, OPEN) | LG-10, LG-11 per language; PG-04 |
| 06G | NOT STARTED | no PR yet | NOT RUN (live Mo outputs) | Independent reviewers and participants (OD-BUDGET, OD-GATE-THRESHOLDS) | PG-07 BLOCKED |
| 06H | MERGED (PR #229, merge 5d588a1) | PR CI green (12 of 12); re-read on main | NOT RUN (hosted fail-closed behaviour) | Approvers named for each gate (OD-LANG-03/04) | PG-10 IN PROGRESS; LG-13/LG-14 enforcement merged, zero languages qualified |
| 07A | BRANCH PUSHED, NO PR | no PR yet | n/a | none | PG-10 |
| 07B | NOT STARTED | no PR yet | NOT RUN (live grounding; OD-BUDGET) | none | PG-03 |
| 07C | NOT STARTED | no PR yet | NOT RUN (live OCR sample; OD-BUDGET) | none | residual live verification |
| 08A0 | BRANCH PUSHED, NO PR | no PR yet | n/a | none | PG-15 (evidence pipeline) |
| 08A | NOT STARTED | no PR yet | NOT RUN | Owner go/no-go | PG-15 |
<!-- MATRIX:END -->

## 3. GitHub status
Merged and green: #213 to #235 (Waves 1 and 2, the Wave 3 plan). Open: none. Twenty-one Wave 3 branches are pushed and listed with heads, bases, migration claims and the recommended merge order in `WAVE3_PR_QUEUE.md`; the lead records each PR number, CI result and merge status after the owner opens it. The lead cannot open pull requests (no GitHub CLI or token in this environment and no connected signed-in browser): the owner opens each from its compare URL and PRs merge only after green CI, a mergeable state and review.

## 4. Engineering completion versus production readiness
- Engineering: 19 of 45 packages merged for their offline scope (42%). Built on branches but NOT merged: 16 packages (08A0, 05B, 05C, 05E, 06C, 01D, 03D2, 03E2, 02E, 04D, 04F, 05D, 06B, 06D, 06E, 07A) plus the OpenRouter embedding adapter, which completes part of 02B; in progress: 02D, 03C completion, 04B completion, 06F, 06G. Not started: 01C, 04C, 07B (blocked on 01D), 07C and 08A (live and freeze steps). Merged code and built branches are both engineering status only.
- Production readiness: **no gate is PASS except PG-11**. PG-01 and PG-07 are BLOCKED; PG-02, PG-03, PG-05, PG-08, PG-10, PG-12, PG-13, PG-14 are IN PROGRESS; PG-04, PG-06, PG-09, PG-15 are NOT STARTED. No language is production-qualified; nothing is deployed; no live verification has run; no human reviewer has signed anything.

## 5. Actual milestones versus the planning model
The model (profile D ramp 12/18/24, 100% of the high effort estimate) planned the first-wave packages to finish between Fri 30 Oct and Thu 5 Nov 2026 and the full scope on Wed 9 Dec. Actually, the 19 merged packages landed on 21 and 22 October, between 8 and 42 calendar days ahead of the model date for each package. That confirms engineering estimates are conservative for contracts, backends and scaffolds. It says nothing about the calendar-bound steps (human review, counsel, licensing, live staging), which have not started.

| Milestone | Planned | Actual |
|---|---|---|
| Phase 00 closed, S1 approved | before the first wave | 2026-10-21 (PRs #211 to #213) |
| First-wave packages (05A, 01A, 02K, 01B0, 03K, 03A, 06A, 01B, 02A) | finish 30 Oct to 10 Nov | merged 21 Oct (01A 22 Oct) |
| Wave 2 packages (02B, 02C, 03B, 03C, 03D1, 03E1, 04A, 04B, 04E, 06H) | finish 13 Nov to 3 Dec | merged 22 Oct |
| Wave 3a launch | not separately planned | 2026-10-22 (owner authorisation) |
| Freeze (08A) | gated by human lead times | not started |

## 6. Outstanding dependencies and owner decisions
Open and provisional decisions with their recommended defaults are in `../OWNER_DECISION_REGISTER.md` (section "Owner direction 2026-10-22"): OD-RESOURCE, OD-EMBED, OD-HOSTED, OD-BUDGET, OD-COVERAGE, OD-BULK-ACTIONS, OD-PLAN-LIMITS, OD-WS-TRANSFER, OD-REPORT-EXPORT are recorded as PROVISIONAL recommendations, not approvals. Still genuinely the owner's: appointing the native-language, legal, security and independent AI reviewers (when qualification starts), the OpenRouter spending ceilings, hosting authorisation, production deployment and the go/no-go.

## 7. Security, privacy and language qualification
- Security: injection corpus merged (held-out detection 77.3%, weakly contaminated, no approved thresholds, no human review); tool-call authorization (01D) in progress; no independent security review yet.
- Privacy: deletion, export and consent controls exist; 05E safeguards in progress; no counsel sign-off.
- Language: 0 of 7 languages qualified (0 of 14 gates approved each). Hosted environments fail closed until a complete, approved record exists (06H). Engineering evidence exists for LG-01 and LG-14 only.

## 8. Critical path and forecast
The model's critical path is native and legal review (assumed 20 working days) then the freeze (3 working days); reviewers must be engaged by Tue 27 Oct for a freeze by Fri 27 Nov, otherwise the date moves one working day per day of delay (Thu 3 Dec for Mon 2 Nov). The owner has stated reviewers will be appointed "when we reach the qualification stage": that is a scheduling risk to 30 November and is reported, not hidden. 30 November remains the **engineering delivery** target; the real-user beta launch is conditional on the gates in section 4 and on the owner's go/no-go. Evidence-backed revised forecast for the full gated release if reviewers are engaged on a given Monday: 2 Nov gives about 3 Dec, 9 Nov about 10 Dec, 16 Nov about 17 Dec (planning model, assumed floors).

## 9. Next packages, owners and immediate actions
- **Owner actions (the critical dependency now):** open the 21 PRs from `WAVE3_PR_QUEUE.md` in the recommended order (01D first among the code PRs; 05C before the governed benchmark); supply the OpenRouter budget configuration (ceilings, price table, approval marker); decide the items listed in the decision register; appoint reviewers when qualification starts (the schedule risk in section 8 stands).
- **Lead actions:** verify CI and mergeability per PR, re-merge `main` into each next branch, renumber migrations (0044, 0045, then 0046 and later), regenerate the locale audit and the legal pack where required, then start 01C, 04C and 07B as soon as 01D merges and the governed OpenRouter embedding benchmark as soon as 05C and the adapter merge and a ceiling is configured.
- **In progress now:** 03C bulk actions, 04B ownership transfer, 02D approval filter and licensing review pack, 06F and 06G review packages.
