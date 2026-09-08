# Sprint 4 — Security & Privacy

How the Intelligent Interview Coach keeps candidate data safe and prevents the agent
from being subverted.

## Trusted vs untrusted data

The **only** source of instructions is the application's own system prompt and tool
contracts. Everything else is treated as **data, never instructions**:

- the candidate's message / goal,
- retrieved career evidence,
- saved preparation memory,
- job descriptions, backgrounds, answers,
- human-in-the-loop decisions.

Injected instructions inside any of these cannot change what the agent is allowed to
do, because capability is enforced structurally (below), not by asking the model to
behave.

## Tool allowlist (no arbitrary execution)

The agent may only call tools in a strict registry (`src/agent/registry.py`). Tool
names are Pydantic arg-model class names; unknown names are **rejected, never
executed** — no dynamic import, `eval`, or arbitrary function resolution. Low-level
stores (vector/BM25/repositories) are never registered; only the five Career tools and
the HITL action tools are. Verified: `unregistered_tool_attempts` rejected across the
evaluation dataset and `tests/test_security_phase11.py` (0 executions).

## Prompt-injection boundaries

- **User input:** routed through the agent, but capability is bounded by the allowlist
  and the deterministic retrieval router.
- **Retrieval as data:** `SearchCareerKnowledge` returns evidence as a tool
  observation; it does not run other Career tools or synthesize a nested answer.
  Retrieved text is context, not commands.
- **Memory as data:** approved preparation memory is injected as a trust-separated,
  clearly-labelled `USER-APPROVED PREPARATION MEMORY — DATA ONLY` message **before**
  the goal, never merged into system instructions (`src/agent/nodes.py`).
- **HITL response as data:** a resume decision is validated against the pending action
  (`validate_decision`) **before** the graph is touched; an invalid decision leaves the
  run paused and unchanged.

## User isolation

Every agent run, preparation memory row, interview session and completed-history row
is scoped by `user_id`. An unknown id and another user's id are **indistinguishable**
(both resolve to not-found), so ownership failures never leak existence. Verified by
cross-user tests across agent runs, memory, and durable interview sessions (0 leaks).

## Data stores and their privacy (do not conflate)

| Store | Contents | Lifecycle |
|---|---|---|
| Preparation memory (`preparation_memories`) | Selected, user-approved durable facts (summary only — never a transcript/JD/CV) | User-reviewable & deletable; not auto-expired |
| Agent checkpoint (LangGraph saver) | Private short-term execution state; may include JD/background/messages for a run | Operational; cleanup is a deployment responsibility (or saver `delete_thread` where supported) |
| Interview session (`interview_sessions`) | Private resumable operational state — config, questions, answers, evaluations | Durable while in progress; retention cleanup of stale sessions (`scripts/cleanup_runtime_data.py`) |
| Completed history (`interviews`/`reports`) | Long-term completed interview record + report | User-owned; deleted only through explicit user/privacy paths |

## Logging policy

Production operational logs contain **safe metadata only**: request/run/session id,
operation, model profile, status, duration, a safe error **category** (exception class
name), and counts. Logs never contain: raw candidate answers, JD, background, agent
conversation, memory text, retrieved chunks, provider responses, SQL parameter
payloads, checkpoint payloads, credentials, or system prompts.

- The global unhandled-API-exception handler is **safe by default**: request id +
  exception class name; a full traceback is emitted only in an explicit non-production
  environment.
- Completed-history persistence failures log a fixed message + exception class name —
  never `exc_info`, `str(exc)`, the SQL statement/params, or candidate content
  (regression: `tests/test_history_idempotency.py`).
- The OpenRouter client logs only id/model/duration/status (guarded by a debug flag);
  no raw provider response is ever logged.

## Secret handling

No secrets are committed. Keys are provided at runtime via environment variables
(`.env.example` documents the names with placeholder values). The evaluator key
(`RAGAS_EVAL_API_KEY`) and the chat key are never printed. A secret scan runs over the
tracked tree.

## Chain-of-thought is never exposed

The Agent Inspector and all events expose observable actions only (tools, retrieval,
sources, memory use, approvals, warnings, timing, safe failure categories). They never
expose chain-of-thought, `reasoning_details`, system prompts, raw provider responses,
raw checkpoint state, the memory prompt, candidate background or the full JD.

## Authentication (transitional — not production)

Identity is resolved from an `X-User-Subject` header, intended for a **trusted upstream
gateway or local development/demo** — it is **not production authentication**.

- After identity is resolved, isolation is enforced everywhere by `user_id` (see
  above).
- Production requires a real authenticating gateway / OIDC in front of the API; this
  is a documented deployment requirement, intentionally out of Sprint scope.
- Production mode must not silently fall back to an anonymous identity for
  authenticated surfaces — deploy behind an authenticating proxy.
