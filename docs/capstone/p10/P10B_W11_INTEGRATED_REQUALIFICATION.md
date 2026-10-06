# P10B-W11 - Integrated Candidate + Admin Requalification

## 1. Status
**Implemented and qualified on branch `release/p10b-w11-integrated-requalification`; COMPLETE only after merge.** W11 remained primarily a QUALIFICATION wave: no product feature, no backend product-logic change, no migration, no new permission, no new dependency, no entitlement, billing, security or privacy behaviour change, 0 paid/live calls. **One bounded P3 responsive-layout defect found by W11 (LAYOUT-W11-01) was corrected, with explicit owner approval, in three shared frontend layout files** (see section 14A). **RC-P10-003 has NOT been created, Pilot 2 remains paused, P10C has not started.**

## 2. Starting main
`fefb8191f9383d64656ea67a1fce753dc32112e4` (W10.14 integrated; Alembic head `0025_security_audit_incidents`).

## 3. W10.14 PR #130
Feature head `cfc482846cf7cff6b3d01f9b643c194d11aa40c7`, merge `ba5808658d11eef9ef3b840e4eda2661e84c7b0e`.

## 4. W10.14 docs PR #131
Head `01d97caef5621c9c2f4e784a718fcacb232f067d`, merge/main `fefb8191f9383d64656ea67a1fce753dc32112e4`. The W10.14 document now records it (the one known omission).

## 5. Branch
`release/p10b-w11-integrated-requalification`.

## 6. Purpose
Prove that the remediated candidate product and the qualified Admin control plane work TOGETHER on the same tree: no cross-plane regression, privilege leak, privacy regression, entitlement/billing coupling, localization regression or qualification-environment contamination. The question W11 answers: is the repository engineering-ready for a SEPARATE RC-P10-003 creation step?

## 7. Fresh-checkout methodology
A detached `git worktree` of the committed W11 tree started with NO `.venv`, NO `node_modules`, NO `.next`, NO `.env`, no developer DB, no checkpoint, no Chroma, no research cache and no qualification artifacts (only tracked data). A fresh Python 3.11 virtual environment was created and `pip install -e ".[dev,db,speech,live]"` (the CI extras) ran from scratch; the frontend was installed with `npm ci`. From that checkout ran: the complete backend suite, the complete Vitest suite, typecheck, lint, production build, the i18n scanner, the complete Playwright suite, the exact CI evaluator set (every `scripts/eval_*.py` named in `.github/workflows/ci.yml`), Ruff, compileall, a fresh-database migration check and the release-matrix evaluator. The fresh run was made at the final committed corrected tree before the evidence text of this document was last refreshed; the only later change is this document (documentation only), after which the release-matrix evaluator, the W11 evaluator, the documentation-consistency evaluator and the protected-store fingerprints were re-checked.

