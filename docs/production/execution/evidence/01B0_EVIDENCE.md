# 01B0 Evidence: prompt asset format and loader contract

Package: 01B0 (interface package, T1). Requirement IDs: REVIEW-02 R1 (externalize, contract part), R2 (validated loader),
R3 (semantic versions independent of hashes), R4 (SHA retained for integrity), R7-contract (attribution needs a declared
version plus hash; `declared_versions_with_hash()`), R9 (variable, compatibility, missing-version, rollback tests, against fixtures).
Not in scope here (01B): R1 migration, R5 `production_versions()` wiring, R6 run-result recording, R8 governed rollback selection.

Branch `feat/01b0-prompt-contract`, base `origin/main` 38eabbc. No prompt text moved, no wording or behaviour change.

## 1. Audit: production prompt families and consumers

| Family | Where defined | Consumer | Template variables / assembly | Declared version identity today | Hash computed today |
|---|---|---|---|---|---|
| Agent system prompt (Mo) | `src/agent/policies.py` `SYSTEM_PROMPT` (plain string, no placeholders) | `src/agent/nodes.py` (`SystemMessage(content=SYSTEM_PROMPT)`); `config_versions.prompt_version` | none; language added by `response_language_directive(code)` (allow-list names only) appended at run time | none | `config_versions._short` (sha256 first 12 hex of the text) -> `"prompt-<12hex>"` in `production_versions()` |
| Mo response-language directive | `src/agent/policies.py` `response_language_directive` | `src/agent/nodes.py` | `{name}` from `LANGUAGE_NAMES` (code f-string) | none | none |
| Interview technique prompts (5) | `src/prompts.py` builders (`_zero_shot`, `_role_persona`, `_few_shot`, `_structured_procedure`, `_rubric_json`) via `SYSTEM_PROMPT_BUILDERS`; metadata in `src/prompt_registry.py` `PromptTechniqueSpec` | `src/prompts.build_system_prompt`, interview service, Prompt Lab prompt comparison | assembled by f-strings from `InterviewConfiguration` (session parameters, schema description, output contract), not `str.format` | technique id only (no version) | none (not covered by `prompt_version`) |
| Interview task prompts | `src/prompts.py` `build_task_system_prompt`, `_TECHNIQUE_DIRECTIVES` | interview service | f-strings | none | none |
| Interview language directive | `src/prompts.py` `_language_directive` | all interview task prompts | f-string name from allow-list | none | none |
| Coaching-style directives | `src/coaching_style.py` `_DIRECTIVES`; applied via `src/prompts._coaching_directive` | feedback/report tasks, Prepare chat | fixed text, no variables (allow-listed code) | none | none |
| RAG baseline system prompt | `src/copilot/rag/prompts.py` `_SYSTEM_PROMPT` | `system_prompt()` / `build_messages` | `{insufficient}` via `str.format` | none | none |
| RAG synthesis prompt | `src/copilot/rag/synthesis.py` `SYNTHESIS_SYSTEM_PROMPT` | Career chat synthesis | `str.format` with `{insufficient}`, `{h_evidence}`, `{h_tools}`, `{h_reco}` etc. | none | none |
| RAG query-understanding prompt | `src/copilot/rag/translation.py` `_SYSTEM_PROMPT` | query translation | `str.format` | none | none |
| Career tool prompts | `src/copilot/tools/job_analyzer.py`, `question_generator.py` (`{categories}`, `{per_category}`) | Career tools | `str.format` | none | none |
| Agent judge prompt | `src/agent/judge.py` `JUDGE_SYSTEM_PROMPT` | agent evaluation | none | none | none |

Conclusions: only the agent system prompt has any identity, and it is a content hash with no declared version. Every other
family has no version identity. Hashes are computed in exactly one place (`src/config_versions.py`).

Compatibility constraints for 01B:
- Rendering must stay byte-identical for default configs. The loader renders with `str.format_map`, equal to `str.format`
  for plain `{name}` placeholders; literal braces must be written `{{ }}` in assets (RAG prompts already do this where needed).
- Interview technique prompts are f-string assemblies, not templates: 01B should store the static blocks as assets and keep
  config-dependent assembly in code, or split into several assets with declared variables. The loader forbids format specs,
  conversions and attribute/index access in placeholders by design.
- The Prompt Lab and `production_versions()` currently expose `prompt_version` as `"prompt-<12hex>"`. 01B must keep that key
  stable and add declared version plus hash alongside (parity test), not replace it silently.
- The REVIEW-02 example names (`system.v3.md`, `rubric_json.v2.md`) are examples only. No asset has an actual version history:
  initial versions should be `1.0.0`. The contract uses `<name>.v<MAJOR.MINOR.PATCH>.md` (superset; `v3` shorthand is not accepted).

