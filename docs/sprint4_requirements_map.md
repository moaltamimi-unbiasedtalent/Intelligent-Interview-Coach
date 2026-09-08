# Sprint 4 Requirements Map — Intelligent Interview Coach

Maps the Sprint 4 course requirements to implementation. Status is accurate as of
Phase 9.5 — items still in progress say so; nothing future is overstated.

## Core requirements

| Requirement | Status (Phase 9.5) | Notes |
|---|---|---|
| Clear agent purpose | ✅ implemented/documented | Career & Interview Preparation Agent — one primary agent from target role to practised interview. |
| 3+ tools (agent) | ✅ complete | The agent registers **5 real Career tools** (job analysis, gap analysis, preparation plan, question generation, and career-knowledge retrieval) as thin adapters over the existing capabilities. |
| LangGraph / LangChain | ✅ implemented | Single stateful bounded LangGraph agent; LangChain/OpenRouter model integration reused. |
| User interface | ✅ implemented | Next.js/TypeScript frontend (Streamlit retained temporarily). |
| Error handling | ✅ implemented | Safe errors + graph/tool failure handling (bounded loop, tool-failure recovery, safe messages). |
| Memory (short-term) | ✅ implemented | Agent execution state (in-run LangGraph checkpoint; transient). |
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
| Medium | 5 tools (agent-registered) | ✅ complete — 5 real tools incl. `SearchCareerKnowledge` (Phase 6) |
| Medium | Security guard | ✅ existing / preserved (agent adds allowlist + injection-safe prompt; retrieved content stays untrusted DATA) |
| Hard | Agentic RAG | ✅ complete — the agent decides *whether* to retrieve; the deterministic Sprint 3 router still decides *which* lanes (Phase 6) |
| Hard | Human-in-the-loop | ✅ complete — LangGraph interrupt/resume with durable checkpoints (Phase 8) |
| Hard | RAGAS | ✅ existing / extend to agent runs later |
| Hard | External source | 🔷 possible company research tool |

> No future work is marked complete. See
> [sprint4_roadmap.md](sprint4_roadmap.md) for phase sequencing and
> [sprint4_architecture.md](sprint4_architecture.md) for the design decisions.
