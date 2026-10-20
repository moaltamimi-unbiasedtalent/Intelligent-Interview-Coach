# Production Master Roadmap V2.2 (corrected)

**Status:** corrected 2026-10-21 against the owner's authoritative requirements, which were recovered from a separate owner conversation and recorded in [`OWNER_REQUIREMENTS_SOURCE_OF_TRUTH_V2_2.md`](OWNER_REQUIREMENTS_SOURCE_OF_TRUTH_V2_2.md). This supersedes the first version of this roadmap (PR #211 at `4084eb9`), which had substituted engineering-observed findings for the reviewer findings and left the owner-requested capabilities as placeholder decisions. Dispositions are PROPOSED for owner review; no owner approval was invented. **Planning only: no production code, database change, paid call, Stripe activation, deployment, feature activation or rewriting of historical results.**

Provenance is kept distinct throughout: explicit owner decisions, owner-requested capabilities, actual Turing College review findings, proposed engineering implementations, and decisions still awaiting the owner.

Companion documents: `RELEASE_SCOPE_V1.md`, `RELEASE_TRAIN_AND_DEPENDENCIES.md`, `PRODUCTION_ACCEPTANCE_MATRIX.md`, `OWNER_DECISION_REGISTER.md`, `MULTILINGUAL_RELEASE_QUALIFICATION.md`, `MASTER_REQUIREMENTS_TRACEABILITY.md`, `RELEASE_BLOCKER_DASHBOARD.md`, `PRODUCTION_ISSUE_RECONCILIATION.json` (machine-checked by `scripts/production/reconcile_issues.py check`).

## 1. What R1.0 is

R1.0 on **30 November 2026** is a **free, invitation-only private production beta** with no live customer payments. The date is the owner's target; release safety and legal gates are not waived to meet it. Seven languages (English, German, Spanish, Italian, Portuguese, French, Dutch) are targeted, each subject to individual qualification (LG-01 to LG-14); a language that fails a mandatory gate is not activated for real users. Russian is excluded and removed from active Candidate language selection. Selected EU markets are proposed, not individually approved. Admin is English-only and owner-operated, with RBAC, specialist permissions, approvals and audit preserved. Basic and Premium may both be free beta access tiers.

R1.0 delivers: complete core Candidate functionality; Admin 2.0 operational essentials; reliable Knowledge Sources; Story Bank and Workspaces; professional core reporting; the five Turing College review corrections; secure hosting, privacy and operations.

## 2. The five actual Turing College review findings (REVIEW-01 to REVIEW-05)

| ID | Finding | Priority | WP | Gate |
|---|---|---|---|---|
| REVIEW-01 | Prompt-injection defence depth: labelled regression corpus, held-out CI gate, injection-risk score on retrieval results, quarantine before context, tool-call revalidation and authorization before side effects | P0 | WP-05 | PG-03 |
| REVIEW-02 | Externalized, versioned prompts with loader, semantic versions plus hashes, run attribution, rollback without code | P1 | WP-17 | PG-12 |
| REVIEW-03 | Tool catalogue parity: registry as single source, generated descriptions, drift prevention, no widened tool set | P1 | WP-17 | PG-12 |
| REVIEW-04 | Silent embedding degradation: surface provider and degradation, fail closed in production, manifests with embedding identity, mismatch detection, BM25/vector/RRF evaluation, multilingual attribution | P0 | WP-06 | PG-05 |
| REVIEW-05 | Agent streaming: authenticated SSE with astream_events v2, safe projections, cancellation, reconnection safety, cost reconciliation, synchronous fallback | P1 | WP-17 | PG-06 |

Each is a separate row with numbered, testable criteria in the traceability document. The demo-observed findings are kept as separate engineering issues (DEMO-01 to DEMO-05) and are not reviewer findings.

## 3. Owner-requested capabilities (REQ-OWN-01 to REQ-OWN-08)

The placeholder owner decisions are replaced by specified R1.0 requirements. Each has numbered acceptance criteria, required tests, security and privacy impact and an honest current status (foundations exist for most; none is complete):

| ID | Requirement | Source | Gate |
|---|---|---|---|
| REQ-OWN-01 | Command Center dashboards with real sourced data; AI operations administration | ADMIN-04, ADMIN-06 | PG-08 |
| REQ-OWN-02 | Basic/Premium plan management without code changes; no billing enabled | ADMIN-02 | PG-08 |
| REQ-OWN-03 | Complete user management with restricted bulk actions and no private-content access | ADMIN-03 | PG-08 |
| REQ-OWN-04 | Prebuilt reports and a governed custom report builder | ADMIN-05 | PG-14 |
| REQ-OWN-05 | Permanent Knowledge Source persistence and reliability (19 owner requirements) | Part 4 | PG-05 |
| REQ-OWN-06 | Functional Story Bank with the create-to-restart acceptance journey | Part 5 | PG-13 |
| REQ-OWN-07 | Functional Workspaces with the invite-to-revoke acceptance journey | Part 6 | PG-13 |
| REQ-OWN-08 | Grouped, collapsible Admin navigation; Review and Diagnostics only under /admin | ADMIN-01 | PG-08 |

Further owner-stated requirements recorded: invitation-only registration (REQ-BETA-01), a real Candidate end-to-end journey test including the Start Interview regression (REQ-CAND-01), a separate frozen beta-scope coverage measure (REQ-COV-01), excluding unsupported market evidence (REQ-COV-02), proving deferrals are inaccessible through UI and API (REQ-DEFER-01) and not letting a disabled feature block an unrelated safe feature (REQ-SCOPE-01).

