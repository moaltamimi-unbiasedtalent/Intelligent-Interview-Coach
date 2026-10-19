# Technical Presentation and Presenter Notes

**Timing is ASSUMED** (10 minutes plus 5 minutes of questions, as recorded in the project's own planning documents). The official presentation requirements are not verified in the repository; adjust the slide count to the real rule once the owner confirms it. Structure follows the six topics the planning documents name (problem, solution, data, evaluation, challenges, what's next) and covers the four assessment dimensions the owner stated: Outcome Quality, Learning Application, Ethical Considerations, Presentation.

| # | Slide | Assumed time | Dimension served |
|---|---|---|---|
| 1 | Problem and users (Situation, Complication, Resolution) | 0:45 | Outcome Quality |
| 2 | The solution: one job, one journey | 0:45 | Outcome Quality |
| 3 | Architecture | 1:00 | Learning Application |
| 4 | Case 2: the agent and function calling | 1:15 | Learning Application |
| 5 | Case 1: RAG and grounding | 1:15 | Learning Application |
| 6 | Prompts, structured outputs and model routing | 0:45 | Learning Application |
| 7 | Human approval and security | 0:45 | Ethical Considerations |
| 8 | Demonstration (offline journey, or the live UI if available) | 1:30 | Outcome Quality |
| 9 | Evaluation: what was measured, including the failed gate | 1:15 | Outcome Quality, Ethical Considerations |
| 10 | Ethics, limitations, lessons, what is next | 0:45 | Ethical Considerations, Presentation |

## Slide 1: Problem and users
- Show: three lines (Situation, Complication, Resolution) and the target user (a candidate preparing for one specific job; not recruiters).
- Say: generic AI preparation lacks role context, grounded facts and comparable feedback; models also invent statistics and sources.
- Do not say: any user count, satisfaction figure or outcome improvement. None exists.

## Slide 2: The solution
- Show: `Opportunity -> Prepare -> Knowledge -> Practice -> Feedback`.
- Say: everything is organised around one job; Mo is an agent with controlled tools; practice and feedback are rubric-based; the privacy centre exports and deletes.
- Note: primary case is the task-automation agent (it automates the preparation workflow); RAG is the supporting capability that grounds it.

## Slide 3: Architecture (diagram 1 of `ARCHITECTURE_DIAGRAMS.md`)
- Show: frontend, FastAPI, application layer, agent, Career Intelligence, interview services, persistence, provider adapters.
- Say: thin routes, business logic in `src/`, one application layer reused by FastAPI and the legacy Streamlit app; owner-scoped data; a single Alembic head.
- Trade-off to mention: more layers than a prototype needs, chosen so the same services are testable without a UI or provider.

## Slide 4: Case 2, the agent and function calling (diagrams 2 and 3)
- Show: the graph (initialise, agent, tools, human_review, finalize) and the 11-tool registry.
- Say: the model chooses a tool; the code validates arguments and prerequisites, rejects unregistered tools, runs deterministic gap analysis and planning itself, and bounds the loop at six steps; three specialists sit behind tools; evaluation is a separate structured-output service, not an agent.
- Evidence: 56-case deterministic orchestration evaluation; live 22-case run (tool selection 0.773, an honest weakness).

## Slide 5: Case 1, RAG and grounding (diagram 4)
- Show: router, structured plus hybrid retrieval, evidence assembly, synthesis, output guard, grounding policy.
- Say: why RAG rather than prompting alone (current, attributable, abstainable facts); citations map only to retrieved evidence; three owner-approved policies; unsupported salary estimates are removed in seven languages.
- Honest note: the knowledge base is not committed; a clean checkout abstains instead of inventing.

## Slide 6: Prompts, structured outputs, model routing
- Say: trust-separated blocks; allow-listed language and style directives; JSON schemas with a repair round; three model profiles through one registry and a per-operation policy.
- Learning story: a live run found requests silently routed to the wrong model (import-time default); fixed; 0 of 90 later requests off-route.

## Slide 7: Human approval and security
- Say: three real pauses (confirm role, approve memory, approve handoff); nothing saved without approval; owner-scoped isolation; Admin is not a data superuser; injection screening; secrets never logged.
- Evidence: HITL, isolation and Admin matrix tests.

## Slide 8: Demonstration
- Run `python scripts/demo_offline_journey.py` (or the live UI). State clearly what is MOCKED (the model text) and REAL (the graph, tools, retrieval, guards, services). See `DEMO_GUIDE.md`.

## Slide 9: Evaluation (`EVALUATION_SUMMARY.md`)
- Show: tests (backend, 1,082 frontend, 412 browser, 52 evaluators), live evidence, and the **failed internal coverage gate: 386/412 developer-local, 258/412 clean checkout, 0 human-qualified**; AC-24 partial.
- Say: the gate is an internal quality bar I set and did not meet; the reasons are source qualification and human review, deliberately deferred; this is an academic demonstration, not a production-release qualification.

## Slide 10: Ethics, limitations, lessons, next
- Say: practice feedback is not a hiring decision; no protected-trait inference; privacy drafts lack legal review; samples are small and human review is pending. Lessons: correct the measurement before the product; citation syntax is not evidence; prompts steer, code enforces. Next: source qualification and human review to close the gate, hosted deployment, semantic calibration, native review.

## Claims to avoid on stage
Production readiness; human-qualified quality; passing the coverage gate; international market support; production speech; operational billing; any outcome metric; "AI interview coach improves hiring chances".
