# Sprint 4 Architecture — Intelligent Interview Coach

This document records the **Sprint 3 → Sprint 4 evolution**, the agent
architecture decisions, and how Sprint 3 reviewer feedback is addressed in the
design. It is a **planning document**: nothing here is implemented in Phase 0.
The current shipping product is the Streamlit application described in the
[README](../README.md).

Status legend: ✅ **Current (Sprint 3, implemented)** · 🔷 **Planned (Sprint 4)**

---

## 1. Sprint 3 (current) request flow

```mermaid
flowchart LR
    U[User] --> QU[Query understanding / router]
    QU --> RL[Predetermined retrieval lanes]
    RL --> T[Domain tools]
    T --> SYN[LangChain / OpenRouter synthesis]
    SYN --> C[Answer with citations]
    C --> IP[Interview Practice<br/>typed handoff]
```

In Sprint 3, **retrieval runs on (almost) every request** as a predetermined step
before synthesis. The router picks structured/hybrid lanes deterministically.

## 2. Sprint 4 (target) agent flow

```mermaid
flowchart TD
    FE[Next.js / TypeScript frontend] --> API[FastAPI backend]
    API --> AG[LangGraph agent<br/>stateful orchestration]
    AG -->|decides next action| DEC{Which tool,<br/>if any?}
    DEC -->|career retrieval| RT[Retrieval tool<br/>deterministic inside]
    DEC -->|JD analysis| JD[JD analysis tool]
    DEC -->|gap analysis| GAP[Candidate gap tool]
    DEC -->|preparation plan| PLAN[Preparation planning tool]
    DEC -->|question generation| QG[Question generation tool]
    DEC -->|company research| EXT[External research tool<br/>later]
    RT --> OBS[Observe tool result]
    JD --> OBS
    GAP --> OBS
    PLAN --> OBS
    QG --> OBS
    EXT --> OBS
    OBS -->|another tool needed?| AG
    OBS -->|approval needed| HITL[Human-in-the-loop]
    HITL --> AG
    OBS --> FIN[Final response]
    FIN --> MEM[Memory<br/>short + selective long-term]
    FIN --> IP[Interview Practice]
```

### Key architectural statement (addresses reviewer feedback)

> **Retrieval will become an explicit agent-selectable tool** rather than being
> automatically required for every user request. The retrieval subsystem itself
> will **remain deterministic internally**, preserving structured/hybrid
> retrieval, geographic source precedence, evidence normalisation and citations.

The agent gains the *decision* of whether to retrieve; the retrieval *mechanics*
stay exactly as hardened in Sprint 3.

---

## 3. Agent architecture decisions

These are fixed now so later phases do not drift:

1. **Single primary agent**, not a multi-agent system.
2. **LangGraph** owns stateful orchestration.
3. **LangChain / OpenRouter** remain the model/tool integration layer.
4. **Retrieval becomes an explicit controlled tool.**
5. Existing **deterministic retrieval routing stays inside** the retrieval tool.
6. Existing **deterministic calculations remain deterministic Python.**
7. Existing **Python RAG and Interview logic remain Python.**
8. **Next.js / TypeScript** becomes the target frontend.
9. **FastAPI** becomes the target API boundary.
10. **Streamlit remains temporarily** as a migration fallback until parity is proven.
11. Important assumptions / memory writes use **human-in-the-loop approval.**
12. Agent loops are **bounded.**
13. **No private chain-of-thought is exposed**; only safe tool/action traces.
14. **RAGAS** remains the generation-quality evaluation layer.
15. Existing **security / privacy boundaries must be preserved.**

## 3a. Phase 1 — application boundary (implemented)

Phase 1 introduced a thin, **Streamlit-free application layer** (`src/application`)
so the existing capabilities are callable without Streamlit UI state or rendering.
Streamlit is now a *consumer* of these services; a future FastAPI backend will
call the same functions.

```mermaid
flowchart TD
    ST[Streamlit UI<br/>src/career/ui.py, src/interview/studio_app.py] --> APP
    subgraph APP[Application layer — src/application  ✅]
        CA[CareerApplicationService<br/>chat + 4 tools]
        IA[InterviewApplicationService<br/>strategy/questions/answers/deep dive/report]
        HS[history_service<br/>save / list / get]
        KS[knowledge_service]
        ES[evaluation_service]
        FA[factories<br/>services / repository / stores]
    end
    APP --> DOM[Existing domain / RAG / tools / persistence<br/>src/copilot, src/*, src/integration]
    FUT[FastAPI  🔷 later] -.calls the same services.-> APP
```

