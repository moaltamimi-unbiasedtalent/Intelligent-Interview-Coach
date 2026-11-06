# 00B owner disposition and reconciliation audit

**Written disposition received 2026-11-06.** The source is the Product Owner’s message authorizing this 00B reconciliation in the Ask4Mo conversation. The approved baseline was `0e8d686f5fc8d71e46bcf2090cd527d4a65e4cd3` after PR #315. The date is recorded at day precision. This record is the evidence reference for each item below.

> I approve BL-5 and BL-12 for R1.6, BL-6 and BL-6.1–BL-6.5 for R1.5, and W12.4E-12 for R1.4. Defer BL-9. Keep BL-6.6 and BL-7 in R1.0. Preserve dependencies, run checks and open a draft PR. No merge, deploy or gate changes.

## Recorded decisions

All ten proposals started as `FIX BEFORE R1.0`. An approved placement changes only the current disposition to `DEFER TO NAMED RELEASE`, its release and the placement evidence fields. Every issue ID, dependency, original register row, historical status and closure record is preserved. The five alias decisions are explicit members of the owner’s BL-6.1 through BL-6.5 range.

| ID | Written decision | Resulting placement | Preserved dependency and scope |
|---|---|---|---|
| BL-5 | APPROVE | R1.6 | BL-3 and BL-4 remain prerequisites. The 12 measurement reviews remain prerequisites for BL-9 and BL-12. |
| BL-6 | APPROVE | R1.5 | BL-3 and BL-4 remain prerequisites. Individual alias decisions and dependencies into BL-9 and BL-12 remain. |
| BL-6.1 | APPROVE | R1.5 | Software Developer to SOC 15-1252. BL-6 and separate human alias review remain. |
| BL-6.2 | APPROVE | R1.5 | Human Resources Manager to SOC 11-3121. BL-6 and separate human alias review remain. |
| BL-6.3 | APPROVE | R1.5 | Sales Manager to SOC 11-2022. BL-6 and separate human alias review remain. |
| BL-6.4 | APPROVE | R1.5 | Accountant to SOC 13-2011. BL-6, separate human review and the combined Accountants and Auditors caveat remain. |
| BL-6.5 | APPROVE | R1.5 | Financial Analyst to SOC 13-2051. BL-6, separate human review, the scope caveat and context decision remain. |
| BL-9 | DEFER | FIX BEFORE R1.0 | Reclassification deferred. BL-5, BL-6 and BL-8 remain prerequisites. Persistent promotion is held without an R1.5 milestone or a new target release. |
| BL-12 | APPROVE | R1.6 | BL-5, BL-6, BL-8, BL-9 and BL-11 remain prerequisites. Runtime and deployment authorization requires its own owner decision. |
| W12.4E-12 | APPROVE | R1.4 | Server-side browser recording retains item 3 and 6 prerequisites. Browser-native speech remains within its existing controls. |

BL-6.6 and BL-7 remain `FIX BEFORE R1.0` in 02E. Their title-resolution and abstention behavior is enabled and the historical ambiguity finding remains on record.

## BL-9 boundary and sequence

The isolated current Candidate API returned HTTP 200 for `/api/v1/knowledge/sources` with legacy BLS OEWS, BLS OOH and O*NET metadata. The Candidate Sources UI displays returned cards. `us_soc_2018` was absent in that probe. The V2 audited persistent-registry promotion has no Candidate path. Current fixture evidence covers scoped legacy and hosted-policy behavior. Hosted staging and real-user market qualification are separate. [Catalog API](../../../src/api/routes/knowledge.py) · [Candidate Sources UI](../../../frontend/components/preparation/SourcesClient.tsx) · [02D source tests](../../../tests/test_source_approval_02d.py)

BL-9 stays a retained R1.0 issue, with its historical promotion work open. The owner deferred the move to R1.5, which removes the proposed R1.5 milestone for this promotion. R1.5 alias review and separately qualified sources can be considered on their own prerequisites. The held US promotion and its dependent coverage claims are outside R1.5 acceptance. Any future BL-9 execution still needs completed BL-5 measurements, BL-6 alias decisions and BL-8 licensing evidence, followed by separately authorized audited persistent import. BL-12 retains separate runtime approval and depends on that work. A formal change to those dependencies would require a new explicit owner decision. This sequencing record does not supply BL-9 closure or a release waiver.

02D, BL-8/RB-LIC-1 and OD-US-CONTENT remain independently required for R1.0. The existing source catalogue, retrieval controls and Candidate behavior are preserved. The R1.6 dependency on independently qualified R1.5 sources is retained.

## Before and after

| Measure | Before | After | Delta |
|---|---:|---:|---:|
| Mapped / unmapped | 452 / 0 | 452 / 0 | 0 / 0 |
| Historical / new / cross-check | 394 / 58 / 168 | 394 / 58 / 168 | 0 / 0 / 0 |
| R1.0 fix | 88 | 79 | −9 |
| R1.0 verify | 74 | 74 | 0 |
| R1.0 fix and verify | 162 | 153 | −9 |
| R1.0 total including 35 owner-decision rows | 197 | 188 | −9 |
| Later-release deferred | 143 | 152 | +9 |
| Owner-decision / closed with evidence | 95 / 52 | 95 / 52 | 0 / 0 |
| R1.4 rows | 23 | 24 | +1 |
| R1.5 rows | 7 | 13 | +6 |
| R1.6 rows | 2 | 4 | +2 |

R1.1, R1.2, R1.3, R1.7, R2.0, unscheduled and historical closed counts keep their prior values. The original ten-move arithmetic is historical. 00B retains BL-9 as its sole R1.0 package assignment, and OD-RECLASS stays open for that held item. The full S1 product scope and agreed release train are retained. [Traceability](../MASTER_REQUIREMENTS_TRACEABILITY.md) · [Generated count report](../RELEASE_BLOCKER_DASHBOARD.md)

## Verification boundary

The reviewed main passed all seven required push workflows on attempt 1. The PR #315 feature tree equals that merge tree. Its [primary browser evidence](https://github.com/moaltamimi-unbiasedtalent/Intelligent-Interview-Coach/actions/runs/42184651938/job/127782008480) includes the Candidate no-gated-endpoint checks with gate-off fixtures. Fresh scoped real FastAPI, frontend and licence-boundary tests are reported separately in the PR verification. The server recording endpoints retain their refusal contract. R1.0 scope exclusions and every pre-existing safety assertion remain required.

Run `python scripts/production/reconcile_issues.py generate-scope` to regenerate the reconciliation, traceability and blocker dashboard while preserving hand-maintained owner history and gate records. Use the existing package, wave matrix and release evidence generators for their affected views. `check` validates the source records and freshness.

R1.0 engineering stays 40/45. 00A, 07B and 07C remain open or incomplete. 08A remains blocked. PG-04 OPEN, 0/98 language approvals and full-S1 launch NO-GO.
