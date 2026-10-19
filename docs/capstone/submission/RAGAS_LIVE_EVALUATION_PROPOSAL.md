# Live RAGAS Evaluation: Proposal for Owner Approval (NOTHING HAS BEEN RUN)

Prepared 2026-10-19 for the review on 2026-10-20. The owner asked for live RAGAS; this treats that as permission to **prepare**, not to spend. **No live RAGAS call was made.** The free deterministic RAGAS evaluation and the judge **estimate-only** mode were run (no model calls). A live run needs the explicit approval of a spending ceiling below and three prerequisites that engineering cannot supply on its own.

## 1. Free results already available

| Run | Result |
|---|---|
| `python scripts/eval_ragas.py` against the review data root (curated stores, 4 synthetic governed sources) | 35 cases, dataset hash `0e0e9298ba77a8bc`; ID context precision mean **0.6591** (21 applicable); ID context recall mean **0.5484** (31 applicable); 4 not applicable. Retrieval-identity metrics, not LLM judgement |
| Same command in a clean checkout (no stores) | recall 0.0: the evaluation only means something against built stores |
| `eval_ragas.py --mode judge --subset reviewer --estimate-only` | 24 judge cases, about 96 judge calls ("about 4 per case"), judge model default `gpt-4o-mini`, **cost unknown** (pricing not queried) |
| The committed baseline (`evaluations/ragas/deterministic_baseline.json`, 2026-09-12) | 0.6757 precision (19 applicable) and 0.5161 recall; **unchanged and not overwritten**. The current numbers differ because the code and data moved; this is a measurement, not a regression claim |

## 2. Readiness check

| Item | Status |
|---|---|
| `ragas` package | installed, version 0.2.15 |
| Evaluator credentials (`RAGAS_EVAL_API_KEY`) | **NOT CONFIGURED** (not in the environment or the project `.env`); `--allow-chat-fallback` would reuse the production chat key and is **not recommended** |
| Evaluator endpoint (`RAGAS_EVAL_BASE_URL`) | not set; documentation says `https://openrouter.ai/api/v1` |
| Evaluator model | default `gpt-4o-mini`; the OpenRouter slug (`openai/gpt-4o-mini`) is **not priced in the P10E pricing snapshot** |
| Evaluator embedding model | default `text-embedding-3-small` through an OpenAI-compatible **embeddings** endpoint; whether the chosen endpoint serves embeddings is **unverified** (ResponseRelevancy needs them) |
| Career Intelligence answer model | Balanced `openai/gpt-5.4` (from `OPENROUTER_MODEL_BALANCED`) for answer generation |
| Dataset | `evaluations/ragas/cases.json`: 35 public held-out synthetic cases with references; the reviewer subset is a fixed 24; no candidate data |
| Results directory | `evaluations/ragas/runs/` is git-ignored and writable; a run writes a unique directory |
| **Budget enforcement** | **GAP: the RAGAS runner has no call cap or spend ceiling of its own (estimate only). The P10E guard admits chat completions only and refuses the embeddings endpoint, so it cannot wrap a RAGAS run as is.** A bounded run needs (a) a NEW ledger with its own genesis and approval record (the P10E ledger must not be reused or reset) and (b) a small code change to price and admit the embeddings endpoint and the evaluator model. Both need the owner's approval |

## 3. Proposed controlled evaluation (for approval)

- **Cases (2 of the fixed reviewer subset):** `role_us_data_analyst` ("What does a data analyst do day to day?") and `role_uk_operations_manager` ("What are the main responsibilities of an operations manager?"); both have references, so all four metrics apply.
- **Expected requests:** answer generation 2 chat calls; judge calls about 8 by the estimator, realistically up to about 30 (context-precision judges each retrieved context); embeddings about 4 to 6; **hard cap 60 requests in total**, timeout 60 s, 1 retry maximum, concurrency 2, output cap 4,096 tokens, input cap 20,000 tokens.
- **Models:** answers `openai/gpt-5.4` (Balanced); evaluator `openai/gpt-4o-mini`; embeddings `text-embedding-3-small` **only if the endpoint is verified compatible** (the first request is a one-call compatibility probe inside the same cap).
- **Provider endpoint:** OpenRouter (`https://openrouter.ai/api/v1`) with a **dedicated evaluator key** supplied by the owner in the process environment (never in chat, files or the repository).
- **Estimated spending:** expected **under USD 0.15** (answers about USD 0.06 at the registry price; judge and embeddings a few cents). **Proposed enforced ceiling: USD 0.50 cumulative** on a new, separate ledger. Not a P10E amendment; the P10E balance (15 calls, about USD 7.89) is not authorization for this run.
- **Abort conditions:** authentication failure; embeddings endpoint incompatible; budget or request cap reached; any request beyond the planned calls; non-finite evaluator score; missing contexts for a case; any uncontrolled retry.
- **Results:** a unique run directory with commit SHA, timestamp, dataset identity and hash, model identifiers, per-metric scores, execution status, valid-score count, call count and actual cost where attributable; shown through the existing CLI output (the Next.js Admin has **no** live RAGAS dashboard and none is built; the existing offline diagnostics must not be presented as live RAGAS). Scores are never described as human-verified.
- **After two cases:** recommend whether a larger run is worthwhile; the full 24-case reviewer subset (about 96 or more judge calls) is **not** run automatically.

## 4. What the owner must decide

1. Approve or amend the USD 0.50 / 60-request ceiling on a new separate ledger (new genesis).
2. Approve the small code change to admit and price the embeddings endpoint and the evaluator model under that ledger.
3. Provide a dedicated `RAGAS_EVAL_API_KEY` (and confirm the embeddings endpoint) in the process environment.

Without all three, the review should present the **free deterministic RAGAS result** and state: **RAGAS LIVE: NOT RUN, credential and guard dependency**.
