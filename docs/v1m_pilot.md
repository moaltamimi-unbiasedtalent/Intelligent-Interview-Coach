# V1M System One shadow pilot

## Scope

The V1M pilot is an advisory, deterministic-decision shadow evaluator. It is
disabled by default and does not change candidate routing, retrieval, synthesis,
specialist execution, or interview evaluation.

The pilot sends only a bounded, synthetic or caller-supplied state of at most
512 characters. Live use requires `V1M_PILOT_ENABLED=true` and
`V1M_API_KEY`. The credential is treated as a paid/provider secret and is
withheld when `ASK4MO_PROVIDER_MODE=offline`.

Implementation:

- `src/copilot/rag/v1m_pilot.py`
- `scripts/eval_v1m_pilot.py`
- `evaluations/v1m/pilot_cases.json`
- `tests/test_v1m_pilot.py`

## Implemented micro-decisions

The shadow model is limited to five closed two/three-label decisions:

| Use case | Labels | Existing deterministic baseline |
|---|---|---|
| Career retrieval need | `retrieval_needed`, `retrieval_not_needed` | Heuristic intent and fixed routing table |
| Target role ambiguity | `role_ambiguous`, `role_unambiguous` | Occupation resolver and repository candidates |
| Utterance type | `smalltalk`, `candidate_question` | Existing intent heuristic |
| Specialist call | `specialist_needed`, `specialist_not_needed` | Pure specialist recommendation from known context |
| Continue versus clarify | `continue_without_clarification`, `needs_clarification` | Existing ambiguity and missing-input gates |

Each label set is fixed in code. V1M receives at most 512 characters and never
receives a candidate document, interview answer, memory, retrieved evidence, or
another private content object.

## Run

Offline-only fixture evaluation:

```bash
PYTHONPATH=. .venv/bin/python scripts/eval_v1m_pilot.py
```

All five use cases, offline:

```bash
PYTHONPATH=. .venv/bin/python scripts/eval_v1m_pilot.py --use-cases
```

Opt-in live synthetic evaluation:

```bash
PYTHONPATH=. V1M_PILOT_ENABLED=true .venv/bin/python \
  scripts/eval_v1m_pilot.py --live --threshold 0.85
```

All five use cases, live synthetic fixtures only:

```bash
PYTHONPATH=. V1M_PILOT_ENABLED=true .venv/bin/python \
  scripts/eval_v1m_pilot.py --use-cases --live --threshold 0.85
```

Live mode sends only the committed synthetic fixtures. It never sends candidate
documents, interview answers, memory, or retrieved evidence.

## Initial live evidence

An opt-in synthetic run on 2026-11-25 using the two-label `choice` primitive
returned exact-label agreement for 4 of 10 fixtures, with 2 provider timeouts.
It consistently lacked discriminative behavior on greetings and short interface
instructions. The key returned valid 200 responses from `POST
/v1/systemone`; model discovery at `GET /v1/models` was not authenticated, and
the separate `POST /api/v1/systemone/decide` route returned 404.

This run is not a qualification, benchmark, or production recommendation. It
supports keeping V1M disabled and not using it for routing or candidate-facing
decisions.

## 30-case shadow extension

An opt-in 2026-11-25 run across all five synthetic use cases returned:

- 30 fixtures requested.
- 10 exact expected-label matches.
- 8 provider timeouts.
- 12 additional returned labels that did not match the fixture expectation.
- 0 uncertain labels under the 0.85 threshold.

Observed patterns included:

- Role ambiguity was usually collapsed to `role_unambiguous`.
- Clarification decisions were usually collapsed to
  `continue_without_clarification`.
- Specialist calls were often returned for states with no specialist context.
- Candidate questions and small talk were not consistently separated.
- Successful response latency was roughly 675–963 ms; timeouts reached the
  10-second limit.

This run is a bounded research sample, not a statistically robust benchmark.
It further supports keeping V1M shadow-only and does not establish live
production readiness.

## Stakeholder assessment

**Current value:** low-to-medium as a shadow research artifact. It is not
currently a production dependency and should not be described as live-qualified
decision intelligence.

**Potential value:** lower-latency routing or classification in a bounded
micro-decision loop, provided that deterministic baselines remain authoritative.

**Required evidence before any activation:**

- A held-out fixture set larger than the initial 10/25-case smoke set.
- At least 95% agreement with the existing deterministic label.
- No material increase in false ambiguity or false clarification.
- Provider error rate below 1%.
- Measured p95 latency below the existing route plus the application timeout.
- Independent privacy/data-retention review.
- A documented fallback for every provider, schema, timeout, and quota failure.
- Human review and an explicit owner decision before any routing effect.

Until those gates pass, V1M is retained only as a shadow research spike and
must remain `V1M_PILOT_ENABLED=false` by default.
