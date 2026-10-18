# P10C-F2A — US Official Source Acquisition (Package 1)

**Status: P10C-F2A PREPARATION COMPLETE — ACQUISITION BLOCKED — REMAINING GOVERNANCE OR SOURCE EVIDENCE REQUIRED.** No file was downloaded, nothing was ingested, no source is qualified, Compensation V2 is not activated and all 12 gates are False.

## 1. Owner authorization (recorded, not self-granted)
Recorded 2026-10-18 from the explicit owner instruction in the P10C-F2A specification; see section M of [the Package 1 authorization](P10C_F1_PACKAGE_1_OWNER_AUTHORIZATION.md) and `owner_decisions` in `p10c_f1/source_dossier.json`. D-04, D-12, D-13, D-15 APPROVED (acquisition and isolated non-production ingestion only; US SOC 2018 and OEWS May 2025; the four named files); D-09, D-20 and Component 1c DEFERRED. No signature or external legal approval is claimed. The source registry lifecycle was **not** advanced: that transition remains the registry's own mechanism and is performed only when acquisition proceeds. Nothing here grants runtime use.

## 2. Preflight (verified against Git and code, 2026-10-18)
- origin/main `1645c8c` (PR #184 merge). P10C-E (PR #182) and P10C-F1 (#183, #184) are merged. The content of `d9ac4c8` is on main; the reconciliation branch `docs/p10c-f1-final-governance-reconciliation` (commit `3ba011c`) has an empty diff against main, but `3ba011c` itself is not an ancestor of main.
- Branch `feat/p10c-f2a-us-source-qualification` from origin/main. Alembic head verified `0038_compensation_concepts` (single head by file chain; no migration added).
- V1 BLS: 1,386 records (read from the P10C-C inventory metadata, not recounted from the database).
- Product coverage evaluator ran: 412 cases, `insufficient_evidence` 94% BELOW GATE (consistent with the reported 386/412 = 93.7%; the exact counts were not re-derived).

## 3. Official source verification
Machine-readable: `p10c_f2a/source_verification.json`. Verified on official bls.gov pages: OEWS May 2025 released 15 May 2026; **2018 SOC** (May 2025 technical notes); about 830 categories, military group excluded; annual wages derived from hourly using a 2,080-hour year where wage-rate data are lacking (BLS methodology); 2022 NAICS industry scope with exclusions; geography scope; MB3 method; top-coded footnote ("equal to or greater than $115.00 per hour or $239,200 per year"); "Estimate not released" footnote; public domain, citation requested, emblem prohibited, commercial use not addressed. All four authorised URLs returned HTTP 200 on HEAD requests (sizes 51,367; 143,843; 279,525; 93,634 bytes). HEAD responses are availability evidence, not acquisition.

Final file name for the occupation-definitions component, verified at the source: `occupation_definitions_m2025.xlsx` (`https://www.bls.gov/oes/occupation_definitions_m2025.xlsx`).

## 4. Licensing
Publisher BLS; public domain except previously copyrighted photographs and illustrations; credit BLS as the source (a request); the BLS emblem must not be used or reproduced; commercial use is not addressed by the page and follows from the public-domain statement for US use; use outside the United States is unresolved; the SOC files rely on the site-wide statement because the SOC page itself has no reuse text. No mandatory legal review remains for the US core; no material licensing issue stops the work.

## 5. Acquisition precondition check (A–P)
| | Result |
|---|---|
| A, B, C, D, E, F, H, I, N, O, P | MET |
| G | MET with note (territorial use unresolved) |
| **J OEWS data dictionary available** | **NOT MET** |
| **K File structure and suppression semantics understood** | **NOT MET** |
| **L Registry permits the workflow** | **NOT MET** (lifecycle not advanced; registry licence state still unverified) |
| **M Isolated ingestion environment** | **NOT VERIFIED** (no staging location created) |

The J/K blocker in detail: no standalone official field specification was found on the BLS pages read (tables, documentation, technical notes, data overview, the first 100,000 characters of the FAQ, and the time-series `oe.txt`, which documents the time-series layout rather than the national XLSX). The pages give partial facts only. The full field list, O_GROUP values, aggregation codes, percentile columns and the symbols for suppressed values are therefore **not verified**. The authoritative description probably ships inside `oesm25nat.zip`, but that cannot be confirmed without downloading it.

Under the specification's stop conditions, **no file was downloaded and nothing was ingested.** `scripts/p10c_f2a_acquisition_gate.py --check` reports `acquisition_allowed: False` with these blockers.

## 6. Acquisition manifest
`p10c_f2a/acquisition_manifest.json` (schema `p10c-f2a-acquisition-manifest/1`) lists the four authorised files, all `NOT_ACQUIRED`, with null SHA-256, timestamps, storage and import batch. The gate script rejects any file marked ACQUIRED without a valid 64-hex SHA-256, timestamp and size. No hash is fabricated.

## 7. What unblocks acquisition
1. Owner decision on J/K: confirm that downloading only the four named files, into an isolated approved location, to read the bundled field description is permitted as part of Package 1 (the files are already within the authorised scope), or supply the official field specification. Ingestion stays stopped until the field semantics are read.
2. Name the isolated raw-file location (outside runtime paths) for M.
3. Registry transition for `us_soc_2018` and `us_bls_oews` through the registry mechanism (L).
After that, F2A continues with the steps in the two companion documents.
