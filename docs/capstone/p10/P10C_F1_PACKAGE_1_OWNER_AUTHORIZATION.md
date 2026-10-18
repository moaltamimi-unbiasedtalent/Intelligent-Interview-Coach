# P10C-F1 Package 1 (United States) — Owner Authorization Readiness

**Overall state: OWNER_APPROVAL_PENDING.** Nothing in this document is an approval. No source, package or decision is APPROVED; no raw dataset was downloaded; Compensation V2 and all 12 product and billing gates are disabled. State vocabulary used below: **VERIFIED** (read on the publisher's official page in this wave), **RECOMMENDED** (my proposal), **LEGAL_REVIEW_REQUIRED**, **OWNER_APPROVAL_PENDING**, **BLOCKED**, **APPROVED** (appears only once an owner authorization is actually recorded in section M; currently none). Supporting data: `docs/capstone/p10/p10c_f1/source_dossier.json`; context: [dossier](P10C_F1_SOURCE_LICENSING_AND_APPROVAL.md), [packages](P10C_F1_ACQUISITION_PACKAGES.md), [appendix](P10C_F1_OWNER_DECISION_APPENDIX.md).

## A. Exact proposed acquisition scope — RECOMMENDED
| Component | Scope | State |
|---|---|---|
| 1a | 2018 SOC structure and definitions (two XLSX files) | RECOMMENDED, OWNER_APPROVAL_PENDING |
| 1b | BLS OEWS May 2025 **national** file (`oesm25nat.zip`) plus the May 2025 occupation-definitions XLSX | RECOMMENDED, OWNER_APPROVAL_PENDING |
| 1c (conditional) | O*NET 31.0 database files **only** for the O*NET-SOC 2019 to SOC 2018 and ESCO to O*NET-SOC crosswalks | RECOMMENDED only if D-20 adopts the O*NET/ESCO route; otherwise excluded |
| Excluded | BLS OOH and projections; OEWS state/metropolitan files; any SOC→ISCO-08 file (none official was found) | not in this package |

## B. Approved-source candidates (candidates only; none approved)
`us_soc_2018`, `us_bls_oews` (core); `us_onet_db` (conditional). Lifecycle states in the registry stay as they are (licensing pending / source identified); this document changes none.

## C. Dataset edition candidates — VERIFIED unless stated
- **OEWS May 2025**: news release for release Friday 15 May 2026 (`bls.gov/news.release/ocwage.nr0.htm`); file `oesm25nat.zip` listed on `bls.gov/oes/tables.htm`.
- **OEWS classification: 2018 SOC — VERIFIED** from "Technical Notes for May 2025 OEWS Estimates" (`bls.gov/oes/2025/may/oes_tec.htm`): estimates "based on the Office of Management and Budget's 2018 Standard Occupational Classification (SOC) system", about 830 categories in 22 of 23 major groups (military major group 55 excluded). The tables page and the news release do not themselves name an edition, and the fallback of using the May 2024 notes is **not needed** (the May 2025 notes were found at the official URL listed on `bls.gov/oes/oes_doc.htm`).
- **2018 SOC**: files `soc_structure_2018.xlsx` and `soc_2018_definitions.xlsx`; the SOC page says the 2018 revision is complete.
- **O*NET**: 31.0 (August 2026), the current and newest release per `onetcenter.org/db_releases.html`; the taxonomy version for 31.0 is not stated there (O*NET-SOC 2019 is the one introduced in 25.1; the crosswalk file name carries 2019): NOT VERIFIED for 31.0 itself.
- OEWS reference mechanics (VERIFIED, May 2025 notes): employment is the average of May 2025 and November 2024 QCEW data; 2022 NAICS; model-based MB3 method; the 1 Oct to 12 Nov 2025 funding lapse caused delay with no methodology change.

## D. Licensing evidence
- **BLS (OEWS and SOC) — VERIFIED**: copyright page and linking page state BLS publications are in the public domain except previously copyrighted photographs and illustrations; asks that users cite BLS as the source; "Unauthorized use of the BLS emblem is prohibited." The SOC page itself has no reuse statement; coverage of the SOC files rests on the site-wide statement hosted by BLS.
- **Commercial use: NOT ADDRESSED by the BLS page.** It follows from the public-domain statement for US use; use outside the United States is not assessed.
- **O*NET — VERIFIED**: CC BY 4.0 for the downloadable database files; other site content separately licensed.

## E. Legal-review requirements — LEGAL_REVIEW_REQUIRED
Core components: none mandatory for US use. Recommended confirmation (owner's decision whether to obtain it, D-21): that the site-wide BLS public-domain statement is accepted as covering the SOC structure files, and commercial use outside the United States. Conditional component 1c: confirm the O*NET attribution wording and that the ESCO→O*NET-SOC file does not carry ESCO third-party conditions. This is not legal advice.

## F. Attribution and redistribution terms
- BLS: public domain, redistribution permitted; cite BLS as source (requested, not a stated condition); never use the BLS emblem. Keep the publisher's own annual-from-hourly derivation (2,080 hours) labelled as BLS's, not ours.
- O*NET (if acquired): "This page includes information from the O*NET 31.0 Database; used under the CC BY 4.0 license; O*NET is a trademark of USDOL/ETA", link the licence, state any changes and that USDOL/ETA has not approved or endorsed the modified information.
- No raw file is redistributed from the repository without the owner's decision; derived rows only as the licence permits.

## G. Acquisition-blocking decisions: reconciliation (none recorded; proposals only)
| ID | Exact decision wording | Status | Proposed answer | Evidence | Packages | Legal review | Blocks Package 1? | Deferrable? | Recommended owner action |
|---|---|---|---|---|---|---|---|---|---|
| D-03 | Adopt UK SOC 2020 as first-class taxonomy and authorise its acquisition | OWNER_APPROVAL_PENDING | Approve | OGL v3.0 verified | 2 | no | **No** | for P1 yes | answer with Package 2 |
| D-04 | Per source, record licence verification and decide ingestion and runtime approval separately | OWNER_APPROVAL_PENDING | Approve ingestion for SOC 2018 and OEWS (and O*NET if 1c); runtime later | BLS copyright page; O*NET licence | all | optional (E) | **Yes** | no | decide ingestion per source |
| D-05 | Keep zero-padded four-character ISCO strings as identity (21 legacy rows) | OWNER_APPROVAL_PENDING | Approve | ISCO codes are identifiers | 3 | ISCO review | **No** | for P1 yes | answer with Package 3 |
| D-07 | Which ESCO language releases and non-English sources may be acquired | OWNER_APPROVAL_PENDING | English only | ESCO download page | 3 | ESCO | **No** | for P1 yes | answer with Package 3 |
| D-09 | Adopt the five-category relationship qualification for crosswalks | OWNER_APPROVAL_PENDING | Approve | prevents title-derived equivalence | 1c, 2, 3 | no | Only 1c | core yes | approve before any crosswalk import |
| D-12 | Select the official edition per source | OWNER_APPROVAL_PENDING | OEWS May 2025; 2018 SOC; (O*NET 31.0) | sections C | all | no | **Yes** | no | approve the three editions |
| D-13 | Authorise acquisition of named taxonomies and crosswalks | OWNER_APPROVAL_PENDING | Approve SOC 2018; 1c only if D-20 | SOC files | 1,2,5,6,7 | no | **Yes** (SOC) | no | approve named files only |
| D-15 | Adopt controlled vocabularies for earnings concept, population and method | OWNER_APPROVAL_PENDING | Approve for US/UK/Eurostat | P10C-D vocabularies | 4,5,6 and OEWS import | no | **Yes for OEWS import** (not SOC) | no for OEWS | approve before importing OEWS |
| D-16 | Precedence category for non-Eurostat international harmonised sources (ILOSTAT) | OWNER_APPROVAL_PENDING | Defer, no C3 | ILOSTAT terms unread | 7 | yes | No | yes | defer |
| D-18 | Region vocabularies for Paraguay/Peru and wider approval | OWNER_APPROVAL_PENDING | Defer | not researched | 7 | no | No | yes | defer |
| D-19 | Name the national occupation classification per wider South America market | OWNER_APPROVAL_PENDING | Defer | not verified | 7 | no | No | yes | defer |
| D-20 | Accept that no official SOC→ISCO-08 / NOC→ISCO-08 crosswalk exists; use O*NET/ESCO-linked routes only, or wait | OWNER_APPROVAL_PENDING | Approve O*NET/ESCO route | none found | 1c, 5 | no | Only 1c | core yes | choose route or wait |
| D-21 | Name who performs qualified legal review for ISCO-08, ESCO third-party components, ShareAlike sources | OWNER_APPROVAL_PENDING | Owner to name | see appendix | 3,7 | n/a | No (unless E is requested) | for P1 yes | name the reviewer |
| D-22 | ASHE weekly pay never annualised; SOC edition confirmed from table notes before import | OWNER_APPROVAL_PENDING | Approve | ASHE bulletin and table page | 2 | no | **No** | for P1 yes | answer with Package 2 |

D-01, D-02, D-06, D-08, D-10, D-11, D-14, D-17 remain deferrable to runtime activation. **Package 1 core is blocked only by D-04, D-12, D-13 and D-15.**

## H. Explicit remaining blockers — BLOCKED until resolved
1. No owner authorization recorded (D-04, D-12, D-13, D-15).
2. OEWS data dictionary / field layout (O_GROUP, statistic columns, suppression symbols, aggregation codes) not yet read: NOT VERIFIED.
3. Whether the May 2025 wage definition and 2,080-hour derivation are unchanged from the May 2024 notes: confirm in the May 2025 notes.
4. If 1c: O*NET-SOC taxonomy version of 31.0 and the semantics of the ESCO→O*NET-SOC file (D-09, D-20).
5. Owner decision on whether the optional legal confirmation in section E is wanted.

## I. Package-specific acceptance criteria
Raw file URL, SHA-256 and timestamp recorded; the file's own edition and reference period equal the section C values; every OEWS occupation code validates against 2018 SOC (aggregations flagged, not forced); no value is scaled, annualised or converted beyond BLS's own derivation; suppressed or missing cells remain missing; evidence class matches the dossier proposal (C1 detailed / C2 broader groups by published level); no title-similarity mapping; registry-gated production-mode importer only; synthetic fixtures untouched; all gates still False after import.

## J. Proposed authorization wording — RECOMMENDED (not in force)
"The owner authorises P10C-F2A to acquire, for ingestion only, (1) the BLS 2018 SOC structure and definitions XLSX files and (2) the BLS OEWS May 2025 national file `oesm25nat.zip` with the May 2025 occupation-definitions XLSX, by manual download from bls.gov by the owner or a named operator, with URL, timestamp and SHA-256 recorded. The owner adopts D-04 (ingestion only), D-12 (OEWS May 2025; 2018 SOC) and D-13 (these named files) and D-15 for the US earnings vocabulary. [Optional: and (3) O*NET 31.0 crosswalk files, if D-20 and D-09 are adopted.] This authorises no runtime use, no activation of Compensation V2, and no other source."

## K. Conditions for P10C-F2A
Signed section M; all of section H items 1–3 closed (4 if 1c); named operator; acquisition by manual download only (no scraping or bulk fetch); protected stores backed up and untouched; import limited to the registry-gated importer with a recorded import batch; stop and report on any deviation from section C or any licence change.

## L. Runtime activation restrictions
Acquisition for ingestion is not runtime approval. Runtime use needs a separate owner decision after measurement qualification by a named reviewer. Compensation V2, the internal resolver and all 12 gates stay off. Existing V1 candidate results and the 1,386 V1 BLS records are unchanged. P10C-G, RC-P10-004 and P11 are not authorised.

## M. Owner sign-off (BLANK — nothing is APPROVED until completed)
| Item | Decision (APPROVE / REJECT / DEFER) | Owner | Date |
|---|---|---|---|
| Component 1a SOC 2018 | | | |
| Component 1b OEWS May 2025 national | | | |
| Component 1c O*NET crosswalks | | | |
| D-04, D-12, D-13, D-15 | | | |
| D-09, D-20 (if 1c) | | | |
| Optional legal confirmation (E) | | | |

## Package 2 (United Kingdom) safety — unchanged and UNAPPROVED
- The ASHE correction dated 19 December 2025 suppresses annual pay estimates for occupations 3312, 331 and 33 (UK and some regions; Tables 2, 3, 14, 15, 20). Any future ingestion must keep those cells **missing**; they are never reconstructed or filled. Weekly pay stays weekly.
- SOC edition: the 2025 bulletin states occupation coding moved from SOC 2010 to SOC 2020 from 2021 and its occupation charts are "defined by SOC 2020" (VERIFIED). The Table 14 page keeps a legacy "soc2010" title/slug and does not state SOC 2020; the 2025 file is `ashetable142025provisional.zip`. The edition must be confirmed from the file's own notes before acquisition.
- Package 2 is OWNER_APPROVAL_PENDING and carries no authorization here.
