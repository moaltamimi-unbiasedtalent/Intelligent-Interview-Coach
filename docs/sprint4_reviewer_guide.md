# Sprint 4 — Reviewer Guide

A practical orientation to the Intelligent Interview Coach — enough to understand and
demo it without reading the whole repo. Companion docs: `sprint4_demo_script.md`,
`sprint4_reviewer_qa.md`, `sprint4_final_requirements_matrix.md`,
`sprint4_final_evidence.md`.

## First 60 seconds

> "Sprint 3 gave Interview OS Coach an evidence-backed Career Intelligence layer. In
> Sprint 4 I turned those capabilities into a stateful LangGraph Agent. The Agent
> decides which controlled tool to use and when, including whether Career retrieval is
> needed. It carries short-term checkpoint state, selectively loads user-approved
> long-term memory, and pauses for human approval where the system should not decide
> autonomously. The result becomes a typed PreparationContext that moves into durable
> Interview Practice. I also added multi-model execution, feedback-informed improvement
> and privacy-safe observability."

- **Why it's an agent:** not a fixed chain — a bounded tool set, and LangGraph decides
  the next action from state; deterministic logic stays inside the tools.
- **Why LangGraph:** explicit state transitions, checkpoint persistence, real
  interrupt/resume — needed for multi-turn preparation and HITL. LangChain provides the
  OpenRouter model/tool-calling integration; LangGraph owns orchestration.

(Full answers in `docs/sprint4_reviewer_qa.md`.)

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

## Post-Sprint polish (bonus) — P4: visible journey & transparent handoff

The lifecycle the architecture implements is now visible to the candidate, and the
Practice handoff is explained rather than magical. Run the primary path (Next.js +
FastAPI) and open **Prepare**:

1. Start a role/JD preparation → the **UNDERSTAND → PREPARE → PRACTISE** journey chrome
   updates from real state.
2. As controlled tools complete, an observable **preparation checklist** fills in
   (understand the opportunity → compare your experience → build priorities → create
   questions).
3. At handoff, the approval card shows **what** will be carried into Practice and
   **where** each piece came from (role, focus areas, generated questions).
4. Approve → Practice opens with a subtle "Prepared in your Coach session" note;
   standalone Practice shows none.

Reviewer lines:

- **Journey:** *"The candidate can now see the same lifecycle the architecture
  implements: understand the opportunity, prepare against it, and practise using that
  context."*
- **Handoff:** *"The handoff is transparent rather than magical. The candidate can see
  which role, focus areas and generated preparation outputs are being carried into
  Practice and where each one came from."*
- **Progress:** *"The preparation checklist reflects completed tools and structured
  state. It is observable workflow progress, not exposed chain-of-thought."*

The full over-delivery story now spans: **P0** live-model evaluation harness /
retrieval restraint / grounding provenance / HITL metrics; **P1** usage-cost
instrumentation / Fast-Balanced-Advanced Coach / same-thread retrieval cache; **P2**
candidate-controlled memory (edit / pin / preview / editable HITL / checkpoint
deletion); **P4** visible end-to-end journey and transparent Practice handoff.

## Post-Sprint polish (bonus) — P5: feedback loop & observability

**Turing College capability map**

| Capability | Status |
|---|---|
| Multi-model support | ✅ P1 — Fast/Balanced/Advanced (registry-backed, server-validated) |
| Feedback / learning loop | ✅ P5 — candidate ratings → human-reviewed engineering loop |
| Observability / tool usage | ✅ Agent Inspector + ✅ P1 usage/cost/cache + ✅ P4 journey/handoff + ✅ P5 optional external sink |

**Feedback (a controlled loop, not self-modification).** Candidates rate an Agent
answer, an interview evaluation or a final report (Helpful / Not helpful + optional
comment). Ratings are user-scoped, attached by reference (never a copy of the rated
content), and accepted only for an **exact candidate-visible output that exists and
belongs to the current user** — the backend verifies the exact Agent response
(`response_id`), the evaluated Interview question, or the generated final report before
accepting a rating (owning the parent run/session alone is not enough; foreign,
unknown, malformed and nonexistent targets all return the same safe not-found). They are
aggregated for human review; a
recurring pattern becomes a new evaluation case and a human-reviewed, regression-tested
prompt/policy change. Feedback **never** modifies prompts, tools, retrieval, memory,
HITL or the model automatically.

> Concrete example (§29). Repeated "the Coach searched Career Knowledge when I only
> asked how the app works" → a developer adds an `evaluations/agent_live/` case with
> `retrieval_expected=false`, tightens the retrieve-vs-not policy, and re-runs
> `eval_agent` + the live harness before shipping. `scripts/export_feedback_summary.py`
> surfaces the aggregate (comments only with an explicit `--include-comments`).

**Observability.** The Agent Inspector remains the primary, first-party view (tools,
retrieval, HITL, model usage, latency, cache, journey, handoff — never chain-of-thought).
An optional external sink (Langfuse) is provider-neutral, **OFF by default**, and
receives only a sanitised operational projection (never prompts, candidate text, JD/CV,
memory, retrieved chunks, answers, the system prompt, tool arguments or tool output);
a provider outage never affects a run.

Reviewer lines:

- **Feedback:** *"The application learns from feedback through a controlled engineering
  loop rather than autonomously rewriting itself. Ratings are aggregated, recurring
  failure patterns become evaluation cases, and any prompt or policy improvement is
  human-reviewed and regression-tested."*
- **Exact target (P5.1):** *"Feedback is not attached merely to a run or session. The
  backend verifies the exact Agent response, evaluated Interview question, or generated
  final report before accepting the rating."*
- **Observability:** *"The Agent Inspector shows what the system did — tools, retrieval,
  HITL, model usage, latency, cache and journey state — without exposing chain-of-thought.
  Optional external observability receives only a sanitised operational projection."*
- **Multi-model:** *"The Coach supports registry-backed Fast, Balanced and Advanced
  model profiles. Changing the model does not change the controlled tool set, grounding
  policy, memory rules or HITL safeguards."* No paid profile comparison has been executed.

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
