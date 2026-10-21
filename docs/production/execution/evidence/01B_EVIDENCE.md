# 01B Evidence: externalized, versioned prompts (REVIEW-02)

Package 01B (T1). Requirement IDs: REVIEW-02 R1 (externalize every production prompt), R2 (validated loader, fail closed),
R3 (semantic versions independent of hashes), R4 (SHA integrity retained), R5 (`production_versions()` reports declared version
plus hash), R6 (effective prompt versions recorded on run and evaluation results), R7 (Prompt Lab attribution to exact prompt
version, model and configuration), R8 (rollback = choosing an existing approved version through a reviewed pointer, audited by
git history and visible in attribution; no new application code), R9 (loader, compatibility, missing-version, variable, rollback
and byte-identity tests).

Branch `feat/01b-versioned-prompts`, stacked on `origin/feat/01b0-prompt-contract` (6f6d383). The PR should target `main` after
01B0 merges (or be opened stacked on 01B0). Owner order for shared files: 01B (this package) then 01D then 01C; this package
edited `src/agent/policies.py` and did NOT edit `src/agent/registry.py`, `src/agent/nodes.py`, `src/copilot/security/*`,
`src/knowledge_admin/*`, `.github/workflows/ci.yml`, `frontend/*`, `deploy/docker-compose.staging.yml` or the release tracker.
No Alembic migration. No provider or network call anywhere (tests, evaluators, migration).

## 1. Granularity decisions

One asset is one prompt text that is independently reviewable and versionable. Code keeps only assembly: ordering,
conditionals, allow-lists, and trusted values substituted into declared `{placeholders}`.

| Family group | Granularity | Why |
|---|---|---|
| `agent/system` | ONE asset, no variables | The hand-written tool descriptions stay literal inside it (package 01C will regenerate that section from the registry as a new asset version, for example 1.1.0 with a `{tool_catalogue}` variable). |
| `agent/response_language` | template, `{language_name}` | The name still comes only from the `LANGUAGE_NAMES` allow-list in code. |
| `interview/*` technique prompts | The f-string assemblies are split into the blocks that `_assemble` already joined: `mission`, `guardrails` (`{ref_open}`, `{ref_close}`), `session_parameters` (9 variables), `task_*`, five `method_*`, `output_contract_evaluation` and `output_contract_generic` (`{schema_name}`, `{schema_description}`), `language_directive`, `task_method`, plus `few_shot_example` (static, literal braces escaped). Assembly order and conditionals stay in `src/prompts.py`. | Template-with-declared-variables is the only granularity the 01B0 loader accepts (plain `{name}`, no format specs), and block-level assets keep each wording change a one-file reviewable version bump. |
| Interview lookup phrases | `persona_tone`, `difficulty_rigour`, `response_detail_length`, `technique_directives`, `coaching/directives` are table assets (`key: value` lines, parsed by `src/prompt_assets.parse_table`) | Same wording must be versionable but is looked up by an allow-listed key. |
| Interview user-message frames | `user_frame_evaluation`, `user_frame_task`, `closing_*` (the untrusted body is a variable; braces inside the body are not re-interpreted) | These sentences are model-visible instructions. |
| `coaching/wrapper` | template, `{directive}` | Moved from `src/coaching_style.py`. |
| `rag/*`, `career/*`, `agent/judge*` | one asset per system prompt or fixed user frame; the localized variables (`insufficient`, headings, intents) stay variables | `src/copilot/rag/localized.py` (per-language headings and sentences) is untouched: it is package 06C scope. |

44 families, all `1.0.0`, pinned in `prompts/current.json` with `{version, sha256}`, and each file also records `sha256` in its
front matter (two integrity checks). Consumer contract ids (`compatible_with`): `agent.policies`, `agent.judge`,
`interview.prompts`, `coaching.style`, `rag.prompts`, `rag.synthesis`, `rag.translation`, `career.tools`.

## 2. Byte-identity proof (the acceptance bar)

Oracle: `tests/fixtures/legacy_prompts/` holds verbatim copies of the nine pre-migration modules (frozen from the 01B0 base),
so the proof does not depend on the code under test. `tests/test_prompt_byte_identity_01b.py` compares the live asset-backed
consumer with the legacy one on every family and branch, and also pins SHA-256 digests of the six static prompts independently of
the oracle copies. Result: no byte-identity gap found; every comparison passes.

