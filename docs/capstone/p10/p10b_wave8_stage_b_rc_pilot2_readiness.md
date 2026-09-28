# P10B Wave 8 Stage B - RC-P10-002 + Pilot 2 readiness

**Status:** DELIVERED (release qualification + pilot readiness). NOT merged. Pilot 2 NOT run.
**Branch:** `feature/capstone-p10b-wave8-stage-b-rc-pilot2` (from `origin/main`).
**Baseline / candidate SHA:** `ab9ff7381ee02ed8de358e549ebf2e466e6ca08d` (origin/main after PR #98,
Stage B0 Visual System v2). **RC-P10-002 points to this exact merged-main SHA.**
**Prior merged baseline:** `d255d34` (PR #97, Wave 8 release qualification).
**Migration head:** `0014_opportunities` (unchanged; up/down/up valid).
**Paid/live/provider calls:** 0.

This stage (1) establishes RC-P10-002 against the qualified merged main and (2) prepares the existing
P10 pilot kit for Pilot 2 against that exact candidate. It is a release-qualification + pilot-readiness
stage: no product/runtime/backend/db/migration/route/copy/i18n change.

## Merged baseline (Phase 0)
- origin/main = `ab9ff73`; recent history: #98 (Stage B0 visual system) <- #97 (Wave 8) <- #96 (W7).
- Stage B0 (`f8e3ec7`) is an ancestor of origin/main -> **merged**.
- Working tree clean; branch cut from origin/main; Waves 1-8 + Stage B0 present.
- 12 Ask4Mo v2 assets present in the merged tree; migration head `0014`.
- **CI note:** GitHub CI for PR #98 could not be queried here (no `gh`/token/bound PR). The full gate
  below was **reproduced locally on the exact merged SHA** as the strongest available evidence.

## Merged release qualification (Phase 1) - all green on ab9ff73
| Check | Result |
|---|---|
| Backend `pytest -q` | **2455 passed, 3 skipped, 0 failed** |
| Ruff / compileall | clean / clean |
| Alembic | single head `0014`; up/down/up valid |
| OpenAPI | 112 paths |
| Frontend typecheck / lint | clean / clean |
| Frontend unit (vitest) | **282 passed (53 files)** |
| Frontend build | success |
| Playwright (CI) | **119 passed, 0 failed** |
| Evaluators | release_candidate(27) / marketing(32) / opportunity_journey / workspace_security(GATE) / documents_evidence / identity_platform / security(22-detect,0-FP) / i18n_l10n - PASS |
| Visual system | 12 assets; 6 empty-state illustrations alpha-verified; placements present; image-free scan = 0 |
| Secret scan | clean (client bundle + src/scripts) |
| Paid/live | 0 |

No regression introduced by the Stage B0 merge (counts identical to the Stage B0 feature-branch run,
now re-verified on merged main).

## Opportunities empty-state closure (Phase 2)
Stage B0 could not observe the Opportunities empty-state illustration because the **then-running dev
backend (:8020) was a stale process from Sep 26 that predated the Wave 5/6 routes** (105 paths, no
`/opportunities`) - an environment condition, evidence-backed, not a code defect. Closed this stage
using the authenticated flow on a **fresh current backend + clean migrated DB**:
- authenticated user reaches `/opportunities`: **yes**
- genuine empty state renders: **yes** (`ask4mo-empty-opportunities-ink.png`, transparent, above title)
- illustration appears only in the empty state: **yes**
- loading does not show it: **yes** (separate `LoadingState` branch)
- error does not show it: **yes** (verified via the stale-backend 404 -> `ErrorState`, no illustration)
- populated does not show it: **yes** (created "QA Test Engineer"; list shows, illustration gone)
- 390px: no overflow (`scrollWidth === clientWidth === 390`); desktop correct
- creating an Opportunity still works: **yes**
No product code was changed to manufacture the state; no defect found.

## RC-P10-002 (Phase 3)
- **Convention discovered:** artifacts directory + `manifest.json` + `gate_results.md` (mirrors
  `artifacts/capstone/p9/RC-P9-001/`). **Not** a git tag (existing tags are sprint-level; RC-P9-001 has
  no tag). RC-P10-002 created under `artifacts/capstone/p10/RC-P10-002/`.
- **Created:** yes. **Identifier:** RC-P10-002. **Exact full SHA:** `ab9ff7381ee02ed8de358e549ebf2e466e6ca08d`.
- Candidate is the qualified merged-main tip (clean checkout); not a dirty tree, not an unmerged branch.
- **Historical RCs untouched:** RC-P9-001 (`319759d`) is immutable and unchanged.
- The RC artifact + this readiness documentation are committed on top of the candidate and do not change
  it (same doc-only pattern as RC-P9-001's evidence follow-up).

## Pilot kit audit (Phase 4)
Existing P10 kit found and reused (not rebuilt): `pilot_plan.md`, `participant_notice.md`,
`moderator_guide.md`, `participant_tasks.md` (T1-T9 + debrief), `observation_template.md`,
`issue_log_template.md`, `pilot_results_template.md`, `pilot_lessons_template.md`,
`pilot_data_handling.md`, `environment_check.md`, `pilot_presentation_template.md`,
`sessions/P01_template.md` (blank), and synthetic `assets/{pilot_cv,pilot_job_description,
pilot_role_context}.md`. **No real Pilot 1 human evidence exists** (only a blank session template) -
AC-24 correctly remains NOT RUN; nothing was invented.

## Pilot 2 changes (Phases 5-9)
Added under `docs/capstone/p10/pilot2/` (extends the kit; does not replace it):
- `pilot2_readiness.md` - RC pin; journey preserving T1-T9 with a new **T3a Opportunity** step;
  **visual-system observation fields** (comprehension / hierarchy / helps-distracts-neutral / empty-state
  clarity / perceived trust / provenance); **6-category issue taxonomy** kept separate (PRODUCT-UX,
  MODEL-QUALITY, VOICE-TRANSCRIPTION, INFRASTRUCTURE, VISUAL-UI, PRIVACY-TRUST); **severity/repair rules**
  (BLOCKER/HIGH/MEDIUM/LOW); privacy controls; 3-5 participant target; qualitative-only (real denominators).
- `pilot2_runbook.md` - owner-facing before/during/after runbook pinned to RC-P10-002 (one candidate for
  the whole pilot; fresh account per participant; synthetic fixtures; Chromium + 390px; consent;
  environment-vs-participant failure discipline; no fixes between participants unless a blocker).
- `pilot2/sessions/P01_pilot2_template.md` - blank per-participant session sheet with the task grid,
  visual-system fields and severity+category issue table.
Methodology: exploratory qualitative usability; observe behaviour first, neutral follow-ups after; no
leading questions ("do the new images make it better?" is prohibited).

## Acceptance traceability (Phase 10)
| Dimension | Status |
|---|---|
| Deterministic release qualification | GREEN (RC-P10-002 gate) |
| Visual-system qualification | GREEN |
| Internal readiness | READY |
| Human pilot (AC-24) | **NOT RUN / PENDING PILOT 2** |
| Live-provider validation | NOT RUN (0 paid/live) |
| Hosted/deployment (EX-12) | BLOCKED / NOT RUN |
Pilot readiness is not pilot completion; green CI/internal QA is not human-usability evidence.

## Release impact
- Application/backend/database/migration/route/copy/i18n: **NONE** (this stage is RC identification +
  pilot documentation + QA closure only).
- Files added: `artifacts/capstone/p10/RC-P10-002/{manifest.json,gate_results.md}`,
  `docs/capstone/p10/pilot2/{pilot2_readiness.md,pilot2_runbook.md,sessions/P01_pilot2_template.md}`,
  this report.
- Tests weakened: none. Paid/live calls: 0.

## Open gates / next
Actual owner-supplied **Pilot 2** sessions against RC-P10-002; then triage, consequential repairs
(new RC if runtime changes), live-provider validation, EX-12, and the final release decision - none of
which are performed in this stage.
