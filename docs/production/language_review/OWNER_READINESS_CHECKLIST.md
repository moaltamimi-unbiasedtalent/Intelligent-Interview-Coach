# Owner readiness checklist: native review, legal translation and independent evaluation (06F, 06G)

**Status: NOTHING IS SUPPLIED AND NOTHING IS SIGNED.** No reviewer is appointed, no qualification is recorded, no budget is approved, no threshold is adopted, no freeze SHA is named. This is the one list of exactly what the owner must supply and where each item goes, so that recording a sign-off later is mechanical and valid under the 06H activation rule (`src/language_activation.py`). Engineering prepared the materials; engineering cannot supply any item below.

Related owner decisions: OD-LANG-03 (native reviewers), OD-LANG-04 (legal and privacy translation qualifiers), OD-BUDGET (live-evaluation budget), OD-GATE-THRESHOLDS (numeric quality and safety thresholds). The planning model needs reviewers and qualifiers named and engaged by Tuesday 27 October for a freeze finished by Friday 27 November (`docs/production/execution/WAVE3_EXECUTION_PLAN.md`).

## 1. Supplied once for all languages

| # | Item | Who | Where it goes | Check |
|---|---|---|---|---|
| 1 | The release SHA to freeze (the commit the reviewers review) | owner | `languages.<code>.release_sha` AND `gates.<LG-nn>.release_sha` for all fourteen gates of every language | `python scripts/language_review_pack.py --freeze --release-sha SHA --out DIR` stores the per-item digests; one SHA for the whole locale, because 06H treats any gate approved at another SHA as stale |
| 2 | Budget for the generated review sample (OD-BUDGET) | owner | a budget configuration file outside the repository named by `AI_BUDGET_CONFIG_PATH`, with `approval_marker` (`OD-BUDGET:<reference>`) and the `evaluation` ceilings; the same marker in `AI_BUDGET_APPROVED_MARKER` | the generation step refuses without marker, ceiling and the 05C governor (`scripts/language_human_eval.py generate --live`); size the budget from `docs/production/execution/evidence/06G_SAMPLE_SIZE_GUIDANCE.md` |
| 3 | Thresholds (OD-GATE-THRESHOLDS) | owner | the thresholds of record for the quality and safety numbers; not stored by the harness | the report compares only with labelled PROPOSALS (`PROPOSED_LEVELS` in `src/language_quality/human_eval.py`) and never emits a PASS |
| 4 | The approver of LG-04 and LG-05 per language (a named human who reads the 06C and 06G reports) | owner | `gates.LG-04.approver`, `gates.LG-05.approver` | not a reviewer's rating and not a script |
| 5 | Engagement dates | owner | the review calendar | 20 working days of review and 3 for the freeze in the planning model |

## 2. Supplied for EACH of the seven languages (en, de, fr, es, it, pt, nl)

Repeat the block for every language. Russian is excluded from R1.0 and has no pack.

