# Capstone Acceptance Ledger (Current)

**Status:** PROPOSED CURRENT LEDGER, reconciled 2026-10-19 against `main` `4043429` (PR #204 merged, all 11 required checks success). It replaces **no** historical record: `p9_acceptance_ledger.md`, the requirements matrix and the RC-P10-003 artifacts stay exactly as written. This ledger combines the original requirement, the P9 disposition, later implementation, the integrated-requalification evidence, the latest actual tests and the open human or live dependencies, so that one document can be cited. Engineering dispositions only: **not owner acceptance, not course acceptance, not production approval.** Status vocabulary: PASS, PARTIAL, FAIL, NOT RUN. A feature merely existing never upgrades a status.

**Totals:** 17 PASS, 8 PARTIAL, 0 FAIL, 0 NOT RUN. Starting point (integrated requalification): 17 PASS, 8 PARTIAL. AC-03 and AC-18 were investigated explicitly and **stay PARTIAL**; no status was upgraded. P9 had recorded 18 PASS, 6 PARTIAL, 1 NOT RUN; changes since P9: AC-24 NOT RUN to PARTIAL (as the matrix and Pilot 2 documents already state), AC-19 PASS to PARTIAL (chromium only).

**Document contradictions found and left unedited:** the requirements matrix P9 block lists AC-03 inside 'AC-01 to AC-12 PASS' while its row B2-B3 and the P9 ledger say PARTIAL; the P9 ledger still says AC-24 NOT RUN; the matrix totals line is stale. This ledger is the proposed single reading.

Evidence classes: REAL (real local code, database or browser), OFFLINE (deterministic, scripted doubles), MOCKED (a double stands in for a provider), LIVE (a real provider call), HUMAN (real participants). Nothing here is PRODUCTION QUALIFIED.

## AC-01
- **Original requirement:** Register/provision, log in, log out, expire session. Backend verifies identity; logout/expiry prevents further protected access; recovery procedure documented
- **Previous status (P9 ledger):** PASS
- **Current engineering evidence:** Auth, session, logout and expiry suites; integrated test with a forged cookie and a database-expired session; Playwright auth spec. Full backend 5,054 passed on main 4043429's code.
- **Evidence classification:** REAL (local SQLite, in-process HTTP, browser)
- **Current verified disposition:** **PASS**
- **Outstanding qualification:** Google OIDC and live email are not validated live (DI-J J-OIDC, J-BREVO); production fail-closed identity is tested, not deployed.
- **Affects academic submission:** no · **Blocks production:** partly (OIDC and email live validation)
- **Required owner decision:** none
- **Sources:** tests/test_auth*.py; tests/test_integrated_requalification.py; frontend/e2e/auth.spec.ts

## AC-02
- **Original requirement:** Two independent users: direct IDs, list/search, downloads, jobs, events, retrieval, caches, feedback, checkpoint paths respect ownership for tested cases (extended to teams/sharing/exports/docs/stories/async by v3 amendment)
- **Previous status (P9 ledger):** PASS
- **Current engineering evidence:** Candidate A cannot read or mutate B (integrated test); W11 cross-plane suite; workspace and sharing isolation; Admin sentinel tests.
- **Evidence classification:** REAL
- **Current verified disposition:** **PASS**
- **Outstanding qualification:** Hosted multi-instance isolation not tested.
- **Affects academic submission:** no · **Blocks production:** no
- **Required owner decision:** none
- **Sources:** tests/test_authorization.py; test_workspaces_p6_5.py; test_integrated_w11.py; eval_workspace_security

## AC-03
- **Original requirement:** Profile and two opportunities: data persists after restart; chosen opportunity supplies correct context; old anonymous records not silently reassigned
- **Previous status (P9 ledger):** PARTIAL
- **Current engineering evidence:** Opportunity model (migration 0014), owner-scoped CRUD, JD link, session and interview association, historical NULL-opportunity rows stay valid, deletion preserves history; fail-closed identity in production. Verified by running the cited suites (all pass). NOT evidenced: (a) two opportunities for one user proving the chosen one supplies the context and the precedence order; (b) a restart test for opportunities, profile or memory (only interview sessions have restart tests); (c) a negative test that legacy or unowned rows are not adopted by the first new user; (d) a single test of the composite durable 'profile' (preferences, documents or evidence, memory).
- **Evidence classification:** REAL for what it covers; the requirement's clauses (a) to (d) have no test
- **Current verified disposition:** **PARTIAL (kept)**
- **Outstanding qualification:** Smallest closing evidence: one offline pytest on a file database, app built twice: two opportunities with different role, company and JD for user A; both persist across the restart; each context endpoint returns its own data and 404 for user B; a session launched from opportunity 2 carries only opportunity 2 and an explicit session field overrides it; plus one NULL-owner legacy row that a newly registered user neither sees nor owns.
- **Affects academic submission:** possibly (AC-25 consistency; the clauses are test gaps, not known defects) · **Blocks production:** no
- **Required owner decision:** OWNER: accept PARTIAL with the disclosed gap, or fund the small test wave
- **Sources:** docs/capstone/p9_acceptance_ledger.md row AC-03; capstone_requirements_matrix.md B2-B3; tests/test_opportunity_journey.py; tests/test_interview_api_durable.py; tests/test_auth_failclosed.py

## AC-04
- **Original requirement:** Complete and revisit Practice: generate report, leave, reopen from History, reload owned URL
- **Previous status (P9 ledger):** PASS
- **Current engineering evidence:** Interview and report suites, return-response and interview Playwright specs pass.
- **Evidence classification:** REAL
- **Current verified disposition:** **PASS**
- **Outstanding qualification:** Live interview quality is not human-rated (DI-C C-INT-HUMAN).
- **Affects academic submission:** no · **Blocks production:** no
- **Required owner decision:** none
- **Sources:** tests/test_interview_*.py; frontend/e2e/interview.spec.ts; return-response.spec.ts

## AC-05
- **Original requirement:** Pause and discover Practice: find unfinished session in UI and resume committed state
- **Previous status (P9 ledger):** PASS
- **Current engineering evidence:** Durable session store, discoverability and resume specs pass.
- **Evidence classification:** REAL
- **Current verified disposition:** **PASS**
- **Outstanding qualification:** none known
- **Affects academic submission:** no · **Blocks production:** no
- **Required owner decision:** none
- **Sources:** frontend/e2e/return-response.spec.ts; tests/test_durable_session_store.py

## AC-06
- **Original requirement:** Progress correctness: metrics match stored data and rubric context; sample size/empty states honest; memory distinct
- **Previous status (P9 ledger):** PASS
- **Current engineering evidence:** Progress correctness tests and Playwright progress spec; trend deliberately deferred and documented.
- **Evidence classification:** REAL
- **Current verified disposition:** **PASS**
- **Outstanding qualification:** Premium analytics narrative quality not human-reviewed (DI-C).
- **Affects academic submission:** no · **Blocks production:** no
- **Required owner decision:** none
- **Sources:** frontend/e2e/progress.spec.ts; tests/test_progress*

## AC-07
- **Original requirement:** Catalogue and knowledge readiness: safe source URLs work; unavailable processed data identified; citations refer to evidence actually used
- **Previous status (P9 ledger):** PASS
- **Current engineering evidence:** Knowledge readiness and source URL tests, eval_knowledge_governance; the catalogue/snapshot/live readiness distinction (matrix A5) is documented as PARTIAL.
- **Evidence classification:** REAL / OFFLINE
- **Current verified disposition:** **PASS**
- **Outstanding qualification:** A5 readiness distinction remains PARTIAL in the matrix.
- **Affects academic submission:** no · **Blocks production:** no
- **Required owner decision:** none
- **Sources:** eval_knowledge_governance; frontend/e2e/product-surfaces.spec.ts

## AC-08
- **Original requirement:** Upload supported documents: synthetic PDF, DOCX, TXT complete parsing/review/indexing with authentic page/section provenance
- **Previous status (P9 ledger):** PASS
- **Current engineering evidence:** Document pipeline suites and eval_documents_evidence (synthetic PDF, DOCX, TXT).
- **Evidence classification:** REAL / OFFLINE
- **Current verified disposition:** **PASS**
- **Outstanding qualification:** Real OCR accuracy not validated (DI-J J-OCR).
- **Affects academic submission:** no · **Blocks production:** no
- **Required owner decision:** none
- **Sources:** tests/test_documents_*.py; eval_documents_evidence

## AC-09
- **Original requirement:** Upload negative cases: corrupt, encrypted, scanned, oversized, malicious, unsupported inputs produce safe outcomes; no path traversal/uncontrolled parsing (scanned -> OCR path per amendment)
- **Previous status (P9 ledger):** PASS
- **Current engineering evidence:** Negative upload cases and malware fail-safe tests.
- **Evidence classification:** REAL / OFFLINE
- **Current verified disposition:** **PASS**
- **Outstanding qualification:** A real malware scanner is not configured (DI-B B-SCANNER).
- **Affects academic submission:** no · **Blocks production:** YES (real scanner)
- **Required owner decision:** none
- **Sources:** tests/test_documents_*; tests/test_p8_hardening*

## AC-10
- **Original requirement:** Correct, replace, delete document: corrections remain user amendments; replacement changes version; deletion revokes access and tracks derived-data cleanup
- **Previous status (P9 ledger):** PASS
- **Current engineering evidence:** Correct, replace and delete document tests.
- **Evidence classification:** REAL
- **Current verified disposition:** **PASS**
- **Outstanding qualification:** Per-version document deletion does not exist (DI-F).
- **Affects academic submission:** no · **Blocks production:** partly
- **Required owner decision:** none
- **Sources:** tests/test_documents_*.py

## AC-11
- **Original requirement:** Dictation coverage: every eligible input in inventory supports record/review/edit/insert/undo/typed fallback; exclusions justified
- **Previous status (P9 ledger):** PASS
- **Current engineering evidence:** eval_dictation_experience and dictation unit tests.
- **Evidence classification:** OFFLINE
- **Current verified disposition:** **PASS**
- **Outstanding qualification:** Live dictation providers not validated.
- **Affects academic submission:** no · **Blocks production:** no
- **Required owner decision:** none
- **Sources:** eval_dictation_experience; frontend/tests/dictation*

## AC-12
- **Original requirement:** Dictation race/error handling: typed text survives; stale results cannot overwrite; cancel/navigation/logout releases capture; nothing auto-submits
- **Previous status (P9 ledger):** PASS
- **Current engineering evidence:** Dictation race, error and cancel unit tests.
- **Evidence classification:** OFFLINE
- **Current verified disposition:** **PASS**
- **Outstanding qualification:** none known
- **Affects academic submission:** no · **Blocks production:** no
- **Required owner decision:** none
- **Sources:** frontend/tests/dictation*

## AC-13
- **Original requirement:** Real transcription: selected provider actually transcribes declared sample audio; mocked tests separately labelled
- **Previous status (P9 ledger):** PARTIAL
- **Current engineering evidence:** Deterministic speech-to-text path only; W12.4E added Whisper and Kyutai adapters with fixture engines; genuine execution NOT VERIFIED; live correction burden NOT RUN.
- **Evidence classification:** OFFLINE / MOCKED
- **Current verified disposition:** **PARTIAL (kept)**
- **Outstanding qualification:** Genuine Whisper execution and human correction-burden measurement (DI-E W12.4E-6, -13).
- **Affects academic submission:** no (deferred by owner) · **Blocks production:** YES
- **Required owner decision:** none (deferred post submission)
- **Sources:** docs/capstone/speech/W12_4E_GOVERNED_SPEECH_PROVIDERS.md; tests/test_speech_w12_4e.py

## AC-14
- **Original requirement:** Spoken Practice: question playback works; one explicit audio-answer submission produces one committed answer/evaluation; retry/reload and text fallback work
- **Previous status (P9 ledger):** PASS
- **Current engineering evidence:** Voice specs and eval_voice_experience (question playback, one explicit submission, text fallback).
- **Evidence classification:** OFFLINE / REAL browser (fake engines)
- **Current verified disposition:** **PASS**
- **Outstanding qualification:** Live voice quality NOT RUN; human review pending.
- **Affects academic submission:** no · **Blocks production:** partly
- **Required owner decision:** none
- **Sources:** frontend/e2e/voice.spec.ts; eval_voice_experience

## AC-15
- **Original requirement:** Specialist cooperation: Research and Candidate specialists execute distinct bounded tasks; Mo combines traceable structured findings
- **Previous status (P9 ledger):** PASS
- **Current engineering evidence:** Specialist tests and eval_multi_agent; live agent benchmark (P10E) completed 22 of 22 cases (tool selection 0.773 aggregate; per-case outcomes for 6 cases recorded in R1).
- **Evidence classification:** OFFLINE + LIVE (partial)
- **Current verified disposition:** **PASS**
- **Outstanding qualification:** Live comparison against thresholds does not exist; no owner thresholds.
- **Affects academic submission:** no · **Blocks production:** no
- **Required owner decision:** none
- **Sources:** tests/test_multi_agent_specialists.py; eval_multi_agent; docs/capstone/p10/P10E_R1_CORE_LIVE_QUALIFICATION.md

## AC-16
- **Original requirement:** Agent failure boundaries: timeout, cancellation, budget exhaustion, invalid tools, insufficient/conflicting evidence, HITL replay handled without unsafe side effects
- **Previous status (P9 ledger):** PASS
- **Current engineering evidence:** Agent failure-boundary tests (timeout, cancellation, budget, invalid tools, HITL replay); provider-failure degradation in the integrated suite.
- **Evidence classification:** OFFLINE / REAL
- **Current verified disposition:** **PASS**
- **Outstanding qualification:** none known
- **Affects academic submission:** no · **Blocks production:** no
- **Required owner decision:** none
- **Sources:** tests/test_agent_*.py; tests/test_integrated_requalification.py

## AC-17
- **Original requirement:** Integrated preparation handoff: reviewed docs/profile/memory reach right opportunity and typed Practice context after approval; no duplicate session
- **Previous status (P9 ledger):** PASS
- **Current engineering evidence:** Handoff specs and backend handoff tests.
- **Evidence classification:** REAL
- **Current verified disposition:** **PASS**
- **Outstanding qualification:** none known
- **Affects academic submission:** no · **Blocks production:** no
- **Required owner decision:** none
- **Sources:** frontend/e2e/home-handoff.spec.ts; tests/test_agent_journey_p4.py

## AC-18
- **Original requirement:** Review surfaces: owned recent runs, safe specialist events, bounded retrieval evidence, actual stored evaluation artifacts inspectable; missing data clear
- **Previous status (P9 ledger):** PARTIAL
- **Current engineering evidence:** Verified by code reading and by running the cited suites: owner-scoping of a run read by id is proven; the Inspector shows safe events for a run id the viewer supplies; evaluation artifacts are viewable by Admin only since W9.3; missing and foreign runs show a safe error. NOT evidenced: (a) an owner-scoped LIST of recent agent runs (no GET /agent/runs route and no UI list; matrix row A6 ABSENT and the code agrees); (b) selected-run retrieval evidence shown to be bounded or itemised (A8: only an overview); (c) a test of the empty evaluation-artifact state. Note: W9.3 made review surfaces admin-only, which narrows the original candidate-facing 'owned runs' intent.
- **Evidence classification:** REAL for by-id inspection; the requirement's clauses (a) to (c) have no implementation or test
- **Current verified disposition:** **PARTIAL (kept)**
- **Outstanding qualification:** Smallest closing evidence: add an owner-scoped, paginated, capped `GET /agent/runs` and a recent-runs list in the Inspector with a pytest proving user A sees only own runs (and Admin sees none of A's), plus a vitest or e2e for the list, the empty state and a selected run's capped evidence. This is a feature change, deliberately not done in this documentation wave.
- **Affects academic submission:** possibly (AC-25 consistency) · **Blocks production:** no
- **Required owner decision:** OWNER: accept PARTIAL with the disclosed gap, or schedule a small feature wave
- **Sources:** p9_acceptance_ledger.md row AC-18; capstone_requirements_matrix.md A6, A8; src/api/routes/agent.py; frontend/components/agent/AgentInspector.tsx; tests/test_review_diagnostics_authz_w9_3.py

## AC-19
- **Original requirement:** Core interface: pages render without clipping/overlap; keyboard use, readable contrast, truthful states, declared browser/viewport coverage
- **Previous status (P9 ledger):** PASS
- **Current engineering evidence:** Chromium Playwright 412 passed including mobile no-overflow, keyboard and accessibility specs; browser and viewport coverage documented. No real-device, cross-browser or screen-reader testing; Opera voice failure P2-09 unreproduced.
- **Evidence classification:** REAL (chromium only)
- **Current verified disposition:** **PARTIAL (changed from PASS: the original requirement names declared browser and viewport coverage and readable contrast, and only chromium is evidenced)**
- **Outstanding qualification:** Cross-browser and real-device runs, automated contrast audit, real screen-reader testing (DI-G G-SR, G-CONTRAST, G-HDR-390).
- **Affects academic submission:** possibly · **Blocks production:** no
- **Required owner decision:** OWNER: accept chromium-only disclosure for the academic scope
- **Sources:** frontend/e2e/w11-visual-a11y.spec.ts; P10B_RELEASE_ACCEPTANCE_MATRIX R-52, R-98

## AC-20
- **Original requirement:** Restart and recovery: documented local startup works; committed state survives restart; disposable backup restore and selected DB/checkpointer migrations pass
- **Previous status (P9 ledger):** PASS
- **Current engineering evidence:** Local startup, restart recovery evaluator, migration tests and a single Alembic head `0039_speech_governance`; PostgreSQL migration-chain evidence from P5-B; hosted restore is EX-12.
- **Evidence classification:** REAL (local disposable)
- **Current verified disposition:** **PASS**
- **Outstanding qualification:** Hosted restore, rollback, TLS and backups NOT RUN (EX-12, DI-H).
- **Affects academic submission:** no (if local demonstration is acceptable: owner question) · **Blocks production:** YES (hosted operation)
- **Required owner decision:** OWNER: does the course require hosting (see the scope decision)
- **Sources:** eval_restart_recovery; tests/test_migrations.py; docs/capstone/p8_hosting_operations.md

## AC-21
- **Original requirement:** Required regression gate: actual required tests/build/contracts/security checks pass for release code; skips/failures visible
- **Previous status (P9 ledger):** PASS
- **Current engineering evidence:** Re-measured: backend 5,054 passed / 34 skipped / 0 failed; vitest 1,082; Playwright 412; 52 of 52 CI evaluator commands; Ruff, compileall, git diff --check, shard verification clean; GitHub CI 11 of 11 checks success on PR #204's head. Must be re-run on the candidate SHA of any RC.
- **Evidence classification:** REAL
- **Current verified disposition:** **PASS**
- **Outstanding qualification:** Re-run on the RC-P10-004 candidate if one is created.
- **Affects academic submission:** no · **Blocks production:** no
- **Required owner decision:** none
- **Sources:** docs/capstone/INTEGRATED_CANDIDATE_ADMIN_OPERATIONS_REQUALIFICATION.md section 12

## AC-22
- **Original requirement:** Agent/retrieval evaluation: same-version baseline comparisons with stated denominators; new cases separate; live advantage claimed only when measured
- **Previous status (P9 ledger):** PARTIAL
- **Current engineering evidence:** Agent and KB live evidence executed in P10E, R1, R2 (285 of 300 calls, same-version, small samples); deterministic baselines; RAGAS live and semantic calibration NOT RUN; coverage BELOW GATE; no owner thresholds.
- **Evidence classification:** OFFLINE + LIVE (partial)
- **Current verified disposition:** **PARTIAL (kept)**
- **Outstanding qualification:** Same-version baseline comparisons with stated denominators across profiles; RAGAS live; semantic calibration (DI-B B-SEMCAL, B-RAGAS-*); owner thresholds.
- **Affects academic submission:** possibly · **Blocks production:** no
- **Required owner decision:** OWNER: thresholds (none invented)
- **Sources:** docs/capstone/p10/P10E_LIVE_CAPABILITY_VALIDATION.md; P10E_R1; P10E_R2

## AC-23
- **Original requirement:** Voice measurement: defined sample, reference transcripts, correction burden, measured latency with environment/provider limits
- **Previous status (P9 ledger):** PARTIAL
- **Current engineering evidence:** EN/DE reference set and deterministic latency; live speech-to-text and latency NOT RUN; human speech quality NOT VERIFIED.
- **Evidence classification:** OFFLINE
- **Current verified disposition:** **PARTIAL (kept)**
- **Outstanding qualification:** Live measurement and human review (DI-E, DI-L).
- **Affects academic submission:** no (deferred by owner) · **Blocks production:** YES
- **Required owner decision:** none
- **Sources:** docs/capstone/p9_voice_measurement.md

## AC-24
- **Original requirement:** Pilot and lessons: actual participant observations distinguished from internal review; consequential fixes receive regression checks. Operational checklist (pilot_lessons_template): >=3 actual participants; identified RC; anonymised observations; participant findings vs internal separate; lessons synthesised; consequential fixes regression-tested (NEW RC if runtime changed); unresolved issues disclosed; no fabricated/LLM participant responses
- **Previous status (P9 ledger):** NOT RUN
- **Current engineering evidence:** n=3 complete structured Pilot 2 sessions on RC-P10-003; anonymised; lessons synthesised; issues disclosed; fixes P2-01..04 regression-tested. No successor RC exists; P10F human revalidation deferred.
- **Evidence classification:** HUMAN (historical, 3 participants) + OFFLINE regression
- **Current verified disposition:** **PARTIAL (kept)**
- **Outstanding qualification:** Successor RC and rerun release gate; human revalidation (P10F); the owner decision on whether AC-24 may close without P10F.
- **Affects academic submission:** UNKNOWN (owner) · **Blocks production:** no
- **Required owner decision:** OWNER: see the AC-24 decision record in the scope decision document
- **Sources:** docs/capstone/p10/pilot2/; RC_P10_003_PILOT2_TRIAGE.md

## AC-25
- **Original requirement:** Submission consistency: README, three decks, selected ten-minute path, script, Q&A, ethics, results, demo fallback and limitations match actual release
- **Previous status (P9 ledger):** PARTIAL
- **Current engineering evidence:** README, three decks, ten-minute path, script, Q&A, ethics report, results report, demo fallback and limitations are not produced; P11 NOT STARTED. Matrix and documents are truthful.
- **Evidence classification:** n/a (documentation)
- **Current verified disposition:** **PARTIAL (kept; depends on P11)**
- **Outstanding qualification:** P11 artifacts; consistent acceptance documents (this ledger is the proposed single current ledger).
- **Affects academic submission:** YES · **Blocks production:** no
- **Required owner decision:** OWNER: approve this ledger as the single current acceptance record
- **Sources:** P11_SUBMISSION_READINESS_PLAN.md

## Additional gates (not re-dispositioned here)
EX-01 to EX-16, CAP-01 to CAP-12, the W9 gate set and the R-01 to R-99 matrix keep their last documented dispositions (see `PRE_SUBMISSION_ACCEPTANCE_GATES.md` section 2 and the register categories E, H, I, J, K). They are not folded into the AC totals above.
