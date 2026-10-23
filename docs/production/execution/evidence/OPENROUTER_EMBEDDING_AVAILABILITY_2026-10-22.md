# OpenRouter embedding availability check (2026-10-22)

Purpose: verify, before any implementation, which embedding models the owner's OpenRouter account can reach and whether OpenRouter's embeddings endpoint is architecture-compatible, as the owner's direction requires ("do not assume that a chat model is available through an embeddings endpoint"). **This is an availability check only: no embedding was generated, no token was consumed, and nothing here is a quality result.**

## How it was checked
Two free, read-only metadata calls with the configured key, which was read inside a single process and never printed or written: `GET /api/v1/key` (account limits; the figures are deliberately not recorded in the repository) and the model listings `GET /api/v1/models` and `GET /api/v1/models?output_modalities=embeddings` (also `GET /api/v1/embeddings/models`). No generation endpoint was called.

## Findings
- The key is valid and not on the free tier; it has a finite credit limit with headroom, so a configurable ceiling is needed (the 05C budget governor), never an assumption of unlimited credit.
- The general chat listing contains 468 models and **no** embedding models: embedding models are listed only through the embeddings listing, which confirms they are a separate endpoint.
- OpenRouter exposes an **embeddings endpoint and 39 embedding models** to this account, including **`openai/text-embedding-3-large` and `openai/text-embedding-3-small`** (and `:batch` variants), so the owner's OpenAI comparison can run through OpenRouter with no direct OpenAI dependency and no `OPENAI_API_KEY`.

## Candidate models (public listing data; price per million prompt tokens computed from the listed per-token price; context in tokens)
| Model | Context | Price per 1M tokens (USD) | Notes |
|---|---|---|---|
| openai/text-embedding-3-large | 8192 | 0.13 | owner-requested comparison; native 3072 dimensions (truncation supported by the API) |
| openai/text-embedding-3-small | 8192 | 0.02 | owner-requested baseline; native 1536 dimensions |
| baai/bge-m3 | 8194 | 0.01 | multilingual, long context |
| intfloat/multilingual-e5-large | 512 | 0.01 | multilingual, short context |
| qwen/qwen3-embedding-8b | 40960 | 0.01 | multilingual |
| qwen/qwen3-embedding-4b | 32768 | 0.02 | multilingual |
| voyageai/voyage-4 / voyage-4-large / voyage-4-lite | 32000 | 0.06 / 0.12 / 0.02 | general text |
| google/gemini-embedding-001 | 20000 | 0.15 | multilingual |
| mistralai/mistral-embed-2312 | 8192 | 0.10 | |
| nvidia/nemotron-3-embed-1b:free and other `:free` models | 32768 | 0 | free tier, rate-limited, suitable only for development |

## Not verified by this check (and therefore open)
Embedding dimensions actually returned per model, per-model rate limits and throttling, multilingual retrieval quality across the seven languages, cross-language retrieval, recall@k and nDCG@k, grounded-answer and citation quality, latency and throughput, determinism and reproducibility, and the end-to-end cost of a real index build. The listed prices imply a very small cost for the planned work (the curated corpus is about 5.3 million tokens, about USD 0.02 at the smallest listed paid price, USD 0.11 at text-embedding-3-small and USD 0.69 at text-embedding-3-large), but that is an estimate, not a measurement.

## Consequence for the plan
OD-EMBED stays PROVISIONAL: benchmark through OpenRouter using the existing provider abstraction, with versioned indexes and manifests (02B), under the 05C budget governor, and choose by measured, reproducible metrics. The work item (an OpenRouter embedding adapter plus the benchmark run) is scheduled in `../WAVE3_EXECUTION_PLAN.md` section 9. No second external provider is needed: every candidate above is reachable through OpenRouter.
