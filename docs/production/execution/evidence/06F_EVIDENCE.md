# 06F Evidence: native review and legal translation qualification MATERIALS (LG-10, LG-11; PG-04 part)

Branch `feat/06fg-review-packages` (shared with 06G), **STACKED on `origin/feat/06c-language-ai-behaviour` (head `fa9f02a1`, pushed, not yet merged)**. It holds the 06C rating protocol and harness that 06G extends, so **this branch merges after 06C**; until 06C is merged its PR diff shows the 06C commits as well. `origin/main` was f5cf7cb throughout (already contained in the 06C base; nothing to merge). **No migration** (Alembic head untouched). No frontend behaviour change; one new read-only build helper script (`frontend/scripts/dump-catalog-strings.mjs`); no Playwright run (port 3141 reserved, unused).

## 0. Position, stated plainly

- **LG-10 and LG-11 are NOT approved and this package cannot approve them.** No native reviewer or legal qualifier is appointed (OD-LANG-03, OD-LANG-04 are AWAITING). No human qualification is recorded as done anywhere. `docs/production/execution/language_readiness.json` is untouched: LG-10 and LG-11 stay `NOT STARTED` for every language.
- What this package delivers is the **complete, review-ready material** so that reviewers' work starts the day they are appointed, plus a checklist of exactly what the owner must supply and how it maps to the 06H record.
- Every non-English text in the packs is an **engineering translation, not reviewed**. Every pack says so on every page (`NOT REVIEWED`), the freeze manifest says `NOT FROZEN` with no freeze SHA, and every sign-off form is blank. No reviewer name, qualification or date is invented anywhere (the only completed forms are synthetic fixtures built inside tests and never written to the repository).
- No model call, no network, no credential, no real data. Nothing is live.

## 1. Requirement mapping

| Requirement | Covered | How | NOT covered |
|---|---|---|---|
| LG-11 materials: native-language human review of interface text, Mo output samples, interview questions and feedback | Materials complete, per language (7) | `docs/production/language_review/<code>/`: `INTERFACE_STRINGS.md` (all 2,611 catalogue strings grouped by surface, with English source, context note and where each appears), `MO_SENTENCES.md` (the 17 Mo-voiced sentences of the 06C inventory with where they appear, the transactional email parts, and the known English-only gaps), `INTERVIEW_SAMPLES.md` (12 synthetic question and feedback prompts with the policy meaning), `INSTRUCTIONS.md`, `SIGNOFF_FORM.*` | The review itself (OPEN: named reviewers) |
| LG-10 materials: legal and privacy translation qualified | Materials complete, per language | `LEGAL_POINTERS.md`: the 283 legal and trust strings (namespaces trust, privacy, terms, aiTransparency, dataPrivacy, legal) with the English source of record; conditional pointer to `docs/production/legal_review/` (05E), which does not exist in this tree and is referenced as "if it exists" | The qualification (OPEN: OD-LANG-04); the legal documents served by the backend are versioned records outside the catalogue and are named, not copied |
| Reviewer instruction sheet (correctness, naturalness, register, terminology, policy-sentence equivalence, absence of English leaks, protected slogan untouched) | Yes | `INSTRUCTIONS.md` in every pack (seven criteria, four verdicts, independence, what a sign-off means) | |
| Sign-off form whose fields match `src/language_activation.py` and is never pre-filled | Yes | `SIGNOFF_FORM.md` and `SIGNOFF_FORM.template.json` per language, one form per gate LG-10 and LG-11: named reviewer, qualification statement, evidence reference, approval date, release SHA (plus optional `approved_until`, independence, conflicts, digest reviewed, verdict). A test asserts every human field is empty and that a blank form never validates; another builds a complete synthetic form and proves its `gate_fragment` yields a locale record that `validate_locale_record` accepts, and that a different SHA makes it stale | Recording a real sign-off (owner, later) |
| Changes-since-review diff so a frozen catalogue is re-reviewed incrementally | Yes | `--freeze --release-sha SHA --out DIR` writes per-item digests (interface, Mo, email, samples) at the owner's SHA; `--diff --baseline DIR/FREEZE_SNAPSHOT.json` writes `CHANGES_SINCE_REVIEW_<code>.md` with added, English-source-changed, translation-changed and removed items. Tested with an added, a removed, a re-sourced and a re-translated key | The owner has not named a SHA, so no snapshot is committed |
| Freeze manifest with per-language digests | Yes | `docs/production/language_review/FREEZE_MANIFEST.json`: per language the content digest (independent of layout), item counts and the SHA-256 of every pack file; `freeze_sha: null`, status `NOT FROZEN`, `reviewed: false`, `signoffs_recorded: 0` | |
| Deterministic generation, `--write` and `--check` | Yes | `scripts/language_review_pack.py`; a test fails while the committed packs are stale, and a second generation is byte-identical | `--check` needs node and the frontend dependencies (see section 5) |
| Single readiness checklist mapping each owner-supplied item to `language_readiness.json` | Yes | `docs/production/language_review/OWNER_READINESS_CHECKLIST.md` (shared with 06G); a test pins the mapped field names and that every named repository path exists | |
| PG-04 (privacy, legal and data rights) | Only the legal-translation review material | | PG-04 as a whole belongs to 05E and the owner |

