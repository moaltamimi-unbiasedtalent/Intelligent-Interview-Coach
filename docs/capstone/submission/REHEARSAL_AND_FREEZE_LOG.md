# Rehearsal and Freeze Log (the folded P12 duties)

Prepared 2026-10-19 on branch `docs/p11-final-capstone-submission` (from `main` `3d1af6f`). This is a **log of what was actually run**, including a mistake. Per the owner's direction the previously proposed P12 rehearsal and freeze duties are part of P11. No submission was made and none is claimed.

## 1. Incident: one unplanned live provider call

During the UI rehearsal I started the backend from the repository working copy on a throwaway database and sent one `POST /agent/run`. It returned a **real model reply** (about 7 seconds): the working copy contains a `.env` and a `.streamlit/secrets.toml`, the backend loaded the OpenRouter key, and `PYTHON_DOTENV_DISABLED=1` and an empty `OPENROUTER_API_KEY` do **not** prevent it (the key also comes from Streamlit secrets). I stopped the servers by exact process id, then:

- The P10E ledger was **not** used and is unchanged: 285 of 300 calls, about USD 2.11 committed. This call went around the P10E guard.
- A read-only account snapshot afterwards showed account usage **+USD 0.0207** since the previous snapshot (6.7722 to 6.7930). The shared key may have other users, so this is an upper estimate of the one call, not an attribution; the per-request cost was not captured.
- No protected store changed: the stack used throwaway databases and a throwaway data directory; no file under `data/` was modified.
- Fix: the rehearsal was repeated from a **fresh git worktree** (no `.env`, no secrets file). There `/agent/run` answered "The assistant isn't configured in this environment." and no provider was contacted. The hazard and the verified workaround are documented in `DEMO_GUIDE.md` and `README.md`; register entries `IR-DEMO-KEY` (no code switch exists to disable key discovery) and `IR-REHEARSAL-CALL` (owner acknowledgement) record it.

## 2. Verification results

| Check | How | Result |
|---|---|---|
| Application startup | backend (uvicorn, port 8020) and frontend (`npm run dev`, port 3015) from a fresh worktree on a throwaway database | PASS: `/api/v1/health` ok; frontend 200 |
| Synthetic candidate flow in the UI | registered, signed in, onboarding, created the fictional Opportunity through the real UI and API | PASS (account creation, sign-in, onboarding screen, Opportunities list showing the fictional Data Analyst Opportunity) |
| No broken demonstration screens | opened Home, Opportunities, Prepare, Practice, History, Progress, Data and privacy and Pricing | PASS: each rendered its content; Prepare shows the Mo form and the safe "not configured" state without a provider; three 401 console messages appeared on first navigation while the session cookie was settling (not investigated further) |
| Offline journey | `python scripts/demo_offline_journey.py` (twice) | PASS: all five steps' checks pass; identical transcript hash on repeat; network blocked; covered by 6 tests |
| README instructions | the commands used in this log (pytest, the demo script, uvicorn, `npm run dev`, `npm test`, evaluators) were run; `pip install -e ".[dev]"` and a fresh `npm install` were **not** re-run | PARTIAL: verified by running except the two install commands |
| Presentation accuracy and evidence consistency | numbers in the submission documents compared with the runs in section 3 and with the register and ledger | PASS: backend 5,060 / vitest 1,082 / Playwright 412 / evaluators 52 / coverage 386, 258, 0 / ledger 17 and 8 / register 392, 340, 52 are the figures used throughout |
| No secret exposure | scanned the new documents and the transcript for key patterns and local paths; the demo data uses the reserved `.invalid` domain | PASS |
| No accidental commercial activation | the 12-gate test and the billing, checkout and speech negative tests in the full suite; the demo disables billing, speech and email by construction | PASS: all 12 gates False; no Stripe interaction |
| Required CI green | `main` `3d1af6f`: PR #205's 11 checks and the merge commit's 9 push checks success | PASS for `main`; CI for this branch runs when its pull request is opened |

## 3. Measurements taken on the final state of this branch

Backend 5,060 passed, 34 skipped, 0 failed; vitest 110 files and 1,082 tests passed; 52 of 52 CI evaluator and guard commands passed (plus compileall, Ruff, `git diff --check`, `alembic heads`, shard verification); the Playwright suite (412 tests, chromium) was last run in the integrated requalification on code identical to this branch's runtime (this branch adds a demonstration script, its tests and documents only). Product coverage unchanged: 386/412 developer-local FAIL, 258/412 clean checkout FAIL, 0/412 human-qualified.

## 4. Freeze

The runtime code is frozen at `main` `3d1af6f` for the purposes of this submission package: the only additions on this branch are `scripts/demo_offline_journey.py`, its tests, the synthetic demonstration data, a regenerated register and documents. Any further runtime change needs new evidence. A timed rehearsal against the real presentation length could not be done (the format is unverified and slides are not built); that step stays with the owner.
