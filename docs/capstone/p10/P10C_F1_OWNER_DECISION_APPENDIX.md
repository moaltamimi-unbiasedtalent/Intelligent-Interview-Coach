# P10C-F1 Owner Decision Appendix

**Status: PROPOSALS ONLY.** Every "proposed" answer below is a recommendation for the owner. **No decision is recorded, no source or package is approved, nothing was acquired, and Compensation V2 stays disabled.** The dossier keeps `owner_decision: null` for every decision. Companion documents: [dossier](P10C_F1_SOURCE_LICENSING_AND_APPROVAL.md), [register](P10C_F1_SOURCE_APPROVAL_REGISTER.md), [packages](P10C_F1_ACQUISITION_PACKAGES.md).

Re-verification on 18 Oct 2026 (official pages): BLS states publications are public domain, asks for citation, prohibits unauthorised use of the BLS emblem, and does **not** address commercial use. **Update:** the May 2025 technical notes now confirm 2018 SOC and the news release date is 15 May 2026 (see the Package 1 document). The OEWS tables page offers `oesm25nat.zip` (May 2025) but states **no release date** and **no SOC edition** (a "last modified 15 May 2026" is a page date, not a release date; an earlier wording of the dossier was corrected). The ONS Table 14 page states OGL v3.0, the 2025 provisional edition released 23 Oct 2025, next release "to be announced", a 19 Dec 2025 correction suppressing annual pay for occupations 3312/331/33 (revised dataset expected Oct/Nov 2026), and gives no SOC edition (its dataset name says SOC 2010).

## 1-2. Acquisition-blocking decisions: exact wording and proposed answer
| ID | Exact decision wording | Proposed | Rationale |
|---|---|---|---|
| D-03 | Adopt UK SOC 2020 as a first-class occupation taxonomy and authorise its acquisition. | Approve | OGL v3.0 verified; ASHE bulletin is SOC 2020; needed for package 2. |
| D-04 | For each source individually, record the licence verification outcome and decide separately (a) approval for ingestion and (b) approval for runtime use. | Approve ingestion for BLS OEWS, SOC 2018, O*NET, ONS ASHE, UK SOC 2020 only; reject nothing yet; defer all others | Only these have a publisher statement read; runtime approval waits for qualification. |
| D-05 | Decide the identity rule for zero-padded ISCO codes (21 legacy rows): keep the padded four-character string as the identity. | Approve padded string identity | Codes like 0110 are identifiers, not numbers. |
| D-07 | Decide which ESCO language releases (and non-English sources) may be acquired. | Approve English only, defer other languages | Keeps package 3 small; Russian availability is unverified. |
| D-09 | Adopt the five-category relationship qualification for crosswalks. | Approve | Prevents title-derived equivalence. |
| D-12 | Select the official edition per source: OEWS May 2025; SOC 2018; O*NET 31.0 (O*NET-SOC 2019); ASHE 2025 (replace with the revised edition when published); UK SOC 2020; ESCO v1.2.1. | Approve for these, conditional on the remaining edition checks in section 6 (OEWS SOC 2018 is now verified) | Matches the local files and official pages. |
| D-13 | Authorise acquisition of named taxonomies and crosswalks: SOC 2018, UK SOC 2020, O*NET-SOC 2019→SOC 2018, ESCO→O*NET-SOC. | Approve for these four; reject any title-similarity crosswalk | Official, source-provided mappings only. |
| D-15 | Adopt controlled vocabularies for earnings concept, population and method. | Approve for US/UK/Eurostat; defer others | Needed before non-US/UK compensation sources. |
| D-16 | Decide the precedence category for non-Eurostat international harmonised sources (ILOSTAT). | Defer (no C3 assignment) | Terms unread and policy open. |
| D-18 | Approve region vocabularies for Paraguay and Peru and the wider South America set. | Defer | Package 7 not yet researched enough. |
| D-19 | Name the national occupation classification per wider South America market. | Defer | Not verified from official pages. |
| D-20 | Accept that no official SOC→ISCO-08 or NOC→ISCO-08 crosswalk exists; use O*NET/ESCO-linked routes only, or wait. | Approve the O*NET/ESCO route; no invented crosswalk | None found. |
| D-21 | Name who performs qualified legal review for ISCO-08, ESCO third-party components and ShareAlike sources. | Owner to name | Required before packages 3 and 7. |
| D-22 | Confirm ASHE weekly pay is never annualised and the SOC edition is confirmed from the table's notes before import. | Approve | Source-defined concept. |

## 3. Outstanding legal-review requirements
ESCO (data licence not named; third-party components); ISCO-08 (ILO permission beyond short excerpts); Chile INE (CC BY-SA ShareAlike); Destatis GENESIS (licence from a third-party catalogue); German Entgeltatlas (no terms found); ILOSTAT (site terms unread; CC BY only from 2023); Canadian wage datasets, Brazil, and ten other South American markets (terms not verified). BLS commercial use outside the United States is also unaddressed on the BLS page. None of this is legal advice.

## 4. Package 1 readiness checklist (US: SOC 2018 + OEWS + mappings)
- [ ] D-04, D-12, D-13, D-20 answered by the owner in writing
- [x] OEWS May 2025 release date (15 May 2026) and SOC 2018 edition confirmed from the news release and May 2025 technical notes (see the Package 1 document)
- [ ] OEWS data dictionary read (O_GROUP, statistic columns, suppression symbols)
- [ ] BLS SOC structure/definitions file URLs recorded; confirm the BLS copyright page is accepted as covering them
- [ ] O*NET 31.0 attribution text and the two crosswalk files' mapping semantics read after download
- [ ] Citation of BLS and O*NET attribution decided; no BLS emblem use
- [ ] Download by owner/approved operator only; SHA-256, URL and timestamp recorded
- [ ] Production-mode registry-gated import; qualification tests pass; nothing runtime-enabled

## 5. Package 2 readiness checklist (UK: SOC 2020 + ASHE + mappings)
- [ ] D-03, D-04, D-12, D-13, D-22 answered in writing
- [ ] SOC edition of Table 14.1a confirmed from the file's own notes (page says SOC 2010, bulletin says SOC 2020)
- [ ] Decide provisional 2025 now versus waiting for the revised Oct/Nov 2026 release; the next-release date is "to be announced"
- [ ] Suppressed 3312/331/33 annual estimates preserved as missing
- [ ] The one row without an occupation code rejected, never assigned
- [ ] Weekly pay kept weekly; OGL attribution statement adopted
- [ ] UK SOC 2020 volume 1 and coding index acquired; ISCO-08 relationships only as partial/ambiguous
- [ ] SHA-256/URL/timestamp recorded; qualification tests pass

## 6. Unresolved licensing and edition questions
OEWS data dictionary; whether the BLS public-domain page covers SOC and OOH files; commercial use of BLS content outside the US; ASHE Table 14 SOC edition and provisional/revised choice; O*NET newest release and ESCO→O*NET-SOC file version; ESCO data licence and language list; ISCO-08 reuse terms; all licences marked NOT VERIFIED in the register.

## 7. P10C-F2 authorization boundaries
F2 may begin only after written owner approval of a named package. When authorised it may: record the owner-approved decisions, acquire only the files named in that package by the owner or an approved operator, hash and register them, and import them through the registry-gated production importer. It may **not**: acquire any unapproved package or source; scrape or bulk-download; approve runtime use; activate Compensation V2 or any gate; alter existing candidate results; build title-similarity mappings; start P10C-G, RC-P10-004 or P11; or merge automatically.
