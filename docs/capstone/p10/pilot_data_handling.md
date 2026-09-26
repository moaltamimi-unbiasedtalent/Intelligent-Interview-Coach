# Pilot Data Handling & Privacy

_The Ask4Mo repository is shared project evidence. **Raw participant PII must never be
committed.** This defines the private→anonymized→repository workflow, participant descriptors,
state reset, and RC versioning during the pilot._

## What must NEVER be committed
name · email · phone · a real CV · private employer information · private interview answers ·
voice/audio recordings · screenshots containing personal data · raw transcripts with
identifiable data.

## Allowed in the repository (anonymized only)
- Participant IDs **P01–P05** (no names/emails).
- Non-sensitive descriptors: general career stage, broad target role/function, prior
  interview-prep experience, pilot language, device/browser.
- Paraphrased, de-identified observations and aggregate counts.
- **Do not** collect protected characteristics unless genuinely necessary (default: don't).

## Private → anonymized → repository workflow
```
PRIVATE MODERATOR NOTES (outside the repo; may hold transient identifiable context)
        │  anonymize: strip names/emails/personal data, paraphrase, assign PXX
        ▼
REPOSITORY PILOT EVIDENCE (sessions/PXX.md, results, lessons — anonymized only)
```
- Keep any identifiable notes **outside** the repository (e.g. a local private file the
  moderator deletes after anonymizing). Document that this split was used.
- If unsure whether something is identifiable, **leave it out** of the repo.

## Recording policy
Default: **moderator notes, not audio/video.** Recording is **not** required for AC-24. If the
owner independently decides to record, obtain **explicit informed consent** first. Do **not**
build any recording capability into Ask4Mo.

## Synthetic assets (use these for core tasks)
`assets/pilot_cv.md`, `assets/pilot_job_description.md`, `assets/pilot_role_context.md` are
**synthetic** (no real person). Personal CV upload is **optional and never required**; if a
participant chooses to use their own non-sensitive context after the core tasks, do not commit it.

## State reset / isolation between participants
Each participant gets a **separate account or a separate disposable dataset** so P02 never sees
P01's data (rely on Ask4Mo's per-account isolation). Suggested reset:
- Give each participant a distinct pilot account (e.g. `p01@pilot.local`, `p02@pilot.local`), OR
- Between participants, stop the app and re-provision a fresh migrated DB
  (`rm -f /tmp/ask4mo_demo.db && DATABASE_URL=sqlite:////tmp/ask4mo_demo.db alembic upgrade head`),
  then restart (frontend :3015 / backend :8020).
- Workspace/share test data must remain isolated per participant.
- Record which reset method was used in each session record.

## RC versioning during the pilot (freeze semantics)
- Initial pilot runs on **RC-P9-001** (SHA `319759d`). No product/runtime change → RC stays valid.
- A **material runtime/code change** after pilot findings → create **RC-P9-002** (or next id) and
  record: new SHA, reason, pilot issue IDs addressed, tests/evals rerun, evaluation versions.
  Never silently mutate RC-P9-001; never mix evidence across RCs without labelling the RC.

## Retention
Delete private moderator notes once anonymized repository evidence is complete. Keep only the
anonymized records needed for AC-24 and the capstone write-up.
