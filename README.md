# Ask4Mo

**Intelligent Interview Coach.** *Ask More. Be More.*

Ask4Mo helps a candidate understand what a specific job requires, prepare with evidence, practise realistic interviews and improve through structured feedback. **Mo**, the AI coach, is a bounded **LangGraph agent** that chooses controlled tools, retrieves career evidence only when it is useful, pauses for human approval where it matters, and hands the approved preparation into a durable **Interview Practice** session. Capstone framing: **Case 2 (AI agent for task automation)** with **Case 1 (RAG-powered knowledge assistance)** as the supporting capability. Submission material: [`docs/capstone/submission/`](docs/capstone/submission/). Capstone showcase entry (optional): not published; its link will be added here if it is.

## Problem and solution

**Situation:** candidates need preparation that reflects the role and their own experience. **Complication:** generic AI preparation lacks role context, grounded facts and comparable feedback, and a model can invent statistics and sources. **Resolution:** Ask4Mo organises preparation, practice and feedback around **one job at a time**: an agent with an allow-listed tool registry, retrieval-augmented answers whose citations map only to retrieved evidence, human approval for sensitive actions, and rubric-based practice feedback. Target users are candidates preparing for professional, specialist and leadership interviews (not recruiters; Ask4Mo is not ATS or HR software, and interview scores are practice feedback, not a hiring decision). Product claims stay within [docs/product/PRODUCT_CLAIMS.md](docs/product/PRODUCT_CLAIMS.md).

```
Opportunity  ->  Prepare (Mo)  ->  Knowledge retrieval  ->  Practice  ->  Feedback  ->  Progress / History
```

## Architecture

```
Next.js 15 / React 19 / TypeScript frontend  (candidate UI, public site, English-only /admin console)
  -> FastAPI /api/v1   (owner-scoped routes, safe error envelope, request ids)
    -> Application layer (src/application)
      -> Mo: bounded LangGraph agent (allow-listed tools, three bounded specialists, agentic RAG, approved memory, human-in-the-loop)
      -> Interview Practice (durable sessions; LLM-backed question and evaluation services)
      -> Documents and evidence, Opportunities, Workspaces, Account lifecycle
    -> SQLAlchemy + Alembic (single head 0039_speech_governance) · knowledge stores + Chroma vector index
    -> Provider adapters (LLM via OpenRouter, email, speech, research): optional, never contacted by tests
```

Diagrams (agent graph, tool registry, RAG pipeline, trust boundaries): [docs/capstone/submission/ARCHITECTURE_DIAGRAMS.md](docs/capstone/submission/ARCHITECTURE_DIAGRAMS.md). The authoritative architecture description is [docs/sprint4_architecture.md](docs/sprint4_architecture.md).

- **LLM integration:** OpenRouter. Career Intelligence and the agent use LangChain's OpenAI-compatible model; Interview Practice uses a direct HTTPX client. One registry maps the Fast, Balanced and Advanced profiles to model slugs; typed schemas validate structured outputs with a repair round.
- **Agent and function calling:** Mo is one stateful graph. It reaches the three specialists (`role_opportunity`, `candidate_evidence`, `interview_strategy`) only through allow-listed tools. **Interview evaluation is not a specialist or an agent**: it is a separate LLM-backed service with a validated structured output. The registered tool set is defined in code (`career_tool_registry`, `src/agent/registry.py`: six Career tools, three specialist tools, two human-action tools). Unregistered tools are rejected; gap analysis and planning are deterministic code.
- **RAG:** deterministic router, structured retrieval plus hybrid vector and BM25 fusion, geography precedence, security screening, citations to retrieved evidence, and a post-answer grounding policy (contextual citations only; external facts need retrieval; no unsourced compensation estimates, in seven languages).
- **Human-in-the-loop:** a real pause for three decisions (confirm an ambiguous role, approve a memory, approve the handoff into practice); nothing is saved without approval.

## Setup and environment

