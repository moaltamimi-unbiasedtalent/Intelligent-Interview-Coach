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
  usage is captured with honest Complete/Partial coverage as of P1 — see the Agent
  cost/performance bullet below). Production auth still transitional.
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
- **Retrieval.** Structured stores (SQLite: roles, competency, compensation,
  labour-market, credentials) + a Chroma vector store with a local-hash embedder
  fallback; a deterministic router picks lanes; hybrid (vector + BM25) fusion.
- **Persistence & auth.** SQLAlchemy ORM over SQLite (dev/tests) or PostgreSQL
  (production, schema owned by Alembic — single head `0007_identity_platform`; see
  `docs/operations_deployment.md`); interview history is per-user with strict
  isolation. Account authentication/authorization lives in `src/authsec/` (password
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
- Tests must not mutate committed artifacts (write to `tmp_path`).
- `ruff check .` (conservative `F`/`E9` rules) must pass.
- Test totals: **always re-measure with `pytest -q`** rather than trusting a number
  copied across docs (historical docs cite different totals from their own point in
  time — that is expected, not a defect). The measured backend suite after Capstone
  P6.5 is **2352 passed, 3 skipped** (P4 2277; P5 2303; P6 2334; P6.5 adds workspaces,
  platform-admin + per-type sharing security suites); the skips are RAGAS installed/absent
  guards; the frontend unit suite is **222 passed** (`cd frontend && npm test`; P6.5 adds
  `/workspaces` + `/admin` pages, feedback category, role-aware Admin nav, i18n key-parity
  across 7 locales) and the Playwright e2e suite adds `workspaces.spec.ts` + `admin.spec.ts`
  (`npm run e2e`).

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
  Admin** (`src/api/routes/admin.py`, router-level `require_platform_admin`) is an OPERATIONS
  surface, **not a data superuser**: account/workspace/entitlement/privacy/provider/audit
  **metadata only** (no CV/answers/Memory/documents), audited privileged changes (role/tier/
  status) with self-lockout guards, no "view as user", no private-data search, owner-scoped
  repos stay owner-scoped. Teams access is a **separate dimension from BASIC/PREMIUM**; no
  billing, no enterprise SSO. Admin reuses the P6 reviewer APIs (no second backend;
  no-auto-promotion preserved). Candidate `FeedbackControl` gains an optional bounded category
  (P6 taxonomy), i18n across 7 locales. Routes: `/api/v1/workspaces/*`, `/api/v1/shares/*`,
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

- **Internationalization coding standard (Capstone P3.5+).** New candidate-facing,
  user-visible strings MUST use the i18n system: add a key to the English source
  catalogue (`frontend/lib/i18n/messages/en.ts`) and every locale catalogue (de/fr/es/
  it/pt/nl), and render via `useT()` / `translate()`. Interface language, Mo conversation
  language and dictation locale are **independent** settings, and a language choice never
  changes labour-market geography. Do not hard-code new English strings in candidate UI;
  reviewer/diagnostic-only text is exempt. See `docs/capstone/p3_5_i18n_l10n.md`.

## Git rules

- Remote: `origin` (configured locally; the GitHub repo rename to Intelligent-Interview-Coach is a follow-up). Turing
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
