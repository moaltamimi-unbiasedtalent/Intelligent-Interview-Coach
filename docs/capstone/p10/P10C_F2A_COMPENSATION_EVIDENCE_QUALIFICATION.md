# P10C-F2A — Compensation Evidence Qualification (BLS OEWS May 2025)

**Status: NOT PERFORMED — blocked behind the acquisition gate.** No OEWS record was ingested and no `CompensationRecordV2` was created from OEWS May 2025. Nothing is qualified; classification C1/C2 and confidence states are not assigned to any real record.

## Existing V1 baseline (read-only, from P10C-C inventory metadata)
1,386 OEWS V1 records: country US, currency USD, pay period annual, statistic median, reference year 2025, all with value and bounds, distinct native codes (no duplicates), code shape xx-xxxx; none has a title, industry or region. The V1 store does not keep the OEWS occupation level, gross/net basis or SOC edition. Per-record reconciliation (QUALIFIED_FOR_V2, REQUIRES_ADDITIONAL_EVIDENCE, INCOMPATIBLE, DUPLICATE, UNRESOLVED) **cannot be performed without the official file**; no V1 record was changed, deleted or migrated, and V1 candidate behaviour is unchanged.

## Measurement rules (verified facts and plan)
Preserve occupation code and label, SOC 2018, country, national scope, 2022-NAICS cross-industry scope (as the file states it), USD, gross straight-time pay as BLS defines it (verify against the May 2025 notes), employee population, mean versus median versus percentile, hourly versus annual, reference period May 2025, edition and source record identifier. BLS's own 2,080-hour annual derivation is retained and labelled as BLS methodology; no second annualisation; no invented percentiles; suppressed or "not released" values stay missing; top-coded values keep the BLS footnote ("equal to or greater than $115.00 per hour or $239,200 per year") and are never treated as exact. Exact scaled-integer money. Vocabularies (D-15) map to the existing concept infrastructure of migration 0038; unknown concepts stay UNKNOWN.

## Classification and confidence
Policy unchanged: C1 detailed national, C2 broad national, C3 harmonised international, C4 abstain; C1 is never assigned because the publisher is official. Confidence states reuse the implemented values; no numeric confidence. Not exercised on real evidence.

## Product coverage
Before: 412 cases, `insufficient_evidence` 94% BELOW GATE (reported 386/412 = 93.7%; 95% gate unchanged). After: **NOT RUN** (no evidence ingested). Improved, regressed and unchanged cases: none claimed. The 13 wiring cases and 13 ambiguity cases remain as analysed in the F1 dossier; UK-dependent and ambiguous cases are not promoted.

## Not run
Import idempotency with real data, revocation with real data, performance, full-suite and PostgreSQL qualification of an import, and the compensation-V2 evaluator against ingested evidence. Structural tests pass but are not evidence of operational qualification.