| Family | Test (all in `test_prompt_byte_identity_01b.py`) | Branches covered |
|---|---|---|
| `agent/system` | `test_agent_system_prompt_is_byte_identical_and_pinned` | text equality plus pinned SHA-256 `72f03d81...` |
| `agent/response_language` | `test_agent_language_directive_every_branch` | every locale code, upper/lower/padded codes, blank, unknown, injection string, English (no directive) |
| interview five techniques, system + user | `test_five_technique_system_prompts_and_user_messages` | 5 techniques x 6 configs (personas, difficulties, details, levels, 1 to 4 interview types, braces and unicode in free text) x 3 question/answer shapes, also `build_messages` |
| interview static blocks and tables | `test_interview_static_pieces_and_tables_are_identical` | mission, guardrails, task, all lookup tables, few-shot example, output contract |
| interview task output contracts | `test_task_output_contracts_per_schema` | all 5 task schemas |
| interview task system prompts | `test_task_system_prompts_every_language_and_style` | 5 tasks x 5 techniques x 3 configs x every language branch (incl. unknown/injection) x 7 coaching-style branches |
| interview task user messages | `test_task_user_messages_every_argument_shape` | 5 tasks x 4 configs x 6 argument shapes (previous Q/A/summaries, question number 0 and 4, branch mode/depth blank and set), also `build_task_messages` |
| coaching style | `test_coaching_style_directive` | all styles, blank, unknown, padded, uppercase |
| RAG baseline | `test_rag_baseline_prompts` | rendered text, pinned SHA-256, template constant, user frames with and without context |
| RAG synthesis | `test_synthesis_template_and_messages_every_language` | template constant, pinned SHA-256, every language, synthesis and evidence message builders |
| query understanding | `test_query_understanding_prompts` | 0, 2, 4 alternates; quote, brace and unicode in the user query |
| career tools | `test_career_tool_prompts` | job analysis with/without/odd focus; question generation default and full args; pinned SHA-256 |
| agent judge | `test_judge_prompts` | system prompt, pinned SHA-256, user message with unicode and nested material |

`production_versions()["prompt_version"]` is asserted equal to the historical `prompt-72f03d8133c3` (hash of the unchanged system
prompt), so the existing key keeps its exact meaning.

Known limits of the proof, stated plainly: the provider-visible message list for the agent is built in `src/agent/nodes.py`
(not edited): it still reads `SYSTEM_PROMPT` and `response_language_directive()` from `policies.py`, both proven identical. The
synthesis and evidence block LABELS (for example `[RETRIEVED EVIDENCE]`) and the per-turn memory block text stay in code;
only the system prompts and the fixed interview/RAG user frames moved.

## 3. Behaviour and security impact

- Fail closed: `src/prompt_assets.py` validates the whole tree eagerly on first use (policies is imported at app start, so a
  missing or tampered asset stops startup with a `PromptError` naming the family). There is no literal fallback anywhere
  (`test_no_production_module_keeps_a_literal_prompt_fallback`), so a corrupted tree can never silently serve a different prompt.
- Integrity: the front-matter hash and the `current.json` pointer hash are verified (`test_tampered_asset_fails_integrity`,
  `test_pointer_hash_mismatch_is_refused`); drafts never resolve; unknown consumer ids raise `IncompatiblePrompt`.
- No Admin free-text editing: assets are repository files, the loader has no write path and `src/prompt_assets.py` has no
  environment override of the asset root. Rollback is a reviewed edit of `prompts/current.json`.
- Untrusted text is only ever a variable value (`body`, `question`, `query`, `material_json`); `str.format` never re-parses
  substituted values, and the byte-identity tests include brace-bearing free text. Placeholders are plain identifiers only.
- Privacy: attribution records family, version and body hash only, never prompt text (asserted for production_versions, run
  results and technique attribution). The hash of a static public-repository prompt is not sensitive.
- Packaging: `deploy/Dockerfile.api` had no wildcard copy of the repo tree (`COPY src`, `migrations`, `scripts`, `alembic.ini` only),
  so one line `COPY prompts ./prompts` was added (PROMPT_ROOT is `<parent of src>/prompts` = `/app/prompts`); `.dockerignore` does not
  exclude it; `test_prompt_root_is_next_to_src_and_shipped_in_the_api_image` guards both. The image was not built here (no Docker run).
  `deploy/docker-compose.staging.yml` was not edited.

