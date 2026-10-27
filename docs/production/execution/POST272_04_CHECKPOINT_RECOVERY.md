# POST272-04 — PostgreSQL checkpoint connection recovery

## Scope and authoritative baseline — 27 October 2026

Focused branch `fix/postgres-checkpoint-recovery`, based on main
`45f4e0bbf9214b56033be405a332880619dd0273`, the actual merge of
[PR #274](https://github.com/moaltamimi-unbiasedtalent/Intelligent-Interview-Coach/pull/274).
All seven mandatory post-merge workflows succeeded: [CI](https://github.com/moaltamimi-unbiasedtalent/Intelligent-Interview-Coach/actions/runs/40414942358),
[immutable/CSP](https://github.com/moaltamimi-unbiasedtalent/Intelligent-Interview-Coach/actions/runs/40414942316),
[Redis](https://github.com/moaltamimi-unbiasedtalent/Intelligent-Interview-Coach/actions/runs/40414942277),
[admission](https://github.com/moaltamimi-unbiasedtalent/Intelligent-Interview-Coach/actions/runs/40414942366),
[budget](https://github.com/moaltamimi-unbiasedtalent/Intelligent-Interview-Coach/actions/runs/40414942246),
[recovery](https://github.com/moaltamimi-unbiasedtalent/Intelligent-Interview-Coach/actions/runs/40414942442),
[migration image](https://github.com/moaltamimi-unbiasedtalent/Intelligent-Interview-Coach/actions/runs/40414942199).
Browser is PR/on-demand; no main Browser result is inferred.

POST272-03 is closed at merged engineering level. POST272-04 remains OPEN pending
this focused PR's review, green qualification and merge. PR #273 remains unmerged;
its historical 27 passed / 2 failed / 6 blocked campaign evidence is retained.
This repair does not import that campaign or resolve its separate `/history` issue.

## Reproduction and root cause

The baseline factory entered `PostgresSaver.from_conn_string()` once and retained
its single psycopg connection for the entire cached service/compiled graph lifetime.
A terminated PostgreSQL backend made that connection permanently unusable. A healthy
SQLAlchemy readiness probe did not replace the independent checkpoint connection.

A real PostgreSQL 16.15 server, real migrations and original AgentApplicationService
reproduced: owner read HTTP 200, actual idle backend termination, general readiness
HTTP 200, original service checkpoint read HTTP 500, new service read completed.
Exactly one synthetic model invocation occurred; fingerprints of checkpoints,
blobs, writes, run controls, ownership index and canonical usage were unchanged.
The [local evidence](evidence/POST272_04_CHECKPOINT_LOCAL.json) retains this before-fix
observation separately from working-copy qualification.

## Smallest recovery lifecycle

The official synchronous PostgresSaver accepts psycopg `ConnectionPool` objects.
Its existing lock serializes cursor operations. We supply the officially supported
`NullConnectionPool`, a ConnectionPool subclass, bounded to one borrowed connection.
Each cursor borrows a fresh session and closes it on return. The same saver, graph,
service and async bridge remain in place. There is no saver replacement, graph
rebuild, API restart, idle-session cache, or operation replay.

Session options retain autocommit, dict rows and disabled automatic prepared
statements. Connection establishment is bounded to two seconds; each SQL statement
to five seconds, with TCP/keepalive failure detection. These are per-cursor bounds,
not a claim that a queued multi-query request always completes within two seconds.
There is no application retry loop. An operation interrupted after acquiring a
connection fails; the next authorized operation can acquire a new connection.
No model, tool, HITL decision, checkpoint write or transaction is retried.

On every new session, `ask4mo.recovery_pending` is checked before any saver operation.
A physical reconnect never clears or bypasses the database hold, including legacy
threads without a 0048 control row. A rejected new session is closed before it can
be lent. Resource shutdown remains owned by CheckpointerInfo; recovery does not
close a connection used by an active producer.

SQLAlchemy's PostgreSQL engine now checks an idle connection before lending it to
run-control/usage operations (`pool_pre_ping`). This addresses the second stale
session path observed in the real outage tests. It does not replay a transaction
that failed after checkout. SQLite engine behavior is unchanged.

Transport/unavailable failures have a typed safe HTTP 503 projection. The handler
uses a fixed public message even if an internal exception contains unsafe text.
PostgreSQL startup failure remains fail-closed, with no MemorySaver downgrade and
no raw driver cause exposed. SQLite, explicit transient mode and injected savers
retain their existing selection and lifetime behavior.

References: [psycopg pool API](https://www.psycopg.org/psycopg3/docs/api/pool.html),
[null-pool lifecycle](https://www.psycopg.org/psycopg3/docs/advanced/pool.html).
The installed official adapter's constructor and `_internal.get_connection` were
inspected directly. Local tooling used checkpoint-postgres 2.0.25, psycopg-pool
3.3.3, psycopg 3.3.6, checkpoint 2.1.2 and LangGraph 0.3.34. The adapter emits an
existing LangGraph-version deprecation warning; the exercised interfaces are
qualified here, without a broad dependency or graph architecture upgrade. CI
records its actual resolved versions in the redacted artifact.

## Real outage qualification

Run `python -m scripts.checkpoint_recovery.qualify --disposable --output /tmp/NEW_DIR`
after installing the existing dev/db extras. The output directory must be new.
The pinned PostgreSQL image must already exist locally; the runner never pulls it.
CI explicitly pulls that same pinned image before qualification.

The runner creates only its own labelled, random-port, loopback-bound PostgreSQL 16
container with RAM-backed data and synthetic credentials. The container's neutral
PID 1 keeps RAM data mounted while tests stop/start the actual PostgreSQL process.
Every server-control and cleanup action re-verifies its exact container ID, name
and ownership label. No existing container, volume, network or database is pruned.
Each case creates and drops an isolated `p5b_*` database through the existing guard.

Seventeen parameterized cases cover the twenty requested scenarios:

| Evidence | Coverage |
| --- | --- |
| Original retained connection reproduction | 200 → outage → 500, readiness healthy, new service reads preserved records |
| Backend termination and actual PG stop/start | Same service, graph and saver; owner 200, other owner 404, unchanged hashes, one model call |
| Extended and repeated outages | Safe 503 in under five seconds in stopped-server test; two refusals; three restart cycles; recovery without restart |
| Two services / 24 concurrent reads | Both recover, no conflicting replacement, unchanged execution/usage |
| Running synchronous and streaming producers | Graph/saver not closed/replaced; competing continuation refused; original producer completes once |
| Interrupted real checkpoint INSERT | Trigger pauses actual SQL; backend terminated; no write/model replay; run remains unsettled and continuation refused |
| HITL | Pending decision and ownership preserved, explicit owner resume works, foreign/duplicate resume refused |
| Two independent API/worker-shaped processes | After recovery, one eligible continuation wins and one conflicts; cumulative actual usage is two calls/18 tokens/1,800 micro-USD; unsettled run admits neither |
| Persistent recovery quarantine | Physical connectivity returns; both controlled and legacy checkpoint reads remain 503; hold stays on |
| Unknown usage / reserved money / kill switch | Byte-for-byte budget rows, unknown canonical usage, held funds and kill switch unchanged; no takeover |
| SSE read-only reconnection | Stable async graph, repeated result reads, unchanged records, no additional model calls |
| Official privacy deletion | Recovered saver owner check and official thread-delete API work |

Local full outage qualification: **17 passed, 0 failed, 0 skipped**. Existing local
checkpoint/HITL/streaming/admission/budget/recovery/privacy/migration selection:
**191 passed, 74 skipped**. A separate public error-redaction regression passed.
Skips are not PostgreSQL/image success. The original behavior is retained in the
regression fixture using the original official single-connection adapter.

For an ambiguous write, the previous checkpoint rows remain persisted. The existing
canonical aggregate conservatively becomes unknown where full cost cannot be
proven; it is never fabricated as zero. Durable unsettled control prevents reuse.
Ordinary read-only recovery leaves the entire canonical record unchanged.

The extended admission workflow requires the real saver and executes this complete
outage suite in its own disposable server after existing cross-instance tests.
It publishes only test IDs, outcomes, counts, PostgreSQL/dependency versions, source
SHA and dirty-tree flag. Private pytest logs/XML and connection strings are not
uploaded. Ordinary repository pytest explicitly skips the destructive opt-in suite;
its mandatory separate workflow must pass with zero skips.

Final exact-head workflow links and test totals belong in the focused PR's evidence
addendum. Local evidence above is explicitly an uncommitted working-copy observation,
not exact-commit CI. Full encrypted recovery, image startup/migration, durable
admission, budget, frontend and Browser checks remain mandatory CI qualifications.
The full PR #273 campaign is NOT RUN; no explicit API-restart workaround is used by
this extracted independent checkpoint regression. HTTP tests use a controlled
identity dependency seam, not a hosted identity/cookie or proxy qualification.
The process test qualifies shared admission behavior, not a deployed worker fleet.

## Preservation and release position

The baseline inventory contains 46 existing worktrees, 314 branch tips and 49
protected-file hashes, including original environment/database/assets. The new
feature checkout is additional; no original worktree is removed or repurposed.
The original development SQLite database was not opened or migrated (last observed
0027). Existing local Python dependencies were not changed; optional PG tooling
was installed only under a temporary target directory. No owner decisions or
approval markers, secrets, provider settings or language records were changed.
Preservation audit after implementation: all 46 original worktree statuses, all 314 original branch tips and all 49 protected-file hashes match the pre-task inventory.

**R1.0 remains 40/45 integrated.** 00A/00B/07B/07C/08A remain open/incomplete.
Hosted staging NOT RUN; human/legal/custody qualification OPEN. PG-01–PG-15 retain
all existing states (only historical PG-11 PASS); LG-01–LG-14 gain no approval and
zero languages are hosted-qualified. OD-HOSTED, H-REDIS-POLICY, OD-BUDGET and
custody/retention/RTO/RPO decisions remain open as recorded in the existing tracker.
No production-readiness or release-go decision follows from this repair.

Remaining sequence, only after this PR is reviewed, merged and main is green:
separate `/history` diagnosis; safe PR #273 reconciliation; exact-source image and
manifest rebuild; complete disposable campaign with fresh evidence; then consider
Task 08 only with required owner authorizations. None begins in this PR. No cloud,
staging/production deployment, live paid model/embedding call, live email, external
activation, real database migration or automatic merge is authorized or performed.
