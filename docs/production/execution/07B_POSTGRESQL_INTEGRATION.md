# 07B PostgreSQL application integration

This increment keeps the governed 07B HTTPX receiver synthetic-only. The existing
07B approval and dedicated `AI_BUDGET_07B_DATABASE_URL` select the PostgreSQL path
when the URL explicitly names the restricted runtime role using
`postgresql+psycopg`, a literal loopback IP, an explicit port and the dedicated
database. The URL and database-generated ledger identity are bound to the
approved policy. Keep connection credentials in authorized
secret storage. Existing SQLite 07B, 05C and Q01 entry points retain their own
behavior.

## Dedicated database and privileges

The versioned SQL provisioner is [07b_postgresql_v1.sql](../../../migrations/07b_postgresql_v1.sql).
The ordinary application Alembic head and tables are independent of this schema.
Apply the SQL in one transaction to a new, dedicated PostgreSQL 16 database.
Use a separate superuser provisioner to install the database-local event trigger.
The runtime never receives that credential. Precreate the following roles
without role memberships, with NOINHERIT and without administrative role attributes.
The owner has NOLOGIN. Use distinct credentials stored outside source control.
Revoke database CREATE and TEMPORARY from PUBLIC, restrict CONNECT to the
intended principals, and grant no writable schemas to the runtime. The runtime
adapter verifies the actual role, effective privileges, connected address, port,
database and PostgreSQL 16 version before every operation, including handoff.
It refuses autocommit and rejects ambient libpq connection and security
overrides. The CLI supplies the approved address explicitly. The client must
expose the actual connected address through psycopg.

| Role | Granted operation |
| --- | --- |
| `ask4mo_07b_owner` | Own schema, routines, tables and policy. Used only by the independent provisioner. |
| `ask4mo_07b_runtime` | Verify ledger binding, reserve, accept handoff, settle with the reservation capability, and read aggregate status. An overrun or ambiguous outcome can only latch the stop. |
| `ask4mo_07b_stop` | Latch an emergency stop and advance its generation. |
| `ask4mo_07b_reconcile` | Mark a verified abandoned reservation unknown, reconcile an eligible hold, and resume, each with a separate valid authorization. |
| `ask4mo_07b_issuer` | Insert a generation-bound, expiring authorization for the intended reconciler. Cannot consume approvals, change holds or resume. |

The provisioner creates the singleton with a fresh `ledger_id` and a pending
policy. Read that identifier with the provisioning credential. The PostgreSQL
07B approval includes that exact UUID as `postgres_ledger_id`. Bind the singleton's
policy to the reviewed result of `database_policy(config)` as JSONB before
handing the runtime credential to the application. The database rejects a policy
for a different identity, and the runtime checks the actual identity on every
transaction. A fresh ledger at the same endpoint requires its own approval.
Routines run under the non-login owner with fixed search paths and
schema-qualified objects. The public role has no privileges in this schema.
Runtime role credentials do not provide the proof needed to settle an unknown
outcome or authorize a resume.

Local-object `GRANT` and `REVOKE` commands in the dedicated database take the
control-row lock before changing privileges. Handoff revalidates the runtime
privileges under that lock. If acceptance wins the lock, a conflicting ACL
change is refused while accepted work remains unsettled. The runtime checks
that the ordering trigger is enabled. PostgreSQL event triggers exclude shared
objects such as roles and databases. Perform cluster-wide role, membership and
database ACL maintenance with the service stopped and drained, using the
separate provisioner. Revalidate the existing ledger and effective privileges
before resuming.

## Dispatch and recovery

1. The receiver checks the existing approved model, endpoint, request shape,
   marker and budget policy. The adapter explicitly uses `READ COMMITTED` and
   the database refuses accounting mutations under unsupported isolation.
   The database locks the singleton, checks its bound policy and clock, verifies
   the total/class/category limits, and commits a reservation. The policy sets a
   floor per operation using the approved token ceilings and prices. A short
   request therefore still needs headroom for one full approved operation. A
   unique fingerprint refuses durable replay. Any existing RESERVED or UNKNOWN
   exposure blocks further admission.
2. The actual HTTPX receiver acquires the same database lock, verifies the
   reservation capability, checks the stop and database deadline, and records
   acceptance. The existing receiver callback also checks local cancellation,
   the environment stop and the local deadline. Commit before invoking the
   synthetic handler. An emergency stop committed before acceptance prevents
   dispatch. A stop after committed acceptance cannot revoke work the receiver
   already owns.
3. The handler runs with no open accounting transaction. Settlement uses a
   fresh transaction and the capability. The database computes a usage estimate
   from the bound token prices and checks it against claimed and reported cost.
   Ambiguous or contradictory evidence retains the larger exposure and latches
   the stop. A settlement carrying an error classification follows this rule
   even with HTTP 200 and matching amounts. An HTTP rejection after acceptance
   also retains exposure until reconciliation. A confirmed pre-handoff refusal
   can release its reservation.
   Duplicate settlement is refused. Connection failures cannot release exposure.
   A crash can leave a durable RESERVED entry even if the handler never ran.
4. Establish quiescence before issuing an abandoned-reservation authorization.
   It changes RESERVED to UNKNOWN while retaining the hold. An independent
   receipt authorizes settlement of UNKNOWN. Resume requires its own
   unconsumed approval for the current stop generation and no remaining
   RESERVED or UNKNOWN exposure. All approvals require finite expiration. The
   governing policy has yet to establish a maximum authorization lifetime.
   Stop, overrun, abandonment, reconciliation and resume write attributable
   audit records.

If the application change must be rolled back, stop and drain this integration
and preserve the database identity, audit and unresolved holds. Keep its 07B entry
disabled until a reviewed version can read the same ledger. No downgrade or
automatic SQLite fallback removes or clears accounting state.

This design trusts the receiver to report usage for its own reservation and
validates those claims against the bound price table. The synthetic loopback
scope relies on an operation-owned database endpoint. Real SDK transport,
independent provider charge evidence, production endpoint authentication and
credential provisioning, and operational backup/restore require separate
qualification. Restoring an older copy or running two copies of a ledger can
reuse the same identity and requires independent continuity and single-writer
verification.
