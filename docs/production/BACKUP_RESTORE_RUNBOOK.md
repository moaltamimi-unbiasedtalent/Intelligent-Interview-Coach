# Backup, restore, rollback and backup-erasure runbook (package 05B, PG-09)

Status: **tooling and procedure delivered and drilled OFFLINE on a synthetic SQLite environment. Nothing here has been run on the hosted staging environment**
(DEPLOYMENT FREEZE, owner decision OD-HOSTED). Every drill record says `hosted_verification: NOT RUN (OD-HOSTED)`. The PostgreSQL-specific paths are written and tested
only against a disposable PostgreSQL when `TEST_DATABASE_URL` is set; they were NOT executed in the delivering run (see section 10).

## 1. What a backup set is

One directory created in one run, described by one `manifest.json` written last (a directory without a manifest is not a set and is refused).

| Part | Content | How it is taken |
|---|---|---|
| `database/` | the application database, consistent snapshot | SQLite: online backup API. PostgreSQL: `pg_dump --format=custom` (credentials through the child process environment, never the command line) |
| `documents/` | every private candidate document file (opaque keys) | file copy, checksummed |
| `knowledge/` | the 02A governed-knowledge backup: registry rows, private source files, `chunks.jsonl`, a file-level copy of the persistent index, its own manifest | `src/knowledge_admin/recovery.py`, staged then written like every other part |

The manifest records: a SHA-256 for every file (as stored and as plaintext), the row count of EVERY table, the Alembic revision, the index collection checksum and embedder
identity, a deterministic retrieval probe (queries and the ordered chunk ids and scores they returned), the consistency evidence (queued or running jobs at the start and the
end, source files unchanged during the copy), the encryption mode and, when signed, an HMAC signature.

Not in a set (by design, each stated so nobody assumes otherwise): the legacy curated structured stores and corpora under the data root (rebuildable from the repository's
committed data by the build scripts); ClamAV signatures and Caddy certificates (re-created); agent checkpoint threads when the checkpoint store is a separate SQLite file
(PostgreSQL keeps them in the application database, so the dump holds them); **the `SECRET_STORE_MASTER_KEY`** (see section 4: the dump holds only ciphertext of managed
provider credentials, and a restore needs the same master key from your secret manager).

## 2. Taking a backup

```
python scripts/backup_set.py backup --out <NEW or empty dir>                    # dry run: counts only, writes nothing
python scripts/backup_set.py backup --out <dir> --execute --encrypt --ledger <erasure ledger>
```

Source configuration is the API's own: `DATABASE_URL`, `DOCUMENT_STORAGE_DIR` (required), `COPILOT_DATA_DIR`, `KNOWLEDGE_STORAGE_DIR`. Rules the tool enforces:

* **Dry-run is the default.** Never overwrites or deletes: the target must be new or empty and must not sit inside a source directory.
* **Active jobs are refused** (a queued or running job means the snapshot could be taken mid-write). Drain the queue or stop the worker first; `--allow-active-jobs` exists
  but marks the set `consistent: false` and a drill must not be based on such a set. The check is repeated after the copy.
* **A source that changes during the copy discards the set** (no manifest is written, so it can never be restored). The index directory is compared by file names and sizes
  only, because merely opening a Chroma collection rewrites its segment files with identical content.
* Output is JSON of codes, counts and short hashes. It never contains a path, URL, credential or key. Record the printed `manifest_sha256` somewhere other than the set (a ticket,
  the drill record): it is the anchor that protects an unsigned manifest.

## 3. Verifying and restoring

```
python scripts/backup_set.py verify  --set <dir> [--require-signature] [--require-encryption]
python scripts/backup_set.py restore --set <dir> --target-root <NEW dir>                  # plan only
python scripts/backup_set.py restore --set <dir> --target-root <NEW dir> --execute
python scripts/backup_set.py restore --set <dir> --target-root <NEW dir> --target-database-url <empty PostgreSQL named *restore*|*staging*|*drill*> --execute
```

