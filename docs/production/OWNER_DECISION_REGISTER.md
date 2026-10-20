# Owner Decision Register (Production Roadmap V2.2)

**Status:** PROPOSED, generated 2026-10-21. Nothing here is decided on the owner's behalf. Historical decisions keep their register IDs and wording; new decisions are listed first.

## New decisions required by V2.2

| ID | Decision | Detail | Proposed release |
|---|---|---|---|
| OD-SCOPE-01 | Confirm or re-scope R1.0 (30 November 2026) | The reconciled R1.0 must-fix and must-verify counts (see RELEASE_BLOCKER_DASHBOARD.md) exceed what a team can plausibly close in about five weeks, and several items depend on people not yet named. Decide: hold the date and re-scope, move the date, or release a subset. | R1.0 |
| OD-LANG-01 | Approve the seven R1.0 languages and the per-language gates LG-01..LG-14 | Languages: English, German, Spanish, Italian, Portuguese, French, Dutch. Decide what happens if a language fails its gates at the cut-off: it is not offered for real-user access (recommended), or the release waits. The owner said R1.0 must not be English-only. | R1.0 |
| OD-LANG-02 | Approve the proposed primary market per language | English-Ireland, German-Germany, Spanish-Spain, Italian-Italy, Portuguese-Portugal, French-France, Dutch-Netherlands. PROPOSED only: used solely as an explicit, user-visible suggestion after source qualification; never inferred from the interface language. | R1.0 |
| OD-LANG-03 | Name the native-language reviewer for each of the seven languages | No reviewer is named. Needed before LG-11. | R1.0 |
| OD-LANG-04 | Name the legal and privacy translation qualifier(s) for the seven languages | Needed before any real-user access (LG-10). | R1.0 |
| OD-LANG-05 | Approve hiding Russian from candidate language choices for R1.0 | Russian is exposed today as an eighth locale; the owner decision excludes it from R1.0 and forbids exposing it as an active beta locale. Code is preserved. | R1.0 |
| OD-LANG-06 | Approve the R1.3 plan for Mandarin, Hindi and Arabic | Each needs new language-specific engineering and human qualification; plans are not yet written. | R1.3 |
| OD-REQ-TEXT | Supply the approved requirement text for the owner-named areas | Admin 2.0, Plans, Users, Reports, Knowledge, Story Bank, Workspaces and navigation (REQ-OWN-01..08): the detailed text is not in the repository, so no scope was invented. | R1.0 |
| OD-REVIEW-FINDINGS | Confirm or replace the five capstone reviewer findings | The reviewer findings were not supplied; five engineering-observed findings (RF-01..RF-05) are recorded in their place. | R1.0 |
| OD-HOSTED | Authorise a hosted staging and production environment | Hosted deployment (EX-12) cannot be certified locally; needed for the TLS, backup, rollback and scale gates. | R1.0 |
| OD-BUDGET | Approve a bounded live-evaluation and live-provider budget for qualification | Native-review samples, live multilingual Mo checks and a larger RAGAS run need an explicit budget; the EUR 10 capstone demonstration budget is not reusable. | R1.0 |
| OD-RELEASE-TRAIN | Approve or amend the proposed themes for R1.1, R1.2 and R2.0 | Only R1.0 (30 November 2026) and R1.3 (languages) were fixed by the owner; the other themes are proposals. | R1.1 |

## Historical pending owner decisions (72)

