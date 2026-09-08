# CLAUDE.md — Intelligent Interview Coach

Guidance for AI-assisted development in this repository. These describe the
**current** architecture and constraints (the project has grown well beyond its
original Sprint 1 scope). Historical Sprint 1 notes live in git history and the
`docs/` write-ups — do not treat them as current constraints.

## Product

**Intelligent Interview Coach** — one Streamlit application (`streamlit run app.py`, one
URL) combining two modules:

- **Career Intelligence** — evidence-grounded career guidance and interview
  preparation using retrieval-augmented generation over a labour-market/careers
  knowledge base. Backend in `src/copilot/*` (LangChain over OpenRouter,
  embeddings, Chroma vector search, BM25 + hybrid retrieval, query translation,
  structured multi-lane retrieval, domain tool calling, citations, prompt-
  injection security); Streamlit UI adapter in `src/career/ui.py`.
- **Interview Practice** — realistic interview simulation, rubric evaluation,
  Interview Deep Dive, final report, voice (recorded) practice, and an
  experimental Live mode. Domain services in `src/*.py`; UI in
  `src/interview/studio_app.py`.

The product is **generic across professions** (software, healthcare, finance,
trades, public sector, …), any level, any interview type. No profession-specific
assumptions in core logic, prompts, scoring or examples.

## Architecture

- **Modular Streamlit monolith.** `app.py` owns page config + top-level
  navigation and delegates to the two modules; business logic lives in `src/`.
- **Career backend/UI split.** `src/copilot/*` is the domain backend (no
  Streamlit import); `src/career/ui.py` renders it. The backend is unit-testable
  without a UI.
- **Typed integration handoff.** `src/integration/*` is the only cross-module
  surface — a plain `PreparationContext` carries a target role, requirements,
  gaps and grounding sources from Career Intelligence to Interview Practice. No
  Chroma/LangChain/DB objects cross the boundary.
- **Application layer (Sprint 4 Phase 1).** `src/application/*` is a thin,
  Streamlit-free boundary the UI consumes and a future FastAPI backend will reuse:
  `CareerApplicationService`, `InterviewApplicationService`, `history_service`,
  `knowledge_service`, `evaluation_service`, plus `factories` and safe `errors`.
  It imports no Streamlit and no UI module (enforced by
  `tests/test_application_boundary.py`); the UI may import it, never the reverse.
  See `docs/sprint4_architecture.md`.
- **FastAPI backend (Sprint 4 Phase 2).** `src/api/*` is a thin, typed HTTP layer
  over `src/application` (base path `/api/v1`); run with
  `uvicorn src.api.main:app --reload`. Streamlit and FastAPI coexist over the same
  application layer. Routes hold no business logic; errors return a safe envelope;
  every request carries an `X-Request-Id`; CORS comes from `FRONTEND_ORIGINS`.
  In-progress interview state uses a transitional, bounded, user-scoped in-memory
  store; identity is a transitional header-based boundary (production needs a real
  gateway/OIDC). No LangGraph yet. See `docs/sprint4_architecture.md`.
- **Next.js frontend foundation (Sprint 4 Phase 3B).** `frontend/*` is a Next.js 15
  (App Router) + React 19 + TypeScript + Tailwind client of `/api/v1`, implementing
  the Precision Coach design system (`docs/design/phase3a/`). Streamlit and Next.js
  coexist over the same application layer. **Phase 3C** made `/prepare` live: the
  coach (`career/chat`), the four preparation tools, sources (`knowledge/*`),
  history (`history/*`) and the `PreparationContext` → `interviews` handoff all run
  against the FastAPI contracts (no Career logic in TypeScript; retrieval stays
  deterministic; LangGraph still planned). Frontend gates: `cd frontend &&
  npm run lint && npm test && npm run typecheck && npm run build` (+ `npm run e2e`;
  Playwright runs serially and never reuses a server in CI). Hand-written TS
  contracts are guarded by `tests/test_openapi_contract.py`. No server secrets reach
  the browser (only `NEXT_PUBLIC_*`); no private preparation data in `localStorage`.
