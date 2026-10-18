# P10C-F1 — Global Source Licensing, Provenance & Approval Readiness (GKB-15)

**Status: PROPOSED ONLY.** No source is approved, no raw dataset was downloaded, no official data was ingested, Compensation V2 is not activated, and all 12 gates remain False. Evidence comes from official publisher pages read in this wave; every fact carries a verification status (`VERIFIED_OFFICIAL_PAGE`, `CORROBORATED_SECONDARY`, `NOT_VERIFIED`). **Public availability is not permission to reuse, and verification is not approval.** Machine-readable form: `docs/capstone/p10/p10c_f1/source_dossier.json`. Companion documents: [approval register](P10C_F1_SOURCE_APPROVAL_REGISTER.md) and [acquisition packages](P10C_F1_ACQUISITION_PACKAGES.md).

## 1. Consolidated inventory
The dossier holds 46 entries. It covers all **31** registry sources of `source_registry_baseline.json` (stable ids kept in `registry_ids`) and all **32** P10C-E register entries (`register_ids`); overlaps were reconciled, not deleted (for example `ons_ashe`/`reg:ons_ashe`; `esco`, `esco_matrix`, `esco_handbook` share one ESCO entry). 19 registry sources outside the priority groups appear as group H entries with licence NOT VERIFIED. `scripts/p10c_f1_dossier.py --check` enforces this coverage.

## 2. Licence-state vocabulary
Each licence records separately: statement found; corroborated against the publisher; terms clear; redistribution; commercial use; attribution; legal review needed; acquisition authorized; runtime authorized. The last two are False everywhere. "Clear" is only used where a publisher statement was read; summaries are not legal advice.

## 3. Findings by group
- **A. United States.** BLS content is public domain (citation requested, emblem restricted): clear. OEWS is May 2025 data, SOC 2018 (VERIFIED from the May 2025 technical notes; release date 15 May 2026). Wages are gross straight-time pay; annual values derive from a 2,080-hour year by the publisher. SOC 2018 structure: 867/459/98/23. O*NET 31.0 is CC BY 4.0 with required attribution and publishes O*NET-SOC 2019 to SOC 2018 and ESCO to O*NET-SOC crosswalks. **No official BLS SOC to ISCO-08 crosswalk was found.** *How the 1,386 V1 BLS records become occupation-linked V2 evidence:* after approval, re-read the national file with the OEWS adapter, import SOC 2018 nodes, link SOC to resolver identities through source-provided crosswalks only, then pass measurement qualification; nothing changes for candidates until runtime approval.
- **B. United Kingdom.** ASHE 2025 (released 23 Oct 2025) is provisional with a revised dataset expected Oct/Nov 2026; OGL v3.0 is clear. Edition: the bulletin states SOC 2020 coding from 2021; the QMI and Table 14 page keep legacy SOC 2010 wording: confirm from the table notes before import. The 19 Dec 2025 correction suppresses annual pay for occupations 3312, 331 and 33; those cells stay missing. Weekly pay stays weekly (no annualisation). The ONS publishes SOC 2020 to ISCO-08 information, but derived from a title-level coding index: it is partial/ambiguous, never an equivalence. The **527 V1 ASHE rows** become UK SOC-linked evidence after package 2; the **one row without an occupation code is not given an invented occupation** and is rejected.
- **C. Europe.** ESCO v1.2.1 (28 languages verified; Russian availability NOT VERIFIED): data licence not named on the pages read, third-party components with own licences → legal review. ISCO-08: ILO permission needed beyond short excerpts → legal review. Eurostat SES 2022 (clear: reuse with acknowledgement) publishes occupation only at ISCO-08 **1-digit**, so it can only support C3 at major-group level; a "Europe-wide occupation-level pay" claim is unsupported. German Entgeltatlas: no BA terms found (NOT VERIFIED); Destatis GENESIS: licence taken from a third-party catalogue (legal review), credentials required.
- **D. Canada.** OGL-Canada verified; NOC edition and wage datasets not confirmed; StatCan states a NOC-ISCO-08 concordance is planned but unpublished.
- **E. Mexico.** INEGI Libre Uso verified (commercial use, attribution, no metadata alteration). Household income is never compensation.
- **F. Brazil.** IBGE/CONCLA pages errored; everything NOT VERIFIED. Survey evidence is not administrative evidence.
- **Wider South America (AR, BO, CL, CO, EC, GY, PY, PE, SR, UY, VE).** Only Chile's licence was verified (CC BY-SA 4.0: ShareAlike → legal review). The others are NOT VERIFIED.
- **ILOSTAT.** CC BY 4.0 only for datasets released from 3 May 2023; site terms unread (403). C3 is **not** auto-assigned; **D-16 needs an explicit policy decision.**

