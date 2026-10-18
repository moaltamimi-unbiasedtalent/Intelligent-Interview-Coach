# P10C-F2A — US Official Source Acquisition (Package 1)

**Status (updated 2026-10-18, continuation): OFFICIAL US FILES ACQUIRED AND INGESTED INTO AN ISOLATED NON-PRODUCTION DATABASE — SOC 2018 GRAPH POPULATED — OEWS MAY 2025 EVIDENCE VALIDATED AND IMPORTED — NOTHING QUALIFIED, NOTHING RUNTIME-APPROVED — COMPENSATION V2 DISABLED — ALL 12 GATES FALSE.** Sections 1–7 record the earlier preparation state and sections 8–10 supersede them where they differ.

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

## 8. Acquisition and data-dictionary follow-up (2026-10-18)
**Authorization:** the owner authorised downloading only the four approved files for isolated documentation inspection; scope unchanged.
**Staging (outside the repository and every protected store):** `/Volumes/Abu Aaliyah/Claude Projects/Interview Practice Studio/ask4mo-source-staging/p10c-f2a/us/` with `raw/`, `extracted/`, `manifests/`, `validation/`. Raw files are not committed.

| File | Official URL | Acquired (UTC) | Bytes | SHA-256 |
|---|---|---|---|---|
| soc_structure_2018.xlsx | https://www.bls.gov/soc/2018/soc_structure_2018.xlsx | 2026-10-18T11:34:07Z | 51,367 | `ade08af40923266f3a854842e888ca3e93c15b26a147c20a2b12a61f4c4f4077` |
| soc_2018_definitions.xlsx | https://www.bls.gov/soc/2018/soc_2018_definitions.xlsx | 2026-10-18T11:34:10Z | 143,843 | `f8b9ca7cccea78e30abfc9b96ab8a9dd2632cc8c8b57ee9b38a9b871e8fe2a89` |
| oesm25nat.zip | https://www.bls.gov/oes/special-requests/oesm25nat.zip | 2026-10-18T11:34:14Z | 279,525 | `b5855a37f3e03e779f6fbf173d3bbc94aeeff33426aef32fa95ce6d025bab1af` |
| occupation_definitions_m2025.xlsx | https://www.bls.gov/oes/occupation_definitions_m2025.xlsx | 2026-10-18T11:34:17Z | 93,634 | `d927416c1165e2043e8626f380f3bcaaa2f98377bfa5ef5c08209e573d95bb24` |

All four returned HTTP 200 with sizes equal to the earlier HEAD values. One request per file, identifying User-Agent, 3-second spacing.

**Archive contents:** `oesm25nat.zip` holds `oesm25nat/national_M2025_dl.xlsx` (289,615 bytes) with sheets `national_M2025_dl` (1,401 data rows, 32 columns), **`Field Descriptions`**, `UpdateTime`, `Filler`. This closes preconditions J and K: the official dictionary ships inside the authorised file.

**Findings (details: `p10c_f2a/data_dictionary_validation.json`):**
- Every column is defined by BLS in the bundled sheet (VERIFIED); reference period and SOC edition are PARTIALLY_VERIFIED from the file (the file does not name the edition; 2018 SOC is verified from the May 2025 technical notes and is consistent with the data: 825 of 830 detailed codes and all major, minor and broad codes match the 2018 structure).
- Scope in the file: national only (area 99), cross-industry (NAICS 000000), ownership 1235.
- O_GROUP counts: total 1, major 22, minor 94, broad 454, detailed 830 (1,401 rows, 1,394 distinct codes). **Seven broad codes appear twice** (broad and detailed) with identical values, as the dictionary describes: one measurement, never double counted.
- **Five OEWS-specific codes are not in the 2018 SOC structure** (21-1018, 25-2052, 25-9045, 51-2028, 53-1047): BLS labels them detailed; they must not become canonical SOC nodes.
- Missing-value semantics: `*` = wage not available (81 rows in every hourly column, exactly the ANNUAL=TRUE occupations; 7 rows in every annual column, exactly the HOURLY=TRUE occupations); `**` (employment not available) and `~` do not occur; **`#` (top-code) does not occur**: 72 rows have an hourly 90th percentile and 77 an annual 90th percentile at or above the $115.00 / $239,200 thresholds as plain published numbers, consistent with BLS's statement that from May 2025 it publishes specific percentile estimates previously footnoted. Annual percentiles are monotone on every complete row. Annual medians differ from hourly times 2,080 by up to $15.20 (BLS's own rounding and derivation): BLS values are kept as published, never recomputed.
- SOC files: structure and definitions agree exactly (23 major, 98 minor, 459 broad, 867 detailed = 1,447 codes, identical code sets), which verifies the earlier SOC counts. The May 2025 occupation-definitions file has 832 code rows; two (11-1031, 45-3031) are not in the national file; the national file's higher-level codes (total, major, minor, broad) are not in it by design.
- Licensing unchanged: BLS public domain, credit BLS, no emblem, commercial use not addressed, territorial use outside the US unresolved.

