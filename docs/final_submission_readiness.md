# Ask4Mo — Final Submission Readiness (Sprint 4 Release Candidate)

**Ask4Mo — Intelligent Interview Coach.** AI Coach: **Mo**. *Ask More. Be More.*

Concise final release-candidate report. **Product feature freeze is ACTIVE** — Phase 8 added
no features, tools, prompts, sources, or ranking changes. Machine-readable results:
[`evaluations/final/submission_readiness.json`](../evaluations/final/submission_readiness.json).

- **Validated commit:** `5dec4fa` (main, after Phase 7H merged, PR #67) — clean tree.
- **Historical rollback tag:** `sprint4-pre-phase7-baseline` → `2385612` (UNCHANGED, preserved).
- **Proposed final tag (NOT created):** `sprint4-submission-ready` (post-merge only).
- **Branch:** `release/sprint4-final-freeze` (not merged).

## Product

Candidates research a role in one place, guess their gaps, and practise blind. Ask4Mo unifies
**understand → prepare → practise → improve**: Mo (a LangGraph agent) analyses the role and CV,
retrieves evidence-grounded career knowledge, builds a preparation plan, then hands off to a
durable Interview Practice session (question → structured feedback → Deep Dive → final report).

- **Primary product:** Next.js 15 / React 19 + FastAPI (`/api/v1`).
- **Legacy/development interface:** Streamlit (not the reviewer experience).

## Architecture

Candidate → Next.js → FastAPI → **one** bounded LangGraph Agent (Mo) → **6 career tools**
(AnalyzeJobDescription, AnalyzeCandidateGaps, BuildPreparationPlan, GenerateInterviewQuestions,
SearchCareerKnowledge, ResearchCurrentMarket) + **2 HITL action tools**
(ProposePreparationMemory, RequestPracticeHandoff) counted separately (8 registered, verified).

- **Local-first Career Intelligence:** the agent decides *whether* to retrieve; the
  deterministic router decides *which* local evidence (structured + hybrid BM25/vector). No LLM
  selects raw vector records, builds SQL, or picks source files. No generic web crawler.
- **Bounded current-market research:** `ResearchCurrentMarket` → a bounded provider service
  (Adzuna advertised-market signals + SSRF-safe fetch of an explicit public company page).
  Ephemeral, network OFF by default, no candidate data outbound, no permanent KB ingestion.
- **Durable:** long-term preparation memory (user-scoped, explicit approval) and Interview
  Practice (OCC + operation lease + idempotency).
- **Offline:** RAGAS evaluation harness and Feedback Intelligence (human-reviewed; no
  self-modification, no automatic feed into production).
- **Optional:** Langfuse telemetry (metadata-only, OFF by default).

## Model profiles

Fast `openai/gpt-5.6-luna` · **Balanced `openai/gpt-5.6-terra` (default reviewer profile)** ·
Advanced `openai/gpt-5.6-sol`. Overridable via `OPENROUTER_MODEL_*`. Unchanged in Phase 8.

## Knowledge / RAG

8,035 occupations · 23,579 aliases · 111,455 skills · 22,383 tasks · 6,968 knowledge areas ·
20,141 work activities · 1,913 compensation · 2,398 labour-market · 2,275 competencies ·
5 credentials · 14,087 vector passages · 31 sources. All knowledge audits READY.

## Evaluation (deterministic, free)

- **Retrieval:** 81 cases, 74 pass (0.914); evidence coverage 0.886; citation, geography,
  unknown-role and unsupported-geography safety all 1.000; 0 fabricated citations.
- **Agent orchestration:** PASS; cross-user access failures 0.
- **RAGAS deterministic:** ID precision 0.676, recall 0.516; dataset hash `0e0e9298ba77a8bc`;
  paid judge NOT RUN (authorization required; estimate ≈140 judge calls, gpt-4o-mini).
- **External research:** 38/38 (SSRF 1.0, prompt-injection 1.0, provider-failure isolation 1.0).
- **Feedback Intelligence:** 33/33 (offline, non-self-modifying, human approval required).

## Safety / privacy

No candidate CV / background / PII / raw answers / memory / secrets exposed to Langfuse,
Adzuna, company sites, the RAGAS judge, Feedback Intelligence, logs, or reports. Retrieved and
tool content stays untrusted DATA (never instructions). CI secret scan PASS (exact command);
`.env.example` placeholders only; generated data and caches never tracked. FastAPI starts with
all optional systems disabled/unconfigured and no network.

## Testing (regression references)

Python 2137 passed / 3 skipped (RAGAS install guards) / 0 failed · frontend 155 unit +
51 Playwright E2E (StrictMode regression covered) · legacy live component 22 · ruff PASS ·
compileall PASS · Alembic single head `0006` (upgrade/downgrade/re-upgrade clean).

## Reviewer demo

```bash
pip install -e ".[dev,db,speech,live]"
# Backend
AGENT_COACH_ENABLED=true OPENROUTER_API_KEY=... uvicorn src.api.main:app --reload
# Frontend (primary UI)
cd frontend && npm ci && npm run dev
# Deterministic evaluations (no paid API, no Adzuna, no Langfuse)
python scripts/eval_agent.py
python scripts/eval_knowledge_retrieval.py
python scripts/eval_ragas.py
python scripts/eval_external_research.py
python scripts/eval_feedback_intelligence.py
```

The full deterministic reviewer evaluation requires no paid API, Adzuna, or Langfuse.

## Known limitations (honest, non-blocking)

1. Germany occupation-specific compensation is lower-resolution (no Destatis detailed data).
2. Credentials / regulated-profession coverage is limited (5 runtime credentials).
3. Emerging-role taxonomy and industry-specific context remain partial.
4. Some Adzuna capabilities remain unwrapped; live Adzuna not validated in this environment.
5. Live Langfuse not validated; no paid RAGAS judge score claimed.

## Optional integrations

Adzuna: NOT CONFIGURED (no live calls) · Langfuse: DISABLED / NOT CONFIGURED · RAGAS paid:
NOT RUN (authorization required) · Destatis: NOT CONFIGURED / PARTIAL.

## Final freeze status

Release candidate **sprint4-final-rc**. P0 = 0, P1 = 0. Deterministic submission readiness:
**PASS**. Live golden rehearsal: **READY — explicit authorization required, NOT RUN**. The
final tag `sprint4-submission-ready` is **not** created in this phase and must point to the
merged main commit after acceptance. Do not auto-merge; do not run paid/live validation.
