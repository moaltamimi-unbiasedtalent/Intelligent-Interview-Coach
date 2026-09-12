# Sprint 4 Requirements Map — Intelligent Interview Coach

Maps the Sprint 4 course requirements to implementation. Status is final as of the end
of Sprint 4 (Phases 0–11); production follow-ups are called out as such and nothing is
overstated.

## Core requirements

| Requirement | Status (final, Sprint 4) | Notes |
|---|---|---|
| Clear agent purpose | ✅ implemented/documented | Career & Interview Preparation Agent — one primary agent from target role to practised interview. |
| 3+ tools (agent) | ✅ complete | The agent registers **5 real Career tools** (job analysis, gap analysis, preparation plan, question generation, and career-knowledge retrieval) as thin adapters over the existing capabilities. |
| LangGraph / LangChain | ✅ implemented | Single stateful bounded LangGraph agent; LangChain/OpenRouter model integration reused. |
| User interface | ✅ implemented | **Next.js is the primary frontend**; Streamlit is legacy/deprecated (retained until Phase 11). See `sprint4_interview_parity.md`. |
| Next.js core Interview Practice | ✅ complete | Full lifecycle in Next.js: question → typed answer → structured feedback → next → end early → complete → report; standalone setup + Agent Coach handoff (**Phase 10**). |
| Durable in-progress interview | ✅ complete | `interview_sessions` table + `DurableInterviewSessionStore`; refresh AND backend-restart resume; optimistic concurrency + operation lease; durable idempotent create; explicit `SessionData` codec (no pickle) (**Phase 10**). |
| Deep Dive (branching) | ✅ complete | HTTP surface (start/answer/next/return) + Next.js panel; main progress isolated; max depth enforced; archived branches persist through restart (**Phase 10**). |
| Streamlit migration | ◑ per parity matrix | Candidate-critical, non-experimental features MIGRATED; Record voice deferred, Live experimental, Prompt Lab developer-only — `sprint4_interview_parity.md`. |
| Evaluation | ✅ complete | Deterministic agent-orchestration regression (56 held-out cases, gated: `scripts/eval_agent.py`) + preserved RAGAS answer-quality harness (opt-in paid); security regression suite; browser E2E. See `sprint4_final_evaluation.md` (**Phase 11**). |
| Observability | ✅ complete | Agent Inspector shows safe observable actions (tools/retrieval/sources/memory/approvals/timing/safe failure categories); never chain-of-thought/prompts/checkpoint. Safe-by-default logging (**Phase 11**). |
| Runtime retention | ✅ complete (in-progress) | Stale durable interview-session cleanup (`scripts/cleanup_runtime_data.py`, dry-run default); completed History & approved memory are user-owned and not auto-expired (**Phase 11**). |
| Production authentication | 🔶 FOLLOW-UP / not production-ready | Transitional `X-User-Subject` boundary, **fail-closed in production**; isolation enforced by `user_id`. Real gateway/OIDC is a documented deployment requirement (`sprint4_security_privacy.md`). |
| Error handling | ✅ implemented | Safe errors + graph/tool failure handling (bounded loop, tool-failure recovery, safe messages). |
| Memory (short-term) | ✅ implemented | The bounded LangGraph execution/thread state (messages, tool results, run bookkeeping). In normal HITL operation this execution state is **persisted through the configured durable checkpoint saver** so a run resumes across HTTP requests/restarts — short-term *memory semantics*, durable *storage*. Distinct from long-term preparation memory. |
| Memory (long-term) | ✅ complete | Selective, user-scoped `preparation_memories` (durable DB) + `/api/v1/memory`; the agent loads a bounded, deterministic set per run. Explicit writes only — no automatic agent persistence (**Phase 7**). |
| Human-in-the-loop | ✅ complete | Real LangGraph `interrupt`/`Command(resume=...)` on a durable checkpoint: ambiguous-role confirmation, approval-gated memory writes, and practice-handoff approval; owner-scoped run/get/resume API (**Phase 8**), surfaced as approval cards in the Agent Coach (**Phase 9**). |
| Candidate agent interaction | ✅ complete | Agent Coach: `/prepare` talks to the LangGraph agent (behind `AGENT_COACH_ENABLED`), with same-thread multi-turn continuation (`POST /agent/runs/{id}/messages`), per-turn step limit, refresh recovery and a candidate-safe conversation projection (**Phase 9**). |
| Agent Inspector | ✅ complete | `/review/agent`: owner-scoped, safe observable execution (tools, retrieval, sources, memory, human approvals, warnings) — never chain-of-thought, prompts or raw checkpoint (**Phase 9**). |
| Safe observability | ✅ complete (local event level) | Safe agent events power the Coach activity line and the Inspector timeline; token/cost is honestly reported as not captured. |
| Persistent checkpoints | ✅ complete (SQLite/Postgres) | Official saver (`langgraph-checkpoint-sqlite`/`-postgres`); paused runs survive service recreation. `MemorySaver` remains the transitional fallback for `:memory:`/unset. Checkpoint schema is saver-owned, separate from Alembic. |
| Model selection (reviewer: "outdated LLMs") | ✅ ADDRESSED | Typed model registry (`src/llm/models.py`) with Fast/Balanced/Advanced profiles → current OpenRouter slugs (env-overridable); explicit workload→profile policy; capability/temperature/legacy handling centralised (**Phase 9.5**). |

## Optional requirements

| Tier | Item | Status |
|---|---|---|
| Medium | Memory (long-term) | ✅ complete — selective preparation memory, Phase 7 |
| Medium | Authentication / personalisation | ⚙️ transitional seam (production OIDC later) |
| Medium | Tools (agent-registered) | ✅ complete — 6 real tools incl. `SearchCareerKnowledge` (Phase 6) and `ResearchCurrentMarket` (Phase 7F) |
| Medium | Security guard | ✅ existing / preserved (agent adds allowlist + injection-safe prompt; retrieved content stays untrusted DATA) |
| Hard | Agentic RAG | ✅ complete — the agent decides *whether* to retrieve; the deterministic Sprint 3 router still decides *which* lanes (Phase 6) |
| Hard | Human-in-the-loop | ✅ complete — LangGraph interrupt/resume with durable checkpoints (Phase 8) |
| Hard | RAGAS | ✅ harness preserved (Career-answer faithfulness/relevancy/precision/recall; adapter + finite-score guards; agent-RAG evaluation prepared where implemented). **No paid live RAGAS run executed** (opt-in `--live`). |
| Hard | External source | 🔷 possible company research tool |

> No future work is marked complete. See
> [sprint4_roadmap.md](sprint4_roadmap.md) for phase sequencing and
> [sprint4_architecture.md](sprint4_architecture.md) for the design decisions.
