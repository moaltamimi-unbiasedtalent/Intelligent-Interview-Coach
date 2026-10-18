# P10C-F2A-Q — US Evidence Qualification Decision Report

**Status: US EVIDENCE QUALIFICATION REVIEWED — NOTHING `qualified`.** 16,140 OEWS observations were reviewed with deterministic engineering rules and moved to the existing state `engineering_checked`; **0 records, 0 aliases and 0 sources are `qualified` or runtime-approved**, because the existing workflow requires a named human reviewer and none exists in the isolated environment. Compensation V2 and all 12 gates remain disabled. Everything below ran in the isolated non-production database `p5b_f2a_us`. Machine-readable results: `p10c_f2a/qualification_report.json` (counts only) and `p10c_f2a/ingestion_report.json`.

## 1. Methodology and separation of duties
| Layer | Who or what | Output | State in this wave |
|---|---|---|---|
| Engineering validation | `us_qualification.review_record` (deterministic, reproducible) | outcome and reasons per record | done: 16,140 of 16,140 ENGINEERING_CHECKED |
| Measurement qualification | named human reviewer (D-08 for aliases, owner-approved reliability rule for measurements) | `qualified` | NOT DONE: no reviewer identity exists; not requested; not forced |
| Owner acceptance | owner | accept the review packet | pending |
| Registry approval | `SourceRegistry` | `approved_for_runtime_use` | NOT requested; sources are `approved_for_ingestion` in the isolated database only |
| Runtime authorisation | owner and gates | candidate use | none; all 12 gates False |

Engineering rules (each failed rule yields a deterministic reason and the outcome INSUFFICIENT; nothing is repaired or guessed): authorised source and edition; source approved for ingestion with a verified licence; staged-file SHA-256 verified; occupation is a canonical SOC 2018 node whose level agrees with the published structure; positive reported value; measurement definition complete (measure, pay period, gross basis, USD); concept, population and method recorded (wage statistic, employees, survey); national US geography; reference and publication period present; provenance complete (archive hash, member, sheet, source rows, field, batch, RSE, employment); mean records carry a published RSE; the record key is unique. **ENGINEERING_CHECKED means these hold. It makes no precision claim, is not `qualified`, and is not operational evidence.**

## 2. Counts and reconciliation (all reproduced by queries; every check matches)
| Quantity | Value | How it reconciles |
|---|---|---|
| SOC nodes / parent relationships | 1,447 / 1,424 | files: 23 + 98 + 459 + 867 codes; relationships = codes minus 23 majors |
| OEWS source rows | 1,401 | 1 total + 22 major + 94 minor + 454 broad + 830 detailed |
| Canonical rows | 1,395 | 1,401 − 1 total − 5 quarantined aggregates |
| Occupations | 1,388 | 1,395 − 7 duplicate second presentations |
| CompensationRecordV2 | 16,140 | annual 8,286 + hourly 7,854; C1 9,450 (detailed) + C2 6,690 (broad) |
| V1 / reconcilable / incompatible | 1,386 / 1,381 / 5 | the 5 are the BLS aggregates |

**Annual-only discrepancy (81 vs 79), resolved.** The two reports counted different things. The acquisition report counted source **rows** with `ANNUAL = TRUE` (81: 58 detailed, 4 minor, 19 broad; no duplicate presentations among them). The ingestion report counted canonical **occupations** (79). The difference is exactly two quarantined BLS-specific aggregates: **25-2052 (source row 412) and 25-9045 (source row 443)**, both `detailed`, both annual-only, neither in the 2018 SOC. No measurement was omitted: the 79 annual-only occupations have 474 absent hourly measurements (79 x 6) and the 7 hourly-only occupations have 42 absent annual measurements, all `*` in the source, all kept absent. The full row table is in the report.

