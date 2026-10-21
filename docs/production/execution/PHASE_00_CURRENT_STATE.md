# Phase 00: Current State (verified baseline)

**Status:** verified 2026-10-21 on `main` `59f1fda` (PR #211 merged; the approved planning baseline is `docs/production/`). This document records facts found by inspection; it does not repeat the roadmap. Nothing was changed in the application.

## 1. Baseline

| Item | Finding |
|---|---|
| Branch and commit | `main` at `59f1fda` (merge of PR #211). The Phase 00 work is on `docs/production-phase-00` |
| CI on `main` | All reported check runs successful at the time of inspection: Python tests and checks, four test shards, evaluators and guards, evaluation extras, static guards, frontend, legacy live component |
| Backend tests | 5,134 collected (`pytest --collect-only`) |
| Frontend tests | 110 vitest files and 57 Playwright spec files in the repository |
| Alembic head | `0039_speech_governance` (single head, 40 revision files) |
| Working tree | Clean apart from untracked frontend image assets that belong to earlier work and are not part of this programme |
| Planning documents | `docs/production/` (roadmap V2.2, scope, train, acceptance matrix, decisions, multilingual qualification, traceability, dashboard, reconciliation JSON, owner requirements source of truth) |
| Reconciliation | 452 traced rows; 394 historical issues preserved; R1.0 must-fix 88, must-verify 74, 0 unmapped (`scripts/production/reconcile_issues.py check` passes) |

## 2. Architecture as built (relevant to the programme)

- **Product:** Next.js 15 / React 19 frontend over a FastAPI backend (`/api/v1`) on SQLAlchemy and Alembic; LangGraph agent (nodes: initialise, agent, tools, human review, finalize) with an allow-listed 11-tool registry and three bounded specialists; Career Intelligence RAG (structured SQLite stores, Chroma vector index, BM25 and RRF hybrid, grounding policy layer); Interview Practice services; governed knowledge lifecycle; Admin control plane with 44 permissions and an English-only UI; DB-backed job queue with a separate worker (`python -m src.jobs.worker`).
- **Key modules for Phase 01 to 03:** `src/security.py` (559 lines, heuristic `detect_injection`); `src/copilot/security/` (injection, rag_guard, output_guard, grounding_policy); `src/copilot/models.py` (`RetrievalResult` has no risk score); `src/agent/registry.py` (94 lines; `ToolRegistry.validate_and_run` validates arguments but has no goal or permission re-authorization); `src/agent/policies.py` (134 lines; hand-written `SYSTEM_PROMPT`); `src/prompts.py` (733 lines of prompt literals) with `src/prompt_registry.py`; `src/config_versions.py` (`production_versions()` returns hash-based `prompt_version`); `src/copilot/embeddings.py` (`build_embedder`: `auto` resolves to the lexical `LocalHashEmbedder` unless a dedicated embedding key is set); `src/agent/events.py` (54 lines) and `src/application/agent_service.py` (744 lines; synchronous run API, no SSE).
- **Admin:** 20 destinations in `frontend/lib/admin/capabilities.ts` rendered flat by `frontend/components/admin/AdminShell.tsx`; platform-wide Review and Diagnostics currently lives at `/review` and is shown in the Candidate "More" menu to admin-permitted users through `INTERNAL_NAV` in `frontend/components/layout/nav-items.ts` (UI only; backend permissions are independent). 15 admin route modules (`admin*.py`) among the modules under `src/api/routes/`.
- **Knowledge:** curated corpus (14,087 chunks and structured stores) plus the governed lifecycle (register, scan, parse, review, approve, index, activate); PR #210 added a read-only curated list. Data paths anchor to one data root (`COPILOT_DATA_DIR`).

## 3. Verified gaps that shape the plan

| # | Gap (verified by inspection) | Consequence | Package |
|---|---|---|---|
| G1 | `deploy/docker-compose.staging.yml` defines `db`, `migrate`, `api`, `web`, `caddy` only: **no job worker service, no knowledge/index volume, no ClamAV service**, although `.env.staging.example` references `CLAMAV_HOST=clamav` and governed knowledge needs the worker | A hosted staging stack as written would reproduce the empty or non-indexing Knowledge Sources the owner keeps encountering | 02A, 02C, 05A |
| G2 | `ClamAvScanner` in `src/documents/file_security.py` is a documented stub (live-unvalidated) | Real malware scanning does not exist yet; the fake scanner is development-only | 02C |
| G3 | `DEFAULT_EMBEDDING_PROVIDER = "auto"` resolves to `LocalHashEmbedder` without a dedicated key; the code comment states OpenRouter does not serve OpenAI's embeddings endpoint | Silent lexical retrieval is possible in production; the earlier live RAGAS run's zero relevancy score may relate to the embedding path (hypothesis, not established: the ledger rows inspected were chat requests) | 02B, 07B |
| G4 | `.env.staging.example` pins `openai/gpt-5.6-*` model slugs, but the demonstration pricing and live runs used `openai/gpt-5.4`, `gpt-5.4-mini`, `gpt-5.5` | Model identity and cost assumptions must be reconciled before hosted budgets are set | 05C, OD-BUDGET |
| G5 | The demonstration spend guard (`src/demo_live`) is a separate ledger for the capstone; there is no production AI budget governor | No hard AI spend cap exists for beta users | 05C |
| G6 | Russian is still an exposed eighth locale (`APP_LOCALES` includes `ru`) | Contradicts the owner decision | 06A |
| G7 | `src/agent/events.py` has no SSE projection; `agent_service` is synchronous | REVIEW-05 is a net-new capability | 04C |
| G8 | `tests/` contain no consolidated UI plus API proof that deferred features are unreachable | REQ-DEFER-01 needs a new suite | 07A |
| G9 | The 31-entry curated manifest is US-centred (O*NET, BLS) while the R1.0 markets are EU | Market-evidence scope needs an owner decision (OD-US-CONTENT) before enabled-feature claims | 02D, 00B |
| G10 | No invitation-only registration control exists | REQ-BETA-01 is net-new | 04E |

## 4. Outstanding operational dependencies

No hosted environment, domain, managed PostgreSQL, object or vector storage decision, embedding credential, malware scanner deployment, monitoring or alerting service, external email (Brevo) or OIDC live verification, production AI budget, named reviewers, native reviewers or legal qualifiers exist or are decided. See `TECHNICAL_DECISIONS.md` and `docs/production/OWNER_DECISION_REGISTER.md`.

## 5. CI finding on PR #212 (dependency drift, not an authorization defect)

PR #212 was red in the four Python test shards and in "Python evaluators and guards". Root cause, reproduced locally with a fresh install of the latest allowed dependencies (starlette 1.9.0, fastapi 0.156.8, against the starlette 1.3.1 and fastapi 0.141.1 of the earlier green runs):

- **Not a real authorization defect.** With separate clients per user (like two browsers) the identity evaluator's checks return 404, 404, 200 on the new dependencies as well. The same code on `main` passes with the old dependencies and fails with the new ones, so the Phase 00 documents did not cause it.
- **A test-harness session-isolation artefact.** The evaluator, and about sixty tests, log several users in through one `TestClient` and pass `cookies={"ask4mo_session": token}` per request to act as one user. httpx sends the jar cookie and the per-request cookie in one `Cookie` header; a minimal Starlette app with no Ask4Mo code shows the order flipped between starlette 1.3 (`jar; per-request`) and 1.9 (`per-request; jar`), and the server keeps the last value, so on a fresh install the most recent login silently overrode the intended user and the cross-user checks measured the wrong identity (0 of 3).
- **Fix without weakening anything:** a harness wrapper in `tests/_client_compat.py` (installed on import of the `tests` package) makes the per-request cookie authoritative on every version, with regression tests (`tests/test_testclient_cookie_precedence.py`). The evaluator and the application are unchanged, the three assertions (404, 404, 200) are unchanged, and the evaluator passes with both the old and the new dependency sets.

## 6. What was not done in Phase 00

No application code, no migration, no provider call, no deployment, no payment activation, no rewriting of historical evidence, no provisioning of any paid service.