**What moved:** service construction (vector store, retriever, tool invoker,
interview/evaluation/report services, repository, pricing) into Streamlit-free
factories; Career chat/tools orchestration into `CareerApplicationService`;
interview strategy/question/answer/deep-dive/report orchestration into
`InterviewApplicationService` (driving a store-agnostic `SessionManager`);
persistence (payload build, duplicate-save guard, safe-failure handling) into
`history_service`; read-only knowledge/evaluation snapshots into their services.

**What did NOT change:** RAG/retrieval behaviour, tool execution, RAGAS scoring,
the interview state machine and scoring, the DB schema, auth, security guards, and
Live/Type/Record behaviour (Live stays flag-gated OFF). No FastAPI, Next.js or
LangGraph was added.

**Enforced by tests:** `src/application` imports no Streamlit and no UI module
(`tests/test_application_boundary.py`); the UI may import the application layer,
never the reverse.

## 3b. Phase 2 — FastAPI backend (implemented)

Phase 2 adds a thin, typed **FastAPI** backend (`src/api`) over the same
application layer. Streamlit keeps working unchanged; both call `src/application`.
FastAPI orchestrates HTTP concerns only — no Career/Interview/RAG/persistence/
RAGAS/security logic is duplicated in routes.

```mermaid
flowchart TD
    ST[Streamlit UI] --> APP[Application layer — src/application]
    API[FastAPI — src/api  ✅<br/>/api/v1] --> APP
    APP --> DOM[Existing domain / RAG / tools / persistence]
    NX[Next.js frontend  🔷 later] -.HTTP.-> API
```

**Surface (`/api/v1`, plus `/api/health` liveness alias):**
- `GET /health`, `/ready`, `/capabilities`
- `POST /career/chat`, `/career/job-analysis`, `/career/gap-analysis`,
  `/career/preparation-plan`, `/career/questions`
- `POST /interviews`, `GET /interviews/{id}`, `POST /interviews/{id}/answers`,
  `/interviews/{id}/next-question`, `/interviews/{id}/complete`,
  `POST|GET /interviews/{id}/report`
- `GET /history/interviews`, `/history/interviews/{id}` (user-scoped)
- `GET /knowledge/sources`, `/knowledge/snapshot`
- `GET /evaluation/latest`, `/evaluation/runs`, `/evaluation/runs/{id}`,
  `/evaluation/ragas/configuration`

**Run locally:** `uvicorn src.api.main:app --reload` (interactive docs at `/docs`).

**Cross-cutting:** a server-generated `X-Request-Id` per request; a stable error
envelope `{"error": {code, message, request_id}}` (app errors → 422/503, unknown
→ safe 500, never a traceback/SQL/secret); CORS from `FRONTEND_ORIGINS` (never
wildcard-with-credentials).

**Resource lifecycle:** expensive resources (vector store, repository, pricing,
translation cache, configs) are built once and cached on `app.state` under a lock
(application-lifetime); `CareerApplicationService`/`InterviewApplicationService`
are cheap request-scoped wrappers. Nothing runs a provider/DB call at import.

**Interview session state (transitional):** in-progress interviews live in a
bounded, thread-safe, **user-scoped in-memory** store (`src/api/session_store.py`)
— the current schema persists only *completed* interviews. This is in-process
only (documented); durable in-progress session state is a later phase. Completed
reports still persist through `history_service`.

**Auth (transitional):** identity comes from the anonymous dev user unless an
`X-User-Subject` header is supplied (set only by a trusted upstream gateway or in
tests). History is strictly user-scoped (`repo.get_interview(user_id, id)`), so no
user can read another's reports. **Production must front the API with a real
authenticating gateway / OIDC** — see Phase 3/7.

**Deferred (documented):** Deep Dive HTTP endpoints (the application service
supports them; the surface is not yet exposed) and company-document uploads (the
existing limits are preserved in the domain; a secure multipart endpoint is a
later phase). No paid RAGAS run endpoint. **No Next.js and no LangGraph yet.**

## 3c. Phase 3B — Next.js frontend foundation (implemented)