A restore always goes into a SEPARATE environment: `database/restored.db` (or the named empty PostgreSQL database), `documents/`, `knowledge/private`, `knowledge/chroma`
under the new root. It refuses a root that exists and is not empty (so it can never overwrite a file), refuses a PostgreSQL target that is not empty or whose name does not
contain `restore`, `staging` or `drill`, verifies the whole set before writing anything, and afterwards compares the schema revision, every table's row count, every document
checksum, the knowledge files and the index checksum with the manifest. A mismatch is a failed result. Nothing is ever restored "in place": to promote a restored environment the
operator points the deployment at it (a deliberate, separate step).

After ANY restore of a set older than an account deletion, re-apply the erasure ledger (section 8): `python scripts/backup_set.py erase reapply --ledger <ledger> --target-root <root> --execute`.
Then run the migrations (`deploy/scripts/migrate.sh`) if the set's revision is older than the deployed head, and let the knowledge serving guard and `/api/v1/ready` confirm the
environment before traffic.

## 4. Encryption at rest: requirement and key handling

**Requirement (stated):** a backup set contains candidate personal data and managed-credential ciphertext. In every hosted environment (`API_ENV` staging, production or any
unknown value) a set MUST be encrypted at rest. The tool enforces it: without `--encrypt` it refuses to write a set unless the operator passes `--attest-encrypted-storage`
(recorded as `storage_attested`, **an attestation the tool cannot verify**, for example a destination on an encrypted volume or bucket with provider-managed keys). Development
and test may write an unencrypted set and say so in the manifest (`unencrypted_set`).

**Sealing option:** `--encrypt` seals every file with AES-256-GCM (chunked, per-file random prefix, associated data binds the set id and the file name, a final-chunk marker detects
truncation) and signs the manifest with a key derived from the sealing key, so a sealed set is also manifest-authenticated.

**Key handling:**
* Generate: `python scripts/backup_set.py keygen` prints a fresh 32-byte base64 key once. It is not saved anywhere. Put it into the secret manager.
* Supply: only through the environment (`BACKUP_ENCRYPTION_KEY`; optional `BACKUP_SIGNING_KEY` for signing an unsealed set). There is no command-line flag for a key (a process list
  shows arguments). The key is never written to the repository, a manifest, a report, a log, a drill record or a `.env` file this tool reads.
* Separate: the key must live somewhere other than the backups (different account and access policy). A manifest holds only an 8-character fingerprint so a wrong key is reported
  as `encryption_key_mismatch` rather than a generic failure.
* Rotation: new sets use the new key; old sets stay readable with the old key until they are destroyed at retention age. Keep an old key only while a set sealed with it exists.
* Loss: a lost key means the sealed sets are unrecoverable. Escrow the key under the owner's key-custody rules.
* Managed provider credentials: the database holds them only as AES-256-GCM ciphertext under `SECRET_STORE_MASTER_KEY`. That key is deployment configuration and is NOT in the set;
  restoring a dump without the same master key leaves managed credentials unreadable (the environment fallback still works).

## 5. Tamper detection

`verify` reports every deviation with a fixed code: `file_checksum_mismatch`, `file_missing`, `unlisted_file`, `unsafe_path_in_manifest`, `symlink_in_set`,
`manifest_tampered` / `manifest_signature_key_mismatch` / `manifest_unsigned` (when a signature exists or is required), `sealed_file_invalid`, `encryption_key_mismatch`,
`set_not_encrypted`. Honest limits: an UNSIGNED, UNSEALED manifest can be edited together with the files it lists and still verify, so record `manifest_sha256` out of band or
sign. Checksums prove integrity against corruption and casual change, not against an attacker who can write both the files and the manifest and who holds no key.

## 6. Rollback

