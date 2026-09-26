# RC-P9-001 — Gate Results

_Safe/non-private evidence summary for the release candidate. Reproduce from a fresh checkout
with the commands below (no paid/live calls). Full narrative: `docs/capstone/p9_*`._

## Required release gate (all green)
| Gate | Command | Result |
|---|---|---|
| Backend regression | `python -m pytest -q` | **2381 passed, 3 skipped** |
| Frontend unit | `npm test` (vitest) | **242 passed** |
| Integrated E2E | `npx playwright test` | **104 passed (chromium)** |
| Ruff | `ruff check .` | **pass** |
| Compileall | `python -m compileall -q app.py src scripts tests` | **pass** |
| Frontend lint | `npm run lint` | **pass** |
| Typecheck | `npm run typecheck` | **pass** |
| Production build | `npm run build` | **pass** |
| OpenAPI | `create_app().openapi()` | **105 paths** |
| Alembic single head | `alembic heads` | **1 head (0011_workspaces_shares)** |
| Secret scan | grep signature scan of `app.py src scripts` | **clean** |

## Deterministic evaluators (20, all PASS)
account_deletion · agent · dictation_experience · documents_evidence · feedback_learning ·
hosting_readiness · identity_platform · knowledge_expansion · knowledge_governance ·
multi_agent · platform_admin · product_coverage · prompt_lab · rate_limits · realtime_voice ·
response_experience · retention · voice_experience · workspace_security · **restart_recovery (new)**.

## AC-20 recovery proof
`python scripts/eval_restart_recovery.py` → PASS (seed → restart → backup → destroy → restore →
verify). Migration `upgrade head → downgrade 0003_interview_sessions → upgrade head` → single head.

## Skip audit (3, justified)
| Test | Reason | Required for release? |
|---|---|---|
| `test_external_research_p7f.py::live Adzuna` | needs `RUN_ADZUNA_INTEGRATION=1` + creds | no (live) |
| `test_live_component.py::render` | legacy Streamlit component needs Streamlit context | no (legacy) |
| `test_ragas_adapter.py` (one case) | environment-conditional (ragas present) | no |

## Paid / live calls
**0.** All external providers use deterministic fakes/stubs.

## EX-12 hosted operation
**BLOCKED / NOT RUN** — hosting cannot be certified from a local build; no authorized deployment.
