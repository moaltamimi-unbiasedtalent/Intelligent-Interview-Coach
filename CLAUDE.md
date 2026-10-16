# CLAUDE.md — Intelligent Interview Coach

Guidance for AI-assisted development in this repository. These describe the
**current** architecture and constraints (the project has grown well beyond its
original Sprint 1 scope). Historical Sprint 1 notes live in git history and the
`docs/` write-ups — do not treat them as current constraints.

## Product

**Intelligent Interview Coach** — delivered primarily as **Next.js + FastAPI** (Streamlit
`streamlit run app.py` is a legacy/development interface), combining two modules:

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

- **Next.js + FastAPI is the primary product; Streamlit is legacy.** The current
  architecture is a Next.js 15 App Router frontend (`frontend/`) over a typed FastAPI
  backend (`src/api/`, `/api/v1`) sitting on the application layer (`src/application/`)
  and domain (`src/agent/`, `src/copilot/`, `src/interview/`). The original modular
  **Streamlit monolith** (`app.py` + `src/*/ui.py`) still runs over the same
  application layer but is a legacy/development interface. Business logic lives in
  `src/` and is UI-agnostic.
- **Career backend/UI split.** `src/copilot/*` is the domain backend (no
  Streamlit import); `src/career/ui.py` renders it. The backend is unit-testable
  without a UI.
- **Typed integration handoff.** `src/integration/*` is the only cross-module
  surface — a plain `PreparationContext` carries a target role, requirements,
  gaps and grounding sources from Career Intelligence to Interview Practice. No
  Chroma/LangChain/DB objects cross the boundary.
- **Application layer (Sprint 4 Phase 1).** `src/application/*` is a thin,
  Streamlit-free boundary the UI consumes and the FastAPI backend reuses:
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
  In-progress interview state is **durably persisted** (Phase 10) in the user-scoped
  `interview_sessions` table via `DurableInterviewSessionStore` (OCC + operation
  leases; the old in-memory store is a test/legacy helper only). **Identity (Capstone
  P1/E1):** real accounts — email/password registration, email verification, password
  recovery, server-side sessions in an HttpOnly cookie, and one bounded social provider
  (Google OIDC; live UNVALIDATED) — resolved by `get_current_user_id` in
  `src/api/dependencies.py`. The transitional `X-User-Subject` header is now
  **development-only** (rejected in production, never overrides a valid session);
  production is fail-closed (401 without a session). Platform roles, product
  entitlements, an audit log and an account lifecycle are established (see
  `docs/capstone/p1_e1_identity_platform.md`). The full LangGraph Agent Coach ships
  (Phases 4–9.5). See `docs/sprint4_architecture.md`.