## 4. Attribution (R5, R6, R7)

- `src/config_versions.production_versions()`: the four original keys unchanged; added `prompt_assets`
  (`{family: {version, sha256}}`) and `prompt_set_version` (a flat `promptset-<12hex>` over every `family@version#sha`). The reviewer
  route `GET /reviewer/config-versions` returns it unchanged (existing `prompt_version.startswith("prompt-")` test passes).
  `tests/contracts/test_prompt_loader_01b0.py::test_production_versions_not_wired` asserted the pre-01B state and was replaced by
  `test_production_versions_wired_by_01b_keeps_the_original_keys` (this is the only 01B0 test changed).
- `AgentRunResult.prompt_versions` (domain result, not added to the API schema: the OpenAPI/TS contract is unchanged; Admin AI
  operations in package 03D can surface it): `agent/system` always, `agent/response_language` only when a directive was added,
  `coaching/wrapper` and `coaching/directives` only when a coaching style was applied, and the prompt families of the model-backed
  tools that actually executed (`AnalyzeJobDescription`, `GenerateInterviewQuestions`). Built in `agent_service._to_result`.
- Evaluation results: `src/agent/eval.py` per-case results carry `prompt_versions` and the metrics dict carries the merged set;
  `src/prompt_registry.technique_prompt_versions(technique, config, task)` attributes interview technique prompts (conditional
  families only when the config renders them).
- Prompt Lab: `ExperimentRun` gains `prompt_assets` (version + hash per family), `model_profiles` (effective model id per Fast,
  Balanced, Advanced from the registry, no provider call) and `configuration_sha256` (canonical hash of the variant config);
  `production_versions` stays a flat string map and now also holds `prompt_set_version`. Fields default empty so experiments
  stored before 01B still load (tested).

## 5. Rollback (R8) and tests

`test_pointer_change_rolls_back_and_forward_with_attribution_and_no_code_change`: with only file edits (a new
`agent/response_language` 1.1.0 asset and a `current.json` pointer move) the rendered directive and the effective version/hash
change, `run_prompt_versions` reports 1.1.0, and moving the pointer back restores the original text and hash exactly. Also tested:
`prompt_set_version` changes and restores, highest approved semver wins without a pointer (1.10.0 > 1.2.0), drafts never resolve.
Limits: the cached loader makes a pointer change effective on the next process start (by design, so the version recorded on a run
is always the version that produced its text); module-level constants (`SYSTEM_PROMPT`) are fixed at import. R8 "governed
configuration mechanism" is satisfied only as far as the reviewed repository pointer file; no Admin-operated rollback control or
runtime audit event was added (that would be new application code, outside this package).

## 6. Files

Added: `prompts/**` (44 assets, `current.json`), `src/prompt_assets.py`, `tests/test_prompt_byte_identity_01b.py`,
`tests/test_prompt_assets_01b.py`, `tests/fixtures/legacy_prompts/*` (oracle copies), this file.
Changed: `src/agent/policies.py`, `src/agent/models.py`, `src/agent/judge.py`, `src/agent/eval.py`, `src/application/agent_service.py`,
`src/prompts.py`, `src/prompt_registry.py`, `src/coaching_style.py`, `src/config_versions.py`, `src/copilot/rag/{prompts,synthesis,translation}.py`,
`src/copilot/tools/{job_analyzer,question_generator}.py`, `src/application/prompt_lab/{models,service}.py`, `deploy/Dockerfile.api` (one COPY line),
`scripts/eval_i18n_l10n.py` (reads the directive asset instead of policies.py source), `prompts/README.md`,
`tests/contracts/test_prompt_loader_01b0.py` and `tests/test_evaluation_contract.py` (each asserted the pre-migration state).

## 7. Tests and commands

Interpreters: repo `.venv` (Python 3.11.15) and the fresh-install canary `/tmp/ci_venv` (Python 3.11.15). The `python` stub issue seen in
01B0 did not recur. All commands run from the worktree; CI shards use `-n 2 --dist loadfile`, local runs used `-n 6 --dist loadfile`.

