# 01D Evidence: server-side tool-call authorization layer (REVIEW-01 R4 and R5; PG-03)

Branch `feat/01d-tool-authorization`, base `origin/main` f5cf7cb (Alembic head 0043_story_bank_completion; no migration in this package). Status of the gate: PG-03 is NOT claimed met. This package delivers the engineering controls and negative tests for R4 and R5; R1 to R3 and R6 are 01A, the owner-approved thresholds (OD-GATE-THRESHOLDS) and the human security review are still missing.

## Requirement mapping

| Requirement | Covered | How | NOT covered |
|---|---|---|---|
| R4: a model-requested tool call is re-authorised server-side (goal, user authorization, tool permission, allowed arguments) before execution | Yes, in code and offline tests | `src/agent/tool_authorization.py` (`ToolAuthorizer.decide`) is the single decision; `ToolRegistry.validate_and_run` is the only path to a handler and refuses without an ALLOW decision bound to the exact tool and arguments. The graph tools node decides every call from trusted run state before execution | Live-model behaviour (no paid call was made); durable `audit_events` row per decision (see below) |
| R5: malicious source content cannot trigger an unauthorised tool call or cross-user disclosure (negative tests) | Yes, offline | Negative tests listed under "Tests"; provenance and taint rules refuse state-changing or egress calls whose arguments were copied from untrusted text, and refuse any state-changing call in a run with quarantined or high-risk retrieved content unless the user's own words cover it | Paraphrased injections that influence a call without copying text and without a flagged retrieval are bounded by the structural controls only (see "Risks") |
| Decision over the authenticated user from the run, never from model arguments | Yes | `RunAuthContext.user_id` comes from `state["user_id"]`; every schema-unknown field (including `user_id`, `owner_id`, `document_id`, nested ids) is refused (`unknown_argument`) | |
| Decision over the user's goal/intent | Yes | `user_text` = goal plus later user turns (never the memory block, JD, background or tool output); a side-effecting call with no user words is refused; in a tainted run the user's words must match the tool's intent lexicon in the seven product languages | The lexicon is a coarse word-prefix list, not language understanding |
| Tool permission and side-effect class | Yes | `ToolPolicy` per tool in code (`DEFAULT_POLICIES`): `read_only`, `state_proposing`, `external`; permissions `agent.tool.read|owner_data|propose|external`, derived from the authenticated identity | Per-plan or per-entitlement permission grants (not requested) |
| Argument shape and bounds | Yes | Pydantic model of each tool (unchanged) plus global limits: 40 000 chars total, 20 000 per string, 100 items per collection, depth 5, JSON types only, boolean-for-number refused, unknown fields refused, object-shaped arguments only | |
| Ownership of every referenced resource id | Framework yes; no current use | `ToolPolicy.resource_args` + injectable `ownership_verifiers`; a declared resource argument with no verifier, a failing verifier, a foreign id, an anonymous user or a nested/type-confused id is refused. **No registered tool accepts a resource id today** (specialists read only the trusted run user), so this is enforced for tools added later and proven with a test tool | Real verifiers for documents, stories, opportunities, interviews and memory are not wired because no tool takes them |
| Run state (cancelled/expired) | Yes | `state["cancelled"]`, `state["deadline_epoch"]`, and an injectable live probe `ToolAuthorizer(run_control=...)` (for 04C to wire durable cancellation) | Nothing in the product sets `cancelled`/`deadline_epoch` yet: cancellation and timeouts are REVIEW-04 R4, a later package; this package only makes every tool call honour them |
| Per-run call budget and loop limits | Yes | 60 attempted calls per run (allowed or refused), 8 per tools step, 3 identical calls (tool + canonical arguments) per run; the existing `MAX_AGENT_STEPS` per-turn bound is unchanged | |
| Injection risk of the context that led to the call | Yes | `SearchCareerKnowledge` copies the 01A screen result (`quarantined_chunks`, `flagged_chunks`, `max_chunk_injection_risk`, a blocked query counts as risk 1.0) into `state["untrusted_context"]` (counts and a number only) | `ResearchCurrentMarket` and `FindCandidateEvidence` carry no injection score; their outputs are treated as untrusted text for provenance only |
| Default deny | Yes | unregistered or disabled tool, no policy, schema fingerprint changed after registration, unknown field, cross-user or unproven id, argument copied from untrusted context: refused, handler never reached | |
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
| `tests/test_tool_authorization_01d.py` (new) | 41 tests |

