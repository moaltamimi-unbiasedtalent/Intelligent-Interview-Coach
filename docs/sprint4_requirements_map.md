# Sprint 4 Requirements Map — Intelligent Interview Coach

Maps the Sprint 4 course requirements to the **planned** implementation. Nothing
here is complete yet; items are plans unless the status says otherwise.

## Core requirements

| Requirement | Plan |
|---|---|
| Clear agent purpose | **Career & Interview Preparation Agent** — one primary agent that helps a candidate go from a target role to a practised interview. |
| 3+ tools | At least **5 existing capabilities + a retrieval tool**: career retrieval, JD analysis, candidate gap analysis, preparation planning, question generation (+ later company research). |
| LangGraph / LangChain | **LangGraph** state machine for orchestration; **LangChain / OpenRouter** for model + tool integration. |
| User interface | **Next.js / TypeScript** frontend (Streamlit retained temporarily as a fallback until parity). |
| Error handling | Existing **safe errors** + **graph/tool failure handling** (bounded loops, tool-failure recovery, safe messages). |
| Memory | **Short-term graph state** + **selective long-term preparation memory** (HITL-approved writes). |
| Human-in-the-loop | **Role confirmation, memory-write approval, handoff approval.** |

## Optional requirements

| Tier | Item | Status |
|---|---|---|
| Medium | Memory | Planned |
| Medium | Authentication / personalisation | Existing foundation / adapt to API frontend |
| Medium | 5 tools | Planned |
| Medium | Security guard | Existing / preserve |
| Hard | Agentic RAG | Planned |
| Hard | RAGAS | Existing / extend to agent runs |
| Hard | External source | Possible **company research tool** |

> No future work is marked complete. See
> [sprint4_roadmap.md](sprint4_roadmap.md) for phase sequencing and
> [sprint4_architecture.md](sprint4_architecture.md) for the design decisions.
