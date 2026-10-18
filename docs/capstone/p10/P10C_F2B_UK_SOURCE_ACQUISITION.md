# P10C-F2B — UK Official Source Acquisition (Package 2)

**Status: P10C-F2B SOURCE PREPARATION COMPLETE — ACQUISITION BLOCKED — OWNER AUTHORIZATION OR SOURCE VERIFICATION REQUIRED.** I did not download, extract or ingest any UK file, approve any source, or activate anything. Compensation V2 and all 12 gates are disabled.

## 1. Preflight (VERIFIED)
Starting main `690868dda176941ef47163e90777a4c2f5b33cee` (PR #186, the P10C-F2A engineering PR, is merged; its closure commit `006337c` is an ancestor). Branch `feat/p10c-f2b-uk-source-qualification` from that main. Alembic head `0038_compensation_concepts` (no migration added). Local V1 UK store: 527 `ons_ashe` rows (see [the compensation document](P10C_F2B_ASHE_COMPENSATION_QUALIFICATION.md)). No UK source is registered in an approved state. Product coverage baseline 386/412 = 93.7%, BELOW the 95% gate; all 12 gates False.

## 2. Authorization status
Package 2 is **not authorised**. The exact request, with owner decisions D-03 and D-22 and a blank sign-off, is [P10C_F2B_PACKAGE_2_OWNER_AUTHORIZATION.md](P10C_F2B_PACKAGE_2_OWNER_AUTHORIZATION.md). I did not self-approve anything.

## 3. Source inventory (candidates; none acquired)
| File | Publisher URL (official) | Reported size | Availability (HEAD, 2026-10-18) |
|---|---|---|---|
| UK SOC 2020 Volume 1 structure Excel | ons.gov.uk/file?uri=/methodology/classificationsandstandards/standardoccupationalclassificationsoc/soc2020/soc2020volume1structureanddescriptionsofunitgroups/soc2020volume1structureanddescriptionofunitgroupsexcel20260827.xlsx | 289.1 kB | 200, xlsx |
| ASHE Table 14, 2025 provisional | ons.gov.uk/file?uri=/employmentandlabourmarket/peopleinwork/earningsandworkinghours/datasets/occupation4digitsoc2010ashetable14/2025provisional/ashetable142025provisional.zip | not stated | 200, zip |
| ASHE guide to tables | ons.gov.uk/file?uri=/employmentandlabourmarket/peopleinwork/earningsandworkinghours/datasets/annualsurveyofhoursandearningsasheguidetotables/current/ashetableguide.xls | 41.5 kB | 200, xls |
HEAD requests are availability evidence only. The manifest (`p10c_f2b/acquisition_manifest.json`, same schema family as F2A) lists all three as `NOT_ACQUIRED` with null hashes, timestamps and storage, `package_authorization` APPROVAL_PENDING, and separate ingestion, qualification and runtime states. The existing gate script was generalised (`--dir`, declared file set, publisher prefix, package authorization): it reports `ingestion gate False` for Package 2 and refuses any acquired file in an unauthorised package; the US package result is unchanged.

## 4. Official facts verified (details and URLs: `p10c_f2b/source_verification.json`)
UK SOC 2020: 9 major, 26 sub-major, 104 minor, 412 unit groups (SOC 2010: 9, 25, 90, 369); Excel, PDF and ZIP downloads; OGL v3.0. ASHE: 2025 estimates provisional (released 23 October 2025), 2024 revised; full-time means more than 30 paid hours a week (25 or more for teaching professions); from 2021 occupation coding moved from SOC 2010 to SOC 2020; the 19 December 2025 correction (codes 3312, 331, 33; Tables 2, 3, 14, 15, 20; UK, London, South East, East; annual earnings; revised data expected October or November 2026); annual pay includes pay affected by absence. Licence: OGL v3.0, third-party photographs, illustrations and videos excluded, no specific attribution wording.

## 5. Preconditions A to P
| | Result |
|---|---|
| A, C, E, H, I, N, P | MET |
| F, G, M, O | MET with note |
| D (editions) | PARTIAL: the Table 14 occupation classification edition is not confirmed |
| K (suppression semantics) | PARTIAL: the notice is verified, the cells and symbol are not |
| **B (Package 2 authorization)** | **NOT MET** |
| **J (ASHE data dictionary)** | **NOT MET** (the guide to tables and the file notes are unread) |
| **L (registry)** | **NOT MET** (needs B) |

Under the specification's stop conditions: **no file was downloaded and nothing was ingested.**

## 6. What unblocks acquisition
Sign section M of the authorization request (or answer individual items). After that: manual download of the three files to `../ask4mo-source-staging/p10c-f2b/uk/` (defined, not created), hashes recorded, the guide to tables and the file notes read, the SOC edition confirmed, then isolated ingestion only if every precondition holds. Human qualification, reviewer endpoints, persistent promotion and runtime stay deferred.
