# Ask4Mo Capstone — P0/E0 Current-State Baseline

Evidence-based inventory of the repository as it exists at the Capstone start. Verified from
code on branch `capstone/p0-e0-architecture-feasibility`, cut from `main` `4f273dd`. This is the
source of truth where code and older docs disagree.

## Repository facts
- **main SHA:** `4f273dd9c190bf016d70d7c7a9fbaee4f411e9d5` (401 commits)
- **Historical tags (unchanged):** `sprint4-submission-ready` → `1b084cb`; `sprint4-pre-phase7-baseline` → `2385612`; `sprint-3-final` → `bb29d02`
- **Primary stack:** Next.js 15 (App Router, `frontend/`) + FastAPI (`src/api/`, `/api/v1`) over an application layer (`src/application/`) + a bounded LangGraph agent (`src/agent/`). Streamlit is legacy/dev only.
- **Migrations:** Alembic `0001`–`0006`, single head. Tables: users, interviews, questions, answers, reports (0001), preparation_memories (0002), interview_sessions (0003), +source_session_id (0004), memory pinning (0005), user_feedback (0006).
- **Frontend routes (13):** `/`, `/prepare`, `/practice`, `/progress`, `/history`, `/history/[id]`, `/sources`, `/settings`, `/help`, `/review`, `/review/agent`, `/review/rag`, `/review/evaluation`. No public/marketing, auth, admin, documents, or workspace routes.

## Capability classification

| Capability | Status | Evidence |
|---|---|---|
| Next.js frontend (primary) | DELIVERED | `frontend/app/*`, 176 unit tests, 60 e2e |
| FastAPI backend `/api/v1` | DELIVERED | `src/api/*`, OpenAPI contract test |
| LangGraph agent (ReAct/goal-based) | DELIVERED | `src/agent/graph.py`, `nodes.py`, `state.py` |
| 6 Career tools + 2 HITL actions | DELIVERED | `src/agent/tools.py` (Analyze JD/Gaps, Build Plan, Generate Questions, SearchCareerKnowledge, ResearchCurrentMarket; Propose Memory, Request Handoff) |
| Governed Agentic RAG | DELIVERED | `src/copilot/*`, deterministic router; agent decides *whether*, router decides *which* |
| Durable Interview Practice | DELIVERED | `DurableInterviewSessionStore`, migrations 0003/0004 |
| Deep Dive evaluation | DELIVERED | `frontend/components/interview/DeepDivePanel.tsx` |
| Approved long-term memory | DELIVERED | `preparation_memories`, `src/application/memory_service.py` |
| Progress (practice metrics) | DELIVERED | `PracticeProgress.tsx`, `GET /api/v1/progress` |
| History detail + report | DELIVERED | `HistoryDetailClient.tsx`, `/history/[id]` |
| Governed Sources (safe links) | DELIVERED | `SourcesClient.tsx`, https-guarded `source_url` |
| Review hub + Agent Inspector | DELIVERED | `/review`, `/review/agent`, owned-run only, no CoT |
| Knowledge & RAG diagnostics | DELIVERED (code); DATA env-dependent | `RagDiagnosticsClient.tsx`; artifacts present here, **gitignored** (empty on fresh clone) |
| Evaluation diagnostics | DELIVERED (code); DATA env-dependent | `EvaluationClient.tsx`; reads `evaluations/ragas/runs/*` (6 present here, gitignored) |
| Help Center + guided tutorial (C10) | DELIVERED | `HelpCenter.tsx`, `components/tutorial/*` |
| Current-market research (ResearchCurrentMarket) | DELIVERED | `src/copilot/research/*` (Adzuna + SSRF-safe fetch), OFF by default |
| Capability toggle (server-enforced) | DELIVERED | `state.py:disabled_tools`, `nodes.py`, `registry.py` |
| Feedback Intelligence (offline) | DELIVERED | `src/copilot/feedback_intelligence/*` |
| Observability (optional Langfuse) | DELIVERED (NoOp default) | `src/observability/*` |
| RAGAS/eval harness | DELIVERED (opt-in paid) | `evaluations/`, `scripts/eval_*` |
| Identity / accounts | PARTIAL | `src/auth.py` transitional `X-User-Subject` → `get_or_create_user`; **no** password/registration/verification/social |
| Recorded / realtime voice | PARTIAL / experimental | `components/live_interviewer`, `[speech]`/`[live]` optional extras, OFF by default |
| App-wide dictation | ABSENT | no dictation control across inputs |
| Multilingual speech (EN/DE) | ABSENT | not wired |
| Private documents / CV upload (B4) | ABSENT | no upload route/table |
| OCR (C2) | ABSENT | no OCR module/dep |
| Evidence/story bank (C7) | ABSENT | not in code |
| Additional specialists (C4) | ABSENT | single agent today |
| Teams/workspaces + sharing (C5) | ABSENT | no team tables |
| Platform roles / RBAC (D2) | ABSENT | only incidental `"basic":"easy"` difficulty string |
| Product entitlements Basic/Premium (D3/D4) | ABSENT | none |
| Admin Console (D1) | ABSENT | reviewer/diagnostics ≠ admin control plane |
| Report export / deletion (A9) | ABSENT | no export/delete endpoints |
| Active-session discovery (A2) | ABSENT | resume by URL only, no discovery list |
| Owned recent-run list (A6) | ABSENT | Inspector needs a run id; no list endpoint |
| Public marketing website (D7) | ABSENT | `/` is the product home, not a marketing site |
| Public hosting (C12) | ABSENT | single `Dockerfile`, no compose/hosting/staging |
| Privacy self-service (export/delete/consent) (D5/D6) | PARTIAL | memory delete + run-thread delete exist; no account/data export or policy surfaces |

## Documentation contradictions carried in (report-only; fix in a docs pass)
1. `post_release_product_surface_audit.md` says "no Agent runtime changed" — the capability toggle **does** change bound tool schemas/execution (`nodes.py`/`registry.py`).
2. Test totals disagree across docs (1928/155/51 vs 2137 vs 2145/166/57 vs local 176 fe).
3. `/evaluation/latest` reads `runs/*/results.json`, not the committed `deterministic_baseline.json` (schema mismatch).
4. Knowledge diagnostics "committed evidence artifacts" wording vs gitignored generated files.
5. `CLAUDE.md` opens with "Modular Streamlit monolith" though Next.js+FastAPI is primary.
6. Capstone reference docs cross-link a `Ask4Mo_Capstone_Delivery_v3/` folder; files are flattened into `docs/capstone/reference/`.

## Environment note
This working checkout is a full dev environment: the generated knowledge/eval artifacts
(`roles.db` 19M, chroma 81M, `build_metadata.json`, `retrieval_after.json`, 6 RAGAS runs) are
present, so Evaluation/Knowledge diagnostics populate here. A **fresh clone / demo machine will
show empty states** until provisioned (`scripts/check_demo_knowledge.py`). Do not fabricate data.
