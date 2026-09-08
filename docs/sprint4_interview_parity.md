# Sprint 4 Phase 10 — Interview Practice: Streamlit ↔ Next.js parity

This matrix records the state of the Interview Practice migration from the legacy
Streamlit app to the Next.js + FastAPI stack after Phase 10. It is the source of
truth for the "Streamlit status" decision (below) and for what remains.

Legend:
- **MIGRATED** — available in Next.js over the durable FastAPI backend.
- **INTENTIONALLY DEFERRED** — not migrated this phase; not candidate-critical.
- **EXPERIMENTAL** — behind a feature flag, off by default, not release-critical.
- **DEVELOPER-ONLY** — internal tooling, never part of the candidate product.
- **OBSOLETE** — withdrawn from the product.

| Capability | Streamlit | Next.js | Status | Notes |
|---|---|---|---|---|
| Interview setup (role/industry/level/questions) | ✅ | ✅ | **MIGRATED** | Standalone setup form; backend-owned taxonomies (`/interviews/options`). |
| Career → Interview handoff (approved PreparationContext) | ✅ | ✅ | **MIGRATED** | `POST /interviews` with `preparation_context`; idempotency `agent-handoff:<run_id>`, now durable across restart. |
| Strategy generation | ✅ | ✅ | **MIGRATED** | Runs during create; unchanged domain service. |
| Main interview (question → answer → evaluation → next) | ✅ | ✅ | **MIGRATED** | Full loop in `PracticeClient`; state machine unchanged. |
| Typed answer | ✅ | ✅ | **MIGRATED** | Controlled composer; preserved on failure, cleared only after success. |
| Structured answer feedback | ✅ | ✅ | **MIGRATED** | Typed `EvaluationOut`; practice-only framing. |
| Next question | ✅ | ✅ | **MIGRATED** | One question per advance; no duplicate provider call (disabled while busy). |
| End interview early | ✅ | ✅ | **MIGRATED** | Accessible inline confirmation → `POST /complete`. |
| Deep Dive (branching) | ✅ | ✅ | **MIGRATED** | Start/answer/go-deeper/return over HTTP; main progress isolated; max depth enforced. |
| Final report / performance review | ✅ | ✅ | **MIGRATED** | Generate + persist (idempotent) + fetch; full `FinalInterviewReport`. |
| Completed history | ✅ | ✅ | **MIGRATED** | Existing history service; second-save protection preserved. |
| In-progress durability (refresh / restart resume) | ⚠️ per-browser only | ✅ | **MIGRATED (improved)** | Durable `interview_sessions` store; survives refresh AND backend restart. |
| Active/resumable session discovery | ❌ | ✅ | **MIGRATED (new)** | `GET /interviews` safe summaries; `DELETE /interviews/{id}`. |
| Error recovery (recoverable ERROR state) | ✅ | ✅ | **MIGRATED** | `POST /recover` returns to `previous_state`; UI offers Resume. |
| Cost / usage tracking | ✅ | ◑ | **MIGRATED (data)** | Recorded + durably persisted; surfaced as `cumulative_cost_usd` (diagnostic-leaning UI). |
| Record voice (speech-to-text answers) | ✅ | ❌ (removed shell) | **INTENTIONALLY DEFERRED** | No production server-side transcription boundary this release; the fake Record control was removed rather than left claiming functionality. No mic/camera access. |
| Live conversation interview | ◑ experimental | ❌ | **EXPERIMENTAL** | Feature-flagged OFF (`live_interview_enabled`); legacy/experimental, not migrated. No camera. |
| Visual/camera coaching | — | — | **OBSOLETE** | Withdrawn from the product; `visual_metrics` retained empty for schema compatibility. |
| Prompt Lab / prompt technique tooling | ✅ | ❌ | **DEVELOPER-ONLY** | Internal experimentation surface; not part of the candidate product. |
| Model profile selection (Fast/Balanced/Advanced) | ◑ | ◑ | **DEFERRED (respect 9.5)** | One session-selected profile per interview; per-operation tiering intentionally not added here. |

## Candidate-critical, non-experimental coverage

All candidate-critical, non-experimental Interview Practice features (setup, handoff,
main interview, typed answers, feedback, next, end early, Deep Dive, report, history,
durable resume, error recovery) are **MIGRATED**. The only non-migrated candidate
capability is **Record voice**, which is **intentionally deferred** (no safe
production transcription path this release) — and, crucially, no candidate-facing
control now claims recording works.

## Streamlit status

Because all candidate-critical, non-experimental features are migrated, Next.js is
the **primary** Interview Practice UI and Streamlit is **LEGACY / DEPRECATED**.
Streamlit code is **retained** (not deleted) until Phase 11 hardening, because it
still hosts deferred/experimental/developer-only surfaces (Record voice, Live,
Prompt Lab). Removal is a separate, later decision.

## In-progress durability vs completed history (do not conflate)

- **Durable interview-session store** (`interview_sessions`, Phase 10): operational,
  resumable state — the serialised `SessionData` for an interview still in progress.
- **History repository** (`interviews`/`reports`): the completed, long-term interview
  record and its report.

These are distinct stores with distinct lifecycles. A completed report is written to
history exactly once; the in-progress session row can be deleted or age out under the
retention policy (`INTERVIEW_SESSION_RETENTION_DAYS`) without touching history.

## PostgreSQL

The schema and SQL are portable (SQLAlchemy models + explicit Alembic migration
`0003_interview_sessions`, JSON payload column, `UniqueConstraint(user_id,
idempotency_key)`). CI exercises the repository against SQLite; a PostgreSQL
integration run is an environment/CI follow-up.
