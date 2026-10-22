# 06G Independent human AI evaluation protocol (PG-07; LG-04, LG-05)

Status: **protocol and harness delivered and proven end to end on FAKE outputs, FAKE raters and FAKE declarations. The live generation and the human rating are NOT RUN / OPEN.** They need the owner's budget (OD-BUDGET), named independent raters (OD-LANG-03) and owner-approved thresholds (OD-GATE-THRESHOLDS). Nothing in this package approves a language, a gate or PG-07.

This protocol EXTENDS the 06C blinded rating protocol (`06C_RATING_PROTOCOL.md`; `src/language_quality/rating.py`, `scripts/language_rating_harness.py`). Everything in 06C about the rubric, blinding, controls and the reviewer packet still holds; this document states only what 06G adds or tightens. The 06C branch merges before this one.

Code: `src/language_quality/human_eval.py` (sample, statistics, agreement, independence, analysis, schema, report), `human_eval_generate.py` (the guarded generation step); command line `scripts/language_human_eval.py`; fixtures `evaluations/language_ai/human_eval_bank_extension.json`, `human_eval_results.schema.json`, `reviewer_declaration.template.json`; tests `tests/test_language_human_eval_06g.py`.

## 1. What is evaluated

Blinded human rating, per language (en, de, fr, es, it, pt, nl; Russian is excluded from R1.0), of three kinds of output: interview questions, interview feedback and Mo answers (grounded answers, abstentions and injection probes), on the four 06C dimensions (clarity, correctness, tone, policy adherence) and two flags (wrong language, unsafe content). Prompts are synthetic only.

## 2. Roles and independence rules

| Role | Who | Status |
|---|---|---|
| Owner | decides budget, thresholds and appointments | OPEN (OD-BUDGET, OD-GATE-THRESHOLDS, OD-LANG-03) |
| Operator | runs the governed generation and the harness commands | later; engineering never runs the live step |
| Independent raters | at least THREE per language, working separately | NOT NAMED |
| Approver | a named human who reads the report and decides LG-04 and LG-05 | NOT NAMED |

A rater is independent only if all of the following hold; the declaration records each as an explicit true or false answer and the harness refuses to call a set of raters independent otherwise:

1. **Not the author.** The text under review was written and machine-translated by the engineering side with AI assistance. A rater did not write, translate or edit any prompt, sentence or reply under review (`is_author_of_reviewed_text`, `contributed_to_prompts_or_translations` are both false).
2. **Not paid by the author's incentives.** Their pay does not depend on the result, they are not employed or contracted by the author or an affiliate, and they have no financial interest in the outcome (`compensation_depends_on_outcome`, `paid_by_author_or_author_affiliate`, `has_financial_interest_in_outcome` are all false).
3. **Declared conflicts.** Relationships to the owner or the product and any other conflict are written down (`NONE` explicitly when there is none). A raised flag or a stated relationship does not disqualify automatically and is never accepted automatically: the status is `OWNER_DECISION_REQUIRED` and the owner decides in writing.
4. **Separate work.** Each rater rates alone and uses no translation tool, search engine or AI assistant (`confirms_no_translation_or_ai_tools`, `confirms_rates_separately_from_other_raters` are true).
5. **Distinct people.** One person is never two rater slots in a language; the same person may rate two languages only if fluent in both.
6. The typed signature must equal the name. A name that is empty, a placeholder or an automation or engineering label is not a named human (`language_activation.named_human`).

The declaration template is `evaluations/language_ai/reviewer_declaration.template.json` (blank; `python scripts/language_human_eval.py declaration-template --language de --slot rater_R1 --out FILE`). `validate-declaration` returns `INCOMPLETE`, `OWNER_DECISION_REQUIRED` or `ELIGIBLE_FOR_OWNER_APPOINTMENT`. It is never an appointment.

## 3. Sample

| Stratum | Items per language | How chosen |
|---|---|---|
| Model outputs | 60 | 5 task kinds x 12 profession-neutral roles (the 6 of 06C plus 6 in `human_eval_bank_extension.json`), so no language gets an easier mix |
| Deterministic policy sentences | 6 | the localized notices Mo shows (06C) |
| Control items | 4 | scripted, unchanged from 06C |
| **Items per rater sheet** | **70** | the same 70 for every rater, in independent order |

The 06C prompts are byte-identical inside the extended bank (a test pins it); `--base` reproduces the 06C sample of 210 prompts. Sample size and the intervals it supports are in `06G_SAMPLE_SIZE_GUIDANCE.md` (generated). In short: 60 outputs per language pin a mean rating to about +-0.3 of a scale point at a spread of 1.0, and 60 clean items show only that an unsafe or wrong-language rate is probably below 5 percent. The owner may enlarge the sample; the guidance gives the price of precision.

## 4. Blinding

As 06C: an opaque sample id from a per-packet salt, a coarse item kind, the prompt and the reply; never the model, profile, prompt version, task label, control status or expected behaviour; the key lives in `private/`. A packet is built with `python scripts/language_human_eval.py sample --outputs outputs.jsonl --out packet --raters 3`; fewer than three raters is refused.

