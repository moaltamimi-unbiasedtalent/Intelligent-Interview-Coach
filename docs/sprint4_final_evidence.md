# Sprint 4 — Final Evidence Sheet

Numeric reviewer evidence, captured at the final-submission freeze from merged `main`
(`f890f3d`, containing the P5 merge `bac1bf9`). All values are actual runs — no paid
provider calls, no live Langfuse call.

## Product regression

| Gate | Result |
|---|---|
| Python tests (`pytest -q`) | **1845 passed, 2 skipped** (the 2 skips are the RAGAS installed/absent guards) |
| Frontend unit tests (`npm test`) | **111 passed** |
| Playwright e2e (`npm run e2e`) | **37 passed** |
| Alembic head | **single head `0006_user_feedback`** (fresh upgrade; `0005→0006`; `0006→0005`; upgrade head — all OK) |
| Docker | production image **builds** |
| `ruff check .` | **pass** |
| `python -m compileall -q app.py src scripts tests` | **pass** |
| Secret scan (source) | **clean** |

## A. Deterministic agent orchestration — SCRIPTED / DETERMINISTIC MODEL HARNESS

> These are the graph/tool **contract** metrics under **scripted** routes — **not** live
> model performance. `required_tool_recall = 1.0` means expected-tool execution recall
> under the scripted cases, not a claim the real model always picks the right tool.

`python scripts/eval_agent.py` — **56 cases**, **GATE STATUS: PASS**:

| Metric | Value | Gate |
|---|---|---|
| required_tool_recall | 1.0 | ≥ 0.95 |
| unnecessary_tool_rate | 0.0 | ≤ 0.05 |
| required_retrieval_recall | 1.0 | ≥ 0.95 |
| unnecessary_retrieval_rate | 0.0 | ≤ 0.05 |
| citation_validity | 1.0 | == 1.0 |
| retrieval_sequence_validity | 1.0 | == 1.0 |
| completion_rate | 1.0 | ≥ 0.95 |
| unregistered_tool_attempts | 9 (all rejected) | — |
| hitl_trigger_recall | 1.0 | — |
| cross_user_access_failures | 0 | MUST be 0 |

## B. Live real-model agent evaluation

- `scripts/eval_agent_live.py` — **22 held-out cases**; profiles **Fast / Balanced /
  Advanced**; record/replay sanitised traces; paid opt-in (`--allow-paid` / `RUN_PAID_EVAL=1`).
  Without opt-in it prints "Configuration OK … did NOT run".
- **Recorded paid run (opt-in, Balanced, 2026-09):** completion **1.0**, retrieval-decision
  accuracy **0.909**, unnecessary-retrieval **0.0**, HITL-decision accuracy **0.909**,
  tool-selection accuracy 0.636 (the real model often answers well without invoking the
  discrete JD/gap/plan tools — a model-behaviour signal, not a contract defect);
  ~$0.002/case. These are real-model *decision* rates on a bounded sample, not an
  "accuracy %".

## B2. LLM-as-judge (qualitative quality — advisory)

- `scripts/eval_agent_judge.py` + `src/agent/judge.py` — a third, distinct layer that
  scores recorded live responses against a fixed rubric (intent / tool_choice /
  retrieval_decision / grounding / helpfulness / safety_control, each 0–2; total 0–12).
  Evaluation tooling only — never in the candidate path or CI, never runtime authority.
  See [docs/llm_judge_evaluation.md](llm_judge_evaluation.md).
- **Recorded paid judge run (opt-in, Advanced judge over 21 judgeable Balanced traces,
  2026-09):** average **10.05 / 12** (median 10), pass-rate **0.76** (16/21 at the
  transparent threshold ≥9 · no critical failure · safety>0 · grounding when evidence
  used), **critical failures 0**, **safety failures 0**, grounding failures 2, retrieval
  false-positives 0 / false-negatives 2. Criterion averages: safety **2.0**, retrieval
  1.81, grounding 1.76, intent 1.67, helpfulness 1.57, tool_choice 1.24.
- **Advisory only** — human calibration of every critical failure + the lowest/highest +
  ≥3 borderline cases is required before treating these as evidence (see the judge doc).
  Run artifacts (`evaluations/agent_live/traces/`, `judge_summary.json`) are generated
  locally and git-ignored.

## C. RAGAS (generation quality)

- **35 cases** (`evaluations/ragas/cases.json`); metrics: faithfulness / response
  relevancy / context precision / context recall (not an accuracy %). Optional, paid,
  manual; evaluator must be configured against OpenRouter.
- **PAID LIVE RAGAS BASELINE: NO** (no successful paid baseline is claimed).

## Evaluation case counts

| Suite | Cases |
|---|---|
| Deterministic agent orchestration | 56 |
| Live agent harness | 22 |
| LLM-as-judge (over recorded live traces) | 21 |
| RAGAS | 35 |

## Reproduce

```bash
# Backend
python -m pytest -q
python scripts/eval_agent.py
python scripts/eval_agent_live.py            # prints "did NOT run" without --allow-paid
python scripts/eval_agent_judge.py           # LLM-as-judge: cost preview only without --allow-paid
ruff check .
python -m compileall -q app.py src scripts tests

# Frontend
cd frontend && npm ci && npm run lint && npm test && npm run typecheck && npm run build && npm run e2e

# Migrations (single head 0006)
DATABASE_URL=sqlite:///./_m.db alembic upgrade head
```
