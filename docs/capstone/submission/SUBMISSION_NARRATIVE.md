# Ask4Mo: Submission Narrative

**Project:** Ask4Mo, an Intelligent Interview Coach. **Primary case:** Case 2, an AI agent for task automation. **Supporting capability:** Case 1, RAG-powered knowledge assistance. **Assessment dimensions (owner-stated; descriptors and weights are not in the repository):** Outcome Quality, Learning Application, Ethical Considerations, Presentation. **Repository state described:** `main` at the merge of PR #205 (`3d1af6f`) plus this P11 branch. Everything below is traceable to the repository; no outcome or impact metric is claimed, because none was measured with real users.

## 1. Situation, Complication, Resolution

**Situation.** Candidates preparing for a specific job need interview preparation that reflects the role and their own experience: what the role demands, how their background compares, what to practise and how well they answered.

**Complication.** Generic AI interview preparation tends to lack role context, to state facts without reliable grounding, and to give practice feedback that is not tied to the role or comparable from one session to the next. A model that answers from memory can invent statistics, salaries and sources, and nothing makes it ask for approval before it saves something about the candidate.

**Resolution.** Ask4Mo organises preparation, practice and feedback around **one job at a time**. **Mo**, the AI coach, is a bounded **LangGraph agent** that chooses from a fixed set of controlled tools, retrieves career evidence only when it is useful, pauses for **human approval** where it matters, and hands the approved preparation into a durable **interview practice** session with structured, rubric-based feedback. Evidence-grounded answers carry citations to retrieved sources; where evidence is missing, Mo says so and does not invent figures.

## 2. The problem and the target users

The problem is the gap between generic advice and the preparation a specific candidate needs for a specific job. **Target users** are candidates preparing for professional, specialist and leadership interviews across professions (not recruiters; Ask4Mo is not ATS or HR software and gives practice guidance, never a hiring decision). The product is deliberately not limited to one profession.

## 3. The solution as a candidate journey

`Opportunity -> Prepare (Mo) -> Knowledge retrieval -> Practice -> Feedback -> Progress and history`, with a privacy centre throughout. An **Opportunity** is a private space for one job (role, company, optional job description). In **Prepare**, Mo analyses the job description, compares the candidate's approved evidence, retrieves grounded career evidence, builds a plan with the available time and generates tailored questions. **Practice** runs a realistic interview with a question, structured feedback, a deep dive and a final report. The runnable, offline version of this journey is described in [`DEMO_GUIDE.md`](DEMO_GUIDE.md).

## 4. Architecture (diagrams in [`ARCHITECTURE_DIAGRAMS.md`](ARCHITECTURE_DIAGRAMS.md))

Next.js 15 / React 19 / TypeScript frontend over a typed **FastAPI** backend (`/api/v1`, owner-scoped routes, safe error envelope, request ids), a thin **application layer** (`src/application`), and domain packages: the agent (`src/agent`), Career Intelligence and RAG (`src/copilot`), interview services (`src/interview_service.py`, `src/evaluation_service.py`), documents and evidence, opportunities, workspaces, and an Admin control plane. Persistence is SQLAlchemy with Alembic (single head `0039_speech_governance`), SQLite for development and tests and PostgreSQL as the production target. Streamlit (`app.py`) remains as a **legacy development interface** over the same application layer; the primary product is Next.js plus FastAPI.

## 5. LLM integration

All model traffic goes through **OpenRouter**. Career Intelligence and the agent use LangChain's OpenAI-compatible chat model; Interview Practice uses a direct HTTPX client. One registry (`src/llm/models.py`) maps three profiles, **Fast, Balanced and Advanced**, to current model slugs and a per-operation policy (`src/llm/policy.py`) resolves which tier an operation uses; Interview Practice uses one candidate-selected profile per session (default Balanced). Structured outputs (job analysis, questions, evaluation) are validated against typed schemas with a repair round and safe failure. Usage and cost are captured honestly: unknown usage is never recorded as zero. Plan-based gating of profiles exists but is **disabled** by a code constant.

## 6. LangGraph agent orchestration

Mo is one stateful graph: `START -> initialise -> agent -> (tools | finalize)`, `tools -> (human_review | agent)`, `human_review -> agent`, `finalize -> END`, with a bound of six steps per user turn and a durable SQLite or PostgreSQL checkpointer (fail-closed when durability is configured). The graph is the orchestrator; the model chooses actions inside it. See [`ARCHITECTURE_DIAGRAMS.md`](ARCHITECTURE_DIAGRAMS.md).

