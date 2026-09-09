# Sprint 4 — Final Requirements Matrix

The single authoritative mapping from Sprint 4 / portfolio expectations to the actual
implementation, with evidence and reviewer-demo pointers. Status vocabulary:
**COMPLETE**, **PARTIAL**, **NOT IMPLEMENTED**, **NOT REQUIRED**.

Verified against merged `main` at this freeze (see `docs/sprint4_final_evidence.md` for
the numeric evidence sheet).

## Core product & agent

**Product:** Intelligent Interview Coach. **Agent:** Career Preparation Agent.
**Primary user:** candidates preparing for professional, specialist and leadership
interviews. **Purpose:** help a candidate understand a target opportunity, identify
preparation gaps, build an evidence-backed preparation strategy, and transition into
targeted Interview Practice.

| Requirement | Status | Implementation | Evidence / code | Reviewer demo | Limitations |
|---|---|---|---|---|---|
| Stateful AI Agent | COMPLETE | A single bounded LangGraph agent decides whether/which/what-order tools to call within a tool allowlist, bounded loop and HITL constraints. Sprint 3 was a largely deterministic Career workflow; Sprint 4 introduced agent-owned orchestration. | `src/agent/graph.py`, `src/agent/nodes.py`, `src/agent/policies.py`, `src/application/agent_service.py` | Prepare page → give a role/JD → watch the agent choose tools | Single agent by design (not multi-agent) |
| Controlled tools | COMPLETE | Five Career tools via a strict allowlist registry (no dynamic import/eval; unknown names rejected). Two SEPARATE human-action tools request approvals. | `src/agent/tools.py`, `src/agent/registry.py` | Inspector → tool timeline | UI actions are never counted as tools |
| Agentic RAG | COMPLETE | The agent decides *whether* to retrieve; `SearchCareerKnowledge` then calls the existing deterministic Career retrieval layer, which decides *which* lanes/sources. The LLM is not the fact source; evidence returns normalised with provenance/citations. | `src/agent/tools.py` (`_search_career_knowledge`), `src/copilot/service.py` | Ask a factual pay/labour-market question → citations appear | Retrieval quality bounded by the KB |
| Long-term memory | COMPLETE | User-approved, bounded, user-scoped DB records (list/edit/pin/unpin/delete/next-run preview/edit-before-save HITL/safe loaded-memory cue). Pinning changes deterministic load priority only; the current request always wins. | `src/memory.py`, `src/application/memory_service.py`, `src/repository.py` (`MemoryRepository`), migrations `0002`/`0005`, `frontend/components/memory/MemoryManager.tsx` | Settings → Preparation memory | Deterministic selection (no vector memory) |
| Short-term memory | COMPLETE | LangGraph checkpoint (execution state), durable saver, separate from long-term memory. | `src/agent/checkpoint.py`, `src/agent/state.py` | Inspector → steps | — |
| Human-in-the-loop | COMPLETE | Real `interrupt()` / `Command(resume=...)` on a durable checkpoint for three decisions only: ambiguous role, long-term memory write, Practice handoff. | `src/agent/human.py`, `src/agent/nodes.py` (`human_review`) | Approve/edit a proposed memory; approve handoff | Selective by design (not per tool) |
| Multi-model | COMPLETE | Fast/Balanced/Advanced registry; candidate selector; server-side validation; raw provider slug rejected; tools/grounding/memory/HITL/security independent of profile. | `src/llm/models.py`, `src/application/agent_service.py` (`_resolve_profile`), `frontend/components/agent/usage.tsx` | Coach → Speed selector; Inspector → profile | No paid profile comparison executed |
| Feedback loop | COMPLETE | Helpful/Not-helpful (+optional comment) on Agent answer, interview evaluation and final report; exact-target ownership+existence validation; aggregate metrics; human-reviewed engineering loop → evaluation case → regression gates. No autonomous self-modification. | `src/feedback.py`, `src/application/feedback_service.py`, `src/api/feedback_targets.py`, `scripts/export_feedback_summary.py`, migration `0006` | Rate an answer; refresh → rating persists | Improvement is human-reviewed, not automatic |
| Observability (first-party) | COMPLETE | Agent Inspector: tools, retrieval, citations, memory, HITL, profile, model calls, tokens, cost coverage, latency, cache, journey, handoff. Never CoT/system prompt/raw checkpoint/tool args. | `frontend/components/agent/AgentInspector.tsx`, `src/agent/usage.py` | `/review/agent` | — |
| Observability (external) | COMPLETE (optional, OFF) | Provider-neutral sink; NoOp default; optional Langfuse emits only a sanitised operational projection via manual events (no auto-tracing). | `src/observability/*` | env-gated; not shown live | OFF by default; no live call in CI |
| Journey UX | COMPLETE | UNDERSTAND → PREPARE → PRACTISE chrome + observable preparation checklist derived from real state. | `frontend/components/agent/JourneyChrome.tsx`, `src/agent/journey.py` | Prepare page | — |
| Practice handoff | COMPLETE | Typed `PreparationContext` is the authoritative handoff; a provenance card shows what/where; interview creation stays OUTSIDE LangGraph and is idempotent. | `src/agent/journey.py` (`derive_handoff_summary`), `frontend/components/agent/PendingHumanActionCard.tsx` | Approve practice → Practice opens | — |
| Interview Practice | COMPLETE | Durable sessions; typed flow (question→answer→evaluation→Deep Dive→report→History); idempotent completion. Not a second autonomous agent. | `src/session_manager.py`, `src/interview/session_repository.py`, migrations `0003`/`0004` | Practice page | Deep-Dive feedback out of scope |
| Primary UI | COMPLETE | Next.js (primary) over FastAPI; Streamlit retained as a legacy development interface (in-app banner). | `frontend/`, `src/api/`, `app.py` | Run Next.js + FastAPI | Streamlit legacy |
| Evaluation | COMPLETE | Four distinct layers (see below). | `scripts/eval_agent.py`, `scripts/eval_agent_live.py`, `evaluations/`, tests | Show artifacts | Paid live/RAGAS runs not executed |
| Security / privacy | COMPLETE | Trust model, tool allowlist, injection guards, shared output guard, citation provenance, exact feedback-target ownership, cross-user isolation, sanitised logging & observability, fail-closed production identity. | `docs/sprint4_security_privacy.md`, `src/copilot/security/*`, `src/agent/grounding.py` | Cross-user tests | Production OIDC is a follow-up |
| Production OIDC | NOT IMPLEMENTED (deployment follow-up) | Transitional `X-User-Subject`; fail-closed in production. | `src/api/dependencies.py` | — | Needs a real gateway/OIDC |
| MCP external tool protocol | NOT REQUIRED | Internal controlled function registry sufficed for internal tools. | — | — | — |
| Multi-agent | NOT REQUIRED | One coherent preparation task; capabilities exposed as tools, not agents. | — | — | — |

