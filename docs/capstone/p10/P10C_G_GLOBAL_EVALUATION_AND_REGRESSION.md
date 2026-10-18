# P10C-G — Global Evaluation Corpus and Regression Qualification (GKB-16, GKB-17)

**Status: CODE QUALIFIED OFFLINE (engineering).** This is not production ready, not human qualified, not source qualified globally, not runtime approved and **not a pass against the 95% product-coverage gate**. Compensation V2 is disabled and all 12 rollout and billing gates are False. The corpus uses synthetic fixtures only; jurisdictions are evaluation jurisdictions, not claims that official data is qualified. Deferred P10C-F work and P10F are not reopened (roadmap section 1b). Roadmap authority: the canonical roadmap has 11 remaining rows; none was added or removed, and the authorised sequence (P10C-G, P10D, W12.4E, W12.4F, W12.5, P10E, integrated requalification, RC-P10-004, AC-24, P11) was preserved without a new change.

## 1. Architecture (reuse, no second engine)
| Piece | File | Role |
|---|---|---|
| Versioned synthetic corpus | `src/knowledge_foundation/data/global_evaluation_corpus.json` (schema `p10c-g/1`, version 1.0.0, 115 cases, 48 scenarios) | stable case ids, expected outcomes, tags, explicit source and qualification state per case |
| Deterministic generator | `scripts/gen_global_evaluation_corpus.py` (`--check` fails when the committed file differs) | no randomness, no clock, no network |
| Runner and governance suite | `src/knowledge_foundation/global_eval.py` | loads the corpus through the EXISTING `compensation.fixtures` loader and `CompensationResolver`; adds 12 governance and negative-regression checks over the EXISTING `SourceRegistry`, `OccupationGraph`, `AliasStore`, importer and `ashe_suppression` guard; fixture integrity rules; required-tag coverage matrix; determinism hash |
| CLI | `scripts/eval_global_corpus.py` | repeats the run, runs the five existing P10C evaluators, writes machine-readable results, exits 1 on any failure |
| Product-coverage guard | `scripts/check_product_coverage_baseline.py`, `evaluations/product_coverage/baseline_gate_status.json` | runs the unchanged 412-case evaluator and fails on any per-case regression against the baseline of the matching environment |
| CI | `.github/workflows/ci.yml` (three steps added before the secret scan) | corpus, guard, artifact upload; no secrets, no `continue-on-error`, results in `$RUNNER_TEMP` |
Small extensions to existing code: the fixture loader accepts taxonomy scheme and edition, language-less aliases and a few more expectation keys; `eval_product_coverage.py` honours an explicit `ASK4MO_EVAL_OUT` results directory (default unchanged). No lifecycle enum, evaluator engine or runtime path was added.

## 2. Inventory of the existing evaluation architecture (baseline before changes)
Synthetic corpora, all reused unchanged: compensation 44 cases, country foundations 64, wider South America and fallback 59 (+9 comparisons), occupation resolver 68. Existing evaluators and their checks: knowledge foundation 23, occupation resolver 19, compensation V2 17, country foundations 19, global fallback 21. Product coverage: 412 cases (`evaluations/product_coverage/cases.json`). CI before this wave: pytest (which covers the unit tests) plus a product-coverage "smoke"; **none of the five P10C evaluators ran in CI and the product-coverage step could never fail (the evaluator exits 0 even when BELOW GATE).** Duplicates and conflicts: the category `geography_independence` appears in all four corpora by design (not conflicting); no conflicting fixture was found. **Stale artifact found:** the committed `evaluations/product_coverage/summary.md` and `results.csv` (29 August 2026) report `insufficient_evidence` 97% with 14 insufficient cases, whereas the evaluator now reports 386 of 412 (93.7%, 26 insufficient) on a developer machine; the committed copies were not regenerated (the evaluator writes to a temporary directory by default) and are NOT the current result.

## 3. Local versus CI result (investigated, measured)
The product-coverage evaluator reads git-ignored local knowledge stores (`data/knowledge/*`, `data/chroma/*`) when they exist. Measured on 2026-10-18:
| Environment | Sufficient | Percent | Status |
|---|---|---|---|
| developer-local (stores present) | 386 of 412 | 93.7% | BELOW_GATE, accepted for Capstone engineering scope |
| clean checkout (tracked files only, a fresh git worktree; CI-like) | 258 of 412 | 62.6% | BELOW_GATE |
These are different measurements and are never merged. The 93.7% figure depends on local licensed stores that CI does not have. CI parity of the clean-checkout number is VERIFIED only in a fresh local worktree; it is NOT VERIFIED on GitHub until the first CI run of the new guard step.

