# Live Capstone Demonstration: Operator Guide

Controlled academic demonstration, **not production**. Synthetic data only. Prepared 2026-10-20 on branch `feat/live-demo-budget-guard`. Spend figures are our own conservative ledger estimates, never provider charges.

## 1. What is live, and what is not

| Capability | State |
|---|---|
| Mo agent (real LangGraph agent, real OpenRouter model, tool call, retrieval, citations) | LIVE, ledger-controlled |
| Interview practice (question generation, answer evaluation) | LIVE, ledger-controlled |
| RAGAS (LLM-judged) | LIVE for a bounded 2-case run; result PARTIAL (section 8) |
| Governed knowledge lifecycle (register, scan, review, approve, index, activate) | REAL worker; the malware scanner is the development-only FAKE (a simulation) |
| Billing, Stripe, speech providers, history and model-profile gating, scheduler | DISABLED (all code gates `False`) |
| Coverage gate (386/412 vs 392 required) | FAILS, unchanged. AC-24 PARTIAL. Human-qualified coverage 0 of 412 |

## 2. Spend control (src/demo_live)

A separate ledger (never the P10E ledger) outside the repo (`/tmp/ask4mo_live_demo/ledger`). Approved cap EUR 10.00; operating stop EUR 8.00; allocations agent 2.00, interview 2.00, RAGAS 3.00, troubleshooting 1.00, reserve 2.00. Every provider request (API, worker, RAGAS, retries, embeddings) passes one httpx chokepoint: atomic worst-case reservation before dispatch, settlement from usage (larger of our estimate and the provider's figure), unknown outcomes held at worst case, kill switch, fail closed on missing config/pricing/ledger, refused in CI, offline mode refuses every external host even if a key exists. USD is counted 1:1 as EUR. Verified by 26 mocked-provider tests (`tests/test_demo_live_budget.py`) including simulated exhaustion and concurrency.

Visible indicator: `http://127.0.0.1:8030` (with a KILL button). CLI: `python scripts/demo/live_budget.py status|kill|resume|recent|plan`.

## 3. Startup

```bash
scripts/demo/live_env.sh start live      # or: offline (default; never contacts a provider)
scripts/demo/live_env.sh status
scripts/demo/live_env.sh stop
```

URLs: app http://localhost:3015, API http://127.0.0.1:8020, spend indicator http://127.0.0.1:8030. Processes run from a clean git worktree (`/tmp/ask4mo_live_wt`) with a separate database `/tmp/ask4mo_live_demo/app.db` (Alembic head `0039_speech_governance`) and data root `/tmp/ask4mo_live_demo/data` (copy of the curated stores; developer stores untouched). `live` injects the OpenRouter key from the owner's main-checkout `.env` into child processes only; it is never printed or written.

## 4. Accounts

Synthetic accounts `admin.live@example.invalid` and `candidate.live@example.invalid`. Passwords were generated randomly and are in `/tmp/ask4mo_live_demo/logins.txt` (mode 600, outside the repo); read the file locally, nobody else needs the values. The admin was promoted with `scripts/bootstrap_admin.py` after a dry-run and the owner's explicit confirmation (`scripts/demo/live_env.sh promote [--yes]`). Disclosure: the earlier review environment admin was promoted by direct SQL; this one was not.

## 5. Knowledge

Curated corpus: 14,087 chunks (O*NET, ESCO and others) in the copied stores. Governed: four SYNTHETIC sources labelled `[SYNTHETIC CAPSTONE DEMO]` registered through the real Admin lifecycle (`scripts/demo/live_env.sh seed`); readiness `ready`, retrieval test `evidence_found`. Governed and curated are different layers; the governed sources are demo fixtures, not authoritative career data.

## 6. Admin walkthrough

Log in as admin at `/admin`. 69 Admin read endpoints answered 200 for the admin; the same routes return 403 for the candidate; no Admin route exposes candidate conversations, documents, answers or memory. Suggested order: Command Center, Users, Workspaces, Support, Plans, Billing (mock, disabled), Integrations, AI and Models, Knowledge (sources, readiness, retrieval test), Jobs, Privacy, Legal, Reports, Security and Audit, Configuration and flags, then the spend indicator.

## 7. Candidate walkthrough (live)

Log in as the candidate, open Prepare (Mo), ask a role question with a target role, observe tool use, retrieval and citations; open Practice, start a short behavioural interview, answer, read the evaluation (practice guidance, not a hiring decision). Verified in this session through the API: Mo run completed (3 model calls, retrieval used, 5 citations to the governed sources), interview question generated and an answer evaluated by the live model. The UI path was not clicked through end to end by the operator here.

## 8. RAGAS (live, bounded)

`scripts/demo/run_ragas.sh deterministic | estimate | live [LIMIT]`. Free deterministic result: 35 cases, dataset hash `0e0e9298ba77a8bc`, ID precision 0.6591, ID recall 0.5484 (retrieval identity, not LLM judgement).

Live attempts (cases `role_us_data_analyst`, `role_uk_operations_manager`; evaluator `openai/gpt-4o-mini`, embeddings `openai/text-embedding-3-small` via OpenRouter, the owner's one key, code commit `1fcead8`):

1. First attempt: PARTIAL 2/8. Cause: a defect in my guard (blocking concurrency wait froze the async event loop). Fixed and regression-tested; the attempt is kept as evidence and its cost counted.
2. Second attempt: **PARTIAL, 7/8 valid scores (87.5%)**: faithfulness 0.2059, response relevancy 0.0, context precision 0.5, context recall 0.0.

These are low and incomplete. They are valid numbers from a tiny sample, not proof of quality and not human-rated; response relevancy 0.0 and recall 0.0 should be investigated (references, retrieval and the embedding path) before any claim. No more cases were run; the 24-case subset is never automatic. Results folders: `/tmp/ask4mo_live_demo/ragas_runs/` (git-ignored; copy `results.json`, `run_config.json`, `summary.md` if needed).

## 9. Fallback and shutdown

Fallback: `scripts/demo_offline_journey.py` and `DEMO_TRANSCRIPT_OFFLINE.md` (no provider). Engage the kill switch from the indicator or CLI at any doubt. Shutdown: `scripts/demo/live_env.sh stop` (exact PIDs).

## 10. Limitations

Estimates not charges (check the provider dashboard; unattributed usage, if any, is reported separately); small samples; fake scanner is a simulation; evaluator and chat share one key; the interview/Mo profiles used are Balanced/Fast per the registry; Advanced (`gpt-5.5`) was not exercised.

## 11. Reviewer sequences

Short (5 min): indicator, candidate Mo question with citations, one interview answer and evaluation, admin Knowledge readiness, RAGAS summary with the PARTIAL caveat. Extended (15 min): add Admin walkthrough, audit trail, privacy boundary (candidate gets 403 on Admin routes), pause/flags, deterministic RAGAS, and the spend ledger `recent`.