Behaviour that changed for existing callers: a tool call whose arguments carry a field the tool does not declare used to be silently run with the field dropped; it is now refused (`invalid_arguments` to the model). Direct `registry.validate_and_run` callers are authorised against the identity in their `ToolContext` only. Per-run budgets (60 calls, 8 per step, 3 identical) are new; none of the existing suites reaches them.

## Security and privacy impact

- No new data is stored beyond the audit trail in the existing checkpoint (identifiers and reason codes) and `untrusted_context` (counts and a number). Argument content and user text never enter audit, logs, events or the model-visible result (tests plant sentinel strings and assert their absence).
- The denial result leaks no policy text, no resource id and nothing about another user; tests assert the fixed vocabulary and absence of policy words.
- Refusing unknown fields closes a silent-drop path (`user_id`, `document_id` and similar are now explicit refusals and audited).
- No provider call, no network call, no migration, no new permission (the 44-permission Admin registry is untouched; `agent.tool.*` are agent-layer capability names in code, not Admin permissions).

## Tests (exact commands and results)

Interpreters: repo `.venv` (Python 3.11) and the fresh-dependency canary `$HOME/.cache/ask4mo/ci_venv/bin/python` (exists; used).

| Command | .venv | canary |
|---|---|---|
| `pytest -p no:cacheprovider tests/test_tool_authorization_01d.py` | 41 passed | 41 passed |
| `pytest -p no:cacheprovider -n 3 --dist loadfile tests/test_tool_authorization_01d.py tests/test_agent_*.py tests/test_memory_*.py tests/test_multi_agent_specialists.py tests/test_injection_corpus_01a.py tests/test_injection_precision_w2_01a.py -o addopts=""` | 503 passed | 503 passed |
| `ruff check .` | All checks passed | n/a |
| `python scripts/ci_test_shards.py verify --shards 4` | OK, 301 files each in exactly one shard | n/a |
| `python scripts/eval_agent.py` | GATE STATUS: PASS (56 cases unchanged; `unregistered_tool_attempts` 9 = the 9 scripted unregistered names, unchanged) | see below |
| `python scripts/eval_multi_agent.py` | GATE STATUS: PASS | see below |

The two numbers marked "see below" and the all-evaluators and full-suite results are recorded in the "Final verification" section.

What the negative tests prove (all in `tests/test_tool_authorization_01d.py`, spy handlers record any reached call):

- retrieved text instructing a side-effecting tool cannot trigger it: a quarantined retrieval whose source title carries an instruction, then `ProposePreparationMemory` (copied text) and `RequestPracticeHandoff` are refused and `pending_action`/`memory_candidate` stay empty; an exfiltration URL taken from a result is refused even when the goal covers the tool; the user's own goal covers a tainted non-destination call (positive control);
- every DEVELOPMENT-split attack text of the 01A corpus (127 attacks) placed in a tool result cannot drive a memory proposal (copied) nor a handoff in a tainted run; the file counts its own corpus access and filters on `split_of(id) == "dev"`; no held-out case was read, printed or used;
- cross-user ids: `user_id`, `owner_id`, `document_id`, `story_id`, `memory_id` and nested ids in arguments are refused; the evidence service is never read for another user (reads recorded) and the real handler reads only the trusted run user; no memory candidate is created;
- resource-id framework: owned allowed, foreign, one-of-several foreign, missing verifier, failing verifier, anonymous, nested and type-confused ids all refused with no handler call;
- invalid, oversized, deeply nested, non-JSON (bytes, set), boolean-for-number and non-object arguments are refused before any side effect;
- cancellation, expiry (state flags and the live probe), the 60-call budget, the 8-call step cap (in the graph) and the repeated-call limit refuse the call; the repeating model is cut off at 3 and the run still terminates by the existing step limit;
- changed schema after registration, a tool without a policy, an unknown name, a decision for a different call and a forged decision are refused;
- fuzz: a deterministic seeded corpus of 1 311 adversarial tool-call payloads (hostile values per field including NaN, infinity, huge strings, null bytes, bidi text, template and SQL strings, nested and deep objects, non-JSON types; unknown fields including nested ids; non-object argument containers; weird tool names) plus 300 random multi-field mutations through the real 11-tool registry: no exception other than a refusal, a handler is reached only for a registered name, an object of declared fields with valid types, exactly one audit record per decision, no hostile text in the audit; a second fuzz drives unknown/foreign fields through the graph and asserts no handler is ever reached.

