# Pilot 2 triage and remediation backlog (RC-P10-003)

Basis: [results](RC_P10_003_PILOT2_RESULTS.md) (n=3) and the [issue register](RC_P10_003_PILOT2_ISSUE_REGISTER.md). This is a triage, not an implementation: **no product fix is made in this wave.** Triage follows the AC-24 decision rule (frequency, severity, task impact, strategy fit, privacy/security impact, accessibility impact, complexity/risk, personal preference).

**Verdict: CONDITIONAL GO - TARGETED REMEDIATION REQUIRED.** BLOCKER 0.

## P0 - blocking
None. No data loss, cross-user exposure, authentication failure, broken core Practice or unsafe condition was observed.

## P1 - must fix before the next RC / final validation
| ID | Item | Why P1 |
|---|---|---|
| P2-01 | Make sharing state, sharing controls and revoke controls easy to find | all 3 counted sessions failed the task; privacy-trust journey; HIGH, U2 |
| P2-03 | Explicit "Interview Answer Score" labelling and explanation (per-question vs overall, existing dimensions, next action) | lowest-rated dimension (3.67); 2 of 3 rated 3; no new scoring formula |
| P2-04 | Provenance states: AI generated / Source-backed / Candidate-provided / Candidate-verified | named the most confusing part; trust-critical; no unsupported verification claim |
| P2-02 | Safe isolated representative knowledge fixture or reproducible pilot knowledge environment | the source-backed experience was never validated; required before the next human validation; never copy or link the protected developer knowledge base |

## P2 - should fix
| ID | Item |
|---|---|
| P2-05 | Explain why each onboarding step matters; add visual explanation; make Help and the tutorial more discoverable |
| P2-08 | Mo naturalness, evaluated under controlled regression coverage |
| P2-09 | Reproduce the Opera voice failure; fix only if confirmed (Safari worked) |
| - | Opportunity/practice context summary and support-entry placement (observations without a dedicated register ID; revisit with the next evidence) |

## P3 - strategic / enhancement
| ID | Item |
|---|---|
| P2-07 | Candidate Progress Intelligence (recurring strengths and weaknesses, trend, practice counts, Opportunity-linked progress, next-practice suggestions) derived only from real structured history |
| P2-06 | Pricing / product comparison and positioning, including re-evaluation of the v4 website changes already on main (PR #137), which Pilot 2 did not test |
| - | Founder / About enhancement, richer product walkthrough or process video |

## Sequencing rules
1. Fix, then run targeted regression and the affected evaluators. Per the AC-24 consequential-fix rule, a runtime change means a **new RC (expected RC-P10-004)**; RC-P10-003 stays immutable and traceable.
2. Do not mix RCs in aggregated Pilot results; stratify by RC.
3. Pilot 2 findings were produced on RC-P10-003 only. They do not validate anything changed afterwards (including the v4 website work on main).
4. AC-24 moves to PASS only after the P1 items are regression-tested.

## Not part of this triage
Platform Admin owner/orchestrator change (see [AD-W12-01](../../admin/AD_W12_01_PLATFORM_ADMIN_OWNER_ORCHESTRATOR.md)), P10C and later phases, live-provider validation, and RC-P10-004 creation.
