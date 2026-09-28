# RC-P10-002 — Gate Results

_Safe/non-private evidence summary for the release candidate. Candidate SHA:
`ab9ff7381ee02ed8de358e549ebf2e466e6ca08d` (origin/main after PR #98, Stage B0 Visual System v2).
Reproduce from a fresh checkout of that SHA with the commands below (no paid/live calls).
Full narrative: `docs/capstone/p10/p10b_wave8_stage_b_rc_pilot2_readiness.md`._

## Required release gate (all green on ab9ff73)
| Gate | Command | Result |
|---|---|---|
| Backend regression | `python -m pytest -q` | **2455 passed, 3 skipped, 0 failed** |
| Frontend unit | `npx vitest run` | **282 passed (53 files)** |
| Integrated E2E | `CI=true npx playwright test` | **119 passed (chromium)** |
| Ruff | `ruff check src scripts` | **pass** |
| Compileall | `python -m compileall -q src scripts` | **pass** |
| Frontend lint | `npm run lint` | **pass** |
| Typecheck | `npx tsc --noEmit` | **pass** |
| Production build | `npm run build` | **pass** |
| OpenAPI | `create_app().openapi()` | **112 paths** |
| Alembic single head | `alembic heads` + up/down/up | **1 head (0014_opportunities); up/down/up valid** |
| Secret scan | grep signature scan of client bundle + `src scripts` | **clean** |

## Deterministic evaluators (release-relevant, all PASS)
release_candidate (27 invariants) · marketing_product_trust (32) · opportunity_journey ·
workspace_security (GATE PASS) · documents_evidence · identity_platform (safety 1.0) ·
security (22/22 detected, 0 false positives) · i18n_l10n. Full CI evaluator set was green as of
Wave 8; no release-relevant code changed between that set and this candidate (Stage B0 is
presentational + assets only).

## Visual System v2 qualification
- 12 assets present under `frontend/public/images/ask4mo/`; the six empty-state illustrations retain
  real alpha; four photos + two editorial illustrations are opaque; dimensions match the inventory.
- Public placements verified (`/`, `/product`, `/trust`, `/about`, `/help`) at desktop + 390px.
- Empty-state placements verified live (opportunities, company, documents story bank, progress,
  history, workspaces) — transparent, centered, above the title, never leaking into
  loading/error/populated states.
- Image-free surfaces scan: **0** leaked references (pricing/legal/auth/onboarding/app/prepare/
  practice/sources/review/settings/account/admin/*-detail).

## B0 Opportunities empty-state closure (this stage)
Reproduced the authenticated flow on a fresh current backend (opportunities route present) + clean DB:
empty state renders `ask4mo-empty-opportunities-ink.png`; creating an opportunity works and the
populated list shows **no** illustration; 390px has no overflow; the error path shows no illustration.
No product code changed; no defect found.

## Paid / live calls
**0.** All external providers use deterministic fakes/stubs.

## Open gates (not part of this stage)
- Human Pilot 2 (AC-24): **NOT RUN / PENDING** — requires owner-supplied participants.
- Live-provider validation: **NOT RUN** (no paid/live authorized).
- EX-12 hosted operation: **BLOCKED / NOT RUN** (no authorized deployment).

## CI note
GitHub CI for PR #98 could not be queried from this environment (no `gh`/token/bound PR). The gate
above was reproduced locally against the exact merged SHA `ab9ff73`.
