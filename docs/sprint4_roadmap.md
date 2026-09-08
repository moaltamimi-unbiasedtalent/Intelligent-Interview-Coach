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
| **3C** | **Career/Preparation frontend integration** ✅ done (live `/prepare` + handoff) | 3–4 days | 3B |
| 3 | Next.js / TypeScript frontend foundation | 3–4 days | 2 |
| **4** | **LangGraph agent foundation** ✅ done (`src/agent`, side-by-side) | 2–3 days | 1 (2 helpful) |
| **5** | **Convert capabilities into agent tools** ✅ done (4 real Career tools) | 2–3 days | 4 |
| **6** | **Agentic RAG (retrieval as an agent-selected tool)** ✅ done (5th tool `SearchCareerKnowledge`) | 2–3 days | 5 |
| **7** | **Selective long-term preparation memory** ✅ done (`preparation_memories`, `/memory`, agent read) | 2–3 days | 4, 5 |
| **8** | **LangGraph human-in-the-loop** ✅ done (interrupt/resume; role confirm, memory approval, handoff; durable SQLite/Postgres checkpoints) | 1–2 days | 4, 7 |
| **9** | **Agent Coach + Agent Inspector + multi-turn** ✅ done (candidate `/prepare` via the agent behind `AGENT_COACH_ENABLED`; same-thread continuation; HITL cards; safe Inspector) | 2–3 days | 3, 4 |
| **9.5** | **Model registry + modern OpenRouter models** ✅ done (typed Fast/Balanced/Advanced profiles; env-overridable; workload policy; addresses "outdated LLMs" feedback) | 1 day | 9 |
| 10 | Complete Streamlit → Next.js migration (prove parity, retire fallback) | 3–5 days | 3, 9 |
| 11 | Agent evaluation / RAGAS extension / hardening | 2–3 days | 5–10 |

## Key dependencies and sequencing notes

- **Phase 1 is the enabler.** Decoupling domain logic from Streamlit lets both the
  FastAPI backend (Phase 2) and the LangGraph agent (Phase 4) call the same core.
- **Retrieval-as-a-tool (Phase 6)** depends on the tool conversion (Phase 5); the
  deterministic retrieval internals from Sprint 3 are wrapped, not rewritten.
- **Long-term memory (Phase 7)** is a separate durable, user-scoped DB
  (`preparation_memories`) from the transient LangGraph checkpoint; writes are
  explicit/user-initiated (no automatic agent persistence yet).
- **HITL (Phase 8)** uses LangGraph's `interrupt`/`Command(resume=...)` on a durable
  checkpoint (official SQLite/Postgres saver) so approvals gate real state changes
  (ambiguous-role confirmation, agent-proposed memory writes, practice handoff). The
  durable checkpoint (execution state) is separate from long-term memory (approved,
  cross-session knowledge).
- **Streamlit stays as a fallback** until Phase 10 proves Next.js parity.
- **Evaluation (Phase 11)** extends the existing RAGAS layer to agent runs rather
  than replacing it.

See [sprint4_architecture.md](sprint4_architecture.md) for the design decisions
and [sprint4_requirements_map.md](sprint4_requirements_map.md) for the
requirement-to-plan mapping.
