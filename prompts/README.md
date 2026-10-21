# Prompt assets

This directory holds the production prompt assets (package 01B, REVIEW-02) in the format defined by
package 01B0. Every model-visible prompt text of the agent (Mo), the interview technique prompts,
the coaching-style directives, the RAG, synthesis and query-understanding prompts, the career
tool prompts and the agent judge prompt is one asset here; code only assembles them. Rendered
output is byte-identical to the former code literals (`tests/test_prompt_byte_identity_01b.py`).
A non-production example tree is in `tests/fixtures/prompts/`.

Families (`<dir>/<name>`), all at `1.0.0`, pinned in `current.json` with their body hash:
`agent/*` (system, response_language, judge, judge_user), `interview/*` (blocks, methods, tasks,
closings, user frames, lookup tables), `coaching/*`, `rag/*`, `career/*`.

Changing a prompt: add a NEW file `<name>.v<next semver>.md` (never edit a released version), run the
tests, then move the pointer in `current.json` in the same reviewed change (a wording change is a
version bump, never an in-place edit; the recorded `sha256` fails the load if a released file is
altered). Rollback is the reverse: point `current.json` back at an earlier approved version, no
code change; it applies on the next process start and the run results, evaluation results and
Prompt Lab records report the effective version and hash. The tree ships in the API image
(`deploy/Dockerfile.api` copies `prompts/` to `/app/prompts`) and the application fails closed at
import if an asset is missing or invalid. Lookup tables (`persona_tone`, `difficulty_rigour`,
`response_detail_length`, `technique_directives`, `coaching/directives`) are `key: value` lines
parsed by `src/prompt_assets.py`.

Contract and loader: `src/prompt_loader.py` (read its module docstring). Summary:

- File: `<root>/<family dir>/<name>.v<semver>.md`; a `---` front matter then the body.
- Front matter keys: `id`, `family` (`dir/name`), `version` (semver, independent of the hash),
  `variables` (`[a, b]`), `compatible_with` (`[consumer-contract-id]`), `description`,
  optional `status` (`approved` default, `draft`, `deprecated`), `deprecated_reason`,
  `rollback_to`, `sha256` (integrity hash of the body, verified at load).
- Body placeholders `{name}` must equal the declared variables; literal braces are `{{ }}`.
- `current.json` pins the approved version per family; rollback is a pointer edit, no code.
- Assets are code-reviewed files. There is no admin free-text editing of system instructions.
