# Pilot 2 — owner runbook (RC-P10-003)

Every session tests the **same** product version. Pair with `RC_P10_003_PILOT2_READINESS.md` and `RC_P10_003_PARTICIPANT_TASKS.md`. **No paid/live providers. No deployment. Do not start a session until the environment gate passes.**

## Candidate (fixed for the whole pilot)
RC-P10-003, product SHA `54aad500ec937b4828984c32c64b77746534633d`. Do NOT test current main. Pilot documentation may be read from current main.

Operating model:
- **Product runtime:** a detached worktree at the candidate SHA, e.g. `git worktree add --detach <path> 54aad500ec937b4828984c32c64b77746534633d`. Run backend and frontend from inside it. Its `data/` directory starts empty, so the relative default paths (`data/cache/external`, Chroma, knowledge, checkpoint) resolve inside that worktree and never touch the developer's stores.
- **Moderator documentation:** the current main checkout (read-only).
- **State:** a fresh throwaway database per participant (or an equally isolated fresh environment); never reuse participant state.

## Environment gate (ALL must hold; any failure = NO SESSION)
1. Product runtime `git rev-parse HEAD` == `54aad500ec937b4828984c32c64b77746534633d`, with no local product edits.
2. Throwaway/fresh pilot DB, migrated to head (`DATABASE_URL=sqlite:////tmp/<name>.db alembic upgrade head`).
3. No protected developer DB path anywhere in the environment; `DATABASE_URL` is never the default.
4. Isolated cache paths: the process runs with the candidate worktree as its working directory (the research cache is relative to the cwd); nothing points at the developer `data/`.
5. A fresh candidate account for this participant, isolated from every other.
6. Synthetic fixtures ready (`../assets/pilot_cv.md`, `pilot_job_description.md`, `pilot_role_context.md`).
7. Frontend and backend healthy (`/api/v1/health`; the frontend points at that backend's `/api/v1`; backend CORS allows the frontend origin).
8. No live provider credentials loaded (OpenRouter, OpenAI realtime, Google, Brevo, Adzuna, or any paid/live integration) unless separately approved in writing.
9. A Chromium-based browser (the tested engine); for the mobile condition a 390px viewport.
10. Consent materials ready (`../participant_notice.md`, `../pilot_data_handling.md`).
11. Moderator session sheet ready (copy of `sessions/P01_RC_P10_003_TEMPLATE.md`).

Also record: `GET /api/v1/capabilities` actuals and whether the browser supports Web Speech (T8 scope; realtime voice is expected OFF without keys). Without the developer knowledge datasets some knowledge-grounded answers will be empty: that is an INFRASTRUCTURE limitation to record, not a participant failure. Never copy, link or mount the developer stores to compensate.

## Protected stores stay frozen
Developer DB `81eef3479704ed91e58abb876926f98108968842`; schema 224 sqlite_master objects; checkpoint `b56d0c39fbba64786495ebb5db59eedecfae5c71`; Chroma `6357c057606273f313b408cc7f144390453a0832`; research cache `25264b17b36f7a365ff8dfaca9eec97e997ee710`; `evaluations/` `67259aba185daa495f8bf8958e1c905fd086b2be`. Fingerprint before the first and after the last session; any change is a stop-and-report event.

## DURING a session
Do not coach unless a task explicitly permits it. Record observations, not interpretations as facts. Separate participant behaviour from infrastructure/model failure. Keep the task order; record any deviation. Capture the visual fields from the readiness document.

## AFTER a session
Anonymise (P01…); raw evidence stays outside git; record attempted / completed / completed-without-help / rescue level / time; classify each issue by severity and category; quotes only when necessary and consent-compatible; no fixes between participants (stop rules apply). Tear down the participant's throwaway environment.

## After all sessions
Aggregate into the results template with real denominators; triage; consequential repairs → targeted regression → new RC (expected RC-P10-004), RC-P10-003 stays traceable. Update AC-24 only from real human observations.
