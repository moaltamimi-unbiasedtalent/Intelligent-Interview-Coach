# BL-9 traceability-only owner disposition

The Product Owner approved the following in the Ask4Mo conversation on **6 November 2026**, at day precision. The reviewed main was `1b0eb8d0b5f963718301ec518930c48149edcc9d` after PR #316.

> I approve Option B for traceability only. Keep BL-9 in R1.0, preserve all 153 obligations, dependencies and Candidate safeguards, and leave coverage decisions open. Run checks and open a draft PR only if guards pass. No merge or deploy.

This supplements the [earlier 00B owner disposition](00B_OWNER_DISPOSITION_2026_11_06.md). It records two distinct acceptance boundaries using the existing requirement identities. BL-9 remains `FIX BEFORE R1.0`. 00B and OD-RECLASS remain **PARTIAL / OPEN**. The allocation stays at **79 fixes and 74 verifications**, with **452 mapped requirements and zero unmapped**.

## Traceability crosswalk

| Existing identity | Acceptance boundary and evidence still required |
|---|---|
| 02D / REQ-COV-02 | R1.0 Candidate source safety. Preserve source and market approval, wrong-market and unknown-market refusal, and the exclusion of unsupported or unlicensed factual evidence. Every enabled market still needs signed source qualification. |
| BL-8 / RB-LIC-1 | R1.0 commercial BLS licensing review for applicable markets. Written evidence from a qualified reviewer remains required. The existing licence, use-scope and attribution controls apply. |
| OD-US-CONTENT | R1.0 policy decision remains open. The owner must decide between clearly labelled non-EU general information and excluding US sources from Candidate retrieval in the beta. The standing prohibition on unqualified US factual evidence for EU labour markets remains in force. |
| REQ-OWN-05 | R1.0 persistent Knowledge Sources acceptance, including provenance, integrity and recovery. Its acceptance evidence remains independently required. |
| BL-9 | V2 audited persistent-registry promotion of `us_soc_2018` and `bls_oews`. The retained R1.0 obligation is open and requires BL-5, BL-6 and BL-8, followed by separately authorized, backed-up persistent import. |
| BL-12 | R1.6 runtime approval and deployment review. Retains BL-5, BL-6, BL-8, BL-9 and BL-11 as prerequisites and requires separate authorization for Candidate-visible V2 use. |

The authenticated synthetic Candidate catalogue evidence shows legacy BLS and O*NET metadata. Factual evidence and citations remain governed by the source-market approval filter, whose committed [approval register](source_approval_register.json) is empty. V2 stays inaccessible through the Candidate API and UI. [02D qualification and licence criteria](02D_LICENSING_REVIEW_PACK.md) · [Candidate scope and catalogue regressions](../../../tests/test_r1_scope_exclusions.py)

## Retained scheduling and coverage questions

- BL-5 remains in R1.6 with its 12 digest-bound measurement decisions. BL-6 and its five individual alias rows remain in R1.5. BL-6.6 and BL-7 remain in R1.0. BL-9 stays blocked on its existing prerequisites and has no R1.5 promotion milestone.
- BL-10 and B-COV-REMEAS keep their proposed R1.1 placements and existing prerequisites. BL-11 remains in R1.0 with its BL-10 and additional evidence-path requirements. BL-18 remains in R1.0 with its historical items 1–12 umbrella. The applicability and ordering of these records remain open.
- The historical coverage result remains **386/412, FAIL**, against **392/412** required. OD-COVERAGE and approval of the separate frozen R1.0 beta-scope measure remain open. No release placement, dependency, closure evidence, source approval or gate is amended by this record.

[Reconciliation and retained dependencies](../PRODUCTION_ISSUE_RECONCILIATION.json) · [Original promotion and coverage requirements](../../capstone/p10/P10C_F2A_POST_SUBMISSION_BACKLOG.md) · [Owner requirements and coverage separation](../OWNER_REQUIREMENTS_SOURCE_OF_TRUTH_V2_2.md)