| Command | Interpreter | Result |
|---|---|---|
| `pytest tests/test_prompt_byte_identity_01b.py tests/test_prompt_assets_01b.py` (new: 99 byte-identity + 23 asset/attribution tests) | repo `.venv` | all passed |
| `pytest tests -n 6 --dist loadfile` (FULL backend suite) | repo `.venv` | 5286 passed, 41 skipped, 0 failed (2m53s) |
| `pytest tests -n 6 --dist loadfile` (FULL backend suite) | `/tmp/ci_venv` | 5284 passed, 43 skipped, 0 failed (4m03s) |
| `ruff check .` | repo `.venv` | All checks passed |
| `python scripts/ci_test_shards.py verify --shards 4` | repo `.venv` | OK, 268 test files, each in exactly one shard |
| `scripts/eval_agent.py` (deterministic orchestration gate) | repo `.venv` and `/tmp/ci_venv` | GATE STATUS: PASS |
| `scripts/eval_i18n_l10n.py` | repo `.venv` and `/tmp/ci_venv` | PASS (reads the directive asset now) |
| `scripts/eval_prompt_lab.py` | repo `.venv` | GATE STATUS: PASS |
| `scripts/eval_prepare_practice_integration.py`, `scripts/eval_onboarding_personalisation.py` | repo `.venv` | PASS (0 paid, 0 live calls) |

Between the two full runs the venvs differ by 2 skips (environment-conditional tests); no failure in either.

Regression evidence (existing suites, all inside the full runs above): `tests/test_prompts.py`, `test_prompt_lab_p6.py`,
`test_prompt_comparison.py`, `test_wave2_coaching_style.py`, `test_wave4_practice_language.py`, `test_w97_russian_locale.py`,
`test_conversation_language.py`, `test_w97a_career_language.py`, `test_candidate_grounding_policy.py`, `test_agent_identity.py`,
`test_agent_judge.py`, `test_agent_tool_selection.py`, `test_reviewer_api_p6.py`, `test_copilot_rag.py`, `test_security_ph6.py`,
`test_model_profile_entitlements_p2c.py`, `test_platform_config_w10_11.py`, `test_ai_admin_w10_7.py`, `test_reporting_w10_12.py`.

A first full run (before the test fixes) found exactly two failures, both tests that asserted the PRE-migration state, and both were
corrected in the same branch before the first push: `tests/contracts/test_prompt_loader_01b0.py::test_production_versions_not_wired`
(01B0 deliberately asserted the wiring was absent) and `tests/test_evaluation_contract.py::test_overall_and_criteria_are_independent_...`
(grepped the prompt text out of `src/prompts.py` source; it now checks the rendered method block). No test was weakened: each now asserts
the same property against the new location.

SHA and CI: see the final report (branch tip) and the throughput record below.

## 8. Remaining risks

- Interview session records and interview evaluation/report results do not yet store the effective prompt versions (the session
  codec and `InterviewConfiguration` are outside this package; `technique_prompt_versions` provides the data when a later package
  wires it). Mo run results and agent evaluation results do.
- Block labels in synthesis (`[USER QUESTION]`, `[RETRIEVED EVIDENCE]`, ...), the specialist prompts and the per-turn memory
  framing remain in code; the synthesis system prompt references those labels, so a future label change needs the paired asset bump.
- `agent/system` keeps the hand-written tool descriptions, so the registry-parity (01C) and tool-authorization (01D) work still has to
  change that asset (a new version) and `policies.py`; this package intentionally does not pre-empt them.
- Front matter parser is minimal (single-line scalars): descriptions cannot span lines; maintainers must update both the file hash and the
  pointer hash when adding a version (a wrong hash fails the load, so an error is loud, not silent).
- The hash covers the body only (front matter such as `variables` and `compatible_with` is validated, not hashed).
- Docker image build and a staging boot were not executed here (static packaging check only); live behaviour with a real model is
  unchanged by construction but not exercised.

## 9. Throughput record

- Start 2026-10-21T18:28Z (`date -u` at first command); implementation and verification complete 2026-10-21T18:57Z.
- Estimate 5 to 8 engineering days (register); actual agent wall-clock about 30 minutes, including two full-suite runs per interpreter
  budget (one aborted run, one with two real failures, one clean run per venv). The estimate covers human review and integration time.
- Rework rounds (fix commits after first push): 0 (the first push is the verified tree; the two test corrections preceded it).
- CI duration: not available (CI runs only once a PR exists; none was opened by this agent).
