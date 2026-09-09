# Sprint 4 — Reviewer Guide

A 5-minute orientation to the Intelligent Interview Coach.

## What it is

A career-preparation agent that takes a candidate from a target role to a practised
interview. A stateful **LangGraph agent** (the "Agent Coach") decides which controlled
Career tools to call and when to retrieve evidence, asks for human approval on
important assumptions and persistent side effects, and hands an approved
**PreparationContext** into a durable **Interview Practice** flow (question → answer →
structured feedback → optional Deep Dive → final report).

## Why it is useful / who it is for

Candidates preparing for a specific role get grounded, role-aware preparation and
realistic interview practice with structured feedback — without losing progress if
they refresh or come back later.

## Architecture

```
Next.js (primary UI)  →  FastAPI  →  Application Services
                                        ├── LangGraph agent ── 5 Career tools
                                        │        ├── Agentic RAG (retrieval-as-data)
                                        │        ├── durable long-term memory
                                        │        ├── real HITL interrupt/resume
                                        │        └── safe Agent Inspector
                                        │        └── durable checkpoint
                                        └── Interview Practice ── SessionManager
                                                 ├── durable session store (resumable)
                                                 └── completed History (report)
```

Identity boundary: a trusted gateway sets `X-User-Subject`; all data is scoped by
`user_id`. See `docs/sprint4_architecture.md` and `docs/sprint4_security_privacy.md`.

## Tools (agent-registered, allowlisted)

`AnalyzeJobDescription`, `AnalyzeCandidateGaps`, `BuildPreparationPlan`,
`GenerateInterviewQuestions`, `SearchCareerKnowledge` (retrieval-only), plus HITL
action tools (`ProposePreparationMemory`, `RequestPracticeHandoff`). Unknown tools are
rejected, never executed.

## Agentic RAG

The agent decides *whether* retrieval is needed; once it calls
`SearchCareerKnowledge`, the existing deterministic engine decides *which*
lanes/sources (occupation resolution, structured + hybrid retrieval, geographic
precedence, ranking, citations). Retrieval returns evidence to LangGraph as data; it
does not run other tools or synthesize a nested answer.

## Memory

Short-term = the LangGraph checkpoint (execution state). Long-term = a separate,
user-scoped database of **selected, approved** preparation facts (summaries only). The
whole conversation is deliberately NOT saved as long-term memory.

## HITL

Real LangGraph `interrupt`/`Command(resume=...)`: the graph checkpoints, the HTTP
request ends, the user decides, and the SAME thread continues — reserved for role
ambiguity, memory persistence and Practice handoff (not every tool call).

## Evaluation

Deterministic orchestration regression (56 held-out cases, `python
scripts/eval_agent.py`, gated in CI) + preserved RAGAS for answer quality (opt-in,
paid). The deterministic suite validates the graph/tool **contract** against held-out
**scripted** routes — it is **not a live-model tool-selection benchmark** (e.g.
`required_tool_recall = 1.0` is expected-tool execution recall under the scripted
cases, not a claim that the real model always picks the right tool). See
`docs/sprint4_final_evaluation.md`.

## Security

Trusted vs untrusted data, tool allowlist, retrieval/memory/HITL-as-data, user
isolation, safe logging, no chain-of-thought exposure. See
`docs/sprint4_security_privacy.md`.

## Reviewer Q&A

- **Why LangGraph / not a simple chain?** A chain runs a fixed sequence; the task needs
  the model to *decide* which tools/retrieval to use, to pause for human decisions, and
  to persist/resume state across HTTP requests — that is stateful graph orchestration.
- **How is this different from Sprint 3?** Sprint 3 was a largely deterministic Career
  Intelligence pipeline. Sprint 4 wraps those trusted capabilities inside a stateful
  agent that decides tool/retrieval use, with human approval for assumptions and
  persistent side effects — the deterministic retrieval engine still owns evidence
  selection and citations.
- **What makes the RAG agentic?** The agent decides whether to retrieve; the
  deterministic router decides what to retrieve. See Agentic RAG above.
- **How do you prevent arbitrary tool execution?** A strict allowlist registry — no
  dynamic import/eval; unknown names rejected. Low-level stores are never registered.
- **Short-term vs long-term memory?** Checkpoint (execution) vs approved durable
  preparation facts — see Memory.
- **How does HITL actually work / resume after the request ends?** LangGraph
  `interrupt` checkpoints the thread; a later `Command(resume=...)` (validated) resumes
  the same thread. See HITL.
- **How do you prevent cross-user memory/checkpoint/interview access?** Everything is
  keyed by `user_id`; unknown and foreign ids are indistinguishable (not-found).