## 2. Contract summary (`src/prompt_loader.py`, documented in the module docstring)

- Asset: `---` front matter (`id`, `family` `dir/name`, `version` semver, `variables`, `compatible_with`, `description`,
  optional `status` approved|draft|deprecated, `deprecated_reason`, `rollback_to`, `sha256`) then the body. No YAML dependency
  (restricted parser, unknown keys rejected).
- `PromptAsset` (frozen): fields above plus `sha256` computed over the UTF-8 body; version and hash are separate and never derived from each other.
- `PromptLoader` protocol: `families`, `versions`, `get`, `resolve(family, version=None)`, `render`, `declared_versions_with_hash`.
- `FilePromptLoader(root)`: eager, fail-closed validation of the whole tree; path must agree with front matter; duplicate versions rejected;
  semver ordering numeric (1.10.0 > 1.2.0); `current.json` pointer (`"1.1.0"` or `{"version","sha256"}`); without a pointer the highest approved version is current;
  drafts never resolve; recorded hashes (front matter or pointer) are verified.
- Errors: `MissingPromptVersion`, `InvalidPromptAsset` (schema, placeholder mismatch, integrity), `VariableMismatch`, `IncompatiblePrompt` (`asset.check_compatible(consumer_id)`).
- `render`: rejects missing and unknown variables; values stringified; no network, no provider.
- `declared_versions_with_hash()` -> `{family: {"version", "sha256"}}`, NOT wired into `production_versions()` (asserted by a test).
- Rollback to an earlier approved version is a `current.json` edit, no code change.

## 3. Security impact

- No write path in the loader and no Admin free-text editing of system instructions: assets are code-reviewed files.
- Integrity hash verified at load (front matter) and at resolve (pointer); mismatch refuses the asset.
- Placeholders restricted to plain identifiers (blocks attribute/index traversal such as `{a.__class__}` in templates).
- Values are never evaluated; the loader makes no network or provider call (test patches sockets to fail).
- No production prompt text added; fixtures are neutral demo strings.

## 4. Files

Added: `src/prompt_loader.py`, `prompts/README.md`, `tests/fixtures/prompts/**` (5 assets + `current.json`),
`tests/contracts/__init__.py` (empty), `tests/contracts/test_prompt_loader_01b0.py`, this evidence file.
Not touched: policies.py, registry.py, nodes.py, prompts.py, rag/prompts.py, config_versions.py, CI, deploy, frontend, migrations, tracker.

## 5. Tests and commands

Interpreter fault (Homebrew stub overwritten by a shell wrapper at about 18:06Z, repaired by the coordinator) delayed the first full run; no source was affected.

| Command | Interpreter | Result |
|---|---|---|
| `pytest tests/contracts tests/test_prompts.py tests/test_prompt_lab_p6.py tests/test_prompt_comparison.py` plus the config-version tests (`test_model_profile_entitlements_p2c`, `test_platform_config_w10_11`, `test_ai_admin_w10_7`, `test_reporting_w10_12`) | repo `.venv` | 462 passed |
| same | `/tmp/ci_venv` (fresh-install canary) | 462 passed |
| `pytest tests/contracts --noconftest` (42 contract tests) | system `/usr/bin/python3` 3.9.6 | 42 passed |
| `ruff check .` | repo `.venv` | All checks passed |
| `python scripts/ci_test_shards.py verify --shards 4` | `/tmp/ci_venv` | OK, 266 test files, each in one of 4 shards |

The full backend suite was not run locally; CI runs it once a PR exists.

## 6. Remaining risks

- Interview prompts are f-string assemblies; 01B must decide the asset granularity (static blocks vs full templates) and prove byte-identity.
- Front matter parser is deliberately minimal (single-line scalars, `[a, b]` lists); descriptions cannot span lines.
- Pointer `current.json` is the rollback mechanism at file level; 01B's governed-configuration rollback (REVIEW-02 R8) is not delivered here.
- Hosted packaging: assets must ship in the Docker image (`deploy/` is out of scope for 01B0); 01B must verify the path resolves in the image.
- Hash scope is the body only; front matter (version, variables) is not covered by the hash.

## 7. Throughput record

- Start 2026-10-21T18:03Z; verification complete about 18:25Z (about 22 minutes agent wall-clock, including the environment fault).
- Estimate 2-3 engineering days (covers human review and integration); actual agent authoring and verification well under one hour.
- Rework rounds (fix commits after first push): 0 code fixes; one evidence-only update commit after verification.
- CI duration: not available (no PR opened by this agent; CI runs only once a PR exists).
