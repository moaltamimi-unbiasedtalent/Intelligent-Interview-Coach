# Ask4Mo offline demonstration transcript

Synthetic candidate, deterministic scripted model, no provider, no network. REAL / MOCKED / DISABLED labels apply to each step.

## Step 1: Account and Opportunity

| Component | State |
|---|---|
| FastAPI app, auth, owner-scoped storage | REAL (throwaway SQLite) |
| Email | MOCKED (in-memory, nothing sent) |
| Live provider | DISABLED |

- Registered and signed in a synthetic candidate (user id 1); created the Opportunity 'Data Analyst' at Northwind Analytics (fictional).
- A second synthetic account asking for that Opportunity receives a not-found answer (ownership isolation).

Checks: PASS opportunity_created, PASS listed_for_owner, PASS foreign_access_denied

## Step 2: Preparation with Mo (LangGraph agent, controlled tools, agentic retrieval)

| Component | State |
|---|---|
| LangGraph agent graph, tool allow-list, guards, step bound | REAL |
| Agent LLM | MOCKED (scripted tool calls and final text) |
| Gap analysis and preparation plan | REAL (deterministic) |
| Job analysis, question generation | MOCKED structured results |
| SearchCareerKnowledge retrieval | REAL over a synthetic fixture corpus (offline hash embedder) |
| Human approval | available; not triggered in this path |

- Tools executed in order: AnalyzeJobDescription, AnalyzeCandidateGaps, BuildPreparationPlan, SearchCareerKnowledge.
- Status: completed. Retrieval used: True. Evidence items: 6; citations: 7.
- Mo's answer (after the post-answer grounding policy): "Here is your preparation outline. Your strongest match is reporting and stakeholder communication; the main gap is Python, so spend your first hours on SQL practice and one stakeholder-explanation story. A Data Analyst prepares data, builds dashboards and communicates findings [1]."
- Response class (internal): EVIDENCE_BACKED_ANSWER.

Checks: PASS tools_in_order, PASS completed, PASS retrieval_used, PASS citation_matches_evidence

## Step 3: Knowledge retrieval, citations and the grounding policies

| Component | State |
|---|---|
| Hybrid retrieval, citations, output guards | REAL (synthetic fixture corpus) |
| Answer text | MOCKED (scripted model reply) |
| Grounding policy layer (contextual citations, no unsourced estimates) | REAL |

- Question: "What does a Data Analyst do?" -> class EVIDENCE_BACKED_ANSWER, 1 citation(s) to retrieved evidence.
- Question: "What does a Data Analyst earn in Canada?" (no Canadian compensation evidence exists) -> class ABSTENTION_WITHOUT_CITATIONS. The scripted reply offered an unsourced salary estimate; the policy layer removed the offer and added the localized guidance: "I cannot give a verified salary figure here. To find reliable figures, tell me the country, the seniority and the occupation, and I can help you locate trustworthy salary sources and judge how comparable they are."

Checks: PASS supported_answer_cited, PASS unsupported_is_an_abstention, PASS no_estimate_offer_survives

## Step 4: Interview practice: question generation

| Component | State |
|---|---|
| Interview service (prompting, JSON validation, repair, usage accounting) | REAL |
| Model reply | MOCKED (scripted) |

- Question 1 (behavioural, communication): "Tell me about a time you had to explain data findings to a stakeholder who was not technical."

Checks: PASS question_present, PASS question_type_behavioural

## Step 5: Interview feedback

| Component | State |
|---|---|
| Evaluation service (rubric JSON, validation) | REAL |
| Model reply | MOCKED (scripted) |

- Overall practice score: 74/100 (practice feedback only, never a hiring decision).
- Strengths: Chose a concrete situation and adapted the chart to the stakeholder; Clear action and a stated outcome
- To improve: Quantify the outcome (for example how many weeks the dashboard was used); Name the data source and the metric
- Missing evidence: No measured result; No mention of how accuracy was checked
- Follow-up question: "What measurable change did the stakeholder's planning show after using the dashboard?"

Checks: PASS has_follow_up_question, PASS names_missing_evidence, PASS usage_recorded

## Result

All checks passed: True. No provider was contacted, no network request left the machine, no paid call was made and no real personal data was used.