- **LangGraph agent foundation (Sprint 4 Phase 4).** `src/agent/*` is a single,
  stateful, bounded (`MAX_AGENT_STEPS`), tool-using LangGraph agent running
  side-by-side with the deterministic Career flow (unchanged). Tools go through a
  strict **allowlist** registry (unknown names never execute; no dynamic import);
  events are safe/observable (never chain-of-thought, prompts or raw provider
  output); model/tool failures terminate safely. Boundary:
  `src/application/agent_service.py` (`AgentApplicationService.run → AgentRunResult`);
  experimental `POST /api/v1/agent/run` (does **not** replace `/career/chat`).
  **Phase 5** registers the four real Career tools as thin adapters over
  `CareerApplicationService` (job analysis + question generation are LLM-backed;
  gap analysis + preparation plan are deterministic). Tools enforce preconditions
  from prior state (gap needs the job-analysis requirements; the planner needs the
  gaps) and never fabricate inputs; where sufficient, the run builds the existing
  `PreparationContext`. **Phase 6 (Agentic RAG)** adds the fifth real tool,
  `SearchCareerKnowledge`, a thin adapter over a **retrieval-only** operation
  (`CareerApplicationService.search_knowledge` →
  `CareerIntelligenceService.retrieve_evidence`): the **agent decides *whether*** to
  retrieve; the **deterministic Sprint 3 router still decides *which*** lanes/sources
  (the model never sees low-level stores — `search_vector_store`/`search_bm25`/
  repositories are never registered). The tool runs retrieval ONLY — it does **not**
  execute the other Career tools and does **not** synthesize a final answer (the
  agent owns those; the tool returns evidence, not an answer). `answer()` and
  `retrieve_evidence()` share one `_gather_evidence` extraction (no duplicate
  retrieval engine). Retrieval is de-duplicated within a run (cache identity = the
  query, which alone determines geography/occupation/lane), retrieved content stays
  **untrusted DATA**, citations come only from retrieved evidence, and the
  deterministic `/career/chat` endpoint (`answer()`) is unchanged. A
  deterministic orchestration regression lives in
  `evaluations/agent/tool_selection_cases.json` + `src/agent/eval.py` (33 cases,
  incl. retrieval recall / unnecessary-retrieval / citation-validity metrics; not a
  live-LLM benchmark). `src/agent` imports no Streamlit/UI and makes no provider
  call on import; HITL Phase 8.
- **Long-term preparation memory (Sprint 4 Phase 7).** Two DISTINCT kinds of memory:
  the LangGraph run state / checkpoint is **short-term** (transient `MemorySaver`);
  **long-term** memory is a selective, user-scoped, durable DB table
  (`preparation_memories`, Alembic `0002`) of preparation facts — a `category` (fixed
  enum), a concise `summary` (≤500 chars) and an optional `target_role`. It NEVER
  stores whole conversations, JDs, CVs, transcripts, answers, retrieved evidence,
  provider responses or system prompts, and has no protected-trait categories.
  `src/memory.py` (vocabulary/bounds/DTO) → `src/repository.py:MemoryRepository`
  (user-scoped) → `src/application/memory_service.py` (validate/bound/dedupe/
  `load_for_agent`) → `POST/GET/DELETE /api/v1/memory`. **Writes are explicit and
  user-initiated only** — the agent never persists memory automatically in Phase 7
  (agent-proposed, human-approved writes are Phase 8). At run start the agent loads a
  bounded (≤10), deterministic set (role-matched then general; no vector search, no
  model call) and injects it as trust-separated **DATA** (never system instructions);
  a saved injection string cannot escape the tool allowlist. Precedence: current
  request → current context → saved memory. A safe `memory_loaded` event records
  counts/categories only. The `/progress` page shows saved memory (grouped, with
  delete).
