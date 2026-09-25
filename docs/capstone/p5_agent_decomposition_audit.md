# P5 — Agent Decomposition Audit

_Capstone P5 + E4. Written before implementation to decide **where** bounded
multi-agent structure genuinely adds value and where it would be needless complexity._

## Guiding principle

> Agentic complexity is introduced ONLY where reasoning, multi-step synthesis,
> uncertainty handling or evidence comparison genuinely benefits from it. Deterministic
> logic is never converted into an agent just to increase the number of agents.

Mo stays the **single candidate-facing orchestrator** (the existing bounded LangGraph
ReAct agent). Specialists sit **behind** Mo, reached only through allowlisted tools; the
candidate still talks to one coach.

## Classification of every Mo capability

Legend — **DET** deterministic (no model) · **TOOL** thin direct tool over an existing
service · **SPECIALIST** a bounded specialist runtime · **HITL** human-in-the-loop
action · **KEEP** keep as-is, do not agentify.

| Capability | Today | P5 decision | Justification |
|---|---|---|---|
| Job-description analysis | LLM tool (`AnalyzeJobDescription`) | **KEEP** (reused by a specialist) | Already a governed structured op; a specialist reuses it, doesn't replace it. |
| Candidate gap analysis | DET tool (`AnalyzeCandidateGaps`) | **KEEP / DET** | Pure comparison; no reasoning benefit from an agent. |
| Preparation plan | DET tool (`BuildPreparationPlan`) | **KEEP / DET** | Arithmetic allocation; deterministic by design. |
| Question generation | LLM tool (`GenerateInterviewQuestions`) | **KEEP** | Single structured generation; no multi-step synthesis. |
| Career-knowledge retrieval | RAG tool (`SearchCareerKnowledge`) | **KEEP** | Deterministic router already owns lane selection; agentic-RAG boundary must not change (owns `retrieval_used`). |
| Current-market research | External tool (`ResearchCurrentMarket`) | **KEEP** | Bounded provider call; single step. |
| **Role & opportunity understanding** | (implicit in Mo's prose) | **SPECIALIST A** | Multi-step synthesis: turn a JD / prior analysis into a *structured brief* (competencies → themes → priorities). Benefits from a dedicated, schema-validated runtime; reuses the governed JD-analysis op. |
| **Selecting the candidate's own evidence** | (none) | **SPECIALIST B (DET)** | Evidence comparison across the private store. Deliberately **deterministic** — owner-scoped selection/ranking of APPROVED evidence. No model ⇒ injection-inert and privacy-safe. This is the strongest, most defensible decomposition. |
| **Interview strategy / answer coaching** | (implicit in Mo's prose) | **SPECIALIST C** | Genuine synthesis + uncertainty handling: map evidence→competencies, surface gaps, and raise **clarifications instead of fabricating** metrics. Benefits from a bounded runtime with a no-fabrication contract. |
| Memory proposal | HITL (`ProposePreparationMemory`) | **KEEP / HITL** | Approval-gated write; unchanged. |
| Practice handoff | HITL (`RequestPracticeHandoff`) | **KEEP / HITL** | Approval-gated; interview creation stays outside LangGraph. |
| Ambiguous-role confirmation | HITL (`CONFIRM_ROLE`) | **KEEP / HITL** | Deterministic trigger in retrieval; unchanged. |
| Final candidate-facing synthesis | Mo + output guard + presentation | **KEEP / DO NOT AGENTIFY** | Mo owns the voice; splitting it would create parallel chat surfaces. |

### The three specialists (the only new agentic structure)

- **A. Role & Opportunity Specialist** — model-backed (reuses the governed JD-analysis
  op), structured `RoleBrief` output.
- **B. Candidate Evidence Specialist** — **deterministic**, owner-scoped selection of the
  candidate's APPROVED claims and verified stories (`EvidenceSelection`).
- **C. Interview Strategy / Coach Specialist** — synthesis over the role brief + bounded
  evidence into a `CoachingPlan`; never invents metrics (raises clarifications).

These are **materially distinct**: different inputs, different outputs, different model
policy (A structured, B **none**, C structured), different data-access rights (only B
touches private evidence, and only deterministically).

## What was deliberately NOT agentified

- Gap analysis, the preparation planner, retrieval routing — all deterministic; an agent
  would add cost and non-determinism with no benefit.
- No fourth/fifth "specialist" was invented to inflate the count.
- Mo's ReAct loop, HITL, Practice, RAG governance, identity, i18n, Brief/Detailed and the
  presentation contract are untouched.

## Chosen integration seam

Specialists are **bounded tools behind Mo** (Pydantic arg-model + handler →
`ToolOutcome`), registered in `career_tool_registry`. This preserves — automatically —
the `bind_tools` allowlist, the bounded step budget, HITL, the output guard, the
`retrieval_used` invariant, and the deterministic agent eval. No graph node changes; Mo
remains the orchestrator that decides when to call a specialist. A deterministic
`recommend_specialists` router + a closed `SpecialistRegistry` provide validated routing
and back the reviewer diagnostic.

See `p5_e4_multi_agent_model_policy.md` for the full design, boundaries and safety proof.
