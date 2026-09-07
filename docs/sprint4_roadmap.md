# Sprint 4 Roadmap — Intelligent Interview Coach

Planned phases for the Sprint 4 evolution into a stateful AI agent. Estimates are
rough and for sequencing only; each phase is delivered on its own branch with no
auto-merge, following the Sprint 3 workflow.

| Phase | Goal | Rough estimate | Depends on |
|---|---|---|---|
| **0** | **Sprint baseline + rebrand** ✅ done | 0.5 day | — |
| **1** | **Decouple Streamlit orchestration from backend domain logic** ✅ done (`src/application`) | 1–2 days | 0 |
| **2** | **FastAPI backend** ✅ done (`src/api`, `/api/v1`) | 2–3 days | 1 |
| **3A** | **Product UX + visual design spike** ✅ done (`docs/design/phase3a`, four concepts) | 1 day | 2 |
| **3B** | **Next.js foundation + Precision Coach design system** ✅ done (`frontend/`) | 3–4 days | 3A (design chosen) |
| 3C | Career/Preparation frontend integration | 3–4 days | 3B |
| 3 | Next.js / TypeScript frontend foundation | 3–4 days | 2 |
| 4 | LangGraph agent foundation | 2–3 days | 1 (2 helpful) |
| 5 | Convert capabilities into agent tools | 2–3 days | 4 |
| 6 | Agentic RAG (retrieval as an agent-selected tool) | 2–3 days | 5 |
| 7 | Short-term + long-term memory | 2–3 days | 4, 5 |
| 8 | Human-in-the-loop (role confirm, memory-write, handoff) | 1–2 days | 4, 7 |
| 9 | Agent Coach + Agent Inspector UI | 2–3 days | 3, 4 |
| 10 | Complete Streamlit → Next.js migration (prove parity, retire fallback) | 3–5 days | 3, 9 |
| 11 | Agent evaluation / RAGAS extension / hardening | 2–3 days | 5–10 |

## Key dependencies and sequencing notes

- **Phase 1 is the enabler.** Decoupling domain logic from Streamlit lets both the
  FastAPI backend (Phase 2) and the LangGraph agent (Phase 4) call the same core.
- **Retrieval-as-a-tool (Phase 6)** depends on the tool conversion (Phase 5); the
  deterministic retrieval internals from Sprint 3 are wrapped, not rewritten.
- **HITL (Phase 8)** depends on the agent (Phase 4) and memory (Phase 7) so that
  approvals gate real state changes.
- **Streamlit stays as a fallback** until Phase 10 proves Next.js parity.
- **Evaluation (Phase 11)** extends the existing RAGAS layer to agent runs rather
  than replacing it.

See [sprint4_architecture.md](sprint4_architecture.md) for the design decisions
and [sprint4_requirements_map.md](sprint4_requirements_map.md) for the
requirement-to-plan mapping.