- **Human-in-the-loop (Sprint 4 Phase 8).** Real LangGraph `interrupt()` /
  `Command(resume=...)` on a **durable** checkpoint. A dedicated `human_review` node
  pauses for three (and only three) decisions — ambiguous-role confirmation
  (`CONFIRM_ROLE`, triggered deterministically when retrieval is ambiguous),
  approval-gated memory writes (`APPROVE_MEMORY`, from the `ProposePreparationMemory`
  action tool, which proposes but never persists), and practice handoff
  (`APPROVE_PRACTICE_HANDOFF`, from `RequestPracticeHandoff`; sets a flag, never
  creates an interview in the graph). These two action tools are registered but
  counted **separately** from the five Career tools. `interrupt()` is the first
  statement in `human_review` so replay runs no side effect before the pause;
  approvals apply once (guarded by `human_decisions` + memory dedupe). Decisions are
  validated against the current pending action *before* the graph is touched (invalid/
  stale → `422`/`409`, run stays paused); a human response is untrusted input. Owner-
  scoped API: `POST /api/v1/agent/run`, `GET /api/v1/agent/runs/{id}`,
  `POST /api/v1/agent/runs/{id}/resume`; ownership is read from the checkpoint, not an
  in-process map. Checkpointer: official `SqliteSaver`/`PostgresSaver` via
  `src/agent/checkpoint.py` (`AGENT_CHECKPOINT_DATABASE_URL` → app DB fallback;
  `langgraph-checkpoint-sqlite` pinned `2.0.x` to keep `langgraph-checkpoint` on `2.x`);
  saver-owned schema, separate from Alembic (no `0003`). **Fail-closed:** when
  durability is explicitly configured (explicit checkpoint URL, or a Postgres URL)
  and the saver can't be built, construction raises `AgentConfigurationError` →
  safe `503` — never a silent `MemorySaver` downgrade; `MemorySaver` is allowed only
  for an explicit `:memory:` or a dev sqlite-file fallback (`durable=False`, and an
  injected saver declares durability explicitly, never guessed). Approved-memory
  writes are **truthful**: `memory_saved` only on real success/dedupe, else
  `memory_save_failed` + a safe warning (never a raw DB error or the memory text; the
  run still completes). `awaiting_human_input` is a normal status; `MAX_AGENT_STEPS`
  preserved and `step_count` never reset on resume. Durable checkpoint (execution
  state) is separate from long-term memory (approved cross-session knowledge).
- **Agent Coach + Inspector + multi-turn (Sprint 4 Phase 9).** `/prepare` renders the
  candidate-facing **Agent Coach** (real LangGraph agent) when the backend advertises
  `agent_coach_enabled` (env `AGENT_COACH_ENABLED`); otherwise it stays on the
  deterministic Career flow (safe rollback; `/career/*` and Streamlit untouched).
  `/capabilities` now reports the true agent state. Same-thread **multi-turn**:
  `POST /api/v1/agent/runs/{id}/messages` (`continue_run`) appends a user turn via
  `update_state(as_node="initialise")` + resumes at `agent` — SAME run/thread, never a
  new run; owner-scoped; refused while `awaiting_human_input`. `MAX_AGENT_STEPS` now
  bounds each USER TURN (`turn_step_count`; reset per turn, never on HITL resume);
  `step_count` stays the thread-lifetime total. `AgentRunResponse.conversation` is a
  bounded (30) candidate-safe `{role,content}` projection (never system/tool/internal
  messages); the run id lives in `?run=` (random, owner-scoped) for refresh via
  `GET /agent/runs/{id}`. HITL renders as Precision Coach approval cards
  (`components/agent/*`); an approved handoff creates the interview in the FRONTEND
  (`POST /interviews`) → `/practice`, never inside LangGraph. Interview creation is
  **idempotent** via an `Idempotency-Key` header (`agent-handoff:<run_id>`) →
  `InMemorySessionStore.create_or_get(user_id, key)` (user-scoped, bounded, eviction-
  cleaned, in-process): refresh/remount/retry resolve to the SAME session with NO
  repeated strategy/first-question generation. The frontend never fabricates
  industry/`career_level` — it sends the PreparationContext (backend derives them from
  `seniority`); a genuine gap returns `422` and a completion card sources career levels
  from `GET /interviews/options`.
  Per-thread resume/continue is serialised with an in-process lock (multi-process
  needs shared locking — documented). **Agent Inspector** (`/review/agent`) shows
  owner-scoped, observable-only execution (never CoT/prompts/raw checkpoint; token/cost
  honestly "not captured"). No model modernisation; production auth still transitional.
- **Model registry (Sprint 4 Phase 9.5).** One typed source of truth
  (`src/llm/models.py`): `ModelProfile` = Fast/Balanced/Advanced → current OpenRouter
  slugs (`openai/gpt-5.6-luna`/`terra`/`sol`), overridable via
  `OPENROUTER_MODEL_FAST|BALANCED|ADVANCED`. A `Workload`→profile policy makes the
  cost/quality trade-off explicit. Two selection modes (`ModelSelectionMode`):
  **REGISTRY** workloads (Agent/Career synthesis/JD/questions → Balanced; utility/RAGAS
  → Fast) resolve their EFFECTIVE model centrally; **INTERVIEW_SESSION** workloads
  (strategy/questions/evaluation/report) use the one candidate-selected session profile
  (default Balanced) — Advanced is only a *recommended* tier for evaluation/report, not
  effective per-operation (no interview redesign; `effective_interview_profile(model)`
  resolves the real tier). Gap analysis + preparation planner stay
  **deterministic/no-model**. `constants.DEFAULT_MODEL`/
  `LOW_COST_MODEL`/`HIGH_CAPABILITY_MODEL` and the Career `DEFAULT_MODEL` are thin
  aliases resolving from the registry (no second source). Capability metadata (tools,
  structured output, temperature, reasoning hint) lives with the registry; temperature
  is omitted for the reasoning family; the agent factory fails closed if its profile
  lacks tool support. Legacy slugs (`gpt-5-mini`→Balanced, `-nano`→Fast, `gpt-5`→
  Advanced) coerce via `ApprovedModel` synonyms so saved sessions never crash. No live
  OpenRouter call at import/`/health`; provider reasoning is never stored/logged/exposed.
  The Interview service keeps one candidate-selected profile per session (default
  Balanced); per-operation tiering is a deferred follow-up (no interview redesign).