| Item | Supplied by | Form field (`docs/production/language_review/<code>/SIGNOFF_FORM.template.json`) | `language_readiness.json` field | Validation (06H) |
|---|---|---|---|---|
| Named native reviewer, full name | owner appoints, reviewer writes | `forms.LG-11.reviewer_name` | `languages.<code>.gates.LG-11.approver` | a real name: not empty, not a placeholder, not an automation or engineering label |
| Native reviewer qualification statement | reviewer | `forms.LG-11.qualification_statement` | kept in the signed form; the evidence reference cites it | required by this protocol |
| Named legal and privacy translation qualifier, full name | owner appoints, qualifier writes | `forms.LG-10.reviewer_name` | `languages.<code>.gates.LG-10.approver` | same rule |
| Legal qualifier qualification statement (counsel or qualified legal translator) | qualifier | `forms.LG-10.qualification_statement` | kept in the signed form | required by this protocol |
| Evidence reference for each gate (path or identifier of the signed form and the review report) | owner files the documents | `forms.<gate>.evidence_reference` | `languages.<code>.gates.<gate>.evidence` | at least 8 characters, not a placeholder |
| Approval date for each gate | reviewer | `forms.<gate>.approval_date` | `languages.<code>.gates.<gate>.approved_on` | ISO date, not in the future |
| The release SHA each reviewer reviewed | owner gives it, reviewer copies it | `forms.<gate>.release_sha` | `gates.<gate>.release_sha` and `languages.<code>.release_sha` | 7 to 40 lowercase hex characters, equal for the locale and all gates |
| Optional end of validity | owner | `forms.<gate>.approved_until` | `gates.<gate>.approved_until` | the gate is stale once the date has passed |
| Independence statement and conflicts declared | reviewer | `forms.<gate>.independence_statement`, `conflicts_declared` | kept in the signed form | required by this protocol (a reviewer is not the author of the text and is not paid by the author's incentives) |
| The pack digest the reviewer reviewed | reviewer copies it from `README.md` | `forms.<gate>.pack_content_digest_reviewed` | kept in the signed form | must equal the digest in `FREEZE_MANIFEST.json`; a changed text needs a re-review (`--diff`) |
| Three independent raters for the blinded evaluation (06G), each with a completed conflict-of-interest declaration | owner appoints, raters declare | `scripts/language_human_eval.py declaration-template` | not stored in the record; the report cites them | `validate-declaration` says ELIGIBLE or needs an owner decision |

Per language the owner therefore supplies: 2 named people (LG-11 and LG-10) with qualifications, their dates, evidence references, the one SHA, and 3 independent raters. A native reviewer is not automatically a legal qualifier; the same person may sign both forms only if qualified for both.

## 3. How a sign-off is recorded later (mechanical)

1. The named person completes the form (`SIGNOFF_FORM.md` or the JSON twin) and returns it with the review report. Nobody edits the blank templates in the repository.
2. `python scripts/language_review_pack.py --validate-form COMPLETED.json --gate LG-11` reports anything missing. When complete it prints the four fields and nothing else changes; it writes no file.
3. The owner copies the printed fields into the gate entry of `docs/production/execution/language_readiness.json` and sets the state of that gate by hand:

   ```json
   "LG-11": { "state": "<set by the owner>", "evidence": "<evidence_reference>", "approver": "<reviewer_name>", "approved_on": "<approval_date>", "release_sha": "<release_sha>" }
   ```

4. The locale record needs `release_sha` equal to the same SHA, all fourteen gates present and each PASS with its own evidence, approver, date and SHA, and the two claim flags (`production_qualified`, `offered_to_real_users`) equal to what the validation derives. A flag is a claim, never an input: set it true only when every gate is complete; otherwise it must stay false or the record is refused.
5. After editing, run `python scripts/eval_locale_inventory.py --write`, then `pytest tests/test_language_activation_06h.py tests/test_language_readiness_06a.py`. The language is offered to real users in staging and production only when the record validates.
6. If the text changes after the review, run `--diff` against the frozen snapshot: the reviewer re-reviews only the changed items and signs again at the new SHA; a new SHA makes every gate of that locale stale until each is re-approved.

LG-10 and LG-11 are only two of the fourteen gates. LG-01 to LG-09 and LG-12 to LG-14 need their own evidence at the same SHA; completing these two does not qualify a language.

## 4. What the 06G evaluation adds (PG-07, LG-04, LG-05)

| Step | Owner action | Supplied artefact |
|---|---|---|
| Appoint 3 independent raters per language | name them; collect declarations | `declarations/<code>/rater_R<n>.json` |
| Approve the budget (item 2 above) and run the generation | set marker and configuration, run `generate --live` | `outputs.jsonl` (the harness refuses a missing, duplicate or empty reply) |
| Send ONLY `packet/reviewer/<code>/rater_R<n>/` plus `README.txt` and `RUBRIC.md` to each rater | | returned `rating_sheet.csv` files |
| Read the report | decide against the thresholds of record | `results.json`, `report.md` (status at best READY_FOR_OWNER_REVIEW) |
| Record LG-04 / LG-05 | the named approver | `language_readiness.json` as in section 3 |

## 5. What the owner must NOT expect from the harness

It approves nothing, sets no threshold, names no reviewer, runs no live call by itself and never prints a PASS. The 05C governor and the pending PR order are described in `docs/production/execution/evidence/06G_EVIDENCE.md`.