Phase 3A selected **Concept D — Precision Coach**; Phase 3B builds the production
frontend *foundation* for it in `frontend/` (Next.js 15 App Router · React 19 ·
TypeScript · Tailwind). It is a typed client of the FastAPI backend; Streamlit keeps
working alongside it over the same application layer.

```mermaid
flowchart TD
    NX[Next.js frontend  ✅ foundation<br/>frontend/ · Precision Coach] --> API[FastAPI /api/v1]
    ST[Streamlit UI  temporary] --> APP[Application layer — src/application]
    API --> APP
    APP --> DOM[Existing domain / RAG / tools / persistence]
    LG[LangGraph agent  🔷 planned] -.later.-> APP
```

**Built:** the Precision Coach design system (tokens → CSS variables + Tailwind
theme, light/dark, no-flash), a restrained app shell (quiet header + mobile bottom
nav), the primary routes (Home, Prepare, Practice, Progress, History, Sources,
Review & Diagnostics + Agent/RAG/Evaluation, Settings) as scaffolds, a small
reusable component + UI-primitive foundation, a typed FastAPI client
(`lib/api/*`), and **live health/capabilities integration** (the Practice page
shows Live only when the backend reports `live_interview_enabled`). Frontend tests
(Vitest, 17) + a Playwright smoke (7) pass; Next.js → FastAPI integration verified
live.

**Deliberately NOT in 3B:** the full Career/Preparation migration (chat, JD/gap
analysis, planning, questions) — that's **Phase 3C**; the Prepare/Practice pages
are visual shells with clearly-marked demo content and an architecture ready to
swap in real API calls. No LangGraph, no model changes, Streamlit not removed.

**Auth (transitional):** the frontend has an auth *seam* (`lib/auth.ts`) only;
production OIDC/gateway is future work. A dev-only `X-User-Subject` may be set via
`NEXT_PUBLIC_DEV_USER_SUBJECT` for local data scoping — never typed by the browser
user.

## 3d. Phase 3C — live Career preparation experience (implemented)

Phase 3C makes `/prepare` real: the Next.js frontend now drives the existing
deterministic Sprint 3 Career Intelligence through the FastAPI contracts, and hands
a `PreparationContext` into a real interview session. No Career logic is duplicated
in TypeScript; retrieval is still deterministic (agentic RAG is Phase 6).

```mermaid
flowchart TD
    U[Candidate] --> NX[Next.js · Precision Coach<br/>/prepare · /practice · /sources]
    NX --> API[FastAPI /api/v1]
    API --> CA[CareerApplicationService]
    CA --> QR[Query understanding / router]
    QR --> RET[Retrieval  deterministic]
    RET --> TOOLS[Domain tools]
    TOOLS --> GR[Grounded response + citations]
    GR --> NX
    NX -->|Start practice| PC[PreparationContext]
    PC --> IA[InterviewApplicationService]
    IA --> NX
    LG[LangGraph agent  🔷 planned] -.will choose retrieval/tools.-> CA
```

**What's live now:**
- **Prepare** — a coach composer + progressive "Add context" (job description, about
  you) posting to `POST /career/chat`; grounded answers render with candidate-facing
  **Career evidence** (citations/sources), an insufficient-evidence state, safe
  observable activity ("Checking career evidence…", never "thinking"), and safe
  errors with a request id.
- **Preparation tools** — all four connected: `job-analysis`, `gap-analysis`,
  `preparation-plan`, `questions`, rendering the real deterministic results.
- **Handoff** — builds a typed `PreparationContext` from gathered data and calls
  `POST /interviews`, then navigates to `/practice?session=<id>` (no extra LLM call;
  target-role precedence preserved).
- **Practice** — reads the real session (`GET /interviews/{id}`), showing the
  session's role + first question; a calm state when the model isn't configured.
- **Sources** and **History** — connected to `/knowledge/*` and `/history/*`
  (user-scoped) with real loading/empty/error states.

**One additive backend change** (§36): `InterviewStateResponse.target_role`
(optional) so the Practice page can show the session's role. Backward-compatible;
OpenAPI, Streamlit and user isolation preserved; guarded by
`tests/test_openapi_contract.py`.

**Still deliberately out:** LangGraph / agent tool-selection / memory / HITL; no
model changes; Streamlit not removed; no browser secrets (only `NEXT_PUBLIC_*`); no
private preparation data in `localStorage`. All Career requests still pass through
the backend security guards (validation, injection, retrieval/output guards, tool
allowlist) — the frontend never bypasses them.

