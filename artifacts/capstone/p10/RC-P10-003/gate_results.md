# RC-P10-003 — Gate Results

_Safe/non-private evidence summary. This artifact is evidence ABOUT the candidate; it is not the candidate. RC-P10-003 is the current candidate only when this directory is present on main. W11 did NOT create this RC: it is created by a separate owner-approved post-W11 action. Artifact RC only: no Git tag, no version bump, no deployment._

Candidate SHA: `54aad500ec937b4828984c32c64b77746534633d`
Qualified runtime merge: `d27993d7f2757cf7605355e3f76c71dac6f85c10` (PR #132; feature head `654ca47ab603fe96d093e10faaa778f5f5ab2e33`). PR #133 (docs head `98c79c8883607cdc088797e11c4f7b82e83130dd`) is documentation-only, so the runtime at the candidate SHA is the qualified W11 runtime.

W11: **COMPLETE AND INTEGRATED** — P10B INTEGRATED QUALIFIED.

Matrix: **99 requirements — 88 PASS, 11 ACCEPTED, 0 BLOCKER** (R-52 PASS, R-98 PASS, R-99 PASS).

## Gate table
| Gate | Result |
|---|---|
| Backend (main tree) | **3145 passed, 4 skipped, 0 failed, 0 errors** |
| Frontend unit (Vitest) | **768 passed (89 files)** |
| Playwright | **239 passed** |
| Typecheck | clean |
| Lint | clean |
| Build | clean |
| i18n scanner | **0 offenders** |
| Ruff | clean |
| compileall | clean |
| CI evaluators | **42 / 42** at W11 close (this artifact PR adds `eval_rc_p10_003.py`) |
| W11 evaluator | **27 checks PASS** at W11 close |
| Alembic | single head `0025_security_audit_incidents`; base→0025, 0025→0024 downgrade and re-upgrade PASS; append-only triggers present; no qualification seed rows |
| Fresh checkout | backend **3138 passed, 11 skipped, 0 failed**; Vitest 768; Playwright 239; evaluators 42/42; Ruff, compileall, typecheck, lint, build, i18n clean; no developer stores created |
| GitHub CI | PR #132 final head: CI PASS, Browser E2E PASS. PR #133 final head: CI PASS, Browser E2E PASS (after one same-commit rerun, below) |
| Secret/privacy sentinels | private-content and secret sentinels never reach any Admin read surface or candidate response (W11 integrated tests) |
| Paid/live calls | **0** |

## Skips (not hidden)
Normal tree (4): 1. live Adzuna (opt-in/credentials) · 2. PostgreSQL W10.9 claim test (needs disposable `TEST_POSTGRES_URL`) · 3. Streamlit component test (needs Streamlit context) · 4. RAGAS adapter (conditional).

Fresh checkout (11): 1. live Adzuna · 2. PostgreSQL claim test · 3. RAGAS optional package · 4. real OCR optional extras · 5. O*NET dataset · 6. ESCO dataset · 7. OOH dataset · 8. BLS EP dataset · 9. CLSSI dataset · 10. Eurostat JVS dataset · 11. DigComp dataset. **0 blockers.**

## ACCEPTED limitations (11) — carried, not completed
| ID | Limitation | Status | Next validation / hardening |
|---|---|---|---|
| R-33 | Email verification is not required to sign in | ACCEPTED | post-RC product/policy decision |
| R-38 | Legacy Streamlit is retained | ACCEPTED | post-Capstone cleanup |
| R-46 | Distributed Redis rate limiting exists as an adapter but is not live validated | ACCEPTED | production-hardening phase / separately authorised live run |
| R-49 | Native/legal language review is pending | ACCEPTED | native/legal review (owner-supplied reviewers) |
| R-50 | Live generated-language validation requires a separately authorised live run | ACCEPTED | separately authorised live run |
| R-51 | Metadata localization / bundle optimization remains post-P10B optimization work | ACCEPTED | post-P10B optimization |
| R-93 | Support attachments are not implemented | ACCEPTED | post-Capstone |
| R-94 | Admin workspace deactivation and universal operator search are not built | ACCEPTED | post-Capstone |
| R-95 | Live billing, production secret vault and external paging are absent | ACCEPTED | later production-hardening phase |
| R-96 | PostgreSQL-only paths have not been exercised against a disposable/live PostgreSQL qualification environment | ACCEPTED | separately authorised PostgreSQL qualification run |
| R-97 | Google OIDC live behaviour is not validated | ACCEPTED | separately authorised run with a provider account |

These are accepted limitations, not blockers, and none is claimed complete. The product is not described as fully production-ready.

## CI history
### CI-W11-01
GitHub's main CI workflow was invalid from W10.11 through W10.14 / early W11 because of YAML parsing (an unquoted colon-space in a step name). The separate Browser E2E workflow did run. Local and fresh-checkout qualification for those waves remains valid; earlier wording implying every GitHub CI job executed was inaccurate. W11 repaired it (R-99 PASS) and PR #132 proved CI executes and passes.

### PR #133 infrastructure rerun
The first Browser E2E attempt failed before any test ran, during `npx playwright install --with-deps chromium`, because `packages.microsoft.com` returned HTTP 403. A rerun on the SAME commit passed. No source change. Classified as external CI infrastructure, not a product defect.

## Environmental evidence (not part of the candidate identity)
Pre-RC developer baseline, captured after normal post-W11 developer app use and after the app servers were stopped; it is NOT the W11 qualification baseline, and no restoration was performed: dev DB `81eef3479704ed91e58abb876926f98108968842`; schema 224 sqlite_master objects; checkpoint `b56d0c39fbba64786495ebb5db59eedecfae5c71`; Chroma `6357c057606273f313b408cc7f144390453a0832`; research cache `25264b17b36f7a365ff8dfaca9eec97e997ee710` (accepted post-incident value, see RC-QUAL-ENV-01); evaluations `67259aba185daa495f8bf8958e1c905fd086b2be`. The W10.13 contamination disclosure ("disclosed contamination with stable post-incident qualification baseline") remains permanent.

## Qualification-environment incident (RC-QUAL-ENV-01) — unisolated legacy evaluator
During the targeted RC-P10-003 evaluator run, the legacy `scripts/eval_release_candidate.py` executed company research for the deterministic fixture company `Acme` without first loading the test-isolation bootstrap. It wrote one cache entry: `data/cache/external/be293349a0419d930134b8c6.json`. The research-cache fingerprint changed `a3ad0eea16f2fadd337bba0ce2fd5ea6a88b1dc8` -> `25264b17b36f7a365ff8dfaca9eec97e997ee710`. No other protected store changed. The evaluator was corrected to bootstrap test isolation before application imports (and 19 further evaluators lacking the same import received it; `eval_rc_p10_003.py` now enforces the rule for every `scripts/eval_*.py`). No cache entry was deleted and no cache state was restored; the file is environment state, not RC evidence, and is not committed. The post-incident fingerprint is the accepted pre-RC baseline. Classification: RC qualification contamination caused by an unisolated legacy evaluator; corrected before RC creation. This is separate from the permanent W10.13 dev-DB disclosure and from the post-W11 interactive app-use drift. The pre/post store comparison of the first targeted run is therefore NOT clean; stability is proven against the new baseline from the corrected run onward. Scope note: the rule covers every CI evaluator (43). Seventeen manual/non-CI evaluators (eval_agent_judge, eval_agent_live, eval_company_intelligence, eval_expanded, eval_external_research, eval_faithfulness_v2, eval_feedback_intelligence, eval_knowledge_retrieval, eval_onboarding_personalisation, eval_opportunity_journey, eval_prepare_practice_integration, eval_quality_v2, eval_rag, eval_ragas, eval_retrieval, eval_retrieval_quality_v2, eval_security) do not bootstrap isolation; they are not run by CI, some are live/opt-in by design, and they are listed as a known follow-up rather than changed here.

## Boundaries
Pilot 2 remains PAUSED. P10C is NOT STARTED. Public launch is NOT AUTHORIZED. Live provider validation was NOT RUN.
