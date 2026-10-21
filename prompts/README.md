# Prompt assets

This directory documents the versioned prompt asset format (package 01B0). It holds **no
production prompt text**: production prompts still live in `src/agent/policies.py`,
`src/prompts.py` and `src/copilot/rag/prompts.py` and are migrated to assets by package 01B.
A non-production example tree is in `tests/fixtures/prompts/`.

Contract and loader: `src/prompt_loader.py` (read its module docstring). Summary:

- File: `<root>/<family dir>/<name>.v<semver>.md`; a `---` front matter then the body.
- Front matter keys: `id`, `family` (`dir/name`), `version` (semver, independent of the hash),
  `variables` (`[a, b]`), `compatible_with` (`[consumer-contract-id]`), `description`,
  optional `status` (`approved` default, `draft`, `deprecated`), `deprecated_reason`,
  `rollback_to`, `sha256` (integrity hash of the body, verified at load).
- Body placeholders `{name}` must equal the declared variables; literal braces are `{{ }}`.
- `current.json` pins the approved version per family; rollback is a pointer edit, no code.
- Assets are code-reviewed files. There is no admin free-text editing of system instructions.
