# Technical Q&A Preparation

Short answers with the evidence to point at. Where the honest answer is "not done" or "not measured", say so.

**1. What kind of agent is Mo?** A single stateful, bounded tool-using agent built as a LangGraph state machine (a ReAct-style loop with a human-review node), not a free-running autonomous agent. It has three bounded specialist sub-agents reachable only through tools. Interview evaluation is deliberately not an agent: it is a structured-output service. Evidence: `src/agent/graph.py`, `src/agent/registry.py`, `src/agent/specialists/`.

**2. How does function calling work here?** The model is given a fixed registry of 11 tool schemas (LangChain `bind_tools`). Each call is validated for registration, arguments and prerequisites (for example the plan needs a prior gap analysis); unknown or disabled tools are rejected and logged; results return as data; gap analysis and planning are deterministic code. Evidence: `src/agent/tools.py`, `tooling.py`, `eval_agent` (56 cases).

**3. Why LangGraph?** Durable checkpoints, explicit routing, a first-class human `interrupt()`/resume, bounded loops and testable nodes. A plain loop would have needed those rebuilt. Trade-off: version pinning (`langgraph` 0.3.x and a matching checkpoint package).

**4. Why RAG instead of just prompting?** Salaries, statistics and requirements change and need sources; RAG gives attributable, current, abstainable evidence and lets the code check that a citation points at something retrieved. Prompting alone cannot make a model cite what it did not retrieve. Trade-off: retrieval quality becomes the limit; coverage is below target (386/412).

**5. Why these models, and how are they chosen?** Three profiles (Fast, Balanced, Advanced) behind one registry; Balanced is the default; an operation policy raises the tier where needed; candidates choose a profile for practice sessions, never a raw model id. The slugs come from OpenRouter configuration, not code branches. Honest: no human-rated model comparison exists, and plan-based profile gating is disabled.

**6. How is the system secured?** Server-side ownership checks on every route, fail-closed identity in production, injection screening on inputs and retrieved text, trust-separated prompts, output guards for secrets and leakage, rate limits, a 44-permission Admin with two-person approval and step-up for sensitive actions, append-only audit, and negative tests (candidate isolation, forged sessions, disabled features). Not done: hosted hardening, a real malware scanner, live Redis, monitoring.

**7. How does human approval work?** The graph pauses with `interrupt()` on a durable checkpoint for three decisions only. A response is validated against the pending action before anything resumes; approvals apply once; memory is written only after approval. Evidence: `tests/test_agent_hitl*.py`.

**8. What happens on failure?** Model or tool errors terminate safely with a controlled message (never a raw error), provider failures degrade to a limited summary, an empty model reply never shows a blank answer, retries are bounded, the step budget stops loops, and an integrated test proves a failing provider leaks no key or prompt. Evidence: `tests/test_integrated_requalification.py`.

**9. How is the code organised?** `src/api` (thin routes), `src/application` (UI-agnostic services), `src/agent` (graph, tools, guards), `src/copilot` (retrieval, RAG, security, policy), `src/interview_service.py` and `evaluation_service.py`, `src/llm` (registry and policy), Admin and billing packages, `frontend/` (Next.js), `scripts/` (evaluators), `tests/` (backend), `migrations/` (Alembic). Business logic is never in routes or components.

**10. What trade-offs did you make?** Deterministic code for safety-relevant steps over model flexibility; breadth (Admin, billing mock, speech governance) beyond the core case, which cost depth in human validation; offline-first evidence over live evidence because of a hard budget; honesty labels over a headline score.

**11. What are the limits of your evaluation?** Small live samples (22 agent cases once; 7 interview roles; 7 policy questions); deterministic proxies; no human rating; no judged (RAGAS) run; no semantic calibration; chromium only; a failed internal coverage gate that was not hidden. Aggregate agent misses of the first run were not itemised.

**12. Is the coverage gate failure a bug?** No. It is an internal bar of 392 of 412 accepted outcomes that the system does not reach (386 developer-local, 258 on a clean checkout). It depends on qualified sources and human review that were deferred; nothing was relaxed to improve it.

**13. What is mocked in the demo?** The model text only. The API, database, agent graph, tool validation, deterministic gap analysis and planning, retrieval over a synthetic corpus, guards and interview services are real.

**14. How do you stop the model inventing salaries?** Three layers: the prompt forbids it; retrieval abstains when nothing in scope exists; a deterministic post-answer layer removes estimate offers and any figure that appears in no in-scope evidence, tool result or user text, and never lets another country's compensation count as support. Tested in seven languages.

**15. Why is Streamlit still in the repo?** It is the legacy interface from the earlier sprint, kept running over the same application layer and covered by a CI smoke check; the primary product is Next.js plus FastAPI.

**16. What would you do with another month?** Qualify sources and appoint reviewers to close the gate; human rating of feedback and citations; semantic retrieval calibration; hosted deployment with monitoring; native-language review; the recent-runs list for the agent inspector.
