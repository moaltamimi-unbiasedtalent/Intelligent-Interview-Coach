# Observability (Phase 7D — privacy-safe Langfuse)

Optional, operational telemetry for Ask4Mo's Agent, Career Intelligence retrieval, Interview
Practice and feedback. It is **off by default**, **metadata-only**, and can **never** become a
runtime dependency or break a candidate request. It complements — never replaces — the
first-party **Agent Inspector**.

## Why Langfuse

Operability: end-to-end traces that correlate a run's model/tool/retrieval/HITL operations and
carry latency / token / cost / error signals across versions and environments. Langfuse is one
*adapter* behind an internal interface — the application never imports the vendor SDK directly.

## Architecture

```
business code ── ObservabilitySink (Protocol, src/observability/base.py)
                      │
        ┌─────────────┴─────────────┐
   NoOpObservabilitySink        LangfuseObservabilitySink
   (default; no network)        (sanitised events only)
                                     │
                             safe_metadata()  ← src/observability/sanitizer.py
```

- `base.py` — the `ObservabilitySink` Protocol + **safe projections** (`safe_trace_projection`,
  `safe_tool_events`, `safe_hitl_event`, `safe_retrieval_metadata`): the only dicts allowed to
  leave the process, each an explicit allow-list of safe scalars/labels.
- `noop.py` — the default: every method a no-op, zero network, zero latency.
- `langfuse.py` — the adapter: emits **manual** events only (it never attaches the LangChain
  auto-trace callback, which would capture prompts/inputs/outputs), tags each with
  environment/release, and passes **all** metadata through the central sanitizer.
- `sanitizer.py` — the privacy backstop (§11–14): redacts secret-keyed values, scrubs
  emails/phones/bearer tokens/credential blobs, strips URL query strings, and maps exceptions to
  a small set of category codes (never `str(exc)`).
- `config.py` — resolves all knobs **once** (enabled, credentials-present, host, environment,
  release, sample rate, content-capture); never raises.
- `context.py` — a non-reversible HMAC pseudonym for user correlation (only when a salt is set).

## How to enable

Set all three (default is disabled):

```
AGENT_EXTERNAL_OBSERVABILITY_ENABLED=true
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_HOST=https://cloud.langfuse.com     # or your self-hosted host
```

Check status without sending data: `python scripts/check_langfuse.py`
→ `DISABLED` / `NOT CONFIGURED` / `READY` / `PARTIAL`. Add `--send-test-trace` (only when
READY) to emit ONE metadata-only connectivity trace.

## Environment variables

| Variable | Default | Meaning |
|---|---|---|
| `AGENT_EXTERNAL_OBSERVABILITY_ENABLED` | `false` | Master switch |
| `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` | — | Credentials (env only; never committed/logged) |
| `LANGFUSE_HOST` | Langfuse cloud | Self-host URL |
| `LANGFUSE_SAMPLE_RATE` | `1.0` | Trace sampling, clamped to [0,1] |
| `LANGFUSE_CAPTURE_CONTENT` | `false` | Stays off in 7D; sanitizer still applies if ever set |
| `OBSERVABILITY_ID_SALT` | — | Salt for a non-reversible pseudonymous user id |
| `ASK4MO_RELEASE` | package/git | Explicit release tag for traces |

Install the optional SDK with `pip install -e ".[observability]"` (pinned `langfuse>=2.0,<3.0`).

## What IS sent (safe metadata)

Run id / session id (opaque), operation type, model profile & identifier, latency, token counts,
cost (only if the provider supplies it), tool names & counts, retrieval-used / domain / lane /
source count / citation count / occupation-resolved (bool) / geography-requested / grounded
(bool), HITL type & status, completion status, error **category**, environment, release, and safe
durability signals (idempotency hit, lease/OCC conflict).

## What is NEVER sent (hard privacy boundary, §9)

Raw CV, candidate name/email/phone/address, candidate background, raw JD, uploaded document
contents, preparation-memory content, system/developer prompts, hidden tool instructions,
**chain-of-thought / reasoning**, raw LangGraph checkpoints, API keys / authorization headers /
cookies, Adzuna / Destatis / Langfuse credentials, raw provider payloads or full model responses,
and **interview answer text**. Content capture is disabled; no debug mode can re-enable CoT (§39).

## Failure behaviour (§5)

Telemetry is best-effort. A Langfuse outage, timeout, 401/403, 429, DNS failure, SDK exception or
serialization error is swallowed with a single sanitized local warning — the Agent run,
interview and feedback submission always continue. Missing credentials degrade to the no-op sink;
they never fail startup (§36).

## Relationship to the Agent Inspector (§25)

The **Agent Inspector** is the first-party, reviewer-facing view of a run (observable execution,
never CoT/prompts/raw checkpoint). Langfuse is external operational telemetry. The Inspector does
not depend on Langfuse and is unchanged by Phase 7D.

## Feedback correlation (§26/§27)

Explicit candidate feedback emits `{surface, rating, category}` and, for an agent answer, a
Langfuse **score** correlated by the opaque `run_id` (parsed from the response id). The free-text
comment is **never** transmitted — it stays in the application database.

## Testing

`tests/test_observability_p7d.py` (+ the P5 suite) run fully offline with a fake client and a
recording sink — real Langfuse is never called. They assert secrets/PII/URLs/CoT/checkpoint
content cannot enter telemetry, the trace structure and tags, feedback score correlation, and
that a failing sink never breaks an interview. Audit: `python scripts/audit_observability.py`.

## Production considerations

Prefer the SDK's background transport (non-blocking); a bounded flush runs at shutdown. Set a
real `LANGFUSE_HOST`, an explicit `ASK4MO_RELEASE`, and (if user correlation is needed) an
`OBSERVABILITY_ID_SALT`. Keep `LANGFUSE_CAPTURE_CONTENT=false`. Rotate credentials outside git.
