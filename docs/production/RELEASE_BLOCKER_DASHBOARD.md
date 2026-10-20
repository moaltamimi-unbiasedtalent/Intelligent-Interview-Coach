# Release Blocker Dashboard (R1.0, 30 November 2026, free private beta)

**Status:** corrected 2026-10-21 against the owner's authoritative requirements. Counts come from `PRODUCTION_ISSUE_RECONCILIATION.json` and are checked by `scripts/production/reconcile_issues.py check`. Dispositions remain PROPOSED for owner review.

## Totals

| Measure | Count |
|---|---|
| Historical issues (all preserved with original IDs) | 394 |
| Historically closed (evidence preserved) | 52 |
| Historically active | 342 |
| Historical production blockers | 161 |
| Historical pending owner decisions | 72 |
| New items | 58: reviewer findings 5, owner capabilities 8, language requirements 16, other owner requirements 6, demo-observed findings 5, later-release scope rows 8, cross-check 10 |
| Traced rows in total | 452 |
| Earlier alias merges recorded in the register | 18 |
| Duplicates reconciled this pass (by meaning, IDs kept) | 6 |
| **R1.0 must-fix** | **88** |
| **R1.0 must-verify** | **74** |
| Items with an OWNER DECISION disposition | 95 (of which unscheduled 15, academic-only 6) |
| Genuinely open owner decisions in the register | 18 new, plus the 72 historical |
| Deferred | R1.1: 88, R1.2: 18, R1.3: 3, R1.4: 23, R1.5: 7, R1.6: 2, R1.7: 1, R2.0: 1 |
| Unmapped issues | **0** |

## Change since the previous reconciliation (PR #211 at `4084eb9`)

| Measure | Previous | Now | Change |
|---|---|---|---|
| Traced rows | 433 | 452 | +19 |
| New items | 39 | 58 | +19 |
| R1.0 must-fix | 70 | 88 | +18 |
| R1.0 must-verify | 74 | 74 | +0 |
| OWNER DECISION disposition | 91 | 95 | +4 |
| Deferred | 146 | 143 | -3 |

Why the numbers moved, not forced to match the old totals:

- The five reviewer findings, eight owner capabilities, the beta, candidate, coverage and deferral-verification requirements and the five demo findings were added as specified R1.0 requirements; REQ-OWN-01 to 08 left OWNER DECISION and became FIX BEFORE R1.0 (this raises must-fix and lowers owner decisions).
- The 19 earlier open decisions shrank to the genuinely open ones: decisions the owner already made (languages, Russian, R1.3, release train, requirement text, reviewer findings) became requirements.
- Russian items moved from a deferral to OWNER DECISION (UNSCHEDULED), because the owner made later activation a separate future decision, not an automatic R2.0 commitment.
- Six historical capstone-submission tasks were reclassified ACADEMIC_ONLY and moved to OWNER DECISION (UNSCHEDULED) pending confirmation of retirement; they no longer count as production work.
- Deferrals were re-routed from the earlier invented R1.1 to R2.0 themes onto the agreed train: commercial to R1.1, speech to R1.4, additional-country evidence to R1.5, compensation to R1.6, with items that fit no agreed theme placed in R1.1 (R1.2 for Admin) as a proposal.

## Totals by release (all dispositions)