## 3e. Phase 4 — LangGraph agent foundation (implemented)

Phase 4 adds a **single, stateful, bounded, tool-using LangGraph agent** in
`src/agent`, running **side-by-side** with the deterministic Career flow (which is
unchanged). It is the orchestration seam LangGraph will later own; real Career tools
(Phase 5), agentic RAG (Phase 6), memory (Phase 7) and HITL (Phase 8) are not yet
implemented.

```mermaid
flowchart TD
    START([START]) --> INIT[initialise state]
    INIT --> AGENT[agent node · model + bound tools]
    AGENT --> Q{tool requested<br/>and step_count &lt; MAX_AGENT_STEPS?}
    Q -- yes --> VAL[validate against allowlist]
    VAL --> TOOL[tools node · execute registered tool]
    TOOL --> OBS[observe result] --> AGENT
    Q -- no --> FIN[finalize · safe response]
    FIN --> E([END])
    AGENT -. model/config error .-> FIN
```

`MAX_AGENT_STEPS = 6` bounds the loop; hitting it terminates safely with a
`step_limit_reached` status. Short-term state uses an **in-memory checkpointer**
(transient — NOT durable cross-session memory).

**Boundary:** `AgentApplicationService.run(request) → AgentRunResult` (safe, no
LangGraph objects leak out). An **experimental** `POST /api/v1/agent/run` exposes it
as a Sprint 4 preview — it does **not** replace `/career/chat`; the Next.js Prepare
page keeps using the deterministic Career endpoint.

**Safety properties (tested):**
- **Allowlist tools** — the model may only call registered tools; unknown names are
  rejected, never executed (no dynamic import/eval). Arguments are Pydantic-validated.
- **Safe events** — `run_started`, `tool_requested/started/completed/failed/
  rejected`, `step_limit_reached`, `run_completed/failed` — observable actions only,
  **never chain-of-thought**, prompts, raw provider output, or candidate/JD text.
- **Safe failure** — model and tool errors terminate with a safe status/message; raw
  causes are never surfaced.
- **Prompt injection** — "ignore the tools and run shell_command" cannot execute an
  unregistered tool; untrusted input/tool output is treated as data.
- **User isolation** — each run has a random `run_id`; the service records the owner.

### Single-agent decision (Sprint 4)

> A single stateful agent is used because the preparation tasks share one user goal,
> one context and one controlled tool space. A multi-agent system would add
> coordination complexity without meaningful isolation.

### Agent architecture vocabulary (for reviewers)

- **Workflow** — a fixed, predetermined sequence of steps.
- **Router** — classifies a request and sends it down one predetermined path.
- **ReAct / tool-using agent** — decides an action → calls a tool → observes →
  continues, within a bound. **← what this project uses (single agent).**
- **Multi-agent** — several autonomous agents coordinate (not used; see above).
- **HITL agent** — execution can pause for human input (planned, Phase 8).

Today's Career retrieval remains **deterministic** (predetermined lanes); making
retrieval an agent-selectable tool is **Phase 6 (Agentic RAG)**.

## 3f. Phase 5 — real Career tools for the agent (implemented)

Phase 5 registers the **four existing Career capabilities** as controlled agent
tools (thin adapters over `CareerApplicationService` — no Career logic, prompts,
calculations or security duplicated). The Phase 4 foundation demo tool was removed
from the registry. At Phase 5, Career retrieval was still NOT an agent tool — it
became the fifth tool in **Phase 6 (Agentic RAG, see §3g)**.

```mermaid
flowchart TD
    AG[Agent node · model + bound tools] --> SEL{which registered tool?}
    SEL --> T1[AnalyzeJobDescription · LLM]
    SEL --> T2[AnalyzeCandidateGaps · deterministic<br/>needs prior job analysis + background]
    SEL --> T3[BuildPreparationPlan · deterministic<br/>needs prior gaps + time]
    SEL --> T4[GenerateInterviewQuestions · LLM]
    T1 & T2 & T3 & T4 --> OBS[structured observation] --> AG
    AG -. Phase 6 adds a 5th tool .-> RET[SearchCareerKnowledge · retrieval<br/>see §3g]
```

