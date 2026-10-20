# Release Blocker Dashboard (R1.0, 30 November 2026)

**Status:** PROPOSED, generated 2026-10-21. Counts come from `PRODUCTION_ISSUE_RECONCILIATION.json` and are checked by `scripts/production/reconcile_issues.py check`.

## Totals

| Measure | Count |
|---|---|
| Historical issues | 394 |
| Historically closed (evidence preserved) | 52 |
| Historically active | 342 |
| Historical production blockers | 161 |
| Historical pending owner decisions | 72 |
| Newly recorded items | 39 (language 16, owner-named areas 8, demonstration findings 5, cross-check 10) |
| Earlier alias merges recorded in the register | 18 |
| Duplicates reconciled in this pass (by meaning, IDs kept) | 6 |
| **R1.0 must-fix** | **70** |
| **R1.0 must-verify** | **74** |
| Owner decisions | 91 |
| Deferred | R1.1: 94, R1.2: 15, R1.3: 2, R2.0: 35 |
| Unmapped issues | **0** |

## R1.0 work by priority

| Priority | Items |
|---|---|
| P0 | 7 |
| P1 | 74 |
| P2 | 52 |
| P3 | 11 |

## R1.0 work by work package

| WP | Fix | Verify | Owner decisions |
|---|---|---|---|
| WP-01 Governance, reviewers and owner decisions | 4 | 0 | 0 |
| WP-02 Hosted deployment, operations and resilience | 18 | 14 | 2 |
| WP-03 Identity, email and access | 1 | 3 | 1 |
| WP-04 Privacy, data rights and legal | 8 | 9 | 14 |
| WP-05 AI security and grounding policy | 0 | 14 | 0 |
| WP-06 Knowledge sources and retrieval (seven markets) | 16 | 7 | 16 |
| WP-07 Candidate journeys, Mo and Practice quality | 0 | 4 | 3 |
| WP-08 Multilingual programme (seven languages) | 15 | 5 | 1 |
| WP-09 Story Bank, Workspaces and shared reports | 0 | 2 | 4 |
| WP-10 Admin 2.0 (English-only): users, plans, reports, knowledge, navigation | 0 | 1 | 7 |
| WP-11 Commercial and billing (gated) | 0 | 0 | 22 |
| WP-12 Speech and realtime voice (gated) | 2 | 1 | 0 |
| WP-13 External integrations | 2 | 3 | 0 |
| WP-14 Human validation and native review | 2 | 5 | 0 |
| WP-15 Quality engineering, accessibility and technical debt | 2 | 2 | 18 |
| WP-16 Live evaluation and measurement | 0 | 4 | 3 |

## Capacity warning

144 items must be fixed or verified before R1.0 and the date is 30 November 2026. Many need people who are not yet named (reviewers A, B, C, native reviewers for seven languages, legal counsel) or an authorised hosted environment. The owner should decide the scope trade-off explicitly (OD-SCOPE-01 in OWNER_DECISION_REGISTER.md); this dashboard does not assume it will fit.

## R1.0 P0 items

| ID | Title | Disposition | WP |
|---|---|---|---|
| BL-1 | Verify reviewer identities and accounts | FIX BEFORE R1.0 | WP-01 |
| BL-2 | Appoint named human reviewers A, B, C | FIX BEFORE R1.0 | WP-01 |
| BL-3 | Complete two-person role changes for appointments | FIX BEFORE R1.0 | WP-01 |
| BL-8 | Legal review of commercial use of BLS content outside US (RB-LIC-1) | FIX BEFORE R1.0 | WP-06 |
| IR-AC-LEDGER | Acceptance criteria dispositions are P9-era and spread over three documents | VERIFY BEFORE R1.0 | WP-07 |
| IR-TURING-RUBRIC | The Turing College capstone brief and rubric are not in the repository | VERIFY BEFORE R1.0 | WP-04 |
| K-PRIV | Privacy, Terms and AI-transparency pages are engineering drafts | FIX BEFORE R1.0 | WP-04 |

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
