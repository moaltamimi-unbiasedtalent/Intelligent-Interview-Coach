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
  `SearchCareerKnowledge`, a thin adapter over the grounded pipeline
  (`CareerApplicationService.chat`): the **agent decides *whether*** to retrieve;
  the **deterministic Sprint 3 router still decides *which*** lanes/sources (the
  model never sees low-level stores — `search_vector_store`/`search_bm25`/
  repositories are never registered). Retrieval is de-duplicated within a run,
  retrieved content stays **untrusted DATA**, citations come only from retrieved
  evidence, and the deterministic `/career/chat` endpoint is unchanged. A
  deterministic orchestration regression lives in
  `evaluations/agent/tool_selection_cases.json` + `src/agent/eval.py` (33 cases,
  incl. retrieval recall / unnecessary-retrieval / citation-validity metrics; not a
  live-LLM benchmark). `src/agent` imports no Streamlit/UI and makes no provider
  call on import; memory Phase 7, HITL Phase 8.
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
- Current measured suite on this branch: **1371 passed, 2 skipped** (the skips are
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
