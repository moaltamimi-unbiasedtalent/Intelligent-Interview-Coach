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

## Owner reprioritisation of 2026-10-18: additional deferred scope
**Decision (sequencing only; not qualification, authorisation, legal clearance or production approval):** the remaining P10C-F work and P10F are deferred until after Capstone submission so the remaining Capstone engineering, integration, evaluation and submission milestones come first. **Reason:** prioritise those milestones. Nothing below is complete or waived.

| # | Deferred item | Depends on | Blocking issues kept visible |
|---|---|---|---|
| 13 | **P10C-F2B United Kingdom:** Package 2 authorization (D-03, D-22, D-04, D-12, D-13, D-15), acquisition of UK SOC 2020 Volume 1, ASHE Table 14 2025 provisional and the guide to tables, edition confirmation, isolated ingestion | owner authorization | Table 14 SOC edition and exact suppressed cells unverified; December 2025 correction; revised 2025 data due October or November 2026; preparation merged (PR #187) |
| 14 | **P10C-F2C ESCO/ISCO:** ESCO language releases (D-07), ISCO-08 reuse, padded-identity rule (D-05), relationship qualification (D-09) | owner authorization and legal review | ESCO data licence not named; ILO permission beyond short excerpts |
| 15 | **P10C-F2D Germany and EU:** Eurostat SES, Entgeltatlas, Destatis | owner authorization | Eurostat publishes occupation only at ISCO major group (C3 broad only); Entgeltatlas terms not found; Destatis licence from a third party |
| 16 | **P10C-F2E Canada, Mexico, Brazil:** NOC, Job Bank and StatCan, SINCO and INEGI, CBO and IBGE | owner authorization | no official NOC or SINCO crosswalk to ISCO-08; Brazil terms unread; household income is never compensation |
| 17 | **P10C-F2F wider South America and international evidence:** eleven markets and ILOSTAT | owner authorization, D-16, D-18, D-19 | Chile CC BY-SA ShareAlike review; most terms unverified; no auto-assigned C3 |
| 18 | Human measurement and alias reviews, reviewer appointments, persistent source authorisation, commercial licensing clearance, Compensation V2 runtime authorisation | items 1 to 12 above | RB-LIC-1 open; no reviewer exists; persistent registry unchanged |
| 19 | **P10F targeted human validation** | P10E | participants and protocol; AC-24 stays PARTIAL until its criteria, including P10F, are met |

**Preserved and unchanged:** F1 governance, F2A US engineering (isolated, 0 qualified, 0 runtime-approved), F2B preparation (nothing acquired), manifests and provenance, the occupation graph and V2 implementation, evidence-qualification reports, human-review packets and this backlog; every country package stays in the registry as unapproved. **Remaining risks:** coverage BELOW the 95% gate (386 of 412); unqualified evidence must never become candidate-facing; Capstone engineering acceptance is not production readiness. **Release restrictions:** any release requiring the 95% gate, human qualification, licensing clearance or P10F validation stays blocked until those are actually met. **Revised pre-submission order:** P10C-G, P10D, W12.4E, W12.4F, W12.5, P10E, Integrated Candidate/Admin/Operations Requalification, RC-P10-004, AC-24, P11. Automated regression, security, functional and integration testing and the Turing College expert-review and submission requirements are retained regardless of the P10F deferral.