## Evaluation layers (kept distinct)

| Layer | Status | What it measures | Evidence |
|---|---|---|---|
| A. Deterministic agent orchestration | COMPLETE | Graph/tool contract on **56 scripted-model** cases (required/retrieval recall, unnecessary rates, citation & retrieval-sequence validity, completion, unregistered attempts, HITL/cross-user probe). **Not** live-model tool-selection accuracy. | `scripts/eval_agent.py`, `src/agent/eval.py`, gate PASS |
| B. Live real-model agent evaluation | COMPLETE (harness); **NO PAID RUN EXECUTED** | Real-model tool/retrieval/HITL decisions on **22 held-out** cases across Fast/Balanced/Advanced; record/replay sanitised traces; paid opt-in. | `scripts/eval_agent_live.py`, `src/agent/live_eval.py` |
| C. RAGAS | COMPLETE (available); optional paid | Generation quality (faithfulness / response relevancy / context precision / context recall) over **35** cases. Not an "accuracy %". | `evaluations/ragas/`, `docs/ragas_evaluation.md` |
| D. Product regression | COMPLETE | pytest, frontend unit, Playwright, Alembic, Docker, secret scan. | see `docs/sprint4_final_evidence.md` |

## Intentionally outside this Sprint

Production OIDC · live PostgreSQL deployment validation · bulk LangGraph checkpoint
retention (deployment op) · paid Fast/Balanced/Advanced comparison · paid live RAGAS
baseline · external company research · voice (experimental, off) · camera/video (never).
