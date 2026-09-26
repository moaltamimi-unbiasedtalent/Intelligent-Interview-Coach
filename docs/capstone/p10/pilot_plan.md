# Ask4Mo P10 — Participant Pilot Plan (AC-24)

_Capstone P10A: **preparation only.** This kit lets the owner run a small, moderated,
qualitative usability pilot with **3–5 real people** against a frozen release candidate. It
contains **no fabricated results** — participant records are filled in only after real sessions._

- **Release candidate under test:** RC-P9-001 · code/eval SHA `319759db1dd7c91ddd6ca313837326c40e05219c`
- **AC-24 status after P10A:** **NOT RUN / PILOT PREPARED** (do not mark PASS)
- **This kit changed no product/runtime code** (RC-P9-001 preserved).

## AC-24 boundary (exact)
> _Pilot and lessons: actual participant observations are distinguished from internal review;
> consequential fixes receive regression checks._ An exploratory **3–5 person** pilot supports
> **qualitative usability findings**, not broad statistical outcome claims.

- **Target:** 3–5 actual people (minimum 3 for AC-24).
- **Purpose:** qualitative usability / comprehension / trust / workflow evidence.
- **NOT the purpose:** statistical proof, hiring-outcome validation, efficacy research, or any
  "improves employment probability by X%" claim. With n=3–5 we report **counts descriptively**
  (e.g. "3/5 …"), never percentages of a population, confidence intervals or significance.
- **What does NOT count as AC-24 evidence:** synthetic personas, LLM-generated feedback,
  developer imagination, automated browser tests, or Claude role-playing a participant.

## Pilot mode (no public deployment)
EX-12 remains **BLOCKED / NOT RUN**. Run via one of:
- **A. Moderated local session** on the owner's machine (default; simplest privacy).
- **B. Moderated screen-share** of a controlled dev environment.
- **C. Private staging** — only if separately authorized (not by this task).

Record which environment was actually used, per participant, in the session record. Public
deployment is **not** part of P10.

## Environment (matches the saved launch preference)
- Frontend (Next.js dev): **http://localhost:3015**
- Backend (FastAPI): **http://127.0.0.1:8020** (`API_ENV=development`, fresh migrated
  `sqlite:////tmp/ask4mo_demo.db`, `FRONTEND_ORIGINS` includes the 3015 origins).
- External paid providers **OFF** (no OpenRouter/OpenAI-realtime/Google/Brevo/Adzuna/RAGAS).
  Mo's LLM answers will show a safe "unavailable" state without a key — that is an
  **environment limitation**, not a participant failure. Realtime voice is OFF → fallback.
- See `environment_check.md` for the pre-session checklist.

## Release-candidate freeze
All initial participants test the **same** RC-P9-001. Do **not** change product behaviour
between participants because one participant dislikes something — collect observations against
one stable build. **Exception:** if a P0 or P1 defect makes continued use unsafe or meaningless,
**STOP** (see `moderator_guide.md` → Stop rule). A material runtime repair requires a **new RC**
(RC-P9-002…), the applicable P9 regression gates, and pilot evidence separated by RC — never
attach RC-P9-001 proof to changed runtime code.

## Participants (3–5)
Prefer a small mix of career/interview contexts if reasonably available. Use anonymous IDs
**P01–P05**. Non-sensitive descriptors only (career stage, broad target function, prior
interview-prep experience, pilot language, device/browser). **Do not** collect names, emails,
phone numbers or protected characteristics in the repository. See `pilot_data_handling.md`.

## Session structure (~45–60 min per participant)
1. Welcome + read `participant_notice.md` (consent to proceed, verbal). ~5 min
2. Tasks T1–T9 from `participant_tasks.md`, think-aloud, moderator observing. ~35–45 min
3. Debrief (trust/AI questions + optional 1–5 ratings). ~10 min
4. Reset state before the next participant (`pilot_data_handling.md` → Reset).

## Data captured
Per task: the fields in `observation_template.md` (completion level, moderator help level,
confusion, comment paraphrase, and issue-type flags). Aggregate into `pilot_results_template.md`;
synthesize into `pilot_lessons_template.md`. Log issues in `issue_log_template.md`.

## Fix discipline (AC-24)
A suggestion is **evidence, not a command.** Evaluate frequency, severity, task impact, strategy
fit, security/privacy/accessibility impact, complexity and whether it's mere preference
(`issue_log_template.md`). For every **consequential fix (P0/P1/P2)**: reproduce → smallest
root-cause fix → add/extend regression coverage → run affected evals + the release gate → record
under a **new RC**. Usability findings that are not software defects use the U1–U4 impact scale.

## Files in this kit
| File | Purpose |
|---|---|
| `pilot_plan.md` | this master plan |
| `participant_notice.md` | plain-language pilot notice (engineering draft) |
| `moderator_guide.md` | moderator behaviour, rescue ladder, stop rule |
| `participant_tasks.md` | T1–T9 task sheet |
| `observation_template.md` | per-task observation fields |
| `issue_log_template.md` | structured issue log |
| `pilot_results_template.md` | aggregated result schema |
| `pilot_lessons_template.md` | traceable lesson format |
| `pilot_data_handling.md` | privacy, PII boundary, reset, RC versioning |
| `environment_check.md` | pre-session setup checklist |
| `sessions/P01_template.md` | blank per-participant record (copy per participant) |
| `assets/pilot_cv.md` | synthetic CV fixture |
| `assets/pilot_job_description.md` | synthetic JD fixture |
| `assets/pilot_role_context.md` | prepared role scenario |

## What the human owner must do next (P10B)
1. Recruit 3–5 actual participants.
2. Run the sessions on RC-P9-001 using this kit.
3. Record **anonymized** observations (copy `sessions/P01_template.md` per participant).
4. Return the observations/results for **P10B** (synthesis + consequential fixes + AC-24).

Until real observations exist, **AC-24 = NOT RUN / PILOT PREPARED.**