## Risks and limits (stated plainly)

1. Provenance is lexical (5-word windows, 14-character values, URL-like values). A paraphrased instruction that does not copy text and arrives in a run with no flagged retrieval is not detected by the taint rules; only the structural controls apply (human approval for memory and handoff, fixed tool set, read-only tools). The user's goal and pasted text in it are treated as the user's own instruction by design.
2. Intent coverage uses a word-prefix lexicon in seven languages and is applied only in tainted or copied-argument situations; it can false-refuse a legitimate paraphrase (a refusal is safe and visible as `not_permitted`) and false-accept a goal containing an incidental word.
3. Injection risk reaches the decision only through `SearchCareerKnowledge`. `ResearchCurrentMarket` and candidate-document output have no risk score.
4. Cancellation and deadlines are honoured but nothing in the product sets them yet (04C). The per-run call budget counts the thread lifetime, so a very long multi-turn conversation can reach 60 calls and then be unable to call tools (the conversation itself continues).
5. `ToolRegistry` constructed without policies refuses everything. A new tool therefore needs a `ToolPolicy` (a test asserts all 11 have one); this is intended default-deny.
6. The audit trail is in the checkpoint, the log and an injectable sink. It is not an `audit_events` row, so an administrator cannot query it in Admin yet.
7. All offline: no live model, no live provider, no browser or Playwright (no frontend change; reserved port 3126 unused).

## Human security review questions (for the owner's future reviewer; none of these is answered here)

1. Is the side-effect classification right? Should `FindCandidateEvidence` (reads private approved evidence) and `ResearchCurrentMarket` (egress to Adzuna and validated company sites) require something stronger than a derived permission, for example an explicit per-run user toggle for owner data?
2. Is "the user's goal" the right trust anchor? Text pasted into the goal is user-authored. Should pasted job descriptions or documents sent in the goal be separated from instructions at the API layer?
3. Taint rule (4) makes a tainted run refuse any state-changing or external call the user's words do not cover. Is a 0.5 retrieval risk and "any quarantined chunk" the right trigger (OD-GATE-THRESHOLDS), and is refusing rather than asking the user the right behaviour?
4. Should refused calls be surfaced to the candidate (for example "Mo declined an action"), or stay Inspector-only?
5. Budgets: are 60 calls per run, 8 per step and 3 identical calls the right numbers, and should the budget be per turn rather than per thread lifetime?
6. Audit: should every decision (or only refusals) be a durable `audit_events` row with a canonical name, who may read it, and what retention applies?
7. Unknown-field refusal is stricter than before (a field was silently dropped). Is there any provider or model that legitimately adds fields to tool arguments that product wants tolerated?
8. The human-approval path re-checks only that an allowed proposal exists. Should the stored candidate also be bound to the decision (hash of the proposed fields) so an approval can only persist what was authorised?
9. Which resource types will future tools take (documents, stories, opportunities, interviews, memory), and who owns the verifiers? The framework refuses any such tool until a verifier is registered.
10. Does the reviewer want a live (paid, governed) red-team run against the real model with the development split before any threshold is set? Nothing here substitutes for it.

## What is still missing (not claimed)

- REVIEW-01 is not complete and PG-03 is not met: the human security review, owner-approved thresholds (OD-GATE-THRESHOLDS) and the live red-team are outstanding; R4 and R5 here are engineering controls verified by deterministic tests only.
- No live-staging evidence, no live model evidence, no independent review.
- 01C (generated tool descriptions), 04C (cancellation/timeouts) and 07B follow in the agent-file ownership order and were not touched.

## Final verification

Recorded below at the end of the run (see the final report for the pushed SHA).
