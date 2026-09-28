# Pilot 2 — readiness & methodology (RC-P10-002)

**Candidate under test:** RC-P10-002 = origin/main `ab9ff7381ee02ed8de358e549ebf2e466e6ca08d`
(post Waves 1-8 + Stage B0 Visual System v2). **One release candidate for the whole pilot.**
**Status:** READINESS ONLY. Pilot 2 has **NOT** been run. No human observations exist yet.
**Paid/live calls:** 0. **This does not conduct or fabricate the pilot.**

Pilot 2 reuses the existing P10 pilot kit (`docs/capstone/p10/*`) — it does not replace it. This file
adds only what is new for Pilot 2: the RC pin, the Opportunity step, the visual-system observation
fields, the issue taxonomy, the severity/repair rules and the participant target. The task sheet
(`participant_tasks.md`, T1-T9 + debrief), moderator guide, participant notice, data-handling note,
synthetic assets (`assets/pilot_cv.md`, `pilot_job_description.md`, `pilot_role_context.md`) and the
observation/issue templates remain the source of truth for their areas.

## Purpose
Test RC-P10-002 as an end-to-end **candidate experience**, not a screen-by-screen inspection. Observe
behaviour first; ask neutral follow-ups afterward. This is an exploratory qualitative usability pilot —
**no statistical significance is claimed**; report actual denominators (e.g. "3/5"), never percentages.

## Participants
- Target: **3-5 actual participants supplied by the owner.** Anonymised `P01`..`P05`.
- If fewer than 3 real participants are observed, Pilot 2 is INCOMPLETE and AC-24 stays NOT RUN.

## Journey (preserves the established T-numbering; adds Opportunity)
Run in order unless a documented reason requires deviation:
1. **T1 Orient** (public Home) — comprehension of what Ask4Mo is / who it is for.
2. **T2 Get started** — sign-in / landing / notice Help & tour.
3. **T3a Opportunity (NEW, Wave 6)** — create an Opportunity for a role; observe whether "one job in one
   place" is understood, and whether the **empty Opportunities state** reads clearly before creation.
4. **T3 Prepare for a role** — JD/role prep; scannable response; Brief/Detailed; find Sources; next step.
5. **T4 Documents / evidence** — accept / correct / reject one item each; empty **Story bank** comprehension.
6. **T5 Interview Practice** — answer, submit, understand feedback, interpret score, next action.
7. **T6 Return journey** — History, Progress, a previous report, resume where applicable (empty-state
   comprehension for History and Progress if the account is new).
8. **T7 Privacy / trust** — what is private; does a workspace member auto-see the CV (expected: no);
   revoke sharing; export/delete controls; empty **Workspaces sharing** comprehension.
9. **T8 Voice (if supported in the approved methodology)** — Listen, Speak, edit transcript, explicit submit.
10. **T9 Final exploration** — perceived usefulness.
11. **Debrief** — per `participant_tasks.md` (AI-generated vs external-source vs verified; Memory; sharing;
    score clarity). Ask only AFTER use; do not coach.

## Visual-system observation fields (NEW for Pilot 2; observe, do not lead)
Do **not** ask "do the new images make it better?" Observe behaviour, then ask neutrally.
Capture, where relevant:
- **Initial product comprehension** — did imagery on Home/Product help or hinder understanding of what
  Ask4Mo is (before reading much copy)?
- **Visual hierarchy** — did the eye go to the right place (headline/CTA) or did an image dominate?
- **Imagery helps / distracts / neutral** — per surface, one of {helps, distracts, neutral}.
- **Empty-state comprehension** — on a genuinely empty Opportunities/Company/Documents-story-bank/
  Progress/History/Workspaces surface, did the illustration + message make the next action clear?
- **Perceived trust** — did the Trust/About imagery affect perceived trustworthiness (up/down/none)?
- **Evidence/privacy boundary understanding** — did any image cause a participant to believe a depicted
  person was a real customer/employee (provenance failure)? Expected: no.

## Issue taxonomy (keep categories SEPARATE; do not collapse into one failure count)
- **PRODUCT/UX** — flow, navigation, terminology, controls.
- **MODEL QUALITY** — relevance/quality of model output (where a model path is exercised).
- **VOICE/TRANSCRIPTION** — STT/TTS behaviour, transcript editing, submit.
- **INFRASTRUCTURE** — service/availability/latency/environment failures (not participant error).
- **VISUAL/UI** — imagery placement, scale, overflow, distraction, empty-state clarity, provenance.
- **PRIVACY/TRUST** — comprehension of privacy boundaries, sharing, evidence/AI-vs-fact separation.

For each task capture where applicable: attempted? · completed? · completed **without help**? ·
completion time · confusion · navigation error · help requested · terminology confusion · source/
evidence comprehension · privacy/trust comprehension · voice/transcription issue · visual comprehension
issue · infrastructure failure · model-quality issue · participant comment · moderator observation.
Distinguish **participant behaviour** from **infrastructure/model** failure.

## Severity & repair rules (post-pilot triage; prepared now, applied later)
- **BLOCKER** — participant cannot complete a core journey.
- **HIGH** — core journey materially confusing, unsafe or unreliable.
- **MEDIUM** — usability issue with a workable path.
- **LOW** — polish/cosmetic; does not materially obstruct the journey.

Prioritise: (1) blockers; (2) repeated confusion; (3) safety/privacy/trust problems; (4) failures
affecting core task completion; (5) high-value bounded usability fixes. Do **not** auto-implement every
suggestion. Consequential repairs get targeted regression + release qualification and a **new RC**
(RC-P10-003); RC-P10-002 must remain traceable to `ab9ff73`. Do not silently mutate the candidate.

## Privacy controls
Use the synthetic CV/JD/role assets by default. Do not request unnecessary participant personal data.
Never commit real participant CVs, recordings, names, emails or other personal data to git. Recording is
opt-in only if it is part of the existing approved methodology (`pilot_data_handling.md`). Anonymise as
`P01`..`P05`. Keep raw participant evidence outside committed repo content; committed findings hold only
the minimum anonymised evidence needed for the Capstone.

## Acceptance status after this stage
- Deterministic release qualification: **GREEN** (RC-P10-002 gate).
- Visual-system qualification: **GREEN**.
- Internal readiness: **READY**.
- Human pilot (AC-24): **NOT RUN / PENDING PILOT 2**.
- Live-provider validation: **NOT RUN**.
- Hosted/deployment (EX-12): **BLOCKED / NOT RUN**.
Pilot readiness is not pilot completion. Green CI/internal QA is not human-usability evidence.