## 4. Work packages

Counts are the corrected reconciliation (Fix and Verify before R1.0, items with an OWNER DECISION disposition, Defer, Closed). The dashboard is authoritative.

| WP | Name | Owner role (person not yet named) | Fix | Verify | Owner | Defer | Closed |
|---|---|---|---|---|---|---|---|
| WP-01 | Governance, reviewers and owner decisions | Product Owner | 4 | 1 | 0 | 0 | 0 |
| WP-02 | Hosted deployment, operations and resilience | Platform and operations lead | 18 | 14 | 2 | 7 | 5 |
| WP-03 | Identity, email and access | Security lead | 2 | 3 | 1 | 2 | 0 |
| WP-04 | Privacy, data rights and legal | Privacy and legal lead | 8 | 8 | 15 | 0 | 2 |
| WP-05 | AI security and grounding policy | AI safety lead | 1 | 14 | 0 | 0 | 5 |
| WP-06 | Knowledge sources and retrieval (seven markets) | Knowledge and data lead | 19 | 7 | 20 | 36 | 10 |
| WP-07 | Candidate journeys, Mo and Practice quality | Product lead (candidate) | 1 | 4 | 4 | 5 | 3 |
| WP-08 | Multilingual programme (seven languages) | Localisation lead | 15 | 5 | 3 | 5 | 0 |
| WP-09 | Story Bank, Workspaces and shared reports | Product lead (collaboration) | 2 | 2 | 2 | 4 | 0 |
| WP-10 | Admin 2.0 (English-only) | Product lead (operations) | 5 | 1 | 2 | 19 | 9 |
| WP-11 | Commercial and billing (gated) | Commercial lead | 1 | 0 | 23 | 10 | 1 |
| WP-12 | Speech and realtime voice (gated) | Speech lead | 2 | 1 | 1 | 23 | 0 |
| WP-13 | External integrations | Integrations lead | 2 | 3 | 0 | 4 | 0 |
| WP-14 | Human validation and native review | Quality and human-review lead | 2 | 5 | 1 | 3 | 0 |
| WP-15 | Quality engineering, accessibility and technical debt | Engineering lead | 3 | 2 | 18 | 13 | 15 |
| WP-16 | Live evaluation and measurement | Evaluation lead | 0 | 4 | 3 | 12 | 2 |
| WP-17 | AI platform engineering: prompts, tool catalogue, streaming (new) | AI platform lead | 3 | 0 | 0 | 0 | 0 |

## 5. Totals and what changed

394 historical issues (52 closed with evidence preserved, 342 active, 161 production blockers, 72 pending owner decisions) are all preserved with original IDs. 58 new items: 5 reviewer findings, 8 owner capabilities, 16 language requirements, 6 other owner requirements, 5 demo-observed findings, 8 later-release scope rows, 10 cross-check items = 452 traced rows, **0 unmapped**. R1.0: **88 fix, 74 verify** (priorities P0 12, P1 86, P2 53, P3 11 across both). Deferred: R1.1 88, R1.2 18, R1.3 3, R1.4 23, R1.5 7, R1.6 2, R1.7 1, R2.0 1. 15 owner decisions are unscheduled (6 academic-only tasks awaiting confirmation of retirement, and the future Russian decision items).

Change from the previous reconciliation (433 rows): +19 rows, must-fix +18, must-verify 0, owner-decision dispositions +4, deferred -3. The movements are explained, not forced to old totals, in `RELEASE_BLOCKER_DASHBOARD.md`: REQ-OWN-01 to 08 left OWNER DECISION and became must-fix; six capstone-submission tasks were reclassified as academic only; Russian items became an unscheduled owner decision; deferrals were re-routed from invented themes onto the agreed R1.1 to R1.7 train.

## 6. Academic-only versus production

Six historical items concern the capstone submission only and are not production dependencies: IR-DEADLINE, IR-TURING-RUBRIC, IR-DEPLOY-EXPECT, IR-AC-LEDGER, IR-RC004-SPEC, G-WALK-ENV. They carry scope class ACADEMIC_ONLY, are not counted as R1.0 work, and are retired only when the owner confirms (OD-ACADEMIC-01); none is silently closed. The failed historical gates and results are untouched.

## 7. Production gates and per-language gates

PG-01 to PG-15 and LG-01 to LG-14 per language are defined measurably in `PRODUCTION_ACCEPTANCE_MATRIX.md`. A mandatory safety, privacy, licensing or operational gate cannot be bypassed by recording an accepted limitation; the owner may remove a feature from scope or delay activation. No PASS evidence is fabricated: none of PG-01 to PG-10 or PG-12 to PG-15 is met today; PG-11 (reconciliation) is met and machine-checked.

## 8. Rules carried forward

Platform Admin is not a candidate-data superuser. Unapproved knowledge never reaches candidate retrieval. Billing, Stripe, server speech, Compensation V2, international sources, history/model-profile gating and the reconciliation scheduler stay disabled; a deferral is valid only while its gate constants are False (checked) and, per REQ-DEFER-01, its UI and API entry points are proven unreachable. No safety, privacy or operational dependency is deferred while its feature is enabled. The EUR 10 capstone demonstration budget is not reusable; any live evaluation needs a new approved budget (OD-BUDGET).

## 9. Critical path

See `RELEASE_TRAIN_AND_DEPENDENCIES.md` section 3. The R1.0 list is large and several steps depend on people and environments the owner has not yet named or authorised; the safe reading is that the owner decides OD-SCOPE-01 early rather than assuming the date holds.