## 2. Changes

New: `src/language_quality/review_pack.py`; `scripts/language_review_pack.py`; `frontend/scripts/dump-catalog-strings.mjs` (read-only esbuild dump of the merged catalogue, never writes inside the repository); `docs/production/language_review/` (README, OWNER_READINESS_CHECKLIST, FREEZE_MANIFEST.json, 7 x 8 generated pack files); `tests/test_language_review_pack_06f.py`.
Not touched: the readiness record, the catalogue, the 06C inventory and harness, `AdminShell.tsx`, `capabilities.ts`, `nav-items.ts`, `src/agent/*`, `src/copilot/security/*`, the frozen contracts, the tracker and the register.

## 3. Design notes

- The catalogue is read through the same esbuild bundling as the 06A audit helper, so the pack shows exactly what the application serves (2,611 keys x 8 locales including preserved Russian, which gets no pack).
- "Where each string appears": the first frontend file that references the exact key; a key built in code (a status name, a tier) is marked `composed` and the namespace file list is given instead (515 of 2,611 keys are composed). Every namespace has a curated context note (54 of 54 at the time of writing); a new namespace still renders with a generic note and is listed in the README, so a future catalogue change never breaks generation.
- Mechanical hints (`=EN` identical to English, `PH` placeholders differ, `EN?` English-only words present, `SLOGAN`, `MISSING`) are signals for the reviewer, never a verdict. The protected slogan "Ask More. Be More." is checked in every language and never altered (a test asserts no `SLOGAN` hint).
- The content digest covers the reviewable CONTENT only, so a layout or note change never invalidates a review; a changed string always does.
- One freeze SHA applies to a whole locale: 06H marks any gate approved at another SHA as stale, so a new SHA means re-approving every gate of that locale. The checklist and the diff report say so.

## 4. Tests and commands

| Check | Result |
|---|---|
| `PY -m pytest -p no:cacheprovider -q tests/test_language_review_pack_06f.py` | 28 passed (repo venv and canary) |
| `PY scripts/language_review_pack.py --check` | review packs current; 0 paid, 0 live, 0 sign-offs |
| `ruff check .` | All checks passed |
| `PY scripts/ci_test_shards.py verify --shards 4` | OK, each test file in exactly one shard |
| CI evaluators (every `scripts/eval_*` step of `ci.yml`, plus the new 06G self-test and sync check) | 49 evaluator commands from `ci.yml` run, 0 failed (every `scripts/eval_*` step incl. `eval_language_ai_behaviour`, `eval_i18n_l10n`, `eval_admin_*`, `eval_release_matrix`, `eval_w11_integrated`, plus the two 06G steps); the working tree stayed clean (evaluators write to temp) |
| Full backend suite `-n 3 --dist loadfile -q` (once, final tree) | 6,930 tests: 6,888 passed, 41 skipped (pre-existing skips, unchanged), 1 failed. The one failure, `tests/test_test_isolation.py::test_identity_evaluator_never_touches_the_developer_database_or_a_caller_supplied_one`, was a crash of the child evaluator process at interpreter exit under load (`libc++abi: recursive_mutex lock failed`, return code -6) while the evaluator itself printed `RESULT: PASS`; the same test passes when run alone and `scripts/eval_identity_platform.py` passes in the evaluator run. It touches nothing of this package. An earlier full run was interrupted by the tooling before its summary line, so the run reported here is the second |
| Fresh-dependency canary `$HOME/.cache/ask4mo/ci_venv/bin/python` | the two new test files: 62 passed under the canary (`$HOME/.cache/ask4mo/ci_venv`); the full suite was run on the repo venv only |

