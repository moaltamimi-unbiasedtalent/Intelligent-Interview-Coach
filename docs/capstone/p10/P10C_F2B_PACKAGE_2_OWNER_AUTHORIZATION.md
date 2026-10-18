# P10C-F2B Package 2 (United Kingdom) — Owner Authorization Request

**Overall state: APPROVAL_PENDING. Nothing in this document is an approval.** The Package 1 authorization does not extend to Package 2; no UK raw file was downloaded; D-03 and D-22 are unanswered; no source was approved or promoted; Compensation V2 and all 12 gates are disabled. State vocabulary: **VERIFIED** (read on an official page on 2026-10-18), **RECOMMENDED** (my proposal), **APPROVAL_PENDING**, **APPROVED** (appears only once an owner authorization is recorded in section M; none today), **BLOCKED**, **LEGAL_REVIEW_REQUIRED** (none identified for OGL content). Companion records: `docs/capstone/p10/p10c_f2b/acquisition_manifest.json`, `source_verification.json`, `ashe_suppression_rules` (under `src/knowledge_foundation/data/`), `uk_v1_baseline.json`; documents [source acquisition](P10C_F2B_UK_SOURCE_ACQUISITION.md), [UK occupation graph](P10C_F2B_UK_OCCUPATION_GRAPH.md), [ASHE compensation qualification](P10C_F2B_ASHE_COMPENSATION_QUALIFICATION.md).

## A. Exact proposed acquisition scope — RECOMMENDED, APPROVAL_PENDING
| Component | File | Why | Reported size |
|---|---|---|---|
| 2a | `soc2020volume1structureanddescriptionofunitgroupsexcel20260827.xlsx` (UK SOC 2020 Volume 1 structure and unit-group descriptions) | the official taxonomy: codes, labels, hierarchy, definitions | 289.1 kB |
| 2b | `ashetable142025provisional.zip` (ASHE Table 14, occupation by four-digit SOC, 2025 provisional) | the compensation evidence | not stated |
| 2c | `ashetableguide.xls` (ASHE guide to tables) | the official table and field documentation | 41.5 kB |
**Excluded:** the 2024 revised Table 14, Tables 2, 3, 15 and 20, any regional or other ASHE table, the SOC 2020 coding index (Volume 2) and NS-SEC (Volume 3), the SOC 2020 to ISCO-08 mapping, ESCO, ISCO-08, O*NET, ILOSTAT, OEWS regional files, commercial recruitment data and any other UK dataset.

## B. Approved-source candidates (candidates only)
`uk_soc_2020` (taxonomy) and `ons_ashe` (compensation). Lifecycle states in the persistent registry stay as they are; nothing is registered or promoted here.

## C. Dataset edition candidates
- **UK SOC 2020: VERIFIED** (ONS page: 9 major, 26 sub-major, 104 minor, 412 unit groups). The Excel file name carries `20260827` while the page says "Last updated: 5 May 2026": which file version is current is **NOT VERIFIED** until the file is read.
- **ASHE Table 14, 2025 provisional: VERIFIED** (released 23 October 2025; next release to be announced). Revised 2025 data is expected October or November 2026 (ONS statement): the owner decides whether to acquire the provisional edition now or wait (D-12).
- **Occupation classification edition of the Table 14 file: NOT VERIFIED.** The page and URL say soc2010; the 2025 bulletin says ONS moved to SOC 2020 from 2021; the 2018 QMI says SOC 2010 (dated). It must be established from the file's own notes before any ingestion; it is **not** forced to SOC 2020. Structural hint only (an inference): the V1 UK rows hold 26 two-digit codes, equal to the SOC 2020 sub-major count (SOC 2010 had 25).

## D. Licensing evidence
**VERIFIED:** ONS dataset and SOC pages state "All content is available under the Open Government Licence v3.0, except where otherwise stated"; the ONS terms page names third-party photographs, illustrations and videos as outside the OGL. OGL v3.0 (licence terms, read in an earlier wave) permits commercial and non-commercial use, redistribution and adaptation with attribution. The ONS pages themselves do not address commercial use or territory.

## E. Legal-review requirements
None identified for the OGL-licensed ONS statistics and classification. Commercial use outside the UK is the same open question as RB-LIC-1 and is not decided here. This is not legal advice.

## F. Attribution and redistribution terms
Attribution statement (OGL default): "Contains public sector information licensed under the Open Government Licence v3.0."; the bulletin suggests the citation "Office for National Statistics (ONS), released 23 October 2025, ONS website, statistical bulletin, Employee earnings in the UK: 2025". Redistribution permitted under the OGL with attribution; the OGL excludes personal data, third-party rights and logos and ends on breach of the attribution condition. No raw file is committed to the repository.

