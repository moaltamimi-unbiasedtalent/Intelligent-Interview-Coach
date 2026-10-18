# P10C-F2A — Post-Submission Backlog (deferred by the product owner, 2026-10-18)

**None of these items is complete. None is waived.** They are deferred until after the Turing College capstone submission unless an existing mandatory release gate requires them earlier; a deferred mandatory production requirement is never classified as done. Items are ordered by priority: security first, then legal exposure, then evidence reliability, then candidate impact, then technical dependency. Related documents: [closure](P10C_F2A_CAPSTONE_ENGINEERING_CLOSURE.md), [human review package](P10C_F2A_HUMAN_REVIEW_AND_APPROVAL.md), [coverage gap analysis](P10C_F2A_COVERAGE_GAP_ANALYSIS.md).

| # | Item | Why it ranks here | Depends on | Blocks | Status |
|---|---|---|---|---|---|
| 1 | Verify reviewer identities and accounts: confirm whether the existing `platform_admin` and `knowledge_admin` accounts in any environment are real named humans | security: authority must belong to a real person | none | 2, 5, 6, 12 | DEFERRED |
| 2 | Appoint named human reviewers (A measurement, B alias, C release approver) and record their acceptance | security and governance | 1 | 5, 6 | DEFERRED |
| 3 | Complete the required two-person role changes for the appointments | security | 2 | 5, 6 | DEFERRED |
| 4 | Decide whether privileged reviewer endpoints are still needed and, if so, implement them behind `require_permission(KNOWLEDGE_APPROVE)` with step-up, audit and tests | security: a new privileged surface needs its own review | 2, 3 | 5, 6 | DEFERRED |
| 5 | Review and decide the 12 measurement batches (or reject any), using the packet and the digest-bound workflow | evidence reliability | 3, 4 | 9, 12 | DEFERRED |
| 6 | Review the five alias proposals individually (3 approve-recommended, 2 conditional) | evidence reliability, candidate impact | 3, 4 | 9, 12 | DEFERRED |
| 7 | Resolve the Data Analyst and Product Manager evidence gaps (approved occupational-title source, or candidate context plus an owner ambiguity policy) | evidence reliability; the 95% gate cannot be reached by Package 1 without it | owner policy or a new source approval | 11 | DEFERRED |
| 8 | Obtain legal review of commercial deployment of BLS content outside the US (RB-LIC-1) | legal exposure | none | 9, 12 | DEFERRED |
| 9 | Review persistent-registry authorisation and promote `us_soc_2018` and `bls_oews` through `SourceRegistry` only after 5, 6 and 8, with a backed-up persistent import | legal and governance | 5, 6, 8 | 12 | DEFERRED |
| 10 | Reassess product coverage after any of the above (the evaluator and its 412 cases stay as they are) | candidate impact | 5, 6, 7, 9 | 11 | DEFERRED |
| 11 | Satisfy the original 95% product gate (392 of 412) before any release that requires it: Package 1 alone reaches at most 391 | candidate impact; release gate | 10, plus Package 2, a projections/OOH package, or item 7 | any release needing the gate | DEFERRED; current status BELOW_GATE |
| 12 | Separate runtime authorisation and deployment review (Compensation V2 activation, candidate-visible evidence, contextual broader-group presentation, runtime source approval) | candidate impact and release | 5, 6, 8, 9, 11 | any candidate-facing V2 result | DEFERRED |

Other open obligations kept visible (not new): Package 2 (UK) and every other source package remain unapproved; the five BLS-specific aggregates stay quarantined pending a later policy review; D-16 and the remaining international owner decisions are open; P10C-G has its own entry conditions and was not started.