## 5. Generating the review sample (05C governor ONLY)

`python scripts/language_human_eval.py generate --live --ceiling-usd X --out outputs.jsonl` is the only code that can spend money, and it refuses unless ALL hold: not CI; `AI_BUDGET_APPROVED_MARKER` has the owner's marker shape and equals the `approval_marker` of the budget configuration (`AI_BUDGET_CONFIG_PATH`, outside the repository); a positive ceiling not above the configuration's `evaluation` stop threshold; the 05C governor is present and approves (configuration, ledger, kill switch) and installs its httpx chokepoint. If 05C is not in the tree the step refuses (fail closed): it never reimplements the governor. Per request: output tokens bounded, a timeout, zero retries; a prompt is answered once (a duplicate is refused, an existing file is resumed, never re-asked); the number of requests is capped; an empty reply stops the run. The model comes from the registry profile (`--profile fast|balanced|advanced`); no provider model id is written in this code and no key is read here. `--offline` writes labelled FAKE replies for the self-test.

Limit: the live responder evaluates the model under the product's conversation-language directive with a neutral coach instruction; it is not the full Mo or Practice product path. An operator who wants end-to-end product outputs supplies them in `outputs.jsonl` instead (the packet builder accepts any file that covers the prompt bank exactly).

## 6. Analysis

`python scripts/language_human_eval.py report --packet packet --ratings ratings --declarations declarations --out result` writes `results.json` (one record per language, validated against `human_eval_results.schema.json`) and `report.md`.

- **Intervals.** The unit is the item (the mean of its raters). Mean ratings carry a 95 percent t interval over items (the larger t value between table rows, so never too narrow); proportions carry a Wilson interval; zero events carry the rule-of-three bound. Rater effects are not modelled, so the interval understates uncertainty a little.
- **Agreement, computed offline.** Cohen's kappa (unweighted and quadratic or linear weighted, per rater pair, averaged) and Krippendorff's alpha (nominal, ordinal, interval; any number of raters, missing ratings allowed) with a seeded bootstrap interval over items. The implementation reproduces the published Krippendorff example (0.743 nominal, 0.815 ordinal, 0.849 interval). Alpha is `null`, never 0 or 1, when it is undefined (no variation, nothing pairable). Bands in the report (below 0.667, 0.667 to 0.800, 0.800 or above) are Krippendorff's tentative guidance, descriptive and not a gate.
- **Status per language**, in order: `INCOMPLETE` (a missing row, invalid value, changed column or foreign id), `RATERS_INSUFFICIENT` (fewer than three complete raters), `CONTROLS_FAILED` (a rater failed more than half the controls), `REVIEWERS_UNVERIFIED` (no declarations supplied), `REVIEWERS_NOT_INDEPENDENT` (a declaration missing, incomplete, duplicated or needing an owner decision), `READY_FOR_OWNER_REVIEW` (the best the harness can say), `SELFTEST_ONLY` (fake packet).
- **There is no PASS anywhere.** `approved` is always false with no approver, date or SHA; the results schema forbids a different value; the report generator raises if its own output contains the word PASS in capitals.
- **Thresholds are the owner's (OD-GATE-THRESHOLDS).** The report lists PROPOSED levels (`PROPOSED_LEVELS`: mean at least 4.0, lower 95 percent bound at least 3.5, share rated 4 or 5 at least 0.80, flag upper bound at most 0.10, alpha at least 0.667, at least 3 raters and 60 items) and shows, for information only, which side of each proposal a measurement lies on (`AT_OR_ABOVE_PROPOSAL`, `BELOW_PROPOSAL`). The labels say PROPOSAL, NOT ADOPTED. Nothing turns a comparison into an approval.

## 7. Results schema

`evaluations/language_ai/human_eval_results.schema.json` (generated from `human_eval.RESULT_SCHEMA`; a test fails if it drifts): schema id and protocol, language, fake flag, status, `approved` false, `approver`, `approved_on`, `release_sha` null, `thresholds` (`adopted` false), sample (items by stratum, raters expected and complete, unit of analysis), reviewers per slot (name or `NOT NAMED (OD-LANG-03)`, independence status), per-dimension mean, spread and 95 percent interval, share rated 4 or 5 with its Wilson interval, per-task means, agreement per dimension (alpha with interval, kappas), flags per item with bounds, control behaviour, the informational proposal comparison and the limitations.

## 8. Pilot revalidation (P2-01 to P2-04, L-AC24)

See `06G_PILOT_REVALIDATION_CHECKLIST.md`: sharing and revocation discoverability, source-backed experience in a representative knowledge environment, answer score interpretation and provenance clarity, run with real participants through the Pilot 2 pack. NOT RUN.

## 9. Limits

Blinding is not perfect (the language and a typical model style are visible; controls are disclosed in general terms). Three raters give agreement figures with wide intervals at 60 items. Raters judge synthetic prompts, not real conversations. The rubric, sample size, controls and proposed levels are engineering proposals the owner may change before the run. A native rating of Mo and interview text does not replace the interface and legal review (LG-10, LG-11; `docs/production/language_review/`). Live behaviour of any model is NOT VALIDATED by this package.