## 8. Environment
Darwin 27.0.0 (macOS 27.0, Apple silicon); Python 3.11.15; Node v24.15.0 (CI uses Node 20: difference recorded); npm 11.12.1; pytest 8.4.2; SQLAlchemy 2.1.3; Ruff 0.16.10; FastAPI 0.142.2; Alembic 1.20.0; Pydantic 2.13.5; LangGraph 0.3.34; ChromaDB 0.6.3; TypeScript 5.9.3; Vitest 2.1.9; Playwright 1.63.0 (browser binary reused from the machine's Playwright cache); Next.js 15.5.25. Provider and database configuration: the host shell exposed no provider, database or secret variables and the fresh checkout had no `.env`; test isolation (`tests/conftest.py`) neutralises them regardless. No credential value was printed. 0 paid/live provider credentials are required.

## 9. Integrated acceptance matrix summary
`docs/capstone/p10/P10B_RELEASE_ACCEPTANCE_MATRIX.md` is now the integrated gate: 99 requirements: 88 PASS, 11 ACCEPTED, 0 BLOCKER. History is preserved (R-01..R-52 originated in W9.13). `scripts/eval_release_matrix.py` recomputes the totals and checks every evidence path.

## 10. Candidate matrix requalification
All 52 W9.13 rows were re-evaluated against the W11 tree (evidence paths exist; the suites that back them ran in the fresh checkout). Stale wording was corrected: R-26/R-28 (PRIV limitations closed), R-35 (isolation bootstrap), R-39 (Alembic head `0025`), R-40..R-45 (W11 evidence). Results changed only where evidence changed (section 11).

## 11. Historical ACCEPTED reconciliation
| Row | W9.13 result | W11 result | Basis |
|---|---|---|---|
| R-47 PRIV-W9-01 | ACCEPTED | **PASS** | Closed in W10.10 (ownership index, indexed deletion, no checkpoint scan); verified by `tests/test_privacy_legal_w10_10.py`, `scripts/eval_admin_privacy_legal.py` and the integrated deletion test |
| R-48 PRIV-W9-02 | ACCEPTED | **PASS** | Closed in W10.10 (versioned legal documents, recorded acceptance, never back-filled) |
| R-52 `/practice` h1 (A11Y-W9-13-01) | ACCEPTED | **PASS** | Not reproducible: a fully rendered `/practice` has an `h1` in de/ru, desktop/mobile, light/dark; the page source has not changed since W9.7 (before W9.13), so the W9.13 observation was most likely taken on a not-yet-rendered state. The W9.13 report is not rewritten. *Owner: please confirm this retirement.* |
| R-33 POLICY-01 | ACCEPTED | ACCEPTED | sign-in still does not require a verified email (pinned by tests) |
| R-38 LEGACY-01 | ACCEPTED | ACCEPTED | the legacy Streamlit app is retained |
| R-46 | ACCEPTED | ACCEPTED | distributed Redis rate limiting is still not live |
| R-49, R-50, R-51 | ACCEPTED | ACCEPTED | native/legal review, live generated-language validation, metadata/bundle optimisation remain open |

## 12. Admin acceptance rows
R-53 to R-80 (28 release-significant Admin requirements: candidate/Admin separation, 43-permission registry, least-privilege presets, no private-data superuser, support-content scope, no break-glass, no impersonation, secret non-disclosure, audit fail-closed and append-only, two-person role changes, step-up, entitlement/billing separation, mock-billing truthfulness, integrations, AI, knowledge, jobs, privacy/legal, pause, flags, reporting, AI economics, security, route coverage, navigation, overclaims), each with real evidence paths.

## 13. Accepted current limitations
| Row | Limitation | Rationale | Blocking? |
|---|---|---|---|
| R-93 | Support attachments not implemented | no secure reusable upload primitive for Support; tickets work without attachments; post-Capstone | no |
| R-94 | Admin workspace deactivation and universal operator search not built | conveniences; candidate workspace owners can deactivate their own workspace; operators search by identifier per domain | no |
| R-95 | Live billing, production secret vault, external paging absent | all labelled in the product; nothing is sold or paged; later production-hardening phase | no |
| R-96 | PostgreSQL-only paths (SKIP LOCKED claim, audit-trigger DDL) not executed live | no disposable `TEST_POSTGRES_URL` in qualification; the SQLite paths are fully exercised and the DDL is rendered and unit-checked | no |
| R-97 | Google OIDC live behaviour unvalidated | an OIDC-only Admin cannot step up (fails closed); needs a provider account and an authorised run | no |

Plus the historical candidate limitations R-33, R-38, R-46, R-49, R-50, R-51. Every ACCEPTED row carries its rationale in the matrix.

## 14. Blockers
**None.** 0 BLOCKER rows. Findings raised by W11: LAYOUT-W11-01 (P3), corrected in W11 (section 14A and R-98, now PASS); CI-W11-01 (CI workflow invalid YAML since W10.11), corrected in W11 (section 14B and R-99, PASS).

## 14A. LAYOUT-W11-01 (found and corrected in W11)
- **Initial local qualification:** about 29px of horizontal overflow of the shared app header at exactly 768px (candidate and Admin alike). Initial classification: P3, ACCEPTED (matrix row R-98).
- **GitHub PR #132 result:** the Browser E2E job on Linux Chromium reproduced the overflow at **42px** at 768px, in light and dark, and failed the W11 Admin visual/a11y tests (the regression then allowed growth only up to 40px).
- **Owner decision:** a bounded W11 remediation was approved instead of loosening the threshold; R-52 stays PASS.
- **Root cause:** the responsive handoff. `PrimaryNavigation` (`md:flex`) showed the full desktop header navigation at Tailwind `md` = 768px, exactly the failing width, while the header also carries the brand, five destinations, More, language, theme and account controls; Linux font metrics need more width than macOS.
- **Fix (three coupled rules):** the desktop/mobile navigation handoff moved from `md` (768px) to `lg` (1024px): `PrimaryNavigation` `md:flex` to `lg:flex`, `MobileNavigation` `md:hidden` to `lg:hidden`, and the `AppShell` main bottom padding `md:pb-20` to `lg:pb-20`. Nothing was hidden or shortened: branding, More, language, theme and account controls, accessible names and all five destinations are unchanged; no `overflow-x` concealment, no font shrinking, no threshold change.
- **Regression:** the test no longer tolerates or expects the defect. At 768px every Admin page must have no document overflow and no Admin-content overflow (and so at all widths); a new explicit breakpoint regression covers candidate `/app` at 768 and 1024 in de and ru (no overflow, no crash, no raw keys, accessible header controls, exactly one visible primary landmark, all five destinations reachable, compact bottom navigation at 768 and desktop header navigation at 1024) and an Admin keeps access through More with keyboard handling at 768 and 1024.
- **Final result:** PASS after deterministic local and fresh-checkout requalification of the corrected tree (sections 32 to 38) and the PR's CI on the corrected head. The finding is recorded, not erased.

## 14B. CI-W11-01 (found and corrected in W11): the CI workflow was invalid YAML since W10.11
While investigating the red PR, the GitHub run list showed the push-triggered workflow `.github/workflows/ci.yml` failing instantly with no jobs on every recent commit. Cause: since W10.11 (commit `4ae4993`) one step name (the durable pause and feature flags evaluator) contained an unquoted colon-space, so the YAML did not parse and GitHub rejected the whole file. Consequence, stated plainly: the Python job (compile, Ruff, import checks, pytest, Alembic validation, evaluators, secret scan, clean-tree check) and the frontend and legacy-component jobs of that file did **not run on GitHub for W10.11, W10.12, W10.13, W10.14 or W11 PR #132 before this fix**; only the separate Browser E2E workflow ran. Those waves were qualified locally and from a fresh checkout (the same commands), and the W10.14 fresh-checkout run included all evaluators, but GitHub-hosted evidence of the Python job for them did not exist; earlier "CI green" statements for them referred to the checks that did run. Fix: the step name is quoted. Verification: the workflow now parses (3 jobs, 41 evaluator steps); every non-pytest step of the Python job (compile, Ruff, import checks, source-manifest validation, Alembic fresh upgrade, downgrade to `0003`, re-upgrade and single-head check on a temp database, product-coverage smoke, secret scan) was executed on the corrected tree and passed; and `scripts/eval_w11_integrated.py` now fails if the workflow does not parse or references a missing evaluator (R-99). Process note: the first run of the repaired workflow on GitHub is the PR's own checks.

## 15. Candidate core journey
Exercised deterministically (no provider): `tests/test_integrated_w11.py` registers a candidate, completes onboarding, creates an Opportunity, uploads a CV, saves memory and a completed interview with report content through the real API; the existing candidate Playwright journeys (`journey`, `interview`, `opportunity-practice`, `onboarding`, `data-privacy`, `support`, ...) run unchanged in the full Playwright suite.

## 16. Support interaction (K2)
A candidate ticket reaches the Support Operator; the operator replies and adds an internal note; the candidate sees the reply and never the note; only holders of `platform.support.read` (the Support Operator and, by its explicit preset, the Platform Administrator) can read the ticket body; another candidate gets 404.

## 17. Deactivation / session interaction (K3)
An Admin deactivation revokes the candidate's sessions in the same transaction; the candidate is refused at once; reactivation does not revive the old session; a new login is required.

## 18. Plan / entitlement interaction (K4)
An Admin plan assignment changes the candidate's own plan view (`/auth/plan`). The candidate's entitlements are then left untouched by every billing event: commercial-term change, failed payment, past-due, refund and provider cancellation (snapshot equality of resolved entitlements, subscription rows and tier).

## 19. Billing non-interference
Static (billing code with comments stripped never touches subscriptions, entitlements or tier) plus the behavioural K4 sequence and the W10.5 suite.

## 20. Pause interaction (K5)
An Operations Admin pauses `agent` through the governed API; the candidate's run is refused with the fixed `platform_paused` contract and a request id, before any service or model is built; the internal reason never leaves Admin; export, capabilities, legal, profile and plan stay available; resume restores admission; `platform_admin` cannot pause (no `config.manage`).

## 21. Feature-flag interaction (K6)
Turning `external_research` OFF through the governed flag API makes `/capabilities` report company research unavailable and the research service report disabled, with no network use, no plan change and no authorization change; restoring the override restores it.

## 22. Knowledge / retrieval interaction (K7)
Unapproved, approved-but-unindexed, indexed-but-inactive and retired versions are never retrieval-eligible; the active version is, and only it; the governed KB tables have no candidate-content columns.

## 23. AI configuration / candidate resolution (K8)
Nothing active: code defaults. A draft, and an approved-but-inactive configuration, change nothing; activation changes what the candidate's Balanced Practice session resolves (the session marker is never rewritten); rollback restores the code mapping; a browser-supplied model is never honoured.

## 24. Privacy / deletion interaction (K9)
A rich candidate (Opportunity, CV file, memory, interview with answers and evidence, support ticket, AI usage, audit rows) is deleted through the real route: the account, every candidate row, the private file and the AI usage facts are gone; no table still holds any sentinel; audit rows survive with the actor anonymised (the append-only trigger did not block deletion); another candidate is untouched; nothing about the deleted candidate is visible on any Admin surface; no backup overclaim.

## 25. Workspace isolation (K10)
A non-member cannot read a workspace or share into it; a member cannot remove the owner; the owner can view what a member shared; Admin workspace metadata never contains report or answer content; removing a member revokes the grants that member made.

## 26. Role / entitlement separation (K11)
A governed two-person role change changes the target's Admin permissions (to exactly the preset) and leaves every product entitlement, the plan view and the Premium-only gate unchanged.

## 27. Private-data sentinels (Q)
Sentinels planted in the Opportunity, CV, memory and the interview's question, answer and evidence never appear on any Admin read surface for any of the six Admin personas (every parameterless GET route plus user and ticket detail). The ticket body appears only for `platform.support.read` holders. Mo conversation and preparation chat live in the agent checkpoint store, which no Admin code path can open (static check).

## 28. Secret sentinels (R)
Six sentinel secrets (provider keys, OAuth secret, Redis URL with password, document key) set in the environment never appear in candidate responses, validation/404/401/403 errors, any Admin read surface for any persona, audit rows or the captured logs.

## 29. Language contract
8 interface locales, 8 Mo conversation languages, 7 dictation/TTS/realtime/document/KB languages; Russian: interface YES, Mo conversation YES, speech NO, KB NO, official ESCO NO, geography inference NO; interface language never changes geography. Verified by `scripts/eval_w11_integrated.py`, `scripts/eval_doc_consistency.py` and the localization suites. Slogan `Ask More. Be More.` exact and never translated.

## 30. Tool / specialist architecture
11 tools = 6 Career + 3 specialists + 2 human-action; exactly 3 specialists (`role_opportunity`, `candidate_evidence`, `interview_strategy`); no Evaluation specialist.

## 31. Evaluation architecture
Evaluation stays an LLM-backed service with schema-validated, model-produced scores; no deterministic scoring formula.

## 32. Backend result
Main tree, final (re-run on the corrected tree after LAYOUT-W11-01): **3145 passed, 4 skipped, 0 failed, 0 errors** (W10.14: 3127; +18 integrated cross-plane tests). Skips (unchanged, explained): live Adzuna needs explicit opt-in and credentials; the PostgreSQL W10.9 claim test needs a disposable `TEST_POSTGRES_URL`; the Streamlit component test needs a Streamlit context; the RAGAS adapter test is conditional on the installed package.

## 33. Frontend result
Vitest **768 passed** in 89 files (unchanged; the layout correction is covered by the Playwright breakpoint regression); typecheck, lint and production build clean; i18n scanner 0 offenders; shared first-load JS 103 kB (identical to the W9.13 baseline, no regression).

## 34. Playwright result
**239 passed** (221 + 18 new visual/accessibility and breakpoint tests); no retries, no timeout increases, no added sleeps.

## 35. Evaluator result
**42 of 42** CI evaluator scripts pass: the 41 scripts listed in the CI workflow at W10.14 (listed, though the workflow itself did not parse on GitHub: section 14B) plus the new `scripts/eval_w11_integrated.py` (27 checks). Correction: the W10.13 and W10.14 closure reports said 39 and 40 evaluators; the true counts were 40 and 41, because the verification loops used a pattern that skipped `scripts/eval_i18n_l10n.py` (its name contains digits). That script was always listed in the workflow and always passed when run locally; it is run and counted from W11. `scripts/eval_release_matrix.py` now recomputes its totals from the integrated matrix; `scripts/eval_admin_qualification.py` still passes (41 checks). Every evaluator that builds the app or touches a database bootstraps `tests.conftest` first (checked by the W10.14 evaluator).

## 36. Fresh-checkout result
From the fresh checkout (repeated on the CORRECTED tree after LAYOUT-W11-01): backend **3138 passed, 11 skipped, 0 failed**; Vitest **768 passed**; Playwright **239 passed**; **42/42** evaluators; Ruff and compileall clean; typecheck, lint, build and scanner clean; the checkout stayed clean and created no developer store. The 11 skips, each classified: (1) live Adzuna: needs opt-in and credentials: expected environmental; (2) PostgreSQL W10.9 claim test: needs a disposable `TEST_POSTGRES_URL`: expected environmental (R-96); (3) `test_ragas_adapter.py:117` requires the optional `ragas` package, which the CI extras do not install (the sibling test at line 110 ran instead): accepted optional dependency; (4) `test_documents_pipeline.py:238` real OCR smoke test needs the optional `[ocr]` extra (`pytesseract`, `pdf2image`), which the CI extras do not install: accepted optional dependency, identical to CI; (5)-(6) `test_local_sources.py:78` and `:87` need local O*NET and ESCO files, and (7)-(11) `test_ph3_expansion.py:158/166/207/215/223` need the OOH, BLS EP, CLSSI, Eurostat JVS and DigComp datasets: intentionally untracked large datasets, accepted data absence. 0 skips are blockers. The Streamlit-context skip of the main tree does not occur in the fresh run.

## 37. Migration result
No migration was added in W11. In the fresh checkout, on a NEW isolated database: base to head succeeded; a single head `0025_security_audit_incidents`; 64 tables; the four append-only triggers (`audit_events`, `incident_events`) are installed; the eight W10.x tables checked (incidents, notifications, role requests, incident events, telemetry events, AI usage facts, flag overrides, pause states) have 0 seed rows; downgrade to `0024_reporting_analytics` and re-upgrade succeeded. The developer DB was never migrated or opened by a migration.

## 38. Visual QA
Programmatic: 13 candidate surfaces x {de, ru} x {desktop 1280, mobile 390} x {light, dark} = **104 page/configuration checks**; 20 Admin pages (18 destinations, a user detail and a support detail, recorded real API shapes) x {tablet 768, desktop 1280} x {light, dark} = **80 page checks** plus a permission-denied state; and the shared-header breakpoint regression (candidate `/app` x {de, ru} x {768, 1024}, plus an Admin at 768 and 1024). Checks: no document or content horizontal overflow (at every width, including 768px), no raw translation key, accessible names on links and buttons, image alt, no Admin link for a candidate, slogan invariant, Cyrillic rendered, no crash (detected by the LOCALIZED error-boundary text), and an `h1`. Results: **768px candidate shared header PASS; 768px Admin shared header PASS; 1024px desktop transition PASS; 390px mobile PASS; 1280px desktop PASS.** Human screenshot sample (eyes-on): candidate Russian mobile dark Home, candidate German desktop light Practice (re-shot after an incomplete first mock), candidate Russian mobile dark Privacy Center, candidate German desktop light Trust; Admin Support, Billing, Security (dark), Reports and Configuration; and, after the correction, **candidate 768px** (compact header with brand, More, language, theme and account; five-destination bottom bar; no overflow), **Admin 768px** (same compact header and bottom bar, Admin destination list above the content), **candidate 1024px** and **Admin 1024px** (full desktop header navigation, no bottom bar). One observation, not a defect: at 768px the dismissible Welcome-tour card overlaps part of the bottom bar until it is dismissed. Not every screenshot was reviewed by eye; the programmatic checks cover the rest.

## 39. Accessibility
Deterministic checks only (see section 38 and the W10.14 static/component checks); no WCAG certification is claimed. A11Y-W9-13-01 retired on evidence (section 11). LAYOUT-W11-01 was corrected (section 14A): at 768px the compact bottom navigation is the single visible primary landmark; from 1024px the desktop header navigation is, with all five destinations, More, language, theme and account controls reachable at both.

## 40. Performance
No material regression. Candidate build: shared first-load JS 103 kB, identical to the W9.13 baseline. Admin fixture (2,000 users, 20,000 audit rows, SQLite, p50 of 5; not an SLA): Admin shell 13 ms, users list 6 ms, jobs list 5 ms, reports overview 9 ms, audit page 6 ms, security events page 18 ms (W10.14: 21/6/4/7/5/14 ms). Backend suite wall time 536 s (W10.14: 508 s) for 18 more tests.

## 41. Dependency / install result
Python: `pip install -e ".[dev,db,speech,live]"` from a fresh venv succeeded. Frontend: `npm ci` succeeded (lockfile consistent). `git diff` of `pyproject.toml`, `requirements.txt`, `frontend/package.json` and `frontend/package-lock.json` since W10.14 closure is empty; no local-path dependency; the OCR and RAGAS extras stay optional (not installed in CI either).

## 42. Developer-store isolation
W11-start baseline (the accepted post-incident state): dev DB `8cd20d503943f090f890e97c6ca55709949a76d3` (224 schema objects), checkpoint `b56d0c39fbba64786495ebb5db59eedecfae5c71`, Chroma `6357c057606273f313b408cc7f144390453a0832`, research cache `d6708df40dab369b4368c1b4deb4dc680c14d0b1`, `evaluations/` `67259aba185daa495f8bf8958e1c905fd086b2be`. After ALL W11 qualification (main-tree suites, visual capture, screenshot sample, fixture generator, performance runs, manual checks, the fresh-checkout run and the document edits) all six fingerprints are identical to the start. This is stability of the disclosed post-incident baseline, NOT pre-W10.13 equality.

## 43. W10.13 contamination inheritance
Inherited verbatim: **disclosed contamination with stable post-incident qualification baseline**. The pre-W10.13 developer DB (`64d66596...`) did not equal the post-W10.13 DB; no restoration occurred. W11 began from the accepted post-incident baseline, did not mutate it, and proved migrations only on isolated temp databases. W11 additionally hardened 13 evaluators (W10.14) and the new W11 evaluators bootstrap `tests.conftest` before application code.

## 44. Paid/live calls
0.

## 45. Known limitations
The ACCEPTED rows of the matrix (section 13 and the historical rows); the PostgreSQL job and trigger tests unexecuted live; Google OIDC, Redis limiter, email and live billing unvalidated or not built; engineering translations pending native/legal review; live generated-language quality unvalidated; no advanced anomaly detection; none of them is a blocker.

## 46. W11 engineering verdict
# P10B INTEGRATED QUALIFIED - RC-P10-003 READY FOR SEPARATE CREATION

Every condition held: 0 BLOCKER rows in the integrated matrix; the full candidate and Admin suites are green; the cross-plane seam tests are green; the complete fresh-checkout qualification (fresh Python venv and `npm ci`) is green; the migration chain is green; the frontend fresh install and build are green; Playwright, the evaluators, the privacy and secret sentinels, localization and route authorization are green; the protected stores are unchanged; 0 paid/live calls; the tree is clean. The owner has confirmed the evidence-based retirement of A11Y-W9-13-01 (R-52, section 11), and LAYOUT-W11-01 (R-98) was corrected rather than accepted (section 14A).

## 47. RC-P10-003 readiness decision
The repository is engineering-ready for a SEPARATE, owner-reviewed RC-P10-003 creation step. **W11 did not create RC-P10-003**: no tag, no branch, no version change, no RC artifact directory. The RC must still carry the ACCEPTED limitations (section 13 and the historical rows) honestly in its own documentation.

## 48. Pilot 2 state
Paused. W11 did not resume it.

## 49. P10C boundary
P10C has not started and is not authorised by W11.

## 50. Next step
A separate, owner-reviewed RC-P10-003 creation action (tag/branch/version/artifacts) if the owner accepts this verdict and the ACCEPTED limitations. Until then: no RC, no Pilot 2, no P10C.
