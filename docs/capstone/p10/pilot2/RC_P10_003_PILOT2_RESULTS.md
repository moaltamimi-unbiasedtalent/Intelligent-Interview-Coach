# Pilot 2 results (RC-P10-003)

**Status: HUMAN EVIDENCE CAPTURED (n=3 complete structured sessions).** **Formal verdict: CONDITIONAL GO - TARGETED REMEDIATION REQUIRED.** **AC-24: PARTIAL** (human evidence captured; consequential-fix regression closure still pending, see section 11). This wave is evidence, documentation and process only: no product fix, no RC change, no Admin permission change.

Companion documents: [issue register](RC_P10_003_PILOT2_ISSUE_REGISTER.md), [triage and remediation backlog](RC_P10_003_PILOT2_TRIAGE.md), [anonymised participant summaries](RC_P10_003_PILOT2_PARTICIPANT_SUMMARIES.md), and the preparation pack ([reactivation](RC_P10_003_PILOT2_REACTIVATION.md), [readiness](RC_P10_003_PILOT2_READINESS.md), [runbook](RC_P10_003_PILOT2_RUNBOOK.md)).

## 1. Candidate under test
- Candidate: RC-P10-003 (artifact RC, not a Git tag). Candidate SHA: `54aad500ec937b4828984c32c64b77746534633d`. RC-P10-003 is immutable and is not repinned by this wave.
- Pilot environment: an isolated candidate worktree with throwaway state, paid and live providers off (0 paid/live calls). The developer knowledge datasets were deliberately NOT available (see section 8).

## 2. Evidence scope and privacy
- The owner's comparison form listed six participants (P01 to P06). **Only three sessions (P02, P04, P06) carry substantially complete structured task and rating evidence. They are the only sessions counted.**
- P01, P03 and P05 have mostly blank task and rating evidence. They are **not counted, not inferred and not back-filled**: no completion, rating or observation is invented for them. This is **not** 6/6 and **not** a six-participant result.
- All quantitative results below are **n=3**. They are descriptive counts and means for an exploratory usability pilot: no statistical significance, percentage of a population or outcome claim is made.
- The raw form contained participant names. **No name, email, identifiable CV detail, transcript, recording or screenshot is committed.** The raw form is not committed; only anonymised summaries exist.

## 3. Participant and environment coverage (counted sessions)
| | P02 | P04 | P06 |
|---|---|---|---|
| Interface language | Italian | English | English |
| Mo conversation language | English | English | English |
| Device | MacBook Pro | MacBook Pro | MacBook Pro |
| Browser | Safari | Safari | Opera first (voice recording failed), Safari (voice worked) |
| Voice tested | yes | yes | yes |
| Career stage | Executive | experienced HR / onboarding professional | Retired |
| AI experience (1 to 5) | 4 | 1 | 2 |

Coverage statements (no broader claim is made):
- **Non-English:** one fully evidenced non-English session (Italian interface).
- **German:** German was used by some listed participants, but their structured evidence is incomplete, so there is **no German session result**.
- **Mobile:** not evidenced.
- **Browsers:** Safari has useful evidence; Opera has one voice-compatibility observation; no cross-browser claim.
- **Voice:** tested by all three counted sessions.
- **Knowledge / Sources:** not validated (section 8).

## 4. Quantitative ratings (1 to 5, n=3)
| # | Dimension | P02 | P04 | P06 | Mean |
|---|---|---|---|---|---|
| 1 | Ease of getting started | 4 | 5 | 5 | 4.67 |
| 2 | Ease of navigation | 4 | 5 | 5 | 4.67 |
| 3 | Clarity of the Opportunity concept | 4 | 5 | 5 | 4.67 |
| 4 | Clarity of Mo guidance | 3 | 5 | 5 | 4.33 |
| 5 | Usefulness of Interview Practice | 4 | 5 | 5 | 4.67 |
| 6 | Clarity of feedback and scores | 3 | 5 | 3 | 3.67 |
| 7 | Confidence in Sources / evidence | 4 | 4 | 4 | 4.00 |
| 8 | Confidence that data stays private | 4 | 4 | 4 | 4.00 |
| 9 | Overall trust | 4 | 5 | 4 | 4.33 |
| 10 | Overall visual quality | 4 | 4 | 4 | 4.00 |
| 11 | Likelihood of using Ask4Mo | 4 | 5 | 4 | 4.33 |
| 12 | Likelihood of recommending Ask4Mo | 4 | 5 | 4 | 4.33 |

Means were recomputed from the source values. Per-participant averages: P02 3.83, P04 4.75, P06 4.33. **Overall average across all 36 recorded ratings: 4.31 / 5 (155 / 36), n=3.** The lowest dimension is feedback/score clarity (3.67); the highest are getting started, navigation, Opportunity clarity and Practice usefulness (4.67 each). Confidence in Sources/evidence (4.00) was rated with Sources unavailable in the pilot environment and must not be read as validation of source-backed answers.

## 5. Moderator scorecard
Codes: U unaided, H1 hint, H2 substantial help, F failed, I infrastructure limitation, N/A not applicable, `?` insufficient evidence. Nothing is guessed; a cell is filled only where the evidence supports it for that participant.