| ID | Decision | Owner action recorded | Priority | If approved: release | WP |
|---|---|---|---|---|---|
| IR-DEADLINE | Course deadline and time zone are unconfirmed (planning documents say 2026-10-20 | REQUIRED: confirm the deadline and time zone | P0 | R1.0 | WP-07 |
| IR-DEPLOY-EXPECT | Does local execution satisfy the course deployment expectation? | REQUIRED: ask the course lead; decide hosted versus local demonstration | P0 | R1.0 | WP-02 |
| IR-RC004-SPEC | No dedicated RC-P10-004 entry-criteria specification existed | REQUIRED: approve or amend the recorded entry conditions; separate approval to create RC-P10-004 | P0 | R1.0 | WP-07 |
| B-EMBED-SEL | Embedding provider and model selection | Choose embedding provider/model | P1 | R1.0 | WP-06 |
| C-PROTO | Reviewer protocols and rating rubric for AI quality | Reviewer appointments, rating protocol | P1 | R1.0 | WP-16 |
| C-THRESH | Owner thresholds for AI quality | Owner sets thresholds and spend cap before final evaluation (evaluation-plan rule) | P1 | R1.0 | WP-16 |
| D-21 | D-21 name who performs qualified legal review | Owner to name legal reviewer | P1 | R1.0 | WP-04 |
| F2B1-OD-01 | Legal seller entity | Owner decision required | P1 | R1.2 | WP-11 |
| F2B1-OD-02 | Product classification (automated digital product) | Owner decision required | P1 | R1.2 | WP-11 |
| F2B1-OD-03 | Product tax code | Owner decision required | P1 | R1.2 | WP-11 |
| F2B1-OD-04 | What Premium includes beyond Basic | Owner decision required | P1 | R1.2 | WP-11 |
| F2B1-OD-05 | Premium monthly price | Owner decision required | P1 | R1.2 | WP-11 |
| I-ALLOW | Numerical Basic/Premium allowances not approved | Owner approval of numbers | P1 | R1.2 | WP-11 |
| I-ENT-POLICY | Paid entitlement policy unapproved | Approve trial/grace/refund/cancel/dispute rules | P1 | R1.2 | WP-11 |
| I-FAST | Basic-to-Fast transition not approved | Approve transition and notice | P1 | R1.2 | WP-11 |
| I-PREMIUM-PRICE | Premium pricing and Basic/Premium product matrix commercial approval | Approve price | P1 | R1.2 | WP-11 |
| IR-DEVDB-STALE | The developer database is 12 Alembic revisions behind the code head | REQUIRED: migrate the developer database or leave it | P1 | R1.0 | WP-07 |
| IR-RAGAS-LIVE-APPROVAL | Live RAGAS evaluation awaits the owner's spending approval and three prerequisit | REQUIRED: approve the ceiling, the new ledger and the code change; provide the key | P1 | R1.0 | WP-06 |
| K-PROVIDER | Third-party model provider data handling for real candidate data | None recorded | P1 | R1.0 | WP-04 |
| SJA-05 | Knowledge approval has no distinct-actor rule or step-up | REQUIRED: whether knowledge approval and activation need a distinct-actor rule and/or fresh-password step-up (related A-04). Source qualific | P1 | R1.0 | WP-15 |
| B-COVEVAL | Decision whether to change coverage evaluator to check data origin/country (F-CO | Owner decision (c) in P10D s12 | P2 | R1.1 | WP-06 |
| C-USD15 | USD 15 extra ceiling not approved; 15 calls remain | Owner approval to raise limits | P2 | R1.1 | WP-16 |
| D-01 | D-01 adopt or amend recovered GKB/C1-C4 specification | D-01 | P2 | R1.1 | WP-06 |
| D-02 | D-02 adopt ambiguity-state and recency/eligibility policy | D-02 | P2 | R1.1 | WP-06 |
| F2B-D22 | D-22 ASHE weekly never annualised; unanswered | D-03, D-22, D-04, D-12, D-13, D-15 | P2 | R1.1 | WP-06 |
| F2B1-OD-06 | Premium annual price (no annual plan exists) | Owner decision required | P2 | R1.2 | WP-11 |
| F2B1-OD-07 | Currency | Owner decision required | P2 | R1.2 | WP-11 |
| F2B1-OD-08 | Tax-inclusive presentation | Owner decision required | P2 | R1.2 | WP-11 |
| F2B1-OD-09 | Supported customer countries | Owner decision required | P2 | R1.2 | WP-11 |
| F2B1-OD-10 | B2B subscriptions | Owner decision required | P2 | R1.2 | WP-11 |
| F2B1-OD-11 | Trial policy | Owner decision required | P2 | R1.2 | WP-11 |
| F2B1-OD-12 | Failed-payment grace period | Owner decision required | P2 | R1.2 | WP-11 |
| F2B1-OD-13 | Cancellation policy | Owner decision required | P2 | R1.2 | WP-11 |
| F2B1-OD-14 | Refund policy | Owner decision required | P2 | R1.2 | WP-11 |
| F2B1-OD-15 | Dispute entitlement policy | Owner decision required | P2 | R1.2 | WP-11 |
| F2B1-OD-16 | Billing data retention | Owner decision required | P2 | R1.2 | WP-11 |
| H-REDIS-POLICY | Redis failure policy per bucket undecided | Failure policy per bucket | P2 | R1.0 | WP-02 |
| I-GRANDFATHER | Grandfathering of existing candidates | Decision | P2 | R1.2 | WP-11 |
| I-HISTORY-SHARE | Existing-share policy before history activation | Decision | P2 | R1.2 | WP-09 |
| I-RESET | Quota reset periods not approved | Owner approval | P2 | R1.2 | WP-11 |
| K-ATTR | Attribution wording decisions | None recorded | P2 | R1.0 | WP-04 |
| K-LEGALACC | Legal acceptance of owner policy decisions | None recorded | P2 | R1.0 | WP-04 |
| M-LEDGER | Mo and company-research cost-ledger gap | Whether Mo/company research must enter ledger before launch | P2 | R1.0 | WP-15 |
| PRIV-BILL-RET | Billing data retention and erasure review | Owner and legal retention decision | P2 | R1.2 | WP-04 |
| PRIV-POLICY01 | Verified-email policy (POLICY-01) | Policy decision before public launch | P2 | R1.0 | WP-04 |
| PRIV-RET | No retention periods for candidate content | Retention schedule | P2 | R1.0 | WP-04 |
| W9.8-D7 | Original-file export bundle | Scope decision | P2 | R1.0 | WP-04 |
| A-AGG | Five BLS-specific aggregates quarantined | Later policy review | P3 | R1.1 | WP-06 |
| D-05 | D-05 padded ISCO identity and plan for 21 legacy rows | D-05 | P3 | R1.1 | WP-06 |
| D-06 | D-06 baseline manifest freeze (GKB-0) | D-06 (status ambiguous between documents) | P3 | R1.1 | WP-06 |
| D-07 | D-07 ESCO language releases | D-07 | P3 | R2.0 | WP-06 |
| D-10 | D-10 FX and PPP sources and methodology | D-10 | P3 | R1.1 | WP-06 |
| D-11 | D-11 secondary-data qualification criteria | D-11 | P3 | R1.1 | WP-06 |
| D-14 | D-14 regional-geography classification rule (policy p10c-d/1) | D-14 | P3 | R1.1 | WP-06 |
| D-16 | D-16 precedence category for non-Eurostat harmonised sources (ILOSTAT) | D-16 | P3 | R1.0 | WP-06 |
| D-17 | D-17 evidence-state vocabulary adoption | D-17 | P3 | R1.1 | WP-06 |
| D-18-19 | D-18 / D-19 South America region vocabularies and national classifications | D-18, D-19 | P3 | R1.1 | WP-06 |
| IR-REHEARSAL-CALL | One unplanned live agent run during the P11 rehearsal (outside the P10E ledger) | REQUIRED: acknowledge the unplanned call | P3 | R1.1 | WP-15 |
| J-OIDC-PWD | OIDC-only users cannot set a password via recovery | Product decision | P3 | R1.1 | WP-03 |
| M-LEGACY01 | Legacy Streamlit UI retained (LEGACY-01) | Retirement task | P3 | R1.1 | WP-15 |
| M-POLICY02 | Evaluation score consistency (POLICY-02) | Decision | P3 | R1.1 | WP-15 |
| PRIV-SUPPORT-NOTICE | Support data / privacy request response time | Whether to commit to response-time statements | P3 | R1.0 | WP-04 |
| SJA-01 | AI config: second approver must be a second Platform Admin | Possible future permission review; none made | P3 | R1.1 | WP-15 |
| SJA-02 | Knowledge Admin cannot retry/cancel failed jobs | Possible future permission review; none made | P3 | R1.1 | WP-15 |
| SJA-03 | Billing/Security-Privacy admins cannot see queue state | Possible future permission review; none made | P3 | R1.2 | WP-15 |
| SJA-04 | Operations Admin partly useful Review/Diagnostics | Whether to add permission or hide the destination | P3 | R1.1 | WP-10 |
| W9.8-D1b | Preparation-chat selective deletion | Prioritisation not recorded | P3 | R1.0 | WP-04 |
| W9.8-D3 | Bulk memory deletion | Not scheduled; no decision recorded | P3 | R1.0 | WP-04 |
| W9.8-D4 | Per-version document deletion | Not scheduled | P3 | R1.0 | WP-04 |
| W9.8-D5 | Auth-session list/revoke UI | Not scheduled | P3 | R1.0 | WP-04 |
| W9.8-D6 | Feedback list and deletion page | Not scheduled | P3 | R1.0 | WP-04 |
| W9.8-D8 | Orphan workspace invitations to a deleted user's email | Not scheduled | P3 | R1.0 | WP-09 |

## New items needing an owner decision (19)

| ID | Title | Proposed release |
|---|---|---|
| REQ-LANG-16 | Approve and qualify the proposed primary market per language | R1.0 |
| REQ-OWN-01 | Owner-requested requirement: Admin 2.0 | R1.0 |
| REQ-OWN-02 | Owner-requested requirement: Plans | R1.0 |
| REQ-OWN-03 | Owner-requested requirement: Users | R1.0 |
| REQ-OWN-04 | Owner-requested requirement: Reports | R1.0 |
| REQ-OWN-05 | Owner-requested requirement: Knowledge (Admin sources) | R1.0 |
| REQ-OWN-06 | Owner-requested requirement: Story Bank | R1.0 |
| REQ-OWN-07 | Owner-requested requirement: Workspaces | R1.0 |
| REQ-OWN-08 | Owner-requested requirement: Navigation | R1.0 |
| XC-AC-AC-18 | Acceptance ledger (current) AC-18: Review surfaces: owned recent runs, safe specialist events, bound | R1.0 |
| XC-AC-AC-23 | Acceptance ledger (current) AC-23: Voice measurement: defined sample, reference transcripts, correct | R1.0 |
| XC-AC-AC-24 | Acceptance ledger (current) AC-24: Pilot and lessons: actual participant observations distinguished  | R1.0 |
| XC-AC-AC-25 | Acceptance ledger (current) AC-25: Submission consistency: README, three decks, selected ten-minute  | R1.0 |
| XC-P9-Deep-page-localization-debt | P9 quality register (carried items) Deep-page-localization-debt: Deep-page localization debt | R1.0 |
| XC-P9-Live-multi-agent-provider-qual | P9 quality register (carried items) Live-multi-agent-provider-qual: Live multi-agent/provider qualit | R1.0 |
| XC-P9-Live-transactional-email | P9 quality register (carried items) Live-transactional-email: Live transactional email | R1.0 |
| XC-P9-Untracked-checkpoint-deletion | P9 quality register (carried items) Untracked-checkpoint-deletion-: Untracked checkpoint deletion re | R1.0 |
| XC-REL-R-33 | Release acceptance matrix (P10B) R-33: Email-verification behaviour pinned | R1.0 |
| XC-REL-R-97 | Release acceptance matrix (P10B) R-97: Google OIDC live behaviour unvalidated | R1.0 |
