# P10C-F2A — Capstone Engineering Closure and Owner Acceptance

**Milestone classification (documentation level only): `P10C-F2A_CAPSTONE_ENGINEERING_ACCEPTED — HUMAN_QUALIFICATION_DEFERRED`.** No database enum or registry state was created or changed for this classification. Recorded 2026-10-18 on the basis of the product owner's explicit instruction (no signature or external legal approval is claimed).

## 1. What is accepted, and what is not
Accepted: the engineering pipeline for US source acquisition, SOC 2018 graph population, OEWS May 2025 ingestion into an isolated database, provenance, idempotency, quarantine of the five BLS-specific aggregates, measurement preservation, V1 compatibility, engineering qualification checks and source-governance boundaries.

**Not accepted, and not to be described as:** production ready; operational compensation qualified; commercially authorised; candidate-runtime approved; globally qualified; 95%-coverage compliant. Accepting the milestone is not approval of operational compensation evidence and does not bypass security, licensing or evidence governance.

## 2. Verification performed for this closure (2026-10-18)
| Item | Reported baseline | This run | How |
|---|---|---|---|
| SOC 2018 nodes / hierarchy relationships | 1,447 / 1,424 | **1,447 / 1,424** | fresh SQL on the isolated database |
| OEWS source rows / quarantined aggregates | 1,401 / 5 | **1,401 / 5** | fresh read-only dry-run of the qualification script against the staged file |
| Canonical occupations | 1,388 | **1,388** | fresh SQL (distinct occupation ids) |
| CompensationRecordV2 | 16,140 | **16,140** (C1 9,450, C2 6,690) | fresh SQL |
| Engineering-checked / qualified / runtime-approved | 16,140 / 0 / 0 | **16,140 / 0 / 0** | fresh SQL; no source is `approved_for_runtime_use` |
| Aliases proposed / qualified | 5 / 0 | **5 / 0** (all engineering_checked) | fresh SQL |
| V1 records / reconcilable / incompatible | 1,386 / 1,381 / 5 | **1,386 / 1,381 / 5**; V1 file unchanged | fresh read-only recount |
| Source files | 4 hashes | **4 of 4 match the manifest** | `--verify-hashes` |
| Source registry (isolated database) | approved_for_ingestion x2 | **approved_for_ingestion x2** | fresh SQL |
| Alembic head | 0038 | **0038_compensation_concepts** (single head, no migration added) | fresh |
| Measurement review batches | 12 | 12 | previous result from the committed packet, **NOT RE-RUN** (digests not recomputed) |
Everything marked fresh was re-queried in this run; the one NOT RE-RUN item is stated as such.

## 3. State separation (never combined)
| State | Status |
|---|---|
| Source acquired | yes (4 official BLS files, hashes recorded) |
| Source ingested | yes, isolated non-production database only |
| Engineering checked | yes: 16,140 records, 5 aliases |
| Human qualified | **no: 0 records, 0 aliases, 0 sources** |
| Runtime approved | **no: 0** |
| Production activated | **no** (Compensation V2 disabled, all 12 gates False) |
The persistent developer registry and every protected store are unchanged. All 16,140 records remain unqualified until the reviewer workflow completes.

## 4. Owner deferrals (post-submission)
Named measurement and alias reviewers and their appointment and acceptance; the 12 measurement batch decisions; the five alias decisions; human qualification audit records; privileged reviewer endpoints; persistent source-registry promotion; commercial runtime licensing clearance (RB-LIC-1); Compensation V2 activation. Review packets and procedures are retained ([human review package](P10C_F2A_HUMAN_REVIEW_AND_APPROVAL.md)); no reviewer identity or decision was fabricated; nothing is transitioned automatically.

## 5. Aliases and compensation safety
Software Developer to 15-1252, Human Resources Manager to 11-3121, Sales Manager to 11-2022, Accountant to 13-2011 and Financial Analyst to 13-2051 remain proposals (engineering_checked, unqualified, none approved). Data Analyst and Product Manager remain unresolved: no mapping, abstention preserved. When an exact occupation lacks the requested measure the resolver abstains; a broader group's statistic appears only as separately labelled contextual evidence with a non-equivalence warning. Candidate compensation behaviour is unchanged.

## 6. Product coverage
Observed capstone engineering baseline: **386 of 412 = 93.7%** (the evaluator measures wider product coverage; it is not a US-only metric). Current status **BELOW_GATE** against the unchanged 95% threshold (392 required). Owner disposition: **ACCEPTED_FOR_CAPSTONE_ENGINEERING_SCOPE**. Deferred remediation: **POST_SUBMISSION**. The gate was not marked PASS; the 412 cases, expectations and failure reporting were not changed; no case was fabricated.

## 7. Licensing
RB-LIC-1 remains open: commercial use of BLS content outside the US is unresolved and no legal clearance is implied. Candidate-facing V2 results remain unauthorised.

## 8. Post-submission backlog and exit criteria
Prioritised backlog: [P10C_F2A_POST_SUBMISSION_BACKLOG.md](P10C_F2A_POST_SUBMISSION_BACKLOG.md). Exit criteria for this closure: deliverables documented (yes); acquisition provenance preserved (yes); counts reconcile (yes); engineering results reproducible (yes); no record falsely human-qualified (yes, 0); no alias falsely approved (yes, 0); no source promoted (yes); regression tests pass (see the final report); coverage correctly reported (yes, BELOW_GATE); 95% gate not weakened (yes); deferral documented (yes); licensing explicit (yes); runtime disabled (yes); protected stores safe (yes); backlog exists (yes); roadmap updated (yes); PR #186 updated (on push).

## 9. Roadmap dependencies
P10C-F remains a parent workstream with open obligations (Package 2 and other sources, D-16 and further owner decisions, the deferred items above). P10C-G may start only when its own entry conditions are met; none is assumed satisfied by this closure.
