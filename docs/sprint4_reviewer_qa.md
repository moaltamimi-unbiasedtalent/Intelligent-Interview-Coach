# Sprint 4 — Reviewer Q&A

Concise, technically truthful answers for a live review.

**What makes this an Agent?** It is not a fixed chain. The app exposes a bounded set of
controlled tools and LangGraph decides which action to take from the current state —
including whether Career retrieval is needed. Deterministic logic stays inside the tools
where determinism is desirable.

**Why LangGraph?** Explicit state transitions, checkpoint persistence and real
`interrupt`/`resume` semantics — important for multi-turn preparation and HITL.

**Why not a deterministic chain?** The task needs the model to *decide* which tools and
retrieval to use, pause for human decisions, and persist/resume across HTTP requests —
that is stateful graph orchestration, not a fixed sequence.

**Why not multi-agent?** It is one coherent candidate-preparation task. Separate
capabilities are exposed as controlled tools rather than adding autonomous agents
without a real coordination need.

**Why six tools?** They map to the real preparation workflow: SearchCareerKnowledge,
AnalyzeJobDescription, AnalyzeCandidateGaps, BuildPreparationPlan,
GenerateInterviewQuestions and ResearchCurrentMarket (bounded current-market evidence,
Phase 7F). (ProposePreparationMemory and RequestPracticeHandoff are
HITL action boundaries, counted separately — not evidence tools.)

**What is Agentic RAG?** The agent decides *whether* to retrieve; the deterministic
Career router decides *which* lanes/sources. The model never becomes the fact source.

**Why keep deterministic retrieval routing?** Evidence selection, geography/occupation
resolution and citations must be reliable and reproducible — that belongs in
deterministic code, not model discretion.

**How do you prevent hallucinated citations?** A deterministic output guard removes any
citation marker not backed by the current run's retrieved evidence (provenance, not
semantic faithfulness) and reuses the Sprint-3 secret/leak guard.

**Does the Agent have memory?** Two kinds: short-term LangGraph checkpoint state, and
selective, user-approved long-term preparation memory (a separate DB).

**What does pinning do?** It changes deterministic load *priority* within otherwise
relevant memories — never makes memory an instruction and never overrides the current
request.

**How does HITL work?** Real `interrupt()` checkpoints the thread; a validated
`Command(resume=...)` continues the SAME thread — for ambiguous role, memory writes and
Practice handoff only.

**Why use interrupts?** So the graph can pause across HTTP requests for a human decision
and resume deterministically without re-running side effects.

**How does the handoff work?** A typed `PreparationContext` carries role/requirements/
gaps/sources; a provenance card shows what/where; the interview is created OUTSIDE
LangGraph, idempotently.

**How do Fast/Balanced/Advanced differ?** Only the model tier changes; the tools,
grounding, memory, HITL and security rules are identical across profiles.

**Did you benchmark the models?** No paid comparison was executed. The live harness and
usage/cost instrumentation are in place; we do not claim any profile is empirically best.

**What observability do you have?** The Agent Inspector shows tools, retrieval,
citations, memory, HITL, profile, model calls, tokens, cost coverage, latency, cache,
journey and handoff — never chain-of-thought, prompts, raw checkpoint or tool arguments.

**Why not full automatic Langfuse tracing?** The product handles candidate and job
information; automatic tracing would capture prompts/content. The optional Langfuse sink
receives only a sanitised operational projection and is OFF by default.

**Does feedback make the Agent learn automatically?** No. Ratings are aggregated and
reviewed; recurring failures become explicit evaluation cases before a human-approved,
regression-tested change ships.

**How do you evaluate the Agent?** Deterministic orchestration regression (56 scripted
cases) is separate from generation-quality (RAGAS) and from the live real-model harness
(22 cases, paid opt-in).

**What is RAGAS measuring?** Faithfulness, response relevancy, context precision and
context recall of generated answers — not a single accuracy percentage.

**Why isn't the scripted suite 100% live-model accuracy?** It validates the graph/tool
contract against scripted routes; it is deliberately not a live-model tool-selection
benchmark (that is the separate live harness).

**How do you protect candidate data?** Trust separation (only app rules + tool code are
instructions), tool allowlist, injection guards, the output guard, sanitised logging and
observability, and user-scoped storage.

**Could one user access another user's memory?** No — every read/write is keyed by
`user_id`; a foreign id is indistinguishable from not-found (tested).

**How do you prevent feedback spoofing?** Feedback is accepted only for an EXACT output
the user owns and that exists — the specific Agent `response_id`, an evaluated interview
question, or a session with a generated report; foreign/unknown/malformed targets return
the same safe 404.

**Why is Interview creation outside LangGraph?** To keep it idempotent against
interrupt/replay — the graph only sets `handoff_approved`; the frontend creates the
session with an idempotency key.

**Why is Streamlit still present?** As a legacy development interface (it shows a banner).
The primary product is Next.js + FastAPI.

**Is OIDC implemented?** No — identity is transitional (`X-User-Subject`), fail-closed in
production; a real gateway/OIDC is a deployment follow-up.

**Is PostgreSQL validated?** Schema/SQL are portable and tested on SQLite; a bounded
Postgres deployment run is a documented follow-up.

**What would you build next in production?** OIDC, a bounded Postgres deployment
validation, checkpoint-retention operations, and (opt-in) paid model + RAGAS baselines.