| Task | P01 | P02 | P03 | P04 | P05 | P06 | Evidenced result |
|---|---|---|---|---|---|---|---|
| T1 Orientation | ? | ? | ? | ? | ? | ? | no task-level outcome recorded |
| T2 Onboarding | ? | ? | ? | ? | ? | ? | outcome not recorded; explanation gap noted (P2-05) |
| T3a Opportunity (create) | ? | U | ? | U | ? | U | 3 of 3 evidenced sessions unaided |
| T3 Prepare | ? | ? | ? | ? | ? | ? | Mo guidance rated 3, 5, 5; Sources unavailable (I) |
| T4 Documents (upload, accept/correct/reject) | ? | U | ? | U | ? | U | upload unaided and controls understood in 3 of 3 |
| T5 Practice (start, question, submit) | ? | U | ? | U | ? | U | start and question clarity rated 5 by all three; submission clear |
| T6 Return journey (History / Progress) | ? | ? | ? | ? | ? | ? | generally discoverable (qualitative); per-participant outcome not recorded |
| T7 Privacy: locate sharing and revoke controls | ? | F | ? | F | ? | F | **0 of 3 located them** (P2-01) |
| T8 Voice | ? | U | ? | U | ? | I then U | tested by 3 of 3; P06 failed in Opera (infrastructure/compatibility), worked in Safari |
| T9 Final exploration | ? | ? | ? | ? | ? | ? | no task-level outcome recorded |

Denominators: **every count above is out of the 3 evidenced sessions, never out of 6.** Unaided totals: T3a 3/3, T4 3/3, T5 (start/submit) 3/3, T8 3/3 tested (2 of 3 without any infrastructure event). T7 sharing/revocation discoverability 0/3. For P01, P03 and P05 every cell is `?`.

## 6. Validated strengths (evidence-backed, n=3)
- **Opportunity:** "one job in one place" made sense; creation was unaided; clarity rated 4, 5, 5.
- **Documents and evidence:** upload unaided; accept / correct / reject controls understood; trust in the evidence representation was high. The longer-term value of the Story Bank was not exercised.
- **Interview Practice:** starting and question clarity rated 5 by all three; submission clear; considered useful; participants said they would use it for real interview preparation.
- **Progress and History:** discoverable; participants generally knew where to continue later; the link to a job was understandable.
- **Voice (where tested):** easy to start, editable transcript and explicit submit understood, felt easier and more realistic.
- **Trust:** overall trust 4.33.
These are strengths of a small, exploratory sample and are not generalised.

## 7. Issues and findings
No BLOCKER was observed. See the [issue register](RC_P10_003_PILOT2_ISSUE_REGISTER.md) for evidence, category, severity and status. Summary: **1 HIGH** (P2-01 sharing/revocation discoverability, usability U2, not a data leak), **5 MEDIUM** (P2-03 score interpretation, P2-04 provenance clarity, P2-05 onboarding benefits, P2-06 pricing/positioning, P2-08 Mo naturalness), **1 validation gap** (P2-02 Sources/knowledge not validated), **1 candidate enhancement** (P2-07 Candidate Progress Intelligence) and **1 item awaiting reproduction** (P2-09 Opera voice, severity unrated until reproduced).

## 8. Environment constraints and validation gaps
- The pilot ran from an isolated candidate worktree without the developer knowledge datasets and with providers off. Sources were unavailable in several sessions and Mo did not consistently surface knowledge-backed evidence.
- **Conclusion: the source-backed experience was NOT fully validated by Pilot 2.** This is an environment limitation, not an automatic product defect. Before the next human validation a safe, isolated, representative knowledge fixture or reproducible pilot knowledge environment is needed. The protected developer knowledge base must not be copied or linked.
- Live providers, hosted operation, mobile and cross-browser behaviour remain unvalidated.

## 9. Evidence ambiguity (recorded, not resolved)
The source form contains inconsistent answers to "is a CV automatically visible to a workspace member?": some participant cells read "Yes", while the following row says the expected answer "No" was understood. **This is recorded as EVIDENCE AMBIGUITY.** It is not resolved silently and no "correctly understood private-by-default" count is reported for it. The broader privacy rating (4.00, n=3) is reported separately and is not a substitute.

## 10. Formal verdict
# CONDITIONAL GO - TARGETED REMEDIATION REQUIRED
The core journey is validated (Opportunity, Documents, Practice, Progress/History, Voice), no BLOCKER or unsafe issue was observed, and overall trust is strong. Material but bounded candidate-experience issues remain: sharing/revocation discoverability, score explanation, provenance clarity, and an unvalidated source-backed experience. One browser-specific voice observation needs reproduction. It is **not** "GO" (P1 items are open) and **not** "STOP / new RC required" (nothing unsafe was found).

## 11. AC-24 decision
- **Criterion** (`p10/pilot_plan.md`, `p10/pilot_lessons_template.md`): at least 3 actual participants; sessions on an identified RC; anonymised observations; participant findings distinguished from internal observations; lessons synthesised; **consequential fixes regression-tested (new RC if runtime changed)**; unresolved issues disclosed; no fabricated or LLM-generated responses.
- **Met by this evidence:** 3 actual participants (n=3 complete structured sessions); RC-P10-003 identified; observations anonymised; participant findings kept separate from internal observation; lessons synthesised here; unresolved issues disclosed; no fabricated data (three further listed participants lacked sufficient structured evidence and were excluded).
- **Not yet met:** the consequential P1 findings have no fix and therefore no regression check or new RC yet.
- **Decision: AC-24 moves from NOT RUN / PENDING PILOT 2 to PARTIAL**, not PASS. It can move to PASS only after the P1 remediation is regression-tested (and a new RC if runtime changed). The criterion is not weakened.

## 12. Recommendation
Proceed to targeted remediation in the order set out in the [triage](RC_P10_003_PILOT2_TRIAGE.md). Do not start P10C, create RC-P10-004 or change any permission as part of this wave.
