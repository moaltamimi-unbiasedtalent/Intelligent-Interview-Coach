# Demonstration Guide

One end-to-end **synthetic** candidate journey: **Opportunity -> Preparation -> Knowledge retrieval -> Interview practice -> Feedback.** No real personal data, no provider required, no paid call. The official presentation format is 10 minutes plus 5 minutes of questions (verified in the brief); the minutes inside this guide are its own allocation.

## 1. What is live, offline, mocked or disabled

| Component | Offline fallback (`scripts/demo_offline_journey.py`) | Live UI demonstration (optional, owner-run) |
|---|---|---|
| Next.js frontend | not used (terminal transcript) | REAL (`npm run dev`); rehearsed provider-free (section 4) |
| FastAPI app, auth, owner-scoped storage | REAL (in-process, throwaway SQLite) | REAL (use a throwaway `DATABASE_URL`, never the development database) |
| LangGraph agent, tool allow-list, guards, grounding policy | REAL | REAL |
| LLM replies (agent, answer synthesis, question, evaluation) | **MOCKED** (scripted) | provider-free rehearsal: none (safe not-configured state); optional live: **LIVE** through OpenRouter on the owner's key (owner decision; the P10E ledger is not used) |
| Gap analysis and preparation plan | REAL (deterministic code) | REAL |
| Knowledge retrieval | REAL over a **synthetic fixture corpus** (offline hash embedder) | needs the local knowledge base built, otherwise Mo abstains ("insufficient evidence") |
| Email | MOCKED (in memory) | DISABLED (not configured) |
| Server-side speech, billing and checkout, Compensation V2, all 12 rollout gates | DISABLED | DISABLED |

**State this on stage:** the offline run proves the control flow, tool use, retrieval, grounding policy, structured outputs and feedback pipeline with scripted model text; it does not show model quality. Model quality evidence is separate (`EVALUATION_SUMMARY.md`) and small-sample.

## 2. Synthetic data

`evaluations/demo/synthetic_demo_candidate.json`: a fictional candidate ("Synthetic Candidate A", reserved `.invalid` email), a fictional employer, a short job description for a Data Analyst, a short background, one practice question and one written answer. The fixture knowledge corpus is the synthetic one used by the P10D evaluator. Nothing derives from a real person or document.

## 3. Primary path: the deterministic offline journey

```bash
python scripts/demo_offline_journey.py                 # prints the transcript, exit code 0 when every check passes
python scripts/demo_offline_journey.py --transcript /tmp/demo.md --json /tmp/demo.json
```

It blocks every network request (any request to a real host raises), uses a temporary database and prints five steps with REAL/MOCKED/DISABLED labels:

| Step | What happens | What to point out |
|---|---|---|
| 1 Account and Opportunity | Registers the synthetic candidate, creates the Opportunity; a second account cannot read it | ownership isolation, 404 not 403 |
| 2 Preparation with Mo | Agent runs four tools in order (job analysis, gap analysis, plan, knowledge search) and answers with a citation | allow-listed tools, deterministic gap/plan, retrieval only when needed, citation maps to evidence |
| 3 Knowledge and grounding | A supported question gets a cited answer; a Canadian-salary question (no evidence) abstains and the scripted unsourced-estimate offer is removed and replaced by localized guidance | grounding policy: contextual citations, no unsourced estimate |
| 4 Interview practice | The interview service returns a validated behavioural question | structured output, schema validation |
| 5 Feedback | The evaluation service returns a rubric score, strengths, gaps, missing evidence and a follow-up question | feedback is practice guidance, not a hiring decision |

A committed reference run is `docs/capstone/submission/DEMO_TRANSCRIPT_OFFLINE.md`; `tests/test_demo_offline_journey.py` proves the journey is deterministic, passes its checks, labels components, uses synthetic data and cannot reach the network.

## 4. UI demonstration (provider-free rehearsal, and the optional live version)

> **Provider-key hazard (found during the P11 rehearsal; read before starting any server).** A working copy that contains `.env` or `.streamlit/secrets.toml` makes the backend load the OpenRouter key and **make real, billed provider calls** (`/agent/run` answered with a real model reply). Neither `PYTHON_DOTENV_DISABLED=1` nor an empty `OPENROUTER_API_KEY` suppresses it (the key also comes from Streamlit secrets). The reliable way to guarantee a provider-free UI run is to start the backend from a **fresh checkout** (`git worktree add /tmp/ask4mo_demo HEAD`), which contains neither file; there Mo answers "The assistant isn't configured in this environment." and no provider is contacted.

**Provider-free UI rehearsal (verified):**
1. `git worktree add /tmp/ask4mo_demo HEAD`, then from that directory: `PYTHONPATH=. DATABASE_URL=sqlite:////tmp/ask4mo_demo.db API_ENV=development AGENT_COACH_ENABLED=true EMAIL_PROVIDER=memory COPILOT_DATA_DIR=/tmp/ask4mo_demo_data FRONTEND_ORIGINS=http://localhost:3015 <path-to-venv>/bin/uvicorn src.api.main:app --port 8020`.
2. From the main checkout: `cd frontend && NEXT_PUBLIC_API_BASE_URL=http://localhost:8020/api/v1 npm run dev -- --port 3015`.
3. Register and sign in with the synthetic candidate, complete onboarding, create the Opportunity; Prepare, Practice, History, Progress and Data and privacy render; Mo shows its safe "not configured" state.

**Optional live version (owner decision, not performed in this wave):** start the backend from a working copy that has the key, with a throwaway `DATABASE_URL` and a built knowledge base, and use only the synthetic data. This makes a handful of real provider calls on the owner's key (outside the P10E evaluation ledger, which must not be used for a demonstration). Without a built knowledge base Mo abstains instead of citing.

The browser flows are also exercised, with network mocks, by the Playwright suite (`cd frontend && npm run e2e`, 412 tests): the closest repeatable evidence of the UI.

## 5. Fallback decision tree

1. Provider or network unreliable, or no key: run section 3 (always works offline).
2. UI will not start: show the transcript and the architecture diagrams; state that the Playwright suite covers the UI.
3. Question about real model quality: show `EVALUATION_SUMMARY.md` (live evidence, small sample) and say plainly that human rating has not been done.
4. A **recorded video fallback was not produced** in this wave (it needs a human screen recording of a working session). The transcript is the recorded fallback artifact until the owner records one.

## 6. Demonstration script (assumed 6 minutes of the assumed 10)

| Time | Say and show |
|---|---|
| 0:00 | The candidate problem in one sentence; Ask4Mo organises preparation, practice and feedback around one job |
| 0:30 | Architecture diagram 1 and 2: frontend, API, agent graph, retrieval, interview services |
| 1:30 | Run the offline journey (or the UI): Step 1 (Opportunity, isolation) |
| 2:15 | Step 2: tools in order; "the model chooses, the code guards": allow-list, deterministic gap analysis, retrieval only when needed |
| 3:15 | Step 3: the cited answer, then the abstention and the removed salary-estimate offer |
| 4:15 | Steps 4 and 5: question and rubric feedback with missing evidence and a follow-up |
| 5:15 | State what is mocked in this run; show the evaluation summary and the failed coverage gate |
