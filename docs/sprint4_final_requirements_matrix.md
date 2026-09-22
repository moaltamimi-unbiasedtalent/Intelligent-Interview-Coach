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
| Controlled tools | COMPLETE | Six Career tools via a strict allowlist registry (no dynamic import/eval; unknown names rejected), incl. `ResearchCurrentMarket` (bounded current-market research, Phase 7F). Two SEPARATE human-action tools request approvals. | `src/agent/tools.py`, `src/agent/registry.py` | Inspector → tool timeline | UI actions are never counted as tools |
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
| Evaluation | COMPLETE | Four distinct layers: deterministic contract gate, live model-decision harness, LLM-as-judge (advisory), RAGAS (optional). Two authorised paid live runs are recorded as evidence. | `scripts/eval_agent.py`, `scripts/eval_agent_live.py`, `scripts/eval_agent_judge.py`, `src/agent/judge.py`, `evaluations/` | Show `docs/sprint4_final_evidence.md` | Paid RAGAS baseline not executed; live runs are a bounded sample, not an accuracy % |
| Security / privacy | COMPLETE | Trust model, tool allowlist, injection guards, shared output guard, citation provenance, exact feedback-target ownership, cross-user isolation, sanitised logging & observability, fail-closed production identity. | `docs/sprint4_security_privacy.md`, `src/copilot/security/*`, `src/agent/grounding.py` | Cross-user tests | Production OIDC is a follow-up |
| Production OIDC | NOT IMPLEMENTED (deployment follow-up) | Transitional `X-User-Subject`; fail-closed in production. | `src/api/dependencies.py` | — | Needs a real gateway/OIDC |
| MCP external tool protocol | NOT REQUIRED | Internal controlled function registry sufficed for internal tools. | — | — | — |
| Multi-agent | NOT REQUIRED | One coherent preparation task; capabilities exposed as tools, not agents. | — | — | — |

## Evaluation layers (kept distinct)

| Layer | Status | What it measures | Evidence |
|---|---|---|---|
| A. Deterministic agent orchestration | COMPLETE | Graph/tool contract on **56 scripted-model** cases (required/retrieval recall, unnecessary rates, citation & retrieval-sequence validity, completion, unregistered attempts, HITL/cross-user probe). **Not** live-model tool-selection accuracy. | `scripts/eval_agent.py`, `src/agent/eval.py`, gate PASS |
| B. Live real-model agent evaluation | COMPLETE; **TWO AUTHORISED PAID RUNS EXECUTED** (Balanced) | Real-model tool/retrieval/HITL decisions on **22 held-out** cases; record/replay sanitised traces; paid opt-in. Recorded evidence: run 1 completion 1.0, retrieval-decision 0.909, unnecessary-retrieval 0.0, judge avg 10.05/12; run 2 completion 1.0, retrieval-decision 0.864, unnecessary-retrieval 0.0, judge avg 9.67/12; 0 critical / 0 safety failures both runs. A paid Fast/Advanced profile comparison was **not** executed. | `scripts/eval_agent_live.py`, `src/agent/live_eval.py`, `docs/sprint4_final_evidence.md` §B |
| C. RAGAS | COMPLETE (available); optional paid | Generation quality (faithfulness / response relevancy / context precision / context recall) over **35** cases. Not an "accuracy %". | `evaluations/ragas/`, `docs/ragas_evaluation.md` |
| D. Product regression | COMPLETE | pytest, frontend unit, Playwright, Alembic, Docker, secret scan. | see `docs/sprint4_final_evidence.md` |

## Intentionally outside this Sprint

Production OIDC · live PostgreSQL deployment validation · bulk LangGraph checkpoint
retention (deployment op) · paid Fast/Balanced/Advanced comparison · paid live RAGAS
baseline · live external-research integration (Adzuna / company web) not validated in
this environment — bounded `ResearchCurrentMarket` tool implemented (Phase 7F) ·
voice (experimental, off) · camera/video (never).

## Sprint 4 deliverables closure (post-release)

These update earlier statuses after the post-release surface audit and the closure phase.
Full narrative: `docs/post_release_product_surface_audit.md`, `docs/sprint4_deliverable_implementation_stories.md`, `docs/sprint4_technical_critique.md`.

| # | Requirement | Status | How / evidence | Limitation |
|---|---|---|---|---|
| 1 | Purpose | COMPLETE | Unified understand→prepare→practise→improve journey | English-first; generic across professions |
| 2 | Core functionality | COMPLETE | Bounded LangGraph agent, allowlisted tools, agentic RAG, HITL, approved memory, durable Practice, evaluation, Deep Dive, report, History, Progress | Live tool-selection ~0.59–0.64 |
| 3 | UI | COMPLETE | Every primary + supporting surface renders real data; no unexplained placeholder (`frontend/app/*`, 166 vitest + 57 e2e) | No per-user Agent-run browser (P3) |
| 4 | Technical | COMPLETE | FastAPI over app layer, durable persistence, user scoping, SSRF/injection guards (2145 pytest, contract, secret scan) | Production OIDC is deployment work |
| 5 | Documentation | COMPLETE | README + reviewer package + critique + stories + audit | Re-check vs behaviour each phase |
| 6 | Technical critique | YES | `docs/sprint4_technical_critique.md` | — |
| 7 | Personality/tone | LIMITED (by choice) | No rubric requirement for a tone preference; model style stays consistent/controlled | Not implemented to avoid touching the frozen agent prompt for uncertain value |
| 10 | Help / guide | YES (strengthened) | Interactive route-aware guided tour + searchable Help Center + contextual links (`frontend/components/tutorial/*`, `frontend/components/help/HelpCenter.tsx`, `docs/guided_tutorial.md`); tests `tutorial.test.tsx`/`help.test.tsx`/`tutorial.spec.ts`. History: PARTIAL → Help Center (closure) → interactive onboarding (this phase) | No behavioural-analytics adaptation; keyword search by design |
| 16 | 5+ tools + capability control | YES | 6 career + 2 HITL tools; server-enforced current-market-research ON/OFF toggle (`tests/test_agent_capability_toggle.py`) | One capability today (same mechanism extends to others) |
| 21 | RAGAS | YES (deterministic) | Reproducible harness; visible read-only at `/review/evaluation`; **paid judge NOT RUN** | Paid judge is opt-in only |
| — | Progress surface | COMPLETE | `/progress` practice metrics + memory (`GET /api/v1/progress`) | No longitudinal trend chart |
| — | History surface | COMPLETE | `/history/[id]` detail report | — |
| — | Sources surface | COMPLETE | Safe public links + governed provenance | Governed sources without a public record are shown, not linked |
| — | Evaluation surface | COMPLETE | `/review/evaluation` offline RAGAS read-only | — |
| — | Knowledge & RAG surface | COMPLETE | `/review/rag` governed counts + offline retrieval quality + known gaps (`GET /knowledge/diagnostics`) | Coverage gaps documented in-product |
