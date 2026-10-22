# 06G pilot revalidation checklist (P2-01 to P2-04, L-AC24)

Status: **NOT RUN. No participant has been recruited and no session has been held.** This checklist prepares the human revalidation of four findings through the existing Pilot 2 pack (`docs/capstone/p10/pilot2/`). It records no result. AC-24 (pilot and lessons) stays NOT RUN / PENDING REAL PARTICIPANTS until real sessions produce evidence. The owner supplies participants, the candidate build and its SHA (OD-RESOURCE, owner).

How to use it: the facilitator follows the Pilot 2 runbook (`RC_P10_003_PILOT2_RUNBOOK.md`), uses the participant tasks (`RC_P10_003_PARTICIPANT_TASKS.md`) without leading, and records outcomes in the results template (`RC_P10_003_PILOT2_RESULTS_TEMPLATE.md`) with real denominators ("3/5"), never a percentage without counts. Participants use synthetic assets only; real names, emails, CVs, recordings and identifiable screenshots never enter git (`docs/capstone/p10/pilot_data_handling.md`). A provider-off limitation is recorded as INFRASTRUCTURE / PROVIDER LIMITATION, never as a participant failure. Observe first; ask neutral follow-ups afterwards.

## Preconditions (all must be true before the first session)

- [ ] One candidate build for the whole pilot; its SHA is written on every session record. Material runtime fixes in between start a new candidate and are not mixed.
- [ ] 3 to 5 real participants named by the owner as P01 to P05; fewer than 3 completed means the pilot is INCOMPLETE.
- [ ] Participants have consented to the session and to anonymised findings; the consent record stays outside git.
- [ ] Synthetic job description, CV and knowledge fixtures are loaded (`P2_02_ISOLATED_KNOWLEDGE_FIXTURE.md` for the representative knowledge environment).
- [ ] The facilitator is not the author of the changes under test, and any conflict with the product is written on the session record (the independence rules of `06G_HUMAN_EVAL_PROTOCOL.md` section 2 apply to the observers too).
- [ ] Language plan stated truthfully: which sessions are in which language; no language coverage is claimed that was not run.

## P2-01 Sharing and revocation discoverability (task T7)

Observe, do not lead: the participant finds how to share a report or story with a workspace member and how to revoke it, and states what a member can and cannot see.

| Observation | Record (n/N) |
|---|---|
| Found where to share, unassisted | |
| Completed a share | |
| Found revocation, unassisted | |
| Completed a revocation and confirmed the member lost access | |
| Stated correctly that joining a workspace exposes nothing private by itself | |
| Repeated confusion about who can see what | |

## P2-02 Source-backed experience in a representative knowledge environment (tasks T3, T4)

Run only against the isolated fixture, never a stripped or empty knowledge base.

| Observation | Record (n/N) |
|---|---|
| Mo answered with sources where evidence exists | |
| Mo said it could not answer where evidence did not exist (no invented figure) | |
| Participant found the Sources and opened one | |
| Participant understood what a source supports | |
| Provider-off limitations recorded as INFRASTRUCTURE, not as failure | |

## P2-03 Answer score interpretation (task T5)

| Observation | Record (n/N) |
|---|---|
| Read the score and said what it means in their own words | |
| Understood it is practice feedback, not a hiring decision | |
| Identified the next action from the feedback | |
| Misread the score (what they said it meant) | |
| Score or feedback unclear (where) | |

## P2-04 AI-generated versus sourced versus verified provenance clarity (debrief, tasks T3, T4)

| Observation | Record (n/N) |
|---|---|
| Distinguished AI-generated text from text from external sources | |
| Distinguished sourced from verified | |
| Understood what Memory saved and when | |
| Believed a depicted person was a real customer (expected: no) | |

## Score interpretation of the 06G rating (not of the pilot)

When the blinded 06G rating and the pilot are read together, keep them apart: the pilot is qualitative (no significance claimed), the rating is quantitative with its intervals (`06G_SAMPLE_SIZE_GUIDANCE.md`). A rating mean without its interval, or a pilot count without its denominator, is not reported. Neither replaces the other, and neither approves a gate.

## Provenance and sharing of results

- [ ] Every result row names the candidate SHA and the language of the session.
- [ ] Findings are anonymised (P01 to P05) before they are committed; raw evidence stays outside git.
- [ ] Issues are classified (PRODUCT-UX, MODEL-QUALITY, VOICE-TRANSCRIPTION, INFRASTRUCTURE, VISUAL-UI, PRIVACY-TRUST) with severity (BLOCKER, HIGH, MEDIUM, LOW).
- [ ] The owner, not engineering, decides what the findings change. L-AC24 changes only from this real evidence.
