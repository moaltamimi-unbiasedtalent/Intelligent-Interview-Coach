# P10B-W9.13 - Full P10B Candidate-Side Requalification

Qualification wave: no product functionality added, no migration, 0 paid/live calls, no RC-P10-003, Pilot 2 not resumed, W10 not started.
Canonical gate: [../P10B_RELEASE_ACCEPTANCE_MATRIX.md](../P10B_RELEASE_ACCEPTANCE_MATRIX.md) (checked by `scripts/eval_release_matrix.py`).

## 1. Baseline
`main` = `7071814a2dde45280c123c7c69d7667106549f82` (W9.12 merged, PR #107). Branch `release/p10b-w9-13-requalification`.

## 2-3. Fresh-checkout methodology and environment
Qualification ran in a **detached git worktree at `7071814`** (no commits ahead of `main` for product code), created fresh with: no `.venv`, no `node_modules`, no
`frontend/.next`, no `.env`, no `data/interview_studio.db`, no `data/chroma`, no `data/cache`; Python and Node dependencies installed from scratch
(`python -m venv` + `pip install -e ".[dev,db,speech,live]"`; `npm ci`). Provider/database variables present in the environment: **none** (0 matches for
OPENROUTER/ADZUNA/BREVO/LANGFUSE/GOOGLE_CLIENT/DATABASE_URL/COPILOT_). No credential value was printed. The developer machine's home-directory Streamlit secrets file
still exists and is neutralised by `tests/conftest.py` (proving that guard, not the absence of the file). Environment: macOS (Darwin 27.0.0), Python 3.11.15,
Node v24.15.0, pytest 8.4.2, ruff 0.16.10, SQLAlchemy 2.1.2, chromadb 0.6.3, python-dotenv 1.2.4, streamlit 1.64.0. Alembic head `0014_opportunities`.
Pre-run `git status --porcelain`: empty.

## 4. Acceptance matrix summary
52 requirements: **43 PASS, 9 ACCEPTED limitations, 0 BLOCKER**. Detail in the matrix; evidence files exist (checked).

## 5-24. Results by area (all from the fresh checkout)
| Area | Result |
|---|---|
| W9.1 resilience (envelope, CORS, retry, offline vs unreachable) | PASS |
| W9.2 recovery / independent regions | PASS |
| W9.3 security/review boundaries, owner-scoped runs | PASS |
| W9.4 Opportunity discoverability | PASS |
| W9.5 onboarding/Welcome/Tutorial; W9.7B verified redirect | PASS (onboarding Playwright green, no sleeps/retries) |
| Localization x8; scanner; catalogue parity | PASS (scanner 0 offenders; slogan exact) |
| Russian (UI + Mo conversation, Cyrillic) | PASS; native/legal review **pending** |
| Language dimensions | PASS: 8 interface, 8 conversation, 7 speech/document/KB; Russian excluded from speech/ESCO/geography |
| Opportunity -> Prepare -> Practice -> Progress/History | PASS (deterministic mocks) |
| Mo/Career conversation, language ownership | PASS; live model quality **not validated** |
| Evidence/RAG, numbered sources, authority 1/2/3 | PASS (not every answer is RAG-grounded) |
| Tools and specialists | PASS: 11 tools (6/3/2), 3 specialists, no Evaluation specialist |
| Interview evaluation contract | PASS (bounds/required fields; no invented consistency formula; POLICY-02) |
| Practice, Deep Dive, reports, idempotent writes | PASS |
| Progress/History/Memory | PASS |
| Data & Privacy Center | PASS; PRIV-W9-01 and PRIV-W9-02 **OPEN** and stated |
| Cross-user isolation (read/export/delete/revoke); admin not a content superuser | PASS |
| Trust page and prohibited-claim guard | PASS |
| Product claim register (28 capabilities 9/10/5/4; 20 allowed; 20 prohibited) | PASS |
| Documentation consistency guard | PASS |
| W9.12 guarantees: TD-W9-01 and TD-W9-02 regressions | PASS (both remain CLOSED) |

## 25-29. Counts and clean-tree proof
- **Backend (fresh venv):** 2559 passed, 10 skipped, 0 failed (run twice; identical). The 10 skips are environmental guards: OCR runtime absent (1), live Adzuna needs
  credentials (1), local O*NET/ESCO files absent (2), local OOH/BLS/CLSSI/Eurostat/DigComp datasets absent (5), `ragas` not installed (1). On the developer checkout the same
  suite shows 3 skips because the datasets are present locally.
- **Frontend:** typecheck and lint clean; build green; **515 unit tests passed** (72 files); hardcoded-English scanner 0 offenders.
- **Playwright:** **199/199** passed, no retries, no skips, no timeout changes.
- **Evaluators:** **25/25** CI evaluators exit 0 (plus the new matrix-integrity guard, 26 with it); `ruff` clean; `compileall` clean.
- **Clean tree:** after the full backend suite, the build, the full Playwright run and all evaluators, `git status --porcelain` in the fresh checkout is **empty**; no
  `data/interview_studio.db`, `data/chroma` or `data/cache` was created there. On the developer checkout the development DB is **byte-identical**, the Chroma store and
  checkpoint file hashes are unchanged and the research cache holds the same 20 files before and after.

## 30-31. Visual and accessibility QA
Driven programmatically over **13 pages** (Home, /app, Opportunities, Prepare, Practice, Progress, History, Settings, Account, /account/data, Trust, Help, onboarding)
in **German and Russian x desktop (1280) and mobile (390) x light and dark = 8 configurations (104 page checks)**: no horizontal overflow, no raw translation keys,
every link/button has an accessible name, every image has an `alt`. Screenshots reviewed by eye: Russian mobile dark Data & Privacy, German desktop light /app, Russian
desktop dark Trust (no layout defects, Cyrillic and diacritics render). Earlier waves' dialog/focus/keyboard coverage (ConfirmDialog, onboarding, menus) stays green in
the unit and Playwright suites. **Finding A11Y-W9-13-01 (P3):** `/practice` has no page-level `h1` (all other pages do); accepted, not a blocker. No WCAG certification is claimed.
Not every page/theme/locale combination was inspected by eye; the other checks rely on the programmatic assertions above.

## 32. Performance baseline
Shared first-load JS **103 kB** (unchanged since W9.8). Route sizes: `/` 2.68 kB, `/app` 3.37, `/account/data` 6.37, `/help` 2.28, `/history` 2.94, `/onboarding` 4.27,
`/opportunities` 3.42, `/practice` 9.47, `/prepare` 15.5, `/progress` 4.3, `/settings` 4.03, `/trust` 1.22. No material regression. Locale/bundle optimisation remains open.

## 33. Schema
Single Alembic head `0014_opportunities`; a fresh `alembic upgrade head` succeeds; no migration added in W9.13; development DB untouched.

## 34-36. Limitations, blockers, decisions
**Blockers: none.** **Accepted limitations (9 matrix rows):** PRIV-W9-01 (preparation-chat indexing/deletion), PRIV-W9-02 (consent history), POLICY-01 (verified email not
required to sign in; preferred future direction: require it for sensitive actions), distributed rate limiting NOT live (Redis adapter optional, fake-tested only),
LEGACY-01 (Streamlit retained), native/legal language review pending, live generated-language validation pending, metadata localization and bundle optimisation pending,
A11Y-W9-13-01 (`/practice` heading). **POLICY-02:** no deterministic evaluation score relationship is invented.

## 37. Live/provider calls
0 paid or live provider calls; no provider credentials were required or present.

## 38. Engineering qualification decision
# P10B QUALIFIED
All deterministic release gates are green from a fresh checkout, no blocker exists, and every remaining issue is an explicitly accepted limitation. This is an
**engineering qualification only**. It does not create RC-P10-003 and does not claim human, legal, native-language or live-model validation.

## 39. W10 handoff
Next phase: **P10B-W10 Platform Administration, Support & Commercial Operations** (design gate W10.0 first). Agreed sequence is unchanged: W9.13, W10, integrated
candidate + admin requalification, RC-P10-003, remaining Pilot 2, P10C. W10 inherits: PRIV-W9-01 and PRIV-W9-02 (data-model work, W10.10), POLICY-01 (verified-email
for sensitive actions, W10.2/W10.10), the optional Redis rate-limit adapter (W10.6/W10.9 to validate and enable), the `eval_release_matrix.py` gate to extend with admin rows,
and the clean-tree and fresh-checkout qualification discipline.
