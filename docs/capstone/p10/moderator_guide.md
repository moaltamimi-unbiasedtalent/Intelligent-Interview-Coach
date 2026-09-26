# Moderator Guide

_How to run a session so the evidence is real and useful. Give tasks, not instructions. Observe;
don't defend the product._

## Before you start
- Complete `environment_check.md`.
- Have `participant_tasks.md`, a copy of `sessions/PXX_template.md`, and the synthetic
  `assets/` open.
- Read the participant `participant_notice.md` aloud / share it; proceed only if they're
  comfortable.

## Core behaviour
- **Give the task, then be quiet.** Let the participant attempt it. Silence is data.
- Ask the participant to **think aloud** where comfortable ("tell me what you're looking at /
  expecting").
- **Do not explain controls prematurely.** Do not teach the UI before they try.
- **Do not defend the product** or justify a design. Note the reaction; move on.
- Ask **neutral** follow-ups: "What did you expect there?", "What would you do next?", "What
  made you pause?". Avoid leading questions ("Isn't this easy?", "Don't you like…?").
- **Distinguish** participant confusion from an **environment/provider limitation** (e.g. Mo's
  answer shows "unavailable" because no LLM key is configured — that is environment, not a
  usability failure). Flag it as `environment/provider limitation` in the observation.
- Capture **where** they hesitate, **where** they needed help, and **what they expected** that
  didn't happen.

## Rescue ladder (record the highest level used per task)
- **L0 — no help:** participant proceeds unaided → `COMPLETED_UNASSISTED`.
- **L1 — repeat the task:** restate the goal, no hint → still counts as unaided if they then
  succeed; note L1.
- **L2 — general hint:** "somewhere on this screen" → `COMPLETED_WITH_HINT`.
- **L3 — specific navigation help:** "open the menu, then Documents" → `COMPLETED_WITH_HELP`.
- **L4 — moderator completes the step** / participant unable → `NOT_COMPLETED`.

Prefer the lowest level that unblocks. The **level itself** is the finding — richer than
pass/fail.

## Recording completion (per task)
Use `observation_template.md`: `COMPLETED_UNASSISTED` / `COMPLETED_WITH_HINT` /
`COMPLETED_WITH_HELP` / `NOT_COMPLETED` / `NOT_RUN`, plus confusion, help level, rough duration,
a paraphrased comment, and the issue-type flags (defect / usability / trust / accessibility /
environment).

## Debrief (after tasks)
Ask the neutral trust/AI questions (`participant_tasks.md` → Debrief) **only after** they've used
the UI — never coach the answer first. Optionally collect the 1–5 ratings (descriptive only).

## Severity vs usability impact
- Real **software defect** → P0/P1/P2/P3 (P0 security/data-loss/blocker; P1 major core-flow;
  P2 material w/ workaround; P3 minor).
- **Usability finding** (not a defect) → U1–U4 (U1 prevents completion / severe
  misunderstanding; U2 meaningful friction / repeated help; U3 noticeable but proceeds; U4
  preference/polish). Don't file a preference as a bug.

## STOP rule (safety)
**Stop the pilot and do not expose more participants** if a session reveals any of:
- P0 security / data-isolation issue, or data loss;
- P1 broken authentication;
- P1 broken core Interview Practice;
- P1 cross-user private-data exposure.

Record what happened, end the session safely, and escalate for review before any further
sessions. Do not keep collecting incomparable evidence on a known-unsafe build. A fix →
**new RC** + regression gates before resuming (`pilot_data_handling.md` → RC versioning).

## Between participants
Reset/isolate state so P02 never sees P01's data (`pilot_data_handling.md` → Reset). Keep
identifiable notes (if any) **outside** the repository; only anonymized records go in
`sessions/`.
