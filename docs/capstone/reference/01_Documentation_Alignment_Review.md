# Ask4Mo documentation alignment review

Reviewed 23 September 2026. Repository: `moaltamimi-unbiasedtalent/Intelligent-Interview-Coach`.

## Verdict

**Ready to start the Capstone baseline phase. Not yet a fully reconciled reviewer package.** The latest code closes several genuine Sprint 4 product gaps, and PR #72 has five successful CI jobs. The remaining issues below concern documentation accuracy, demo provisioning and release provenance. This review does not certify the current local installation, external providers or production deployment.

Scope: the newly downloaded 401-commit repository, its reviewer documentation and implementation, the previously supplied project/course text, and the seven-document v2 delivery package in this workspace. No new attachment was included in the latest message. Application source and remote repository were not modified. The original snapshot and v2 documents are preserved.

## Verified baseline and evidence

| Item | Finding | Evidence class |
|---|---|---|
| Latest main | `4f273dd9c190bf016d70d7c7a9fbaee4f411e9d5`, 401 reachable commits | Fresh clone and remote ref |
| Latest merge | PR #72, guided product tutorial, merged 22 September | GitHub PR metadata |
| Historical release | `sprint4-submission-ready` still resolves to `1b084cb1626a137a2e8bef61a3c3dd2d4be72b47` | Git tag resolution |
| Delta since release | 12 commits, 60 changed files, including product surfaces and runtime capability control | Git comparison |
| PR #72 CI | Five jobs successful: Python, frontend, Legacy Live, Next.js Playwright, Legacy Streamlit smoke | GitHub Actions jobs at PR head `a6dbf2b` |
| Current local frontend | 176 tests passed in 33 files; TypeScript check passed | This review, detached `4f273dd` snapshot |
| Browser suite inventory | 60 tests in 12 files | Test discovery only locally, not a local execution |
| Current main push CI | Not independently established | PR jobs are not a substitute for main-push results |
| Python total | Closure documentation reports 2145 passed / 3 skipped | Historical reported total, not a local rerun |

