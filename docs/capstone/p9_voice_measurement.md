# P9 Voice Measurement Set (AC-23)

_A bounded, reproducible voice-measurement plan with **synthetic/public reference utterances**
(no private candidate recordings). English + German are included because the controlling
acceptance explicitly requires them; the product configures seven languages, but this document
does NOT claim human-quality validation for any language._

## Scope & honesty
- **Deterministic UI latency** (Listen/Speak controls, state transitions) is measurable locally
  and separated from **provider round-trip latency**.
- **Fake-adapter timings are NOT provider latency** and are never reported as such.
- **Live browser STT correction burden**: measurable only in a real browser Web Speech
  environment. The CI/dev environment here uses deterministic fakes (no real microphone/engine),
  so the **live correction-burden portion is NOT RUN** — it is not simulated via the fake adapter.
- **Realtime provider latency**: NOT RUN (no authorized realtime key) — part of EX-02 live.

## Reference utterances (synthetic; expected transcripts)
Five categories per language: short answer, medium answer, career terminology, numbers/date,
proper-noun/technical term.

### English (EN)
| # | Category | Reference transcript |
|---|---|---|
| EN-1 | short | "I led the migration." |
| EN-2 | medium | "I coordinated three teams to deliver the platform on schedule and under budget." |
| EN-3 | career term | "I improved stakeholder alignment and cross-functional delivery." |
| EN-4 | numbers/date | "We cut latency by 42 percent between March and September 2025." |
| EN-5 | proper noun/technical | "I deployed the service on Kubernetes with an ISO 27001 control set." |

### German (DE)
| # | Category | Reference transcript |
|---|---|---|
| DE-1 | short | "Ich habe die Migration geleitet." |
| DE-2 | medium | "Ich habe drei Teams koordiniert, um die Plattform termingerecht und im Budget zu liefern." |
| DE-3 | career term | "Ich habe die Abstimmung mit Stakeholdern und die bereichsübergreifende Lieferung verbessert." |
| DE-4 | numbers/date | "Wir haben die Latenz zwischen März und September 2025 um 42 Prozent reduziert." |
| DE-5 | proper noun/technical | "Ich habe den Dienst auf Kubernetes mit einem ISO-27001-Kontrollsatz bereitgestellt." |

## Correction-burden metric (definition, ready to run live)
When a real browser STT environment is available and legitimately testable **without paid
provider activation**, measure per utterance:

`edit_distance = Levenshtein(word-level)(recognized, reference)` and
`correction_burden = edit_distance / reference_word_count`.

Record: browser, OS, language, environment, sample count, median + p95. A `correction_burden`
of 0 means the recognition matched the reference exactly.

## Status (this environment)
| Aspect | EN | DE | Notes |
|---|---|---|---|
| Reference transcripts defined | ✅ | ✅ | above (synthetic) |
| Config / locale mapping | ✅ | ✅ | 7-locale `ttsLocales`/dictation locales; `voice_experience` eval |
| Deterministic UI latency | ✅ | ✅ | control render + state transition < a few ms (React state); see perf summary |
| Live browser STT correction burden | **NOT RUN** | **NOT RUN** | no real Web Speech engine in CI/dev; not simulated via fake |
| Provider round-trip latency (realtime) | **NOT RUN** | **NOT RUN** | no authorized realtime key (EX-02 live) |
| Human voice-quality review | **NOT RUN** | **NOT RUN** | no human review claimed |

## AC-23 disposition
**PARTIAL** — the measurement set, reference transcripts (EN+DE), metric definition and
deterministic UI-latency portion are delivered; the live correction-burden and provider-latency
portions are honestly **NOT RUN** and must not be faked. Seven languages remain
**CONFIGURED**, not **HUMAN-VALIDATED**.