## 4. Coverage kept apart (never one metric)
| Notion | Value | Basis |
|---|---|---|
| A. Candidate-runtime product coverage | 386/412 developer-local; 258/412 clean checkout; both BELOW the 95% gate (392 required) | observed (guard) |
| B. Offline structural coverage | 5 of 7 US compensation cases resolve in the isolated database | REPORTED from the P10C-F2A packet (internal mode, not candidate coverage) |
| C. Engineering-checked evidence | 16,140 OEWS records and 5 aliases | REPORTED (isolated database) |
| D. Human-qualified source coverage | 0 records, 0 aliases | REPORTED |
| E. Synthetic evaluation coverage | 115 corpus cases and 12 governance checks all pass; 83 of 83 required tags exercised | measured by this wave |
The owner accepted 93.7% for the current Capstone engineering scope: an accepted limitation, not a PASS. The 412-case denominator, the 95% threshold and every expected outcome are unchanged.

## 5. Country coverage matrix (synthetic cases; every cell PASS)
Per jurisdiction: exact code, official title, wrong taxonomy edition, broad evidence (C2, or C3 for the harmonised EU source), child without its own measure (abstain with labelled broader context), other-country request (no fallback), operational mode (withheld). FR stands for the harmonised EU source (C3); CL stands for wider South America (ISCO namespace).

| Jurisdiction | exact code | official title | wrong edition | broad | child abstains + context | no cross-country fallback | operational withheld |
|---|---|---|---|---|---|---|---|
| US | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| GB | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| DE | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| FR | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| CA | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| MX | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| BR | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| CL | PASS | PASS | PASS | PASS | PASS | PASS | PASS |

## 6. Required coverage by area (83 required tags; each exercised by at least one passing case or check)
| Area | Required tags | Exercised |
|---|---|---|
| occupation_classification | 14 | 14 |
| compensation_evidence | 24 | 24 |
| fallback_and_abstention | 12 | 12 |
| multilingual | 9 | 9 |
| lifecycle_and_governance | 10 | 10 |
| negative_regression | 14 | 14 |
Classification: exact code, official title, curated alias proposal, unqualified alias (resolves, never operational), ambiguous title, unsupported title, wrong edition, wrong country, missing classification, broad and detailed occupation, conflicting candidates (a code in two editions), revoked mapping, missing provenance. Compensation: exact, unsupported and unavailable measures, mean versus median, percentile, hourly versus annual, weekly versus annual (no hidden period conversion), full-time versus all-employee, national versus regional, detailed versus broad, taxonomy editions, publication periods, provisional versus revised vintages, missing and suppressed values, revoked evidence, conflicting sources, unqualified and unapproved sources, incomplete provenance. Fallback: country-native detailed and broad, authorised international (C3), unavailable national evidence, insufficient specificity, national versus international, unapproved harmonised mapping (carries nothing), FX and PPP not configured, unsupported geography; C3 is never promoted to C1 and C4 abstains. Multilingual (en, de, fr, es, pt, it, nl, ru; unsupported zh): official titles, authorised aliases, accent folding, same text in two languages, cross-language needing opt-in, unsupported language, language never selecting the country, unverified-language alias needing context.

## 7. Abstention matrix (expected non-evidence outcomes in the corpus)
| Outcome | Reason | Cases | Examples |
|---|---|---|---|
| abstain | - | 3 | x-weekly-unavailable-no-annualisation, x-annual-never-derived-from-weekly, x-unapproved-harmonised-mapping-carries-nothing |
| abstain | evidence_exists_but_is_not_operational | 8 | us-operational-withheld, gb-operational-withheld, de-operational-withheld, fr-operational-withheld, ca-operational-withheld, mx-operational-withheld ... |
| abstain | evidence_withheld_citation_incomplete | 1 | x-incomplete-provenance-withheld |
| abstain | exact_occupation_measurement_unavailable | 9 | us-child-abstains-with-context, gb-child-abstains-with-context, de-child-abstains-with-context, fr-child-abstains-with-context, ca-child-abstains-with-context, mx-child-abstains-with-context ... |
| abstain | no_evidence_for_occupation_in_country | 10 | us-other-country-never-falls-back, gb-other-country-never-falls-back, de-other-country-never-falls-back, fr-other-country-never-falls-back, ca-other-country-never-falls-back, mx-other-country-never-falls-back ... |
| abstain | no_evidence_for_requested_reference_year | 1 | x-absent-period-abstains |
| abstain | no_evidence_for_requested_region | 1 | x-regional-never-becomes-national |
| abstain | source_value_suppressed | 1 | x-suppressed-never-zero |
| ambiguous | - | 3 | x-edition-missing-is-ambiguous, o-ambiguous-title-no-salary, ml-false-friend-without-language-is-ambiguous |
| conflict | - | 3 | x-default-measures-not-combined, x-populations-not-combined, x-currencies-never-combined |
| conflict | comparable_sources_of_equal_precedence_disagree | 1 | x-conflicting-sources-preserved |
| insufficient_context | - | 2 | o-missing-classification, ml-unverified-language-alias-needs-context |
| not_configured | - | 2 | x-fx-conversion-not-configured, x-ppp-conversion-not-configured |
| not_found | - | 10 | us-wrong-edition, gb-wrong-edition, de-wrong-edition, fr-wrong-edition, ca-wrong-edition, mx-wrong-edition ... |
| unsupported | - | 4 | x-unsupported-geography, x-valid-code-unlisted-country, o-wrong-country-title, ml-unsupported-language |