- **What is RAGAS measuring?** Faithfulness / relevancy / context precision & recall of
  generated answers — not a single "accuracy %".
- **Why not expose chain-of-thought?** It is unsafe and unnecessary; the Inspector
  shows observable actions instead.
- **Why Fast/Balanced/Advanced models?** A workload→profile policy makes the
  cost/quality trade-off explicit; the strongest model is not always the right one. The
  Agent Coach exposes the three tiers to the candidate (P1); every tier keeps the same
  grounding, HITL, tool allowlist and step budget — only the model changes.
- **How is agent usage/cost reported without overclaiming?** Per run the Inspector shows
  model-call counts, tokens, cache hits/misses and — when the provider reports it —
  estimated cost. Coverage is marked Complete or Partial; unknown usage is never shown as
  zero and no paid Fast-vs-Advanced cost comparison has been run (opt-in only). See
  `docs/sprint4_final_evaluation.md` §11.
- **How does Interview state survive restart?** The SessionManager state machine is
  unchanged; its validated `SessionData` is serialised to a durable, user-scoped
  session store with optimistic concurrency and recoverable operation leases.

## Post-Sprint polish (bonus)

Beyond the Sprint 4 requirements, a polish pass added (offline-tested, no architecture
change): a **live-model evaluation harness** separate from the scripted regression
(`scripts/eval_agent_live.py`, manual/paid); a deterministic **agent output guard**
that (reusing the Sprint-3 `guard_output`) redacts secret-like strings, flags verbatim
system-instruction leakage, and **validates citation provenance** — removing
fabricated/stale citation references from the final answer — plus a safe
uncited-retrieval observability warning. This guard validates citation *provenance*, not
semantic claim-level faithfulness (that remains an evaluation concern, measured by
RAGAS / live evaluation when executed). Also: a sharper **retrieve-vs-not** policy +
preferred preparation sequence; and safe **HITL frequency** metrics. See
`docs/sprint4_final_evaluation.md` §10.

A second polish pass (**P1 — measure first, optimise second**, `docs/…final_evaluation.md`
§11) added **agent usage accounting** (safe per-run token/model-call counts with honest
complete/partial coverage — unknown is never shown as zero), **Fast/Balanced/Advanced
Coach modes** (registry-backed; a raw model slug is never accepted from the browser; all
tiers keep grounding/HITL/allowlist/step-budget), and a **safe per-thread retrieval
cache** (reuses evidence for an equivalent same-thread request; never shared across users
or runs). No paid comparative benchmark was executed. Remaining items (memory-management
UI, journey chrome, feedback loop, external company research) are documented follow-ups.

## Post-Sprint polish (bonus) — P2: memory management UX

Long-term preparation memory became a candidate-controlled feature (trust model
unchanged: selective, user-scoped, bounded, explicitly approved, DATA only). Demo:

1. The Coach proposes a useful memory during a run.
2. The candidate sees the **exact** value that would be saved (category / memory / for
   / a static "why").
3. They **edit it before saving** (or approve as-is, or reject).
4. **Settings → Preparation memory** shows the saved memory.
5. They **pin** it.
6. **What may be used next time** (enter a role) shows it will be preferred for a
   relevant future role — the preview uses the *same* loader a real run uses.

Also: a candidate can **delete a Coach run** (its checkpoint thread only) without
touching saved memory or Interview History.

- **What memory is:** *"Long-term memory is not hidden chat history. It is a small
  user-controlled set of approved preparation facts that the candidate can inspect,
  edit, prioritise and delete."*
- **What pinning does:** *"Pinning changes deterministic load priority only. It does
  not make the memory an instruction and it never overrides the user's current
  request."*
- **Checkpoint vs memory:** *"Checkpoint state and long-term memory remain separate.
  Where the official LangGraph saver supports thread deletion, the user can explicitly
  delete that execution thread without touching their approved long-term memories."*

See `docs/sprint4_architecture.md` §3h.

## Known limitations (explicit)

- Production **OIDC not implemented** — the API must run behind an authenticating
  gateway; identity is transitional (`X-User-Subject`), fail-closed in production.
- **PostgreSQL** full integration is a deployment check (schema/SQL are portable and
  tested on SQLite; a bounded Postgres run is documented as a follow-up).
- Agent **checkpoint retention** cleanup is a deployment responsibility where the saver
  does not expose thread deletion.
- **Record voice** deferred (no production transcription path); **Live** is
  experimental and off by default; **no camera**.
- **Per-operation Interview model tiering** deferred (one profile per session).
- **Paid** model comparison and live RAGAS runs were **not executed** (opt-in only).
