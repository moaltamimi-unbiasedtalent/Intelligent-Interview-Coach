# P10C-F2A — Compensation Evidence Qualification (BLS OEWS May 2025, national)

**Status: OFFICIAL OEWS EVIDENCE VALIDATED AND IMPORTED into the isolated non-production database. NOTHING IS QUALIFIED (`qualification_status` = `unqualified` on all 16,140 records) AND NOTHING IS RUNTIME-APPROVED. Compensation V2 is disabled.** Structural qualification of the pipeline is complete; operational qualification of the evidence is not claimed.

## Source and dictionary
`oesm25nat.zip` (`national_M2025_dl.xlsx`): 1,401 data rows, national (area 99), cross-industry (NAICS 000000), ownership 1235; BLS-authored Field Descriptions sheet read (32 columns, all defined). Reference period May 2025, release 15 May 2026, 2018 SOC (May 2025 technical notes), straight-time gross wage excluding premium pay, employees only (self-employed excluded) (May 2025 notes, read 2026-10-18).

## Import (production mode of the registry-gated importer, isolated database only)
| Quantity | Value |
|---|---|
| Rows read / all-occupations total (not an occupation) | 1,401 / 1 |
| Quarantined BLS-specific aggregates (POLICY A) | 5 rows: 21-1018, 25-2052, 25-9045, 51-2028, 53-1047 |
| Duplicate presentations merged (POLICY B) | 7 codes, one observation each |
| Occupations imported | 1,388 (818 detailed, 570 broad: 22 major + 94 minor + 454 broad) |
| CompensationRecordV2 imported | **16,140** (rejected: 0) |
| Evidence class | C1 9,450 (detailed), C2 6,690 (broad); no C3; none assigned by publisher authority alone |
| Re-import | same batch key, `already_imported`, 0 added (idempotent); 6.8 s |
| First import | 12.9 s (about 1,250 records/s) |
| Provenance audit | 16,140 of 16,140 complete (publisher, dataset, edition, batch, archive SHA-256, member, sheet, source rows, source field, RSE, employment) |

Measures per occupation: annual and hourly x (mean, median, 10th, 25th, 75th, 90th percentile) = up to 12; each is its own record (`pay_period`, `measure`, `percentile` are part of the identity). Annual medians also carry the published 10th/90th percentiles as bounds (`percentile_10_90`), as in V1. Controlled vocabularies (D-15): `pay_basis` gross, `earnings_concept` wage_statistic, `population_scope` employees, `evidence_method` survey, `geography_level` national, `occupation_level` detailed or broad.

