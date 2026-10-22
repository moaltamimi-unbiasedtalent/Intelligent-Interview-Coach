# Release Readiness Tracker (R1.0)

**Status:** LIVE TRACKER, initialised 2026-10-21 at Phase 00. Definitions of each gate are in `../PRODUCTION_ACCEPTANCE_MATRIX.md` (not repeated here); package scope is in `IMPLEMENTATION_PACKAGE_REGISTER.md`. This file records only state, owner role, evidence link and next action, and is updated as each package merges. A gate is PASS only with evidence at a named SHA; no state below has been upgraded from the historical record, and none is a pass.

State vocabulary: NOT STARTED, IN PROGRESS, READY FOR REVIEW, PASS, FAIL, BLOCKED (with the blocking decision).

## 1. Production gates

| Gate | Name | Packages | Owner role (person not yet named) | State | Evidence | Blocked by / next action |
|---|---|---|---|---|---|---|
| PG-01 | Secure hosted deployment | 05A | Platform and operations lead | BLOCKED | none | OD-HOSTED; topology as code delivered on branch feat/05a-staging-topology @ 0a7d6fb (no PR, no CI, not deployed) |
| PG-02 | Identity and account lifecycle | 04E, 05D | Security lead | NOT STARTED | none | OD-INVITE; live email and OIDC need the hosted environment |
| PG-03 | Injection defence and tool safety | 01A, 06E, 07B | AI safety lead | NOT STARTED | none | OD-GATE-THRESHOLDS; start corpus build (01A) |
| PG-04 | Privacy, legal and data rights | 05E, 06F | Privacy and legal lead | NOT STARTED | none | Name legal qualifiers (OD-LANG-04); counsel engagement |
| PG-05 | Knowledge Sources and embedding/index integrity | 02K, 02A, 02B, 02C, 02D, 02E | Knowledge and data lead | NOT STARTED | none | OD-EMBED, OD-MALWARE, OD-LANG-02, OD-US-CONTENT |
| PG-06 | Candidate end-to-end reliability | 04C, 04D | Product lead (candidate) | NOT STARTED | none | Needs staging (05A) |
| PG-07 | Independent human AI evaluation | 06G | Quality and human-review lead | BLOCKED | none | No reviewers named (00A) |
| PG-08 | Admin 2.0 functionality | 03A, 03B, 03C, 03D1, 03D2 | Product lead (operations) | NOT STARTED | none | OD-ADMIN-NAV, OD-PLAN-ENFORCE, OD-BULK-ACTIONS |
| PG-09 | Observability, resilience, backup, restore, rollback | 05B, 05C | Platform and operations lead | NOT STARTED | none | Needs staging (05A) |
| PG-10 | Deferred and paid features disabled | 07A, 06A | Engineering lead | IN PROGRESS | Gate constants checked False by `reconcile_issues.py check` | UI plus API inaccessibility suite not written; Russian exclusion delivered on branch feat/06a-locale-boundaries (no PR, no CI, corrections pending) |
| PG-11 | Complete issue reconciliation | all | Product Owner | PASS (machine-checked) | `reconcile_issues.py check`; `tests/test_production_reconciliation.py` | Re-run on every change |
| PG-12 | Prompt versioning, provenance, registry parity | 01B0, 01B, 01D, 01C | AI platform lead | NOT STARTED | none | Phase 01 approval |
| PG-13 | Story Bank and Workspaces | 04A, 04B, 06B | Product lead (collaboration) | NOT STARTED | none | OD-WS-TRANSFER |
| PG-14 | Reports and safe analytics | 03K, 03D1, 03E1, 03E2 | Product lead (operations) | NOT STARTED | none | OD-REPORT-EXPORT |
| PG-15 | Free beta operational acceptance | 08A0, 08A | Product Owner | NOT STARTED | none | All of the above |

## 2. Per-language gates (LG-01 to LG-14 for each language)

All 98 language-gate cells are NOT STARTED or NOT RUN; none has passed. Per-language rows are kept separately so one language failing never hides another's evidence. The table is updated per language as evidence arrives.

| Language | Proposed market (not approved) | Gates passed | Activation | Blocker |
|---|---|---|---|---|
| English | Ireland | 0 of 14 | NOT ACTIVE | Source qualification for the market (OD-LANG-02); US-centred content (OD-US-CONTENT) |
| German | Germany | 0 of 14 | NOT ACTIVE | Native and legal review; market approval |
| Spanish | Spain | 0 of 14 | NOT ACTIVE | Same |
| Italian | Italy | 0 of 14 | NOT ACTIVE | Same |
| Portuguese | Portugal | 0 of 14 | NOT ACTIVE | Same |
| French | France | 0 of 14 | NOT ACTIVE | Same |
| Dutch | Netherlands | 0 of 14 | NOT ACTIVE | Same |
| Russian | none | not applicable | EXCLUDED from R1.0 | Still selectable on main; removed from active selection on branch feat/06a-locale-boundaries pending PR, CI and review |

## 3. Reviewer findings and owner requirements

| Item | Package | State |
|---|---|---|
| REVIEW-01 Injection defence depth | 01A | NOT STARTED |
| REVIEW-02 Versioned prompts | 01B | NOT STARTED |
| REVIEW-03 Tool catalogue parity | 01C | NOT STARTED |
| REVIEW-04 Embedding degradation | 02B | NOT STARTED |
| REVIEW-05 Streaming and cancellation | 04C | NOT STARTED |
| REQ-OWN-01 Command Center and AI operations | 03D1 and 03D2 (contract 03K) | NOT STARTED (foundations exist) |
| REQ-OWN-02 Plans | 03B | NOT STARTED (foundations exist) |
| REQ-OWN-03 Users | 03C | NOT STARTED (foundations exist) |
| REQ-OWN-04 Reports and builder | 03E1 and 03E2 (contract 03K) | NOT STARTED (foundations exist) |
| REQ-OWN-05 Knowledge Sources | 02A and 02C | NOT STARTED (foundations exist; staging topology gap found) |
| REQ-OWN-06 Story Bank | 04A | NOT STARTED (foundations exist) |
| REQ-OWN-07 Workspaces | 04B | NOT STARTED (backend exists) |
| REQ-OWN-08 Admin navigation | 03A | NOT STARTED |

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
