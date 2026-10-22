# Release Readiness Tracker (R1.0)

**Status:** LIVE TRACKER, initialised 2026-10-21 at Phase 00. Definitions of each gate are in `../PRODUCTION_ACCEPTANCE_MATRIX.md` (not repeated here); package scope is in `IMPLEMENTATION_PACKAGE_REGISTER.md`. This file records only state, owner role, evidence link and next action, and is updated as each package merges. A gate is PASS only with evidence at a named SHA; no state below has been upgraded from the historical record, and none is a pass.

State vocabulary: NOT STARTED, IN PROGRESS, READY FOR REVIEW, PASS, FAIL, BLOCKED (with the blocking decision).

## 1. Production gates (state as of 2026-10-22, main @ e4aed13)

IN PROGRESS means engineering is merged but the gate's evidence is incomplete; it is never read as PASS. Only PG-11 is PASS.

| Gate | Name | Packages | Owner role (person not yet named) | State | Evidence | Blocked by / next action |
|---|---|---|---|---|---|---|
| PG-01 | Secure hosted deployment | 05A | Platform and operations lead | BLOCKED | Topology as code merged (PR #218); nothing deployed | OD-HOSTED |
| PG-02 | Identity and account lifecycle | 04E, 05D | Security lead | IN PROGRESS | 04E merged (PR #228): hosted invitation-required, fail-closed | 05D live round trips need OD-HOSTED; invitation email and issuer decisions open |
| PG-03 | Injection defence and tool safety | 01A, 01D, 06E, 07B | AI safety lead | IN PROGRESS | 01A merged (PR #223); held-out detection 77.3% (weakly contaminated), benign false positives 14.3% | No approved thresholds (OD-GATE-THRESHOLDS); independent held-out set; human security review; 01D, 06E, 07B outstanding |
| PG-04 | Privacy, legal and data rights | 05E, 06F, 04F | Privacy and legal lead | NOT STARTED | none | Counsel and legal qualifiers not named (OD-LANG-04) |
| PG-05 | Knowledge Sources and embedding/index integrity | 02K, 02A, 02B, 02C, 02D, 02E | Knowledge and data lead | IN PROGRESS | 02K, 02A, 02B, 02C merged (PRs #215, #221, #227, #226): offline proof only | Production embedder not chosen or benchmarked (OD-EMBED, OD-BUDGET); no real clamd run; 02D licensing and 02E coverage outstanding; OD-US-CONTENT |
| PG-06 | Candidate end-to-end reliability | 04C, 04D | Product lead (candidate) | NOT STARTED | none | Needs staging (OD-HOSTED); 04C follows 01D and 01C |
| PG-07 | Independent human AI evaluation | 06G | Quality and human-review lead | BLOCKED | none | No reviewers named (00A, OD-BUDGET) |
| PG-08 | Admin 2.0 functionality | 03A, 03B, 03C, 03D1, 03D2 | Product lead (operations) | IN PROGRESS | 03A, 03B, 03C, 03D1 merged (PRs #216, #230, #231, #224) | 03D2 views outstanding; OD-BULK-ACTIONS, OD-PLAN-LIMITS |
| PG-09 | Observability, resilience, backup, restore, rollback | 05B, 05C | Platform and operations lead | NOT STARTED | none | Wave 3a; live drills need OD-HOSTED; OD-BUDGET for the cap |
| PG-10 | Deferred and paid features disabled | 07A, 06A, 06H | Engineering lead | IN PROGRESS | 06A and 06H merged (PRs #214, #229): Russian excluded, hosted language fail-closed | 07A inaccessibility suite outstanding |
| PG-11 | Complete issue reconciliation | all | Product Owner | PASS (machine-checked) | `reconcile_issues.py check` (452 items, 0 unmapped); `tests/test_production_reconciliation.py` | Re-run on every change |
| PG-12 | Prompt versioning, provenance, registry parity | 01B0, 01B, 01D, 01C | AI platform lead | IN PROGRESS | 01B0 and 01B merged (PRs #217, #220): 44 prompt assets, byte-identity tests | 01D and 01C outstanding |
| PG-13 | Story Bank and Workspaces | 04A, 04B, 06B | Product lead (collaboration) | IN PROGRESS | 04A and 04B merged (PRs #234, #233) | 06B per-language journeys; OD-WS-TRANSFER |
| PG-14 | Reports and safe analytics | 03K, 03D1, 03E1, 03E2 | Product lead (operations) | IN PROGRESS | 03K, 03D1, 03E1 merged (PRs #219, #224, #232) | 03E2 views outstanding; OD-REPORT-EXPORT |
| PG-15 | Free beta operational acceptance | 08A0, 08A | Product Owner | NOT STARTED | none | All of the above |

## 2. Per-language gates (LG-01 to LG-14 for each language)

No language is production-qualified and none can be offered to real users in staging or production: 06H (merged, PR #229) fails closed until a language has a complete approved record. Engineering evidence exists for LG-01 (locale audit: 2,611 keys per language on main, none missing or blank) and LG-14 (boundaries), but no gate has been approved by a named human, so the approved count is 0 of 14 for every language. All other gates are NOT RUN, NOT STARTED or ENGINEERING DRAFT.

| Language | Proposed market (not approved) | Gates approved | Activation | Blocker |
|---|---|---|---|---|
| English | Ireland | 0 of 14 | NOT ACTIVE in hosted environments | Source qualification for the market (OD-LANG-02); US-centred content (OD-US-CONTENT) |
| German | Germany | 0 of 14 | NOT ACTIVE | Native and legal review; market approval |
| Spanish | Spain | 0 of 14 | NOT ACTIVE | Same |
| Italian | Italy | 0 of 14 | NOT ACTIVE | Same |
| Portuguese | Portugal | 0 of 14 | NOT ACTIVE | Same |
| French | France | 0 of 14 | NOT ACTIVE | Same |
| Dutch | Netherlands | 0 of 14 | NOT ACTIVE | Same |
| Russian | none | not applicable | EXCLUDED from R1.0 (removed from active selection, merged in PR #214) | none for R1.0 |

## 3. Reviewer findings and owner requirements

| Item | Package | State |
|---|---|---|
| REVIEW-01 Injection defence depth | 01A (merged), 01D | R1 to R3, R6 engineering merged; R4, R5 (01D) not started; no approved thresholds, no human security review |
| REVIEW-02 Versioned prompts | 01B0, 01B (merged) | Engineering merged (R1 to R7); R8 rollback is a reviewed pointer edit only, no Admin control |
| REVIEW-03 Tool catalogue parity | 01C | NOT STARTED (after 01D) |
| REVIEW-04 Embedding degradation | 02B (merged) | Fail-closed enforcement and manifests merged; production-embedder benchmark NOT RUN |
| REVIEW-05 Streaming and cancellation | 04C | NOT STARTED (after 01D and 01C) |
| REQ-OWN-01 Command Center and AI operations | 03K, 03D1 (merged), 03D2 | Backend merged; views not started |
| REQ-OWN-02 Plans | 03B (merged) | Engineering merged; limit values open (OD-PLAN-LIMITS) |
| REQ-OWN-03 Users | 03C (merged) | Engineering merged; bulk actions not built (OD-BULK-ACTIONS) |
| REQ-OWN-04 Reports and builder | 03K, 03E1 (merged), 03E2 | Backend merged (CSV, JSON); views not started; OD-REPORT-EXPORT |
| REQ-OWN-05 Knowledge Sources | 02A, 02B, 02C (merged) | Offline proof only; hosted proof, real clamd and drills not run |
| REQ-OWN-06 Story Bank | 04A (merged) | Engineering merged; Prepare per-story consent not built; native review pending |
| REQ-OWN-07 Workspaces | 04B (merged) | Engineering merged; OD-WS-TRANSFER open; PostgreSQL race untested |
| REQ-OWN-08 Admin navigation | 03A (merged) | Engineering merged |
| REQ-BETA-01 Invitation-only registration | 04E (merged) | Engineering merged; no invitation email; first-admin bootstrap via CLI |

## 4. Phase 00 exit-gate evidence

| Gate | State | Evidence needed to close | Where it will be recorded |
|---|---|---|---|
| E8 documentation, reconciliation and static checks pass and CI is green on PR #212 | PASS at 4ad22be; the closeout head's checks are shown on the PR | Green GitHub CI on the corrected head SHA (all required jobs: four shards, evaluators and guards, evaluation extras, static guards, frontend, Playwright, Streamlit smoke, legacy live component, aggregate check); `reconcile_issues.py check`, `execution_packages.py check`, the reconciliation, package, scope-exclusion and cookie-precedence tests, `ruff`, shard plan verification | PR #212 checks; exit report section 8 |
| E10 owner approval to start Phase 01 | GRANTED (owner message 2026-10-21), effective on the owner's merge of PR #212 | Written owner approval (recorded in the decision register): S1 full scope selected; resourcing direction; direction approvals; reclassification not applied | Owner decision register; this tracker |

## 5. Early parallel workstream (deployment topology and Knowledge persistence)

02A, 05A and 05E start in the first implementation wave with the highest staffing priority. **The existing `deploy/docker-compose.staging.yml` must not be deployed** until the first 05A PR adds the worker, knowledge and index volumes and ClamAV and OD-HOSTED is answered. State: NOT STARTED, BLOCKED on OD-HOSTED for deployment (the topology fix as code is not blocked).

## 6. Historical gates preserved

The historical 95% coverage gate (386 of 412 against 392) remains FAIL; AC-24 remains PARTIAL; human-qualified coverage remains 0 of 412. A separate frozen beta-scope coverage measure (02E, OD-COVERAGE) is reported beside, never instead of, these.

## 7. First-wave integration status (2026-10-21)

Branches exist for 02K, 01B0, 03K, 05A, 01A, 03A, 06A and 01B; 02A is in progress. No pull request has been opened, so no GitHub CI result exists and no gate is PASS on this wave's evidence. See `FIRST_WAVE_INTEGRATION_DASHBOARD.md` for SHAs, merge order, the conflict dry-run (none) and blockers. Language activation enforcement (LG-01..LG-14, fail closed) is tracked as package 06H. No language is production-qualified.

## 8. Wave 2 integration update (2026-10-22)

Main is `f9a06a9`. PRs #213 to #221 are merged: 02K, 01B0, 03K, 01B, 05A, 02A, 03A and 06A, each after green GitHub CI. **Merged code is not a passed gate.** Gate states are unchanged: PG-01 stays BLOCKED (topology code merged, nothing deployed, OD-HOSTED unanswered); PG-10 stays IN PROGRESS (Russian removed from active selection, UI plus API inaccessibility suite still to be written); no language is production-qualified (06A: LG-01 and LG-14 have evidence, every other gate for every language is NOT RUN, NOT STARTED or ENGINEERING DRAFT; 06H enforcement is in progress); governed Knowledge persistence is proven offline only (02A), not on hosted volumes; the injection corpus (01A) is not merged and its held-out detection is 54.5%, so the prompt-injection gate is not met. Outstanding operational and human evidence: live staging deployment and drills, a real ClamAV in staging, a production embedder run (OD-BUDGET), native and legal language reviews, source licences and EU eligibility, independent evaluation, security review. See `WAVE2_EXECUTION_DASHBOARD.md`.

## 9. Wave 2 final state and the five-layer view (2026-10-22)

Wave 2 is merged: PRs #222 to #234, main @ `e4aed13`, one Alembic head (`0043_story_bank_completion`). The tracker above and `WAVE3_EXECUTION_PLAN.md` (section 3) record each package's engineering, CI, live-staging, human-qualification and gate-acceptance state separately. The earlier sections 7 and 8 are kept as the historical record of Waves 1 and 2 and are superseded by sections 1 to 3 above.
