# Wave 4 Task 06 — pre-change recovery gap matrix

Baseline: PR #271 merged at `88a5ce4e4d5e92bee75fbec2721ce28e73d9ac6d`.
All six baseline main workflows passed. Permanent checkout retained; 45 worktrees,
49 protected files and all existing branches inventoried. Existing artwork is untracked.

| Requirement | Existing implementation | Gap / focused disposition |
|---|---|---|
| Whole application database | 05B pg_dump/custom archive, checksums, all-table counts | Counts/revision are read outside the dump snapshot. Qualified capture will freeze writes and bind a PostgreSQL exported snapshot and schema evidence. |
| Checkpoints and run controls | In the dump when in the same database; 0048 rows protected | Checkpoint URL can be separate. Qualified path must explicitly verify co-location/public schema and refuse separate stores rather than omit them. |
| Budget / unsettled usage | Durable 05C counters, unknown reservations, kill; 0048 admission | Historical recovery can roll spending backward. Persistent database recovery hold must precede restore, block access/AI/admission/promotion and require authorized reconciliation. |
| Private documents | Every file copied with checksum | Missing roots/referenced files and SQL/file timing require strict completeness checks, drain, locks and content fingerprints. |
| Knowledge and embedding identity | 02A registry/index manifest, files/chunks/checksum | Live Chroma opening may rewrite files; qualified capture must inspect a scratch copy and preserve identity without paid embedding calls. |
| Manifest confidentiality | AES-256-GCM files, HMAC manifest | Retrieval probe text currently lives in clear metadata. Qualified sets must seal probe evidence too. |
| Erasure ledger | Independent append-only hash chain | Missing files look empty; a truncated/rehashable chain has no trusted head. Require independent signed external head/anchor and refuse missing/stale/tampered history. |
| PostgreSQL erasure/rewrite | Manual procedure only; SQLite AccountDeletionService reuse | Extend the same erasure engine to PostgreSQL and official checkpoint deletion; keep originals immutable. Existing privacy deletion of per-user usage facts remains intentional; non-identifying monetary ledger must survive. |
| Restore targets and failures | Empty-target checks, dry-run default | Add atomic SQL restore, durable pre-restore quarantine, strict qualified component checks and a verified receipt only after full validation/erasure. No automatic promotion. |
| Current-head rollback | Seeder exists only for 0043 | Add synthetic 0048 protection fixture. Never delete protected control/budget/usage rows to force downgrade; qualify new-target restore alternative. |
| Operator image | API lacks PG client tools | Narrow, separately invoked recovery image/profile using verified application build and PG16 clients; no normal-startup backup/restore and no Docker socket. |
| Legacy helpers | restore.sh allows --clean/FORCE; optional tar components | Explicitly legacy/unqualified, guarded against hosted accidental invocation; qualified runner never calls them. |
| Off-host/custody | Runbook procedure | Verify transfer to independent disposable local storage; source/set/ledger/key access separation, escrow/rotation/retention remain owner decisions. No provider chosen or cloud provisioned. |

Not included: independent erasure history/keys (must remain outside sets), secret-store
master key, image binaries, live provider receipts, external logs/snapshots/replicas,
TLS certificates/ClamAV signatures and untracked curated corpora. Release metadata
binds required artifacts; it does not reconstruct missing credentials or corpora.
Separate checkpoint databases are a refused configuration, not a supported omission.

35-day retention/erasure defaults remain unapproved engineering policy. No PG/LG
acceptance, hosted deployment, paid evaluation, real data or operator key generation.