## 4. Classification and precedence proposals
Proposals live in each entry's `proposal` block and use UNKNOWN wherever not defensible; C4 is abstain and is never a source class. BLS OEWS: C1/C2 by published group level; ASHE: C1 (4-digit) / C2 (broader); Eurostat SES: C3, major group only; ILOSTAT: UNKNOWN pending D-16. Precedence categories reuse the P10C-C policy vocabulary.

## 5. Occupation-graph artifact readiness
| Artifact | Official source | Ready to acquire? |
|---|---|---|
| US SOC 2018 nodes | BLS SOC pages | licence statement indirect (site-wide public domain) |
| UK SOC 2020 nodes | ONS (OGL) | yes, subject to D-03 |
| NOC nodes | StatCan | edition not confirmed |
| SINCO nodes, CBO nodes | INEGI, MTE/IBGE | not identified / not verified |
| ESCO multilingual aliases | ESCO download | legal review first |
| Official crosswalks | O*NET (SOC, ESCO); ONS (title-level ISCO) | O*NET yes; ONS partial only |
| ISCO-linked evidence | Eurostat SES | major group only |
No mapping may be built from title similarity.

## 6. Provenance, freshness, retention
Provenance record fields: publisher, dataset, edition, acquisition timestamp, source URL, licence evidence, raw-file SHA-256 (computed at acquisition; **none exists and none is claimed**), transformation version, taxonomy, reference period, qualification, import batch, attribution, runtime eligibility. Freshness fields: publication date, reference year, edition, acquisition date, last verification, supersession, review-due (owner-set; no invented deadlines; ASHE 2025 provisional flagged). Retention: raw files and hashes stay in owner-controlled storage outside the repository so imports are rebuildable deterministically; only licence-permitted derived rows may be committed.

## 7. CI evaluation fixtures
The 412-case product-coverage evaluator (386 sufficient, 26 insufficient, 93.7%, 95% gate) must keep using synthetic or licence-clear structural fixtures that are marked non-approvable; unapproved source contents are never placed in fixtures; the gate is not lowered.

## 8. Product-coverage traceability (26 cases)
13 **wiring** cases (compensation_187/199/203/195/207 US; 188/200/204/196/208 UK; education_083; future_growth_235; annual_openings_299) depend on packages 1 and 2 and the OOH/projections edition. 13 **ambiguity** cases (compensation_183/184/191/192; education_073/075/084; future_growth_215/223; short_term_outlook_247/255; annual_openings_279/287) stay insufficient without user context; ambiguity is not reclassified as success. Even after acquisition the score is not asserted to reach the gate.

## 9. Owner decision register
D-01..D-19 reconciled (`owner_decisions` in the dossier) as *blocks acquisition* or *deferrable to runtime activation*; three proposed additions: D-20 crosswalk gap policy, D-21 legal-review owner, D-22 ASHE weekly/edition confirmation. No decision is recorded as made.

## 10. Validation and protected stores
Run: `python scripts/p10c_f1_dossier.py --check`, `pytest tests/test_source_qualification_p10cf1.py`, ruff, `git diff --check`. No database, Redis, Chroma, corpus, cache, checkpoint or evaluation artifact was touched; no paid LLM or Stripe call was made.

## 11. P10C-F2 prerequisites (not started)
Owner decisions D-04, D-12, D-13 and the relevant per-package decisions; legal review for ESCO/ISCO/ShareAlike sources; confirmation of the OEWS data dictionary and of the ASHE 2025 table-notes SOC edition (the OEWS May 2025 classification is now verified as 2018 SOC); written approval of at least one package.

## 12. Owner decision appendix
See [P10C_F1_OWNER_DECISION_APPENDIX.md](P10C_F1_OWNER_DECISION_APPENDIX.md): exact wording and proposed answers for the acquisition-blocking decisions, legal-review list, Package 1 and 2 checklists, open edition questions and P10C-F2 boundaries.

## 13. Package 1 owner authorization
See [P10C_F1_PACKAGE_1_OWNER_AUTHORIZATION.md](P10C_F1_PACKAGE_1_OWNER_AUTHORIZATION.md). It verifies the OEWS May 2025 classification as 2018 SOC from the May 2025 technical notes, supersedes the earlier "May 2025 notes not read" caveats in this document and the appendix, and carries a blank owner sign-off.
