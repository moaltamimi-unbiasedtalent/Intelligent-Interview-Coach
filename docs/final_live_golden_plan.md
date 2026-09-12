# Ask4Mo — Final Live Golden Rehearsal Plan

**Status: READY — EXPLICIT AUTHORIZATION REQUIRED. NOT RUN.**

This is the single, normal, end-to-end live rehearsal of the reviewer product. It may incur
model/provider cost, so it is **not executed** in Phase 8. It runs exactly once, with the
normal reviewer configuration, only after the user explicitly authorizes a paid run.
Machine-readable form: [`evaluations/final/golden_run_plan.json`](../evaluations/final/golden_run_plan.json).

## Configuration

- **Profile:** Balanced (`openai/gpt-5.6-terra`) — the intended default reviewer profile.
  Do **not** switch to Advanced for a better demo.
- **Backend:** FastAPI (`uvicorn src.api.main:app`), `AGENT_COACH_ENABLED=true`,
  `OPENROUTER_API_KEY` set. Optional systems stay off unless the scenario needs them.
- **Frontend:** Next.js (`npm run start`), `http://localhost:3000` (or a free port if :3000 is
  held by an unrelated process — proven with `E2E_PORT` for the automated suite).
- **External research:** NOT required for the core golden. Only include
  `ResearchCurrentMarket` if the scenario genuinely asks for current information *and*
  Adzuna is configured *and* it has been authorized; otherwise bounded research is already
  demonstrated deterministically (`scripts/eval_external_research.py`, 38/38).
- **Observability:** optional; live Langfuse is NOT required and NOT authorized here.

## Inputs (synthetic / public only — no real candidate PII)

- **Candidate profile:** a synthetic mid-level backend software engineer summary (skills,
  years, target move) — no real name, email, phone, or personal history.
- **Job description:** a public/synthetic "Backend Software Engineer" JD (generic company).
- No production user data. No real CV upload.

## Golden path (single run)

1. Home → Prepare.
2. Mo analyses the candidate profile + JD (AnalyzeJobDescription).
3. Career Intelligence retrieval runs; **real citations are visible** in the evidence.
4. Gap analysis + preparation plan generated (AnalyzeCandidateGaps, BuildPreparationPlan).
5. Optional memory proposal → human approval path (ProposePreparationMemory / APPROVE_MEMORY).
6. Mo → Practice handoff (RequestPracticeHandoff / APPROVE_PRACTICE_HANDOFF).
7. Practice setup; **Q1 appears without a reload**.
8. Answer submitted → structured evaluation returned.
9. Deep Dive opened and works; return from Deep Dive works.
10. Next question or completion; final report generated.
11. History shows the completed session; reload/resume works where practical.
12. Agent Inspector timeline is coherent (observable-only; no CoT/prompts/raw checkpoint).

## Success criteria (§40)

no 5xx · no masked provider error · no reload needed for Q1 · citation-backed evidence ·
correct handoff · Practice evaluation works · Deep Dive works · return works · report works ·
History works · no candidate-data leakage (URL/localStorage) · no cross-user issue ·
Inspector timeline coherent · no P0/P1.

## Abort criteria

Any 5xx, masked provider error, Q1 requiring a reload, candidate-data leakage, or cross-user
access → abort the run, record the observation, classify it (§41), and stop. Do not retry to
chase a pass.

## Failure classification (§41)

- **Model variance** (e.g. the model answers well without calling a discrete tool): a measured
  model-behaviour signal, **not** automatically a product bug.
- **Provider failure** (timeout / 429 / 5xx from the provider): recorded separately as an
  environmental issue.
- **Product defect** (crash, leakage, masked error, broken handoff): P0/P1 by severity — fix
  separately, then request authorization before another paid run.

## One-run rule (§39)

When authorized, run exactly ONE rehearsal. Do not prompt-tune, change tools, change the
model after seeing the result, change the scenario after a failure, or rerun repeatedly.

## Estimated provider cost

- **Expected provider calls:** ~6–12 model calls for one full path (JD analysis, question
  generation, per-answer evaluation, Deep Dive, final report; gap analysis and the planner are
  deterministic/no-model). Exact count depends on the number of practice questions answered.
- **Cost:** not reliably knowable without provider pricing metadata; expected to be small
  (single-session, short contexts, Balanced profile). No pricing call is made here.

## Authorization

To execute later (after Phase 8 is merged and green):

```bash
# Backend (Terminal 1)
AGENT_COACH_ENABLED=true OPENROUTER_API_KEY=... uvicorn src.api.main:app --reload
# Frontend (Terminal 2)
cd frontend && npm run start           # or E2E_PORT/other port if :3000 is busy
# Then drive the golden path above once, Balanced profile, synthetic inputs only.
```

Paid RAGAS and live Adzuna remain separately unauthorized and are **not** part of this golden.

**LIVE GOLDEN: READY — EXPLICIT AUTHORIZATION REQUIRED.**
