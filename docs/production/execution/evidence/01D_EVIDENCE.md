# 01D Evidence: server-side tool-call authorization layer (REVIEW-01 R4 and R5; PG-03)

Branch `feat/01d-tool-authorization`, base `origin/main` f5cf7cb (Alembic head 0043_story_bank_completion; no migration in this package). Status of the gate: PG-03 is NOT claimed met. This package delivers the engineering controls and negative tests for R4 and R5; R1 to R3 and R6 are 01A, the owner-approved thresholds (OD-GATE-THRESHOLDS) and the human security review are still missing.

## Requirement mapping

| Requirement | Covered | How | NOT covered |
|---|---|---|---|
| R4: a model-requested tool call is re-authorised server-side (goal, user authorization, tool permission, allowed arguments) before execution | Yes, in code and offline tests | `src/agent/tool_authorization.py` (`ToolAuthorizer.decide`) is the single decision; `ToolRegistry.validate_and_run` is the only path to a handler and refuses without an ALLOW decision bound to the exact tool and arguments. The graph tools node decides every call from trusted run state before execution | Live-model behaviour (no paid call was made); durable `audit_events` row per decision (see below) |
| R5: malicious source content cannot trigger an unauthorised tool call or cross-user disclosure (negative tests) | Yes, offline | Negative tests listed under "Tests"; provenance and taint rules refuse state-changing or egress calls whose arguments were copied from untrusted text, and refuse any state-changing call in a run with quarantined or high-risk retrieved content unless the user's own words cover it | Paraphrased injections that influence a call without copying text and without a flagged retrieval are bounded by the structural controls only (see "Risks") |
| Decision over the authenticated user from the run, never from model arguments | Yes | `RunAuthContext.user_id` comes from `state["user_id"]`; an undeclared argument that is identity- or resource-like (`user_id`, `ownerId`, `document_id`, `workspace`, ...), structured (object or list), or part of a flood of more than 5 undeclared keys is refused (`unknown_argument`); a harmless undeclared scalar is ignored by the tool exactly as before | |
| Decision over the user's goal/intent | Yes | `user_text` = goal plus later user turns (never the memory block, JD, background or tool output); a side-effecting call with no user words is refused; in a tainted run the user's words must match the tool's intent lexicon in the seven product languages | The lexicon is a coarse word-prefix list, not language understanding |
| Tool permission and side-effect class | Yes | `ToolPolicy` per tool in code (`DEFAULT_POLICIES`): `read_only`, `state_proposing`, `external`; permissions `agent.tool.read|owner_data|propose|external`, derived from the authenticated identity | Per-plan or per-entitlement permission grants (not requested) |
| Argument shape and bounds | Yes | Pydantic model of each tool (unchanged) plus global limits: 40 000 chars total, 20 000 per string, 100 items per collection, depth 5, JSON types only, boolean-for-number refused, unknown fields refused, object-shaped arguments only | |
| Ownership of every referenced resource id | Framework yes; no current use | `ToolPolicy.resource_args` + injectable `ownership_verifiers`; a declared resource argument with no verifier, a failing verifier, a foreign id, an anonymous user or a nested/type-confused id is refused. **No registered tool accepts a resource id today** (specialists read only the trusted run user), so this is enforced for tools added later and proven with a test tool | Real verifiers for documents, stories, opportunities, interviews and memory are not wired because no tool takes them |
| Run state (cancelled/expired) | Yes | `state["cancelled"]`, `state["deadline_epoch"]`, and an injectable live probe `ToolAuthorizer(run_control=...)` (for 04C to wire durable cancellation) | Nothing in the product sets `cancelled`/`deadline_epoch` yet: cancellation and timeouts are REVIEW-04 R4, a later package; this package only makes every tool call honour them |
| Per-run call budget and loop limits | Yes | 60 attempted calls per run (allowed or refused), 8 per tools step, 3 identical calls (tool + canonical arguments) per run; the existing `MAX_AGENT_STEPS` per-turn bound is unchanged | |
| Injection risk of the context that led to the call | Yes | `SearchCareerKnowledge` copies the 01A screen result (`quarantined_chunks`, `flagged_chunks`, `max_chunk_injection_risk`, a blocked query counts as risk 1.0) into `state["untrusted_context"]` (counts and a number only) | `ResearchCurrentMarket` and `FindCandidateEvidence` carry no injection score; their outputs are treated as untrusted text for provenance only |
| Default deny | Yes | unregistered or disabled tool, no policy, schema fingerprint changed after registration, unknown identity-like field, cross-user or unproven id, argument copied from untrusted context: refused, handler never reached | |
| Audit record per decision | Yes | One record per decision: `run_id, step, call_index, tool (registered name or "unregistered"), side_effect, allowed, reason, tainted`. Written to the run's checkpoint state (`tool_authorization`, bounded 200), the logger `ask4mo.agent.tool_authorization`, and an optional injectable sink. Never arguments, never user text, never a fingerprint | A durable, queryable `audit_events` row (needs a DB handle in the agent layer, `src/application/*` wiring and a canonical event name in `admin_audit.py`: left to the owner, see questions) |
| Structured result to the model never reveals another user's data or policy text | Yes | A refusal returns only `{"error": <fixed message>, "code": <not_available|invalid_arguments|limit_reached|run_not_active|not_permitted>}`; an unknown/disabled tool and invalid arguments keep their previous exact messages | |
| No change to tool set, descriptions or model-visible schemas | Yes | 11 tools, descriptions and JSON schemas untouched (a test asserts no `additionalProperties` was introduced); `eval_agent` and the 56 tool-selection cases unchanged and passing | |

