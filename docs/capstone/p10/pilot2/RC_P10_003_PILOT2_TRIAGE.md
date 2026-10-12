# Pilot 2 triage and remediation backlog (RC-P10-003)

Basis: [results](RC_P10_003_PILOT2_RESULTS.md) (n=3) and the [issue register](RC_P10_003_PILOT2_ISSUE_REGISTER.md). This is a triage, not an implementation: **no product fix is made in this wave.** Triage follows the AC-24 decision rule (frequency, severity, task impact, strategy fit, privacy/security impact, accessibility impact, complexity/risk, personal preference).

**Verdict: CONDITIONAL GO - TARGETED REMEDIATION REQUIRED.** BLOCKER 0.

## P0 - blocking
None. No data loss, cross-user exposure, authentication failure, broken core Practice or unsafe condition was observed.

## P1 - must fix before the next RC / final validation
| ID | Item | Why P1 |
|---|---|---|
| P2-01 | Make sharing state, sharing controls and revoke controls easy to find | all 3 counted sessions failed the task; privacy-trust journey; HIGH, U2. **Status: REMEDIATED - PENDING HUMAN REVALIDATION** (implemented and covered by deterministic regression; not closed until a targeted human revalidation; AC-24 remains PARTIAL while P2-02, P2-03 and P2-04 are open) |
| P2-03 | Explicit "Interview Answer Score" labelling and explanation (per-question vs overall, existing dimensions, next action) | lowest-rated dimension (3.67); 2 of 3 rated 3; no new scoring formula. **Status: REMEDIATED - PENDING HUMAN REVALIDATION** (visible label, per-answer vs session distinction, seven existing dimensions shown, no formula and no bands, no backend change; not closed until human revalidation; AC-24 remains PARTIAL while P2-04 is open) |
| P2-04 | Provenance states: AI generated / Source-backed / Candidate-provided / Candidate-verified | named the most confusing part; trust-critical; no unsupported verification claim. **Status: REMEDIATED - PENDING HUMAN REVALIDATION** (the candidate-facing state is "Reviewed by you", never "verified"; the misleading Story Bank "Evidence verified" label is corrected; no backend change) |
| P2-02 | Safe isolated representative knowledge fixture or reproducible pilot knowledge environment | the source-backed experience was never validated; required before the next human validation; never copy or link the protected developer knowledge base. **Status: REMEDIATED - PENDING HUMAN REVALIDATION** (the isolated retrieval environment now exists and is deterministically validated; the candidate-facing source experience has not yet been re-tested by humans) |

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

## Current remediation status (after P2-04)
All four P1 items (P2-01, P2-02, P2-03, P2-04) are REMEDIATED with deterministic regression coverage and are PENDING targeted human revalidation. The historical Pilot 2 verdict (CONDITIONAL GO - TARGETED REMEDIATION REQUIRED, on RC-P10-003) is unchanged: the remediated runtime has not yet been qualified under a new RC and has not been re-tested by humans.

**AC-24 decision.** The AC-24 boundary (`p10/pilot_plan.md`) is: actual participant observations are distinguished from internal review; consequential fixes receive regression checks (at least 3 actual participants, an identified RC, anonymised observations, lessons, disclosed issues). Its completion checklist (`p10/pilot_lessons_template.md`, "verify before claiming PASS") and the consequential-fix rule (`p10/issue_log_template.md`) additionally require that fixes are regression-tested AND recorded under a NEW RC when runtime changed (affected evaluators plus the release gate run on it). The P1 fixes have regression checks, but no new RC (RC-P10-004) exists and the release gate has not yet been run on the remediated runtime. **AC-24 therefore remains PARTIAL**; it can move to PASS when the remediated runtime is qualified and recorded under RC-P10-004. Human revalidation is a separate validation step (P10F) and is not part of the AC-24 criterion as written.

**Integrated qualification.** P2-01 to P2-04 were qualified together on one runtime (`PILOT2_P1_REMEDIATION_QUALIFICATION.md`). The states above are unchanged (pending human revalidation), AC-24 remains PARTIAL and RC-P10-004 is not created.