## 3. Reliability (POLICY G)
No threshold exists in any approved policy, and none was created. BLS publishes relative standard errors only for employment (EMP_PRSE) and the mean wage (MEAN_PRSE); **it publishes none for the median or any percentile**, so no precision statement is made about 13,450 of the 16,140 records. Observed over the 1,388 occupations: employment PRSE min 0.0, median 1.8, p75 3.7, p90 6.4, p99 16.9, max 35.0 (53 occupations above 10, 7 above 25, none above 50); mean-wage PRSE min 0.0, median 0.7, p75 1.2, p90 2.2, p99 8.4, max 15.9 (7 above 10, none above 25). Those counts are descriptive reference points, not thresholds. Uncertainty, source authority, occupation and geographic specificity, completeness and freshness stay separate dimensions. No record required a new material reliability judgment under these rules, so none was left pending for that reason; a reviewer who adopts a precision rule later can re-review without losing history.

## 4. Quarantined aggregates and duplicates (POLICY A, B)
The five codes (21-1018, 25-2052, 25-9045, 51-2028, 53-1047) stay quarantined: official source observations with non-canonical SOC identities, excluded from exact matching, no node, no title-derived mapping, no schema change; deferred for later policy review. The seven duplicate presentations (13-1020, 13-2020, 29-2010, 31-1120, 39-7010, 47-4090, 51-2090) were re-verified identical on every field except O_GROUP, produce one record per measure (re-import: same batch, 0 added), and keep both source presentations in provenance. Matching wage amounts alone never deduplicate unrelated observations.

## 5. Curated aliases (D-08 framework; POLICY E)
Evidence rule (documented and reproducible): a market title may be proposed as an alias of an official detailed SOC 2018 occupation only when **exactly one** official detailed title contains every word of it (singular and plural treated as one word). Similarity, popularity and model knowledge are not evidence.

| Case | Market title | Decision | SOC target | Basis | Alias state |
|---|---|---|---|---|---|
| pc_compensation_187 | Software Developer | PROPOSED_SINGLE | 15-1252 Software Developers | number variant of the official title | engineering_checked |
| pc_compensation_195 | Human Resources Manager | PROPOSED_SINGLE | 11-3121 Human Resources Managers | number variant | engineering_checked |
| pc_compensation_207 | Sales Manager | PROPOSED_SINGLE | 11-2022 Sales Managers | number variant | engineering_checked |
| pc_compensation_199 | Accountant | PROPOSED_SINGLE | 13-2011 Accountants and Auditors | component of the official title (scope wider: includes auditors; reviewer must confirm) | engineering_checked |
| pc_compensation_203 | Financial Analyst | PROPOSED_SINGLE | 13-2051 Financial and Investment Analysts | component of the official title (adds "Investment"; reviewer must confirm) | engineering_checked |
| pc_compensation_183 | Data Analyst | NO_AUTHORITATIVE_EVIDENCE | none | no official title or definition contains it | none created; abstains (not_found) |
| pc_compensation_191 | Product Manager | NO_AUTHORITATIVE_EVIDENCE | none | same | none created; abstains (not_found) |

