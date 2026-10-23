# 04F Dictation correction-burden protocol and harness

**This is a harness, not a result.** No participant has dictated anything for it. It makes no measurement claim and defines no pass or fail threshold (the owner decides acceptance). The live run is **OPEN / NOT RUN** and needs appointed test participants (acceptance items AC-13 and AC-23-A).

Tool: `scripts/dictation_burden.py` (standard library only; no audio, no network, no provider). Prompts: `evaluations/dictation_burden/prompts_v1.json` (five invented, personal-data-free sentences per language for the seven speech languages; Russian is not offered; the non-English sentences are engineering drafts that a native speaker must confirm before a session). Tests: `tests/test_dictation_burden_04f.py`.

## Protocol for a human session

Preparation (organiser)
1. Appoint participants who speak the language natively and agree to take part; give each a pseudonymous code (`P01`; never a name or email, the tool rejects an email-like code).
2. Fix the browser, version, operating system, microphone type and room for the session; one sheet per participant, language and browser. Do not pool different engines.
3. `python scripts/dictation_burden.py template --language de-DE --participant P01 --browser "Chrome 130" -o p01_de.json`

Session (participant, with the production Prepare page, dictation language set to the sheet language)
4. Read the printed prompt aloud ONCE, naturally, using the microphone button.
5. Before touching the field, copy its text exactly into `raw`.
6. Correct the field until it says what the prompt says; copy the result into `final`.
7. Repeat for the five prompts. No audio recording of any kind. Note any unsupported-language message or permission problem in the session notes (not in the sheet).

Scoring (organiser)
8. `python scripts/dictation_burden.py score p01_de.json -o p01_de_results.json` (fails closed with exit code 2 on an invalid sheet: unknown language, out-of-range prompt, missing field, email-like participant code, wrong `data_origin`).

## Definitions

Word level, after normalisation: Unicode NFC, case-folded (so the German sharp s becomes "ss" on both sides), punctuation removed from the edges of each word, inner hyphens and apostrophes kept.

| Term | Meaning |
|---|---|
| edits | minimum word insertions + deletions + substitutions turning `raw` into `final` (Levenshtein over words; the total is unique, the split between kinds uses a fixed tie-break) |
| correction burden | edits / words in `final` x 100: edit operations per 100 intended words; 0 means no correction was needed |
| per-word edit distance | edits / words in `final` (same quantity as a fraction) |
| residual error | edits between `final` and the printed prompt; non-zero means the tester left a mismatch, reported and never hidden |
| pooled burden | total edits / total final words, per language and overall |

Reported per language: trials, participants, words, edits split by kind, pooled burden, median / min / max trial burden, trials with residual error. Not reported: any verdict.

## Limits (printed in every result file)

- Word level only: punctuation is ignored, so the effort of fixing punctuation is not counted.
- Depends on accent, microphone, room, browser engine and version.
- No audio is captured; recognition quality of the engine itself (raw accuracy against the prompt) is not scored separately, only what the tester had to change.
- No acceptance threshold is built in; a small participant count is shown as it is and must not be extrapolated.

## Worked example on FAKE data

`python scripts/dictation_burden.py example -o <dir>` writes `sheet.json` and `results.json` there. The sheet has `data_origin = synthetic_example`, invented participants `FAKE-A` and `FAKE-B` and invented dictation outputs:

| Trial | raw (as dictated) differs from final by | edits | final words | burden |
|---|---|---|---|---|
| en-US prompt 1 | "the" missing (1 insertion), "problem" for "problems" (1 substitution) | 2 | 17 | 11.76 |
| en-US prompt 3 | nothing | 0 | 19 | 0.00 |
| de-DE prompt 1 | stray "äh" (1 deletion), "Interview" for "Interviewerin" (1 substitution) | 2 | 15 | 13.33 |

Pooled: 4 edits over 51 words = 7.84 per 100 words (1 insertion, 1 deletion, 2 substitutions), median trial burden 11.76. These numbers demonstrate the arithmetic only; they say nothing about any browser or language, and the test `test_worked_example_is_synthetic_hand_checkable_and_carries_the_banner` pins them.

## What still has to happen (OPEN)

1. Owner appoints participants and sets the browsers and the acceptance threshold (if any).
2. Native speakers confirm the prompt sentences read naturally in their language.
3. Run the sessions, score the sheets, store results with `data_origin = human_session`.
4. Only then can AC-13 / AC-23-A be assessed; until then they remain NOT RUN.
