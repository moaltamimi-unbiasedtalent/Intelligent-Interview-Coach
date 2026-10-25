# Wave 4 Task 06 — encrypted recovery engineering

Baseline: PR #271 merged at `88a5ce4e4d5e92bee75fbec2721ce28e73d9ac6d`.
[Pre-change gap matrix](WAVE4_TASK06_RECOVERY_AUDIT.md). This is disposable
qualification, not deployment, operational approval or a production RTO/RPO.

## Recovery boundary

The existing 05B engine remains the backup format, AES-256-GCM implementation,
checksum/signature authority and PostgreSQL dump/restore path. The additive
`backup_set.py qualified` commands require sealed complete sets, a reviewed
release binding, fresh producer-drain attestation and independent trusted ledger
head. Dry-run is the default; all target writes need `--execute`.

A qualified source must use PostgreSQL 16, public schema, one Alembic revision,
all candidate/knowledge roots and matching persisted embedding identity. All
application and official checkpoint tables must share that database. Separate
checkpoint URLs, additional schemas and checkpoint threads without durable
owner/run mappings are refused. They are not silently skipped. All database
rows, including managed credential ciphertext, unknown charges, reservations,
usage, controls, constraints, triggers and sequence state are verified after
restore. Every table count and a digest of every row are compared before any
intentional erasure. The dump uses an exported PostgreSQL snapshot and table
write locks. Source files are hashed before/after; Chroma is opened on a scratch
copy. Schema changes and active jobs prevent publication. Drain evidence is an
operator attestation, not proof that every external writer has been fenced.

Private document and governed-source checksums, collection/chunk evidence and
index identities travel in the sealed set. Retrieval query text is itself sealed;
only local-hash fixture probes execute during qualification. No semantic model
or paid embedding is invoked. Release metadata carries application SHA, anchored
release manifest, migration head, prompt/activation hashes and budget capability
2 plus recovery capability 1. Runtime keys are never image inputs or manifest
fields.

## Restore quarantine and reconciliation

Restore accepts only a NEW root and empty, unused PostgreSQL target with an
explicit restore/staging/drill name. Before SQL restore it sets the persistent
`ask4mo.recovery_pending=on` database setting. This lives outside restored table
history. `pg_restore --single-transaction --exit-on-error` never uses `--clean`.
The root receives `RECOVERY_PENDING.json`; `RECOVERY_VERIFIED.json` is written
only after row/schema/file/index checks and independent erasure reapplication.
A failure retains the hold and PENDING evidence; no failed target is promoted.

Even a verified target remains held. API repository access/readiness, agent
creation/claim, worker job claim, budget reservation/resume and immutable
promotion/rollback refuse it. Unknown cost remains unknown; reservations and
spending counters are never released/reset. Global AI kill is additionally
latched. Cancelled/unsettled runs and official checkpoints are preserved.
An explicit 0047-to-0048 upgrade is allowed only on the new target with
`--upgrade-to-head`; no downgrade or source migration is performed.

There is deliberately no automatic reconciliation or release-hold command.
Before authorizing access an operations owner must fence old/new producers,
compare the snapshot with independent current provider receipts and all external
charge/erasure activity, reconcile durable reservations without inventing costs,
and approve the intended release/configuration. Record the approver, UTC time,
source/target identities, current ledger anchor and evidence in protected storage.
Only then may an authorized database operator reset the database setting on the
isolated target and recycle every connection. The AI kill remains latched until
separate approved budget/resume controls permit it. Existing connections do not
inherit changed database defaults; connection recycling is mandatory. None of
these approvals or operations occurred in Task 06.

Application rollback is image-only and still rejects incompatible schema,
active/unsettled work, missing budget capability 2 or recovery capability 1, and
recovery-held state. 0048 rehearsal seeds real protected controls, partial usage
and unknown monetary reservations, confirms downgrade refusal without changing
any of them, then restores to a new target. It never deletes protected rows to
force a downgrade. Legacy reversible-head fixtures retain their existing path.

## Erasure and independent evidence

The existing append-only erasure ledger format is retained. Appends use a process
lock and idempotency recheck. Qualified operations require an independently held
HMAC-signed current sequence/head, authenticated with a separate 32-byte ledger
key. Missing, truncated, tampered or rehashed history is refused. The trusted
current head must be retained outside backup/restore roots in separately
controlled storage. Restoring both a stale ledger AND a stale trusted head is a
custody failure this local tool cannot discover; use an independently retained
latest anchor, not the historical anchor embedded in the backup.

Reapplication uses AccountDeletionService and official PostgresSaver.delete_thread.
Personal per-user usage facts follow the existing erasure policy; this intentional
privacy deletion is separately counted. The non-identifying monetary ledger,
unknown charges and counters are retained and fingerprinted. Subscription-bound
identity retention follows existing restricted deletion-requested behavior;
account access remains held. A PostgreSQL rewrite restores to a new quarantined
scratch target, reapplies deletion and seals a NEW set. The original is preserved,
and no complete erasure/physical media destruction is claimed. Copies, replicas,
provider retention and key copies require independently attested disposition.
The existing 35-day values remain engineering defaults pending owner/legal approval.