CI sources: [PR #72](https://github.com/moaltamimi-unbiasedtalent/Intelligent-Interview-Coach/pull/72), [CI run](https://github.com/moaltamimi-unbiasedtalent/Intelligent-Interview-Coach/actions/runs/35734836396), [Browser E2E run](https://github.com/moaltamimi-unbiasedtalent/Intelligent-Interview-Coach/actions/runs/35734836443).

Local test caveats: reused the existing frontend dependencies after confirming identical lockfiles. The unit run emitted React `act(...)` warnings in diagnostics/provenance tests and a Vite deprecation warning. These did not fail the suite. A local browser server could not bind a port in this environment. Python test dependencies were unavailable, so no local Python pass is claimed. No paid provider call or new golden rehearsal was run.

## Corrections required before presenting the package as fully aligned

### 1. The v2 Capstone backlog now includes delivered work

**Priority: correct before sending implementation prompts.** A1 History detail, A3 basic Progress, A4 source links, A7 evaluation UI, the overview portion of A8 RAG diagnostics, and C10 guided onboarding now have implementations. The v2 scope matrix and master/P2/P6/P8 prompts still describe several as missing or optional future work.

Change those instructions to **preserve, regression-test and adapt to verified accounts**, with only the remaining gaps scheduled. A2 active-session discovery, A6 owned recent-run discovery, live readiness distinctions and selected-run retrieval evidence remain relevant. The RAG overview is not a full per-run inspector.

Sources: [History client](https://github.com/moaltamimi-unbiasedtalent/Intelligent-Interview-Coach/blob/4f273dd/frontend/components/interview/HistoryClient.tsx), [Progress](https://github.com/moaltamimi-unbiasedtalent/Intelligent-Interview-Coach/blob/4f273dd/frontend/components/progress/PracticeProgress.tsx), [tutorial documentation](https://github.com/moaltamimi-unbiasedtalent/Intelligent-Interview-Coach/blob/4f273dd/docs/guided_tutorial.md). Local correction guide: `02_Updated_Transition_Guide.md`.

### 2. Test totals and canonical release labels disagree

`docs/sprint4_submission_summary.md:96–98` and `docs/sprint4_final_evidence.md:3–13` retain 1928 Python / 155 frontend / 51 browser tests. `docs/final_submission_readiness.md:74–75` records 2137 / 155 / 51, while the closure audit records 2145 / 166 / 57. Current local frontend testing gives 176, and 60 browser tests are discoverable.

Do not overwrite historical evidence with a newly inferred total. Add a single current evidence table with exact code state, date, execution mode and source. Label prior tables as historical. README currently calls the old evidence sheet “current verified test/eval numbers”; that label needs correction. Confirm exact Python and browser totals from the relevant CI logs before quoting them as current executed totals.

Source: [old results table](https://github.com/moaltamimi-unbiasedtalent/Intelligent-Interview-Coach/blob/4f273dd/docs/sprint4_submission_summary.md#results).

### 3. Evaluation UI exists, but the deterministic baseline is not what it reads

`src/application/evaluation_service.py:18–55` reads `evaluations/ragas/runs/*/results.json`. Those runs are ignored and absent from this fresh clone. The committed `evaluations/ragas/deterministic_baseline.json` has a different schema and is not read by that route. It records deterministic ID precision **0.6757** and recall **0.5161**, with source code SHA `7a9b97e`, 35 cases and differing applicable-case counts.

Therefore the implementation-story claim that these deterministic results are “now visible” at `/review/evaluation` is not supported for a clean checkout. The page correctly offers an empty state, but documentation must explain the local-artifact prerequisite. Choose later between a separately labelled deterministic-artifact reader or provisioning an actual compatible stored run. Never relabel the deterministic baseline as a paid judge run or fabricate results.

Sources: [reader](https://github.com/moaltamimi-unbiasedtalent/Intelligent-Interview-Coach/blob/4f273dd/src/application/evaluation_service.py#L18), [baseline](https://github.com/moaltamimi-unbiasedtalent/Intelligent-Interview-Coach/blob/4f273dd/evaluations/ragas/deterministic_baseline.json), [claim](https://github.com/moaltamimi-unbiasedtalent/Intelligent-Interview-Coach/blob/4f273dd/docs/sprint4_deliverable_implementation_stories.md#optional-21--ragas).

### 4. Knowledge diagnostics show snapshots, not a live readiness check

`knowledge_service.py:16–18,28–84` reads `data/knowledge/build_metadata.json`, `evaluations/knowledge/retrieval_after.json` and a coverage report. The first two files are ignored and absent in this clone, contrary to the UI footer's “committed evidence artifacts” wording. Counts default to missing values. Even a populated build snapshot does not prove the currently mounted stores are usable.

Correct the wording to distinguish configured source catalogue, locally generated build snapshot, offline evaluation and actual retrieval readiness. Require `scripts/check_demo_knowledge.py` on the demo machine. Run it only with the proper dependencies and provisioned data, then record its result. Do not create zero-filled or sample production statistics.

Sources: [diagnostics projection](https://github.com/moaltamimi-unbiasedtalent/Intelligent-Interview-Coach/blob/4f273dd/src/application/knowledge_service.py#L16), [UI footer](https://github.com/moaltamimi-unbiasedtalent/Intelligent-Interview-Coach/blob/4f273dd/frontend/components/review/RagDiagnosticsClient.tsx#L123), [.gitignore](https://github.com/moaltamimi-unbiasedtalent/Intelligent-Interview-Coach/blob/4f273dd/.gitignore#L49).

### 5. The post-release closure changed agent runtime behaviour

`docs/post_release_product_surface_audit.md:135–138` says no Agent runtime changed. The same closure introduces server-enforced exclusion/rejection of `ResearchCurrentMarket`. `nodes.py` and `registry.py` change the bound tool schemas and tool execution behaviour. This is a legitimate, bounded feature, but it is a runtime change.

State that the original golden evidence belongs to its recorded code (`afb4f45`) and historical release lineage, while the current candidate includes later changes with their own regression evidence. Preserve the old tag. Do not transfer the original golden PASS or 0 P0/P1 statement into a new current-code certification without new evidence and any required authorization.

Sources: [closure claim](https://github.com/moaltamimi-unbiasedtalent/Intelligent-Interview-Coach/blob/4f273dd/docs/post_release_product_surface_audit.md#completion-audit--sprint-4-deliverables-closure-addendum), [current nodes](https://github.com/moaltamimi-unbiasedtalent/Intelligent-Interview-Coach/blob/4f273dd/src/agent/nodes.py), [golden record](https://github.com/moaltamimi-unbiasedtalent/Intelligent-Interview-Coach/blob/4f273dd/docs/final_live_golden_result.md).

### 6. Smaller, but reviewer-visible contradictions remain

- Reviewer guide lines 233–234 calls memory management, journey chrome, feedback and external research follow-ups, although subsequent sections and code implement them. Add historical scope labels or replace the obsolete statement.
- Requirements matrix line 32 says Deep-Dive feedback is out of scope. `DeepDivePanel.tsx:75,109` displays branch evaluation. Distinguish this from candidate helpful/not-helpful ratings if that was the intended missing capability.
- Technical critique line 35 calls deterministic RAGAS ID values “generation-quality numbers.” These are retrieval ID metrics. Paid semantic judging remains unrun.
- `CLAUDE.md` labels itself current but begins its architecture section with “Modular Streamlit monolith.” Put the current Next.js/FastAPI/application-layer/LangGraph architecture first and clearly label historical phases. Keep Streamlit legacy/development only.
- The critique's broad coverage claim should preserve the narrower golden caveat: insufficient evidence for the selected software-engineering scenario, not proof that every software-engineering role has no citable evidence.

## What now works in code

| Capability | Current implementation | Boundary |
|---|---|---|
| Completed History | Clickable rows, owned detail route, report renderer | Requires completed data for the same identity |
| Progress | Completed-session aggregates, recent links and approved memory | No longitudinal trend chart; zero sessions hides the practice panel |
| Sources | Safe public links and inspectable provenance | No fabricated public links or guaranteed answer citations |
| Evaluation | Read-only stored-run view with empty/error states | Compatible local results must exist |
| Knowledge & RAG | Build/evaluation projection and known gaps | Snapshot data, not a fresh retrieval health probe |
| Guidance | 12-step route-aware tour, searchable Help Center, contextual links | Preference state stays in the browser, not synced accounts |
| Capability control | Current-market tool excluded from schemas and rejected on invocation when disabled | One controlled capability, not a plugin marketplace |

## Readiness checklist

1. Reconcile the current documentation using the bounded prompt in the transition guide.
2. Freeze an exact reviewer code SHA and preserve the original Sprint 4 tag.
3. Record PR CI separately from main-push CI and local checks.
4. Provision the knowledge stores and run the documented no-provider readiness probe on the demo installation.
5. Use a synthetic account with an actual completed interview for History/Progress; disclose synthetic data.
6. Explain missing evaluation runs honestly or intentionally implement a separately labelled deterministic evidence reader.
7. Walk through the return journey, safe links, tour, and diagnostics in the actual local installation.
8. Keep local-only acceptance, weekly capacity and paid API budget as explicit decisions for the course lead/owner.

**Final decision:** proceed with P0 and preserve the new work. Resolve these alignment items before claiming the complete package is reviewer-ready. No new product features or documentation fixes have been applied to the remote repository by this review.