## G. Applicable owner decisions (none recorded)
| ID | Exact wording | Proposed | Rationale |
|---|---|---|---|
| D-03 | Adopt UK SOC 2020 as a first-class national occupational taxonomy and authorise its acquisition. | APPROVE | OGL verified; official structure verified (9/26/104/412); needed for any UK evidence |
| D-22 | ASHE weekly pay stays weekly and is never annualised, and the SOC edition of the Table 14 file is confirmed from the acquired file's own documentation before ingestion. | APPROVE | source-defined concept; the edition cannot be inferred from a page title |
| D-04 | Per source: record the licence verification and approve acquisition and isolated non-production ingestion (not runtime use). | APPROVE ingestion for `uk_soc_2020` and `ons_ashe` | OGL read on official pages |
| D-12 | Select editions: UK SOC 2020 (the Volume 1 Excel as read), ASHE 2025 provisional (replace with the revised edition when published, by a later decision). | APPROVE, conditional on the edition check | matches the pages read |
| D-13 | Authorise acquisition of the named UK taxonomy file. | APPROVE (component 2a only) | official, single file |
| D-15 | Apply the controlled earnings, population, method and evidence-method vocabularies to ASHE (UK weekly gross, full-time employees, survey). | APPROVE | needed to import compensation |
| D-09, D-20 | Cross-taxonomy relationship qualification and SOC-to-ISCO mapping. | keep DEFERRED | excluded from Package 2 |

## H. Explicit remaining blockers (BLOCKED until resolved)
1. Owner authorization of Package 2 and decisions D-03, D-22, D-04, D-12, D-13, D-15 (none recorded).
2. The ASHE guide to tables and the Table 14 file's own notes have not been read: sheet layout, measures, symbols, full-time and part-time scope, coefficient-of-variation coding, SOC edition (NOT VERIFIED).
3. The exact suppressed cells of the 19 December 2025 correction (the notice itself is VERIFIED; cells are not).
4. Which UK SOC 2020 file version is current.
5. Registry lifecycle for the UK sources (needs 1 first).

## I. Package-specific acceptance criteria
Raw file URL, SHA-256, size and timestamp recorded; the file's own edition and reference period match section C; classification edition confirmed from file documentation; every ASHE occupation code validates against the acquired UK SOC 2020 structure (a code outside it is rejected, never forced); weekly pay stays weekly, no annualisation, no GBP conversion; suppressed and not-available cells stay missing (the machine-readable record covers codes 33, 331, 3312 for annual pay in UK, London, South East and East; regression tests fail if a value is restored); provisional status and the correction are recorded; full-time and part-time populations stay separate; evidence class from the actual code length (C1 four-digit, C2 broader); production-mode registry-gated import into an isolated database only; idempotent re-import; V1 untouched; all 12 gates False.

## J. Proposed authorization wording — RECOMMENDED (not in force)
"The owner authorises the P10C-F2B continuation to acquire, for isolated non-production ingestion only, (1) the ONS UK SOC 2020 Volume 1 structure Excel file, (2) the ONS ASHE Table 14 2025 provisional archive `ashetable142025provisional.zip` and (3) the ONS ASHE guide to tables `ashetableguide.xls`, by manual download from ons.gov.uk by a named operator with URL, timestamp and SHA-256 recorded. The owner adopts D-03, D-22, D-04 (ingestion only), D-12 (UK SOC 2020; ASHE 2025 provisional), D-13 (component 2a) and D-15 for the UK earnings vocabulary. This authorises no runtime use, no human qualification, no activation of Compensation V2 and no other source."

## K. Conditions for the acquisition step
Section M signed; sections H items 1, 2 and 4 closed (2 may be closed by reading the files once authorised: reading is part of the step, ingestion stays stopped until it is done); named operator; manual single-file downloads only; protected stores untouched; import limited to the registry-gated importer in an isolated database; stop and report on any edition, licence or layout deviation.

## L. Runtime activation restrictions
Acquisition and engineering checks are not qualification and not runtime approval. Human measurement and alias qualification remain deferred until after the capstone submission (owner decision). Compensation V2, UK compensation runtime and all 12 gates stay off; existing V1 UK results are unchanged; the 95% coverage gate is not weakened.

## M. Owner sign-off (BLANK — nothing is APPROVED until completed)
| Item | Decision (APPROVE / REJECT / DEFER) | Owner | Date |
|---|---|---|---|
| Component 2a UK SOC 2020 Volume 1 structure | | | |
| Component 2b ASHE Table 14 2025 provisional | | | |
| Component 2c ASHE guide to tables | | | |
| D-03, D-22 | | | |
| D-04, D-12, D-13, D-15 | | | |