## Operator procedure (plan only)

1. Review the exact release manifest/anchor and application SHA with the existing
   `release_images.py verify`. Build `build-recovery` from that exact local API
   image ID. API, worker and migrate still use the one original application image;
   web still uses the matching frontend image. No registry is assumed.
2. Review `recovery.json`, its independent SHA-256 anchor and
   `recovery-release.json`. `verify-recovery` checks actual API parent layers,
   application files/dependencies, non-root UID, immutable metadata and bundled
   PostgreSQL 16 clients. The client loader/libraries are isolated from Python.
3. Supply private runtime configuration and existing custody-managed keys via
   read-only mounted files, mode 0600 or stricter, readable only by the operator service UID 10001. Prepare protected operator copies with the correct ownership; never loosen permissions on original private files. `SECRET_STORE_MASTER_KEY` is
   separate from backup/ledger keys and is needed for future credential use, not
   dumped into the backup. Do not place keys on the command line. No operator keys
   were generated during this work.
4. Prepare a reviewed JSON array of bind mounts with `type`, absolute `source`,
   approved `target`, boolean `read_only`, and `bind: {create_host_path: false}`.
   Source documents/knowledge/index, keys, release facts and trusted anchors must
   be read-only. Ledger storage is independent; backup/new-target/destination
   roots cannot overlap. The profile refuses socket mounts and auto-created paths.
   The operator must authorize database networking and source read/target write
   credentials separately; backup capture needs table-lock privileges. Do not
   reuse a production write role unnecessarily.
5. `release_images.py recovery-profile` generates one opt-in `recovery` service,
   non-root/read-only rootfs, dropped capabilities and bounded temporary storage.
   Backup/restore/rewrite require an explicit reviewed existing database
   `--network`; it is declared external so this profile never provisions one.
   Verify/transfer run with networking disabled. Normal startup does nothing. Its default command is help. Review resolved
   Compose configuration, all target identities and protected mount permissions.
   Set `BACKUP_MANIFEST_SHA256` nowhere implicitly: provide the independently
   reviewed `--manifest-sha256` argument explicitly for verify/restore/transfer.
6. For backup, stop/fence producers and record a fresh UTC drain observation.
   Run `backup_set.py qualified backup --out /backup/NEW
   --attest-drained-at UTC [--execute]`. Preserve the returned new signed ledger
   head in independent custody; do not overwrite the previous evidence.
7. For restore use `qualified restore --set /backup/SET --manifest-sha256 HASH
   --target-root /target/NEW [--execute]` with explicit private
   `TARGET_DATABASE_URL`. Review receipts, checkpoint/accounting integrity and
   erasure evidence; retain quarantine until separately authorized reconciliation.
8. For independent encrypted transfer use `qualified transfer --set /backup/SET
   --manifest-sha256 HASH --destination /destination/NEW [--execute]`.
   Verification runs before and after copying. Restore from the verified copy.
   This is a local destination simulator, not a cloud upload adapter or provider
   residency/security claim. For erasure use `qualified rewrite` with a new
   scratch database/root and `--out /destination/NEW`; retain the old set pending
   separate authorized destruction/attestation.

Hosted shell `restore.sh` refuses even with FORCE. The historical local helper
requires a separately named unsafe acknowledgement; the qualified profile never
invokes it. Normal API/worker startup never backs up, restores, upgrades or
silently downgrades data.

## Exclusions and owner decisions

Not recovered automatically: independent erasure ledger/latest trusted anchor,
backup/signing/ledger/master keys, external provider receipts, deployment images,
TLS/certificate stores, external logs/object snapshots/replicas, live scanner
signatures and untracked curated corpora. Release hashes identify dependencies;
they do not recreate missing external artifacts. Hosted semantic retrieval and
managed-key rotation require separately authorized qualification.

OPEN: provider, region/residency, encryption-at-rest/transport/access controls,
source/destination/ledger separation, retention/legal erasure periods, immutable
storage/lifecycle policy, key owners/escrow/dual control/rotation, recovery operator,
monitoring/alert ownership, approved RTO/RPO and restoration/reconciliation authority.
If all required decryption/escrow keys are lost, sealed data is unrecoverable.
Rotation must verify a newly sealed copy under a new custody key and independently
attest disposition of all old copies/keys; no automated deletion is introduced.

No hosted deployment, paid request, live email, real database migration, legal or
language approval occurred. PG-09 stays unapproved. R1.0 remains 40/45 integrated;
00A, 00B, 07B, 07C and 08A stay open. Next is separately scoped Task 07 full-stack
integration only after Task 06 review, merge and green main; hosted/paid work still
requires separate authorization.
