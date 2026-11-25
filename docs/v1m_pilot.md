# V1M System One pilot

## Scope

The V1M pilot is an advisory, deterministic-decision shadow evaluator. It is
disabled by default and does not change candidate routing, retrieval, synthesis,
or interview evaluation.

The pilot sends only a bounded, synthetic or caller-supplied state of at most
512 characters. Live use requires `V1M_PILOT_ENABLED=true` and
`V1M_API_KEY`. The credential is treated as a paid/provider secret and is
withheld when `ASK4MO_PROVIDER_MODE=offline`.

Implementation:

- `src/copilot/rag/v1m_pilot.py`
- `scripts/eval_v1m_pilot.py`
- `evaluations/v1m/pilot_cases.json`
- `tests/test_v1m_pilot.py`

## Run

Offline-only fixture evaluation:

```bash
PYTHONPATH=. .venv/bin/python scripts/eval_v1m_pilot.py
```

Opt-in live synthetic evaluation:

```bash
PYTHONPATH=. V1M_PILOT_ENABLED=true .venv/bin/python \
  scripts/eval_v1m_pilot.py --live --threshold 0.85
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
