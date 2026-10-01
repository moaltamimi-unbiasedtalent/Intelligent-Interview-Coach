# Pilot 2 — owner runbook (RC-P10-002)

> **STATUS UPDATE (roadmap reconciliation, main d6c3493): Pilot 2 is PAUSED.** It resumes only after candidate remediation (W9.8-W9.13) is complete, admin changes affecting support/privacy are stable, and the full integrated qualification (P10B-W11) passes against a replacement RC-P10-003 (which does not exist yet). This document and the RC-P10-002 evidence below are immutable historical record; expect the resumed pilot to use a different RC. See `docs/capstone/capstone_phase_plan.md`.

A concise, repeatable session runbook so each Pilot 2 session tests the **same** product version.
Pair this with `pilot2_readiness.md` (journey/fields/taxonomy) and the existing kit
(`participant_tasks.md`, `moderator_guide.md`, `participant_notice.md`, `pilot_data_handling.md`,
`environment_check.md`). **Do not run paid/live providers. Do not deploy.**

## Candidate (fixed for the whole pilot)
- **RC-P10-002** = origin/main `ab9ff7381ee02ed8de358e549ebf2e466e6ca08d`.
- Check out that exact SHA for every session. Confirm `git rev-parse HEAD` matches before starting.

## BEFORE each session
1. **Services**: start the backend (current code, so the Opportunity/Company routes exist) and the
   frontend. Confirm the frontend points at that backend's `/api/v1`.
2. **Account/test data**: use a **fresh account per participant** (or a fresh migrated DB) so empty
   states render genuinely. A brand-new account is gated into onboarding first (expected) — either
   complete onboarding as the participant's first step (part of T2) or pre-complete it if the pilot
   script starts past sign-in.
3. **Synthetic fixtures**: load only `assets/pilot_cv.md`, `pilot_job_description.md`,
   `pilot_role_context.md`. No real personal data.
4. **Browser/device**: Chromium-based browser (the tested engine). Desktop plus, if testing mobile,
   a 390px-wide viewport.
5. **Microphone** (only if T8 voice is in scope): confirm mic permission before the session.
6. **Consent/information**: walk through `participant_notice.md`; capture consent per
   `pilot_data_handling.md`. Recording is opt-in only.
7. **Providers**: expect deterministic/offline behaviour. If a model answer is unavailable it is an
   **environment limitation**, not a participant failure — record it as INFRASTRUCTURE, not PRODUCT/UX.

## DURING the session
- Do **not** coach unless the task explicitly permits help. Let the participant attempt first.
- Record **observations, not interpretations as facts**. Note what they did and said.
- Distinguish participant behaviour from infrastructure/model failure.
- Preserve task order (T1 -> T3a -> T3 -> T4 -> T5 -> T6 -> T7 -> T8 -> T9 -> debrief) unless there is a
  documented reason to deviate; record any deviation.
- For empty-state and imagery moments, capture the visual-system fields from `pilot2_readiness.md`
  (comprehension / hierarchy / helps-distracts-neutral / trust / provenance).

## AFTER each session
- Anonymise findings (`P01`..`P05`); keep raw personal evidence out of git.
- Record task completion (attempted / completed / completed-without-help / time).
- Classify each issue by **severity** (BLOCKER/HIGH/MEDIUM/LOW) **and** by **category** (PRODUCT-UX /
  MODEL-QUALITY / VOICE-TRANSCRIPTION / INFRASTRUCTURE / VISUAL-UI / PRIVACY-TRUST).
- Preserve quotes only when necessary and consent-compatible.
- **Do not implement fixes between participants** unless a blocker prevents the remaining pilot from
  running. If that happens, stop, record the exact candidate-version change, and note that subsequent
  participants tested a different version (a new RC).

## Session record
Copy `sessions/P01_pilot2_template.md` for each participant (P01, P02, ...). Store completed raw sheets
outside committed repo content per `pilot_data_handling.md`; commit only the minimum anonymised summary.

## After all sessions
- Aggregate into `pilot_results_template.md` (real denominators, e.g. "3/5").
- Triage per the severity/repair rules in `pilot2_readiness.md`.
- Consequential repairs -> targeted regression -> new RC (RC-P10-003). RC-P10-002 stays traceable.
- Update AC-24 only when actual human observations exist. Until then it remains NOT RUN / PENDING.
