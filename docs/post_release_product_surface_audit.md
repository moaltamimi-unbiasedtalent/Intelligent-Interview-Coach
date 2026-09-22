# Post-Release Product-Surface Audit — Progress, History, Sources, Review & Diagnostics

Investigation and minimal corrective fixes for four surfaces reported as empty/broken after
the Sprint 4 submission freeze (`sprint4-submission-ready` → `1b084cb`). No runtime behaviour
of the Agent, retrieval, prompts, tools, models or schemas was changed; these are product-surface
wiring, projection and empty-state fixes with regression tests.

## Executive summary

| Surface | Reported | Root cause | Class | Status |
|---|---|---|---|---|
| Progress | Appears empty | Rendered saved *memory* only; real persisted practice metrics existed (`dashboard_metrics`) but were never wired to an API/page | Empty-state / missing projection | **Fixed** |
| History | Can't be viewed | List rendered bare "Interview #N"; rows non-interactive; the backend detail endpoint was orphaned (no route/client) | Frontend wiring | **Fixed** |
| Sources | Not linked/inspectable | Public URLs exist in the manifest (31/31) but were dropped by the `/knowledge/sources` projection; some renderers showed plain text | Projection + rendering | **Fixed** |
| Review & Diagnostics | No usable data | Agent Inspector works but needs a run id (no run list); the Evaluation page was a static stub despite a working `/evaluation/*` backend | Frontend wiring + intentional limits | **Partially fixed** |

Identity is consistent across surfaces (one client `authHeaders()`; no SSR bypass). Persistence
is sound; the only cross-store nuance (Agent runs live in the LangGraph checkpoint, interviews in
the app DB) is by design.

## User identity

One mechanism attaches identity for every surface: `frontend/lib/api/client.ts` `authHeaders()`
sends `X-User-Subject` only when `NEXT_PUBLIC_DEV_USER_SUBJECT` is set; otherwise no header (dev →
anonymous `local-dev`, prod → 401 fail-closed). Every page is a `"use client"` component fetching
through this one client, so Prepare / Practice / Progress / History / Diagnostics / Feedback /
Memory all resolve to the **same** subject. This was **not** a defect. The only risk is *temporal*:
changing the dev subject (or moving to a non-dev env without a gateway) re-scopes every surface.

## Persistence map

| Surface | Store |
|---|---|
| Prepare / Agent Coach + Agent Inspector | LangGraph checkpoint (`data/agent_checkpoints.sqlite`, durable) |
| Practice, History, Progress, Memory, Feedback | app DB (`data/interview_studio.db`) |
| Evaluation (offline) | flat JSON artifacts (`evaluations/ragas/runs/*/results.json`) |

No surface writes one store and reads another. Agent runs and interviews are deliberately separate.

## Progress

- **Expected:** the candidate's journey — saved preparation memory **and** progress from completed
  practice.
- **Actual (before):** only `GET /memory`; showed "Nothing saved yet." even after completed
  practice. `InterviewRepository.dashboard_metrics(user_id)` computed real metrics but had no API.
- **Root cause:** missing API projection + a page scoped to memory only.
- **Fix:** new read-only, user-scoped `GET /api/v1/progress` (→ `history_service.practice_progress`
  → `repo.dashboard_metrics`); a `PracticeProgress` section on `/progress` showing sessions,
  answers evaluated, average practice score, most-common focus area, and recent sessions (each
  linking to its history detail). Renders nothing when there is no practice (honest empty state);
  fabricates nothing (unknown values stay null).
- **Tests:** `tests/test_api.py::test_progress_metrics_wired_and_user_scoped` (populated + empty +
  cross-user); real aggregation already covered by `tests/test_repository.py::test_dashboard_metrics`;
  frontend `frontend/tests/progress.test.tsx` (populated tiles + linked recent session + hidden when
  empty); e2e `frontend/e2e/product-surfaces.spec.ts`.

## History

- **Expected:** open a completed session and read its report.
- **Actual (before):** the list worked but rendered only "Interview #N" (metadata dropped); rows had
  no click target; `GET /history/interviews/{id}` (with the full report) existed but was never
  called; no `/history/[id]` route.