## 8. Governance and negative-regression results (12 checks, each in its own throwaway store)
| Check | Result | What it proved |
|---|---|---|
| g-lifecycle-ladder | PASS | source_identified=discovered; licence_pending=licensing_pending; licensing_verified=licensing_verified; ingestion_approved=approved_for_ingestion; runtime_approved=approved_for_runtime_use; revoked=re |
| g-unqualified-never-operational | PASS | unqualified=evidence_exists_but_is_not_operational; engineering_checked=evidence_exists_but_is_not_operational; all gates open presentable=True; after revocation value=None |
| g-unapproved-promotion-and-licensing-bypass | PASS | fixture_cannot_be_approved=refused, pending_source_cannot_import=refused, cannot_skip_the_lifecycle=refused, no_approval_without_verified_licence=refused, verified_licence_cannot_be_downgraded_while_a |
| g-false-reviewer-approval | PASS | record_without_reviewer=refused, alias_without_reviewer=refused, record_with_invented_reviewer_id_when_authority_is_wired=refused, alias_with_invented_reviewer_id_when_authority_is_wired=refused, auth |
| g-fabricated-mapping | PASS | equivalent_from_a_derived_rule=refused, verified_without_a_source_provided_basis=refused, verified_with_no_source=refused, derived_rule_without_a_stated_limitation=refused, unregistered_source=refused |
| g-invented-compensation | PASS | zero_value=refused, negative_value=refused, reported_without_value=refused, suppressed_with_an_amount=refused, currency_not_iso=refused, percentile_without_the_percentile_measure=refused, bounds_inver |
| g-incorrect-currency-assumption | PASS | CAD row stating USD rejected={'currency_mismatch': 1}; unstated CAD kept as CAD; South America row without a stated currency rejected={'currency_missing': 1} |
| g-suppressed-reconstruction | PASS | rejected={'publisher_suppressed_measurement_must_stay_missing': 1}; stored=[('3311', 'annual'), ('3312', 'weekly')] |
| g-revoked-mapping | PASS | before revocation: context offered=1, own value=None; after: context=0, own value=None |
| g-provenance-on-import | PASS | citation fields present=True; source without attribution refused at import=True |
| g-secondary-never-presents-as-c1-c3 | PASS | added=0; rejected={'evidence_class_undeterminable': 1}: authorised secondary evidence has no C1 to C3 class, so it is never stored as evidence |
| g-unsupported-statistical-comparison | PASS | 5 of 5 differing measurements have distinct comparability keys; unknown measure or basis is comparable with nothing=True |
Lifecycle mapping to the ACTUAL repository vocabulary (no new enum): source identified = `discovered`; licence pending = `licensing_pending`; ingestion approved = `approved_for_ingestion`; runtime approved = `approved_for_runtime_use`; revoked = `restricted` (or `superseded`); engineering checked and human qualified are measurement and alias `qualification_status` values (`engineering_checked`, `qualified`); "acquisition approved" and "source acquired" are owner and manifest records, not registry states. Design notes found, not defects: (a) the state `licensing_verified` can be reached without a verified licence (the existing P10C-A test asserts this on purpose); approval is what requires the verified licence, and that is enforced; (b) authorised secondary evidence has no C1 to C3 class and is therefore never stored as evidence.

## 9. Reproducibility, clean rebuild and performance (measured)
Three repeated runs gave an identical determinism hash. Each run builds its stores in its own temporary directory and removes them (a test checks that nothing is left behind); no developer store is read or written. Run total [1.669, 1.46, 1.468] seconds; fixture rebuild 0.152 s; resolver latency over 115 corpus requests: p50 1.14 ms, p95 1.74 ms, max 2.03 ms. The suite was also run in a fresh git worktree containing only tracked files: corpus 115 of 115, governance 12 of 12, determinism true, product-coverage guard against the clean-checkout baseline (258 of 412) with 0 regressions.

## 10. How to run
`python scripts/eval_global_corpus.py --repeat 2 --json /tmp/p10c_g_results.json` (exit 1 on any failure); `python scripts/check_product_coverage_baseline.py` (exit 1 on any per-case regression; never a pass); `python scripts/gen_global_evaluation_corpus.py --check`; `pytest tests/test_global_eval_p10cg.py`. After an intended improvement a developer refreshes the baseline of the current environment with `--update-profile` and the owner reviews it; the baseline is never updated by CI.

## 11. Remaining blockers, limitations and release restrictions
No source is human qualified or runtime approved; Package 2 and the other country packages are unapproved (deferred); RB-LIC-1 is open; the product-coverage gate is BELOW (accepted limitation); the corpus is synthetic and says nothing about real-data quality; the clean-checkout baseline is verified locally but not yet on GitHub; the five US alias proposals and the evidence batches still need human review (deferred). Protected stores: not written (the developer databases keep their hashes; the test harness fingerprints them). A source-text guard in the P10C-B tests forbids certain code tokens in `src/knowledge_foundation`; one initial tag name tripped it and was renamed rather than the guard being weakened.