Each tool wraps `CareerApplicationService`: `analyze_job_description` (LLM),
`analyze_candidate_gaps` (deterministic), `build_preparation_plan` (deterministic),
`generate_questions` (LLM). Tool arguments are Pydantic-validated; **preconditions**
come from prior state (gap analysis requires the job-analysis requirements; the
planner requires the gaps) and fail safely if unmet — the agent never fabricates
missing inputs. Tool outputs update typed `AgentState`
(`requirements`/`gaps`/`preparation_plan`/`questions`) and, where sufficient, the
service builds the **existing** `PreparationContext` (reused from `src/integration`).

**Function-calling story (for reviewers):** the agent receives a *fixed* registry of
Career tools; the model may request only those functions; each requested name is
checked against the **allowlist** and its arguments validated with Pydantic before
the existing Career implementation runs; the structured result returns to the graph
as an observation; the model then calls another tool or finishes.

**Agent vs workflow (why this is agentic):** a fixed workflow would always run
JD→Gap→Plan→Questions. Here, "analyse this JD" runs **only** the JD analyzer, while
"full preparation" runs JD→Gap→Plan(→Questions) — the model chooses tools and order
from intent and dependencies; the code does not hard-code the sequence. A
deterministic orchestration regression (`evaluations/agent/tool_selection_cases.json`
+ `src/agent/eval.py`) exercises routing, prerequisites, rejection and completion
without a provider (it is **not** a live-LLM benchmark).

## 3g. Phase 6 — Agentic RAG: retrieval as an agent-selectable tool (implemented)

Phase 6 exposes the existing Career retrieval capability as the **fifth** real agent
tool, `SearchCareerKnowledge`. This directly addresses the Sprint 3 reviewer note
that *"retrieval should be exposed as a tool rather than a predetermined step after
every user query."* Retrieval is now **conditional**: the agent decides *whether*
external career evidence is needed at all.

**Two decision layers (the core design).** Retrieval selection and retrieval routing
are deliberately separated:

1. **The agent decides IF to retrieve** — by choosing to call `SearchCareerKnowledge`
   (or not). A rewrite request, or a question answerable from information the user
   already gave, triggers no retrieval.
2. **The deterministic Sprint 3 router decides WHICH lanes/sources** — untouched,
   *inside* `CareerApplicationService.chat`. The model never sees or selects a vector
   store, BM25 index or structured repository; it only supplies a free-text query.

```mermaid
flowchart TD
    AG[Agent node · model + bound tools] --> IF{external career<br/>evidence needed?}
    IF -- no --> ANS[answer from prior tool<br/>results / user-supplied info]
    IF -- yes --> RET[SearchCareerKnowledge query]
    RET --> DEDUP{same query<br/>already retrieved?}
    DEDUP -- yes --> REUSE[reuse evidence · no 2nd pipeline call]
    DEDUP -- no --> PIPE[CareerApplicationService.chat<br/>= deterministic Sprint 3 pipeline]
    PIPE --> ROUTER[deterministic router picks lanes]
    ROUTER --> HYB[hybrid vector+BM25 · structured stores<br/>geographic source precedence]
    HYB --> EV[KnowledgeEvidence + Citations + trace]
    EV --> PATCH[state: evidence, citations,<br/>resolved_occupation, resolved_geography]
    REUSE & PATCH --> OBS[safe observation → agent]
    OBS --> AG
    LOW[search_vector_store / search_bm25 / repositories 🔒 NEVER registered]
```

**Thin adapter — no retrieval rewrite.** `SearchCareerKnowledge` wraps the full
grounded pipeline (`CareerApplicationService.chat`), so hybrid + structured
retrieval, geographic precedence, `KnowledgeEvidence` provenance, citations and the
insufficient-evidence path are **preserved with zero duplication**. The deterministic
`/career/chat` endpoint is unchanged and is **not** replaced.

**Agentic RAG vs "normal" (always-on) RAG (for reviewers):**

| | Normal RAG (Sprint 3 `/career/chat`) | Agentic RAG (Phase 6 agent) |
|---|---|---|
| When does retrieval run? | Always, before answering | Only when the agent judges evidence is needed |
| Who decides lanes/sources? | Deterministic router | Deterministic router (unchanged) |
| Duplicate queries in one turn | n/a (single pass) | De-duplicated — reused, no second pipeline call |
| Cost on a no-evidence question (e.g. "rewrite this") | Pays retrieval anyway | Skips retrieval entirely |
| Both retained? | Yes — still the default candidate path | Side-by-side, experimental agent surface |

