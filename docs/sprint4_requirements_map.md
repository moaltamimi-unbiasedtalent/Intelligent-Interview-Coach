# Sprint 4 Requirements Map — Intelligent Interview Coach

Maps the Sprint 4 course requirements to implementation. Status is accurate as of
Phase 4 — items still in progress say so; nothing future is overstated.

## Core requirements

| Requirement | Status (Phase 4) | Notes |
|---|---|---|
| Clear agent purpose | ✅ implemented/documented | Career & Interview Preparation Agent — one primary agent from target role to practised interview. |
| 3+ tools (agent) | ✅ complete | The agent registers **4 real Career tools** (job analysis, gap analysis, preparation plan, question generation) as thin adapters over the existing capabilities. Career retrieval becomes an agent tool in **Phase 6** (Agentic RAG). |
| LangGraph / LangChain | ✅ implemented | Single stateful bounded LangGraph agent; LangChain/OpenRouter model integration reused. |
| User interface | ✅ implemented | Next.js/TypeScript frontend (Streamlit retained temporarily). |
| Error handling | ✅ implemented | Safe errors + graph/tool failure handling (bounded loop, tool-failure recovery, safe messages). |
| Memory | ⚙️ short-term only | Agent execution state (in-run checkpoint). Long-term cross-session memory is **Phase 7**. |
| Human-in-the-loop | 🔷 planned | Role confirm / memory-write / handoff approval — **Phase 8**. |

## Optional requirements

| Tier | Item | Status |
|---|---|---|
| Medium | Memory (long-term) | 🔷 planned (Phase 7) |
| Medium | Authentication / personalisation | ⚙️ transitional seam (production OIDC later) |
| Medium | 5 tools (agent-registered) | ⚙️ 4 today; a 5th (retrieval) lands in Phase 6 |
| Medium | Security guard | ✅ existing / preserved (agent adds allowlist + injection-safe prompt) |
| Hard | Agentic RAG | 🔷 planned (Phase 6) |
| Hard | RAGAS | ✅ existing / extend to agent runs later |
| Hard | External source | 🔷 possible company research tool |

> No future work is marked complete. See
> [sprint4_roadmap.md](sprint4_roadmap.md) for phase sequencing and
> [sprint4_architecture.md](sprint4_architecture.md) for the design decisions.
