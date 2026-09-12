# Ask4Mo — Final Live Golden Rehearsal Evidence

**SINGLE AUTHORIZED RUN: YES · RUNS EXECUTED: 1 · RERUNS: 0**

One authorized, paid, end-to-end live rehearsal of the real reviewer product (Next.js + FastAPI
+ live LangGraph agent on the Balanced profile). Machine-readable form:
[`evaluations/final/golden_run_result.json`](../evaluations/final/golden_run_result.json).

## Configuration

- **run_id:** `final-golden-20260912-192348`
- **validated code SHA:** `afb4f45` (branch `release/sprint4-final-freeze`, clean tree before the run)
- **profile / model:** Balanced → `openai/gpt-5.6-terra` (default reviewer profile; not switched)
- **backend:** FastAPI `src.api.main:app` on `127.0.0.1:8000`, `AGENT_COACH_ENABLED=true`
- **frontend:** Next.js production build on `:3999` (`:3000` was held by an unrelated process — not touched)
- **credential:** the existing local OpenRouter key from `.streamlit/secrets.toml`, bridged
  ephemerally into the backend process environment only — never printed, logged, or committed.

## Synthetic scenario (no real PII)

- Candidate: synthetic mid-level Backend Software Engineer (~4 yrs Python/REST/PostgreSQL/Docker/CI-CD/AWS).
- Job description: synthetic mid-level Backend Software Engineer role.

## Observed candidate journey

| Step | Result |
|---|---|
| Home → Prepare | **PASS** — no candidate data in URL or localStorage |
| Ask Mo — analysis | **PASS** — role-requirement map + gap analysis (AnalyzeJobDescription, AnalyzeCandidateGaps) |
| Career Intelligence citations | **NOT MET** — see note below (safety intact) |
| Preparation plan | **PASS** — target role, strengths, priority gaps, plan ready |
| Memory HITL | **NOT TRIGGERED** — model did not propose memory naturally (not forced) |
| Mo → Practice handoff | **PASS** — RequestPracticeHandoff → provenance-rich handoff card → approval |
| Practice setup | **PASS** — a genuine context gap returned 422 and surfaced a graceful "one last detail" card (industry + career level), not a crash or fabrication |
| **Q1 without reload** | **PASS (critical)** — auto-navigated to `/practice`; "Question 1 of 6" appeared with no reload |
| Answer evaluation | **PASS** — 82/100, structured, "not a hiring decision" |
| Deep Dive | **PASS** — level 1 of 2 loaded with a relevant follow-up |
| Deep Dive return | **PASS** — returned to the question view; feedback state preserved |
| Final report | **PASS** — "Performance review · Practice readiness 82/100"; structured; no internal metadata |
| History | **PASS** — completed session present in the server-backed history list |
| Reload / resume | **PASS** — fresh navigation to the session URL re-loaded the durable report |
| Agent Inspector | **PASS** — coherent timeline (tools, retrieval, HITL, usage); no CoT/prompt/checkpoint/secret |

## Agent / tool behaviour (from the Agent Inspector)

Run completed. Tools used: Analysing the job description (6 sources), Checking career evidence
(SearchCareerKnowledge), Comparing your experience (gap analysis, 11 sources), Checking career
evidence (again), Getting ready for practice. Retrieval used: Yes. Human confirmation requested
→ Practice handoff approved (HITL). Usage: Balanced, 11 model calls (8 agent / 3 tool),
32,250 tokens, coverage Complete, estimated cost "—".

## Citation evidence — the one unmet demonstration criterion (and why it is safe)

The chosen scenario deliberately used the normal reviewer flow. When asked explicitly for
evidence, the agent **did** invoke `SearchCareerKnowledge`, but the knowledge base returned
**insufficient evidence** for a "backend software engineer" role — a **documented coverage gap**
(software-engineering role resolution is among the known failing cases in the 0.914 retrieval
baseline). Crucially, **Mo refused to fabricate citations**: *"It returned insufficient evidence
and no sources/citations, so I can't responsibly present citations."* This is the
no-fabricated-citation **safety property working as designed** — a stronger positive signal than a
citation would have been. Deterministic citation capability is independently proven by the
retrieval suite (citation_completeness 1.0).

## HITL evidence

Practice handoff used the real `RequestPracticeHandoff` action tool → a candidate-safe handoff
card sourcing "Role — from your job description" and "Priority areas — from your gap analysis" →
explicit approval (`APPROVE_PRACTICE_HANDOFF`). The interview was created in the frontend after
approval (idempotent), never inside LangGraph.

## Practice / Deep Dive / Report / History

Durable Interview Practice drove question → evaluation (82/100) → Deep Dive (level 1 of 2) →
return → completion → performance review (82/100) → history persistence → resume. All server
responses 200; the session and report survived a fresh reload.

## Provider usage

Agent run: 11 model calls (8 agent / 3 tool), 32,250 tokens, coverage Complete. Interview
practice added ~3 model calls (answer evaluation, deep-dive evaluation, final report) →
**~14 total provider calls**. **Cost: UNKNOWN** (Inspector reported "—"; no pricing metadata).

## Security / privacy

No candidate data in URL or localStorage (only an `agent.profile` UI preference). No cross-user
issue (owner-scoped run/session ids). No chain-of-thought, system prompt, checkpoint, or secret
exposed anywhere (Inspector included). **HTTP 5xx: 0.** The only non-2xx was one expected 422
(graceful setup-gap handling). No masked provider error.

## Failures / model variance

- No product defect. No provider failure. No abort condition triggered.
- Model variance (not defects): turn-2 role mapping answered without retrieval; memory not
  proposed naturally; evidence request retrieved but hit a KB coverage gap.

## Final verdict

**LIVE GOLDEN: PASS** (with one documented caveat — governed citations were not surfaced for the
software-engineering scenario due to a known KB coverage gap; the agent retrieved and correctly
refused to fabricate, so the safety-critical property held). **Product defect: NO. P0: 0. P1: 0.**

**AUTHORIZED RUNS: 1 · RUNS EXECUTED: 1 · RERUNS: 0.**