**Database (migrations).** Forward-fix first. Take a verified set before every migration (`deploy/scripts/migrate.sh` reminds you). A downgrade is a rehearsed escape hatch only for a
reversible head: the head migration's downgrade is FAIL-CLOSED (it refuses, deleting nothing, while candidate-authored state exists). The rehearsal
(`python scripts/rollback_rehearsal.py`) proves, on SQLite: upgrade to head, refused downgrade with an unchanged revision and unchanged row counts, clean downgrade of one revision
preserving the other tables, re-upgrade, and a restore of the pre-migration set into a separate environment (the fallback when a downgrade is refused or unsafe).
If a migration cannot be reversed, restore the pre-migration set into a new database and repoint the deployment.

**Application images (Wave 4 Task 03, no deployment).** The local immutable release controls and their evidence are in
[`execution/WAVE4_TASK03_IMMUTABLE_RELEASE.md`](execution/WAVE4_TASK03_IMMUTABLE_RELEASE.md). They replace the earlier tag-pointer proposal with
verified content-addressed application images and a plan-only rollback profile. API and worker use the same verified backend image; web is tied to the
same source release. Rollback requires a fresh, drained target observation, zero unsettled agent runs/active jobs, and an explicitly compatible schema.
The rollback profile has NO migrate service and performs no database downgrade, restore, usage settlement or deletion. Never combine it with the build template.

A schema mismatch is a refusal, not an instruction to downgrade automatically. Prefer a forward fix. Any database recovery follows the separately authorized
backup/restore procedure, preserving the original environment and erasure ledger. Local image export/load verification is not a database restore or a hosted
rollback drill. The full hosted operation remains NOT RUN (OD-HOSTED).

## 7. Restore drills and records

`python scripts/restore_drill.py --synthetic --record-dir docs/production/execution/evidence/drills --label <name> --commit-sha <sha>` backs up a synthetic environment, restores it into a
separate one and verifies: schema revision, every table's row count, every document checksum, the governed knowledge files, the index collection checksum (against the manifest and
the live source), retrieval evidence parity (the recorded probe queries return the same chunk ids and scores), that a second restore into the non-empty target is refused, that a
tampered file, an unlisted file and an edited signed manifest are detected, and that the source was not changed. It writes `drill-<UTC>-<label>.json` and `.md` (never overwriting).
`--from-environment` runs the same drill against the operator's configured source (`kind: operator_supplied`). Result values: PASS, FAIL, PARTIAL (a check was NOT RUN, for example
manifest-edit detection on an unsigned set). **A synthetic offline PASS is not hosted evidence.** The hosted drill (OD-HOSTED) is open: run it on staging with a sealed set and keep
the record.

## 8. Backup erasure after account deletion (PRIV-BACKUP)

**The facts.** `AccountDeletionService` removes the account's data from the LIVE application. Every set taken before the deletion still holds it. A set is a point-in-time copy and
is never edited in place, so the data leaves backups in exactly two ways: the set is destroyed at its maximum age, or it is rewritten (restored into a scratch copy, the deletion
re-applied, a NEW set taken) and the original destroyed.

**The window (an engineering default, to be confirmed by the owner and legal counsel; not a legal statement).** `BACKUP_RETENTION_DAYS = 35`: no set is kept longer. `ERASURE_WINDOW_DAYS = 35`:
the data of an account whose live deletion has completed is removed from every older set no later than 35 days after that completion, PROVIDED the operator destroys sets at retention
age and records it. Every set that can hold the data is at most 35 days old when the account is deleted, so expiry alone reaches the end of the window; a rewrite can finish earlier.
**Until then the data IS still in those backups**; the product must not say otherwise.

**Procedure.**
1. Register every set when it is made (`backup --ledger`, or `erase register`) so the inventory is complete. Keep the ledger OUTSIDE the database and the sets (a restore of an older database must not forget a deletion). It is append-only and hash-chained; edits, deletions and reordering are detected.
2. When a live deletion completes (the privacy deletion job finished), record it: `erase record-deletion --ledger L --user-id N --deleted-at <ISO>`. Only the numeric id is stored.
3. `erase plan --ledger L --sets-dir D` lists each set against each deletion: `contains_account`, `may_contain_account` (sealed or PostgreSQL set, not inspectable), `rewritten_without_account`,
   `account_not_in_set`, `absent_without_attestation`, `attested_destroyed_but_still_present`, and which are overdue.