| Release | Items | Theme |
|---|---|---|
| R1.0 | 197 | 30 November 2026: free, invitation-only private production beta; seven languages each subject to individual qu |
| R1.1 | 132 | Indicative December 2026: paid beta and plan expansion (Stripe and subscription lifecycle after provider/legal |
| R1.2 | 19 | Indicative December 2026 to January 2027: advanced Admin and automation (scheduled reporting, advanced analyti |
| R1.3 | 3 | Indicative January to February 2027: Mandarin, Hindi, Arabic (new locale, prompt, safety, retrieval, accessibi |
| R1.4 | 23 | Indicative February 2027: voice interview experience (qualified STT, TTS and live voice practice; licensing an |
| R1.5 | 7 | Indicative February to March 2027: global career intelligence (additional countries, qualified occupational so |
| R1.6 | 2 | Indicative March 2027: Compensation Intelligence V2 (qualified salary datasets, geographic comparison, freshne |
| R1.7 | 1 | After R1.6, date not committed: teams and enterprise (enterprise Workspaces, organization subscriptions, SSO a |
| R2.0 | 1 | Evidence-led, subsequent: expanded intelligent career platform (personalized guidance, agentic workflows, deep |
| UNSCHEDULED | 15 | owner decisions with no release yet |
| n/a (closed) | 52 | closure evidence preserved |

## R1.0 work by priority

| Priority | Items |
|---|---|
| P0 | 12 |
| P1 | 86 |
| P2 | 53 |
| P3 | 11 |

## R1.0 work by work package

| WP | Fix | Verify | Owner decisions |
|---|---|---|---|
| WP-01 Governance, reviewers and owner decisions | 4 | 1 | 0 |
| WP-02 Hosted deployment, operations and resilience | 18 | 14 | 2 |
| WP-03 Identity, email and access | 2 | 3 | 1 |
| WP-04 Privacy, data rights and legal | 8 | 8 | 15 |
| WP-05 AI security and grounding policy | 1 | 14 | 0 |
| WP-06 Knowledge sources and retrieval (seven markets) | 19 | 7 | 20 |
| WP-07 Candidate journeys, Mo and Practice quality | 1 | 4 | 4 |
| WP-08 Multilingual programme (seven languages) | 15 | 5 | 3 |
| WP-09 Story Bank, Workspaces and shared reports | 2 | 2 | 2 |
| WP-10 Admin 2.0 (English-only): users, plans, reports, knowledge, navigation | 5 | 1 | 2 |
| WP-11 Commercial and billing (gated) | 1 | 0 | 23 |
| WP-12 Speech and realtime voice (gated) | 2 | 1 | 1 |
| WP-13 External integrations | 2 | 3 | 0 |
| WP-14 Human validation and native review | 2 | 5 | 1 |
| WP-15 Quality engineering, accessibility and technical debt | 3 | 2 | 18 |
| WP-16 Live evaluation and measurement | 0 | 4 | 3 |
| WP-17 AI platform engineering: versioned prompts, tool catalogue, streaming | 3 | 0 | 0 |

## Capacity warning

162 items must be fixed or verified before R1.0 on 30 November 2026. The date is the owner's target; safety, privacy, licensing and operational gates are not waived to meet it. Many items need people not yet named (reviewers, native reviewers, legal qualifiers) or an authorised hosted environment. OD-SCOPE-01 asks the owner what happens if a mandatory gate is not met: delay, remove the feature from scope, or keep it disabled.

## R1.0 P0 items

| ID | Title | Origin | Disposition | WP |
|---|---|---|---|---|
| BL-1 | Verify reviewer identities and accounts | REGISTER-HISTORICAL | FIX BEFORE R1.0 | WP-01 |
| BL-2 | Appoint named human reviewers A, B, C | REGISTER-HISTORICAL | FIX BEFORE R1.0 | WP-01 |
| BL-3 | Complete two-person role changes for appointments | REGISTER-HISTORICAL | FIX BEFORE R1.0 | WP-01 |
| BL-8 | Legal review of commercial use of BLS content outside US (RB-LIC-1) | REGISTER-HISTORICAL | FIX BEFORE R1.0 | WP-06 |
| K-PRIV | Privacy, Terms and AI-transparency pages are engineering drafts | REGISTER-HISTORICAL | FIX BEFORE R1.0 | WP-04 |
| REQ-BETA-01 | Invitation-only registration for the private beta | OWNER-REQUIREMENT | FIX BEFORE R1.0 | WP-03 |
| REQ-CAND-01 | Real Candidate end-to-end journey tests including Start interview | OWNER-REQUIREMENT | FIX BEFORE R1.0 | WP-07 |
| REQ-COV-02 | Exclude unsupported or unlicensed market evidence from enabled features | OWNER-REQUIREMENT | FIX BEFORE R1.0 | WP-06 |
| REQ-DEFER-01 | Verify every deferral leaves the feature inaccessible through UI and backend | OWNER-REQUIREMENT | FIX BEFORE R1.0 | WP-15 |
| REQ-OWN-05 | Knowledge Sources: permanent persistence and reliability | OWNER-REQUIREMENT | FIX BEFORE R1.0 | WP-06 |
| REVIEW-01 | Prompt-injection defence depth (Turing College review finding) | TURING-REVIEW | FIX BEFORE R1.0 | WP-05 |
| REVIEW-04 | Silent embedding degradation (Turing College review finding) | TURING-REVIEW | FIX BEFORE R1.0 | WP-06 |

## Gates that keep deferred features disabled

- `src.billing.policy.LIVE_BILLING_ENABLED` must be False
- `src.billing.policy.EXTERNAL_CHECKOUT_AUTHORIZED` must be False
- `src.billing.policy.STRIPE_WEBHOOK_AUTHORIZED` must be False
- `src.billing.policy.RECONCILE_SCHEDULER_ENABLED` must be False
- `src.billing.policy.PROVIDER_READS_AUTHORIZED` must be False
- `src.speech.policy.SERVER_SPEECH_PROVIDERS_AUTHORIZED` must be False
- `src.speech.policy.WHISPER_API_TRANSPORT_AUTHORIZED` must be False
- `src.speech.policy.MODEL_DOWNLOADS_AUTHORIZED` must be False
- `src.speech.policy.VOICE_CLONING_ENABLED` must be False
- `src.application.history_access.HISTORY_RESTRICTIONS_ENFORCED` must be False
- `src.application.model_profile_access.MODEL_PROFILE_ENFORCED` must be False
