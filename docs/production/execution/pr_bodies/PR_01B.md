# 01B: Versioned prompt assets and run attribution (REVIEW-02 part 1)

**Branch:** `feat/01b-versioned-prompts`  **Head SHA:** `7c2b8791725a83e21d9f0eb521a765b39e079a28`  **Compare URL:** https://github.com/moaltamimi-unbiasedtalent/Intelligent-Interview-Coach/pull/new/feat/01b-versioned-prompts
**Stacked on:** `feat/01b0-prompt-contract` (6f6d383). Open after 01B0 merges, or stacked on it.

## Requirements and package IDs
Package 01B. REVIEW-02 R1 to R7 (R8 rollback is pointer-edit only; no Admin control). Depends on 01B0.

## Change summary
44 prompt families moved to versioned assets under `prompts/` (all 1.0.0, pinned in `current.json` with sha256); `src/prompt_assets.py` is the only access path (eager validation, fail closed, no literal fallback); consumers switched with identical module constants; `production_versions()` keeps its 4 keys and adds `prompt_assets` and `prompt_set_version`; agent run results, agent eval and Prompt Lab runs carry prompt versions and hashes (never text); `COPY prompts ./prompts` added to `deploy/Dockerfile.api`. No migration, no API schema change, no live model call.

## Acceptance criteria
Rendered prompts byte-identical to pre-migration; every run attributable to prompt versions; rollback by pointer edit restores the original exactly; tampered or mismatched assets fail loudly; agent/system stays one asset so 01D and 01C can cut new versions.

## Tests and evidence
Byte-identity: 99 tests against verbatim legacy copies plus 23 asset tests. Full backend suite: 5286 passed, 41 skipped on the repo venv; 5284 passed, 43 skipped on the fresh venv; 0 failed. ruff, shard plan, eval_agent and eval_i18n_l10n pass. Evidence: docs/production/execution/evidence/01B_EVIDENCE.md. GitHub CI not yet run.

## Risks and limitations
Interview session and evaluation records do not yet store prompt versions; synthesis labels and specialist prompts remain in code; rollback needs a process restart and is git-audited only; Docker image build not executed; one 01B0 test was updated because 01B wires `production_versions()`.

## Dependency and merge order
After 01B0. Shared agent-policy order 01B, then 01D, then 01C.