4. Either wait for retention age and destroy the set, or rewrite it: `erase rewrite --ledger L --set S --out NEW --execute`. The rewrite restores a scratch copy, runs the SAME
   `AccountDeletionService` for every ledger account (documents, rows, checkpoint threads in the snapshot), verifies, and writes a new set. It never edits or deletes the original.
5. The OPERATOR destroys the original set (this tool never deletes) and records it: `erase attest-destroyed --ledger L --set-id ID --by <label> --reason rewritten|expired`. The tool refuses while a set with that id is still present, refuses `expired` before retention age and `rewritten` for a set that was not rewritten.
6. After ANY restore, run `erase reapply` so a restored old backup does not resurrect deleted accounts.

**What the tool will and will not claim.** `erasure_claim` is `complete_per_operator_attestation` only when every set older than a deletion is either provably free of the account
(rewritten, or not in the snapshot) or absent with an operator attestation, and no unregistered set exists. A rewritten set whose original still exists is `incomplete`. The
tool cannot verify that storage media were wiped. It never reports "erased from backups" for a set that was not rewritten or destroyed.

**Not covered:** backups outside this tool (a managed database provider's snapshots, object-storage versions, replicas, laptop copies); PostgreSQL sets are rewritten by the manual
procedure (restore into a disposable PostgreSQL, run `AccountDeletionService`, take a new set), which is NOT exercised by this package; agent checkpoints held in a separate store are
not in the set at all.

## 9. Remaining staging changes (application image profiles supplied separately)

1. **Backup runner.** A one-shot `backup` service (profile `ops`, not started by default) built from the api image, mounting `documents` and `knowledge-data` read-only and a `backups`
   volume (or an object-storage client) read-write, with `DATABASE_URL`, `DOCUMENT_STORAGE_DIR`, `COPILOT_DATA_DIR`, and `BACKUP_ENCRYPTION_KEY` from the secret manager (not `.env.staging`
   in the repository). The worker must be stopped or drained during a backup.
2. **PostgreSQL client tools.** `deploy/Dockerfile.api` installs `libpq5` but not `pg_dump` / `pg_restore`: add `postgresql-client-16`, or run the backup from the `postgres:16` image.
3. **Application image pointer.** Wave 4 Task 03 supplies image-only local release/rollback profiles using verified Docker image IDs, replacing the earlier mutable image tag proposal.
   Registry publication/signing is not implemented or authorized; do not substitute an unverified remote reference. The base Compose file remains a build template, not the release profile.
4. **Restore target.** A `restore` profile with an empty PostgreSQL service named `*restore*` and empty volumes, so drills never touch live volumes.
5. **Ledger and sets off the host.** The erasure ledger and the sets belong on storage with a different access policy from the application host; the ledger must be backed up independently.
6. **Retention.** A scheduled destruction of sets older than 35 days, recorded with `erase attest-destroyed`.

## 10. Verification status

| Item | Status |
|---|---|
| Backup set, verify, restore, tamper and refusal cases, sealing, signing, erasure procedure, restore drill harness and record, rollback rehearsal | Tested offline (SQLite, local embedder). Records under `docs/production/execution/evidence/drills/` |
| PostgreSQL `FOR UPDATE SKIP LOCKED` claim, audit-trigger DDL, managed secrets table, `pg_dump`/`pg_restore` through the set, PostgreSQL migration rollback | Tests written (`tests/test_pg_05b.py`), run only when `TEST_DATABASE_URL` names a disposable PostgreSQL. **NOT RUN in the delivering run** |
| Hosted staging backup, restore, rollback, erasure | **NOT RUN (OD-HOSTED)** |
| Restore time and size at real data volume; off-site copy; key escrow; retention destruction schedule | Not exercised |
| Legal confirmation of the 35-day window | Open (owner and legal counsel) |