Requirements: Python 3.10+ (CI runs 3.11), Node and npm (CI pins the Node version in `.github/workflows`). LLM-backed features need an OpenRouter key; everything else, the tests and the offline demonstration work without one.

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"            # backend and test dependencies (see pyproject.toml extras for db, speech, ocr)
cd frontend && npm install && cd ..
```

Minimum environment for the live product: `OPENROUTER_API_KEY` (never commit it) and `AGENT_COACH_ENABLED=true`. `API_ENV` defaults to `development` (the developer identity fallback is then allowed); set `API_ENV=production` for the fail-closed behaviour described below. Use a **throwaway** `DATABASE_URL` for any demonstration; never point a demo at a development database.

## How to run

```bash
# Terminal 1: backend (http://localhost:8000, docs at /docs)
AGENT_COACH_ENABLED=true API_ENV=development OPENROUTER_API_KEY=... uvicorn src.api.main:app --reload
# Terminal 2: frontend, the primary UI (http://localhost:3000)
cd frontend && npm run dev
```

**Warning:** a working copy containing `.env` or `.streamlit/secrets.toml` loads the OpenRouter key and makes real, billed calls; for a provider-free UI run, start the backend from a fresh checkout (see the demo guide). `streamlit run app.py` is a **legacy development interface**, not the Ask4Mo reviewer experience. The knowledge base is built from local sources and is **not committed**: a fresh checkout abstains ("insufficient verified evidence") instead of inventing citations. Check readiness with `python scripts/check_demo_knowledge.py`; build instructions are in the [archived reference README](docs/README_REFERENCE_AND_HISTORY.md#knowledge-base--citations-grounded-evidence).

## Demonstration (no provider, no network)

For a review-day environment with the curated knowledge base and governed sources (isolated copy, keyless), see [docs/capstone/submission/REVIEW_DAY_READINESS.md](docs/capstone/submission/REVIEW_DAY_READINESS.md) and `scripts/review/review_env.sh`.


```bash
python scripts/demo_offline_journey.py        # synthetic candidate: Opportunity -> Preparation -> Retrieval -> Practice -> Feedback
```

It prints each step with REAL / MOCKED / DISABLED labels (the model text is scripted; the API, agent graph, tool validation, retrieval over a synthetic corpus, grounding policy and interview services are real), blocks every network request and is covered by tests. Guide, script and optional live-UI instructions: [docs/capstone/submission/DEMO_GUIDE.md](docs/capstone/submission/DEMO_GUIDE.md).

## Evaluation evidence

Full detail, modes and limits: [docs/capstone/submission/EVALUATION_SUMMARY.md](docs/capstone/submission/EVALUATION_SUMMARY.md).

| Evidence | Result |
|---|---|
| Backend tests (pytest) | 5,060 passed, 34 skipped, 0 failed |
| Frontend unit / browser E2E / CI evaluators | 1,082 passed / 412 passed (chromium) / 52 of 52 commands |
| Live agent benchmark (22 cases, one run) | tool selection 0.773, retrieval decision 0.909, approval decision 0.909 (small sample) |
| Grounding policies | 77 policy tests plus integrated tests in 7 languages; live sample of 7 questions (predates the final corrections) |
| **Internal coverage gate** | **386/412 developer-local: FAIL (392 required); 258/412 clean checkout: FAIL; 0/412 human-qualified** |
| Acceptance criteria | 17 PASS, 8 PARTIAL; **AC-24 (pilot) PARTIAL**, human revalidation deferred |

```bash
python -m pytest -n 4 -p no:cacheprovider tests         # backend, no provider calls
python scripts/eval_agent.py                           # deterministic agent orchestration + gates (56 cases)
cd frontend && npm test && npm run e2e                 # vitest, then Playwright
```

This is an **academic demonstration** with disclosed gaps, not a production-release qualification.

## Ethical considerations, security and privacy

Private by default and owner-scoped; no fabricated citations, evidence or scores; no protected-trait inference, no camera; candidate content is untrusted data in labelled prompt blocks; Mo is AI and can be wrong. Details and the disclosed gaps: [docs/capstone/submission/ETHICS_AND_LIMITATIONS.md](docs/capstone/submission/ETHICS_AND_LIMITATIONS.md), [docs/privacy.md](docs/privacy.md), [docs/security.md](docs/security.md).

- **Accounts and sessions:** email/password with server-side sessions (opaque token in an HttpOnly cookie). **Production is fail-closed:** a request without a valid session is `401`, never a downgrade. The `X-User-Subject` header and an anonymous developer identity exist only in development and test environments. **Google OIDC** exists in the backend, is off by default, has no frontend button and is **not validated live**.
- **Admin:** a permission-based control plane (qualified in W10.14; the platform owner role holds all 44 canonical permissions since W12.1); Admins are never a private-candidate-data superuser, with two-person approval and step-up where designed. Not built: Support attachments, Admin workspace deactivation, universal operator search, live billing, a production secret vault and external paging.
- **Privacy centre** (`/account/data`): view, export, delete items and the account, revoke shares. PRIV-W9-01 and PRIV-W9-02 were closed in W10.10, with stated limits: preparation runs are indexed per user from W10.10 onward and legal-document acceptance is recorded from W10.10 onward and is never back-filled; hosting backups follow the provider's retention.
- **Localization boundaries:** Eight **interface locales** (en, de, fr, es, it, pt, nl, ru) and the same eight Mo conversation languages. Dictation, text-to-speech and realtime voice support seven languages (not Russian); the knowledge base, document/OCR language and labour-market geography are separate lists, and Russian is not an official ESCO language and Russia is not a supported labour market. Translations other than English are engineering translations pending native and legal review. The slogan is never translated.

## Known limitations

- The internal product-coverage gate **fails** (see above); the knowledge base is not committed; international compensation (Compensation V2) is built and **disabled**; no source is qualified for candidate-visible international use.
- Live evidence is small-sample; no human has rated interview feedback, answers or translations; tool-selection discipline of the live model is imperfect.
- Privacy notice, terms and AI-transparency pages are engineering drafts without legal review; selective preparation-chat deletion, bulk memory deletion and per-version document deletion do not exist.
- No hosted deployment, backup restore drill or monitoring was tested; billing is a **mock** (Premium is a preview, `BILLING_ENABLED=false`); server-side speech is disabled and not verified; Google sign-in and live email are not validated live; the rate limiter is per-process unless the optional, unvalidated Redis adapter is configured.
- Browser coverage is chromium only; no screen-reader testing; WCAG compliance is not claimed.
- The full tracked list is the deferred-issues register: [docs/capstone/POST_SUBMISSION_DEFERRED_ISSUES_REGISTER.md](docs/capstone/POST_SUBMISSION_DEFERRED_ISSUES_REGISTER.md); current acceptance state: [docs/capstone/CAPSTONE_ACCEPTANCE_LEDGER_CURRENT.md](docs/capstone/CAPSTONE_ACCEPTANCE_LEDGER_CURRENT.md).

## Documentation

Map of canonical documents: [docs/README.md](docs/README.md). Roadmap and scope: [docs/capstone/capstone_phase_plan.md](docs/capstone/capstone_phase_plan.md). Submission package: [docs/capstone/submission/](docs/capstone/submission/). The previous long README (foundation architecture, Sprint history, optional services) is preserved in [docs/README_REFERENCE_AND_HISTORY.md](docs/README_REFERENCE_AND_HISTORY.md).