## 7. Function calling (tool use)

The model sees a **fixed, allow-listed registry** of 11 tools (`career_tool_registry`): six Career tools (job-description analysis, candidate-gap analysis, preparation plan, interview-question generation, career-knowledge search, current-market research), three specialist tools (`AnalyzeRoleOpportunity`, `FindCandidateEvidence`, `BuildCoachingStrategy`) and two human-action tools (`ProposePreparationMemory`, `RequestPracticeHandoff`). Tool calls are validated (arguments, prerequisites), an unregistered or disabled tool is rejected and logged, tool results are placed in trust-separated blocks and never treated as instructions, and gap analysis and planning are **deterministic** code, not model output. Three bounded **specialist** agents exist behind tools; interview evaluation is a separate structured-output service, not an agent.

## 8. RAG and retrieval

Structured stores (roles, competencies, compensation, labour market, credentials) plus a Chroma vector index with an offline hash-embedder fallback; a deterministic router picks lanes; hybrid vector plus BM25 fusion; query translation for non-English questions; geography precedence; security screening of retrieved text; and citations that map only to retrieved evidence. A **post-answer grounding policy** (owner-approved) enforces: citations on an abstention must be relevant context, never another country's compensation as support; external factual questions need retrieval before a verified claim, while legitimate clarification needs no tool; and Mo never offers or states an unsourced compensation estimate (seven knowledge-base languages). The knowledge base is built from local sources and is **not** committed, so a clean checkout abstains instead of inventing evidence. Knowledge coverage is below the internal target (section 12).

## 9. Prompt engineering

Prompts keep trust zones apart (system instructions, user question, job description and candidate context as untrusted data, tool results, retrieved evidence); responses use a labelled template (evidence with citations, tool results, recommendation); language and coaching-style directives are built only from allow-lists (a candidate-supplied string never reaches a prompt); evaluation prompts demand a rubric JSON; a deterministic Prompt Lab compares prompt and model-policy variants offline with no auto-promotion. Prompt quality against human raters is **not** measured.

## 10. Human-in-the-loop controls

The graph pauses with a real `interrupt()` for exactly three decisions: confirming an ambiguous role, approving a proposed memory write, and approving a handoff into practice. Decisions are validated against the pending action before the graph is touched; approvals apply once; nothing is persisted without approval; a stale or invalid decision is refused and the run stays paused.

## 11. Evaluation

Deterministic evaluators (52 commands in CI) and tests cover orchestration, retrieval, grounding, security and privacy; a hard-guarded live harness (one cumulative budget ledger, never in CI) recorded model routing, a 22-case agent benchmark, a seven-role interview harness and a grounding-policy sample. The measured numbers, their sample sizes and their limits are in [`EVALUATION_SUMMARY.md`](EVALUATION_SUMMARY.md). No acceptance thresholds were set by the owner and none were invented.

## 12. Ethics and privacy

Private by default and owner-scoped; candidate documents are untrusted data and never placed in prompts; no fabricated citations, evidence or scores; no protected-trait inference; no camera; scores are practice feedback, not hiring decisions; the privacy centre supports export and deletion with stated limits; admins are never a private-data superuser. Details and the disclosed gaps: [`ETHICS_AND_LIMITATIONS.md`](ETHICS_AND_LIMITATIONS.md).

## 13. Limitations (the honest summary)

The internal **product-coverage gate fails** (386 of 412 developer-local against 392 required; 258 of 412 on a clean checkout; 0 human-qualified); acceptance criterion AC-24 is PARTIAL and the human revalidation (P10F) is deferred; interview and feedback quality has not been rated by humans; translations other than English are engineering translations; production speech, live billing, hosted operation and international source qualification are not delivered; live evidence is small-sample. The full, tracked list is the deferred-issues register (392 issues).

## 14. Future development

Qualify sources and human reviewers to close the coverage gate; human rating of interview feedback and citation support; semantic retrieval calibration and a judged evaluation run; hosted deployment and monitoring; native-language review; the recent-run list for the agent inspector; speech activation and commercial features behind their existing gates. All are tracked in the register with owners and evidence still unknown.