- **Next.js frontend foundation (Sprint 4 Phase 3B).** `frontend/*` is a Next.js 15
  (App Router) + React 19 + TypeScript + Tailwind client of `/api/v1`, implementing
  the Precision Coach design system (`docs/design/phase3a/`). Streamlit and Next.js
  coexist over the same application layer. **Phase 3C** made `/prepare` live: the
  coach (`career/chat`), the four preparation tools, sources (`knowledge/*`),
  history (`history/*`) and the `PreparationContext` → `interviews` handoff all run
  against the FastAPI contracts (no Career logic in TypeScript; retrieval stays
  deterministic; the LangGraph Agent Coach and full durable Interview Practice landed
  in later phases — 4–11). Frontend gates: `cd frontend &&
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
  **Phase 5** registered the first four Career tools as thin adapters over
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
  counted **separately** from the Career evidence tools (the full, current allow-list is `career_tool_registry` in `src/agent/registry.py`: six Career tools, three specialist tools, two human-action tools). `interrupt()` is the first
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
  usage is captured with honest Complete/Partial coverage as of P1 — see the Agent
  cost/performance bullet below). (At that phase production auth was still transitional; current identity is described under **Persistence & auth**.)
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
- **Durable Interview Practice + full Next.js flow (Sprint 4 Phase 10).** In-progress
  interviews persist in the user-scoped `interview_sessions` table
  (`DurableInterviewSessionStore`, migration 0003): the FastAPI routes load a payload →
  mutate the **unchanged** `SessionManager` → serialise (`session_codec`, no pickle) →
  save under **optimistic concurrency** (`version`), with a stale-reclaimable
  **operation lease** guarding provider-backed steps and **durable idempotency** on
  create. Next.js drives the whole lifecycle (question → answer → typed evaluation →
  Deep Dive → complete → report; standalone setup + refresh/restart resume). Completed
  history is crash-safe/idempotent via `interviews.source_session_id` (migration 0004),
  saved AFTER the report is durably persisted; the fake Record control was removed.
  Streamlit is legacy/deprecated. See `docs/sprint4_interview_parity.md`.
- **Final evaluation + hardening (Sprint 4 Phase 11).** Deterministic agent
  orchestration eval (56 held-out cases, `src/agent/eval.py`, `scripts/eval_agent.py`,
  gated: required/retrieval recall, unnecessary rates, citation & retrieval-sequence
  validity, completion, unregistered attempts, HITL/cross-user probe). RAGAS preserved
  (opt-in paid). Logging is safe-by-default (unhandled handler no `exc_info` in prod;
  history failures metadata-only). Identity is **fail-closed in production** (401 with
  no supplied identity). Retention: `scripts/cleanup_runtime_data.py` (dry-run default)
  removes only stale in-progress sessions (never history/memory/checkpoints). Reviewer
  package in `docs/sprint4_{reviewer_guide,demo_script,final_evaluation,security_privacy}.md`.
- **Agent cost/performance (post-Sprint 4, P1 — measure first).** `src/agent/usage.py`
  is one canonical safe `AgentRunUsage` (agent/tool/total model-call counts, tokens,
  cost, `usage_complete` + `missing_usage_sources`). Outer agent usage is read from the
  returned `AIMessage`; tool-internal usage is captured at the AGENT boundary via
  LangChain's usage-metadata callback (the Sprint-3 structured-output path is unchanged).
  Each provider call is counted **once** (no double count); **unknown usage is never 0**
  (it flips `usage_complete=false`); cost is reported-or-resolver-or-`None` (never
  invented). An optional request `profile` selects the Fast/Balanced/Advanced registry
  model (validated Literal — a raw slug is rejected; a candidate can never send one);
  every tier keeps grounding, HITL, the tool allowlist and the bounded step budget (kept
  at 6 for all tiers). A bounded, **per-thread** retrieval cache (`retrieval_cache` in
  agent state, keyed by the normalised query) reuses evidence for an equivalent
  same-thread request — thread-scoped ⇒ per-user/per-run, never shared; hit/miss counts
  are observable, keys are never logged/exposed. `AgentRunResult`/`AgentRunResponse` carry
  `usage`, `profile`, `latency_ms`, `cache_hits/misses`; the Coach shows a subtle usage
  line and the Inspector a full safe breakdown. No paid comparative benchmark executed.
  See `docs/sprint4_final_evaluation.md` §11.
- **Memory management UX (post-Sprint 4, P2).** Long-term preparation memory is now
  candidate-controlled (trust model unchanged: selective, user-scoped, bounded,
  explicitly approved, DATA only). A `pinned` column (Alembic `0005`, single head) adds
  a deterministic load-priority signal — NOT an instruction and never overriding the
  current request; load order is role-matched pinned → role-matched → general pinned →
  general (no-role variant symmetric), capped at 10, different-role excluded.
  `MemoryApplicationService.update` (partial, shared validators, dedupe-excluding-self →
  `409`) backs `PATCH /api/v1/memory/{id}`; `GET /api/v1/memory/preview` delegates to
  the SAME `load_for_agent` so a next-run preview cannot drift. HITL gains
  edit-before-save: an `APPROVE_MEMORY` approval may carry an edited `memory`
  (category/summary/target_role only, validated before resume; pinned/source_run_id/
  user_id/graph-state rejected), persisted via the same `create` path, still untrusted
  DATA. `AgentApplicationService.delete_run` + `DELETE /api/v1/agent/runs/{id}` delete
  ONLY a run's checkpoint thread via the saver's official `delete_thread` (no raw SQL;
  unsupported saver reported truthfully, never faked). Settings is the primary memory
  UI (edit/pin/delete/preview); `/progress` links to it; a safe Coach cue shows loaded
  memory count + summaries. See `docs/sprint4_architecture.md` §3h.
- **Candidate journey + handoff transparency (post-Sprint 4, P4).** `src/agent/journey.py`
  holds two PURE derivations over safe state (no model call, no chain-of-thought, no raw
  tool args/checkpoint): `derive_journey` → UNDERSTAND→PREPARE→PRACTISE with each stage
  status derived ONLY from real structured outputs (plus the per-tool booleans the UI
  checklist reads), and `derive_handoff_summary` → a candidate-safe
  `PracticeHandoffSummary` (target role + focus areas + question count, each with a
  truthful source) that PROJECTS the existing PreparationContext — only fields that
  exist, never fabricated. Both ride on `AgentRunResult`/`AgentRunResponse` (`journey`,
  `handoff_summary`). The frontend renders restrained journey chrome + an observable
  preparation checklist (completed controlled steps, never reasoning), a provenance-rich
  practice-handoff card, and a subtle "Prepared in your Coach session" note on Practice
  ONLY via the `?from=coach` handoff path (standalone shows none). Interview creation
  stays OUTSIDE LangGraph (idempotent frontend path — unchanged). Streamlit shows a
  legacy-interface banner; Next.js + FastAPI is the primary product. Pure
  UX/transparency — no new agent/tool/retrieval/memory/interview behaviour.
- **Feedback loop + observability (post-Sprint 4, P5).** Candidate feedback
  (`src/feedback.py`, `user_feedback` table, Alembic `0006`, single head) is a
  user-scoped rating (helpful/not_helpful) + optional bounded comment attached BY
  REFERENCE to one output — an Agent answer (stable `response_id` = `<run_id>:<absolute
  assistant index>`, never a content hash), an interview evaluation (`session:question`)
  or a final report (`session`). It stores NO copy of any rated content; the comment is
  untrusted text, never fed into any prompt/tool/policy. `FeedbackApplicationService`
  validates + verifies target OWNERSHIP (injected per-surface verifiers: agent-run owns
  / session owns) → foreign/unknown is not-found; idempotent upsert; safe aggregate
  metrics. **Exact-target validation (P5.1):** each verifier proves the EXACT rated
  output exists AND is owned — an assistant message with that `response_id` in the run's
  safe conversation, an Interview question with a completed evaluation at that position,
  or a session that has generated its final report — never just parent ownership;
  foreign/unknown/malformed/nonexistent targets all return the same safe not-found
  (`src/api/feedback_targets.py`, fail-closed). `POST/GET/DELETE /api/v1/feedback`
  (server sets user_id). The loop is
  human-reviewed (`scripts/export_feedback_summary.py`, aggregate-only unless
  `--include-comments`) — NEVER autonomous self-modification. Observability
  (`src/observability/`) is a provider-neutral `ObservabilitySink`: NoOp default
  (external OFF via `AGENT_EXTERNAL_OBSERVABILITY_ENABLED`), optional Langfuse sink
  emitting ONLY a sanitised allow-listed projection via manual events (never the
  auto-trace callback → no prompt/content capture), lazily imported, best-effort (a
  provider outage never breaks a run/interview/feedback). Unknown usage stays None
  (never 0). The Agent Inspector remains the primary first-party view. See
  `docs/sprint4_reviewer_guide.md`.
- **Providers.** Career Intelligence uses LangChain over OpenRouter; the
  Interview module uses a direct OpenRouter HTTPX client. Optional speech
  (`[speech]`) and Live (`[live]`) backends are lazily imported. **Live is
  experimental and OFF by default** — it surfaces only when
  `INTERVIEW_LIVE_ENABLED=true`, and its lifecycle (provider-driven barge-in,
  token-expiry refresh, bounded reconnect) lives in the browser component
  (`components/live_interviewer/frontend`, unit-tested via `lifecycle.ts`). There
  is **no camera/visual coaching**: the product never requests camera access
  (asserted by an e2e test); delivery coaching is timing/pacing only.
- **Store paths are anchored (W12.4A).** Every default store path (Chroma, the five structured SQLite stores, manifests, build metadata, the research cache and the default application database URL) derives from one data root, the repository `data/` directory or `COPILOT_DATA_DIR`, and is never relative to the process working directory (a process started elsewhere used to see an empty knowledge base, and an API and a worker could use different stores). Mo's agent shares the same career service and Admin-governed retriever as `/career/chat`. Admin Knowledge has derived readiness, an active inventory and a retrieval-only test (`docs/capstone/knowledge/W12_04A_KNOWLEDGE_ACCESSIBILITY_OPERATIONS.md`).
- **Retrieval.** Structured stores (SQLite: roles, competency, compensation,
  labour-market, credentials) + a Chroma vector store with a local-hash embedder
  fallback; a deterministic router picks lanes; hybrid (vector + BM25) fusion.
- **Persistence & auth.** SQLAlchemy ORM over SQLite (dev/tests) or PostgreSQL
  (production, schema owned by Alembic — single head, currently `0031_account_closure` (see `migrations/versions/`); see
  `docs/operations_deployment.md`); interview history is per-user with strict
  isolation. Identity is server-side accounts and sessions (HttpOnly cookie); production is
  fail-closed; the `X-User-Subject` header and anonymous developer user exist only in
  development/test environments and never override a valid session; Google OIDC is implemented
  in the backend but disabled by default, not wired into the frontend and not validated live. Account authentication/authorization lives in `src/authsec/` (password
  hashing, tokens), `src/auth_repository.py`, `src/application/auth_service.py` and
  `src/application/authorization.py`; the Streamlit-side OIDC seam remains in
  `src/auth.py`. `src/security.py` is the (separate) prompt-injection guard.
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
- Tests must not mutate committed artifacts (write to `tmp_path`). **Test isolation (W9.12, durable):** `tests/conftest.py` disables `.env` loading, scrubs provider/model variables, forces a temp `DATABASE_URL`, refuses any SQLAlchemy engine that is not in-memory or in the system temp directory, and fails the session if development stores (`data/*.db`, checkpoints, caches) change. Never open the development database or call a live provider from a test; CI also fails if tests/evaluators dirty the working tree. Evaluators write to a temp dir unless run with `--write`.
- `ruff check .` (conservative `F`/`E9` rules) must pass.
- Test totals: **always re-measure with `pytest -q`** rather than trusting a number
  copied across docs (historical docs cite different totals from their own point in
  time — that is expected, not a defect). Measured totals are recorded per wave in the evidence documents under `docs/capstone/p10/w9/` and by CI; do not copy figures here (the per-phase numbers once listed in this bullet were period evidence).
  Known baseline: a few model-registry tests depend on a local `.env` (`OPENROUTER_MODEL_*`) and fail in a dirty local environment only (TD-W9-02 scope).

- **Multilingual turn-based voice (Capstone P7 + E5).** A bounded voice MODALITY (not a
  human-trait signal): hear Mo/questions via browser TTS and answer by speaking via the reused
  P3 STT, with editable transcripts and explicit submission preserved. New TTS layer mirrors
  the P3 STT seam under `frontend/lib/speech/`: `ttsTypes.ts` (`SpeechOutputAdapter`),
  `speechSynthesisAdapter.ts` (browser `speechSynthesis`), `useSpeechOutput.ts` (state machine
  IDLE/SPEAKING/PAUSED/STOPPED/UNSUPPORTED/ERROR; cancels on unmount — no zombie speech),
  `ttsLocales.ts` (7-language product→speech locale map + honest per-language status),
  `speechText.ts` (`toSpeechText` — deterministic markdown/link/URL/citation sanitiser, NO LLM;
  citations→"sources on screen"), `fakeSpeechOutputAdapter.ts`. `components/ui/VoicePlaybackControl.tsx`
  (Listen/Stop; renders null when unsupported) is wired into `AgentConversation` (speaks
  `presentation.answer`, brief-first) and `PracticeClient` (the visible question). **Invariants:**
  speech never auto-submits; TTS never auto-opens the mic (no voice loop); **STT and TTS are
  mutually exclusive per surface** via a shared `voiceCoordination` provider (both hooks claim/
  release one audio channel; starting one stops the other, never auto-starts it, never clears
  text; `/prepare` + `/practice` wrap the provider); Practice evaluation
  stays TEXT-only; speech-output language follows the Mo conversation language and never changes
  career geography; Ask4Mo stores NO audio (no MediaRecorder/Blob/voiceprint) and derives NO
  human-trait signal (emotion/accent/confidence/personality/intelligence/honesty/hiring — none);
  voice preference is device-local (localStorage); Admin sees only speech *architecture*
  metadata; workspaces never auto-share audio/voice. Realtime/streaming voice (C1) is DEFERRED.
  Deterministic gate `scripts/eval_voice_experience.py` (26 invariants incl. the human-trait
  prohibition scanned as code identifiers) + `tests/test_voice_experience_p7.py`; unit
  `tests/voice-output.test.tsx`; Playwright `e2e/voice.spec.ts` (fake speech engines). i18n
  `voice` namespace across the 7 locales then supported (8 now; speech remains 7 languages). No migration (Alembic head `0011_workspaces_shares`); 0
  paid/speech-provider calls; live human voice quality UNVALIDATED. See
  `docs/capstone/p7_voice_architecture_audit.md` + `p7_e5_voice_experience.md`.
- **Teams/Workspaces + Platform Admin (Capstone P6.5).** Bounded collaboration + a bounded
  operations console. Tables (migration `0011_workspaces_shares`, head now
  `0011_workspaces_shares`): `workspaces`, `workspace_memberships` (role WORKSPACE_OWNER/MEMBER
  **on the membership**, never on the User), `workspace_invitations` (opaque token stored
  **hashed**, single-use, 72h expiry), `share_grants` (owner + workspace + resource + VIEW +
  status), plus a `user_feedback.category` column (P6 taxonomy). `src/workspace_repository.py`
  is owner/workspace-scoped; `src/application/workspace_service.py` +
  `src/application/sharing_service.py` enforce every invariant server-side and audit them.
  **Private-by-default**: joining a workspace exposes nothing — the only cross-member access
  is an explicit, allow-listed, **VIEW-only** share grant — operational types **interview
  report + story** (both wired to owner-scoped loaders + bounded VIEW projections;
  preparation summary is PLANNED/excluded); never raw documents/CV/Memory/auth/audit.
  Ownership never transfers;
  revocation and source deletion cut access immediately (the decision is re-derived on every
  read via `active_share_owner_for_member`, so a cached link can't bypass it); shared content
  is read **as the owner** (owner scoping intact). Invitations require the accepting account's
  own email to match (no foreign acceptance), are single-use and expiring; the last owner
  can't orphan a workspace; leave/remove revokes that member's outbound shares. **Platform
  Admin** (`src/api/routes/admin.py`; since W10.1 every route declares an explicit `require_permission(...)`) is an OPERATIONS
  surface, **not a data superuser**: account/workspace/entitlement/privacy/provider/audit
  **metadata only** (no CV/answers/Memory/documents), audited privileged changes (role/tier/
  status) with self-lockout guards, no "view as user", no private-data search, owner-scoped
  repos stay owner-scoped. Teams access is a **separate dimension from BASIC/PREMIUM**; no
  billing at that phase (billing/payment administration is now planned under P10B-W10; enterprise SSO remains out of scope). Admin reuses the P6 reviewer APIs (no second backend;
  no-auto-promotion preserved). Candidate `FeedbackControl` gains an optional bounded category
  (P6 taxonomy), i18n across the locales then supported (7; 8 now). Routes: `/api/v1/workspaces/*`, `/api/v1/shares/*`,
  `/api/v1/admin/*`; frontend `/workspaces` (candidate, i18n) + `/admin` (English ops).
  New CI gates: `eval_workspace_security`, `eval_platform_admin`. See
  `docs/capstone/p6_5_workspace_admin_design.md` + `p6_5_workspaces_platform_admin.md`.
- **Knowledge governance, Prompt Lab & feedback learning (Capstone P6 + E6 + E7).** A
  governance layer over the UNCHANGED KB plus three governed systems. **Knowledge (K1–K4):**
  `src/copilot/knowledge/governed_datasets.py` + committed `data/knowledge/governed/*.json`
  add bounded, reviewed datasets with **abstention-first** access — K1 German occupation
  compensation (provenance + pay unit + reference year; never invents a salary), K2
  credentials/regulated-professions matrix (required vs preferred + authority lineage), K3
  versioned role aliases (confident exact matches only; never overrides existing
  resolution), K4 additional Adzuna operations as a bounded, allow-listed, parameter-validated
  spec (live UNVALIDATED / cost-gated, no live call). `src/copilot/knowledge/governance.py`
  adds a first-class **Knowledge Manifest**, a **deterministic readiness** state machine
  (`ReadinessState`; READY ≠ "folder exists" — a fresh clone honestly reports
  SOURCE_MISSING/INDEX_MISSING for the generated stores), **source health**, a **coverage
  matrix** (no universal-coverage claim) and the **7-language boundary** (UI support ≠ KB
  content coverage). The committed deterministic **RAGAS** baseline (0.6757/0.5161) is
  preserved; the model-judged judge is NOT RUN. **E6 Prompt Lab** (`src/application/prompt_lab/`)
  is a bounded, admin-only, human-reviewed experiment framework: variants over
  prompt/model-policy/specialist CONFIG run against fixed deterministic evaluators with NO
  live model and NO cost, isolated from production (a run never mutates the model policy),
  with **no auto-promotion** (`applied_to_production=False` always) and prompt/config version
  identity (`src/config_versions.py`). **E7 feedback learning** builds on the offline
  Feedback Intelligence (7G): a bounded taxonomy (`src/feedback_taxonomy.py`) + an
  improvement-candidate lifecycle (`src/copilot/feedback_intelligence/improvement.py`:
  PROPOSED→TRIAGED→EXPERIMENTING→ACCEPTED→IMPLEMENTED, human-only transitions, IMPLEMENTED
  never automatic) — governed improvement, never autonomous self-modification. **Retention**
  (`src/application/retention_service.py`): a classified inventory + a safe
  `TemporaryArtifactCleaner` (dry-run default, only under one root, idempotent). A
  PLATFORM_ADMIN-gated reviewer surface (`/api/v1/reviewer/*`) exposes readiness/manifest/
  coverage/source-health/config-versions/retention/Prompt Lab — candidates get 403; no
  secret/embedding/prompt/CoT leaks. `scripts/demo_readiness.py` fails non-zero on a missing
  KB. New CI gates: `eval_knowledge_governance`, `eval_prompt_lab`, `eval_feedback_learning`,
  `eval_retention` (all offline, 0 paid calls). No migration (Alembic head stays
  `0010_candidate_documents`). See `docs/capstone/p6_knowledge_current_state_audit.md` +
  `p6_e6_e7_knowledge_promptlab_learning.md`.
- **Bounded multi-agent architecture + per-operation model policy (Capstone P5 + E4).**
  Mo stays the SINGLE candidate-facing orchestrator (its ReAct loop/graph/nodes/HITL/RAG
  governance/Practice are unchanged). Three materially distinct **bounded specialists** sit
  BEHIND Mo, reached only through allowlisted tools (`src/agent/specialist_tools.py` →
  `career_tool_registry`): **Role & Opportunity** (`AnalyzeRoleOpportunity`, structured
  `RoleBrief`, reuses the governed JD-analysis op), **Candidate Evidence**
  (`FindCandidateEvidence`, **deterministic**, owner-scoped selection of APPROVED claims +
  verified stories via `EvidenceAccessService` — the `user_id` is TRUSTED run state, never
  model-supplied; rejected/unreviewed/`source_revoked`/`model_suggested` excluded at the
  repo; no model ⇒ injection-inert, never reads raw documents), and **Interview
  Strategy/Coach** (`BuildCoachingStrategy`, maps evidence→competencies, raises
  CLARIFICATION_NEEDED instead of inventing metrics; injectable reasoner + deterministic
  fallback — the live coaching model is UNVALIDATED, so the deterministic path ships and
  every test/eval makes 0 paid calls; a reasoner's evidence ids are re-validated against the
  owner-scoped set). Specialists are advisory (no side effects, no auto-memory, cannot start
  Practice) and never set `retrieval_used` (owned by `SearchCareerKnowledge`). Typed
  contracts in `src/agent/specialists/schemas.py`; a closed `SpecialistRegistry` +
  deterministic bounded `recommend_specialists` router validate routing. **E4**:
  `src/llm/policy.py` is ONE central per-operation model policy (operations ORCHESTRATION /
  SPECIALIST_ROLE_ANALYSIS / SPECIALIST_EVIDENCE_ANALYSIS / SPECIALIST_COACHING /
  FINAL_RESPONSE / STRUCTURED_GENERATION / EVALUATION), a pure resolver over
  `src/llm/models.py` (no provider call/secret at import). Effective tier = max(user
  profile envelope, operation min-capability floor), capped at Advanced; a deterministic
  operation declares `capability=NONE` (no client built); bounded lower-tier fallback to a
  floor (orchestration/final never degrade to Fast). Profile, per-operation policy,
  Brief/Detailed and interface/conversation/dictation language are independent — none
  changes the model; a raw client slug is rejected (`_resolve_profile` + `resolve_policy`
  accept only fast/balanced/advanced). Safe diagnostics only:
  `AgentRunResult.specialist_outputs` + `ResolvedModelPolicy.to_dict()` carry no
  CoT/secret/private content; no new candidate chat surface. Deterministic gate
  `scripts/eval_multi_agent.py` (7-language injection-inert fixtures, cross-user isolation,
  no-fabrication, id sanitisation) in CI; the existing `eval_agent` gate is unchanged. See
  `docs/capstone/p5_agent_decomposition_audit.md` + `p5_e4_multi_agent_model_policy.md`.
- **Private candidate documents (Capstone P4).** `src/documents/*` + `src/application/
  {documents_service,stories_service,report_export}.py` implement owner-scoped upload →
  validate → private store (`DocumentStore`, never a public URL) → parse (pypdf/
  python-docx/txt) or OCR (optional `[ocr]` extra; `OcrEngine` abstraction, live
  UNVALIDATED) → **deterministic, verbatim, provenance-bearing extraction (no LLM)** →
  user review → story bank (source-backed/revocation-aware) → MD/JSON report export.
  Candidate documents are **untrusted DATA and are never placed in an LLM prompt**;
  tables (migration 0010) cascade from `users.id`. See
  `docs/capstone/p4_e2_e3_documents_evidence.md` and `p4_privacy_data_inventory.md`.
  **P10B Wave 3 hardening:** failures carry a bounded taxonomy (`ParseError`/`OcrError.kind`
  → `document_versions.failure_kind`, migration `0012`; `DOC_FAIL_*` in `persistence.py`) so the
  UI shows a localized, actionable reason (a scanned/image doc with OCR uninstalled is
  `ocr_unavailable`, never "corrupt") — never a raw exception/path. `POST /documents/{id}/reprocess`
  re-runs the SAME pipeline on the already-stored file (owner-scoped) as the safe retry once OCR is
  enabled. **There is ONE governed upload pipeline and ONE upload component,
  `frontend/components/documents/DocumentUpload.tsx`** — reuse it (do not build a second uploader);
  Prepare/Practice integration is Wave 4. **OCR runtime (Wave 3 closure):** availability is verified
  against the real chain — `OcrEngine.is_available()` runs the Tesseract **binary**, scanned-PDF OCR
  also needs Poppler (`pdftoppm`); never mark OCR available merely because `pytesseract` imports.
  `deploy/Dockerfile.api` installs the runtime (`tesseract-ocr` + `-{deu,fra,spa,ita,por,nld}` +
  `poppler-utils` + `pip ".[db,ocr]"`, ~+150–200 MB); `ocr_runtime_status()` gives safe per-language
  availability at `GET /admin/providers`. Live/human OCR accuracy stays UNVALIDATED.

- **Internationalization coding standard (Capstone P3.5+).** New candidate-facing,
  user-visible strings MUST use the i18n system: add a key to the English source
  catalogue (`frontend/lib/i18n/messages/en.ts`) and every locale catalogue (de/fr/es/
  it/pt/nl/ru), and render via `useT()` / `translate()`. Interface language, Mo conversation
  language and dictation locale are **independent** settings, and a language choice never
  changes labour-market geography. Do not hard-code new English strings in candidate UI;
  reviewer/diagnostic-only text is exempt. See `docs/capstone/p3_5_i18n_l10n.md`.
  **P10B-W9.6/W9.7 — full localization, Russian, protected slogan (durable rules):** the product has
  **eight** interface/conversation locales (en/de/fr/es/it/pt/nl/**ru**), declared ONCE in
  `src/locales.py` (`SUPPORTED_LOCALE_CODES`, `AppLocale`) and `frontend/lib/i18n/locales.ts`
  (`APP_LOCALES`, Russian label "Русский"). Adding an app locale NEVER enables other dimensions: speech
  (dictation `DICTATION_LANGUAGES`, TTS `ttsLocales`, realtime `SUPPORTED_REALTIME_LOCALES`), document/OCR
  language (`DOCUMENT_LANGUAGE_CODES`), KB/taxonomy languages (`governance.SUPPORTED_LANGUAGES`; Russian is
  NOT an ESCO language) and labour-market geography (`CAREER_GEOGRAPHIES`; Russia is not a market) are
  separate lists; hide speech controls for a conversation language without speech support
  (`isSpeechOutputLocale`). A fragment missing a supported locale is a hard error (no silent English
  fallback). The deterministic scanner `frontend/scripts/scan-i18n.mjs` (+ `tests/no-hardcoded-english.test.ts`,
  `eval_i18n_l10n`) must stay at 0 unexplained candidate-facing literals, including copy stored in object
  literals. **The slogan "Ask More. Be More." is a protected brand invariant: it is NEVER translated,
  transliterated or re-punctuated in any locale (current or future).** It is defined once as `BRAND_SLOGAN`
  in `frontend/lib/brand.ts`; every locale's `common.tagline` is that constant; embedded copy uses the exact
  phrase; the scanner approves ONLY that exact string. Enforced by `tests/brand-slogan-invariant.test.ts`
  and `eval_i18n_l10n`. New languages are ENGINEERING translations until native/legal review. See
  `docs/capstone/p10/w9/P10B_W9_7_RUSSIAN_LOCALE.md`.
  **P10B-W9.7A - language ownership + guard + error tiers (durable rules):** two language dimensions own
  different text and must not be coupled: the **interface** language owns Ask4Mo UI chrome (labels, buttons,
  source summaries); the Mo **conversation** language owns everything Mo "says" - the model's prose AND the
  deterministic text standing in for it (the Career-chat response-template headings, the insufficient-evidence
  sentence/note, the "model unavailable" fallback). `/career/chat` takes a bounded optional
  `conversation_language`; bounded text lives in `src/copilot/rag/localized.py`; English/default output must stay
  byte-identical. `LANGUAGE_NAMES` has one copy (`src/locales.py`). The scanner also detects string-tuple arrays,
  JSX text mixed with `{}` expressions and HTML-entity text - never hide candidate copy in a literal array. Loading
  placeholders must be bounded and labelled and must resolve on every settled state (incl. auth `unknown`).
  `ErrorState` has three tiers: `section` (compact), `page` (default, proportional) and `fatal` (route error
  boundary only). Colour tokens are alpha-capable since W9.12 (`token()` helper in `frontend/tailwind.config.ts`; `bg-warning/10`-style utilities emit `color-mix(...)` of the same CSS variable); `frontend/tests/tailwind-token-opacity.test.ts` fails if any such utility would emit no CSS.
  **P10B Wave 2 — coaching style + onboarding:** Mo coaching style is a **bounded enum**
  (supportive/balanced/direct/challenging) in `src/coaching_style.py` → a **trusted allow-list-only
  directive** (`coaching_style_directive`) appended like the language directive. It sets only the
  TONE of coaching prose (Prepare Mo chat; interview **evaluation/report wording only**, never
  question/strategy generation) and NEVER changes scoring, rubric, evidence, difficulty, grounding
  or safety — never pass the raw code to the model. First-run onboarding is gated by
  `users.onboarding_completed_at` (NULL = pending; existing accounts backfilled to completed by
  migration `0013`); it reuses `user_preferences` + `PATCH /auth/preferences` (no parallel store).
  Preference ownership stays separate and independent: interface ≠ conversation ≠ dictation ≠
  **career_geography** (account-default market, never inferred from locale) ≠ session language
  (per-interview override). See `docs/capstone/p10/p10b_wave2_premium_onboarding.md`.
  **P10B Wave 4:** the INTERVIEW (Practice) generation language is a bounded
  `conversation_language` on `InterviewConfiguration` (persisted via the JSON session codec — no
  migration) turned into a trusted, allow-list-only directive by `prompts._language_directive`,
  injected into every task's SYSTEM prompt. The directive is PROSE-ONLY: it never changes scoring
  (LLM scores are not recomputed; the user-message DATA is identical across languages), evidence,
  grounding or geography. Never pass a raw language string to the model — resolve names only from the
  allow-list.

- **Prepare/Practice context seam (Capstone P10B Wave 4).** Prepare and Practice consume the ONE
  governed document system — reuse `frontend/components/documents/DocumentPicker.tsx` (over
  `DocumentUpload`); do not build a second uploader/endpoint/store. A candidate-selected JD is passed
  as `job_description_document_id` and resolved to text SERVER-side (owner-scoped,
  `DocumentsApplicationService.extracted_text` / `dependencies.resolve_document_text`) into the
  existing screened `job_description` DATA field — never expose raw document text to the client, and
  never open a new raw-model path. Candidate CV context comes ONLY from APPROVED evidence via
  `EvidenceAccessService` (`use_candidate_evidence` → `candidate_background`), never the raw CV. See
  `docs/capstone/p10/p10b_wave4_prepare_practice_integration.md`.

- **Company Intelligence (Capstone P10B Wave 5).** The candidate-facing company-research surface is a
  thin directable layer over the EXISTING Phase 7F engine (`src/copilot/research/*`) — do NOT build a
  second research architecture and do NOT weaken its SSRF/robots/size/injection guards.
  `src/application/company_intelligence_service.py` orchestrates the governed `ExternalResearchService`
  and returns a candidate report with an EXPLICIT claim taxonomy the UI must never blur: **FACT**
  (official/company source), **REVIEW** (third-party opinion — NOT integrated; link-only, never
  scraped/copied), **MODEL_INFERENCE** (deterministic, source-derived suggestion, never a verified
  fact — this layer makes NO model call). Endpoint `POST /api/v1/research/company`
  (`src/api/routes/company.py`) is gated by capability `current_market_research` + pause
  `current_market` + cost `cost_research_user`, and resolves any selected JD owner-scoped via
  `resolve_document_text` (foreign/missing → no text; JD is DATA, never a prompt). **Identity is
  disambiguated deterministically:** research runs only against an explicit, validated website — never
  guess a domain from a name. Geography comes only from explicit country/location, never inferred from
  language; company names are never translated. No migration (read-mostly; ephemeral 7F file cache
  only — durable per-role persistence is Wave 6's Opportunity model). Glassdoor/Kununu/Google are
  NOT_INTEGRATED (ToS/licensing) — link out, never scrape. Deterministic gate
  `scripts/eval_company_intelligence.py`; UI at `frontend/app/company/*` + `components/company/*` (no
  emoji, no em dash). See `docs/capstone/p10/p10b_wave5_company_intelligence.md`.

- **Opportunity vs Workspace (Capstone P10B Wave 6) - durable product rule.** An **Opportunity** is a
  candidate's PRIVATE preparation context for ONE job (role + company + optional JD); it is the
  organising home for Company Intelligence, Prepare, Practice, reports and progress for that job. A
  **Workspace** is for COLLABORATION/sharing with other people (VIEW-only grants). These are distinct -
  never merge them; an Opportunity never auto-creates a Workspace and is never required. ORM
  `Opportunity` in `src/persistence.py` (owner-scoped, FK `users.id` CASCADE; optional
  `job_description_document_id` FK SET NULL); `interviews`/`interview_sessions` carry a NULLABLE
  `opportunity_id` (SET NULL) - deleting an Opportunity never destroys history, and legacy/standalone
  rows stay valid with NULL. Migration `0014_opportunities` (additive; single head; the two
  `opportunity_id` FKs are added only on DBs that support ALTER-ADD-FK, plain column+index on SQLite).
  `src/opportunity_repository.py` + `src/application/opportunity_service.py` +
  `src/api/routes/opportunity.py` (`/api/v1/opportunities`, BASIC, owner-scoped → 404 on foreign,
  metadata-only audit events). Opportunity is CONTEXT that PRE-POPULATES Company Intelligence / Prepare
  / Practice (via `?opportunity=<id>`), never a replacement: reuse the Wave 5 research engine and the
  interview flow. **Precedence = explicit session choice > Opportunity context > account preference >
  default** (Opportunity context is an initial value, never a silent override; it carries no
  conversation_language/career_geography - those stay account/session-owned). No CV/evidence text or
  research content is copied into an Opportunity; evidence stays governed (approved-only). Deterministic
  gate `scripts/eval_opportunity_journey.py`; UI `frontend/app/opportunities/*` +
  `components/opportunities/*` (no emoji, no em dash). Opportunity SHARING is deferred (a future seam
  over the existing VIEW-only share model - no new authorization). See
  `docs/capstone/p10/p10b_wave6_opportunity_model.md`.

- **Public marketing claim discipline (Capstone P10B Wave 7) - durable rules.** Market only what
  exists: every public claim must be traceable to implemented behaviour, deterministic evidence,
  documented provider status, or an explicit limitation (status ladder CONFIGURED / IMPLEMENTED /
  DETERMINISTICALLY TESTED / LIVE VALIDATED / HUMAN VALIDATED - never collapsed). The public story is
  **Opportunity-centred** (Opportunity = private job-preparation context; Workspace = collaboration -
  never conflate on marketing). Provider discipline: Glassdoor / Kununu / Google / LinkedIn are **NOT
  INTEGRATED** and must never be claimed as sources (link-out only); no "real-time company
  intelligence" or unrestricted-web-browsing claims. Pricing reflects authoritative entitlements
  (`lib/pricing.ts`): Basic EUR 0, Premium EUR 19.99 **preview** - `BILLING_ENABLED=false`, never a
  purchase path; do not invent prices or billing. **Never** fabricate testimonials, customer counts,
  ratings, logos or reviews, and never use unsupported absolutes ("100%", "bias-free", "GDPR
  certified/compliant", outcome guarantees). Canonical Ask4Mo logo only (no invented mark, **no emoji
  as iconography** - use the inline-SVG `MarketingIcon` set). No em dash in customer-facing copy
  (guarded). Interface language never determines career geography / conversation / dictation / session
  language. Public routes must never expose candidate-private content; new authenticated routes must be
  added to `app/robots.ts` disallow. Deterministic gate `scripts/eval_marketing_product_trust.py`. See
  `docs/capstone/p10/p10b_wave7_marketing_product_trust_pricing.md`.

- **Admin permissions, audit and Command Center (P10B-W10.1) - durable rules.** Admin authorization is
  `require_permission("platform.<domain>.<action>")` (`src/api/dependencies.py`) over the code-defined registry
  and role presets in `src/application/admin_permissions.py` (43 permissions, six presets; default deny; no
  custom roles, no role tables, no break-glass, no content-inspection permission; role strings live in
  `users.platform_role`, a plain column). Never add an admin route without a permission (CI invariant:
  `src/api/admin_route_invariant.py`, `scripts/eval_admin_foundation.py`). Privileged changes are audited in
  the SAME transaction as the mutation (`audit=` on `AccountRepository.set_*`; an audit failure rolls the
  change back) using canonical names in `src/application/admin_audit.py`; a failed denial audit never grants
  access. `/admin/providers` returns only the allowlist schema in `src/api/schemas/admin.py` (no secrets, no
  open dicts, health "not tested"). The frontend gets resolved permissions as `account.admin_permissions` and
  only reflects them (no role mapping, no browser storage). The admin UI is English-only. **W10.2:** account deactivation revokes all live sessions in the same transaction (`AdminUserRepository`), and `SessionRepository.resolve` rejects any non-active account at request time (SEC-W10-01); reactivation never revives sessions; the last active `platform_admin` and self-deactivation are protected server-side; roles are the code-defined presets only; admin responses are allowlist schemas with no candidate content; new admin links use `VerifiedLink`; gate `scripts/eval_admin_access.py`. **W10.3 support:** `support_tickets` / `support_messages` (customer-visible) / `support_internal_notes` (Admin-only, a separate table with NO candidate code path; never in a candidate response, export or audit payload); candidate routes `/support/tickets*` are owner-scoped and strict (`extra=forbid`), admin routes `/admin/support/*` use `platform.support.read|reply|manage|note`; status lifecycle and priority are server-validated and candidate-immutable; no SLA, email, attachment or live provider; messages are plain text; tickets/messages/notes are deleted with the account and the visible thread (not notes) is in the self-service export; gate `scripts/eval_admin_support.py`. **W10.4 plans:** product access is decided ONLY by `src/entitlements.py` (`EntitlementService`, code-defined `REGISTRY`, `require_entitlement`), never by a tier comparison; authorization (ownership, `require_permission`), technical capability (`/capabilities`, flags) and entitlement stay separate, and billing (W10.5) is not implemented. Plans are versioned (`plan_versions` draft, active, retired; active/retired are immutable; activating never moves subscribers), subscriptions pin one subject (user XOR workspace) to one version with history, and the legacy `tier` column is a compatibility value changed only by the subscription domain (`PlanRepository.assign`). Existing real plans only (basic, Premium preview); no invented price, quota or plan family; no fallback to Premium (Basic is the explicit least-privilege fallback). Gate `scripts/eval_admin_entitlements.py`. **W10.6 integrations:** the integration set is code-defined (`src/integrations.py`; no custom integration, no admin-entered URL); credentials go through `SecretStore` (`src/secret_store.py`): the environment adapter is externally managed and read-only, `get_for_runtime` is the only value read path and is confined to the store and adapter probes (never an admin route, schema or audit payload), and no secret value, prefix, suffix or mask is ever returned or persisted. **W12.4B secure provider administration:** an opt-in writable `EncryptedDatabaseSecretStore` (`SECRET_STORE_BACKEND=encrypted_database`, migration `0026_managed_secrets`) keeps Admin-managed credentials ONLY as AES-256-GCM ciphertext (`cryptography` AESGCM, slot bound as associated data); the 32-byte base64 `SECRET_STORE_MASTER_KEY` is deployment-managed, never in the database and never an Admin control, and production/staging refuse to start without a valid key when the backend is selected. Precedence is managed, then environment fallback, then not configured; environment secrets are never copied in. Configure, replace and remove need `platform.integrations.secret.rotate` AND a fresh password step-up, audit in the same transaction, and `expected_revision`; no route reveals, masks, previews or exports a value, and `platform_admin` is the only preset holding the permission (still 43 permissions). Runtime consumers read credentials through `src.core.secrets.read_setting` / `read_secret` (never `os.environ` directly); some (OpenRouter, embeddings, Brevo, Redis, Langfuse) pick up a rotation only after an API and worker restart. **W12.4C email and identity:** identity mail goes through `EmailService` (`src/mail/service.py`), which returns a bounded `SendResult` and records a minimal `EmailAttempt` (migration `0027_email_attempts`: no recipient, token, link or content). `provider_accepted` is NOT delivery and no `delivered`/`bounced` state exists (no webhook). The Brevo adapter never retries (a read timeout is `delivery_unknown`), the console sender is development/test only (hosted environments use `NotConfiguredEmailSender`), links are built only from the configured https `APP_BASE_URL`, link tokens are consumed with one atomic conditional UPDATE (codes `token_invalid|used|expired`), a password reset is issued only to an active account with a password credential and revokes every session, and an OIDC link onto an unverified password account destroys that unproven credential first. Google sign-in uses PKCE S256 (verifier in an HttpOnly cookie, all transaction cookies spent on every callback), validates the returned ID token (RS256 only, iss, aud, azp, exp, iat, sub, at_hash; TLS authenticates the direct token response), requires the UserInfo `sub` to equal the ID-token `sub`, requires real-boolean `email_verified`, and in hosted environments builds the callback only from the configured `OIDC_REDIRECT_URI`. Templates are plain text in the eight locales with the protected slogan. Admin: `GET /admin/integrations/email_brevo/delivery`, a read-only Brevo probe and a bounded test email to the acting administrator's own address only. **W12.4D-B Stripe Managed Payments foundation:** `BILLING_PROVIDER` is a code-defined allow-list (`mock`, `stripe_managed_payments`; anything else fails closed). `StripeManagedPaymentsProvider` (`src/billing/stripe_provider.py`) is a FOUNDATION: it reports truthful capabilities (no checkout, refund, payment methods or tax), `refund()` raises `ProviderRejected`, and nothing contacts Stripe. Credentials are four separate W12.4B slots (sandbox and live key and webhook secret, never interchangeable); live billing is the code constant `policy.LIVE_BILLING_ENABLED = False`; the Stripe client is built per instance (pinned API version `2026-09-30.endive`, no retries, never the SDK's global key); readiness has no healthy or merchant-of-record-approved state; Stripe events are refused until W12.4D-D (`policy.PROVIDERS` stays `(mock,)`); any future Checkout Session must pass `require_managed_payments` (`managed_payments.enabled = true`) so Ask4Mo is never an ordinary merchant. Billing is never an entitlement source. **W12.4D-C checkout and lifecycle foundation:** `CheckoutService` (`src/billing/checkout.py`) + candidate routes `/billing/checkout/availability|status`, `/billing/checkout-sessions`, `/billing/checkout-returns` (the ONLY four candidate billing routes; there is no payment-success endpoint) over `BillingProvider.create_checkout_session`. The client sends a plan code only; price, currency, interval, provider, environment and return URLs are server decisions (active immutable terms + an active `billing_provider_prices` mapping that equals them; return URLs from the trusted https origin, never Host). Attempts are durable and idempotent (`billing_checkout_sessions`, migration `0028_checkout_sessions`: unique `(user_id, idempotency_key)`, one open attempt per user and plan version, stable provider idempotency key per record). A browser return only sets `browser_returned_at`; subscription and payment states beyond `confirmation_pending` need verified provider evidence (`lifecycle.require_evidence`, W12.4D-D) and no paid checkout status exists; no entitlement is ever changed. Real Stripe checkout is impossible by configuration (`policy.EXTERNAL_CHECKOUT_AUTHORIZED = False`, Stripe capabilities `checkout: false`, mock refuses), `LIVE_BILLING_ENABLED` stays False, and Managed Payments eligibility and sandbox access remain unverified. **W12.4D-D signed webhooks, reconciliation and entitlement bridge:** `POST /billing/webhooks/stripe` (`src/api/routes/billing_webhooks.py`, `src/billing/webhook.py`) is the only unauthenticated billing route; it is authenticated by the Stripe signature over the raw body (`stripe_events.verify_signature`: tolerance both directions, signing secret of the configured environment only via the SecretStore), validates `livemode` against the configured environment, durably stores an allow-listed normalised event (`billing_provider_events`, unique per provider, environment and event id; the stored row is the outbox) BEFORE acknowledging, and changes nothing else. It is non-operational while `policy.STRIPE_WEBHOOK_AUTHORIZED = False` (code constant). Processing (`reconcile.py`, W10.9 job `billing_process_provider_event` and a bounded sweep job) claims events under a lease and reconciles the provider's AUTHORITATIVE state from a `ProviderStateReader` (runtime default `NullStateReader`; `StripeStateReader` exists but is never constructed) into `billing_provider_links`: ownership only through the trusted W12.4D-C checkout record (never email), price and terms must match, stale snapshots and terminal states are never overwritten, refund and dispute facts are monotonic. `entitlement_bridge.py` is the ONLY writer of `subscriptions.source = 'provider'`; it acts only under an explicit `EntitlementPolicy`, and the runtime policy is UNAPPROVED (`runtime_policy()`; undecided rules are `None` = hold), so no paid entitlement is granted or revoked at runtime; admin and migration assignments are never overridden or revoked. Provider-initiated refunds, cancellations and disputes are recorded as facts without two-person approval. Migration `0029_provider_webhooks`. **W12.4D-E billing operations:** candidate `GET /billing/summary` (own verified local state, eleven user-facing states from `lifecycle.overview_state`; payment, subscription and access stay separate; Link guidance with NO invented URL, no invoices) and Admin `/admin/billing/operations/*` (`src/billing/operations.py`, `admin_billing_ops.py`): reads need `platform.billing.read`, recovery (retry, requeue of an EXPIRED lease, reconcile one link) needs `platform.jobs.manage`, takes a reason and an Idempotency-Key, targets only our record ids, re-drives the existing verified pipeline, is recorded in `billing_recovery_actions` and audited in the same transaction, and is REFUSED (`reader_unavailable`) while the runtime reader is Null. No revenue is reported. `billing/scheduler.py` is a one-shot idempotent tick, disabled by `RECONCILE_SCHEDULER_ENABLED = False`. Migration `0030_billing_recovery` (fail-closed downgrade). All billing gates remain off. **W12.4D-F1R account closure and recovery authorization:** `AccountDeletionService.delete_account` refuses (`SubscriptionResolutionRequired`) while a provider-managed subscription is unresolved (a non-terminal link, an unknown state, or a checkout that can still be completed) unless `preserve_billing_reference` is set; `POST /auth/account/delete` records ONE idempotent `billing_account_closures` case and answers `409 subscription_resolution_required` (the account stays; no provider call is made; provider cancellation is unverified and never claimed). The privacy-request deletion calls `ClosureService.begin_retained_erasure`: personal and content data are erased and only an anonymised shell, links and linked checkouts are retained until verified terminal state purges them (no retention period invented). Billing recovery needs `platform.billing.recover` (registry 44; `billing_admin` and `platform_admin` only) plus a fresh password step-up through the billing-scoped step-up routes; `platform.jobs.manage` confers nothing here and the provider billing job types are not manually retryable through the generic job API. Migration `0031_account_closure` (fail-closed downgrade). **W12.4D-F2-A provider integration readiness:** `StripeStateReader` (`src/billing/provider_state.py`) is a typed, READ-ONLY normaliser (every SDK call passes `_invoke`, which only resolves `READ_ONLY_OPERATIONS` retrieve/list; unknown status, malformed timestamp/amount/currency, missing or live `livemode` are `ProviderStateInvalid`; auth/permission/API-version/account/feature refusals are the non-retryable `ProviderStateConfiguration`, parked as `needs_review`). A real reader exists only through `build_authorized_reader`, which refuses unless the code constant `policy.PROVIDER_READS_AUTHORIZED` is true (False) and the environment is sandbox; `build_runtime_reader()` always returns the Null reader and no application code constructs a real one (test-enforced). Admin readiness reports twelve separate `provider_read_stages`; none implies connection or health. The checkout redirect allow-list stays the single exact host `checkout.stripe.com` (default port only). Owner checklist for the sandbox wave: `docs/capstone/billing/W12_04D_F2_A_STRIPE_INTEGRATION_READINESS.md`. No migration, no Stripe call. **W12.4D-F2-B1R webhook financial safety:** a validly signed FINANCIAL event (one of the 14 supported types) under an unsupported or missing API version is stored as `needs_review` / `unsupported_api_version` with a reference-only payload (`stripe_events.reference_only`: kind plus the opaque, prefix-checked object id; no other field is read), counted in Admin `awaiting_operator` and `held_unsupported_api_version`, never claimed by the worker or sweep, and recoverable only through `platform.billing.recover` plus step-up, which reconciles from AUTHORITATIVE provider reads (`_reconcile_incompatible`) and takes no refund or dispute facts from the payload. Irrelevant event types stay `ignored` (type is classified before version); a malformed subscription event is `needs_review`, never ignored. Doc: `docs/capstone/billing/W12_04D_F2_B1R_WEBHOOK_FINANCIAL_EVENT_SAFETY.md`. Status keeps configuration, runtime and health separate; only an explicit manual test (bounded, adapter-defined destination, no polling) can show healthy; Google OIDC, Redis distributed limiting and email stay qualified as not validated / not live. Validation errors never echo submitted input. Gate `scripts/eval_admin_integrations.py`. **W10.9 jobs:** background work is a DB-backed queue (`jobs`, `job_workers`) run by a SEPARATE worker (`python -m src.jobs.worker`; the API never executes jobs, no external broker, no Celery/Redis/APScheduler). Job types are code-defined (`src/jobs/registry.py`): no arbitrary handler name or shell job; every payload is schema-validated, never holds a credential and is never shown to Admin (typed safe summary only). All creation goes through `JobService.enqueue`; claiming is PostgreSQL `FOR UPDATE SKIP LOCKED` / SQLite guarded conditional UPDATE, handlers run outside the claim transaction under a lease, and every post-claim write is guarded by lease owner + attempt, so handlers MUST be idempotent. Failures store a fixed category and message, never exception text. Running jobs are not cancellable; a manual retry requeues the same job. Gate `scripts/eval_admin_jobs.py`. **W10.8 governed knowledge:** Admin-managed knowledge lives in `src/knowledge_admin/` (tables `knowledge_sources`, `knowledge_source_versions`, `knowledge_index_records`) and is written ONLY to the separate `governed_knowledge` collection, never the legacy corpus. UNAPPROVED KNOWLEDGE NEVER ENTERS CANDIDATE RETRIEVAL: nothing is embedded before human approval (scan -> parse -> review -> approve -> index job -> explicit activate), and `GovernedKnowledgeRetriever` trusts only the SQL active set (no BM25 channel, no reliance on vector deletion). Versions are immutable (one active per source, enforced by a partial unique index); authority stays 1 official / 2 framework / 3 industry; KB languages stay the 7 (Russian is NOT one); a licence class of `unclear`/`restricted` or missing provenance or a non-passed malware scan blocks approval; no URL is ever fetched; parse/index/remove are W10.9 jobs with id-only payloads and deterministic chunk ids (replay-safe). Gate `scripts/eval_admin_knowledge.py`. **W10.10 privacy and legal:** privacy requests are durable (`privacy_requests`, SEC-W10-04 closed); an Admin deletion runs the SAME `AccountDeletionService` as a W10.9 job and completes only when every checkpoint run is purged (there is NO second deletion engine and NO admin export/download of candidate data; Privacy Admin never sees candidate content). New preparation runs are registered in the `preparation_runs` ownership index (ids/state only, no chat content, no FK to users) BEFORE the checkpoint is created; per-user discovery is one indexed query and nothing may ever scan the checkpoint store; historical runs are indexed only from verified references. Legal documents (terms, privacy, ai_transparency) have versions: a published version is immutable, exactly one is current, acceptance records (user, version, timestamp, code-defined source) carry NO IP/device and are NEVER back-filled; legal acceptance is not consent and re-acceptance is not enforced. Never write a GDPR-compliance or legal-compliance claim or a statutory retention period. Gate `scripts/eval_admin_privacy_legal.py`. **W10.5 billing is MOCK ONLY:** `BillingService -> BillingProvider -> MockBillingAdapter` (`src/billing/`); there is NO live provider, checkout, payment method, card data, tax engine, public webhook, coupon engine or revenue/MRR reporting, and the mock adapter is disabled by default (`BILLING_PROVIDER=mock`) and fails closed in any non-dev/test environment. BILLING STATE IS NEVER ENTITLEMENT STATE: billing code must not read or write `subscriptions`, entitlements or the tier (price changes, failed payments, refunds and provider cancellation never change access). Money is integer minor units + currency; commercial terms are versioned immutable rows attached to `plan_versions` (no row means unconfigured, never free; NO price is seeded). Price changes and refunds need a DIFFERENT active administrator with `platform.plans.price.change` / `platform.billing.refund` (no self-approval, no override); refunds and events are idempotent W10.9 jobs; everything is labelled MOCK BILLING - NOT LIVE BILLING. Gate `scripts/eval_admin_billing.py`. **W10.7 AI and model administration:** model configuration is governed through `src/ai_admin/` over the code-defined registry (`src/llm/models.py`) and operation policy (`src/llm/policy.py`) via ONE seam, `src/llm/governed.py`. A configuration may change ONLY which approved catalogue entry (`luna`/`terra`/`sol`, chosen by id, never a provider slug) serves Fast/Balanced/Advanced and bounded numeric tunables (max output tokens, timeout, retries) of model-backed operations; capability, minimum tier, fallback floor, structured-output/tool flags, deterministic and realtime operations, the three specialists, the Interview session profile, prompts and secrets stay code-defined. AN AI CONFIGURATION IS NEVER ACTIVE WITHOUT A PASSED, HASH-BOUND EVALUATION AND A DISTINCT SECOND APPROVER (not the requester, not the author): there is no force or bypass parameter, `activate` re-derives both from stored facts, the activation environment is SERVER-authoritative (API_ENV: development/dev/local/test/testing, staging, production; an unknown value disables activation; no request field chooses it) and production requires a prior STAGING activation of the same hash (development never counts), activations are append-only, and rollback or revert-to-code needs no new approval. Evaluations are deterministic contract checks run as a W10.9 job (`ai_evaluate_config`), make 0 provider calls and are NOT live-quality evidence. The resolver (`src/ai_admin/resolver.py`) fails closed to the code defaults on any integrity problem and, with nothing active, behaviour is identical to pre-W10.7 (environment override, then code default; an active configuration wins over the environment override). Interview Practice stays one SESSION-selected profile for all its operations, resolved at execution through the governed profile mapping (`interview_service._governed`); `ModelSettings.model` is only a compatibility marker, candidates never send a slug, and only operations with a real runtime consumer (orchestration, structured generation, evaluation) have tunables (`src/llm/runtime.py`), each either `null` = INHERIT the consumer's real default or an explicit number forced into every consumer (no equality-with-a-baseline shortcut; inherit and a number hash differently). Cross-process convergence is bounded by the 5 s cache TTL, never instant. Gate `scripts/eval_admin_ai_models.py`. **W10.11 durable pause and feature flags (closes SEC-W10-05):** operator pause state is the DATABASE (`platform_pause_states`, `src/application/pause.py`), never process memory: every admission reads it (no cache), an unreadable store REFUSES the request (`platform_state_unavailable`, never "assume running"), the gate runs BEFORE any service or provider is built, and the candidate sees only the fixed `platform_paused` code (localized x8; the internal reason never leaves Admin). Pause changes need `platform.config.manage` (W10.0 owner: operations administrator), carry an expected revision and a required reason, and audit in the same transaction; the environment is the SERVER's (`API_ENV`), never a request field. Pause refuses new candidate activity of a fixed capability list only: Admin recovery, privacy/account controls and the W10.9 worker are never paused. Feature flags are CODE-DEFINED (`src/platform_config/flags.py`: only `external_research` and `company_web_research`), with durable environment-scoped overrides (inherit / enabled / disabled, revision-protected); a flag can only RESTRICT availability (`available = authorized AND flag`) and never grants permission, entitlement, billing or AI changes; there is NO generic key/value, JSON or environment editor and no secret/security setting is mutable. Gate `scripts/eval_admin_platform_config.py`. **W10.12 reporting:** Admin reports (`src/reporting/`, `/admin/reports/*`, GET only) are AGGREGATES ONLY and READ-ONLY: no candidate content, no identifiers, no per-user or raw-event route, no provider or pricing call, no job. Candidate cohorts below `REPORTING_MIN_COHORT = 5` (an engineering control, not anonymisation) are suppressed (value null, never the count or "<5"); rates also need a non-small numerator and complement; partitions get secondary suppression. A metric without evidence is `unavailable` or `not_captured`, never zero; unknown tokens and cost are NULL (cost is integer micro-USD, `reported`/`calculated`/`unavailable`), shown as "known cost, partial coverage". AI usage is captured at ONE canonical boundary per workflow (Agent: the run's cumulative aggregate upserted once; Practice: each UsageRecord once) so nothing is double counted; `ai_usage_facts` and `operational_metric_events` (bounded, no identity/path/query/body) start from W10.12 with no back-fill. Product activation = first Opportunity, Prepare run or Practice session; returning = activity on two distinct UTC dates. Commercial reporting needs `platform.reports.commercial.read`, access-plan assignments are not revenue, billing is MOCK BILLING - NOT LIVE REVENUE, currencies are never combined and churn is not fabricated. Gate `scripts/eval_admin_reporting.py`. **W10.13 security, audit and incidents:** security administration is metadata only - no break-glass, no impersonation, no candidate-content browsing. A security event is a typed projection of `audit_events` (no second log; no email, IP or user agent). `audit_events` and `incident_events` are append-only at the database: triggers reject DELETE and any UPDATE except `actor_user_id` value to NULL (which account deletion relies on); they are installed by migration `0025` and by `create_all`, and the PostgreSQL DDL is only rendered and unit-checked, never claimed live-executed. A platform role is NEVER changed directly: `POST /admin/role-changes` creates a request, a DIFFERENT active Admin who currently holds `platform.users.role.assign` approves, neither may be the target, both need a fresh password step-up (`POST /admin/step-up`, 5 minutes, bound to the server-side session, NOT MFA; OIDC-only accounts fail closed), a stale target role is never applied, approval + role update + audit are one transaction, and no route may call `set_platform_role`. Incident and alert free text is never copied into audit context; alerts are in-app only with code-defined categories and dedupe keys. Gate `scripts/eval_admin_security.py`. **W12.1 owner / orchestrator (AD-W12-01, supersedes the W10.14 preset for the CURRENT runtime):** `platform_admin` is the platform owner / orchestrator holding ALL 43 canonical control-plane permissions (`ROLE_PLATFORM_ADMIN: PERMISSION_SET`, a code-defined preset; no migration). 43 / 43 is NOT a private-candidate-content superuser: there is still no permission that reads a CV, document, answer, Mo conversation, memory or evidence, no break-glass, no impersonation or view-as, and every privileged route stays `require_permission`-gated (never a role-name check). Step-up, two-person approval (requester != approver), expected revisions and audit are NOT bypassed by the owner, and authorization is not capability (the environment SecretStore stays read-only, billing stays MOCK, unapproved knowledge never reaches candidate retrieval). Specialist presets stay least-privilege delegated roles; never add a 44th permission casually. **W10.14 historical record (ROLE-W10-01, kept true):** W10.14 and RC-P10-003 qualified `platform_admin` at 28 of 43 with the 15 specialist permissions (billing, jobs, knowledge manage/approve, privacy execute, legal, config, security/incident mutation, audit export, price change, commercial reports, secret rotation) held only by domain roles; that is evidence of that point in time and is not rewritten. Every evaluator that builds the app or touches a database MUST import `tests.conftest` first (temp DB, no `.env`, non-temp engines fail fast). Gate `scripts/eval_admin_qualification.py` and `tests/test_admin_qualification_w10_14.py` (route x persona over real HTTP, 43 x 7 matrix, sentinels). **P10B-W11:** `docs/capstone/p10/P10B_RELEASE_ACCEPTANCE_MATRIX.md` is the INTEGRATED release gate (R-01..R-52 from W9.13, R-53+ Admin and cross-plane); `tests/test_integrated_w11.py` proves candidate+Admin seams together; W11 qualified the tree but does NOT create RC-P10-003 (a separate owner-reviewed step); evaluators `scripts/eval_release_matrix.py` and `scripts/eval_w11_integrated.py` are CI gates. See
  `docs/capstone/admin/W10_1_ADMIN_FOUNDATION_COMMAND_CENTER.md`.

## Roadmap

The single canonical forward-looking roadmap is `docs/capstone/capstone_phase_plan.md` (status section at the top). Admin/operations phase P10B-W10 is planned in `docs/capstone/admin/ADMIN_PLATFORM_MASTER_PLAN.md`. Core admin rule: platform admin is not an unrestricted private-candidate-data superuser.

## Git rules

- Remote: `origin` (configured locally; the GitHub repo rename to Intelligent-Interview-Coach is a follow-up). Turing
  submissions are pushed to the `TuringCollegeSubmissions/*` remote.
- Work on a feature branch and integrate through a Pull Request (see the **Completed Wave Integration
  Rule** below). Never force-push `main`; never bypass required CI without explicit owner instruction.
- End commit messages with `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.

### Completed Wave Integration Rule (permanent, owner-established)

A completed implementation wave must not remain local-only. Every approved Ask4Mo implementation wave must:

1. complete its acceptance gates;
2. run the required deterministic tests/evaluators;
3. commit all intended changes;
4. ensure no secrets, local databases, database backups, logs or private data are included;
5. push the implementation branch to GitHub (never `--force` on `main`);
6. open or update a Pull Request into `main`;
7. allow required CI to complete;
8. fix CI failures, or explicitly block and report them (including GitHub Actions billing/spending-limit
   failures: never claim CI passed when jobs did not execute);
9. merge only after required checks pass, using the repository's normal merge strategy;
10. `git fetch origin --prune`, switch to `main` and fast-forward it from `origin/main`
    (`git pull --ff-only origin main`); if it cannot fast-forward, inspect and report - never reset
    destructively;
11. verify `local main == origin/main` with a clean working tree (and that the Alembic head is as expected);
12. report the GitHub PR and the final SHA.

A wave must NOT be reported as "fully integrated" if it exists only as a local commit. Deliberately cumulative
local development waves may be synchronized through one cumulative PR before continuing, but that is the
exception; afterwards return to per-wave integration. Workflow:
implement -> test -> commit -> push -> PR -> CI -> merge -> sync local main -> verify SHA equality.
- Never commit `.env`, `.streamlit/secrets.toml`, virtual environments, caches,
  generated evaluation runs, or `node_modules`.

## Explainability

The owner must be able to explain every line in a review: keep code simple,
comment the *why* where non-obvious, and keep `docs/` current after each phase
(files changed, functionality, commands, test results, risks, review concepts).