- **Root cause:** a half-built detail feature (frontend wiring).
- **Fix:** rows now show role/questions/date and link to a new `/history/[id]` page; added
  `api.history.get(id)` and typed `InterviewDetail`; `HistoryDetailClient` renders the report via a
  shared `ReportView`; a foreign/unknown id → safe not-found (never another user's data).
- **Tests:** `tests/test_api.py::test_history_detail_returns_report_for_owner` (+ the existing
  user-scoping test); frontend `frontend/tests/history-detail.test.tsx` (row link + metadata, detail
  report, 404); e2e product-surfaces spec (row → detail).

## Sources / citations

- **Evidence classes:** governed local KB (manifest), official statistics, vector passages, Adzuna
  market API, company official web. All 31 governed sources in `data/source_manifest.json` carry an
  official public `source_url`.
- **Root cause:** the `/knowledge/sources` DTO (`SourceEntryOut`) omitted `source_url`, so the
  `/sources` page could not link; the Agent Inspector rendered sources as plain text though they
  carried a URL. (Agent Coach sources already linked correctly.)
- **Fix:** `SourceEntryOut` now includes `source_url` (https-guarded via `_public_url`), `provider`,
  `country`, `reference_year`; `/sources` cards link when a URL exists (new tab,
  `rel="noopener noreferrer"`) and otherwise stay inspectable with provenance and a "Governed source
  · no public record link" note — **no fabricated URLs**; the Agent Inspector links sources.
  External/company URLs remain the External-Research layer's already-sanitised `public_url` (query
  stripped, https only, never an authenticated/API endpoint).
- **Source-link policy:** *public link available* → clickable; *internal governed source* →
  inspectable, never invented; *external current source* → sanitised public URL only.
- **Tests:** `tests/test_api.py::test_knowledge_sources_include_safe_public_url`,
  `::test_public_url_guard_drops_non_https`; frontend `frontend/tests/sources.test.tsx` (linked vs
  governed-not-linked); e2e product-surfaces spec.

## Review & Diagnostics

- **Audience:** reviewer/developer (under the "More" menu), never candidate-facing.
- **Findings:** `/review` is a working hub. The **Agent Inspector** (`/review/agent`) is fully
  functional and durable (LangGraph checkpoint) and works with Langfuse OFF, but needs a run id
  (reached via the Coach's "View run details" or pasted) — there is **no run-list endpoint**.
  `/review/rag` is an intentional legacy placeholder. `/review/evaluation` was a **static stub**
  despite a working `GET /evaluation/*` backend and on-disk RAGAS artifacts.
- **Fix:** wired `/review/evaluation` to the existing `GET /evaluation/latest` — a read-only view of
  the latest stored offline RAGAS run (metrics + run config), clearly labelled offline benchmark
  evaluation that **never triggers a paid run** and is **not** live candidate analytics. Safe fields
  only (no CoT, prompts, checkpoints or secrets — unchanged).
- **Intentional limitation (not fixed):** no per-user Agent-run index exists, so a "recent runs"
  browser would require a new persistence subsystem — out of scope for a minimal fix. The Inspector
  keeps its informative empty state ("paste a run id / open from the Coach"). Documented here.
- **Tests:** frontend `frontend/tests/evaluation.test.tsx` (metrics shown / empty state); e2e
  product-surfaces spec.

## Security / privacy

No change to trust boundaries. Sources expose only https public URLs (guarded); the Evaluation view
shows offline public-benchmark metrics only; the Agent Inspector still exposes no CoT/prompt/
checkpoint/secret; History/Progress remain strictly user-scoped (foreign id → 404/empty).

## Tests & gates

Python **2141 passed / 3 skipped** (+4 new); frontend **164 unit** (+9); Playwright **55 e2e** (+4);
ruff, compileall, OpenAPI contract, secret scan (exact CI) all pass; agent / retrieval /
external-research / feedback-intelligence / observability gates unchanged (PASS/READY).

## Known limitations

1. Progress shows defensible practice metrics only (sessions, answers evaluated, average score, top
   focus area, recent sessions) — no longitudinal trend chart (not persisted; would need new data).
2. Agent Inspector still has no run browser (no per-user run index; run id via the Coach link or
   paste). Deliberately not built here.
3. `/review/rag` remains a legacy placeholder (the Streamlit RAG diagnostic is unchanged).
4. Governed sources without a public record link are shown as inspectable provenance, never a
   fabricated URL.