**Manifest:** updated to schema `p10c-f2a-acquisition-manifest/2`: `state` ACQUIRED with real hashes, plus separate `ingestion_state` NOT_INGESTED, `qualification_status` NOT_QUALIFIED and `runtime_approval` NOT_APPROVED. `scripts/p10c_f2a_acquisition_gate.py --check --verify-hashes` re-hashes the staged files (passes).

**Registry state:** unchanged. No lifecycle transition was made; precondition L (registry lifecycle for `us_soc_2018` and `us_bls_oews`) remains the one open gate before ingestion.

**Remaining ingestion blockers:** (1) registry lifecycle transition through the registry's own mechanism (L); (2) treatment of the five OEWS-specific codes (owner or engineering decision); (3) Ask4Mo reliability thresholds for PRSE-based qualification (BLS defines PRSE but no threshold); (4) commercial use outside the US. Ingestion into CompensationRecordV2 has not started and is not authorised by this follow-up.

## 9. Owner policy decisions (recorded 2026-10-18)
POLICY A (BLS-specific aggregates), B (duplicate presentations), C (reliability) and D (commercial licensing) are recorded in the dossier (`owner_policies`) and in section M.2 of the Package 1 authorization document, on the basis of the explicit owner instruction (no signature or legal approval claimed).

## 10. Controlled isolated ingestion (2026-10-18)
**Preflight:** branch `feat/p10c-f2a-us-source-qualification` at `47a3527`; PR #186 exists; the four staged files re-verified against the manifest hashes (`--verify-hashes` and `verify_staged_files`): all OK. The staging directory is located from `P10CF2A_STAGING_DIR`, else the sibling `ask4mo-source-staging/p10c-f2a/us` of the repository, else the manifest's recorded path.

**Isolated environment:** a dedicated PostgreSQL 16 cluster created inside the staging directory (loopback port 55433, trust auth, own data directory) and database `p5b_f2a_us` (the sanctioned test-isolation name; announced through `P5B_PG_ADMIN_URL`). It was chosen after a listener on port 55432 turned out to be a Colima/Docker SSH forward, which was **not** used. Migration head `0038_compensation_concepts` (single head, `alembic upgrade head` run on the isolated database only, no new migration). Backup/rollback: the database and cluster are disposable and recreated by `scripts/p10c_f2a_ingest.py`; nothing else depends on them. Developer PostgreSQL, Redis, Chroma, corpus, research cache, checkpoints, evaluation artifacts, candidate data and admin configuration were not touched (the V1 SQLite file was opened read-only/immutable; its size and mtime were unchanged).

**Source registry transitions (isolated database only, through `SourceRegistry`, audited):** `us_soc_2018` and `bls_oews`: registered (`discovered`, origin `authorised_manual`) > `licensing_pending` > licence set `verified` (BLS public-domain statement read 2026-10-18) > `licensing_verified` > `approved_for_ingestion`, each citing the owner authorisation. `approved_for_runtime_use` was never requested. The audit events carry no actor user because no human admin user exists in the isolated database. The persistent registry and `source_registry_baseline.json` are unchanged: durable approval there stays an owner/admin action. Mapping of the requested vocabulary to **existing** states: OWNER_AUTHORIZED_FOR_ACQUISITION = manifest/dossier record; SOURCE_ACQUIRED = manifest `state`; SOURCE_VALIDATED = manifest `validation_state` plus registry `licensing_verified`; EVIDENCE_QUALIFIED = **not reached** (`qualification_status` stays `unqualified`); RUNTIME_APPROVED = **not reached**.

**Runtime blocker RB-LIC-1 (POLICY D):** commercial runtime use outside the United States is not established. No ingestion result changes that.

Counts, measurement handling, V1 reconciliation, retrieval and coverage are in [the graph document](P10C_F2A_OCCUPATION_GRAPH_QUALIFICATION.md) and [the evidence document](P10C_F2A_COMPENSATION_EVIDENCE_QUALIFICATION.md). Machine-readable results: `p10c_f2a/ingestion_report.json` (counts only; no salary values).
