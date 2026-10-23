# 06C Evidence: per-language AI behaviour (prompts, interview and feedback; LG-04, LG-05 engineering part)

Branch `feat/06c-language-ai-behaviour`, from `origin/main` f5cf7cb (all Wave 1 and Wave 2 packages merged, Alembic head `0043_story_bank_completion`). **No migration.** No frontend change (no Playwright, port 3125 unused). Requirements: REQ-LANG-03, REQ-LANG-04, D-LANG; gates LG-04, LG-05.

## 0. Position, stated plainly

- **LG-04 and LG-05 are NOT approved and this package cannot approve them.** 06H requires a named human approver, an evidence reference, a date and the release SHA per gate and language; none exists. The committed readiness record is untouched (LG-04 stays `NOT RUN`, LG-05 `NOT STARTED`); the lead may move them to `ENGINEERING DRAFT` with this file as the evidence reference. No language is qualified.
- **No live model call was made.** Everything is offline with deterministic fakes. Live quality measurement, the live scoring-invariance comparison and the blinded native-reader rating are **NOT RUN / OPEN**: they need the owner's budget marker (OD-BUDGET) and named native reviewers (OD-LANG-03).
- Every non-English sentence in this package is an **engineering translation, not native-reviewed** (LG-11). The mechanical review below finds missing, empty, unchanged-English and English-word-bearing sentences; it cannot judge correctness or tone.
- One real gap is an **owner decision, not a bug I could fix**: the interview input guard does not detect the "ignore previous instructions" attack in French, Spanish, Italian, Portuguese or Dutch (OD-INPUT-GUARD-LANGUAGES, section 4, finding F7). It is pinned by a ratchet test and reported, not hidden.

## 1. Requirement mapping

| ID | Covered | How | NOT covered |
|---|---|---|---|
| REQ-LANG-03, LG-04 (prompts and policies per language; switching language cannot bypass a policy; directives stay allow-listed) | Yes, offline | `tests/test_language_policy_06c.py`: directive allow-listing at all three sites, 25 hostile or malformed codes, mixed-script and homoglyph input, a forged directive inside candidate content, prompt parity (the system prompt in any language equals the English prompt plus only the directive, 5 tasks x 5 techniques x 5 style settings), coaching style reaches feedback only, grounding decisions identical across the seven languages and independent of the chosen language, guards take no language parameter | Live Mo behaviour per language; lexical injection recall for non-English input at the interview input guard (F7, open); a model that translates its own system prompt when leaking (F8, residual) |
| REQ-LANG-04, LG-05 (scoring is language-independent) | Yes, offline | `tests/test_scoring_invariance_06c.py` drives the real `EvaluationService` and `ReportService` with a content-aware, language-blind fake provider over four synthetic answer pairs in seven languages, on both the strict-schema and defensive paths: identical evaluations, usage records and request parameters, the system prompt differs only by the directive, a coaching style changes neither scores nor the scoring request. Tolerance: exactly zero (`src/language_quality/invariance.py`) | Whether a real model grades an answer and its translation alike (live, NOT RUN); correctness of rubric text in each language (native review) |
| REQ-LANG-04 (structured outputs on the interview question and evaluation paths) | Yes | Inspection and three gap closures (section 3); `tests/test_structured_output_06c.py` | `translation.py` and `reranker.py` (Career, not interview; F9) |
| D-LANG (localized policy sentences are engineering translations) | Inventory and mechanical review done | `src/language_quality/inventory.py`, generated `06C_POLICY_SENTENCE_INVENTORY.md` (17 keys x 8 locales), eight missing agent-path sentences added | Native review (LG-11, OD-LANG-03): state stays PENDING HUMAN REVIEW |
| Blinded native-reader rating protocol and harness | Yes, end to end on fake data | `06C_RATING_PROTOCOL.md`, `src/language_quality/rating.py`, `scripts/language_rating_harness.py`, `tests/test_language_rating_harness_06c.py` | The live run and the native rating (NOT RUN); thresholds (OD-GATE-THRESHOLDS); reviewers (OD-LANG-03) |

