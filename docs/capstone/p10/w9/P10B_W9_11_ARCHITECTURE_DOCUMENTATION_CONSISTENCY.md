# P10B-W9.11 - Architecture & Documentation Consistency

Documentation, comment/docstring and bounded copy wave. **No runtime product behaviour changed**, **no migration**
(Alembic head `0014_opportunities`), 0 paid/live calls, no RC-P10-003, Pilot 2 not resumed, W9.12 and W10 not started.
Rule applied: **fix documentation to match the code; never change working code to match stale documentation.**

## 1. Baseline
`main` = `dacaa9e3f40742158cdadb7bf0cad6c8dd061780` (W9.10 merged, PR #105). Branch `docs/p10b-w9-11-architecture-consistency`.

## 2. Methodology
Authority order: running code, schemas/migrations, tests, evaluators, routes, config, W9.9 Trust Claim Matrix, W9.10
capability matrix/claim register, newer closure docs, older docs. Two independent read-only passes: (a) verified facts from code
(identity resolution, tool registry, specialists, authority constants, speech/locale lists, admin routes, pricing, help/contact,
workspaces); (b) a sweep of README, CLAUDE.md, docs/*, docs/capstone/*, frontend/README and code comments/docstrings for stale
statements, plus an ASCII-folded diacritics scan. Every row below has a disposition.

## 3-4. Discrepancy matrix (84 rows reviewed: P1 = 19, P2 = 30, P3 = 35)
Dispositions: FIXED = corrected; BANNER = historical document labelled, body preserved; OK = verified accurate (no action);
DEFERRED = intentionally left (reason). Row IDs refer to the sweep (A auth, B tools, C specialists, D privacy, E locales,
F authority, G architecture coverage, H billing, I support, J Streamlit framing).

| IDs | Topic (actual implementation) | Disposition |
|---|---|---|
| A1, A14, A15, A16, A17 | README/privacy/operations/limitations said OIDC absent, Streamlit OIDC, or no accounts. Actual: server-side accounts + sessions, fail-closed prod, dev-only header | FIXED (README, privacy.md, operations note) / BANNER (limitations) |
| A2, A18 | CLAUDE.md "production auth still transitional"; stale single-head `0007` | FIXED (reworded, no hard-coded head) |
| A3-A6 | sprint4_architecture "transitional auth", "single agent", "chat + 4 tools" | FIXED (Current-state overview added; historical passages annotated) |
| A7-A11 | Sprint 4 reviewer/security/requirements docs state transitional identity | BANNER (period evidence preserved) |
| A12, A13, A21, A22 | frontend/README, `lib/auth.ts`, memory route and session-store comments | FIXED (comments/docs only) |
| A19, A20, A23, A24 | dev-only wording accurate / planning docs | OK / DEFERRED (accurate or planning-era) |
| B1-B4, B6, B15 | "five/four Career tools" | FIXED (CLAUDE.md, `agent_service.py`, `tools.py` comments, architecture, frontend README, runtime-architecture doc) |
| B5, B7, B12, B13, B14 | phase-era counts in historical docs | BANNER / FIXED (matrix row) / DEFERRED (historical) |
| B8, B9, B11 | accurate or Sprint 3 design | OK / BANNER |
| B10 | security.md "four tools" | BANNER |
| C1-C4 | planning docs promised an Evaluation specialist / 4 specialists | FIXED (reconciliation notes) |
| C5, C6, C7 | reference planning docs / this task's own records | DEFERRED (historical planning) / n.a. |
| D1 | `DATA_RETENTION_NOTE` described Settings delete-all | FIXED as scope comment (string is Streamlit-only and accurate there; unchanged at runtime) |
| D2-D4, D6 | privacy.md/limitations.md Streamlit-era | FIXED (privacy.md rewritten) / BANNER |
| D5, D7, D8 | testing note, Streamlit label, matrix row | OK / FIXED (matrix row) |
| E1, E4-E6, E7 | "7 locales/seven languages" where 8 interface locales apply | FIXED (CLAUDE.md, comments, page metadata "eight languages") |
| E2 | requirements matrix "seven-language" rows | FIXED (language reconciliation note) |
| E3, E10 | historical doc / test titles | DEFERRED |
| E8, E9, E11 | speech-specific "seven" wording is correct | OK |
| F1 | `schemas/career.py` comment reversed (1=industry..3=official) | FIXED (comment only; runtime constants were already right) |
| F2, F3 | correct | OK |
| G1, G2, G4 | README and architecture omit Opportunities, workspaces, accounts, Data & Privacy, Admin, languages | FIXED |
| G3 | final_submission_readiness "canonical" but dated | BANNER |
| G5 | already labelled | OK |
| H1, H2 | billing "no billing" vs W10 planning | FIXED (CLAUDE.md note) / OK |
| I1 | ticketing appears only as a plan | OK (plan, not a claim); README/architecture state it is not implemented |
| J1-J7 | Streamlit framed as the product; "future FastAPI" docstrings | FIXED / BANNER |
| J8 | README stack statement | OK |

## 5-7. README, auth/OIDC, current architecture
README restructured to current sections (what it is, journey, architecture, authentication/security, privacy, localization/voice,
limitations, docs map) with historical material kept under "Reference". Authentication is documented factually: session accounts;
production fail-closed; dev header/anonymous user only in development/test `API_ENV`; Google OIDC backend exists but is disabled by default,
not wired into the frontend and not validated live; sign-in does not currently require a verified email (a runtime observation recorded
as a limitation, not changed); the limiter is in-memory/single-replica. `docs/sprint4_architecture.md` gained a "Current-state overview".

## 8-10. Tool registry, specialists, evaluation
Verified from code: `career_tool_registry` registers **11** tools = six Career (`AnalyzeJobDescription`, `AnalyzeCandidateGaps`,
`BuildPreparationPlan`, `GenerateInterviewQuestions`, `SearchCareerKnowledge`, `ResearchCurrentMarket`) + three specialist tools + two
human-action tools; none is conditional on configuration (only a per-run candidate option hides `ResearchCurrentMarket`). The registry
is the single source of truth; docs describe the composition rather than repeating a number. **Exactly three specialists**:
`role_opportunity` (model-backed), `candidate_evidence` (deterministic, owner-scoped), `interview_strategy` (model-backed with deterministic
fallback). **No Evaluation specialist.** Interview evaluation (`src/evaluation_service.py`) is an LLM-backed service with a schema-validated
`AnswerEvaluation` (it is not an agent, specialist or tool; note: scores are model-produced and validated, not recomputed
deterministically). `src/application/evaluation_service.py` (offline RAGAS run reader) and `scripts/eval_*.py` (CI gates) are distinct things,
now named as such.

## 11. Privacy and retention
`docs/privacy.md` rewritten for W9.8 (what is stored, `/account/data`, export scope, terminology delete/archive/revoke/unlink/anonymise/retain,
limits). PRIV-W9-01 and PRIV-W9-02 are stated; no retention periods invented; no compliance claim; `DATA_RETENTION_NOTE` scoped to the legacy UI.

## 12-13. Language dimensions, Russian/ESCO
Verified: 8 interface locales and 8 Mo conversation languages (`src/locales.py`); dictation, TTS and realtime 7 each; document/OCR 7; KB 7;
Russian excluded from speech, ESCO and geography. Docs now name each dimension (interface locale, conversation language, dictation, TTS/realtime,
labour-market geography, taxonomy language) instead of a generic "N languages".

## 14. Authority levels
Canonical (constants, unchanged): 1 = official/statistical, 2 = public/professional framework, 3 = reputable industry. The only reversed text was a
comment in `src/api/schemas/career.py` (fixed). Guarded by `eval_doc_consistency.py`.

## 15-19. Journey, workspaces, admin, Premium, ticketing
Journey documented as Opportunity -> Prepare -> Practice -> Progress/History with Mo throughout. Workspaces: membership, VIEW-only share grants of
`interview_report` and `story`, owner scoping, revocation, no admin content access. Admin: **current** = `platform_admin`, bounded read-mostly console,
reviewer/evaluation/knowledge diagnostics, pause switches, audit view; **planned (W10, not implemented)** = full control plane. Premium is a preview
(`BILLING_ENABLED=false`, nothing is gated behind premium except a demo endpoint). Support: there is a Help Center and an owner-scoped feedback API;
**there is no ticketing and no contact form**.

## 20. RAG / evidence wording
README and architecture state: retrieval-only tool, deterministic router, sources shown only when retrieved career evidence is used, explicit
insufficient-evidence behaviour; not every answer is RAG-grounded or cited.

## 21. Diacritics cleanup (bounded)
Clear mechanical ASCII-folding repaired in the `company` and `marketing` namespaces of de, fr, es, it, pt, nl (de 43, fr 63, es 43, it 20, pt 57, nl 18
lines), only where the intended word is unambiguous (for example `Fuehren`->`Führen`, `A verifier`->`À vérifier`, `nao esta`->`não está`, `e`->`è`/`é`
only in unmistakable verb contexts; reviewed). Ambiguous words (es `esta`, it `da`, fr `ou`/`la`, pt `para`) were left alone. No retranslation or
restyling. Russian is unchanged. **Native-speaker and legal review remain pending; this is not a quality claim.**

## 22. Historical documents
Not rewritten. A short banner now marks 5 Sprint 1-3 documents and 7 Sprint 4 closure documents as historical, pointing to the current sources;
`docs/architecture.md` and similar already carried banners.

## 23. Automation added
`scripts/eval_doc_consistency.py` (16 invariants, in CI, plus `tests/test_doc_consistency_guard.py`): authority semantics in constants/comment/docs; 8 vs 7
language sets and Russian exclusion; README locale-vs-speech statement; specialists exactly three and documented without an Evaluation specialist;
tool registry composition (6 + 3 + 2 = registry size) and docs match; README/privacy current-state statements and PRIV limitations; admin current-vs-planned
statement; docs index; retention note scope.

## 24. Files changed (summary)
README.md, CLAUDE.md, frontend/README.md, docs/README.md (new map), docs/privacy.md, docs/sprint4_architecture.md, docs/operations_deployment.md,
docs/knowledge_runtime_architecture.md, 12 historical banners, capstone matrix/plan docs, code comments/docstrings (`api/schemas/career.py`,
`agent/tools.py`, `application/agent_service.py`, `application/__init__.py`, `application/errors.py`, `api/routes/memory.py`, `api/session_store.py`,
`auth.py`, `constants.py`, `frontend/lib/auth.ts`, `lib/tutorial/steps.ts`, `lib/i18n/catalog.ts`, `w96/index.ts`), public page metadata
(`frontend/app/page.tsx`: "eight languages"), 6 locale catalogues (diacritics), the consistency guard + test, CI step.

## 25-27. Verification and confirmations
Results are in the PR description. Runtime behaviour: unchanged (comments, docs, one SEO metadata string and diacritics in existing catalogue copy only).
Migration: none; Alembic head `0014_opportunities`. 0 paid/live calls.

## 28. Open items (unchanged)
PRIV-W9-01, PRIV-W9-02, TD-W9-01, TD-W9-02; native Russian and legal/privacy translation review; live generated-language validation; metadata
localization; locale/bundle optimisation.

## 29. W9.12 handoff (new findings beyond TD-W9-01/02)
1. Sign-in does not require a verified email (`login` checks password and status only): decide product policy; this is behaviour, not documentation.
2. Rate limiter is in-memory only (`RATE_LIMIT_BACKEND=redis` is recorded but not used); unsafe across replicas.
3. `src/auth.py` / `get_current_user` are legacy Streamlit-era code with no FastAPI callers: candidate for removal or clear isolation.
4. The original `/auth/account/delete-request` endpoint and `requestDeletion` client method are unused by the UI.
5. Interview evaluation scores are model-produced and only schema-validated; consider a deterministic consistency check between criteria and overall score.
6. Remaining phase-era comments saying "seven locales" in w96 fragment headers and test titles; remaining Sprint-era docs (`testing.md`, `reviewer_guide`) not audited line by line.
7. The Streamlit `DATA_RETENTION_NOTE` string and legacy UI are candidates for retirement.
8. Plus TD-W9-01 (Tailwind opacity tokens) and TD-W9-02 (full test-isolation audit).

## 30. Paid/live calls
0.