- **Providers.** Career Intelligence uses LangChain over OpenRouter; the
  Interview module uses a direct OpenRouter HTTPX client. Optional speech
  (`[speech]`) and Live (`[live]`) backends are lazily imported. **Live is
  experimental and OFF by default** — it surfaces only when
  `INTERVIEW_LIVE_ENABLED=true`, and its lifecycle (provider-driven barge-in,
  token-expiry refresh, bounded reconnect) lives in the browser component
  (`components/live_interviewer/frontend`, unit-tested via `lifecycle.ts`). There
  is **no camera/visual coaching**: the product never requests camera access
  (asserted by an e2e test); delivery coaching is timing/pacing only.
- **Retrieval.** Structured stores (SQLite: roles, competency, compensation,
  labour-market, credentials) + a Chroma vector store with a local-hash embedder
  fallback; a deterministic router picks lanes; hybrid (vector + BM25) fusion.
- **Persistence & auth.** SQLAlchemy ORM over SQLite (dev/tests) or PostgreSQL
  (production, schema owned by Alembic — see `docs/operations_deployment.md`);
  interview history is per-user with strict isolation. Auth in `src/auth.py`.
- **Evaluation.** Deterministic, offline retrieval/coverage evaluations are the
  primary CI gate (11R, 11R-A, KB-2, product coverage, quality_v2,
  faithfulness_v2). **RAGAS** is an *optional* secondary generation-quality layer
  (`[evaluation]`), never in normal CI — see `docs/ragas_evaluation.md`.
- Constants live in `src/constants.py` (interview) and `src/copilot/constants.py`
  (career). Configuration is loaded via config modules: secrets/env first, never
  a hard-coded key, controlled missing-configuration results — never a crash.
- Prefer explicit, readable Python. Type hints on functions; docstrings on public
  functions and classes.

## Security & privacy constraints

- Never hard-code, print, log or commit an API key or any secret.
- Treat job descriptions, candidate backgrounds, answers, retrieved documents and
  uploaded files as **untrusted** content: enforce input length/size limits,
  scan for prompt injection, and place retrieved/tool content in trust-separated
  blocks that are never followed as instructions.
- Never expose a full system prompt through the UI; never request hidden
  chain-of-thought (use structured evaluation with concise explanations).
- Never fabricate candidate achievements, credentials, examples, metrics or
  evaluation scores. Never store protected demographic characteristics or make
  personality/health diagnoses. Interview scores are practice feedback, not a
  hiring decision.
- RAGAS and other evaluators run only on public benchmark data, never on private
  candidate/company content, and only when their credentials are configured.

## Testing

- Pytest for all automated tests; never make live/paid provider calls in tests
  (mock the boundaries). Do not weaken tests to pass or silently swallow errors.
- Tests must not mutate committed artifacts (write to `tmp_path`).
- `ruff check .` (conservative `F`/`E9` rules) must pass.
- Current measured suite on this branch: **1526 passed, 2 skipped** (the skips are
  the RAGAS installed/absent guards). Re-measure with `pytest -q` rather than
  hard-coding a number in multiple places.

## Git rules

- Remote: `moaltamimi-unbiasedtalent/Interview-OS-Coach` (`origin`). Turing
  submissions are pushed to the `TuringCollegeSubmissions/*` remote.
- Work on a feature branch; open a PR. **Do not auto-merge.** Commit and push only
  when a phase/prompt instructs it.
- End commit messages with `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.
- Never commit `.env`, `.streamlit/secrets.toml`, virtual environments, caches,
  generated evaluation runs, or `node_modules`.

## Explainability

The owner must be able to explain every line in a review: keep code simple,
comment the *why* where non-obvious, and keep `docs/` current after each phase
(files changed, functionality, commands, test results, risks, review concepts).
