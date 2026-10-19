# Architecture Diagrams

Diagrams are Mermaid (rendered by GitHub and most Markdown viewers) and were drawn from the code, not from planning documents: node names come from `src/agent/graph.py`, the tool list from `src/agent/registry.py`, retrieval stages from `src/copilot/service.py`. Each diagram states what is live, mocked or disabled in the offline demonstration.

## 1. System context

```mermaid
flowchart LR
    C[Candidate browser] --> FE[Next.js 15 frontend<br/>candidate UI, public site, English-only /admin]
    FE --> API[FastAPI /api/v1<br/>owner-scoped routes, safe error envelope, request ids]
    API --> APP[Application layer<br/>src/application]
    APP --> AG[Mo: bounded LangGraph agent<br/>src/agent]
    APP --> INT[Interview Practice<br/>question + evaluation services]
    APP --> DOC[Documents and evidence, Opportunities,<br/>Workspaces, Account lifecycle]
    AG --> CI[Career Intelligence + RAG<br/>src/copilot]
    CI --> KB[(Structured stores + Chroma vector index)]
    APP --> DB[(SQLAlchemy + Alembic<br/>SQLite dev/tests, PostgreSQL target)]
    AG -. LLM via OpenRouter .-> LLM[(Provider: not contacted in tests or the offline demo)]
    INT -. LLM via OpenRouter .-> LLM
    ST[Streamlit app.py<br/>legacy development interface] --> APP
```

## 2. Mo: the LangGraph agent

```mermaid
flowchart TD
    S((START)) --> I[initialise<br/>load bounded approved memory as DATA]
    I --> A[agent<br/>model chooses a tool or answers]
    A -->|tool requested and within 6 steps| T[tools<br/>allow-list, argument and prerequisite validation]
    A -->|answer or step limit| F[finalize]
    T -->|human decision needed| H[human_review<br/>interrupt - durable checkpoint]
    T -->|otherwise| A
    H --> A
    F --> E((END))
    E --> RES[Result built in the application layer:<br/>output guard + grounding policy + citation consistency]
```

Human decisions (only three): confirm an ambiguous role, approve a proposed memory, approve the handoff into practice. Resume validates the decision against the pending action before the graph is touched.

## 3. Function calling: the tool registry (11 tools)

```mermaid
flowchart LR
    M[Model] -->|tool call| V{Registry allow-list<br/>unknown tool = rejected and logged}
    V --> C1[AnalyzeJobDescription - LLM-backed, schema-validated]
    V --> C2[AnalyzeCandidateGaps - deterministic]
    V --> C3[BuildPreparationPlan - deterministic]
    V --> C4[GenerateInterviewQuestions - LLM-backed]
    V --> C5[SearchCareerKnowledge - retrieval only, no answer]
    V --> C6[ResearchCurrentMarket - bounded, flag-gated]
    V --> S1[AnalyzeRoleOpportunity - specialist]
    V --> S2[FindCandidateEvidence - specialist, owner-scoped approved evidence only]
    V --> S3[BuildCoachingStrategy - specialist]
    V --> H1[ProposePreparationMemory - proposes, never saves]
    V --> H2[RequestPracticeHandoff - sets a flag, never creates a session]
```

## 4. RAG pipeline and grounding

```mermaid
flowchart TD
    Q[Question] --> SEC[Input validation + injection screening]
    SEC --> TR[Query translation if non-English]
    TR --> R[Deterministic router: pick lanes]
    R --> SR[Structured retrieval<br/>roles, competencies, compensation, labour market, credentials]
    R --> HY[Hybrid retrieval: vector + BM25 fusion over narrative passages]
    SR --> EV[Evidence assembly<br/>geography precedence, source screening, citations]
    HY --> EV
    EV --> SYN[Synthesis prompt: trust-separated blocks]
    SYN --> LLM[(LLM)]
    LLM --> OG[Output guard: secrets, leakage, invalid markers]
    OG --> GP[Grounding policy: contextual citations only,<br/>no cross-country support, no unsourced estimate,<br/>no figure absent from evidence]
    GP --> ANS[Answer + citations that map to retrieved evidence]
    EV -. empty .-> ABS[Abstention with localized guidance]
```

## 5. Data and trust boundaries

```mermaid
flowchart LR
    subgraph Untrusted DATA
      JD[Job description]
      BG[Candidate background]
      DOCS[Uploaded documents]
      RET[Retrieved passages]
      TOOLOUT[Tool results]
    end
    subgraph Trusted
      SYS[System instructions, allow-lists]
      POL[Policies: authorization, grounding, HITL]
    end
    Untrusted DATA --> PROMPT[Prompt blocks labelled as data]
    SYS --> PROMPT
    PROMPT --> LLM[(LLM)]
    LLM --> POL
    POL --> OUT[Candidate-visible output]
    OWN[(Owner-scoped storage)] --- POL
    ADM[Admin control plane] -. metadata only, never candidate content .-> OWN
```

## 6. Offline demonstration: what is real

```mermaid
flowchart LR
    D1[Account + Opportunity<br/>REAL FastAPI + SQLite temp] --> D2[Preparation: LangGraph agent<br/>REAL graph and guards, MOCKED model]
    D2 --> D3[Retrieval + grounded answer<br/>REAL retrieval over synthetic corpus, MOCKED reply, REAL policy]
    D3 --> D4[Practice question<br/>REAL service, MOCKED reply]
    D4 --> D5[Feedback<br/>REAL service, MOCKED reply]
    X[DISABLED: live provider, speech, billing, email, rollout gates]
```
