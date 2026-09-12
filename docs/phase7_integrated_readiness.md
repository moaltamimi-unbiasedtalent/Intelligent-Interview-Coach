# Phase 7 — Integrated Readiness (7H Quality Gate)

Concise reviewer-oriented summary of the Phase 7 system and its validation. This is a
**quality gate**, not a new capability: Phase 7H added no product features (only one
documentation defect fix). Machine-readable results:
[`evaluations/phase7/integrated_quality_report.json`](../evaluations/phase7/integrated_quality_report.json).

- **Validated commit:** `4dc3432` (main, after Phase 7G merged, PR #66) — clean tree.
- **Protected rollback tag:** `sprint4-pre-phase7-baseline` → `2385612` (UNCHANGED).
- **Branch:** `feature/phase7-integrated-quality-gate` (not merged).

## What Phase 7 added

| Phase | Delivered |
|---|---|
| 7A / 7A.1 | Knowledge foundation; gap closure, data governance, Adzuna readiness |
| 7B | Multi-source normalization (governed normalized layer) |
| 7C | Runtime knowledge integration + Agentic RAG hardening |
| 7D | Privacy-safe **optional** Langfuse observability (OFF by default) |
| 7E | RAGAS evaluation harness + reproducible deterministic baseline |
| 7F | Bounded `ResearchCurrentMarket` external current-market tool (6th agent tool) |
| 7G | Offline Feedback Intelligence agent (admin/engineering, human-reviewed) |

## Architecture (invariants verified)

- **One candidate Agent**, LangGraph, bounded step budget — unchanged topology except the
  intentional 6th tool registration.
- **6 candidate tools** (verified from the registry): AnalyzeJobDescription,
  AnalyzeCandidateGaps, BuildPreparationPlan, GenerateInterviewQuestions,
  SearchCareerKnowledge, ResearchCurrentMarket — plus 2 HITL action tools
  (ProposePreparationMemory, RequestPracticeHandoff) counted separately (8 registered).
- **No generic web/search tool.** **No Feedback Intelligence tool** exposed to candidates.
- **Career Intelligence** remains local, governed RAG: the agent decides *whether* to
  retrieve; the deterministic Sprint 3 router decides *which* local evidence. No LLM
  selects raw vector records, constructs SQL, or picks source files.
- **External research** is ephemeral (network OFF by default, no permanent KB ingestion,
  SSRF- and injection-safe, no candidate data outbound).
- **Feedback Intelligence** is offline, not part of the candidate graph, and has no
  git/shell/network/prompt/KB/config write capability; human approval never executes.

## Quality metrics

- **Python:** 2137 passed, 3 skipped (RAGAS install guards), 0 failed.
- **Frontend (Next.js):** lint ✓, typecheck ✓, 155 vitest tests ✓, build ✓, 51 Playwright E2E ✓
  (StrictMode mounted-ref regression covered). Legacy live component: 22 tests ✓, typecheck ✓, build ✓.
- **Agent orchestration eval:** PASS (cross-user access failures = 0).
- **Retrieval:** 81 cases, 74 passed (0.914); evidence coverage 0.886; citation, geography,
  unknown-role and unsupported-geography safety all 1.000.
- **RAGAS (deterministic, free):** ID precision 0.676, recall 0.516; dataset hash
  `0e0e9298ba77a8bc`; reviewed baseline built from a clean tree; paid judge NOT RUN.
- **External research:** 38/38 (SSRF 1.0, prompt-injection 1.0, provider-failure isolation 1.0).
- **Feedback Intelligence:** 33/33; offline, non-self-modifying, human approval required.
- **Runtime knowledge:** 8,035 occupations · 23,579 aliases · 111,455 skills · 22,383 tasks ·
  6,968 knowledge areas · 20,141 work activities · 1,913 compensation · 2,398 labour-market ·
  2,275 competencies · 5 credentials · 14,087 vector passages · 31 sources.

## Security / privacy

- CI secret scan (exact command) PASS; `.env.example` placeholders only; generated data and
  caches gitignored (never tracked).
- No candidate CV / background / PII / raw answers / memory / secrets exposed to Langfuse,
  Adzuna, company sites, the RAGAS judge, Feedback Intelligence, logs, or reports.
- FastAPI starts with every optional system disabled/unconfigured and no network; no heavy
  optional module (RAGAS/Langfuse/datasets) is imported at runtime load.

## Evaluation reproducibility

- Deterministic retrieval/coverage evaluations are the primary CI gate; RAGAS deterministic
  ID metrics are reproducible (fixed dataset hash, clean-tree provenance). No paid or live
  call runs without an explicit `--allow-paid` flag; credentials alone are never treated as
  authorization.

## Known limitations (non-blocking)

1. Germany occupation-specific compensation is lower-resolution (no Destatis detailed data).
2. Credentials / regulated-profession coverage is limited (5 runtime credentials).
3. Emerging-role taxonomy and industry-specific context remain partial (tracked gaps).
4. Some current-market provider capabilities remain unwrapped.
5. No paid RAGAS baseline yet; live Langfuse and live Adzuna are unverified in this
   environment (optional, disabled/not configured).
6. `gen_product_coverage_cases` sampling makes some informational coverage sub-metrics vary
   run-to-run (command exit stays 0; non-gating).

## How to reproduce

```bash
# Python gates
python -m pytest -q
python scripts/eval_agent.py
python scripts/eval_knowledge_retrieval.py
python scripts/eval_ragas.py                 # deterministic; paid judge needs --allow-paid
python scripts/eval_external_research.py && python scripts/audit_external_research.py
python scripts/eval_feedback_intelligence.py && python scripts/audit_feedback_intelligence.py
python scripts/audit_observability.py
ruff check . && python -m compileall -q app.py src scripts tests

# Frontend gates (:3000 may be held by an unrelated container -> set E2E_PORT)
cd frontend && npm ci && npm run lint && npm test && npm run typecheck && npm run build
CI=true E2E_PORT=3999 npm run e2e
```

## What remains before final freeze (Phase 8)

- Phase 8 may optionally run **one** controlled paid RAGAS baseline and the live golden
  rehearsal — only with explicit authorization. No benchmark-tuning loop.
- Optional live connectivity validation (Langfuse, Adzuna) if credentials are provided.
- This branch is **merge-ready** but must be reviewed and merged manually; Phase 7H does
  not create the final freeze tag.

**Phase 7 freeze candidate: YES. Ready for Phase 8: YES (after review/merge).**