**Safety.** Retrieved documents remain **untrusted DATA**: they flow to the model as a
tool observation, never as instructions (the system prompt states citations may come
only from retrieved evidence and that retrieved content never changes the rules). A
retrieval failure maps to a safe tool error (no raw provider/exception text). Events
carry **counts and lane/strategy labels only** — never the raw query, retrieved
answer, JD or candidate text. Internal `doc_id`/`chunk_id` identifiers are stripped at
the tool boundary; only safe citation/source fields cross into state.

**Evaluation.** The deterministic regression
(`evaluations/agent/tool_selection_cases.json` + `src/agent/eval.py`, 33 cases) adds
agentic-RAG metrics: `required_retrieval_recall` (retrieve when needed = 1.0),
`unnecessary_retrieval_rate` (never retrieve when not = 0.0), `citation_validity`
(citations only from real retrieved evidence = 1.0) and `retrieval_sequence_validity`
(the `retrieval_used` flag always reflects an executed retrieval tool = 1.0), while
`unregistered_tool_attempts` confirms low-level store names (`search_vector_store`,
`search_bm25`, `search_compensation_repository`, …) are rejected, never executed.

## 4. Internal naming is intentionally stable

To evolve functionality first and avoid churn/regression risk, Sprint 4 **does
not** rename internal identifiers:

- Packages: `src/copilot`, `src/career`, `src/interview`, `src/integration`,
  `src/core`, `src/ui`.
- Class names, database tables, migration identifiers, environment variable
  names, API/provider configuration names, stable persistence keys, and RAGAS
  artifact structures.
- The GitHub repository is **not** renamed in Sprint 4.
- No package-wide `copilot → agent` rename.

Only the **user-facing product name** changed (Interview OS Coach → Intelligent
Interview Coach). Bare "Interview OS" shell/architecture terms in code comments and
internal docstrings are internal references and are left as-is.

---

## 5. Sprint 3 reviewer feedback record

**Positive:**
- Strong code organisation.
- Clear, understandable project.
- Strong documentation; Mermaid diagrams helpful.
- Good developer habits; conventional commit prefixes.
- Dockerised app; environment templates.

**Improvement points:**
- Some referenced LLMs were outdated.
- Retrieval should be exposed as a **tool** rather than only a predetermined step.

**How Sprint 4 addresses them:**
- A **model registry / current-model review** will be added in a later Sprint 4
  phase (not changed in Phase 0, to avoid runtime behaviour change).
- **Retrieval is now an explicit agent tool** — `SearchCareerKnowledge`, delivered
  in **Phase 6 (Agentic RAG, §3g)**: the agent decides *whether* to retrieve while
  the deterministic Sprint 3 router still decides *which* lanes, internals preserved.

---

## 6. Current vs planned capability matrix

| Capability | Sprint 3 (current) | Sprint 4 (planned) |
|---|---|---|
| Career Intelligence | ✅ | ✅ (via agent tools) |
| Advanced RAG | ✅ | ✅ |
| Structured retrieval | ✅ | ✅ (inside retrieval tool) |
| Hybrid retrieval | ✅ | ✅ (inside retrieval tool) |
| Function / tool calling | ✅ | ✅ (agent-selectable) |
| RAGAS evaluation | ✅ | ✅ (extend to agent runs) |
| Interview Practice | ✅ | ✅ |
| Persistence | ✅ | ✅ |
| Authentication | ✅ | ✅ (adapt to API frontend) |
| Security guards | ✅ | ✅ (preserved) |
| Docker | ✅ | ✅ |
| CI / testing | ✅ | ✅ |
| FastAPI backend | — | 🔷 |
| Next.js / TypeScript frontend | — | 🔷 |
| LangGraph orchestration | — | 🔷 |
| Agent-selectable tools | — | ✅ (5 real Career tools, Phases 5–6) |
| Agentic RAG | — | ✅ (Phase 6 — `SearchCareerKnowledge`) |
| Short-term memory | — | 🔷 |
| Long-term memory | — | 🔷 |
| Human-in-the-loop (HITL) | — | 🔷 |
| Agent Inspector UI | — | 🔷 |
| Agent evaluation metrics | — | 🔷 |

See also [sprint4_requirements_map.md](sprint4_requirements_map.md) and
[sprint4_roadmap.md](sprint4_roadmap.md).
