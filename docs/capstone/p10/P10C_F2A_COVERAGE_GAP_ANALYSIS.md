# P10C-F2A — Coverage Gap Analysis (all 26 insufficient product-coverage cases)

**Status: ANALYSIS ONLY. Observed runtime coverage is unchanged: 386/412 = 93.7%, below the 95% gate.** The gate needs **392** sufficient cases, so at least **6** more are required with no regression. No evaluator expectation, denominator or threshold was changed (the evaluator and `evaluations/product_coverage/cases.json` are untouched). Source: the 412-case evaluator run (offline lexical mode), per-case results, and the isolated qualified-source database.

## 1. Three evaluations, kept apart
| Evaluation | Result |
|---|---|
| A. Current candidate runtime coverage (observed) | 386 sufficient, 26 insufficient, 93.7%, BELOW GATE; unchanged by all P10C-F2A work because Compensation V2 is disabled and the evaluator reads the legacy runtime sources |
| B. Isolated structural coverage (observed, internal mode, isolated database) | 5 of the 7 US compensation cases resolve to a SOC identity and retrieve an annual-median C1 observation using engineering-checked aliases; 0 are qualified; this is NOT candidate coverage |
| C. Potential qualified-source coverage (hypothetical, stated assumptions) | see section 3; not observed |

## 2. Gap matrix (26 cases)
Root cause: `wiring` = occupation-code wiring; `ambiguous_title` = the title has no unique occupation. Failure reason for every row: **missing_source** (the candidate runtime holds no production source for that slice; evidence 0). Runtime dependency for every row: Compensation V2 / runtime wiring is disabled and out of scope.

| Case | Country | Requested occupation | Evidence asked | Root cause | Alias review | Official source | Isolated structural result | Category | Gain after human qualification |
|---|---|---|---|---|---|---|---|---|---|
| pc_education_073 | (none) | Data Analyst | education | ambiguous_title | AMBIGUOUS | BLS employment projections / Occupational Outlook Handbook | not applicable | needs_additional_source_package | 0 |
| pc_education_075 | (none) | Product Manager | education | ambiguous_title | INSUFFICIENT_EVIDENCE | BLS employment projections / Occupational Outlook Handbook | not applicable | needs_additional_source_package | 0 |
| pc_education_083 | (none) | Civil Engineer | education | wiring | not assessed | BLS employment projections / Occupational Outlook Handbook | not applicable | needs_additional_source_package | 0 |
| pc_education_084 | (none) | Project Manager | education | ambiguous_title | not assessed | BLS employment projections / Occupational Outlook Handbook | not applicable | needs_additional_source_package | 0 |
| pc_compensation_183 | US | Data Analyst | compensation | ambiguous_title | AMBIGUOUS | BLS OEWS May 2025 | not_found | needs_new_evidence_or_owner_policy | 0 |
| pc_compensation_184 | UK | Data Analyst | compensation | ambiguous_title | AMBIGUOUS | ONS ASHE | not applicable | needs_another_country_package | 0 |
| pc_compensation_187 | US | Software Developer | compensation | wiring | APPROVE_RECOMMENDED | BLS OEWS May 2025 | evidence via SOC alias, class C1 | needs_reviewer_approval_and_runtime_activation | 1 |
| pc_compensation_188 | UK | Software Developer | compensation | wiring | APPROVE_RECOMMENDED | ONS ASHE | not applicable | needs_another_country_package | 0 |
| pc_compensation_191 | US | Product Manager | compensation | ambiguous_title | INSUFFICIENT_EVIDENCE | BLS OEWS May 2025 | not_found | needs_new_evidence_or_owner_policy | 0 |
| pc_compensation_192 | UK | Product Manager | compensation | ambiguous_title | INSUFFICIENT_EVIDENCE | ONS ASHE | not applicable | needs_another_country_package | 0 |
| pc_compensation_195 | US | Human Resources Manager | compensation | wiring | APPROVE_RECOMMENDED | BLS OEWS May 2025 | evidence via SOC alias, class C1 | needs_reviewer_approval_and_runtime_activation | 1 |
| pc_compensation_196 | UK | Human Resources Manager | compensation | wiring | APPROVE_RECOMMENDED | ONS ASHE | not applicable | needs_another_country_package | 0 |
| pc_compensation_199 | US | Accountant | compensation | wiring | CONDITIONAL_APPROVAL_RECOMMENDED | BLS OEWS May 2025 | evidence via SOC alias, class C1 | needs_reviewer_approval_and_runtime_activation | 1 |
| pc_compensation_200 | UK | Accountant | compensation | wiring | CONDITIONAL_APPROVAL_RECOMMENDED | ONS ASHE | not applicable | needs_another_country_package | 0 |
| pc_compensation_203 | US | Financial Analyst | compensation | wiring | CONDITIONAL_APPROVAL_RECOMMENDED | BLS OEWS May 2025 | evidence via SOC alias, class C1 | needs_reviewer_approval_and_runtime_activation | 1 |
| pc_compensation_204 | UK | Financial Analyst | compensation | wiring | CONDITIONAL_APPROVAL_RECOMMENDED | ONS ASHE | not applicable | needs_another_country_package | 0 |
| pc_compensation_207 | US | Sales Manager | compensation | wiring | APPROVE_RECOMMENDED | BLS OEWS May 2025 | evidence via SOC alias, class C1 | needs_reviewer_approval_and_runtime_activation | 1 |
| pc_compensation_208 | UK | Sales Manager | compensation | wiring | APPROVE_RECOMMENDED | ONS ASHE | not applicable | needs_another_country_package | 0 |
| pc_future_growth_215 | US | Data Analyst | future_growth | ambiguous_title | AMBIGUOUS | BLS employment projections / Occupational Outlook Handbook | not applicable | needs_additional_source_package | 0 |
| pc_future_growth_223 | US | Product Manager | future_growth | ambiguous_title | INSUFFICIENT_EVIDENCE | BLS employment projections / Occupational Outlook Handbook | not applicable | needs_additional_source_package | 0 |
| pc_future_growth_235 | US | Financial Analyst | future_growth | wiring | CONDITIONAL_APPROVAL_RECOMMENDED | BLS employment projections / Occupational Outlook Handbook | not applicable | needs_additional_source_package | 0 |
| pc_short_term_outlook_247 | US | Data Analyst | short_term_outlook | ambiguous_title | AMBIGUOUS | BLS employment projections / Occupational Outlook Handbook | not applicable | needs_additional_source_package | 0 |
| pc_short_term_outlook_255 | US | Product Manager | short_term_outlook | ambiguous_title | INSUFFICIENT_EVIDENCE | BLS employment projections / Occupational Outlook Handbook | not applicable | needs_additional_source_package | 0 |
| pc_annual_openings_279 | US | Data Analyst | annual_openings | ambiguous_title | AMBIGUOUS | BLS employment projections / Occupational Outlook Handbook | not applicable | needs_additional_source_package | 0 |
| pc_annual_openings_287 | US | Product Manager | annual_openings | ambiguous_title | INSUFFICIENT_EVIDENCE | BLS employment projections / Occupational Outlook Handbook | not applicable | needs_additional_source_package | 0 |
| pc_annual_openings_299 | US | Financial Analyst | annual_openings | wiring | CONDITIONAL_APPROVAL_RECOMMENDED | BLS employment projections / Occupational Outlook Handbook | not applicable | needs_additional_source_package | 0 |

