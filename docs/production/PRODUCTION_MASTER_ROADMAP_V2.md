# Production Master Roadmap V2.2

**Status:** PROPOSED baseline for owner review, 2026-10-21. **Production implementation does not begin until the owner has reviewed the reconciled baseline.** No feature was activated, no provider was called, nothing was deployed or merged by this work.

**Provenance and honesty notes.**
- The repository contained no earlier "Roadmap V2" or "V2.1" document; this file is the first version in the repository, so nothing here "updates" earlier text. The previously approved requirements the owner named (Admin, Story Bank, Workspaces, Reports, Knowledge sources, AI security) are carried as: (a) the 394 existing register issues, which already hold their evidence-backed parts, and (b) eight owner-named areas recorded as OWNER DECISION rows because their detailed text is not in the repository (OD-REQ-TEXT). No scope was invented for them.
- The "five capstone reviewer findings" were not supplied. Five engineering-observed findings from the live-demonstration work (RF-01..RF-05) are recorded in their place; the owner should confirm or replace them (OD-REVIEW-FINDINGS).
- Historical gates, results and statuses are preserved verbatim and are not upgraded: coverage 386/412 against 392 is FAIL, AC-24 is PARTIAL, human-qualified coverage is 0 of 412, and RC-P10-003 and the capstone ledger are untouched.

Companion documents (all in `docs/production/`): `RELEASE_SCOPE_V1.md`, `RELEASE_TRAIN_AND_DEPENDENCIES.md`, `PRODUCTION_ACCEPTANCE_MATRIX.md`, `OWNER_DECISION_REGISTER.md`, `MULTILINGUAL_RELEASE_QUALIFICATION.md`, `MASTER_REQUIREMENTS_TRACEABILITY.md`, `RELEASE_BLOCKER_DASHBOARD.md`, `PRODUCTION_ISSUE_RECONCILIATION.json` (machine-checked by `scripts/production/reconcile_issues.py check`).

## 1. Fixed owner decisions (language)

R1.0 on 30 November 2026 includes all seven existing candidate languages (English, German, Spanish, Italian, Portuguese, French, Dutch); it is not English-only. Proposed primary markets (English to Ireland, German to Germany, Spanish to Spain, Italian to Italy, Portuguese to Portugal, French to France, Dutch to Netherlands) are proposals until owner approval and source qualification, and the interface language never selects the labour-market country. Russian is excluded from R1.0 (code preserved, not an active beta locale). Mandarin, Hindi and Arabic belong to R1.3 and each needs new engineering and human qualification. Platform Admin stays English-only in R1.0. No language is called production-qualified before all of its gates pass.

## 2. Revised work packages

Counts are the reconciliation as generated 2026-10-21 (FIX / VERIFY before R1.0, OWNER DECISION, DEFER, CLOSED); the dashboard is authoritative.

| WP | Name | Owner role (person not yet named) | Fix | Verify | Owner | Defer | Closed |
|---|---|---|---|---|---|---|---|
| WP-01 | Governance, reviewers and owner decisions | Product Owner | 4 | 0 | 0 | 0 | 0 |
| WP-02 | Hosted deployment, operations and resilience | Platform and operations lead | 18 | 14 | 2 | 7 | 5 |
| WP-03 | Identity, email and access | Security lead | 1 | 3 | 1 | 2 | 0 |
| WP-04 | Privacy, data rights and legal | Privacy and legal lead | 8 | 9 | 14 | 0 | 2 |
| WP-05 | AI security and grounding policy | AI safety lead | 0 | 14 | 0 | 0 | 5 |
| WP-06 | Knowledge sources and retrieval (seven markets) | Knowledge and data lead | 16 | 7 | 16 | 37 | 10 |
| WP-07 | Candidate journeys, Mo and Practice quality | Product lead (candidate) | 0 | 4 | 3 | 5 | 3 |
| WP-08 | Multilingual programme (seven languages) | Localisation lead | 15 | 5 | 1 | 6 | 0 |
| WP-09 | Story Bank, Workspaces and shared reports | Product lead (collaboration) | 0 | 2 | 4 | 4 | 0 |
| WP-10 | Admin 2.0 (English-only): users, plans, reports, knowledge, navigation | Product lead (operations) | 0 | 1 | 7 | 19 | 9 |
| WP-11 | Commercial and billing (gated) | Commercial lead | 0 | 0 | 22 | 11 | 1 |
| WP-12 | Speech and realtime voice (gated) | Speech lead | 2 | 1 | 0 | 23 | 0 |
| WP-13 | External integrations | Integrations lead | 2 | 3 | 0 | 3 | 0 |
| WP-14 | Human validation and native review | Quality and human-review lead | 2 | 5 | 0 | 4 | 0 |
| WP-15 | Quality engineering, accessibility and technical debt | Engineering lead | 2 | 2 | 18 | 13 | 15 |
| WP-16 | Live evaluation and measurement | Evaluation lead | 0 | 4 | 3 | 12 | 2 |

WP-08 (multilingual) is split into WP-08A to WP-08I in `MULTILINGUAL_RELEASE_QUALIFICATION.md`. New language requirements are REQ-LANG-01..16.

## 3. Totals

394 historical issues (52 closed with evidence preserved, 342 active, 161 production blockers, 72 pending owner decisions) plus 39 new items (16 language, 8 owner-named areas, 5 demonstration findings, 10 cross-check items from the acceptance ledger, release matrix and P9 register) = 433 traced rows, **0 unmapped**. R1.0: 70 fix, 74 verify. Owner decisions: 91. Deferred: R1.1 94, R1.2 15, R1.3 2, R2.0 35. Duplicates reconciled by meaning in this pass: 6 (plus 18 alias merges recorded earlier); no ID was removed.

## 4. Critical path (updated)

See `RELEASE_TRAIN_AND_DEPENDENCIES.md` section 3. In short: owner decisions and naming of reviewers and qualifiers in the week of 21 October; audit, hiding Russian and environment stand-up from 26 October; per-language fixes and seven-market source qualification through mid-November; native-language review and legal translation qualification (long lead, human) 16 to 22 November; freeze and go/no-go 23 to 27 November; release 30 November for the languages whose gates passed. The human steps and the size of the fix/verify list put the date at risk (OD-SCOPE-01).

## 5. Rules carried forward (unchanged)

Platform Admin is not a candidate-data superuser. Unapproved knowledge never reaches candidate retrieval. Compensation V2, international sources, billing, Stripe, server speech, history/model-profile gating and the scheduler stay disabled; a deferral is valid only while its gate constants are False (checked). No safety, privacy or operational dependency is deferred while its feature is enabled (rule S1). The EUR 10 capstone demonstration budget is not reusable for production qualification; any live evaluation needs a new approved budget (OD-BUDGET). Never claim human validation, live validation or production qualification that has not happened.

## 6. What this wave did not do

No implementation; no code change to hide Russian or to add controls; no new Admin, Story Bank, Workspace or navigation work; no deployment; no provider call; no merge; no new evaluation. The disposition of every item is proposed by the rules in `MASTER_REQUIREMENTS_TRACEABILITY.md` and awaits owner review.