For the last two, several SOC occupations could plausibly apply, but selecting one (or recording an ambiguity set) needs evidence from an approved source (for example a separately approved occupational-title dataset); none is acquired here. Every alias is language `en` (basis curated_manual), country-scoped to US, taxonomy `soc@2018`, source `us_soc_2018`, type `recognized_title`, approval **PENDING_HUMAN_REVIEW**; **0 aliases are `qualified`** (the store refuses `qualified` without a named reviewer). Tests cover: exact official title (resolves only when the label's language is unverified-accepted, the existing conservative policy), curated alias, ambiguous alias (shared by two occupations: AMBIGUOUS, no first match), unsupported alias, wrong taxonomy edition, wrong country, unregistered alias source, fixture source not evidence, revocation (deprecated aliases stop resolving) and the qualification authority.

## 6. Broader-group and missing-measure behaviour (POLICY F)
Rule implemented and tested (isolated only): when the exact occupation lacks the requested measure the resolver **abstains** (C4, `exact_occupation_measurement_unavailable`, no value, no measure, no pay period substituted, no conversion). A parent group's statistic is returned only in `contextual_evidence` with the broader code and label, evidence class, source citation, reference period, measure, pay period and the warning that it is NOT the requested occupation's value. With `allow_broader_occupation=false` there is no context either. Real-data results: 79 annual-only occupations asked for hourly: 9 abstain with labelled context, 70 abstain with none, **0 own values substituted**; 7 hourly-only occupations asked for annual: 4 with context, 3 without, 0 substituted. An ambiguous hierarchy abstains and lists each parent separately. **Test impact, stated openly:** this changes the internal resolver's earlier "broader group as primary evidence" behaviour, so the expectations that asserted it were updated to the owner rule (not weakened to pass): `tests/test_compensation_v2_p10cc.py::test_broader_fallback_follows_only_verified_broader_relationships_and_is_labelled`, `tests/test_country_foundations_p10cd.py::test_candidates_reached_through_several_parents_never_resolve_arbitrarily`, `tests/test_global_fallback_p10ce.py::test_the_fallback_trace_names_the_stage_and_never_uses_another_country`, and the corpus cases `broader-fallback-labelled`, `ca-broader-same-taxonomy`, `ca-broader-isco-cross-taxonomy`, `ca-cross-taxonomy-ambiguity-conflict`, `sa-broader-group-fallback`. The resolver is non-operational and imported by no candidate path.

## 7. V1 reconciliation (layers kept apart)
1,386 V1 records (read-only recount; the V1 file's size and mtime unchanged). **RECONCILABLE_WITH_OFFICIAL_V2: 1,381** (exact code, year, statistic and values); **same occupation identity verified: 1,381** (exact SOC code in the 2018 graph); **qualified V2 evidence: 0**; **runtime-approved: 0**; INCOMPATIBLE 5. The earlier label QUALIFIED_FOR_V2 was misleading and was renamed. No V1 record was mutated.

## 8. Product coverage (three views, kept apart)
| View | Result |
|---|---|
| Actual candidate runtime coverage (the 412-case evaluator) | **before 386/412 = 93.7%; after 386/412 = 93.7%; 0 improved, 0 regressed, 26 unchanged; BELOW the 95% gate.** Runtime is disabled and the evaluator reads the legacy knowledge, so no improvement is claimed. |
| Structural resolution (isolated database, aliases engineering_checked, internal mode) | 5 of the 7 US compensation cases resolve to a SOC identity and retrieve an annual median (C1) |
| Isolated qualified-source coverage | **0 of 7**: no alias and no measurement is `qualified` |
| If a reviewer approved all 5 aliases and the runtime counted them (not claimed) | 391/412 = 94.9%, still below 95% |

Remaining blockers for the 26: 2 US titles without authoritative alias evidence, the UK cases (package 2 not authorised), the education/outlook/openings cases (BLS OOH and projections excluded), human review of aliases and measurements, and runtime activation, which is out of scope.

## 9. Governance and licensing
Registry: `us_soc_2018` and `bls_oews` are `approved_for_ingestion` with a verified licence in the isolated database; transitions were made through `SourceRegistry` (audited, no actor user); the persistent developer registry and the committed baseline are unchanged; no direct status writes; `approved_for_runtime_use` never requested. **RB-LIC-1 remains open.** To close it the owner needs (a) a qualified legal opinion that BLS-published OEWS and SOC content, which is a U.S. Government work in the public domain under U.S. law, may be commercially used and redistributed in each non-US target market (the US statute applies in the US; treatment abroad is jurisdiction-specific), and optionally (b) a written statement from BLS on non-US commercial use. Neither exists; no clearance is implied.

## 10. Decisions and actions for the reviewer and owner
Name a measurement reviewer and an alias reviewer (D-08); adopt or decline a precision rule (POLICY G); review the five alias proposals and the two evidence gaps; confirm the new broader-group behaviour for any product contract; decide on persistent-registry approval; close RB-LIC-1; decide whether the five aggregates ever need a schema extension.
