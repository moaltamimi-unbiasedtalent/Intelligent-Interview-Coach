# RAGAS Evaluation Report (Phase 7E)

Reproducible RAG-quality evaluation for Ask4Mo. It has **two clearly separated modes** and a
hard paid-call guard: a FREE deterministic layer (default, CI-safe, no LLM) and an OPT-IN
LLM-judged layer (RAGAS, requires explicit `--allow-paid`).

Reproduce:

```bash
python scripts/eval_ragas.py                     # FREE deterministic RAG metrics (default)
python scripts/eval_ragas.py --mode judge --estimate-only          # cost estimate, no calls
python scripts/eval_ragas.py --mode judge --subset reviewer --allow-paid   # OPT-IN paid judge
python scripts/audit_ragas_evaluation.py         # harness readiness audit
```

## Deterministic results (FREE — no LLM)

Two complementary suites. **Neither makes a paid call.**

### A. ID-based context precision / recall (Phase 7E)

Computed from the real deterministic retrieval over the public RAGAS dataset
(`evaluations/ragas/cases.json`), scoring retrieved-evidence **source ids** against each case's
expected source family. Cases with no defensible reference family (safety / insufficient-by-
design) are `NOT_APPLICABLE`, never 0 (§15). Baseline `evaluations/ragas/deterministic_baseline.json`:

| Metric | Value | Applicable cases |
|---|--:|--:|
| ID context precision (mean) | **0.676** | 19 |
| ID context recall (mean) | **0.516** | 31 |
| NOT_APPLICABLE | — | 4 |

- dataset cases: 35 · dataset hash: `0e0e9298ba77a8bc` · git: `d892acc` · RAGAS: 2.15
- Granularity is the stable **source id / source family** (never a mutable vector rank), so
  results reproduce across runs. Family overlap (ESCO serves role/skills/competency) makes
  precision a *source-family membership* signal — labelled as such, not exact-passage precision.

### B. Ask4Mo deterministic retrieval baseline (Phase 7C, authoritative — unchanged)

From `scripts/eval_knowledge_retrieval.py` over 81 held-out cases (the authoritative safety
suite; RAGAS supplements, never replaces it, §34):

| Metric | Value |
|---|--:|
| retrieval cases | 81 |
| pass rate | 0.914 |
| evidence coverage | 0.886 |
| citation completeness | **1.000** |
| geography correctness | **1.000** |
| unknown-role safety | **1.000** |
| unsupported-geography safety | **1.000** |
| no-fabricated-citation | **1.000** |

Safety metrics are deterministic hard gates and are **not** delegated to an LLM judge (§46/§59).

## LLM-judged results (RAGAS)

**NOT RUN — PAID EVALUATION NOT AUTHORIZED.**

The harness is complete and proven with mocks, but no paid judge run was executed in this phase
(§26/§67). To run one: `python scripts/eval_ragas.py --mode judge --subset reviewer --allow-paid`
(needs `RAGAS_EVAL_API_KEY` + a chat credential). Estimate (from `--estimate-only`): 24 fixed
subset cases × 4 metrics ≈ 96 judge calls; judge model from `RAGAS_EVAL_MODEL` (default
`gpt-4o-mini`); cost **unknown** (provider pricing not queried — never fabricated).

Metrics available when authorized (per-metric, no single magic score, §44/§45):

| Metric | What it means | What it does NOT prove |
|---|---|---|
| Faithfulness | answer claims are supported by the supplied retrieved contexts | source correctness / freshness / global truth (§52) |
| Response Relevancy | answer addresses the user's question | faithfulness / truth / citation accuracy (§53) |
| Context Precision | relevant retrieved evidence is ranked appropriately | that all needed evidence was retrieved (§54) |
| Context Recall | retrieved contexts cover the reference (referenced cases only) | — |

## Paid-call safety

- Default `python scripts/eval_ragas.py` runs deterministic only — **no paid calls**.
- Judge mode requires explicit `--allow-paid` (or legacy `--live`); `--mode judge` alone prints
  NOT RUN. `--estimate-only` makes no model call. CI never passes `--allow-paid` (§65).

## Privacy

The evaluation dataset is **synthetic / public / curated** — no real CV, candidate name/email/
phone, memory, or production interview answers ever reach a judge (§37). Results never store the
API key (verified by tests). No chain-of-thought is requested or persisted (§39).

## Limitations

- The judge model may share a provider family with production; this is **not** independent human
  evaluation (§8). ID precision is source-family-level, not exact-passage. No paid baseline has
  been run yet — the numbers above are the deterministic layer only.

See [ragas_evaluation.md](ragas_evaluation.md) for design, and `scripts/eval_agent.py` /
`scripts/eval_knowledge_retrieval.py` for the separate agent-orchestration and deterministic
retrieval evaluators.
