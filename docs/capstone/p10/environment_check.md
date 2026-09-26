# Pre-Session Environment Checklist

_Run this BEFORE a participant is in front of you. Don't discover a broken setup with someone
watching. Tick every box; record the actuals in the session record._

## Launch (frozen RC-P9-001; ports per saved preference)
- [ ] On RC-P9-001 code (`git rev-parse HEAD` is `319759d…` or main with it merged; no local
      product edits).
- [ ] Fresh migrated DB: `rm -f /tmp/ask4mo_demo.db && DATABASE_URL=sqlite:////tmp/ask4mo_demo.db PYTHONPATH="$PWD" .venv/bin/alembic upgrade head` → head `0011_workspaces_shares`.
- [ ] Backend up on **:8020** — `API_ENV=development DATABASE_URL=sqlite:////tmp/ask4mo_demo.db FRONTEND_ORIGINS=http://localhost:3015,http://127.0.0.1:3015 .venv/bin/uvicorn src.api.main:app --host 127.0.0.1 --port 8020`; `GET /api/health` → 200.
- [ ] Frontend up on **:3015** — `NEXT_PUBLIC_API_BASE_URL=http://localhost:8020/api/v1 npm --prefix frontend run dev -- --port 3015`; `http://localhost:3015` → 200.

## Ready state
- [ ] Marketing home renders at `http://localhost:3015`.
- [ ] App home renders at `http://localhost:3015/app`.
- [ ] Participant account/dataset ready and **isolated** (see `pilot_data_handling.md` → Reset).
- [ ] History/Progress in a known/clean state for this participant.
- [ ] Synthetic **CV** (`assets/pilot_cv.md`) and **JD** (`assets/pilot_job_description.md`)
      available to hand to the participant (as text or a saved file for upload).
- [ ] Interview Practice starts and advances (quick self-check).

## Provider / capability status (record actuals)
- [ ] External **paid providers OFF** unless separately authorized (no OpenRouter/OpenAI-
      realtime/Google/Brevo/Adzuna/RAGAS). Expect Mo LLM answers to show a safe "unavailable"
      state — that is an environment limitation, not a participant failure.
- [ ] `GET /api/v1/capabilities` recorded (e.g. `agent_coach_enabled`, `realtime_voice_enabled`
      → expected **false** without keys).
- [ ] Voice: note whether the browser supports Web Speech (STT/TTS) for T8; realtime expected
      OFF → fallback.

## Record for this session
- Environment used: **A local / B screen-share / C staging** → ____
- Browser + version: ____  · OS: ____  · Screen size/device: ____
- Interface language / conversation language used: ____
- RC: **RC-P9-001** (`319759d`)
