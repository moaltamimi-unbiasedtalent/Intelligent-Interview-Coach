# Sprint 4 — Submission Summary

**Ask4Mo — Intelligent Interview Coach** (*Ask More. Be More.*) is a stateful AI Career
Preparation Agent that turns evidence-backed career intelligence into targeted interview
practice. Its candidate-facing AI Coach is **Mo** — the identity of that same agent (not
a new agent, model or backend). LangGraph decides which controlled
tools to use and when. Agentic RAG supplies grounded career evidence; selective memory
preserves user-approved context; HITL protects important assumptions and persistent
actions; and a typed `PreparationContext` carries the result into durable Interview
Practice. The final system also includes registry-backed multi-model execution,
candidate feedback with a human-reviewed improvement loop, and privacy-safe first-party
and optional external observability.

## Problem

Candidates preparing for professional, specialist and leadership interviews lack
grounded, role-aware preparation and realistic practice, and lose progress across
sessions.

## Solution

A stateful Career Preparation Agent that helps a candidate understand a target
opportunity, identify gaps, build an evidence-backed plan, and move into durable
Interview Practice — with human approval where the system should not decide alone.

## Architecture

Candidate → Next.js → FastAPI → LangGraph agent (short-term checkpoint state, selective
approved long-term memory, HITL interrupts, Fast/Balanced/Advanced) → controlled tools →
`PreparationContext` → HITL Practice approval → durable Interview Practice → Deep Dive +
Final Report. See `docs/sprint4_architecture.md` for the full diagram.

## Agent tools

Five allowlisted Career tools — SearchCareerKnowledge, AnalyzeJobDescription,
AnalyzeCandidateGaps, BuildPreparationPlan, GenerateInterviewQuestions — plus two
separate HITL action boundaries (ProposePreparationMemory, RequestPracticeHandoff).
Unknown tools are rejected, never executed.

## Agentic RAG

The agent decides *whether* to retrieve; the deterministic Career router decides *which*
lanes/sources. The model is never the fact source; evidence returns normalised with
citations.

## Memory + HITL

Short-term checkpoint state vs selective, user-approved long-term memory (list / edit /
pin / delete / next-run preview / edit-before-save). Pinning changes priority only; the
current request always wins. Real `interrupt`/`resume` HITL guards role ambiguity,
memory writes and Practice handoff.

## Multi-model

Fast / Balanced / Advanced registry profiles; candidate selector; server-side
validation; a raw provider slug is never accepted. Tools, grounding, memory, HITL and
security are identical across profiles. No paid comparison executed.

## Feedback

Helpful / Not-helpful (+ optional comment) on Agent answers, interview evaluations and
final reports, validated against the exact owned output. Aggregated for human review →
evaluation case → controlled, regression-tested change. No autonomous self-modification.

## Observability

Agent Inspector (first-party) shows tools, retrieval, citations, memory, HITL, profile,
model calls, tokens, cost coverage, latency, cache, journey and handoff — never
chain-of-thought. Optional Langfuse (OFF by default) receives only sanitised operational
metadata.

## Interview handoff

`PreparationContext` is the authoritative typed handoff; provenance is shown; interview
creation stays outside LangGraph and is idempotent.

## Evaluation

Four distinct layers: deterministic orchestration regression (56 scripted cases, gated
in CI), the live real-model harness (22 cases, paid opt-in — not executed), RAGAS
generation quality (35 cases, optional paid — no paid baseline), and product regression
(pytest / frontend / Playwright / Alembic / Docker / secret scan).

## Security

Trust separation, tool allowlist, injection guards, shared output guard, citation
provenance, exact feedback-target ownership, cross-user isolation, sanitised logging and
observability, and fail-closed production identity.

## Results

Python **1845 passed / 2 skipped**; frontend **111**; Playwright **37**; Alembic single
head **0006**; Docker builds; ruff/compileall/secret-scan clean; deterministic agent gate
**PASS**. See `docs/sprint4_final_evidence.md`.

## Limitations (intentional)

Production OIDC; live PostgreSQL deployment validation; bulk checkpoint retention; paid
Fast/Balanced/Advanced comparison; paid live RAGAS baseline; external company research;
Streamlit retained as legacy; Live voice experimental/off; no camera/video.