By category: needs_reviewer_approval_and_runtime_activation 5; needs_new_evidence_or_owner_policy 2; needs_another_country_package 7; needs_additional_source_package 12. By occupation root cause: wiring 13, ambiguous_title 13.

| Category | Meaning | Cases |
|---|---|---|
| Reviewer approval + runtime activation | US compensation with an engineering-checked alias | 187, 195, 199, 203, 207 |
| New evidence or owner policy | Data Analyst and Product Manager US compensation: no authoritative occupation evidence | 183, 191 |
| Another country package | UK compensation (ASHE, Package 2, UK SOC 2020): not authorised | 184, 188, 192, 196, 200, 204, 208 |
| Additional source package | education (4), future growth (3), short-term outlook (2), annual openings (3): BLS OOH and employment projections are explicitly excluded from Package 1 | 073, 075, 083, 084, 215, 223, 235, 247, 255, 279, 287, 299 |
| Candidate context | none of the 26 supplies context; Data Analyst and Product Manager would need it | (183, 191 and the dependent education/outlook/openings cases) |

## 3. Scenarios
| ID | Scenario | Sufficient | % | Meets 95% | Assumptions or basis |
|---|---|---|---|---|---|
| A | current candidate runtime coverage (observed) | 386 | 93.69 | False | the 412-case evaluator, observed |
| B | isolated structural coverage of the US compensation cases (observed, internal mode, aliases engineering-checked, not approved, not runtime) | 5 of 7 US cases | n/a | n/a | structural resolution in the isolated database; not candidate coverage |
| C1 | potential: the five US aliases and the OEWS measurements human-approved AND runtime activated | 391 | 94.9 | False | a named reviewer approves all five aliases and the measurement batches; runtime wiring and activation of Compensation V2 for US compensation; RB-LIC-1 resolved for the deployment markets; the evaluator counts the new evidence as sufficient |
| C2 | C1 plus Package 2 (UK) for the five resolvable UK titles | 396 | 96.12 | True | Package 2 authorised, acquired, qualified and runtime-activated; UK SOC 2020 alias evidence exists for the same five titles (not yet reviewed) |
| C3 | C1 plus one legitimately resolved Data Analyst or Product Manager title | 392 | 95.15 | True | an approved occupational-title source or an owner-adopted context policy evidences a unique occupation for that title (NOT currently available) |

## 4. The remaining gap, explained
392 sufficient cases are required; the baseline is 386; the maximum legitimate gain from Package 1 with the current evidence is 5, giving 391: 1 short. Package 1 alone cannot reach the gate with the evidence that exists: even if a reviewer approved all five aliases and the runtime counted them, coverage would be 391/412 = 94.9%, **one case short**. Legitimate ways to close the last case, none available today: Package 2 for the UK titles (+5 if the same five titles resolve in UK SOC 2020: 396, 96.1%), a BLS projections/OOH package (up to 12 cases, still gated by the unresolved titles for Data Analyst and Product Manager), or a legitimately evidenced identity for one of Data Analyst or Product Manager (+1: 392, 95.15%, exactly at the gate). Forcing a mapping for those two titles would manufacture a pass and is not proposed.

## 5. Evaluation integrity statement
No evaluator, case, expectation, denominator or threshold was modified in this wave. Resolver-level tests (not the product-coverage evaluator) that asserted the superseded "broader group as primary evidence" behaviour were updated to the owner rule in the previous wave: original expectation (broader-group value returned as evidence), reason (owner policy F: abstain, context only), supporting evidence (the policy decision and the labelled-context tests), regression analysis (full backend suite passes; no product-coverage case changed). Candidate runtime evaluation and offline qualification remain separate.