Negative tests include: blank form never validates; reviewer names of an automation or an engineering label, a placeholder, a malformed or future date, a bad SHA, a short qualification, a missing independence statement, a stale or foreign digest and a wrong gate are each refused; the readiness record is never written by the package (source scan); the packs and checklist pass the repository's language-claim scanner (no document claims a language is qualified or reviewed).

## 5. Risks and limits

- The packs are large (about 3 MB of generated Markdown). They must be regenerated with `--write` whenever a catalogue string, a Mo sentence, an email template or the synthetic bank changes, exactly like `06A_LOCALE_AUDIT.md`; a test fails while they are stale. A later package that adds catalogue keys therefore also commits regenerated packs.
- `--check` (and the test) need node and `frontend/node_modules` (esbuild), as the 06A audit test does; the CI python test shards install them. The evaluator job has no node, so the pack check is a pytest test, not an evaluator step.
- The usage scan is textual: composed keys are found at namespace level only.
- Machine hints cannot judge a translation. Register (formal or informal address) is left to the reviewer, who is asked to state which form is used; the owner may need to decide the form per language.
- The legal documents served by the backend (versioned terms, privacy and AI-transparency records) are not part of the catalogue and are not copied into the packs; the qualifier is pointed at them and, if it exists in the release tree, at the 05E legal review pack.
- Reviewers see engineering translations of text that also appears in public pages; their review of marketing copy is under LG-11, legal accuracy under LG-10.

## 6. Missing human, live and gate evidence (all NOT RUN / OPEN)

Named native reviewers and legal qualifiers for seven languages (OD-LANG-03, OD-LANG-04); their completed forms and review reports; the freeze SHA; the other twelve gates of each language (LG-01 to LG-09, LG-12 to LG-14) at the same SHA; any record in `language_readiness.json`. Calendar: the planning model needs reviewers named and engaged by Tuesday 27 October for a freeze finished by Friday 27 November.

## 7. Owner decisions needed

1. Name the seven native reviewers and the legal and privacy translation qualifier(s), and engage them (OD-LANG-03, OD-LANG-04). Use `OWNER_READINESS_CHECKLIST.md`.
2. Name the freeze release SHA when the catalogue is frozen, then run `--freeze` and send the packs.
3. Decide the form of address (formal or informal) per language if the reviewers report an inconsistency.
4. Decide whether the 05E legal review pack, once merged, should be listed in each pack by name (today it is referenced conditionally).

## 8. SHA and throughput

- SHA: code commits `bcb05082` (06F) and `fa926f9f` (06G), pushed to `origin/feat/06fg-review-packages`; the final head is the evidence commit on top (an evidence file cannot name its own commit; the final report states it after `git ls-remote origin feat/06fg-review-packages`). `origin/main` was f5cf7cb and already in the base, so no merge or conflict resolution was needed. Expected conflicts when other packages land: regenerated packs (`python scripts/language_review_pack.py --write`) if the catalogue changed, and `.github/workflows/ci.yml` (one added step).
- Throughput: started 2026-10-22 about 14:30 CEST; first push 15:26 CEST; rework rounds: 3 (a test expectation of mine used the wrong half-width rule, a blinding scan matched ordinary words, and the first hint test expected no English-word flag on a sentence containing "the"; all found by my own tests and fixed before the push).