## 2. Findings from the review

| # | Finding | Severity | Status |
|---|---|---|---|
| F1 | The Career-chat language directive (`localized.language_directive`) was an inline literal in code, outside the versioned prompt assets | medium (REVIEW-02: every model-visible prompt is an asset) | **Fixed**: new asset `rag/response_language` v1.0.0, byte-identical (test against the former literal for all eight codes), pointer added |
| F2 | A JSON `true` or `false` in a score field was silently coerced by lax integer validation into a score of 1 or 0 | high (a wrong score recorded silently) | **Fixed**: `OverallScore` and `RubricScore` refuse a boolean; numeric strings and integral floats keep their coercion |
| F3 | The strict (provider-enforced) path still string-handled the reply (code fences, preambles, trailers) | medium | **Fixed**: exact JSON parse in the strict path; a wrapped reply takes the existing bounded fallback (defensive path, one repair); validation unchanged |
| F4 | The strict schema left `question_type` and `difficulty` as free strings; a model answering in the candidate's language could emit a localized label ("technisch"), which the lenient validator silently recorded as `behavioural` | medium (language-dependent misclassification) | **Fixed**: the strict schema now carries the English `enum`; the defensive validator is unchanged |
| F5 | Eight Mo-voiced deterministic sentences of the agent path are English only (model unavailable, not configured, step limit, two human-review cards, three grounding warnings) | medium (language ownership) | **Tables added and tested; wiring OPEN**: `src/agent/*` is owned by 01D, 01C, 04C, 07B. Pure substitution; the test pins that the English column equals the literals, so nothing changes in English |
| F6 | Three policy findings in `src/copilot/security/grounding_policy.py` and the `next_step` label (`src/agent/presentation.py`, rendered verbatim by `AgentAnswer.tsx`) are English only | low to medium | **OPEN**, tracked in the register `OPEN_ENGLISH_ONLY` (a test fails if one is fixed without updating it) |
| F7 | The interview input guard `security.detect_injection` is English-led: the attack sentence is blocked in English, only warned in German, and **not detected in French, Spanish, Italian, Portuguese, Dutch** (the Career-chat scanner `copilot.security.injection` detects all seven) | high for LG-04, but a product decision | **OPEN, owner decision** OD-INPUT-GUARD-LANGUAGES. Structural defences hold in those languages (labelled DATA block, system prompt independent of context, output guard), asserted by test. Pinned by `test_interview_input_guard_per_language_ratchet_for_the_open_owner_decision`, which fails on purpose when the guard changes. Recommendation: route `_screen_context` through the existing multilingual scanner, warn first, then block, after the owner accepts the false-positive risk on job descriptions |
| F8 | The output guard's system-prompt leak markers are English fragments; a model that translates its own instructions into the answer language is not caught by them | low (best effort by design) | **Residual, documented**, no change |
| F9 | `src/copilot/rag/translation.py` and `src/copilot/retrieval/reranker.py` extract JSON by string handling | low (Career path, not interview) | **OPEN, not touched** (out of the package's interview scope) |
| F10 | The mechanical review found no English leak, no placeholder drift and no unchanged-English copy in the pre-existing localized tables; register of address differs (French formal, others informal) | note | Native-review item (LG-11), nothing to fix mechanically |

## 3. Changes

Production code (all small):
- `src/copilot/rag/localized.py`: `language_directive` renders the new asset; eight agent-path sentence tables `AGENT_TEXT` plus `agent_text()` (bounded, unknown key raises, unknown code resolves to English).
- `prompts/rag/response_language.v1.0.0.md` and one pointer entry in `prompts/current.json` (expected trivial conflict if 01D or 01C also add or bump a family). `tests/test_prompt_assets_01b.py` `EXPECTED_FAMILY_COUNT` 44 to 45 (expected one-line conflict with any other package adding a family; the lead sums the counts).
- `src/models.py`: boolean-score refusal (`Field` bounds placed BEFORE the validator on purpose: the other order silently drops `minimum`/`maximum` from the strict schema, which a test now pins), `WithJsonSchema` enum on the lenient enum fields.
- `src/response_parser.py`: `parse_exact_json_object`, `exact_json` option (default off, so every existing caller is unchanged).
- `src/interview_service.py`: the strict path passes `exact_json=True` (one line).

New package `src/language_quality/` (offline, no provider, no network): `inventory.py`, `invariance.py`, `rating.py`.
New fixtures `evaluations/language_ai/`: `answer_pairs.json`, `synthetic_prompt_bank.json`, `rating_controls.json` (synthetic, engineering translations).
New scripts: `scripts/language_rating_harness.py`, `scripts/eval_language_ai_behaviour.py` (9 checks; one new CI step); `scripts/eval_i18n_l10n.py` gains one check, `localized_policy_sentences_complete` (added only, nothing loosened).
New docs: this file, `06C_RATING_PROTOCOL.md`, generated `06C_POLICY_SENTENCE_INVENTORY.md` (regenerate with `python scripts/eval_language_ai_behaviour.py --write`; a test fails if it drifts).
`.github/workflows/ci.yml`: one new evaluator step.

Not touched: `src/agent/*`, `src/copilot/security/*`, `src/security.py`, the frontend, catalogues (so `06A_LOCALE_AUDIT.md` is not regenerated: no catalogue key added), migrations, the tracker, the register, `language_readiness.json`.

## 4. Behaviour changes the lead should know

- A model that advertises structured outputs but returns a fenced or prefixed JSON object now costs one extra call (strict call, then the defensive primary) instead of being accepted by string extraction. Both calls are billed once and counted; the result is still validated.
- A provider that honours the strict schema can no longer return a localized `question_type` or `difficulty`; before, an unconstrained string was allowed.
- A boolean in a score field now fails validation (and so triggers the existing fallback or repair) instead of recording 1 or 0.

## 5. Security and privacy impact

No new data, table, migration, secret, provider call, network call or environment read. The rating packet is synthetic only and the reviewer folder is blinded (a test scans it for the seed, the key, task labels, control names, model and profile words; whole-word match so Dutch "gecontroleerd" is not a false positive). Model text that begins with a formula character gets a leading apostrophe so a spreadsheet cannot execute it. The harness source contains no import of an HTTP, provider or model module and no environment or credential read (a test asserts it). The aggregation cannot approve: `approved` is always false and there is no PASS value in the code.

## 6. Tests and commands

All commands were run from the worktree with the repo venv (`PY` = `.venv/bin/python`, a symlink to the repo venv) and `-p no:cacheprovider`; the fresh-dependency canary `$HOME/.cache/ask4mo/ci_venv/bin/python` exists and was used for the targeted tests.

| Command | Result |
|---|---|
| `PY -m pytest tests/test_language_policy_06c.py tests/test_scoring_invariance_06c.py tests/test_structured_output_06c.py tests/test_policy_sentence_inventory_06c.py tests/test_language_rating_harness_06c.py` | **550 passed** (421 policy suite, 17 scoring invariance, 61 structured output, 25 sentence inventory, 26 rating harness), repo venv and canary |
| Same five files plus `tests/test_prompt_assets_01b.py tests/test_interview_service.py tests/test_response_parser.py` on the canary | passed |
| `PY -m ruff check .` | clean (two unused imports in my own new files were fixed) |
| `PY scripts/ci_test_shards.py verify --shards 4` | OK: 305 test files, each in exactly one of 4 shards |
| All 48 evaluators that `.github/workflows/ci.yml` runs (`scripts/eval_*`, run with the CI arguments, including the new `eval_language_ai_behaviour.py`) | all passed, none dirtied the working tree |
| `PY scripts/eval_language_ai_behaviour.py` | 9 of 9 checks (directives, prompt_parity, coaching_style, grounding_parity, structured_output, scoring_invariance, sentence_inventory, rating_harness, gates_not_approved) |
| `PY scripts/eval_i18n_l10n.py` | PASS, with the added `localized_policy_sentences_complete` check |
| `PY scripts/language_rating_harness.py selftest` | selftest OK: 7 languages, status SELFTEST_ONLY, approved=False |
| **Full backend suite** `PY -m pytest -n 3 --dist loadfile -q` (once, on the final tree) | **6868 tests, 0 failures, 0 errors, 41 skipped** |

One earlier full run had exactly one failure, `tests/test_language_readiness_06a.py::test_committed_audit_table_is_current_...`: it needs `frontend/node_modules` (esbuild) and this worktree has none. It is environmental, not a regression; with `frontend/node_modules` symlinked to the main checkout (never committed) the same test passes in the final run. The 41 skips are existing skips (dormant Russian live-UI tests, node and browser availability); none was added or changed by this package.

Mutation checks I ran while writing the tests (each made a test fail, then was reverted): the boolean-score refusal before the `Field` bounds (the strict schema lost `minimum`/`maximum`; caught by the new schema test), a blinding scan that matched the Dutch word "gecontroleerd" as "control" (made whole-word).

## 7. Risks and limitations

- The policy suite proves identical BEHAVIOUR of the deterministic policy layers and identical PROMPT STRUCTURE across languages. It says nothing about how a live model behaves in each language.
- The detection lexicons are heuristics over seven languages; recall for non-English attacks was measured by the 01A corpus (multilingual 60.7 percent) and is not improved here (F7).
- The scoring-invariance offline result shows the code does not change a score by language. Because the model produces the scores, a language effect inside the model is only measurable live.
- The strict-path change relies on providers returning a pure JSON object when they enforce a schema, which is their contract; a provider that wraps its output pays one extra call.
- Sample sizes in the rating plan (30 model outputs per language, two raters) are proposals and give a coarse estimate.
- The agent-path wiring (F5) and the English-only findings (F6) stay open until the owning packages merge; until then Mo's fallback and card sentences remain English whatever the conversation language.

## 8. Missing human, live and gate evidence

All of the following are NOT RUN / OPEN: the live generation of outputs under the 05C budget marker; the blinded native-reader rating (named reviewers, OD-LANG-03; thresholds, OD-GATE-THRESHOLDS); the live scoring-invariance comparison (`noise_floor` first, then `live_invariance_report` with approved thresholds); native review of every localized sentence (LG-11); the owner decision on multilingual rules for the interview input guard (OD-INPUT-GUARD-LANGUAGES); a named approver, evidence reference, date and release SHA for LG-04 and LG-05 per language (06H).

## 9. Owner decisions needed

1. OD-INPUT-GUARD-LANGUAGES: extend the interview input guard to French, Spanish, Italian, Portuguese and Dutch (route through the existing multilingual scanner, warn then block), accepting the false-positive risk, or accept the structural defence alone.
2. OD-BUDGET for the live generation and OD-LANG-03 for named native reviewers; confirm or change the rating plan sizes and the rubric.
3. OD-GATE-THRESHOLDS: approve, change or reject `LIVE_TOLERANCE_PROPOSED` for the live scoring-invariance check.

## 10. SHA and throughput

- Code commits (before this evidence commit): `09ed870b` inventory and agent-path tables and the Career-chat directive asset, `1363a36a` structured-output gaps, `f66095e6` policy suite and scoring invariance, `00554ddd` rating harness, evaluator and the additive i18n check. The final head SHA (this evidence commit on top) is in the report and verified with `git ls-remote origin feat/06c-language-ai-behaviour`.
- Merged `origin/main` immediately before the final push: main was still at f5cf7cb, so there was nothing to merge and no conflict to resolve. Expected conflicts when other packages land: `prompts/current.json` (one new pointer entry) and the `EXPECTED_FAMILY_COUNT` line in `tests/test_prompt_assets_01b.py`.
- Throughput: started 2026-10-22 07:22 (CEST); first push 07:45 (all four code commits); rework rounds: 2 (the boolean-score validator order dropped the schema bounds and a blinding test matched a Dutch word; both found by my own tests and fixed before the first push).