## Design in one page

`decide(name, raw_args, run, spec)` is pure over its inputs and runs the checks in this order, stopping at the first refusal: run state; registry membership and per-run disabled tools; declared policy; pinned schema fingerprint (SHA-256 of the argument JSON schema taken at registration, recomputed per call); raw shape and bounds; loop limits; identity and permission; unknown fields and Pydantic validation and boolean type confusion; resource ownership; goal and context taint.

Taint rules (order matters): (1) a state-changing or external call needs a non-empty user goal; (2) an argument that looks like a URL, host or address and appears in untrusted text but not in the user's text is always refused (`untrusted_destination`, the exfiltration channel), even when the goal covers the tool; (3) any other argument copied from untrusted text (a 5-word window, or a 14-character value, present in untrusted text and absent from the user's text and the user's approved memory) is refused unless the user's goal covers the tool intent; (4) in a run with quarantined chunks or a retrieval risk of 0.5 or more, a state-changing or external call needs the user's goal to cover its intent. Untrusted text = the outputs of `SearchCareerKnowledge`, `ResearchCurrentMarket`, `FindCandidateEvidence`, the job description and the candidate background. The user's own approved saved memory is data but is not treated as a stranger's text (otherwise re-proposing a saved memory would be refused).

Human approval path: the memory write in `human_review` is the only state change a tool call can lead to; it now re-checks that the run's trail holds an ALLOWED `ProposePreparationMemory` decision and a trusted owner, so a forged `memory_candidate` in state is never persisted (`MEMORY_FAILED`, truthful warning). Approval itself is still validated by the service (unchanged).

## Changes

| File | Change |
|---|---|
| `src/agent/tool_authorization.py` (new) | policy table, decision function, audit sink, run-context builder, public denial vocabulary |
| `src/agent/registry.py` | `ToolSpec.schema_sha`, `ToolRegistry.authorizer`, `authorize()`, `validate_and_run(..., decision=, run=)` (only path to a handler), `register(..., policy)`, `career_tool_registry(..., authorizer=)` |
| `src/agent/nodes.py` | tools node decides every call before execution, audit trail, loop fingerprints, taint merge, denied event/history/result; `_memory_write_authorized` before memory persistence |
| `src/agent/state.py` | additive keys: `tool_authorization`, `tool_call_fps`, `untrusted_context`, `cancelled`, `deadline_epoch` |
| `src/agent/tools.py` | `SearchCareerKnowledge` publishes the retrieval's injection summary (`_retrieval_taint`); no change to arguments, description or result |
| `tests/test_tool_authorization_01d.py` (new) | 42 tests |