## Measurement integrity
- `*` (not available) stays **absent**: 79 annual-only occupations have no hourly records (474 absent measurements) and 7 hourly-only occupations have no annual records (42), exactly the ANNUAL/HOURLY flags. No zero, no interpolation, no hourly-from-annual or annual-from-hourly inference. (The dictionary's 81 annual-only rows include the two quarantined aggregates 25-2052 and 25-9045.)
- `**` and `~` do not occur; **`#` does not occur** (the file carries plain numbers above the $115.00 / $239,200 thresholds, consistent with BLS's May 2025 statement). Any other marker is rejected.
- Published annual wages are stored as published; no second annualisation. Values use exact decimals (floats converted through their shortest decimal text). Mean, median and each percentile are distinct records; broad groups stay C2.
- Reliability (POLICY C): `EMP_PRSE`, `MEAN_PRSE` and `TOT_EMP` are in every record's provenance; no cutoff exists; no record is qualified.

## V1 reconciliation (read-only; per-record file kept in staging, no salary values)
V1 holds **1,386** OEWS records (recounted from `data/knowledge/compensation.db`, opened read-only and immutable; size and mtime unchanged), all distinct codes, no duplicates. Verdicts: **QUALIFIED_FOR_V2 = 1,381** (year, statistic and exact values equal an ingested official record) and **INCOMPATIBLE = 5** (the BLS-specific aggregates). V2 therefore also holds 7 occupations V1 lacks (the hourly-only occupations, which have no annual median). "QUALIFIED_FOR_V2" here means reconcilable, not that any V2 `qualification_status` was set. No V1 row was changed or deleted and V1 candidate behaviour is unchanged.

## Retrieval (existing resolver, internal mode, isolated database)
Exact detailed occupation: evidence, exact, C1, cited. Broad occupation and a duplicate-presentation code: evidence, C2. Non-canonical aggregate, invalid SOC code and wrong taxonomy edition: `not_found`. Military occupation (in the SOC graph, no wage): abstain C4. Other country: abstain (no cross-country fallback). **Operational mode** (`require_operational` true): abstain, value withheld, not candidate-presentable, because the source is approved for ingestion only and no measurement is qualified. Resolve latency on 200 occupations: p50 3.5 ms, p95 6.9 ms.

**Observation for the owner.** When the exact occupation lacks the requested measurement (an annual-only occupation asked for an hourly wage, or an hourly-only one asked for an annual wage) the existing P10C-C broader-group policy returns the parent group's value, labelled `broader_group` and C2. That is policy-compliant and labelled, but the owner may prefer abstention when the exact occupation exists and simply publishes the other pay basis; a policy decision, not changed here.

## Product coverage
Runtime evaluator (412 cases): **before 386 sufficient / 26 insufficient = 93.7%, gate 95%, BELOW GATE** (exact counts from the evaluator's results file). The evaluator reads the legacy runtime knowledge, not the isolated database, so candidate runtime coverage is unchanged by this wave (**after: 386 sufficient / 26 insufficient = 93.7%, identical per case: 0 improved, 0 regressed, 26 unchanged**). Qualified-source structural assessment of the seven US compensation cases among the 26: **0 of 7 resolve** because the case titles ("Data Analyst", "Software Developer", "Product Manager", "Human Resources Manager", "Accountant", "Financial Analyst", "Sales Manager") are not exact official SOC labels and no curated aliases exist (D-08). No wiring case was promoted, no ambiguity treated as a match, no evaluation definition changed, the 95% threshold untouched. The other 19 insufficient cases (UK, education, outlook, openings) are not addressed by US OEWS evidence.

## Evidence qualification and confidence
Evidence class follows the actual specificity (C1 detailed national, C2 broad national). Confidence and abstention states are the implemented ones (evidence, ambiguous, insufficient_context, unsupported, not_found, abstain, conflict); no numeric confidence. Source conflicts: none arise (one source, one edition); conflicting duplicate presentations are rejected, not averaged. Freshness: reference period May 2025, publication 15 May 2026, acquired 2026-10-18; no automatic replacement; supersession by a later edition is a future owner decision.

## Remaining before any qualification or runtime use
Named measurement-qualification reviewer and an owner-approved reliability rule (POLICY C); alias curation for title wiring (D-08); decision on broader fallback for a missing measure; persistent-registry approval by the owner/admin path; resolution of commercial use outside the US (RB-LIC-1); a decision on a schema extension if the five aggregates should ever be stored.

## Testing and validation (2026-10-18)
- New tests: `tests/test_us_sources_p10cf2a.py` (11, including real staged-file counts when the staging directory exists), `tests/test_pg_p10cf2a.py` (PostgreSQL, synthetic workbooks), updated gate and dossier tests.
- Full backend suite with the isolated PostgreSQL server announced (so the PostgreSQL tests ran): 4,528 passed, 4 skipped, 0 failed, counted from the progress output (the pytest summary line is suppressed by the repository's quiet configuration). An earlier run stopped at a failure caused by editing a module while the suite was importing it; the rerun with no edits in flight passed.
- `eval_knowledge_foundation.py` PASS (all 12 gates off), `eval_occupation_resolver.py` PASS, `eval_compensation_v2.py` PASS; Ruff clean on the whole repository; `git diff --check` clean; `scripts/p10c_f2a_acquisition_gate.py --check --verify-hashes` OK; dossier check OK. Type checks: no separate type-check step is configured in this repository (not run). Frontend untouched (not run). Browser E2E: not run (no UI change).
- Security: the xlsx files are parsed read-only with openpyxl (no macro or formula execution), the runner refuses output inside the repository, refuses any database not named `p5b_*` on the announced loopback server, imports `tests.conftest` first, makes no network call and uses no paid LLM or Stripe call; no candidate data is involved.