Behaviour that changed for existing callers: a tool call whose arguments carry an identity-like, structured or excessive set of undeclared fields used to run with those fields silently dropped; it is now refused (`invalid_arguments` to the model). A harmless undeclared scalar (a model inventing a field name; the existing 01B prompt test sends `role` for `target_role`) still runs with the field dropped, as before. Direct `registry.validate_and_run` callers are authorised against the identity in their `ToolContext` only. Per-run budgets (60 calls, 8 per step, 3 identical) are new; none of the existing suites reaches them.

## Security and privacy impact

- No new data is stored beyond the audit trail in the existing checkpoint (identifiers and reason codes) and `untrusted_context` (counts and a number). Argument content and user text never enter audit, logs, events or the model-visible result (tests plant sentinel strings and assert their absence).
- The denial result leaks no policy text, no resource id and nothing about another user; tests assert the fixed vocabulary and absence of policy words.
- Refusing identity-like and structured undeclared fields turns a silent-drop path (`user_id`, `document_id` and similar) into an explicit, audited refusal. Plain undeclared scalars are still dropped by the tool (they cannot influence execution); this was chosen over refusing every undeclared field because a real model invents field names and the existing suite depends on that being tolerated.
- No provider call, no network call, no migration, no new permission (the 44-permission Admin registry is untouched; `agent.tool.*` are agent-layer capability names in code, not Admin permissions).

## Tests (exact commands and results)

Interpreters: repo `.venv` (Python 3.11) and the fresh-dependency canary `$HOME/.cache/ask4mo/ci_venv/bin/python` (exists; used).

| Command | .venv | canary |
|---|---|---|
| `pytest -p no:cacheprovider tests/test_tool_authorization_01d.py` | 42 passed | 42 passed |
| `pytest -p no:cacheprovider -n 3 --dist loadfile tests/test_tool_authorization_01d.py tests/test_agent_*.py tests/test_memory_*.py tests/test_multi_agent_specialists.py tests/test_prompt_assets_01b.py tests/test_injection_corpus_01a.py tests/test_injection_precision_w2_01a.py -o addopts=""` | 527 passed | 527 passed |
| `ruff check .` | All checks passed | n/a |
| `python scripts/ci_test_shards.py verify --shards 4` | OK, 301 files each in exactly one shard | n/a |
| `python scripts/eval_agent.py` | GATE STATUS: PASS (56 cases unchanged; `unregistered_tool_attempts` 9 = the 9 scripted unregistered names, unchanged) | see below |
| `python scripts/eval_multi_agent.py` | GATE STATUS: PASS | see below |

Both `eval_agent` and `eval_multi_agent` pass under the repo venv; the canary was used for the targeted suites above (the evaluators were run under the repo venv only).

## Final verification

| Check | Result |
|---|---|
| FULL backend suite, `pytest -n 3 --dist loadfile -q` (repo venv, one run, after the last code change) | 6319 passed, 41 skipped, 0 failed (12m33s) |
| All 49 CI evaluator commands from `.github/workflows/ci.yml` (`scripts/eval_*`, `gen_*`, `check_*`, one pass after the last code change) | 49 OK, 0 failed |
| `ruff check .` | All checks passed |
| `python scripts/ci_test_shards.py verify --shards 4` | OK, 301 files each in exactly one shard |

Notes on the verification runs: (a) an earlier full run found one real regression, `tests/test_prompt_assets_01b.py::test_agent_run_records_prompts_of_the_model_backed_tools_it_executed` (a scripted call sends the undeclared field `role`; the first version of this layer refused every undeclared field). The cause was fixed in the layer (harmless undeclared scalars are tolerated as before; identity-like or structured ones are refused) and the test was not touched; (b) the same earlier run failed `tests/test_language_readiness_06a.py` only because the worktree has no `frontend/node_modules` (the catalogue helper runs Node); with the main checkout's `node_modules` symlinked (not committed) it passes, and the final full run had the symlink; (c) one evaluator, `eval_platform_admin.py`, aborted once with a native `libc++abi recursive_mutex` error while another suite was running concurrently; it passed alone and in the final pass (environmental, not related to this change); (d) the full suite was run once, with no other suite concurrent.

Throughput: start 2026-10-22 07:22 CEST; first push recorded in the final report; rework rounds after the first full-suite run: 1 (the undeclared-scalar tolerance above). Compare URL: https://github.com/moaltamimi-unbiasedtalent/Intelligent-Interview-Coach/pull/new/feat/01d-tool-authorization
